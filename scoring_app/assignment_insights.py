import re


TOOL_KEYWORDS = [
    "RACI",
    "5WHY",
    "5 Why",
    "逻辑树",
    "ERP库存数据",
    "ERP",
    "PPT",
    "ASTRAL",
]

CASE_KEYWORDS = ["星链计划", "LTP", "CCC", "钢材发料", "真实成本", "业务痛点"]
ACTION_KEYWORDS = ["行动", "分工", "审批", "采购", "仓库", "系统开发", "责任到人", "追踪会"]
REFLECTION_KEYWORDS = ["复盘", "反思", "个人失误", "能力短板", "认知迭代", "ASTRAL"]
PLANNING_KEYWORDS = ["目标", "规划", "里程碑", "资源", "数据权限", "预算", "ERP库存数据", "90天", "四季度"]
EXPRESSION_KEYWORDS = ["语速偏快", "停顿", "节奏", "PPT", "现场表达", "评委记录", "逻辑清晰"]


def extract_assignment_insights(document_text, transcript_text):
    document_sentences = _split_sentences(document_text)
    transcript_sentences = _split_sentences(transcript_text)
    return {
        "case": _find_signals(document_sentences, CASE_KEYWORDS, 4),
        "tools": _find_signals(document_sentences, TOOL_KEYWORDS, 4),
        "metrics": _extract_metric_signals(document_sentences, 5),
        "actions": _find_signals(document_sentences, ACTION_KEYWORDS, 5),
        "reflection": _find_signals(document_sentences, REFLECTION_KEYWORDS, 4),
        "planning": _find_signals(document_sentences, PLANNING_KEYWORDS, 5),
        "expression": _find_signals(transcript_sentences, EXPRESSION_KEYWORDS, 4),
        "transcript_metrics": _extract_metric_signals(transcript_sentences, 3),
    }


def select_dimension_signals(dimension, insights, max_items=3):
    name = dimension["name"]
    source_key = dimension.get("source_key")
    if source_key is None and dimension.get("material_source") == "录音转写":
        source_key = "transcript"
    if source_key == "transcript":
        category_names = ["expression", "transcript_metrics", "metrics"]
    elif "战略" in name or "知行" in name:
        category_names = ["case", "tools", "actions", "metrics"]
    elif "复盘" in name or "认知" in name:
        category_names = ["reflection", "actions", "case"]
    elif "课题" in name or "创新" in name:
        category_names = ["case", "metrics", "planning"]
    elif "规划" in name or "前瞻" in name:
        category_names = ["planning", "metrics", "actions"]
    else:
        category_names = ["case", "tools", "metrics", "actions"]

    selected = []
    for category_name in category_names:
        for signal in insights.get(category_name, []):
            if signal not in selected:
                selected.append(signal)
            if len(selected) >= max_items:
                return selected
    return selected


def format_insight_section(insights):
    lines = []
    labels = [
        ("case", "案例/业务场景"),
        ("tools", "工具方法"),
        ("metrics", "量化数据"),
        ("actions", "行动措施"),
        ("reflection", "复盘反思"),
        ("planning", "规划资源"),
        ("expression", "现场表达"),
    ]
    for key, label in labels:
        values = insights.get(key) or []
        if values:
            lines.append("- {}：{}".format(label, "；".join(values[:4])))
    return "\n".join(lines) or "- 未识别到足够具体的作业信号；评价时必须指出缺少案例/数据/反思/资源规划。"


def extract_evidence_signal(text):
    evidence = text
    if evidence.startswith("优势亮点："):
        evidence = evidence[len("优势亮点：") :]
    match = re.search(r"可识别到(.+?)。", evidence)
    if match:
        return match.group(1)
    match = re.search(r"材料围绕「(.+?)」(.+?)，", evidence)
    if match:
        return "围绕{}的{}".format(match.group(1), match.group(2))
    if "能够形成基本表述" in evidence:
        return "基本表述和材料完整度线索"
    return _limit(evidence, 70)


def condense_takeaway(text):
    cleaned = _strip_takeaway_prefix(text)
    sentence = cleaned.split("。")[0]
    return _limit(sentence, 80)


def _find_signals(sentences, keywords, limit):
    signals = []
    for sentence in sentences:
        if _looks_like_identifier_sentence(sentence):
            continue
        if any(keyword in sentence for keyword in keywords):
            signals.append(_compress_signal(sentence))
        if len(signals) >= limit:
            break
    return _ordered_unique(signals)


def _extract_metric_signals(sentences, limit):
    signals = []
    for sentence in sentences:
        if _looks_like_identifier_sentence(sentence):
            continue
        if _has_metric(sentence):
            signals.append(_compress_signal(sentence))
        if len(signals) >= limit:
            break
    return _ordered_unique(signals)


def _has_metric(text):
    return bool(re.search(r"\d+(?:\.\d+)?\s*(?:%|天|分|次|个|项|人|月|年|以内|以上|以下)?", text))


def _looks_like_identifier_sentence(text):
    compact = re.sub(r"\s+", "", text)
    if re.search(r"(股票代码|证券代码)[:：]?\d{6}", compact):
        return True
    if re.search(r"\b\d{6}\.(SZ|SH|BJ|HK)\b", text, re.IGNORECASE):
        return True
    return False


def _split_sentences(text):
    normalized = re.sub(r"\s+", " ", (text or "").strip())
    return [
        item.strip(" ，,；;")
        for item in re.split(r"[。！？\n\r]+", normalized)
        if item.strip(" ，,；;")
    ]


def _compress_signal(sentence, size=80):
    cleaned = re.sub(r"\s+", " ", sentence).strip(" ，,；;")
    if len(cleaned) <= size:
        return cleaned

    metric_match = re.search(r"[^。！？；;，,]{0,28}\d+(?:\.\d+)?[^。！？；;]{0,45}", cleaned)
    if metric_match:
        return _limit(metric_match.group(0).strip(" ，,；;"), size)

    for keyword in TOOL_KEYWORDS + CASE_KEYWORDS + EXPRESSION_KEYWORDS:
        index = cleaned.find(keyword)
        if index >= 0:
            start = max(0, index - 24)
            end = min(len(cleaned), index + 56)
            return _limit(cleaned[start:end].strip(" ，,；;"), size)

    return _limit(cleaned, size)


def _ordered_unique(items):
    seen = set()
    unique = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique


def _strip_tail(text):
    return text.split("表现")[0].split("仍有")[0]


def _strip_takeaway_prefix(text):
    cleaned = text
    for prefix in (
        "补充结构化反思页，",
        "补强战略到行动的逻辑闭环：",
        "强化课题创新突破点：",
        "完善资源规划与协同安排：",
        "优化现场表达节奏：",
    ):
        cleaned = cleaned.replace(prefix, "")
    return _strip_tail(cleaned)


def _limit(text, size):
    if len(text) <= size:
        return text
    return text[: size - 1].rstrip() + "…"
