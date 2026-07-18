"""
忘记密码：SMTP 邮件链接 + Supabase Auth Admin 更新密码。

Token hash 存于 Auth user_metadata（无需改 user_settings_racing 表结构）。
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote

import requests


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _hash_token(token: str) -> str:
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def find_auth_user_by_email(
    *,
    supabase_url: str,
    service_headers: Dict[str, str],
    email: str,
    per_page: int = 200,
    max_pages: int = 10,
) -> Optional[Dict[str, Any]]:
    """用 Admin API 按邮箱查找 Auth 用户。"""
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        return None
    base = (supabase_url or "").rstrip("/")
    for page in range(1, max_pages + 1):
        try:
            resp = requests.get(
                f"{base}/auth/v1/admin/users",
                headers=service_headers,
                params={"page": page, "per_page": per_page},
                timeout=30,
            )
            if resp.status_code != 200:
                return None
            payload = resp.json()
            users = payload.get("users") if isinstance(payload, dict) else payload
            if not users:
                return None
            for user in users:
                if (user.get("email") or "").strip().lower() == email:
                    return user
            if len(users) < per_page:
                return None
        except Exception:
            return None
    return None


def create_password_reset_token(
    *,
    supabase_url: str,
    service_headers: Dict[str, str],
    email: str,
    ttl_minutes: int = 60,
    cooldown_seconds: int = 120,
) -> Optional[str]:
    """
    生成一次性重置 token（明文仅返回一次）。

    返回值约定（与 Sigma_bazi 一致）：
      - token 字符串：成功
      - ""（空串）：冷却中
      - None：未知邮箱 / 无效输入 / 写入失败
    """
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        return None

    user = find_auth_user_by_email(
        supabase_url=supabase_url,
        service_headers=service_headers,
        email=email,
    )
    if not user:
        return None

    uid = user.get("id")
    if not uid:
        return None

    meta = user.get("user_metadata") if isinstance(user.get("user_metadata"), dict) else {}
    last = str(meta.get("pwd_reset_sent_at") or "")
    if last and cooldown_seconds > 0:
        try:
            prev = datetime.fromisoformat(last.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) - prev < timedelta(seconds=cooldown_seconds):
                return ""
        except Exception:
            pass

    token = secrets.token_urlsafe(32)
    token_hash = _hash_token(token)
    expires = (
        datetime.now(timezone.utc) + timedelta(minutes=max(5, int(ttl_minutes)))
    ).isoformat().replace("+00:00", "Z")

    new_meta = {
        **meta,
        "pwd_reset_token_hash": token_hash,
        "pwd_reset_expires_at": expires,
        "pwd_reset_sent_at": _now_iso(),
    }
    base = (supabase_url or "").rstrip("/")
    try:
        resp = requests.put(
            f"{base}/auth/v1/admin/users/{uid}",
            headers=service_headers,
            json={"user_metadata": new_meta},
            timeout=30,
        )
        if resp.status_code not in (200, 201):
            print(f"create_password_reset_token failed: {resp.status_code} {resp.text}")
            return None
    except Exception as e:
        print(f"create_password_reset_token error: {e}")
        return None
    return token


def reset_password_with_token(
    *,
    supabase_url: str,
    service_headers: Dict[str, str],
    email: str,
    token: str,
    new_password: str,
) -> Tuple[bool, str]:
    """
    校验邮件链接 token，并用 Admin API 写入新密码。
    成功 (True, '')；失败 (False, error_code)。
    """
    email = (email or "").strip().lower()
    token = (token or "").strip()
    pwd = (new_password or "").strip()
    if not email or not token or len(pwd) < 6:
        return False, "invalid_input"

    user = find_auth_user_by_email(
        supabase_url=supabase_url,
        service_headers=service_headers,
        email=email,
    )
    if not user:
        return False, "account_not_found"

    uid = user.get("id")
    meta = user.get("user_metadata") if isinstance(user.get("user_metadata"), dict) else {}
    expected = str(meta.get("pwd_reset_token_hash") or "")
    exp_s = str(meta.get("pwd_reset_expires_at") or "")
    if not expected:
        return False, "token_missing"
    if _hash_token(token) != expected:
        return False, "token_invalid"
    if exp_s:
        try:
            exp = datetime.fromisoformat(exp_s.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) > exp:
                return False, "token_expired"
        except Exception:
            pass

    cleared_meta = {
        **meta,
        "pwd_reset_token_hash": None,
        "pwd_reset_expires_at": None,
        "password_reset_at": _now_iso(),
        "password_reset_by": "email_link",
    }
    base = (supabase_url or "").rstrip("/")
    try:
        resp = requests.put(
            f"{base}/auth/v1/admin/users/{uid}",
            headers=service_headers,
            json={"password": pwd, "user_metadata": cleared_meta},
            timeout=30,
        )
        if resp.status_code not in (200, 201):
            print(f"reset_password_with_token failed: {resp.status_code} {resp.text}")
            return False, "update_failed"
    except Exception as e:
        print(f"reset_password_with_token error: {e}")
        return False, "update_failed"
    return True, ""


def build_reset_url(app_base_url: str, email: str, token: str) -> str:
    base = (app_base_url or "").strip().split("?")[0].rstrip("/")
    return (
        f"{base}/?pwd_reset=1"
        f"&email={quote(email, safe='')}"
        f"&token={quote(token, safe='')}"
    )
