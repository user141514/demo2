from flask import Blueprint, current_app

from ..core import (
    clear_session_cookie,
    current_user,
    json_error,
    json_response,
    logout_current_session,
    read_json_body,
    set_session_cookie,
)
from ..core.errors import ApplicationError
from ..services.auth_service import AuthError, create_password_reset, login_user, register_user, reset_password


auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/register", methods=["POST"])
def register():
    return _run_auth_flow(register_user, status_code=201)


@auth_bp.route("/login", methods=["POST"])
def login():
    return _run_auth_flow(login_user)


@auth_bp.route("/logout", methods=["POST"])
def logout():
    logout_current_session()
    response = json_response({"ok": True})
    return clear_session_cookie(response)


@auth_bp.route("/me", methods=["GET"])
def me():
    user = current_user()
    if user is None:
        response = json_error("auth_required", "当前未登录。", 401)
        return clear_session_cookie(response)
    return json_response({"user": user})


@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    try:
        create_password_reset(read_json_body())
    except AuthError as exc:
        return json_error(exc.code, exc.message, exc.status_code)
    except Exception:
        current_app.logger.exception("Failed to send password reset mail")
        return json_response(
            {
                "ok": True,
                "message": "如果该邮箱已注册，系统会向该邮箱发送密码重置邮件。",
            }
        )
    return json_response(
        {
            "ok": True,
            "message": "如果该邮箱已注册，系统会向该邮箱发送密码重置邮件。",
        }
    )


@auth_bp.route("/reset-password", methods=["POST"])
def reset_password_route():
    try:
        reset_password(read_json_body())
    except AuthError as exc:
        return json_error(exc.code, exc.message, exc.status_code)
    response = json_response({"ok": True})
    return clear_session_cookie(response)


def _run_auth_flow(handler, status_code=200):
    try:
        user, token = handler(read_json_body())
    except ApplicationError as exc:
        return json_error(exc.code, exc.message, exc.status_code)
    response = json_response({"user": user}, status_code=status_code)
    return set_session_cookie(response, token)
