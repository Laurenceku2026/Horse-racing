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
from typing import Callable, Dict, List, Optional, Set, Tuple

import requests

HKT = timezone(timedelta(hours=8))
INCIDENT_SCAN_LIMIT = 5000
INCIDENT_LLM_CACHE_KEEP_LIMIT = 15000

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


def build_incident_llm_map_from_texts(
    incident_texts,
    supabase_url: str,
    headers: Optional[Dict],
    *,
    chunk_size: int = 100,
) -> Dict[str, float]:
    """批量读取 incident LLM 缓存（按 hash in 查询，不调用 DeepSeek）。"""
    if not supabase_url or not headers:
        return {}

    text_by_hash: Dict[str, str] = {}
    for text in incident_texts or []:
        if is_empty_incident(text):
            continue
        text_by_hash[incident_text_hash(text)] = text

    if not text_by_hash:
        return {}

    mapping: Dict[str, float] = {text: 0.0 for text in text_by_hash.values()}
    hash_list = list(text_by_hash.keys())
    chunk_size = max(20, min(int(chunk_size or 100), 150))

    for offset in range(0, len(hash_list), chunk_size):
        chunk = hash_list[offset: offset + chunk_size]
        hash_filter = ",".join(chunk)
        url = (
            f"{supabase_url}/rest/v1/incident_llm_cache"
            f"?incident_text_hash=in.({hash_filter})"
            f"&select=incident_text_hash,llm_impact_score"
        )
        try:
            resp = requests.get(url, headers=headers, timeout=60)
            if resp.status_code != 200:
                continue
            for row in resp.json() or []:
                h = row.get("incident_text_hash")
                text = text_by_hash.get(h)
                if text is not None:
                    mapping[text] = float(row.get("llm_impact_score") or 0)
        except Exception as exc:
            print(f"批量读取 incident_llm_cache 失败: {exc}")

    return mapping


def get_combined_incident_adjustment(
    incident_text: str,
    supabase_url: str = "",
    headers: Optional[Dict] = None,
    llm_weight: float = 0.5,
    incident_llm_map: Optional[Dict[str, float]] = None,
) -> Tuple[float, float, float]:
    """
    返回 (combined, rule_score, llm_impact)
    combined = clamp(rule + llm_weight * llm_impact, -20, 20)
    """
    rule = get_rule_incident_score(incident_text)
    llm = 0.0
    if not is_empty_incident(incident_text):
        if incident_llm_map is not None:
            llm = float(incident_llm_map.get(incident_text, 0.0) or 0.0)
        else:
            llm = get_llm_impact_from_cache(incident_text, supabase_url, headers)
    combined = max(-20.0, min(20.0, rule + llm_weight * llm))
    return combined, rule, llm


def incident_combined_feature_score(
    incident_text: str,
    incident_llm_map: Optional[Dict[str, float]] = None,
    supabase_url: str = "",
    headers: Optional[Dict] = None,
    llm_weight: float = 0.5,
) -> float:
    """ML/展示用 incident 特征分：规则分 + llm_weight×LLM 缓存分，范围 -20~+20。"""
    combined, _, _ = get_combined_incident_adjustment(
        incident_text,
        supabase_url,
        headers,
        llm_weight=llm_weight,
        incident_llm_map=incident_llm_map,
    )
    return combined


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
    horse_id: str = "",
    horse_name: str = "",
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
        "horse_id": str(horse_id) if horse_id else None,
        "horse_name": (horse_name or "")[:200] or None,
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
        if resp.status_code == 400 and ("prompt_tokens" in (resp.text or "") or "horse_name" in (resp.text or "")):
            payload.pop("prompt_tokens", None)
            payload.pop("completion_tokens", None)
            payload.pop("total_tokens", None)
            payload.pop("horse_id", None)
            payload.pop("horse_name", None)
            resp = requests.post(url, headers=hdrs, json=payload, timeout=20)
            return resp.status_code in (200, 201, 204)
        return False
    except Exception as exc:
        print(f"写入 incident_llm_cache 失败: {exc}")
        return False


