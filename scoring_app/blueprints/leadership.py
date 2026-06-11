from flask import Blueprint, request

from ..core import current_user_id, json_error, json_response, require_auth, send_download
from ..core.errors import ApplicationError
from ..services.leadership_service import (
    build_model_export,
    create_model,
    generate_anchors,
    generate_descriptions,
    generate_dimensions,
    get_model,
    list_models,
    save_anchors,
    save_descriptions,
    save_dimensions,
)


leadership_bp = Blueprint("leadership", __name__, url_prefix="/api")


@leadership_bp.route("/leadership-models", methods=["POST"])
@require_auth
def create_leadership_model_route():
    try:
        result = create_model(request.form, request.files, current_user_id())
    except ApplicationError as exc:
        return json_error(exc.code, exc.message, exc.status_code)
    return json_response(result, 201)


@leadership_bp.route("/leadership-models", methods=["GET"])
@require_auth
def list_leadership_models_route():
    return json_response(list_models(current_user_id()))


@leadership_bp.route("/leadership-models/<model_id>", methods=["GET"])
@require_auth
def get_leadership_model_route(model_id):
    try:
        result = get_model(model_id, current_user_id())
    except ApplicationError as exc:
        return json_error(exc.code, exc.message, exc.status_code)
    return json_response(result)


@leadership_bp.route("/leadership-models/<model_id>/dimensions:generate", methods=["POST"])
@require_auth
def generate_dimensions_route(model_id):
    try:
        result = generate_dimensions(model_id, current_user_id())
    except ApplicationError as exc:
        return json_error(exc.code, exc.message, exc.status_code)
    return json_response(result)


@leadership_bp.route("/leadership-models/<model_id>/dimensions", methods=["PATCH"])
@require_auth
def save_dimensions_route(model_id):
    try:
        result = save_dimensions(model_id, current_user_id(), request.get_json(force=True) or {})
    except ApplicationError as exc:
        return json_error(exc.code, exc.message, exc.status_code)
    return json_response(result)


@leadership_bp.route("/leadership-models/<model_id>/descriptions:generate", methods=["POST"])
@require_auth
def generate_descriptions_route(model_id):
    try:
        result = generate_descriptions(model_id, current_user_id())
    except ApplicationError as exc:
        return json_error(exc.code, exc.message, exc.status_code)
    return json_response(result)


@leadership_bp.route("/leadership-models/<model_id>/descriptions", methods=["PATCH"])
@require_auth
def save_descriptions_route(model_id):
    try:
        result = save_descriptions(model_id, current_user_id(), request.get_json(force=True) or {})
    except ApplicationError as exc:
        return json_error(exc.code, exc.message, exc.status_code)
    return json_response(result)


@leadership_bp.route("/leadership-models/<model_id>/anchors:generate", methods=["POST"])
@require_auth
def generate_anchors_route(model_id):
    try:
        result = generate_anchors(model_id, current_user_id())
    except ApplicationError as exc:
        return json_error(exc.code, exc.message, exc.status_code)
    return json_response(result)


@leadership_bp.route("/leadership-models/<model_id>/anchors", methods=["PATCH"])
@require_auth
def save_anchors_route(model_id):
    try:
        result = save_anchors(model_id, current_user_id(), request.get_json(force=True) or {})
    except ApplicationError as exc:
        return json_error(exc.code, exc.message, exc.status_code)
    return json_response(result)


@leadership_bp.route("/leadership-models/<model_id>/export", methods=["GET"])
@require_auth
def export_leadership_model_route(model_id):
    export_format = (request.args.get("format") or "docx").lower()
    try:
        export_info = build_model_export(model_id, current_user_id(), export_format)
    except ApplicationError as exc:
        return json_error(exc.code, exc.message, exc.status_code)
    return send_download(
        export_info["content"],
        export_info["filename"],
        export_info["mimetype"],
    )
