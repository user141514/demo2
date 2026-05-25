from flask import Blueprint, current_app

from ..core import json_response
from ..llm_config import get_public_llm_status
from ..services.mail_service import password_reset_delivery_available
from ..services.score_service import list_report_type_values


meta_bp = Blueprint("meta", __name__, url_prefix="/api")


@meta_bp.route("/health", methods=["GET"])
def health():
    return json_response(
        {
            "status": "ok",
            "llm": get_public_llm_status(),
            "auth": {
                "cookie_name": current_app.config["AUTH_COOKIE_NAME"],
                "password_reset_mail_ready": password_reset_delivery_available(),
                "smtp_suppressed": current_app.config["SMTP_SUPPRESS_SEND"],
            },
        }
    )


@meta_bp.route("/report-types", methods=["GET"])
def report_types():
    return json_response({"items": list_report_type_values()})