def trim_incident_llm_cache(
    supabase_url: str,
    headers: Dict,
    keep: int = INCIDENT_LLM_CACHE_KEEP_LIMIT,
) -> Dict:
    """incident_llm_cache 超过 keep 时删除最旧记录（按 created_at, id）。"""
    keep_limit = max(1, int(keep or INCIDENT_LLM_CACHE_KEEP_LIMIT))
    result: Dict = {
        "deleted": 0,
        "kept": keep_limit,
        "total": 0,
        "error": None,
    }
    if not supabase_url:
        result["error"] = "supabase_url missing"
        return result
    payload = {"p_keep": keep_limit}
    rpc_urls = (
        f"{supabase_url}/rest/v1/rpc/trim_incident_llm_cache",
        f"{supabase_url}/rest/v1/rpc/trim_table_rows",
    )
    try:
        for idx, url in enumerate(rpc_urls):
            body = (
                payload
                if idx == 0
                else {
                    "p_table": "incident_llm_cache",
                    "p_keep": keep_limit,
                    "p_order_sql": "created_at ASC, id ASC",
                }
            )
            resp = requests.post(url, headers=headers, json=body, timeout=60)
            if resp.status_code != 200:
                if idx == 0:
                    continue
                result["error"] = f"HTTP {resp.status_code}: {(resp.text or '')[:300]}"
                return result
            row = resp.json() or {}
            result["deleted"] = int(row.get("deleted") or 0)
            result["kept"] = int(row.get("kept") or keep_limit)
            result["total"] = int(row.get("total") or 0)
            if row.get("error"):
                result["error"] = str(row.get("error"))
            return result
        result["error"] = "trim_incident_llm_cache RPC not installed"
        return result
    except Exception as exc:
        result["error"] = str(exc)
        print(f"trim_incident_llm_cache 失败: {exc}")
        return result


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


VENUE_LABELS_ZH = {"ST": "沙田", "HV": "跑馬地"}
VENUE_LABELS_EN = {"ST": "Sha Tin", "HV": "Happy Valley"}


def format_venue_label(venue: str, lang: str = "zh") -> str:
    code = (venue or "").strip().upper()
    if not code:
        return "-"
    labels = VENUE_LABELS_ZH if lang == "zh" else VENUE_LABELS_EN
    name = labels.get(code, code)
    return f"{name} ({code})" if lang == "zh" else code


def fetch_past_incident_records(
    supabase_url: str,
    headers: Dict,
    *,
    limit: int = INCIDENT_SCAN_LIMIT,
    race_dates: Optional[List[str]] = None,
) -> Tuple[List[Dict], bool]:
    """从 past_performances_v2 拉取含 incident 的往绩（含赛日/马匹元数据）。"""
    if not supabase_url or not headers:
        return [], False
    select_cols = "incident,race_date,venue,race_no,horse_no,horse_id,horse_name"
    try:
        if race_dates:
            clean_dates = sorted({d[:10] for d in race_dates if d})
            if not clean_dates:
                return [], False
            in_clause = ",".join(clean_dates)
            url = (
                f"{supabase_url}/rest/v1/past_performances_v2"
                f"?select={select_cols}"
                f"&incident=not.is.null&race_date=in.({in_clause})&limit={limit}"
            )
        else:
            url = (
                f"{supabase_url}/rest/v1/past_performances_v2"
                f"?select={select_cols}&incident=not.is.null&limit={limit}"
            )
        resp = requests.get(url, headers=headers, timeout=60)
        if resp.status_code != 200:
            return [], False
        rows = resp.json() or []
        records = [r for r in rows if r.get("incident") and not is_empty_incident(r.get("incident", ""))]
        return records, len(rows) >= limit
    except Exception as exc:
        print(f"读取 past_performances_v2 incident 记录失败: {exc}")
        return [], False


def _dedupe_incident_records(records: List[Dict]) -> Tuple[List[str], Dict[str, Dict]]:
    """按 incident 哈希去重，保留最新赛日的一条元数据。"""
    pending_texts: List[str] = []
    meta_by_hash: Dict[str, Dict] = {}
    seen: Set[str] = set()
    sorted_records = sorted(
        records,
        key=lambda r: str(r.get("race_date") or ""),
        reverse=True,
    )
    for rec in sorted_records:
        text = rec.get("incident", "")
        if is_empty_incident(text):
            continue
        h = incident_text_hash(text)
        if h in seen:
            continue
        seen.add(h)
        pending_texts.append(text)
        meta_by_hash[h] = {
            "race_date": (rec.get("race_date") or "")[:10] or None,
            "venue": rec.get("venue") or "",
            "race_no": rec.get("race_no"),
            "horse_no": rec.get("horse_no") or "",
            "horse_id": rec.get("horse_id") or "",
            "horse_name": rec.get("horse_name") or "",
        }
    return pending_texts, meta_by_hash


