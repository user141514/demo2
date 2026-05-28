import json
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError

from flask import Blueprint, Response, current_app, request, stream_with_context

from ..core import current_user_id, json_error, json_response, require_auth, send_download
from ..utils import now_iso
from ..core.errors import ApplicationError
from ..services.score_service import (
    build_score_export,
    create_score,
    create_score_from_submission,
    delete_user_score,
    get_user_score,
    list_user_scores,
    list_user_scores_paginated,
    prepare_score_submission,
    update_user_score,
)


scores_bp = Blueprint("scores", __name__, url_prefix="/api")


@scores_bp.route("/score", methods=["POST"])
@require_auth
def create_score_route():
    try:
        result = create_score(request.form, request.files, current_user_id())
    except ApplicationError as exc:
        return json_error(exc.code, exc.message, exc.status_code)
    return json_response(result)


@scores_bp.route("/score/stream", methods=["POST"])
@require_auth
def create_score_stream_route():
    try:
        submission = prepare_score_submission(request.form, request.files)
    except ApplicationError as exc:
        return json_error(exc.code, exc.message, exc.status_code)

    user_id = current_user_id()
    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    }
    return Response(
        stream_with_context(_stream_score_submission(submission, user_id)),
        headers=headers,
        mimetype="application/x-ndjson",
    )


def _stream_score_submission(submission, user_id):
    yield _stream_event(
        "status",
        message="评分材料已接收，正在生成结果。",
        progress=8,
    )

    interval = _stream_heartbeat_seconds()
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(create_score_from_submission, submission, user_id)
        heartbeat_count = 0
        while True:
            try:
                result = future.result(timeout=interval)
            except TimeoutError:
                heartbeat_count += 1
                yield _stream_event(
                    "heartbeat",
                    message="评分仍在进行，请保持当前页面。",
                    progress=min(92, 12 + heartbeat_count * 6),
                    elapsed_seconds=round(heartbeat_count * interval, 1),
                )
                continue
            except ApplicationError as exc:
                yield _stream_event(
                    "error",
                    code=exc.code,
                    message=exc.message,
                    status=exc.status_code,
                    progress=100,
                )
                break
            except Exception:
                current_app.logger.exception("Streaming score submission failed.")
                yield _stream_event(
                    "error",
                    code="score_stream_failed",
                    message="评分生成失败，请稍后重试。",
                    status=500,
                    progress=100,
                )
                break

            yield _stream_event("result", result=result, progress=100)
            break


def _stream_event(event_type, **payload):
    payload = {"type": event_type, **payload}
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"


def _stream_heartbeat_seconds():
    try:
        return max(0.01, float(os.getenv("SCORING_SCORE_STREAM_HEARTBEAT_SECONDS", "8")))
    except Exception:
        return 8.0


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


@scores_bp.route("/scores/<score_id>", methods=["DELETE"])
@require_auth
def delete_score_route(score_id):
    try:
        delete_user_score(score_id, current_user_id())
    except ApplicationError as exc:
        return json_error(exc.code, exc.message, exc.status_code)
    return json_response({"deleted": True})


@scores_bp.route("/scores/<score_id>", methods=["PATCH"])
@require_auth
def patch_score_route(score_id):
    try:
        updates = request.get_json(force=True) or {}
        detail = update_user_score(score_id, current_user_id(), updates)
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
        export_info["content"],
        export_info["filename"],
        export_info["mimetype"],
    )


@scores_bp.route("/scores/<score_id>/pause", methods=["POST"])
@require_auth
def pause_score_route(score_id):
    """Pause a score for human review. Returns resume_token."""
    from uuid import uuid4
    from ..repository import get_score_detail, create_pause_record

    # Verify score exists and belongs to user
    try:
        get_score_detail(score_id, current_user_id())
    except Exception:
        from ..services.score_service import ApplicationError
        raise ApplicationError("score_not_found", "Score not found", 404)

    body = request.get_json(silent=True) or {}
    reason = body.get("reason", "Human review requested")
    pause_id = uuid4().hex
    resume_token = uuid4().hex

    create_pause_record(pause_id, score_id, current_user_id(), reason, resume_token, now_iso())
    return json_response({"pause_id": pause_id, "resume_token": resume_token})


@scores_bp.route("/scores/<score_id>/resume", methods=["POST"])
def resume_score_route(score_id):
    """Resume a paused evaluation. Requires valid resume_token."""
    from ..repository import resolve_pause_record, get_active_pause

    body = request.get_json(silent=True) or {}
    token = body.get("token", "")
    if not token:
        from ..services.score_service import ApplicationError
        raise ApplicationError("missing_token", "resume_token is required", 400)

    active = get_active_pause(score_id)
    if not active:
        from ..services.score_service import ApplicationError
        raise ApplicationError("no_active_pause", "No active pause found for this score", 404)

    resolved = resolve_pause_record(score_id, token, now_iso())
    if not resolved:
        from ..services.score_service import ApplicationError
        raise ApplicationError("invalid_token", "Invalid resume token", 403)

    return json_response({"status": "resumed"})


@scores_bp.route("/calibration", methods=["GET"])
@require_auth
def calibration_stats_route():
    """Return per-dimension calibration statistics."""
    report_type = request.args.get("report_type", "")
    if not report_type:
        from ..services.score_service import ApplicationError
        raise ApplicationError("missing_param", "report_type is required", 400)

    from ..calibration import get_calibration_stats
    stats = get_calibration_stats(report_type)
    return json_response({"report_type": report_type, "dimensions": stats})
