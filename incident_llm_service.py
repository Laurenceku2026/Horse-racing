"""
Incident LLM 缓存服务
- 规则分数为主，LLM impact 叠加（各限 -20~+20，合计封顶）
- 热路径只读 Supabase 缓存，不自动调用 DeepSeek
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set, Tuple

import requests

HKT = timezone(timedelta(hours=8))
INCIDENT_SCAN_LIMIT = 5000

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
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
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
        "prompt_tokens": int(prompt_tokens or 0),
        "completion_tokens": int(completion_tokens or 0),
        "total_tokens": int(total_tokens or 0),
    }
    try:
        url = f"{supabase_url}/rest/v1/incident_llm_cache"
        hdrs = dict(headers)
        hdrs["Prefer"] = "resolution=merge-duplicates,return=minimal"
        resp = requests.post(url, headers=hdrs, json=payload, timeout=20)
        if resp.status_code in (200, 201, 204):
            return True
        if resp.status_code == 400 and "prompt_tokens" in (resp.text or ""):
            payload.pop("prompt_tokens", None)
            payload.pop("completion_tokens", None)
            payload.pop("total_tokens", None)
            resp = requests.post(url, headers=hdrs, json=payload, timeout=20)
            return resp.status_code in (200, 201, 204)
        return False
    except Exception as exc:
        print(f"写入 incident_llm_cache 失败: {exc}")
        return False


def analyze_incident_with_deepseek_api(incident_text: str, secrets: Dict) -> Dict:
    """调用 DeepSeek API（仅用于批量补全/管理员，不在热路径自动调用）。"""
    default = {
        "llm_impact_score": 0,
        "incident_type": "normal",
        "suggestion": "",
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }
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
        usage = getattr(response, "usage", None)
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        total_tokens = int(getattr(usage, "total_tokens", 0) or 0)
        match = re.search(r"\{[^{}]*\}", result_text)
        if match:
            data = json.loads(match.group())
            return {
                "llm_impact_score": float(data.get("impact_score", 0)),
                "incident_type": str(data.get("incident_type", "其他")),
                "suggestion": str(data.get("suggestion", "")),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            }
    except Exception as exc:
        print(f"DeepSeek incident 分析失败: {exc}")
    return default


def format_datetime_hkt(iso_str: str) -> str:
    """Supabase ISO8601 → 香港时间字符串。"""
    if not iso_str:
        return "-"
    try:
        normalized = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(HKT).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return (iso_str or "")[:19].replace("T", " ")


def fetch_past_incident_texts(
    supabase_url: str,
    headers: Dict,
    *,
    limit: int = INCIDENT_SCAN_LIMIT,
) -> Tuple[List[str], bool]:
    """从 past_performances_v2 拉取 incident 文本。返回 (texts, truncated)。"""
    if not supabase_url or not headers:
        return [], False
    try:
        url = (
            f"{supabase_url}/rest/v1/past_performances_v2"
            f"?select=incident&incident=not.is.null&limit={limit}"
        )
        resp = requests.get(url, headers=headers, timeout=60)
        if resp.status_code != 200:
            return [], False
        rows = resp.json() or []
        texts = [r.get("incident", "") for r in rows if r.get("incident")]
        return texts, len(rows) >= limit
    except Exception as exc:
        print(f"读取 past_performances_v2 incident 失败: {exc}")
        return [], False


def fetch_cached_incident_hashes(supabase_url: str, headers: Dict) -> Set[str]:
    """分页读取 incident_llm_cache 全部 hash。"""
    cached: Set[str] = set()
    if not supabase_url or not headers:
        return cached
    page_size = 1000
    offset = 0
    try:
        while True:
            url = (
                f"{supabase_url}/rest/v1/incident_llm_cache"
                f"?select=incident_text_hash&limit={page_size}&offset={offset}"
            )
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code != 200:
                break
            rows = resp.json() or []
            if not rows:
                break
            cached.update(str(r.get("incident_text_hash") or "") for r in rows if r.get("incident_text_hash"))
            if len(rows) < page_size:
                break
            offset += page_size
    except Exception as exc:
        print(f"读取 incident_llm_cache hash 失败: {exc}")
    return cached


def count_missing_incident_cache(
    supabase_url: str,
    headers: Dict,
    *,
    limit: int = INCIDENT_SCAN_LIMIT,
) -> Dict:
    """统计未写入 incident_llm_cache 的唯一 incident 数。"""
    texts, truncated = fetch_past_incident_texts(supabase_url, headers, limit=limit)
    unique_hashes: Set[str] = set()
    incident_rows = 0
    for text in texts:
        if is_empty_incident(text):
            continue
        incident_rows += 1
        unique_hashes.add(incident_text_hash(text))

    cached_hashes = fetch_cached_incident_hashes(supabase_url, headers)
    missing_hashes = unique_hashes - cached_hashes
    cached_unique = len(unique_hashes & cached_hashes)

    return {
        "missing_unique": len(missing_hashes),
        "total_unique": len(unique_hashes),
        "cached_unique": cached_unique,
        "incident_rows_scanned": incident_rows,
        "scan_limit": limit,
        "truncated": truncated,
    }


def batch_cache_missing_incidents(
    incident_texts: List[str],
    supabase_url: str,
    headers: Dict,
    secrets: Dict,
    max_new_calls: int = 20,
) -> Dict:
    """批量补全未缓存的 incident（限制单次 API 调用数）。"""
    stats = {
        "cached": 0,
        "analyzed": 0,
        "skipped": 0,
        "errors": 0,
        "remaining_missing": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }
    seen = set()
    cached_hashes = fetch_cached_incident_hashes(supabase_url, headers)
    for text in incident_texts:
        if is_empty_incident(text):
            stats["skipped"] += 1
            continue
        h = incident_text_hash(text)
        if h in seen:
            continue
        seen.add(h)
        if h in cached_hashes:
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
            prompt_tokens=result.get("prompt_tokens", 0),
            completion_tokens=result.get("completion_tokens", 0),
            total_tokens=result.get("total_tokens", 0),
        )
        if ok:
            stats["analyzed"] += 1
            stats["prompt_tokens"] = stats.get("prompt_tokens", 0) + int(result.get("prompt_tokens", 0) or 0)
            stats["completion_tokens"] = stats.get("completion_tokens", 0) + int(result.get("completion_tokens", 0) or 0)
            stats["total_tokens"] = stats.get("total_tokens", 0) + int(result.get("total_tokens", 0) or 0)
            cached_hashes.add(h)
        else:
            stats["errors"] += 1
    missing_stats = count_missing_incident_cache(supabase_url, headers)
    stats["remaining_missing"] = missing_stats.get("missing_unique", 0)
    stats["missing_stats"] = missing_stats
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


def _sum_incident_cache_tokens(
    supabase_url: str,
    headers: Dict,
    *,
    created_since: Optional[str] = None,
) -> Dict:
    """分页汇总 incident_llm_cache 的 Token 用量。"""
    totals = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "rows_with_tokens": 0,
        "rows_scanned": 0,
        "columns_available": True,
    }
    if not supabase_url or not headers:
        return totals

    page_size = 1000
    offset = 0
    since_dt = None
    if created_since:
        try:
            since_dt = datetime.fromisoformat(created_since.replace("Z", "+00:00"))
            if since_dt.tzinfo is None:
                since_dt = since_dt.replace(tzinfo=timezone.utc)
        except Exception:
            since_dt = None

    select_cols = "prompt_tokens,completion_tokens,total_tokens,created_at"
    while True:
        try:
            url = (
                f"{supabase_url}/rest/v1/incident_llm_cache"
                f"?select={select_cols}&limit={page_size}&offset={offset}"
            )
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code == 400 and "prompt_tokens" in (resp.text or ""):
                totals["columns_available"] = False
                break
            if resp.status_code != 200:
                break
            rows = resp.json() or []
            if not rows:
                break
            for row in rows:
                totals["rows_scanned"] += 1
                if since_dt:
                    created_raw = row.get("created_at") or ""
                    try:
                        created_dt = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
                        if created_dt.tzinfo is None:
                            created_dt = created_dt.replace(tzinfo=timezone.utc)
                        if created_dt < since_dt:
                            continue
                    except Exception:
                        continue
                prompt = int(row.get("prompt_tokens") or 0)
                completion = int(row.get("completion_tokens") or 0)
                total = int(row.get("total_tokens") or 0)
                if total <= 0 and prompt <= 0 and completion <= 0:
                    continue
                totals["rows_with_tokens"] += 1
                totals["prompt_tokens"] += prompt
                totals["completion_tokens"] += completion
                totals["total_tokens"] += total if total > 0 else (prompt + completion)
            if len(rows) < page_size:
                break
            offset += page_size
        except Exception as exc:
            print(f"汇总 incident_llm_cache Token 失败: {exc}")
            break
    return totals


def fetch_incident_llm_usage_stats(
    supabase_url: str,
    headers: Dict,
) -> Dict:
    """DeepSeek 用量代理指标：每条 cache 行 ≈ 一次 API 分析写入。"""
    now = datetime.now(timezone.utc)
    since_24h = (now - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S")
    since_7d = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S")

    stats = {
        "cache_total": _count_incident_cache_rows(supabase_url, headers),
        "cache_24h": _count_incident_cache_rows(supabase_url, headers, created_since=since_24h),
        "cache_7d": _count_incident_cache_rows(supabase_url, headers, created_since=since_7d),
        "latest_at": "",
        "recent_rows": [],
        "tokens_total": _sum_incident_cache_tokens(supabase_url, headers),
        "tokens_24h": _sum_incident_cache_tokens(supabase_url, headers, created_since=since_24h),
        "tokens_7d": _sum_incident_cache_tokens(supabase_url, headers, created_since=since_7d),
    }

    try:
        url = (
            f"{supabase_url}/rest/v1/incident_llm_cache"
            f"?select=incident_text,llm_impact_score,incident_type,model_version,created_at,"
            f"prompt_tokens,completion_tokens,total_tokens"
            f"&order=created_at.desc&limit=15"
        )
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code == 400 and "prompt_tokens" in (resp.text or ""):
            url = (
                f"{supabase_url}/rest/v1/incident_llm_cache"
                f"?select=incident_text,llm_impact_score,incident_type,model_version,created_at"
                f"&order=created_at.desc&limit=15"
            )
            resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code == 200 and resp.json():
            rows = resp.json()
            stats["recent_rows"] = rows
            latest_raw = rows[0].get("created_at") or ""
            stats["latest_at"] = format_datetime_hkt(latest_raw)
    except Exception as exc:
        print(f"读取 incident_llm_cache 最近记录失败: {exc}")

    return stats