def build_incident_context_maps(
    supabase_url: str,
    headers: Dict,
    *,
    perf_limit: int = 50000,
) -> Dict:
    """构建 incident 哈希 / 赛日键 → 马匹上下文，及 horse_id → 马名。"""
    by_hash: Dict[str, Dict] = {}
    by_race_key: Dict[str, Dict] = {}
    horse_names: Dict[str, str] = {}
    if not supabase_url or not headers:
        return {"by_hash": by_hash, "by_race_key": by_race_key, "horse_names": horse_names}

    select_cols = "incident,race_date,venue,race_no,horse_no,horse_id,horse_name"
    page_size = 1000
    offset = 0
    total_loaded = 0
    try:
        while total_loaded < perf_limit:
            url = (
                f"{supabase_url}/rest/v1/past_performances_v2"
                f"?select={select_cols}&incident=not.is.null"
                f"&order=race_date.desc&limit={page_size}&offset={offset}"
            )
            resp = requests.get(url, headers=headers, timeout=60)
            if resp.status_code != 200:
                break
            rows = resp.json() or []
            if not rows:
                break
            for rec in rows:
                text = rec.get("incident", "")
                if is_empty_incident(text):
                    continue
                h = incident_text_hash(text)
                if h not in by_hash:
                    by_hash[h] = {
                        "race_date": (rec.get("race_date") or "")[:10] or "",
                        "venue": rec.get("venue") or "",
                        "race_no": rec.get("race_no"),
                        "horse_no": str(rec.get("horse_no") or ""),
                        "horse_id": str(rec.get("horse_id") or ""),
                        "horse_name": rec.get("horse_name") or "",
                    }
                race_key = _incident_race_key(
                    rec.get("race_date"),
                    rec.get("venue"),
                    rec.get("race_no"),
                    rec.get("horse_no"),
                )
                if race_key and race_key not in by_race_key:
                    by_race_key[race_key] = {
                        "horse_id": str(rec.get("horse_id") or ""),
                        "horse_name": rec.get("horse_name") or "",
                        "incident_text_hash": h,
                    }
            total_loaded += len(rows)
            if len(rows) < page_size:
                break
            offset += page_size
    except Exception as exc:
        print(f"构建 incident 上下文失败: {exc}")

    try:
        horses_url = f"{supabase_url}/rest/v1/horses_v2?select=horse_id,name_zh,name_en&limit=50000"
        resp = requests.get(horses_url, headers=headers, timeout=60)
        if resp.status_code == 200:
            for h in resp.json() or []:
                hid = str(h.get("horse_id") or "")
                if hid:
                    horse_names[hid] = h.get("name_zh") or h.get("name_en") or hid
    except Exception as exc:
        print(f"读取 horses_v2 失败: {exc}")

    return {"by_hash": by_hash, "by_race_key": by_race_key, "horse_names": horse_names}


def _incident_race_key(
    race_date: object,
    venue: object,
    race_no: object,
    horse_no: object,
) -> str:
    rd = str(race_date or "")[:10]
    vn = str(venue or "").strip().upper()
    rn = str(race_no or "").strip()
    hn = str(horse_no or "").strip()
    if not rd or not vn or not rn or not hn:
        return ""
    return f"{rd}|{vn}|{rn}|{hn}"


