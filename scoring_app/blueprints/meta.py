from flask import Blueprint, current_app

from ..core import json_response
from ..llm_config import get_public_llm_status
from ..services.mail_service import password_reset_delivery_available
from ..services.score_service import list_report_type_values


meta_bp = Blueprint("meta", __name__, url_prefix="/api")


def _check_database():
    """Execute SELECT 1 to verify database connectivity."""
    try:
        from ..database import get_connection

        conn = get_connection()
        try:
            row = conn.execute("SELECT 1").fetchone()
            return row is not None and row[0] == 1
        finally:
            conn.close()
    except Exception:
        return False


@meta_bp.route("/health", methods=["GET"])
def health():
    return json_response(
        {
            "status": "ok",
            "llm": get_public_llm_status(),
            "auth": {
                "cookie_name": current_app.config["AUTH_COOKIE_NAME"],
                "cookie_secure": current_app.config["AUTH_COOKIE_SECURE"],
                "password_reset_mail_ready": password_reset_delivery_available(),
                "smtp_suppressed": current_app.config["SMTP_SUPPRESS_SEND"],
            },
            "storage": {
                "artifact_backend": "database",
            },
            "database": {"connected": _check_database()},
        }
    )


@meta_bp.route("/report-types", methods=["GET"])
def report_types():
    return json_response({"items": list_report_type_values()})
