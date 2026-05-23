import hashlib
import json
import os
import secrets
import smtplib
import sqlite3
import uuid
from datetime import datetime, timedelta
from email.message import EmailMessage
from functools import wraps
from urllib.parse import urlencode

from flask import current_app, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from .database import get_data_dir
from .repository import (
    claim_orphan_scores,
    consume_password_reset_token,
    count_users,
    create_password_reset_token,
    create_user,
    create_user_session,
    get_active_password_reset_token,
    get_active_session,
    get_user_by_email,
    revoke_session,
    revoke_user_sessions,
    update_user_password,
)


class AuthError(Exception):
    def __init__(self, code, message, status_code):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def configure_auth(app):
    app.config.setdefault(
        "AUTH_COOKIE_NAME", os.getenv("SCORING_APP_AUTH_COOKIE_NAME", "scoring_session")
    )
    app.config.setdefault(
        "AUTH_SESSION_DAYS", int(os.getenv("SCORING_APP_AUTH_SESSION_DAYS", "7"))
    )
    app.config.setdefault(
        "AUTH_COOKIE_SECURE",
        _is_truthy(os.getenv("SCORING_APP_AUTH_COOKIE_SECURE", "0")),
    )
    app.config.setdefault(
        "SMTP_HOST", (os.getenv("SCORING_APP_SMTP_HOST") or "").strip()
    )
    app.config.setdefault(
        "SMTP_PORT", int(os.getenv("SCORING_APP_SMTP_PORT", "587"))
    )
    app.config.setdefault(
        "SMTP_USERNAME", (os.getenv("SCORING_APP_SMTP_USERNAME") or "").strip()
    )
    app.config.setdefault(
        "SMTP_PASSWORD", os.getenv("SCORING_APP_SMTP_PASSWORD", "")
    )
    app.config.setdefault(
        "SMTP_FROM", (os.getenv("SCORING_APP_SMTP_FROM") or "").strip()
    )
    app.config.setdefault(
        "SMTP_USE_TLS", _is_truthy(os.getenv("SCORING_APP_SMTP_USE_TLS", "1"))
    )
    app.config.setdefault(
        "SMTP_SUPPRESS_SEND",
        _is_truthy(os.getenv("SCORING_APP_SMTP_SUPPRESS_SEND", "0")),
    )
    app.config.setdefault(
        "EXPOSE_RESET_TOKENS",
        _is_truthy(os.getenv("SCORING_APP_EXPOSE_RESET_TOKENS", "0")),
    )
    app.config.setdefault(
        "APP_BASE_URL", (os.getenv("SCORING_APP_BASE_URL") or "").strip()
    )


def load_current_user():
    g.current_user = None
    g.current_session = None
    g.current_session_token = None
    token = request.cookies.get(current_app.config["AUTH_COOKIE_NAME"])
    if not token:
        return
    session = get_active_session(_hash_token(token), _utcnow_value())
    if session is None:
        return
    g.current_session = session
    g.current_session_token = token
    g.current_user = _public_user(session["user"])


