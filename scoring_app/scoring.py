import logging
import re
from uuid import uuid4

from .assignment_insights import (
    condense_takeaway,
    extract_assignment_insights,
    extract_evidence_signal,
    select_dimension_signals,
    summarize_missing_evidence,
)
from .core.text_quality import looks_like_garbled_text
from .live_scoring import live_score_submission
from .rules import DISCLAIMER, get_report_definition, score_to_level, total_to_level
from .utils import now_iso


logger = logging.getLogger(__name__)


class ScoringError(Exception):
    pass


def score_submission(report_type, document_text, transcript_text, metadata):
    # === GRAPH KILL SWITCH ===
    import os
    if os.getenv("SCORING_USE_GRAPH", "").lower() in ("1", "true", "yes"):
        from .graph.pipeline import execute_scoring_pipeline

        initial_state = {
            "report_type": report_type,
            "document_text": document_text,
            "transcript_text": transcript_text,
            "metadata": metadata,
            "name": metadata.get("name", ""),
            "org": metadata.get("org", ""),
            "score_date": metadata.get("date", ""),
            "note": metadata.get("note", ""),
            "pdf_bytes": b"",
        }
        result = execute_scoring_pipeline(initial_state)
        result.setdefault("scoring_mode", "")
        result.setdefault("llm_provider", "")
        result.setdefault("llm_model", "")
        return result
    # === END KILL SWITCH ===

    if not document_text or len(document_text.strip()) < 40:
        raise ScoringError("未能获取足够的文档文本，无法生成评分结果。")

    definition = get_report_definition(report_type)
    transcript_present = bool(transcript_text.strip())
    assignment_insights = extract_assignment_insights(document_text, transcript_text)

    try:
        live_payload = live_score_submission(
            report_type=report_type,
            definition=definition,
            document_text=document_text,
            transcript_text=transcript_text,
            assignment_insights=assignment_insights,
        )
        dimension_results = live_payload["dimensions"]
        overall_comment = live_payload["overall_comment"]
        report_strengths = live_payload.get("strengths") or None
        report_improvements = live_payload.get("improvements") or None
        scoring_mode = live_payload.get("mode", "live")
        llm_provider = live_payload.get("provider", "")
        llm_model = live_payload.get("model", "")
    except Exception:
        logger.exception(
            "Live LLM scoring failed; falling back to heuristic scoring. report_type=%s transcript_present=%s",
            report_type,
            transcript_present,
        )
        dimension_results = _build_heuristic_dimensions(
            definition=definition,
            document_text=document_text,
            transcript_text=transcript_text,
            transcript_present=transcript_present,
            assignment_insights=assignment_insights,
        )
        strengths, improvements = _build_takeaways(
            [item for item in dimension_results if item["score"] is not None],
            assignment_insights=assignment_insights,
        )
        overall_comment = _build_overall_comment(
            report_type=report_type,
            total_score=None,
            strengths=strengths,
            improvements=improvements,
            transcript_present=transcript_present,
            assignment_insights=assignment_insights,
        )
        report_strengths = None
        report_improvements = None
        scoring_mode = "heuristic"
        llm_provider = ""
        llm_model = ""

    result = _assemble_result(
        report_type=report_type,
        metadata=metadata,
        transcript_present=transcript_present,
        dimension_results=dimension_results,
        overall_comment=overall_comment,
        report_strengths=report_strengths,
        report_improvements=report_improvements,
        assignment_insights=assignment_insights,
        clean_dimension_text=(scoring_mode == "live"),
    )
    result["scoring_mode"] = scoring_mode
    result["llm_provider"] = llm_provider
    result["llm_model"] = llm_model
    return result