def resolve_incident_cache_display(
    row: Dict,
    ctx: Dict,
    *,
    lang: str = "zh",
) -> Dict:
    """合并 cache 行 + 往绩上下文，解析赛日/马匹显示字段。"""
    by_hash = ctx.get("by_hash") or {}
    by_race_key = ctx.get("by_race_key") or {}
    horse_names = ctx.get("horse_names") or {}

    text = row.get("incident_text") or ""
    h = row.get("incident_text_hash") or (incident_text_hash(text) if text else "")
    meta = by_hash.get(h, {})

    race_date = (row.get("race_date") or meta.get("race_date") or "")[:10]
    venue = row.get("venue") or meta.get("venue") or ""
    race_no = row.get("race_no") if row.get("race_no") is not None else meta.get("race_no")
    horse_no = str(row.get("horse_no") or meta.get("horse_no") or "")
    horse_id = str(row.get("horse_id") or meta.get("horse_id") or "")
    horse_name = (row.get("horse_name") or meta.get("horse_name") or "").strip()

    if not horse_name and horse_id:
        horse_name = horse_names.get(horse_id, "")
    if not horse_name:
        race_key = _incident_race_key(race_date, venue, race_no, horse_no)
        if race_key:
            rk_meta = by_race_key.get(race_key, {})
            horse_name = rk_meta.get("horse_name") or ""
            if not horse_id:
                horse_id = rk_meta.get("horse_id") or ""

    race_label = f"第{race_no}场" if lang == "zh" and race_no else (f"R{race_no}" if race_no else "-")
    return {
        "race_date": race_date or "-",
        "venue_label": format_venue_label(venue, lang) if venue else "-",
        "race_label": race_label,
        "horse_no": horse_no or "-",
        "horse_id": horse_id or "-",
        "horse_name": horse_name or "-",
        "incident_text": text,
    }


def search_incident_llm_cache(
    supabase_url: str,
    headers: Dict,
    *,
    race_date_from: str = "",
    race_date_to: str = "",
    venue: str = "",
    keyword: str = "",
    page: int = 1,
    page_size: int = 50,
    order: str = "created_at.desc",
) -> Dict:
    """分页查阅 incident_llm_cache（管理员）。"""
    result = {"rows": [], "total": 0, "page": max(1, page), "page_size": page_size}
    if not supabase_url or not headers:
        return result

    page_size = max(10, min(int(page_size or 50), 200))
    page = max(1, int(page or 1))
    offset = (page - 1) * page_size

    select_cols = (
        "id,incident_text_hash,incident_text,race_date,venue,race_no,horse_no,horse_id,horse_name,"
        "rule_score,llm_impact_score,incident_type,suggestion,model_version,"
        "prompt_tokens,completion_tokens,total_tokens,created_at"
    )
    url = f"{supabase_url}/rest/v1/incident_llm_cache?select={select_cols}"
    if race_date_from:
        url += f"&race_date=gte.{race_date_from}"
    if race_date_to:
        url += f"&race_date=lte.{race_date_to}"
    if venue and venue.upper() in ("ST", "HV"):
        url += f"&venue=eq.{venue.upper()}"
    kw = (keyword or "").strip()
    if kw:
        from urllib.parse import quote
        url += f"&incident_text=ilike.{quote(f'%{kw}%')}"
    url += f"&order={order}&limit={page_size}&offset={offset}"

    try:
        hdrs = dict(headers)
        hdrs["Prefer"] = "count=exact"
        resp = requests.get(url, headers=hdrs, timeout=30)
        if resp.status_code == 400 and (
            "prompt_tokens" in (resp.text or "")
            or "horse_name" in (resp.text or "")
            or "horse_id" in (resp.text or "")
        ):
            select_cols = (
                "id,incident_text_hash,incident_text,race_date,venue,race_no,horse_no,"
                "rule_score,llm_impact_score,incident_type,suggestion,model_version,created_at"
            )
            url = url.replace(
                "id,incident_text_hash,incident_text,race_date,venue,race_no,horse_no,"
                "rule_score,llm_impact_score,incident_type,suggestion,model_version,"
                "prompt_tokens,completion_tokens,total_tokens,created_at",
                select_cols,
            )
            resp = requests.get(url, headers=hdrs, timeout=30)
        if resp.status_code not in (200, 206):
            return result
        result["rows"] = resp.json() or []
        content_range = resp.headers.get("Content-Range", "")
        if "/" in content_range:
            total = content_range.split("/")[-1]
            if total.isdigit():
                result["total"] = int(total)
        if not result["total"]:
            result["total"] = len(result["rows"])
    except Exception as exc:
        print(f"查阅 incident_llm_cache 失败: {exc}")
    return result


