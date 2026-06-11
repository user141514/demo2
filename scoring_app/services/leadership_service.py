from uuid import uuid4

from ..core.errors import ApplicationError
from ..leadership_documents import extract_leadership_source_file
from ..leadership_export import (
    DOCX_MIMETYPE,
    build_leadership_docx_bytes,
    build_leadership_pdf_bytes,
)
from ..leadership_generation import (
    build_anchor_drafts,
    build_description_drafts,
    build_dimension_drafts,
    parse_context_from_form,
)
from ..leadership_llm import generate_stage_with_llm
from ..leadership_repository import (
    create_leadership_model,
    get_leadership_artifact,
    get_leadership_model,
    list_leadership_models,
    store_leadership_artifact,
    update_leadership_model,
)
from ..leadership_state import build_workflow_state, infer_current_step
from ..utils import now_iso


def create_model(form, files, user_id):
    source_file, source_text = extract_leadership_source_file(files.get("source_file"))
    context = parse_context_from_form(form, source_text)
    if not context.get("company_name"):
        raise ApplicationError("missing_company_name", "公司名称不能为空。", 400)
    if not context.get("target_group"):
        raise ApplicationError("missing_target_group", "建模对象层级/群体不能为空。", 400)

    model_id = uuid4().hex
    created_at = now_iso()
    title = "{} {} 领导力模型".format(
        context.get("company_name"),
        context.get("target_group"),
    )
    record = {
        "model_id": model_id,
        "user_id": user_id,
        "title": title,
        "context": context,
        "status": "context_ready",
        "current_step": "dimensions",
        "created_at": created_at,
        "updated_at": created_at,
    }
    artifacts = []
    if source_file is not None:
        artifacts.append(
            {
                "artifact_kind": "source_file",
                "filename": source_file["filename"],
                "mimetype": source_file["mimetype"],
                "content_bytes": source_file["content_bytes"],
                "created_at": created_at,
            }
        )
    create_leadership_model(record, artifacts=artifacts)
    return get_model(model_id, user_id)


def list_models(user_id):
    return {
        "items": [
            _summary_payload(model)
            for model in list_leadership_models(user_id)
            if model is not None
        ]
    }


def get_model(model_id, user_id):
    model = _require_model(model_id, user_id)
    return _detail_payload(model)


def generate_dimensions(model_id, user_id):
    model = _require_model(model_id, user_id)
    dimensions = _generate_stage(
        "dimensions",
        {"context": model["context"]},
        lambda: build_dimension_drafts(model["context"]),
        _validate_dimensions,
    )
    return _update_and_return(
        model_id,
        user_id,
        {
            "dimensions": dimensions,
            "dimensions_confirmed": False,
            "descriptions": [],
            "descriptions_confirmed": False,
            "anchors": [],
            "anchors_confirmed": False,
            "status": "dimensions_pending_review",
            "current_step": "dimensions",
        },
    )


def save_dimensions(model_id, user_id, payload):
    dimensions = _validate_dimensions(payload.get("dimensions"))
    return _update_and_return(
        model_id,
        user_id,
        {
            "dimensions": dimensions,
            "dimensions_confirmed": True,
            "descriptions": [],
            "descriptions_confirmed": False,
            "anchors": [],
            "anchors_confirmed": False,
            "status": "dimensions_confirmed",
            "current_step": "descriptions",
        },
    )


def generate_descriptions(model_id, user_id):
    model = _require_model(model_id, user_id)
    if not model.get("dimensions_confirmed"):
        raise ApplicationError("dimensions_required", "请先确认维度框架。", 409)
    descriptions = _generate_stage(
        "descriptions",
        {"context": model["context"], "dimensions": model["dimensions"]},
        lambda: build_description_drafts(model["context"], model["dimensions"]),
        lambda value: _validate_list(value, "descriptions"),
    )
    return _update_and_return(
        model_id,
        user_id,
        {
            "descriptions": descriptions,
            "descriptions_confirmed": False,
            "anchors": [],
            "anchors_confirmed": False,
            "status": "descriptions_pending_review",
            "current_step": "descriptions",
        },
    )


def save_descriptions(model_id, user_id, payload):
    descriptions = _validate_list(payload.get("descriptions"), "descriptions")
    return _update_and_return(
        model_id,
        user_id,
        {
            "descriptions": descriptions,
            "descriptions_confirmed": True,
            "anchors": [],
            "anchors_confirmed": False,
            "status": "descriptions_confirmed",
            "current_step": "anchors",
        },
    )


def generate_anchors(model_id, user_id):
    model = _require_model(model_id, user_id)
    if not model.get("descriptions_confirmed"):
        raise ApplicationError("descriptions_required", "请先确认维度描述。", 409)
    anchors = _generate_stage(
        "anchors",
        {
            "context": model["context"],
            "dimensions": model["dimensions"],
            "descriptions": model["descriptions"],
        },
        lambda: build_anchor_drafts(model["context"], model["descriptions"]),
        _validate_anchors,
    )
    return _update_and_return(
        model_id,
        user_id,
        {
            "anchors": anchors,
            "anchors_confirmed": False,
            "status": "anchors_pending_review",
            "current_step": "anchors",
        },
    )