def require_auth(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if g.get("current_user") is None:
            return error_response("auth_required", "请先登录后再操作。", 401)
        return view_func(*args, **kwargs)

    return wrapped


def register_user(payload):
    email = _normalize_email(payload.get("email"))
    display_name = (payload.get("display_name") or "").strip()
    password = payload.get("password") or ""

    if not _looks_like_email(email):
        raise AuthError("invalid_email", "请输入有效邮箱。", 400)
    if len(display_name) < 2:
        raise AuthError("invalid_display_name", "姓名至少需要 2 个字符。", 400)
    if len(password) < 8:
        raise AuthError("invalid_password", "密码至少需要 8 位。", 400)
    if get_user_by_email(email) is not None:
        raise AuthError("email_exists", "该邮箱已注册。", 409)

    now_value = _utcnow_value()
    is_first_user = count_users() == 0
    user = {
        "user_id": uuid.uuid4().hex,
        "email": email,
        "display_name": display_name,
        "password_hash": generate_password_hash(password),
        "created_at": now_value,
        "updated_at": now_value,
    }
    try:
        create_user(
            user["user_id"],
            user["email"],
            user["display_name"],
            user["password_hash"],
            user["created_at"],
        )
    except sqlite3.IntegrityError:
        raise AuthError("email_exists", "该邮箱已注册。", 409)
    if is_first_user:
        claim_orphan_scores(user["user_id"])
    token = create_login_session(user["user_id"])
    return _public_user(user), token


def login_user(payload):
    email = _normalize_email(payload.get("email"))
    password = payload.get("password") or ""
    if not email or not password:
        raise AuthError("invalid_credentials", "邮箱或密码错误。", 401)

    user = get_user_by_email(email)
    if user is None or not check_password_hash(user["password_hash"], password):
        raise AuthError("invalid_credentials", "邮箱或密码错误。", 401)

    token = create_login_session(user["user_id"])
    return _public_user(user), token


def create_login_session(user_id):
    token = secrets.token_urlsafe(32)
    now = _utcnow()
    expires_at = now + timedelta(days=current_app.config["AUTH_SESSION_DAYS"])
    create_user_session(
        uuid.uuid4().hex,
        user_id,
        _hash_token(token),
        _to_utc_text(now),
        _to_utc_text(expires_at),
    )
    return token


def logout_current_session():
    token = g.get("current_session_token")
    if token:
        revoke_session(_hash_token(token), _utcnow_value())


def create_password_reset(payload):
    if not password_reset_delivery_available():
        raise AuthError(
            "mail_unavailable",
            "密码重置邮件服务暂不可用，请稍后重试。",
            503,
        )

    email = _normalize_email(payload.get("email"))
    if not email:
        return

    user = get_user_by_email(email)
    if user is None:
        return

    raw_token = secrets.token_urlsafe(32)
    now = _utcnow()
    now_text = _to_utc_text(now)
    expires_text = _to_utc_text(now + timedelta(hours=1))
    token_id = uuid.uuid4().hex
    create_password_reset_token(
        token_id,
        user["user_id"],
        _hash_token(raw_token),
        now_text,
        expires_text,
    )
    try:
        _deliver_password_reset_email(user, raw_token)
    except Exception:
        raise


def reset_password(payload):
    raw_token = (payload.get("token") or "").strip()
    password = payload.get("password") or ""
    if not raw_token:
        raise AuthError("missing_token", "缺少重置凭证。", 400)
    if len(password) < 8:
        raise AuthError("invalid_password", "密码至少需要 8 位。", 400)

    token = get_active_password_reset_token(_hash_token(raw_token), _utcnow_value())
    if token is None:
        raise AuthError("invalid_reset_token", "重置链接无效或已过期。", 400)

    now_value = _utcnow_value()
    update_user_password(
        token["user_id"],
        generate_password_hash(password),
        now_value,
    )
    revoke_user_sessions(token["user_id"], now_value)
    consume_password_reset_token(token["token_id"], now_value)


def password_reset_delivery_available():
    if current_app.config["SMTP_SUPPRESS_SEND"]:
        return True
    required = [
        current_app.config["SMTP_HOST"],
        current_app.config["SMTP_FROM"],
        current_app.config["APP_BASE_URL"],
    ]
    return all(required)


def set_session_cookie(response, token):
    response.set_cookie(
        current_app.config["AUTH_COOKIE_NAME"],
        token,
        max_age=current_app.config["AUTH_SESSION_DAYS"] * 24 * 60 * 60,
        httponly=True,
        samesite="Lax",
        secure=current_app.config["AUTH_COOKIE_SECURE"],
        path="/",
    )
    return response


def clear_session_cookie(response):
    try:
        response.delete_cookie(
            current_app.config["AUTH_COOKIE_NAME"],
            path="/",
            samesite="Lax",
            secure=current_app.config["AUTH_COOKIE_SECURE"],
        )
    except TypeError:
        response.delete_cookie(
            current_app.config["AUTH_COOKIE_NAME"],
            path="/",
        )
    return response


def error_response(code, message, status_code):
    return jsonify({"error": code, "message": message}), status_code


def _deliver_password_reset_email(user, raw_token):
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
        "created_at": _utcnow_value(),
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
    base_url = current_app.config["APP_BASE_URL"]
    if not base_url:
        base_url = "http://127.0.0.1:5000"
    return "{}?{}".format(base_url.rstrip("/"), urlencode({"reset_token": raw_token}))


def _public_user(user):
    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "display_name": user["display_name"],
        "created_at": user["created_at"],
    }


def _normalize_email(value):
    return (value or "").strip().lower()


def _looks_like_email(value):
    return bool(value and "@" in value and "." in value.split("@")[-1])


def _hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _utcnow():
    return datetime.utcnow().replace(microsecond=0)


def _utcnow_value():
    return _to_utc_text(_utcnow())


def _to_utc_text(value):
    return value.isoformat() + "Z"


def _is_truthy(value):
    return str(value).strip().lower() in {"1", "true", "yes", "on"}
