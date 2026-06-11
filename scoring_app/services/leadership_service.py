from uuid import uuid4

from ..core.errors import ApplicationError
from ..leadership_documents import extract_leadership_source_file
from ..leadership_export import (
    DOCX_MIMETYPE,
    build_leadership_docx_bytes,
    build_leadership_pdf_bytes,
)
from ..leadership_contract import (
    context_summary,
    missing_context_fields,
    normalize_anchor,
    normalize_anchors,
    normalize_description,
    normalize_descriptions,
    normalize_dimension_candidates,
    normalize_dimensions,
)
from ..leadership_generation import (
    apply_context_message,
    build_anchor_drafts,
    build_description_drafts,
    build_dimension_candidates,
    build_dimension_drafts,
    build_single_anchor_text,
    build_single_description_draft,
    merge_source_text,
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
    is_ready_context = bool(context.get("company_name") and context.get("target_group"))
    context["summary_confirmed"] = is_ready_context
    context["context_summary"] = context_summary(context)

    model_id = uuid4().hex
    created_at = now_iso()
    title = "{} {} 领导力模型".format(
        context.get("company_name") or "未命名企业",
        context.get("target_group") or "待定对象",
    )
    record = {
        "model_id": model_id,
        "user_id": user_id,
        "title": title,
        "context": context,
        "status": "context_ready" if is_ready_context else "context_collecting",
        "current_step": "dimensions" if is_ready_context else "context",
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


def add_source_file(model_id, user_id, files):
    model = _require_model(model_id, user_id)
    source_file, source_text = extract_leadership_source_file(files.get("source_file"))
    if source_file is None:
        raise ApplicationError("missing_source_file", "请上传 PDF、DOCX、TXT 或 Markdown 文件。", 400)
    created_at = now_iso()
    store_leadership_artifact(
        model_id,
        {
            "artifact_kind": "source_file_{}".format(uuid4().hex[:10]),
            "filename": source_file["filename"],
            "mimetype": source_file["mimetype"],
            "content_bytes": source_file["content_bytes"],
            "created_at": created_at,
        },
    )
    context = merge_source_text(model["context"], source_text, source_file["filename"])
    return _update_and_return(
        model_id,
        user_id,
        {
            "context": context,
            "status": "context_pending_confirm" if not context.get("summary_confirmed") else model["status"],
            "current_step": "context" if not context.get("summary_confirmed") else model["current_step"],
        },
    )


def handle_context_message(model_id, user_id, payload):
    model = _require_model(model_id, user_id)
    message = (payload.get("message") or "").strip()
    if not message:
        raise ApplicationError("missing_message", "请先输入需要记录的信息。", 400)
    context, assistant_message, next_field = apply_context_message(
        model["context"],
        payload.get("field"),
        message,
    )
    updated = _update_and_return(
        model_id,
        user_id,
        {"context": context, "status": "context_pending_confirm", "current_step": "context"},
    )
    updated["assistant_message"] = assistant_message
    updated["next_question"] = next_field
    return updated


def confirm_context(model_id, user_id):
    model = _require_model(model_id, user_id)
    context = dict(model["context"] or {})
    context["summary_confirmed"] = True
    context["missing_fields"] = missing_context_fields(context)
    context["context_summary"] = context_summary(context)
    candidates = _generate_dimension_candidates(context)
    context["dimension_candidates"] = candidates
    return _update_and_return(
        model_id,
        user_id,
        {
            "title": "{} {} 领导力模型".format(
                context.get("company_name") or "未命名企业",
                context.get("target_group") or "待定对象",
            ),
            "context": context,
            "dimensions": candidates["recommended"],
            "dimensions_confirmed": False,
            "descriptions": [],
            "descriptions_confirmed": False,
            "anchors": [],
            "anchors_confirmed": False,
            "status": "dimensions_pending_review",
            "current_step": "dimensions",
        },
    )


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
    candidates = _generate_dimension_candidates(model["context"])
    context = dict(model["context"] or {})
    context["dimension_candidates"] = candidates
    return _update_and_return(
        model_id,
        user_id,
        {
            "context": context,
            "dimensions": candidates["recommended"],
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
    dimensions = _validate_dimensions(payload.get("dimensions"), min_count=3)
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
        lambda value: _validate_descriptions(value, model["dimensions"]),
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
    model = _require_model(model_id, user_id)
    descriptions = _validate_descriptions(payload.get("descriptions"), model["dimensions"])
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
        lambda value: _validate_anchors(value, model["dimensions"]),
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
    model = _require_model(model_id, user_id)
    anchors = _validate_anchors(payload.get("anchors"), model["dimensions"])
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


def regenerate_description(model_id, user_id, dimension_id, payload):
    model = _require_model(model_id, user_id)
    dimensions = normalize_dimensions(model["dimensions"])
    dimension = _find_dimension(dimensions, dimension_id)
    if dimension is None:
        raise ApplicationError("dimension_not_found", "未找到对应维度。", 404)
    descriptions = normalize_descriptions(model["descriptions"], dimensions)
    replacement = build_single_description_draft(
        model["context"],
        dimension,
        payload.get("direction") or "",
    )
    descriptions = _replace_by_dimension_id(descriptions, dimension_id, replacement)
    return _update_and_return(
        model_id,
        user_id,
        {
            "descriptions": descriptions,
            "descriptions_confirmed": False,
            "status": "descriptions_pending_review",
            "current_step": "descriptions",
        },
    )


def regenerate_anchor(model_id, user_id, anchor_id, payload):
    model = _require_model(model_id, user_id)
    dimensions = normalize_dimensions(model["dimensions"])
    anchors = normalize_anchors(model["anchors"], dimensions)
    target = _locate_anchor(anchors, anchor_id)
    if target is None:
        raise ApplicationError("anchor_not_found", "未找到对应行为锚定。", 404)
    anchor, level, index = target
    anchor["anchors"][level][index]["text"] = build_single_anchor_text(
        payload.get("level") or level,
        payload.get("direction") or "",
    )
    updated_anchor = normalize_anchor(anchor)
    anchors = _replace_by_dimension_id(anchors, updated_anchor["dimension_id"], updated_anchor)
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

    normalized = _normalized_model(model)
    if export_format == "docx":
        content = build_leadership_docx_bytes(normalized)
        mimetype = DOCX_MIMETYPE
    else:
        content = build_leadership_pdf_bytes(normalized)
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
    normalized = _normalized_model(model)
    workflow = build_workflow_state(model)
    current_step = infer_current_step(model)
    return {
        "model_id": model["model_id"],
        "title": normalized["title"],
        "status": model["status"],
        "current_step": current_step,
        "context": normalized["context"],
        "dimension_candidates": normalized["dimension_candidates"],
        "dimensions": normalized["dimensions"],
        "descriptions": normalized["descriptions"],
        "anchors": normalized["anchors"],
        "workflow": workflow,
        "export_urls": _export_urls(model),
        "created_at": model["created_at"],
        "updated_at": model["updated_at"],
    }


def _summary_payload(model):
    context = model["context"] or {}
    return {
        "model_id": model["model_id"],
        "title": model["title"],
        "company_name": context.get("company_name") or "",
        "target_group": context.get("target_group") or "",
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


def _generate_dimension_candidates(context):
    try:
        generated = generate_stage_with_llm("dimensions", {"context": context})
        candidates = normalize_dimension_candidates(generated)
        if candidates["recommended"] and candidates["alternatives"]:
            return candidates
    except Exception:
        pass
    return build_dimension_candidates(context)


def _validate_dimensions(value, min_count=4):
    dimensions = _validate_list(value, "dimensions")
    normalized = normalize_dimensions(dimensions)
    if len(normalized) < min_count or len(normalized) > 8:
        raise ApplicationError("invalid_dimensions", "维度数量必须为 {}-8 个。".format(min_count), 400)
    for item in normalized:
        if not item.get("name") or not item.get("definition"):
            raise ApplicationError("invalid_dimensions", "维度名称和定义不能为空。", 400)
    return normalized


def _validate_descriptions(value, dimensions):
    descriptions = _validate_list(value, "descriptions")
    normalized = normalize_descriptions(descriptions, normalize_dimensions(dimensions))
    for item in normalized:
        if not item.get("description"):
            raise ApplicationError("invalid_descriptions", "维度描述不能为空。", 400)
    return normalized


def _validate_anchors(value, dimensions=None):
    anchors = _validate_list(value, "anchors")
    normalized = normalize_anchors(anchors, normalize_dimensions(dimensions or []))
    for item in normalized:
        for key in ("excellent", "standard", "below"):
            if not item.get("anchors", {}).get(key):
                raise ApplicationError("invalid_anchors", "行为锚定必须包含三组行为。", 400)
    return normalized


def _validate_list(value, field_name):
    if not isinstance(value, list) or not value:
        raise ApplicationError("invalid_{}".format(field_name), "{} 不能为空。".format(field_name), 400)
    return value


def _safe_filename(value):
    return "".join(char if char.isalnum() or char in "-_." else "_" for char in value)[:80]


def _normalized_model(model):
    context = dict(model.get("context") or {})
    context["missing_fields"] = context.get("missing_fields") or missing_context_fields(context)
    context["context_summary"] = context.get("context_summary") or context_summary(context)
    dimensions = normalize_dimensions(model.get("dimensions") or [])
    descriptions = normalize_descriptions(model.get("descriptions") or [], dimensions)
    anchors = normalize_anchors(model.get("anchors") or [], dimensions)
    candidates = normalize_dimension_candidates(
        context.get("dimension_candidates") or {"recommended": dimensions, "alternatives": []}
    )
    return {
        **model,
        "title": model.get("title") or "{} {} 领导力模型".format(
            context.get("company_name") or "未命名企业",
            context.get("target_group") or "待定对象",
        ),
        "context": context,
        "dimension_candidates": candidates,
        "dimensions": dimensions,
        "descriptions": descriptions,
        "anchors": anchors,
    }


def _find_dimension(dimensions, dimension_id):
    wanted = str(dimension_id)
    for item in dimensions:
        if str(item.get("id")) == wanted:
            return item
    return None


def _replace_by_dimension_id(items, dimension_id, replacement):
    wanted = str(dimension_id)
    updated = []
    replaced = False
    for item in items:
        if str(item.get("dimension_id")) == wanted:
            updated.append(replacement)
            replaced = True
        else:
            updated.append(item)
    if not replaced:
        updated.append(replacement)
    return updated


def _locate_anchor(anchors, anchor_id):
    for anchor in anchors:
        for level, items in (anchor.get("anchors") or {}).items():
            for index, item in enumerate(items):
                if item.get("id") == anchor_id:
                    return anchor, level, index
    return None
