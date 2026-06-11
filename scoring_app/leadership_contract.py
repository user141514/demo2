ANCHOR_LEVELS = {
    "excellent": {"label": "优秀", "legacy": "excellent", "prefix": "E"},
    "standard": {"label": "达标", "legacy": "pass", "prefix": "S"},
    "below": {"label": "不达标", "legacy": "negative", "prefix": "B"},
}


def normalize_dimension(item, index=1):
    dim_id = item.get("id") or item.get("dimension_id") or index
    source_refs = _source_refs(item.get("source_refs") or item.get("sources"))
    return {
        "id": dim_id,
        "name": str(item.get("name") or item.get("dimension_name") or "").strip(),
        "definition": str(item.get("definition") or "").strip(),
        "sources": _source_list(source_refs),
        "source_refs": source_refs,
        "priority": str(item.get("priority") or "important").strip(),
        "rationale": str(item.get("rationale") or "").strip(),
    }


def normalize_dimensions(items):
    return [normalize_dimension(item, index + 1) for index, item in enumerate(items or [])]


def normalize_dimension_candidates(value):
    if isinstance(value, dict):
        recommended = value.get("recommended") or value.get("dimensions") or []
        alternatives = value.get("alternatives") or []
    else:
        recommended = value or []
        alternatives = []
    return {
        "recommended": normalize_dimensions(recommended),
        "alternatives": normalize_dimensions(alternatives),
    }


def normalize_description(item, dimension=None):
    dimension = dimension or {}
    dimension_id = item.get("dimension_id") or item.get("id") or dimension.get("id")
    name = item.get("dimension_name") or item.get("name") or dimension.get("name") or "未命名维度"
    description = (
        item.get("description")
        or item.get("core_requirement")
        or item.get("value_contribution")
        or ""
    )
    quality_check = item.get("quality_check") or _quality_check_from_legacy(item.get("quality_status"))
    return {
        "dimension_id": dimension_id,
        "dimension_name": name,
        "name": name,
        "description": str(description).strip(),
        "quality_check": quality_check,
        "core_requirement": str(item.get("core_requirement") or description).strip(),
        "value_contribution": str(item.get("value_contribution") or "").strip(),
        "quality_status": _legacy_quality_status(quality_check),
    }


def normalize_descriptions(items, dimensions=None):
    by_id = {item.get("id"): item for item in dimensions or []}
    return [
        normalize_description(item, by_id.get(item.get("dimension_id")))
        for item in items or []
    ]


def normalize_anchor(item, dimension=None):
    dimension = dimension or {}
    dimension_id = item.get("dimension_id") or item.get("id") or dimension.get("id")
    name = item.get("dimension_name") or item.get("name") or dimension.get("name") or "未命名维度"
    source = item.get("anchors") if isinstance(item.get("anchors"), dict) else item
    anchors = {
        level: _anchor_items(
            source.get(level) or source.get(spec["legacy"]) or [],
            dimension_id,
            level,
        )
        for level, spec in ANCHOR_LEVELS.items()
    }
    return {
        "dimension_id": dimension_id,
        "dimension_name": name,
        "name": name,
        "anchors": anchors,
        "excellent": _anchor_texts(anchors["excellent"]),
        "pass": _anchor_texts(anchors["standard"]),
        "negative": _anchor_texts(anchors["below"]),
    }


def normalize_anchors(items, dimensions=None):
    by_id = {item.get("id"): item for item in dimensions or []}
    return [normalize_anchor(item, by_id.get(item.get("dimension_id"))) for item in items or []]


def set_context_field(context, field, value):
    context = dict(context or {})
    if field in {"strategy_keywords", "management_pains", "excellent_behaviors", "standard_refs"}:
        context[field] = _split_list(value)
    elif field:
        context[field] = str(value or "").strip()
    context["missing_fields"] = missing_context_fields(context)
    return context


def missing_context_fields(context):
    return [
        label
        for key, label in [
            ("industry", "行业/业务类型"),
            ("company_size", "企业规模/发展阶段"),
            ("strategy_keywords", "当前战略重点"),
            ("management_pains", "主要管理痛点"),
            ("target_group", "建模对象层级/群体"),
            ("excellent_behaviors", "优秀管理者画像"),
        ]
        if not context.get(key)
    ]


def context_summary(context):
    return {
        "enterprise": "{}｜{}｜{}".format(
            context.get("company_name") or "未命名企业",
            context.get("industry") or "未提供行业",
            context.get("company_size") or "未提供规模",
        ),
        "target": context.get("target_group") or "未确认",
        "strategy": "、".join(context.get("strategy_keywords") or ["未提供"]),
        "pains": "、".join(context.get("management_pains") or ["未提供"]),
        "excellent_profile": "、".join(context.get("excellent_behaviors") or ["未提供"]),
        "documents": "、".join(context.get("document_keywords") or ["暂无上传解析关键词"]),
        "standards": "、".join(context.get("standard_refs") or ["综合基线（内置）"]),
        "missing_fields": missing_context_fields(context),
    }


def _source_refs(value):
    if isinstance(value, dict):
        return {
            "strategy": value.get("strategy"),
            "framework": value.get("framework"),
            "interview": value.get("interview"),
        }
    refs = {"strategy": None, "framework": None, "interview": None}
    if isinstance(value, list):
        for item in value:
            source_type = str(item.get("type") or "")
            text = item.get("text")
            if "战略" in source_type:
                refs["strategy"] = text
            elif "标准" in source_type:
                refs["framework"] = text
            elif "访谈" in source_type:
                refs["interview"] = text
    return refs


def _source_list(source_refs):
    labels = {"strategy": "战略映射", "framework": "标准库参照", "interview": "访谈归纳"}
    rows = [{"type": labels[key], "text": value} for key, value in source_refs.items() if value]
    return rows or [{"type": "信息缺口", "text": "材料不足，需补充战略、痛点或优秀行为证据。"}]


def _anchor_items(items, dimension_id, level):
    prefix = ANCHOR_LEVELS[level]["prefix"]
    base = str(dimension_id) if str(dimension_id).upper().startswith("D") else "D{}".format(dimension_id)
    rows = []
    for index, item in enumerate(items or [], 1):
        if isinstance(item, dict):
            text = item.get("text") or ""
            anchor_id = item.get("id") or "{}-{}{}".format(base, prefix, index)
        else:
            text = str(item or "")
            anchor_id = "{}-{}{}".format(base, prefix, index)
        if text.strip():
            rows.append({"id": anchor_id, "text": text.strip(), "level": level})
    return rows


def _anchor_texts(items):
    return [item.get("text") for item in items or [] if item.get("text")]


def _quality_check_from_legacy(value):
    if isinstance(value, dict):
        return {
            "passed": value.get("status") == "passed" or bool(value.get("passed")),
            "issues": value.get("issues") or [],
        }
    return {"passed": True, "issues": []}


def _legacy_quality_status(quality_check):
    return {
        "status": "passed" if quality_check.get("passed") else "review",
        "issues": quality_check.get("issues") or [],
    }


def _split_list(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [
        item.strip()
        for item in str(value or "").replace("；", "\n").replace("，", "\n").splitlines()
        if item.strip()
    ]
