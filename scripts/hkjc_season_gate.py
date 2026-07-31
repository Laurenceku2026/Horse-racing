#!/usr/bin/env python3
"""
HKJC 马季 / 休赛期自动检测（供 GitHub Actions 使用）。

官方赛期参考（香港赛马会）：
  - 2025/26：2025-09-07 开锣 → 2026-07-12/15 煞科
  - 2026/27：2026-09-06 开锣（已公布）
  - 规律：约 9 月初开锣，7 月中煞科；其间约 6–8 周休赛

判定策略（混合）：
  1) 优先查 hkjc-api-server /api/meetings：有活跃赛日 → 赛季中
  2) API 返回空列表 → 休赛 / 无赛程
  3) API 失败时回退日历软窗口（香港时间）：
       7/16–8/31、9/1–9/5 → 休赛
       其余 → 视为赛季中（继续跑采集，避免误停）

stdout 仅输出一行：IN_SEASON 或 OFF_SEASON
exit code 恒为 0（由 workflow 根据输出决定是否跳过）
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

HKT = timezone(timedelta(hours=8))
DEFAULT_API_BASE = "https://hkjc-api-server.onrender.com"


def now_hkt() -> datetime:
    return datetime.now(HKT)


def soft_calendar_off_season(dt: datetime | None = None) -> bool:
    """典型休赛窗口（不必精确到每年开锣日）。"""
    dt = dt or now_hkt()
    m, d = dt.month, dt.day
    if m == 8:
        return True
    if m == 7 and d >= 16:
        return True
    if m == 9 and d <= 5:
        return True
    return False


def fetch_active_meetings(api_base: str, timeout: float = 25.0):
    """
    返回：
      list  — API 成功（可能为空）
      None  — 请求失败
    """
    base = (api_base or DEFAULT_API_BASE).rstrip("/")
    url = f"{base}/api/meetings?detailed=0"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"meetings API unavailable: {exc}", file=sys.stderr)
        return None

    if not isinstance(payload, dict) or not payload.get("success", True):
        print(f"meetings API unexpected payload: {payload!r}", file=sys.stderr)
        return None

    data = payload.get("data")
    if data is None:
        return []
    if isinstance(data, list):
        return data
    print(f"meetings API data is not a list: {type(data)}", file=sys.stderr)
    return None


LOCAL_VENUE_CODES = {"ST", "HV", "SHA TIN", "HAPPY VALLEY"}


def _meeting_date(meeting: dict) -> str:
    for key in ("date", "race_date", "meetingDate", "meeting_date"):
        val = meeting.get(key)
        if val:
            return str(val)[:10]
    return ""


def _is_local_meeting(meeting: dict) -> bool:
    """只认本地沙田/跑马地，忽略海外转播（S1/S4 等）。"""
    raw = (
        meeting.get("venueCode")
        or meeting.get("venue")
        or meeting.get("venue_code")
        or ""
    )
    code = str(raw).strip().upper()
    if code in LOCAL_VENUE_CODES:
        return True
    # 兼容中文名
    name = str(meeting.get("venueName") or meeting.get("venue_name") or "")
    if "沙田" in name or "跑馬" in name or "跑马" in name or "Sha Tin" in name or "Happy Valley" in name:
        return True
    return False


def has_near_term_local_meetings(
    meetings: list,
    today: str,
    *,
    within_days: int = 14,
) -> bool:
    """是否有 [today, today+within_days] 内的本地赛日。"""
    try:
        start = datetime.strptime(today, "%Y-%m-%d").date()
    except ValueError:
        return False
    end = start + timedelta(days=max(0, int(within_days)))
    end_s = end.strftime("%Y-%m-%d")
    for m in meetings:
        if not isinstance(m, dict) or not _is_local_meeting(m):
            continue
        d = _meeting_date(m)
        if d and today <= d <= end_s:
            return True
    return False


def detect_season(api_base: str | None = None) -> str:
    dt = now_hkt()
    today = dt.strftime("%Y-%m-%d")
    soft_off = soft_calendar_off_season(dt)
    print(
        f"HKT now={dt.strftime('%Y-%m-%d %H:%M:%S')} soft_off={soft_off}",
        file=sys.stderr,
    )

    meetings = fetch_active_meetings(api_base or os.environ.get("HKJC_API_URL", DEFAULT_API_BASE))
    if isinstance(meetings, list):
        local = [m for m in meetings if isinstance(m, dict) and _is_local_meeting(m)]
        n_all, n_local = len(meetings), len(local)
        near = has_near_term_local_meetings(meetings, today, within_days=14)
        any_future = has_near_term_local_meetings(meetings, today, within_days=370)
        print(
            f"meetings={n_all} local={n_local} near14_local={near} any_future_local={any_future}",
            file=sys.stderr,
        )
        if soft_off:
            # 休赛窗口：只认近 14 天本地赛（新季开锣前可提前启动）
            return "IN_SEASON" if near else "OFF_SEASON"
        return "IN_SEASON" if any_future else "OFF_SEASON"

    # API 失败：日历回退
    if soft_off:
        print("API failed + soft off-season → OFF_SEASON", file=sys.stderr)
        return "OFF_SEASON"
    print("API failed + calendar in-season → IN_SEASON (try collect)", file=sys.stderr)
    return "IN_SEASON"


def main() -> int:
    status = detect_season()
    print(status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
