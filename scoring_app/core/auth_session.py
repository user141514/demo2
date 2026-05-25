from functools import wraps

from flask import current_app, g, request

from ..repository import get_active_session, revoke_session
from ..services.auth_service import current_timestamp, hash_token, public_user
from .http import json_error


def load_current_user():
    g.current_user = None
    g.current_session = None
    g.current_session_token = None
    token = request.cookies.get(current_app.config["AUTH_COOKIE_NAME"])
    if not token:
        return
    session = get_active_session(hash_token(token), current_timestamp())
    if session is None:
        return
    g.current_session = session
    g.current_session_token = token
    g.current_user = public_user(session["user"])


def require_auth(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if g.get("current_user") is None:
            return json_error("auth_required", "请先登录后再操作。", 401)
        return view_func(*args, **kwargs)

    return wrapped


def current_user():
    return g.get("current_user")


def current_user_id():
    user = current_user()
    return user["user_id"] if user is not None else None


def logout_current_session():
    token = g.get("current_session_token")
    if token:
        revoke_session(hash_token(token), current_timestamp())


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
