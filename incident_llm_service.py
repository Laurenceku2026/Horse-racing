"""
Incident LLM 缓存服务
- 规则分数为主，LLM impact 叠加（各限 -20~+20，合计封顶）
- 热路径只读 Supabase 缓存，不自动调用 DeepSeek
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Dict, List, Optional, Tuple

import requests

EMPTY_INCIDENTS = frozenset({"", "无特别报告。", "無特別報告。", "None", "null"})


def incident_text_hash(text: str) -> str:
    normalized = (text or "").strip()
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()


def is_empty_incident(text: str) -> bool:
    return not text or text.strip() in EMPTY_INCIDENTS


def get_rule_incident_score(incident_text: str) -> float:
    from scoring_engine import calculate_incident_score
    return float(calculate_incident_score(incident_text or ""))


def get_llm_impact_from_cache(
    incident_text: str,
    supabase_url: str,
    headers: Optional[Dict],
) -> float:
    """只读缓存，未命中返回 0（不调 API）。"""
    if is_empty_incident(incident_text) or not supabase_url or not headers:
        return 0.0
    try:
        h = incident_text_hash(incident_text)
        url = (
            f"{supabase_url}/rest/v1/incident_llm_cache"
            f"?incident_text_hash=eq.{h}&select=llm_impact_score&limit=1"
        )
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200 and resp.json():
            return float(resp.json()[0].get("llm_impact_score") or 0)
    except Exception as exc:
        print(f"读取 incident_llm_cache 失败: {exc}")
    return 0.0


def get_combined_incident_adjustment(
    incident_text: str,
    supabase_url: str = "",
    headers: Optional[Dict] = None,
    llm_weight: float = 0.5,
) -> Tuple[float, float, float]:
    """
    返回 (combined, rule_score, llm_impact)
    combined = clamp(rule + llm_weight * llm_impact, -20, 20)
    """
    rule = get_rule_incident_score(incident_text)
    llm = get_llm_impact_from_cache(incident_text, supabase_url, headers)
    combined = max(-20.0, min(20.0, rule + llm_weight * llm))
    return combined, rule, llm


def save_incident_llm_cache(
    incident_text: str,
    llm_impact: float,
    incident_type: str,
    suggestion: str,
    supabase_url: str,
    headers: Dict,
    race_date: str = "",
    venue: str = "",
    race_no: Optional[int] = None,
    horse_no: str = "",
    model_version: str = "deepseek-chat",
) -> bool:
    if is_empty_incident(incident_text):
        return False
    payload = {
        "incident_text_hash": incident_text_hash(incident_text),
        "incident_text": incident_text[:2000],
        "race_date": race_date or None,
        "venue": venue or None,
        "race_no": race_no,
        "horse_no": str(horse_no) if horse_no else None,
        "rule_score": get_rule_incident_score(incident_text),
        "llm_impact_score": llm_impact,
        "incident_type": incident_type,
        "suggestion": suggestion[:200] if suggestion else "",
        "model_version": model_version,
    }
    try:
        url = f"{supabase_url}/rest/v1/incident_llm_cache"
        hdrs = dict(headers)
        hdrs["Prefer"] = "resolution=merge-duplicates,return=minimal"
        resp = requests.post(url, headers=hdrs, json=payload, timeout=20)
        return resp.status_code in (200, 201, 204)
    except Exception as exc:
        print(f"写入 incident_llm_cache 失败: {exc}")
        return False


def analyze_incident_with_deepseek_api(incident_text: str, secrets: Dict) -> Dict:
    """调用 DeepSeek API（仅用于批量补全/管理员，不在热路径自动调用）。"""
    default = {"llm_impact_score": 0, "incident_type": "normal", "suggestion": ""}
    if is_empty_incident(incident_text):
        return default
    try:
        from openai import OpenAI
    except ImportError:
        return default

    api_key = secrets.get("DEEPSEEK_API_KEY", "")
    base_url = secrets.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    if not api_key:
        return default

    client = OpenAI(api_key=api_key, base_url=base_url)
    prompt = f"""分析以下香港赛马竞赛事件报告，评估对马匹下一场表现的影响。
事件报告：{incident_text}