def _assemble_result(
    report_type,
    metadata,
    transcript_present,
    dimension_results,
    overall_comment,
    report_strengths=None,
    report_improvements=None,
    assignment_insights=None,
    clean_dimension_text=False,
):
    if clean_dimension_text:
        dimension_results = [_clean_dimension_text(item) for item in dimension_results]
    scored_dimensions = [item for item in dimension_results if item["score"] is not None]
    if not scored_dimensions:
        raise ScoringError("当前材料无法形成有效评分。")

    weighted_points = sum(
        item["score"] * (item["actual_weight"] / 10.0) for item in scored_dimensions
    )
    available_weight = sum(item["actual_weight"] for item in scored_dimensions)
    total_score = round((weighted_points / available_weight) * 100.0, 1)

    doc_scores = [
        item["score"]
        for item in dimension_results
        if item["material_source"] == "文档" and item["score"] is not None
    ]
    audio_scores = [
        item["score"]
        for item in dimension_results
        if item["material_source"] == "录音转写" and item["score"] is not None
    ]
    doc_average = round(sum(doc_scores) / len(doc_scores), 1) if doc_scores else None
    audio_average = round(sum(audio_scores) / len(audio_scores), 1) if audio_scores else None
    lowest_dimension = min(scored_dimensions, key=lambda item: item["score"])
    generated_strengths, generated_improvements = _build_takeaways(
        scored_dimensions,
        assignment_insights=assignment_insights,
    )
    strengths = report_strengths or generated_strengths
    improvements = report_improvements or generated_improvements

    if overall_comment:
        overall_comment = _limit(overall_comment, 700)
    else:
        overall_comment = _build_overall_comment(
            report_type=report_type,
            total_score=total_score,
            strengths=strengths,
            improvements=improvements,
            transcript_present=transcript_present,
            assignment_insights=assignment_insights,
        )

    return {
        "score_id": uuid4().hex,
        "name": metadata["name"],
        "org": metadata["org"],
        "report_type": report_type,
        "course_session": metadata.get("course_session", ""),
        "date": metadata["date"],
        "note": metadata.get("note", ""),
        "pdf_filename": metadata.get("pdf_filename", ""),
        "upload_path": metadata.get("upload_path", ""),
        "document_preview": metadata.get("document_preview", ""),
        "transcript_present": transcript_present,
        "created_at": now_iso(),
        "total_score": total_score,
        "total_level": total_to_level(total_score),
        "doc_average": doc_average,
        "audio_average": audio_average,
        "lowest_dimension": {
            "name": lowest_dimension["name"],
            "score": lowest_dimension["score"],
        },
        "overall_comment": overall_comment,
        "strengths": strengths,
        "improvements": improvements,
        "disclaimer": DISCLAIMER,
        "dimensions": dimension_results,
    }


def _build_heuristic_dimensions(
    definition,
    document_text,
    transcript_text,
    transcript_present,
    assignment_insights=None,
):
    dimension_results = []
    for dimension in definition["dimensions"]:
        if dimension["source_key"] == "transcript" and not transcript_present:
            result = {
                "id": dimension["id"],
                "name": dimension["name"],
                "group_name": dimension["group"],
                "group_weight": dimension["group_weight"],
                "actual_weight": dimension["actual_weight"],
                "material_source": dimension["material_source"],
                "score": None,
                "level_label": None,
                "evidence": "录音材料未提供。",
                "comment": "",
            }
        else:
            relevant_text = (
                document_text if dimension["source_key"] == "document" else transcript_text
            )
            score = _score_dimension(relevant_text, dimension, assignment_insights)
            result = {
                "id": dimension["id"],
                "name": dimension["name"],
                "group_name": dimension["group"],
                "group_weight": dimension["group_weight"],
                "actual_weight": dimension["actual_weight"],
                "material_source": dimension["material_source"],
                "score": score,
                "level_label": score_to_level(score),
                "evidence": _build_evidence(
                    relevant_text,
                    dimension,
                    score,
                    assignment_insights,
                ),
                "comment": _build_comment(
                    score,
                    dimension,
                    transcript_present,
                    assignment_insights,
                ),
            }
        dimension_results.append(result)
    return dimension_results

def _score_dimension(text, dimension, assignment_insights=None):
    normalized = text.strip()
    keyword_hits = [kw for kw in dimension["keywords"] if kw in normalized]
    coverage = len(set(keyword_hits)) / float(len(dimension["keywords"]) or 1)
    length_bonus = min(len(normalized) / 1200.0, 1.0) * 0.7
    score = 4.1 + (coverage * 3.7) + length_bonus
    completeness = _dimension_completeness(dimension, assignment_insights or {})

    if dimension["needs_numbers"] and re.search(r"\d+(\.\d+)?%?", normalized):
        score += 0.5
    if completeness >= 4:
        score += 1.0
    elif completeness <= 1:
        score -= 0.8
    if not keyword_hits and len(normalized) < 150:
        score -= 0.8
    if len(normalized) < 60:
        score -= 0.4
    if dimension["source_key"] == "transcript" and not (assignment_insights or {}).get("expression"):
        score = min(score - 0.7, 4.6)
    if re.search(r"(没有说明|比较笼统|只说会继续沟通|缺少具体)", normalized):
        score -= 0.7
    if looks_like_garbled_text(normalized):
        score = min(score, 4.2)
    score = max(3.8, min(9.0, score))
    return round(score, 1)