def fetch_past_incident_texts(
    supabase_url: str,
    headers: Dict,
    *,
    limit: int = INCIDENT_SCAN_LIMIT,
) -> Tuple[List[str], bool]:
    """从 past_performances_v2 拉取 incident 文本。返回 (texts, truncated)。"""
    records, truncated = fetch_past_incident_records(supabase_url, headers, limit=limit)
    texts, _ = _dedupe_incident_records(records)
    return texts, truncated


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


def get_recent_race_dates_with_incidents(
    supabase_url: str,
    headers: Dict,
    *,
    days_back: int = 7,
    days_forward: int = 1,
) -> List[str]:
    """取得近 N 天（含今天/明日）含 incident 的赛日列表。"""
    if not supabase_url or not headers:
        return []
    today = datetime.now(HKT).date()
    start = (today - timedelta(days=days_back)).isoformat()
    end = (today + timedelta(days=days_forward)).isoformat()
    try:
        url = (
            f"{supabase_url}/rest/v1/past_performances_v2"
            f"?select=race_date&incident=not.is.null"
            f"&race_date=gte.{start}&race_date=lte.{end}&limit=10000"
        )
        resp = requests.get(url, headers=headers, timeout=60)
        if resp.status_code != 200:
            return []
        dates = sorted(
            {
                str(r.get("race_date") or "")[:10]
                for r in (resp.json() or [])
                if r.get("race_date")
            }
        )
        return dates
    except Exception as exc:
        print(f"读取近赛日 incident 失败: {exc}")
        return []


def get_upcoming_meeting_dates(
    supabase_url: str,
    headers: Dict,
    *,
    days_ahead: int = 14,
) -> List[str]:
    """本地赛程表中的未来赛日（新赛期）。"""
    if not supabase_url or not headers:
        return []
    today = datetime.now(HKT).date().isoformat()
    end = (datetime.now(HKT).date() + timedelta(days=days_ahead)).isoformat()
    try:
        url = (
            f"{supabase_url}/rest/v1/races"
            f"?select=race_date&race_date=gte.{today}&race_date=lte.{end}&limit=5000"
        )
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code != 200:
            return []
        return sorted(
            {
                str(r.get("race_date") or "")[:10]
                for r in (resp.json() or [])
                if r.get("race_date")
            }
        )
    except Exception as exc:
        print(f"读取未来赛日失败: {exc}")
        return []


def fetch_incident_texts_for_race_dates(
    supabase_url: str,
    headers: Dict,
    race_dates: List[str],
    *,
    limit: int = INCIDENT_SCAN_LIMIT,
) -> Tuple[List[str], bool]:
    """按赛日拉取 incident 文本。"""
    records, truncated = fetch_past_incident_records(
        supabase_url, headers, limit=limit, race_dates=race_dates
    )
    texts, _ = _dedupe_incident_records(records)
    return texts, truncated


def fetch_incident_texts_for_race_dates_with_meta(
    supabase_url: str,
    headers: Dict,
    race_dates: List[str],
    *,
    limit: int = INCIDENT_SCAN_LIMIT,
) -> Tuple[List[str], Dict[str, Dict], bool]:
    records, truncated = fetch_past_incident_records(
        supabase_url, headers, limit=limit, race_dates=race_dates
    )
    texts, meta = _dedupe_incident_records(records)
    return texts, meta, truncated


def run_auto_incident_backfill(
    supabase_url: str,
    headers: Dict,
    secrets: Dict,
    *,
    days_back: int = 7,
    days_forward: int = 1,
    include_upcoming_meetings: bool = True,
    max_new_calls: int = 500,
    fill_all: bool = False,
) -> Dict:
    """
    赛日自动补全：检查近赛日 + 本地新赛期相关往绩中的未缓存 incident。
    供 GitHub Actions / 管理员触发；普通用户界面不调用。
    """
    recent_dates = get_recent_race_dates_with_incidents(
        supabase_url, headers, days_back=days_back, days_forward=days_forward
    )
    upcoming_dates = (
        get_upcoming_meeting_dates(supabase_url, headers)
        if include_upcoming_meetings
        else []
    )
    target_dates = sorted(set(recent_dates) | set(upcoming_dates))
    texts, truncated = fetch_incident_texts_for_race_dates(
        supabase_url, headers, target_dates, limit=INCIDENT_SCAN_LIMIT
    )
    if not texts:
        return {
            "analyzed": 0,
            "cached": 0,
            "skipped": 0,
            "errors": 0,
            "remaining_missing": 0,
            "target_dates": target_dates,
            "message": "no incidents for target dates",
        }
    stats = batch_cache_missing_incidents(
        texts,
        supabase_url,
        headers,
        secrets,
        max_new_calls=max_new_calls,
        fill_all=fill_all,
    )
    stats["target_dates"] = target_dates
    stats["scan_truncated"] = truncated
    stats["mode"] = "auto"
    return stats


