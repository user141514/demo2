from flask import Blueprint, request

from ..core import current_user_id, json_error, json_response, require_auth, send_download
from ..core.errors import ApplicationError
from ..services.score_service import build_score_export, create_score, get_user_score, list_user_scores


scores_bp = Blueprint("scores", __name__, url_prefix="/api")


@scores_bp.route("/score", methods=["POST"])
@require_auth
def create_score_route():
    try:
        result = create_score(request.form, request.files, current_user_id())
    except ApplicationError as exc:
        return json_error(exc.code, exc.message, exc.status_code)
    return json_response(result)


@scores_bp.route("/scores", methods=["GET"])
@require_auth
def list_scores_route():
    return json_response(list_user_scores(current_user_id()))


@scores_bp.route("/scores/<score_id>", methods=["GET"])
@require_auth
def score_detail(score_id):
    try:
        detail = get_user_score(score_id, current_user_id())
    except ApplicationError as exc:
        return json_error(exc.code, exc.message, exc.status_code)
    return json_response(detail)


@scores_bp.route("/scores/<score_id>/export", methods=["GET"])
@require_auth
def export_score(score_id):
    export_format = (request.args.get("format") or "md").lower()
    try:
        export_info = build_score_export(score_id, current_user_id(), export_format)
    except ApplicationError as exc:
        return json_error(exc.code, exc.message, exc.status_code)
    return send_download(
        export_info["file_path"],
        export_info["filename"],
        export_info["mimetype"],
    )
