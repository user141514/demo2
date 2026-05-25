from flask import Blueprint, render_template

from ..services.score_service import list_report_type_keys


pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/", methods=["GET"])
def index():
    return render_template("index.html", report_types=list_report_type_keys())