def estimate_backfill_tokens(remaining_calls: int, tokens_total_stats: Optional[Dict] = None) -> Dict:
    """根据历史 Token 均值估算补全费用规模（仅供参考）。"""
    default_per_call = 450
    avg_per_call = default_per_call
    if tokens_total_stats:
        rows = int(tokens_total_stats.get("rows_with_tokens") or 0)
        total = int(tokens_total_stats.get("total_tokens") or 0)
        if rows > 0 and total > 0:
            avg_per_call = max(100, int(total / rows))
    est_tokens = remaining_calls * avg_per_call
    return {
        "remaining_calls": remaining_calls,
        "avg_tokens_per_call": avg_per_call,
        "estimated_total_tokens": est_tokens,
    }


def batch_cache_missing_incidents(
    incident_texts: List[str],
    supabase_url: str,
    headers: Dict,
    secrets: Dict,
    max_new_calls: int = 20,
    *,
    fill_all: bool = False,
    progress_callback: Optional[Callable[[Dict], None]] = None,
) -> Dict:
    """批量补全未缓存的 incident。fill_all=True 时不限制本次 API 调用数。"""
    stats = {
        "cached": 0,
        "analyzed": 0,
        "skipped": 0,
        "errors": 0,
        "remaining_missing": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "fill_all": fill_all,
        "planned_calls": 0,
    }
    seen = set()
    cached_hashes = fetch_cached_incident_hashes(supabase_url, headers)
    all_records, _ = fetch_past_incident_records(supabase_url, headers, limit=INCIDENT_SCAN_LIMIT)
    _, meta_by_hash = _dedupe_incident_records(all_records)
    if incident_texts:
        source_texts = incident_texts
    else:
        source_texts, _ = _dedupe_incident_records(all_records)
    pending_unique: List[str] = []
    for text in source_texts:
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
        pending_unique.append(text)
    stats["planned_calls"] = len(pending_unique) if fill_all else min(len(pending_unique), max_new_calls)

    model_version = str(secrets.get("DEEPSEEK_MODEL", "deepseek-chat"))
    for text in pending_unique:
        if not fill_all and stats["analyzed"] >= max_new_calls:
            break
        h = incident_text_hash(text)
        meta = meta_by_hash.get(h, {})
        result = analyze_incident_with_deepseek_api(text, secrets)
        ok = save_incident_llm_cache(
            text,
            result["llm_impact_score"],
            result["incident_type"],
            result["suggestion"],
            supabase_url,
            headers,
            race_date=meta.get("race_date") or "",
            venue=meta.get("venue") or "",
            race_no=meta.get("race_no"),
            horse_no=meta.get("horse_no") or "",
            horse_id=meta.get("horse_id") or "",
            horse_name=meta.get("horse_name") or "",
            model_version=model_version,
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
            if progress_callback:
                progress_callback(dict(stats))
        else:
            stats["errors"] += 1
    missing_stats = count_missing_incident_cache(supabase_url, headers)
    stats["remaining_missing"] = missing_stats.get("missing_unique", 0)
    stats["missing_stats"] = missing_stats
    trim_result = trim_incident_llm_cache(supabase_url, headers)
    stats["trim"] = trim_result
    if trim_result.get("deleted", 0) > 0:
        print(
            f"incident_llm_cache 清理：删除 {trim_result['deleted']} 条，保留上限 {trim_result.get('kept', INCIDENT_LLM_CACHE_KEEP_LIMIT)}"
        )
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