def save_anchors(model_id, user_id, payload):
    anchors = _validate_anchors(payload.get("anchors"))
    return _update_and_return(
        model_id,
        user_id,
        {
            "anchors": anchors,
            "anchors_confirmed": True,
            "status": "ready_to_export",
            "current_step": "export",
        },
    )


def build_model_export(model_id, user_id, export_format):
    if export_format not in {"docx", "pdf"}:
        raise ApplicationError("invalid_export_format", "仅支持 DOCX 和 PDF 导出。", 400)
    model = _require_model(model_id, user_id)
    if not model.get("anchors_confirmed"):
        raise ApplicationError("model_not_ready", "请先确认行为锚定后再导出。", 409)

    artifact_kind = "export_{}".format(export_format)
    cached = get_leadership_artifact(model_id, artifact_kind)
    if cached is not None:
        return {
            "content": cached["content_bytes"],
            "filename": cached["filename"],
            "mimetype": cached["mimetype"],
        }

    if export_format == "docx":
        content = build_leadership_docx_bytes(model)
        mimetype = DOCX_MIMETYPE
    else:
        content = build_leadership_pdf_bytes(model)
        mimetype = "application/pdf"

    filename = "{}.{}".format(_safe_filename(model["title"]), export_format)
    store_leadership_artifact(
        model_id,
        {
            "artifact_kind": artifact_kind,
            "filename": filename,
            "mimetype": mimetype,
            "content_bytes": content,
            "created_at": now_iso(),
        },
    )
    return {"content": content, "filename": filename, "mimetype": mimetype}


def _update_and_return(model_id, user_id, updates):
    updates["updated_at"] = now_iso()
    updated = update_leadership_model(model_id, user_id, updates)
    if updated is None:
        raise ApplicationError("leadership_model_not_found", "建模记录不存在。", 404)
    return _detail_payload(updated)


def _generate_stage(stage, model_data, fallback, validator):
    try:
        generated = generate_stage_with_llm(stage, model_data)
        return validator(generated)
    except Exception:
        return fallback()


def _require_model(model_id, user_id):
    model = get_leadership_model(model_id, user_id)
    if model is None:
        raise ApplicationError("leadership_model_not_found", "建模记录不存在。", 404)
    return model


def _detail_payload(model):
    workflow = build_workflow_state(model)
    current_step = infer_current_step(model)
    return {
        "model_id": model["model_id"],
        "title": model["title"],
        "status": model["status"],
        "current_step": current_step,
        "context": model["context"],
        "dimensions": model["dimensions"],
        "descriptions": model["descriptions"],
        "anchors": model["anchors"],
        "workflow": workflow,
        "export_urls": _export_urls(model),
        "created_at": model["created_at"],
        "updated_at": model["updated_at"],
    }


def _summary_payload(model):
    return {
        "model_id": model["model_id"],
        "title": model["title"],
        "company_name": model["context"].get("company_name") or "",
        "target_group": model["context"].get("target_group") or "",
        "status": model["status"],
        "current_step": infer_current_step(model),
        "workflow": build_workflow_state(model),
        "created_at": model["created_at"],
        "updated_at": model["updated_at"],
    }


def _export_urls(model):
    if not model.get("anchors_confirmed"):
        return {}
    return {
        "docx": "/api/leadership-models/{}/export?format=docx".format(model["model_id"]),
        "pdf": "/api/leadership-models/{}/export?format=pdf".format(model["model_id"]),
    }


def _validate_dimensions(value):
    dimensions = _validate_list(value, "dimensions")
    if len(dimensions) < 4 or len(dimensions) > 8:
        raise ApplicationError("invalid_dimensions", "维度数量必须为 4-8 个。", 400)
    normalized = []
    for index, item in enumerate(dimensions, 1):
        if not item.get("name") or not item.get("definition"):
            raise ApplicationError("invalid_dimensions", "维度名称和定义不能为空。", 400)
        normalized.append(
            {
                "id": int(item.get("id") or index),
                "name": str(item.get("name")).strip(),
                "definition": str(item.get("definition")).strip(),
                "sources": item.get("sources") if isinstance(item.get("sources"), list) else [],
                "priority": str(item.get("priority") or "重要维度").strip(),
            }
        )
    return normalized


def _validate_anchors(value):
    anchors = _validate_list(value, "anchors")
    for item in anchors:
        for key in ("excellent", "pass", "negative"):
            if not isinstance(item.get(key), list) or not item.get(key):
                raise ApplicationError("invalid_anchors", "行为锚定必须包含三组行为。", 400)
    return anchors


def _validate_list(value, field_name):
    if not isinstance(value, list) or not value:
        raise ApplicationError("invalid_{}".format(field_name), "{} 不能为空。".format(field_name), 400)
    return value


def _safe_filename(value):
    return "".join(char if char.isalnum() or char in "-_." else "_" for char in value)[:80]