只返回 JSON：
{{"impact_score": -20到20的整数, "incident_type": "受阻/抢口/走外叠/出闸笨拙/健康问题/正常/其他", "suggestion": "20字内建议"}}"""

    try:
        response = client.chat.completions.create(
            model=secrets.get("DEEPSEEK_MODEL", "deepseek-chat"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=200,
        )
        result_text = response.choices[0].message.content or ""
        match = re.search(r"\{[^{}]*\}", result_text)
        if match:
            data = json.loads(match.group())
            return {
                "llm_impact_score": float(data.get("impact_score", 0)),
                "incident_type": str(data.get("incident_type", "其他")),
                "suggestion": str(data.get("suggestion", "")),
            }
    except Exception as exc:
        print(f"DeepSeek incident 分析失败: {exc}")
    return default


def batch_cache_missing_incidents(
    incident_texts: List[str],
    supabase_url: str,
    headers: Dict,
    secrets: Dict,
    max_new_calls: int = 20,
) -> Dict:
    """批量补全未缓存的 incident（限制单次 API 调用数）。"""
    stats = {"cached": 0, "analyzed": 0, "skipped": 0, "errors": 0}
    seen = set()
    for text in incident_texts:
        if is_empty_incident(text):
            stats["skipped"] += 1
            continue
        h = incident_text_hash(text)
        if h in seen:
            continue
        seen.add(h)
        if get_llm_impact_from_cache(text, supabase_url, headers) != 0 or _cache_exists(text, supabase_url, headers):
            stats["cached"] += 1
            continue
        if stats["analyzed"] >= max_new_calls:
            break
        result = analyze_incident_with_deepseek_api(text, secrets)
        ok = save_incident_llm_cache(
            text,
            result["llm_impact_score"],
            result["incident_type"],
            result["suggestion"],
            supabase_url,
            headers,
        )
        if ok:
            stats["analyzed"] += 1
        else:
            stats["errors"] += 1
    return stats


def _cache_exists(incident_text: str, supabase_url: str, headers: Dict) -> bool:
    try:
        h = incident_text_hash(incident_text)
        url = f"{supabase_url}/rest/v1/incident_llm_cache?incident_text_hash=eq.{h}&select=id&limit=1"
        resp = requests.get(url, headers=headers, timeout=10)
        return resp.status_code == 200 and bool(resp.json())
    except Exception:
        return False


def _count_incident_cache_rows(
    supabase_url: str,
    headers: Dict,
    *,
    created_since: Optional[str] = None,
) -> int:
    """Supabase count via Content-Range header."""
    if not supabase_url or not headers:
        return 0
    try:
        url = f"{supabase_url}/rest/v1/incident_llm_cache?select=id"
        if created_since:
            url += f"&created_at=gte.{created_since}"
        hdrs = dict(headers)
        hdrs["Prefer"] = "count=exact"
        hdrs["Range"] = "0-0"
        resp = requests.get(url, headers=hdrs, timeout=20)
        if resp.status_code not in (200, 206):
            return 0
        content_range = resp.headers.get("Content-Range", "")
        if "/" in content_range:
            total = content_range.split("/")[-1]
            if total.isdigit():
                return int(total)
        return len(resp.json()) if resp.json() else 0
    except Exception as exc:
        print(f"统计 incident_llm_cache 失败: {exc}")
        return 0


def fetch_incident_llm_usage_stats(
    supabase_url: str,
    headers: Dict,
) -> Dict:
    """DeepSeek 用量代理指标：每条 cache 行 ≈ 一次 API 分析写入。"""
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    since_24h = (now - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S")
    since_7d = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S")

    stats = {
        "cache_total": _count_incident_cache_rows(supabase_url, headers),
        "cache_24h": _count_incident_cache_rows(supabase_url, headers, created_since=since_24h),
        "cache_7d": _count_incident_cache_rows(supabase_url, headers, created_since=since_7d),
        "latest_at": "",
        "recent_rows": [],
    }

    try:
        url = (
            f"{supabase_url}/rest/v1/incident_llm_cache"
            f"?select=incident_text,llm_impact_score,incident_type,model_version,created_at"
            f"&order=created_at.desc&limit=15"
        )
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code == 200 and resp.json():
            rows = resp.json()
            stats["recent_rows"] = rows
            stats["latest_at"] = (rows[0].get("created_at") or "")[:19].replace("T", " ")
    except Exception as exc:
        print(f"读取 incident_llm_cache 最近记录失败: {exc}")

    return stats
