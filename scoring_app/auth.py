from .core import (
    clear_session_cookie,
    load_current_user,
    logout_current_session,
    require_auth,
    set_session_cookie,
)
from .core.http import json_error
from .core.settings import configure_app as configure_auth
from .services.auth_service import (
    AuthError,
    create_password_reset,
    current_timestamp,
    hash_token,
    login_user,
    public_user,
    register_user,
    reset_password,
)
from .services.mail_service import password_reset_delivery_available


def error_response(code, message, status_code):
    response = json_error(code, message, status_code)
    return response, status_code

__all__ = [
    "AuthError",
    "clear_session_cookie",
    "configure_auth",
    "create_password_reset",
    "current_timestamp",
    "error_response",
    "hash_token",
    "load_current_user",
    "login_user",
    "logout_current_session",
    "password_reset_delivery_available",
    "public_user",
    "register_user",
    "require_auth",
    "reset_password",
    "set_session_cookie",
]
