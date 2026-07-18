"""
简易 SMTP 发信（用于忘记密码重置邮件）。
推荐 Gmail：smtp.gmail.com:587 + 应用专用密码（非登录密码）。
"""
from __future__ import annotations

import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Tuple


def smtp_configured(
    *,
    host: str = "",
    user: str = "",
    password: str = "",
) -> bool:
    return bool((host or "").strip() and (user or "").strip() and (password or "").strip())


def send_email(
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    mail_from: str,
    to_addr: str,
    subject: str,
    text_body: str,
    html_body: str = "",
    use_tls: bool = True,
) -> Tuple[bool, str]:
    """发送一封邮件。成功返回 (True, '')，失败 (False, error)。"""
    host = (host or "").strip()
    user = (user or "").strip()
    password = (password or "").strip()
    mail_from = (mail_from or user or "").strip()
    to_addr = (to_addr or "").strip().lower()
    if not smtp_configured(host=host, user=user, password=password):
        return False, "smtp_not_configured"
    if not to_addr or "@" not in to_addr:
        return False, "invalid_to"
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = mail_from
        msg["To"] = to_addr
        msg.attach(MIMEText(text_body or "", "plain", "utf-8"))
        if html_body:
            msg.attach(MIMEText(html_body, "html", "utf-8"))

        context = ssl.create_default_context()
        with smtplib.SMTP(host, int(port or 587), timeout=30) as server:
            if use_tls:
                server.starttls(context=context)
            server.login(user, password)
            server.sendmail(mail_from, [to_addr], msg.as_string())
        return True, ""
    except Exception as e:
        return False, str(e)


def build_password_reset_email(
    *,
    reset_url: str,
    lang: str = "zh",
    app_name: str = "香港赛马AI分析系统",
) -> Tuple[str, str, str]:
    """返回 (subject, text, html)。"""
    if lang == "en":
        subject = f"{app_name} — Password reset"
        text = (
            f"We received a password reset request for your {app_name} account.\n\n"
            f"Open this link within 1 hour to set a new password:\n{reset_url}\n\n"
            "If you did not request this, ignore this email."
        )
        html = (
            f"<p>We received a password reset request for your <b>{app_name}</b> account.</p>"
            f'<p><a href="{reset_url}">Set a new password</a> (link expires in 1 hour).</p>'
            f'<p style="color:#666;font-size:0.9rem;">If you did not request this, ignore this email.</p>'
        )
        return subject, text, html

    subject = f"{app_name} — 重置密码"
    text = (
        f"您好，我们收到您在「{app_name}」的密码重置申请。\n\n"
        f"请在 1 小时内打开以下链接设置新密码：\n{reset_url}\n\n"
        "如非本人操作，请忽略本邮件。"
    )
    html = (
        f"<p>您好，我们收到您在「<b>{app_name}</b>」的密码重置申请。</p>"
        f'<p><a href="{reset_url}">点击设置新密码</a>（链接 1 小时内有效）。</p>'
        f'<p style="color:#666;font-size:0.9rem;">如非本人操作，请忽略本邮件。</p>'
    )
    return subject, text, html


def env_smtp_settings(getenv=os.getenv) -> dict:
    """从环境变量读取 SMTP 设置（Secrets 由调用方注入 getenv）。"""
    return {
        "host": (getenv("SMTP_HOST") or "smtp.gmail.com").strip(),
        "port": int(getenv("SMTP_PORT") or "587"),
        "user": (getenv("SMTP_USER") or getenv("SMTP_FROM") or "").strip(),
        "password": (getenv("SMTP_PASSWORD") or "")
        .strip()
        .replace(" ", "")
        .replace("\u00a0", ""),
        "mail_from": (
            getenv("SMTP_FROM") or getenv("SMTP_USER") or "Techlife2027@gmail.com"
        ).strip(),
        "use_tls": (getenv("SMTP_USE_TLS") or "1").strip() not in ("0", "false", "False"),
    }