def _build_evidence(text, dimension, score, assignment_insights=None):
    normalized = text.strip()
    keywords = dimension["keywords"]
    keyword_hits = _ordered_unique([keyword for keyword in keywords if keyword in normalized])
    readable_sentences = [
        sentence for sentence in _split_sentences(normalized)
        if not looks_like_garbled_text(sentence)
    ]
    focus = dimension["focus"]
    source = dimension["material_source"]
    has_numbers = _has_relevant_number(readable_sentences, keyword_hits)
    signals = select_dimension_signals(dimension, assignment_insights or {}, max_items=4)
    signal_text = _join_signals(signals)

    if not readable_sentences:
        return "优势亮点：当前{}文本可读性不足，尚难识别与「{}」直接相关的有效信息，因此该维度暂缺可用于支撑评分的具体亮点。".format(
            source,
            focus,
        )

    if keyword_hits:
        keyword_text = "、".join(keyword_hits[:5])
        if len(keyword_hits) >= 4:
            coverage_text = "覆盖较完整"
        elif len(keyword_hits) >= 2:
            coverage_text = "已有一定覆盖"
        else:
            coverage_text = "形成初步覆盖"
        number_text = "，同时出现可追踪的量化信号" if has_numbers else ""
        assignment_text = "作业证据包括{}。".format(signal_text) if signals else _missing_sentence(assignment_insights)
        return _limit(
            "优势亮点：{}材料围绕「{}」{}，命中{}等相关评价点{}。{}这些证据能说明该维度的支撑强弱和分数来源。".format(
                source,
                focus,
                coverage_text,
                keyword_text,
                number_text,
                assignment_text,
            ),
            220,
        )

    assignment_text = (
        "可参考的作业线索为{}。".format(signal_text)
        if signals
        else _missing_sentence(assignment_insights)
    )
    return _limit(
        "优势亮点：{}已出现与「{}」相关的基础表述。{}但工具方法、量化结果或行为闭环仍不足，支撑力度有限。".format(
            source,
            focus,
            assignment_text,
        ),
        220,
    )


def _build_comment(score, dimension, transcript_present, assignment_insights=None):
    focus = dimension["focus"]
    signals = select_dimension_signals(dimension, assignment_insights or {}, max_items=2)
    signal_text = _join_signals(signals)
    if signals:
        follow_up = "当前缺口是证据链还不够完整，建议围绕{}补齐动作分工、结果验证和复盘解释。".format(signal_text)
    else:
        follow_up = "{}，建议围绕{}补齐对应材料。".format(_missing_sentence(assignment_insights), focus)
    if not transcript_present:
        follow_up = "当前仅基于已提供材料形成判断，建议后续补充完整录音信息，以便同时评估现场表达、节奏控制和逻辑呈现。"
    return _limit("改进空间：{}".format(follow_up), 180)


def _build_takeaways(scored_dimensions, assignment_insights=None):
    ranked = sorted(scored_dimensions, key=lambda item: item["score"], reverse=True)
    strengths = [_strength_takeaway(item) for item in ranked[:3]]
    weaker = sorted(scored_dimensions, key=lambda item: item["score"])[:4]
    improvements = [
        _improvement_takeaway(item, assignment_insights=assignment_insights)
        for item in weaker
    ]
    if len(improvements) < 5:
        improvements.append(
            "将关键量化成效做成视觉冲击页：把百分比、天数、阶段改善等核心数据放大呈现，配合趋势图或箭头对比，避免在正文或口述中被评委遗漏。"
        )
    if len(improvements) < 6:
        improvements.append(
            "强化正式汇报的叙事闭环：建议按照问题背景、工具方法、行动分工、结果验证、个人反思的顺序组织材料，让评委能快速看见管理成长路径。"
        )
    return strengths, improvements


