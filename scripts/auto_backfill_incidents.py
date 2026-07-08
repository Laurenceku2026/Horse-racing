#!/usr/bin/env python3
"""
赛日自动补全 incident LLM 缓存（GitHub Actions / 手动运行）。

环境变量：
  SUPABASE_STOCK_URL
  SUPABASE_STOCK_SECRET_KEY
  DEEPSEEK_API_KEY
  DEEPSEEK_BASE_URL (可选)
  DEEPSEEK_MODEL (可选)
  INCIDENT_AUTO_MAX_CALLS (可选，默认 500)
"""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from incident_llm_service import run_auto_incident_backfill  # noqa: E402


def main() -> int:
    supabase_url = os.environ.get("SUPABASE_STOCK_URL", "").strip()
    supabase_key = os.environ.get("SUPABASE_STOCK_SECRET_KEY", "").strip()
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()

    if not supabase_url or not supabase_key or not api_key:
        print("Missing SUPABASE_STOCK_URL, SUPABASE_STOCK_SECRET_KEY, or DEEPSEEK_API_KEY")
        return 1

    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
    }
    secrets = {
        "DEEPSEEK_API_KEY": api_key,
        "DEEPSEEK_BASE_URL": os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        "DEEPSEEK_MODEL": os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
    }
    max_calls = int(os.environ.get("INCIDENT_AUTO_MAX_CALLS", "500"))

    result = run_auto_incident_backfill(
        supabase_url,
        headers,
        secrets,
        days_back=int(os.environ.get("INCIDENT_AUTO_DAYS_BACK", "7")),
        days_forward=int(os.environ.get("INCIDENT_AUTO_DAYS_FORWARD", "1")),
        max_new_calls=max_calls,
        fill_all=False,
    )
    print(
        "auto_backfill:",
        f"dates={result.get('target_dates')}",
        f"analyzed={result.get('analyzed', 0)}",
        f"cached={result.get('cached', 0)}",
        f"errors={result.get('errors', 0)}",
        f"remaining={result.get('remaining_missing', 0)}",
        f"tokens={result.get('total_tokens', 0)}",
    )
    return 0 if int(result.get("errors", 0) or 0) == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
