from pathlib import Path

from flask import Blueprint, current_app, render_template, send_from_directory

from ..services.score_service import list_report_type_keys


pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/", methods=["GET"])
def index():
    return render_template("index.html", report_types=list_report_type_keys())


@pages_bp.route("/leadership", methods=["GET"])
def leadership_app():
    app_dir = Path(current_app.static_folder) / "leadership-react"
    return send_from_directory(app_dir, "index.html")
