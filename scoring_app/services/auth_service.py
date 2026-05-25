import hashlib
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta

from flask import current_app
from werkzeug.security import check_password_hash, generate_password_hash

from ..core.errors import ApplicationError
from ..repository import (
    claim_orphan_scores,
    consume_password_reset_token,
    count_users,
    create_password_reset_token,
    create_user,
    create_user_session,
    get_active_password_reset_token,
    get_user_by_email,
    revoke_user_sessions,
    update_user_password,
)
from .mail_service import password_reset_delivery_available, send_password_reset


class AuthError(ApplicationError):
    pass


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

    now_value = current_timestamp()
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
    return public_user(user), token


def login_user(payload):
    email = _normalize_email(payload.get("email"))
    password = payload.get("password") or ""
    if not email or not password:
        raise AuthError("invalid_credentials", "邮箱或密码错误。", 401)

    user = get_user_by_email(email)
    if user is None or not check_password_hash(user["password_hash"], password):
        raise AuthError("invalid_credentials", "邮箱或密码错误。", 401)

    token = create_login_session(user["user_id"])
    return public_user(user), token


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
    create_password_reset_token(
        uuid.uuid4().hex,
        user["user_id"],
        hash_token(raw_token),
        _to_utc_text(now),
        _to_utc_text(now + timedelta(hours=1)),
    )
    send_password_reset(user, raw_token)


def reset_password(payload):
    raw_token = (payload.get("token") or "").strip()
    password = payload.get("password") or ""
    if not raw_token:
        raise AuthError("missing_token", "缺少重置凭证。", 400)
    if len(password) < 8:
        raise AuthError("invalid_password", "密码至少需要 8 位。", 400)

    token = get_active_password_reset_token(hash_token(raw_token), current_timestamp())
    if token is None:
        raise AuthError("invalid_reset_token", "重置链接无效或已过期。", 400)

    now_value = current_timestamp()
    update_user_password(
        token["user_id"],
        generate_password_hash(password),
        now_value,
    )
    revoke_user_sessions(token["user_id"], now_value)
    consume_password_reset_token(token["token_id"], now_value)


def create_login_session(user_id):
    token = secrets.token_urlsafe(32)
    now = _utcnow()
    expires_at = now + timedelta(days=current_app.config["AUTH_SESSION_DAYS"])
    create_user_session(
        uuid.uuid4().hex,
        user_id,
        hash_token(token),
        _to_utc_text(now),
        _to_utc_text(expires_at),
    )
    return token


def public_user(user):
    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "display_name": user["display_name"],
        "created_at": user["created_at"],
    }


def hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def current_timestamp():
    return _to_utc_text(_utcnow())


def _normalize_email(value):
    return (value or "").strip().lower()


def _looks_like_email(value):
    return bool(value and "@" in value and "." in value.split("@")[-1])


def _utcnow():
    return datetime.utcnow().replace(microsecond=0)


def _to_utc_text(value):
    return value.isoformat() + "Z"