def _strength_takeaway(item):
    signal = extract_evidence_signal(item.get("evidence") or "")
    if item["score"] >= 8.0:
        tone = "优势较突出"
    elif item["score"] >= 7.0:
        tone = "证据较扎实"
    elif item["score"] >= 6.0:
        tone = "已经形成可说明的证据"
    else:
        tone = "目前仅能确认基础线索"
    return _limit(
        "{}得分{}，{}，材料中可见{}。".format(
            item["name"],
            item["score"],
            tone,
            signal,
        ),
        160,
    )


def _improvement_takeaway(item, assignment_insights=None):
    name = item["name"]
    signals = _join_signals(select_dimension_signals(item, assignment_insights or {}, max_items=2))
    if "复盘" in name or "认知" in name:
        return "补充结构化反思页，直面个人不足：建议呈现最大收获、关键失误或能力短板、认知变化和1-2条可观察行为改变，避免只停留在宏观感悟。"
    if "战略" in name or "知行" in name:
        detail = "可围绕{}展开，".format(signals) if signals else ""
        return "补强战略到行动的逻辑闭环：{}建议明确说明任务如何支撑公司战略、业务痛点和组织价值，并显性引用5WHY、逻辑树等问题解决工具。".format(detail)
    if "课题" in name or "创新" in name:
        detail = "结合{}，".format(signals) if signals else ""
        return "强化课题创新突破点：{}在已有业务价值之外，建议补充差异化方法、可验证收益和对现状的破局思考，避免只呈现常规管理动作。".format(detail)
    if "规划" in name or "前瞻" in name:
        detail = "围绕{}，".format(signals) if signals else ""
        return "完善资源规划与协同安排：{}建议列明跨部门角色、数据权限、预算或系统支持、关键里程碑和决策节点，增强课题立项的可执行性。".format(detail)
    if "逻辑" in name or "展现" in name:
        detail = "针对{}，".format(signals) if signals else ""
        return "优化现场表达节奏：{}建议在关键数据和结论处放慢语速、停顿1-2秒并指向PPT，让评委同步接收核心证据。".format(detail)
    return "{}仍有提升空间，建议补充更具体的案例、量化证据、行动分工和结果验证。".format(name)


def _build_overall_comment(
    report_type,
    total_score,
    strengths,
    improvements,
    transcript_present,
    assignment_insights=None,
):
    score_part = (
        "{}汇报已完成综合评估。".format(report_type)
        if total_score is None
        else "{}汇报综合评级为{}，总分{}分。".format(
            report_type, total_to_level(total_score), total_score
        )
    )
    case_text = _join_signals((assignment_insights or {}).get("case", [])[:1])
    metric_text = _join_signals((assignment_insights or {}).get("metrics", [])[:2])
    signal_text = ""
    if case_text or metric_text:
        signal_text = " 作业主线可见{}{}。".format(
            case_text or "具体业务场景",
            "，关键数据包括{}".format(metric_text) if metric_text else "",
        )
    missing = summarize_missing_evidence(assignment_insights or {})
    if len(missing) >= 3:
        strengths_text = "当前只能确认基础表达，{}，尚不足以证明完整的问题分析和行动闭环。".format("、".join(missing[:4]))
    else:
        takeaway = "；".join(condense_takeaway(item) for item in strengths[:2])
        strengths_text = "主要证据集中在{}，说明汇报已经具备一定业务洞察和执行基础。".format(takeaway)
    improvements_text = "主要提升空间在于{}，后续应把抽象判断转化为可被评委直接看见的证据链。".format(
        "；".join(condense_takeaway(item) for item in improvements[:2])
    )
    transcript_text = (
        "当前未提供录音材料，录音相关维度暂按待补充处理。"
        if not transcript_present
        else "本次结果已同时综合书面材料与录音转写信息，结论兼顾材料质量和现场呈现。"
    )
    return _limit(
        "{}{} {} {} {}".format(
            score_part, signal_text, strengths_text, improvements_text, transcript_text
        ),
        700,
    )


def _ordered_unique(values):
    seen = set()
    unique = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def _join_signals(signals):
    return "；".join(signal for signal in signals if signal)


def _dimension_completeness(dimension, insights):
    if dimension["source_key"] == "transcript":
        return len([key for key in ("expression", "transcript_metrics") if insights.get(key)])
    return len([key for key in ("case", "tools", "metrics", "actions", "reflection", "planning") if insights.get(key)])


