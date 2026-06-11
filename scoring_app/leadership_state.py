STEPS = [
    ("context", "建模背景"),
    ("dimensions", "维度框架"),
    ("descriptions", "维度描述"),
    ("anchors", "行为锚定"),
    ("export", "模型导出"),
]


def build_workflow_state(model):
    """Derive the visible state chain from persisted stage payloads."""
    context = model.get("context") or {}
    has_context = bool(context)
    context_done = bool(context.get("summary_confirmed") or model.get("status") == "context_ready")
    has_dimensions = bool(model.get("dimensions"))
    dimensions_done = bool(model.get("dimensions_confirmed"))
    has_descriptions = bool(model.get("descriptions"))
    descriptions_done = bool(model.get("descriptions_confirmed"))
    has_anchors = bool(model.get("anchors"))
    anchors_done = bool(model.get("anchors_confirmed"))

    states = {
        "context": _state(
            "context",
            context_done,
            has_context,
            True,
            "已确认" if context_done else ("待确认" if has_context else "待采集"),
        ),
        "dimensions": _state(
            "dimensions",
            dimensions_done,
            has_dimensions,
            context_done,
            "已确认" if dimensions_done else ("待确认" if has_dimensions else "待生成"),
        ),
        "descriptions": _state(
            "descriptions",
            descriptions_done,
            has_descriptions,
            dimensions_done,
            "已确认" if descriptions_done else ("待确认" if has_descriptions else "待生成"),
        ),
        "anchors": _state(
            "anchors",
            anchors_done,
            has_anchors,
            descriptions_done,
            "已确认" if anchors_done else ("待确认" if has_anchors else "待生成"),
        ),
        "export": {
            "key": "export",
            "label": "模型导出",
            "state": "available" if anchors_done else "locked",
            "status_label": "可导出" if anchors_done else "待生成",
            "done": False,
            "disabled": not anchors_done,
            "has_result": anchors_done,
        },
    }
    return [states[key] for key, _label in STEPS]


def infer_current_step(model):
    for item in build_workflow_state(model):
        if item["state"] in {"available", "pending-review"}:
            return item["key"]
    return "export"


def _state(key, done, draft_exists, available, status_label):
    if done:
        display_state = "done"
    elif draft_exists:
        display_state = "pending-review"
    elif available:
        display_state = "available"
    else:
        display_state = "locked"
    label = dict(STEPS)[key]
    return {
        "key": key,
        "label": label,
        "state": display_state,
        "status_label": status_label,
        "done": done,
        "disabled": display_state == "locked",
        "has_result": done or draft_exists,
    }
