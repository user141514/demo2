import json
import smtplib
from email.message import EmailMessage
from urllib.parse import urlencode

from flask import current_app

from ..database import get_data_dir
from ..utils import now_iso


def password_reset_delivery_available():
    if current_app.config["SMTP_SUPPRESS_SEND"]:
        return True
    required = [
        current_app.config["SMTP_HOST"],
        current_app.config["SMTP_FROM"],
        current_app.config["APP_BASE_URL"],
    ]
    return all(required)


def send_password_reset(user, raw_token):
    reset_url = _build_password_reset_url(raw_token)
    subject = "智能体评分系统密码重置"
    body = (
        "您好，{name}：\n\n"
        "请在 1 小时内打开下面的链接重置密码：\n"
        "{url}\n\n"
        "如果这不是您的操作，请忽略这封邮件。\n"
    ).format(name=user["display_name"], url=reset_url)

    if current_app.config["SMTP_SUPPRESS_SEND"]:
        _write_mail_outbox(user["email"], subject, body, reset_url, raw_token)
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = current_app.config["SMTP_FROM"]
    message["To"] = user["email"]
    message.set_content(body)

    server = smtplib.SMTP(
        current_app.config["SMTP_HOST"],
        current_app.config["SMTP_PORT"],
        timeout=15,
    )
    try:
        if current_app.config["SMTP_USE_TLS"]:
            server.starttls()
        username = current_app.config["SMTP_USERNAME"]
        password = current_app.config["SMTP_PASSWORD"]
        if username:
            server.login(username, password)
        server.send_message(message)
    finally:
        try:
            server.quit()
        except Exception:
            pass


def _write_mail_outbox(email, subject, body, reset_url, raw_token):
    outbox_path = get_data_dir() / "mail_outbox.log"
    record = {
        "to": email,
        "subject": subject,
        "created_at": now_iso(),
        "delivery_mode": "suppressed",
    }
    if current_app.config["EXPOSE_RESET_TOKENS"]:
        record.update(
            {
                "body": body,
                "reset_url": reset_url,
                "reset_token": raw_token,
            }
        )
    with outbox_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _build_password_reset_url(raw_token):
    base_url = current_app.config["APP_BASE_URL"] or "http://127.0.0.1:5000"
    return "{}?{}".format(base_url.rstrip("/"), urlencode({"reset_token": raw_token}))