def _missing_sentence(assignment_insights):
    missing = summarize_missing_evidence(assignment_insights or {})
    return "、".join(missing[:4]) if missing else "需要把现有线索进一步转化为可验证证据"


def _has_relevant_number(sentences, keyword_hits):
    if not keyword_hits:
        return False
    for sentence in sentences:
        if _looks_like_identifier_sentence(sentence):
            continue
        keyword_count = sum(1 for keyword in keyword_hits if keyword in sentence)
        if keyword_count < 2:
            continue
        if re.search(r"\d+(\.\d+)?%?", sentence):
            return True
    return False


def _looks_like_identifier_sentence(sentence):
    compact = re.sub(r"\s+", "", sentence)
    if re.search(r"(股票代码|证券代码)[:：]?\d{6}", compact):
        return True
    if re.search(r"\b\d{6}\.(SZ|SH|BJ|HK)\b", sentence, re.IGNORECASE):
        return True
    return False


def _split_sentences(text):
    return [segment.strip() for segment in re.split(r"[。！？\n\r]+", text) if segment.strip()]


def _limit(text, size):
    if len(text) <= size:
        return text
    return text[: size - 1].rstrip() + "…"


def _clean_dimension_text(dimension):
    cleaned = dict(dimension)
    cleaned["evidence"] = _clean_feedback_text(cleaned.get("evidence") or "")
    cleaned["comment"] = _clean_feedback_text(cleaned.get("comment") or "")
    return cleaned


def _clean_feedback_text(text):
    cleaned = _strip_standard_tail(text)
    cleaned = _strip_score_judgement_tail(cleaned)
    cleaned = _drop_incomplete_tail(cleaned)
    return _ensure_sentence_ending(cleaned)


def _strip_standard_tail(text):
    cleaned = str(text or "").strip()
    cleaned = re.sub(
        r"[，,；;]?\s*(?:并)?(?:不|未)?(?:符合|达到|满足|属于|处于)"
        r"(?:(?:[^。！？；;\n\r]{0,60}(?:评分标准|评估标准|评价标准|标准|要求|档位|区间|水平)"
        r"[^。！？；;\n\r]{0,80})|(?:\s*[“\"「《][^”\"」》]{0,120}[”\"」》]))"
        r"\s*(?:[。！？；;…]+|\.\.\.)?\s*$",
        "",
        cleaned,
    )
    cleaned = re.sub(r"[，,；;]\s*([。！？])", r"\1", cleaned)
    cleaned = re.sub(r"([。！？；;]){2,}", r"\1", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.rstrip(" \t\r\n，,；;：:")


def _strip_score_judgement_tail(text):
    cleaned = str(text or "").strip()
    cleaned = re.sub(
        r"[，,；;]?\s*(?:因此|所以|故|由此|据此|综合来看|综合判断)?"
        r"(?:可)?(?:判定|判断|评定|定位)?(?:为)?"
        r"[^。！？；;\n\r]{0,80}(?:(?:得分|得)\s*\d+(?:\.\d+)?\s*分|评分\s*(?:为)?\s*\d+(?:\.\d+)?\s*(?:分)?)"
        r"\s*(?:[。！？；;…]+|\.\.\.)?\s*$",
        "",
        cleaned,
    )
    return cleaned.rstrip(" \t\r\n，,；;：:")


def _drop_incomplete_tail(text):
    cleaned = str(text or "").strip()
    if not cleaned:
        return ""
    if re.search(r"(?:\.{3,}|…+)\s*$", cleaned):
        cleaned = re.sub(r"(?:\.{3,}|…+)\s*$", "", cleaned).rstrip()
        return _truncate_to_last_sentence(cleaned)
    if re.search(r"[。！？]$", cleaned):
        return cleaned
    if re.search(r"[，,；;：:]$", cleaned):
        return _truncate_to_last_sentence(cleaned)
    return _truncate_to_last_sentence(cleaned)


def _truncate_to_last_sentence(text):
    cleaned = str(text or "").strip()
    matches = list(re.finditer(r"[。！？]", cleaned))
    if not matches:
        return cleaned
    return cleaned[: matches[-1].end()].strip()


def _ensure_sentence_ending(text):
    cleaned = str(text or "").strip()
    if not cleaned:
        return ""
    if re.search(r"[。！？]$", cleaned):
        return cleaned
    return cleaned.rstrip(" \t\r\n，,；;：:.") + "。"
