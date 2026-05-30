import re
from uuid import uuid4

from .core.text_quality import looks_like_garbled_text
from .live_scoring import live_score_submission
from .rules import DISCLAIMER, get_report_definition, score_to_level, total_to_level
from .utils import now_iso

# Lazy-initialized TF-IDF evidence ranker
_ranker = None


def _get_ranker():
    """Return the module-level EvidenceRanker instance."""
    global _ranker
    return _ranker


def _ensure_ranker(definition):
    """Initialize or re-initialize the EvidenceRanker with a definition."""
    global _ranker
    try:
        from .evidence_ranker import EvidenceRanker

        _ranker = EvidenceRanker(definition)
    except Exception:
        _ranker = None


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

    try:
        live_payload = live_score_submission(
            report_type=report_type,
            definition=definition,
            document_text=document_text,
            transcript_text=transcript_text,
        )
        dimension_results = live_payload["dimensions"]
        overall_comment = live_payload["overall_comment"]
        scoring_mode = live_payload.get("mode", "live")
        llm_provider = live_payload.get("provider", "")
        llm_model = live_payload.get("model", "")
    except Exception:
        dimension_results = _build_heuristic_dimensions(
            definition=definition,
            document_text=document_text,
            transcript_text=transcript_text,
            transcript_present=transcript_present,
        )
        strengths, improvements = _build_takeaways(
            [item for item in dimension_results if item["score"] is not None]
        )
        overall_comment = _build_overall_comment(
            report_type=report_type,
            total_score=None,
            strengths=strengths,
            improvements=improvements,
            transcript_present=transcript_present,
        )
        scoring_mode = "heuristic"
        llm_provider = ""
        llm_model = ""

    result = _assemble_result(
        report_type=report_type,
        metadata=metadata,
        transcript_present=transcript_present,
        dimension_results=dimension_results,
        overall_comment=overall_comment,
    )
    result["scoring_mode"] = scoring_mode
    result["llm_provider"] = llm_provider
    result["llm_model"] = llm_model
    return result


def _assemble_result(report_type, metadata, transcript_present, dimension_results, overall_comment):
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
    strengths, improvements = _build_takeaways(scored_dimensions)

    if overall_comment:
        overall_comment = _limit(overall_comment, 220)
    else:
        overall_comment = _build_overall_comment(
            report_type=report_type,
            total_score=total_score,
            strengths=strengths,
            improvements=improvements,
            transcript_present=transcript_present,
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


def _build_heuristic_dimensions(definition, document_text, transcript_text, transcript_present):
    dimension_results = []
    used_sentences = set()
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
            score = _score_dimension(relevant_text, dimension)
            evidence = _build_evidence(
                relevant_text,
                dimension=dimension,
                used_sentences=used_sentences,
                definition=definition,
            )
            if evidence:
                used_sentences.add(evidence)
            result = {
                "id": dimension["id"],
                "name": dimension["name"],
                "group_name": dimension["group"],
                "group_weight": dimension["group_weight"],
                "actual_weight": dimension["actual_weight"],
                "material_source": dimension["material_source"],
                "score": score,
                "level_label": score_to_level(score),
                "evidence": evidence,
                "comment": _build_comment(score, dimension["focus"], transcript_present),
            }
        dimension_results.append(result)
    return dimension_results


def _score_dimension(text, dimension):
    normalized = text.strip()
    keyword_hits = [kw for kw in dimension["keywords"] if kw in normalized]
    coverage = len(set(keyword_hits)) / float(len(dimension["keywords"]) or 1)
    length_bonus = min(len(normalized) / 1200.0, 1.0) * 0.7
    score = 4.1 + (coverage * 3.7) + length_bonus

    if dimension["needs_numbers"] and re.search(r"\d+(\.\d+)?%?", normalized):
        score += 0.5
    if not keyword_hits and len(normalized) < 150:
        score -= 0.8
    if len(normalized) < 60:
        score -= 0.4
    if looks_like_garbled_text(normalized):
        score = min(score, 4.2)

    score = max(3.8, min(9.0, score))
    return round(score, 1)


def _build_evidence(text, keywords=None, dimension=None, used_sentences=None, definition=None):
    """Select best evidence sentence using weighted scoring (rank first, then fallback)."""
    # Extract keywords from dimension if not provided directly
    if keywords is None and dimension:
        keywords = dimension.get("keywords", [])
    if keywords is None:
        keywords = []

    # Try TF-IDF ranker if dimension and definition are available
    if dimension and definition:
        ranker = _get_ranker()
        if ranker is None:
            _ensure_ranker(definition)
            ranker = _get_ranker()
        if ranker:
            try:
                return ranker.best_evidence(text, dimension)
            except Exception:
                pass  # Fall back to weighted scoring

    # Fallback: weighted sentence scoring
    sentences = _split_sentences(text)
    candidates = []
    is_short = len(sentences) < 5

    for idx, sentence in enumerate(sentences):
        if looks_like_garbled_text(sentence):
            continue

        kw_density = _calc_keyword_density(sentence, keywords)
        focus_score = _calc_focus_alignment(
            sentence,
            dimension.get("name", "") if dimension else "",
            dimension.get("focus", "") if dimension else "",
        )

        if is_short:
            # Short texts: position and exhaustivity are noisy, rely on keyword + focus only
            total = 0.50 * kw_density + 0.50 * focus_score
        else:
            pos_score = _calc_position_bonus(idx, len(sentences))
            exhaustivity = _calc_exhaustivity_penalty(sentence, used_sentences or set())
            total = (
                0.35 * kw_density + 0.40 * focus_score + 0.15 * pos_score - 0.10 * exhaustivity
            )
        candidates.append((total, sentence))

    if not candidates:
        return "文档文本提取质量不足，未找到可直接引用的有效证据。"

    candidates.sort(key=lambda x: x[0], reverse=True)
    return _limit(candidates[0][1], 80)


def _calc_keyword_density(text, keywords):
    """Calculate keyword hit ratio for a piece of text (0.0-1.0)."""
    if not keywords:
        return 0.0
    hits = sum(1 for kw in keywords if kw in text)
    return min(hits / float(len(keywords)), 1.0)


def _calc_focus_alignment(text, dim_name, dim_focus):
    """Calculate focus alignment score by matching name and focus tokens (0.0-1.0)."""
    if not dim_name and not dim_focus:
        return 0.0

    focus_score = 0.0
    name_score = 0.0

    if dim_focus:
        if dim_focus in text:
            focus_score = 1.0
        else:
            text_chars = set(text)
            focus_chars = set(dim_focus)
            if focus_chars:
                overlap = len(text_chars & focus_chars)
                focus_score = overlap / len(focus_chars)

    if dim_name:
        if dim_name in text:
            name_score = 0.8
        else:
            text_chars = set(text)
            name_chars = set(dim_name)
            if name_chars:
                overlap = len(text_chars & name_chars)
                name_score = 0.6 * (overlap / len(name_chars))

    if dim_focus and dim_name:
        return 0.6 * focus_score + 0.4 * name_score
    elif dim_focus:
        return focus_score
    else:
        return name_score


def _calc_position_bonus(idx, total_sentences):
    """Calculate position quality score (0.0-1.0) based on sentence position."""
    if total_sentences <= 1:
        return 1.0
    if idx == 0:
        return 1.0  # First sentence
    if idx == total_sentences - 1:
        return 0.6  # Last sentence
    return 0.0


def _calc_exhaustivity_penalty(sentence, used_sentences):
    """Return 1.0 if the sentence is already used as evidence by another dimension."""
    if not used_sentences:
        return 0.0
    return 1.0 if sentence in used_sentences else 0.0


def _build_comment(score, focus, transcript_present):
    label = score_to_level(score)
    tone = {
        "卓越": "该维度表现突出，关键论述完整且有较强支撑。",
        "优秀": "该维度表现扎实，能够较好支撑整体汇报质量。",
        "良好": "该维度具备基础支撑，但细节和说服力仍可继续加强。",
        "合格": "该维度已有基本表达，但论据与完整性偏弱。",
        "不合格": "该维度材料支撑不足，难以形成有效判断。",
    }[label]
    follow_up = "建议继续围绕{}补充更具体的案例、动作和结果。".format(focus)
    if not transcript_present:
        follow_up = "当前仅基于已提供材料形成判断，建议后续补充完整录音信息。"
    return _limit("{} {}".format(tone, follow_up), 120)


def _build_takeaways(scored_dimensions):
    if not scored_dimensions:
        return ["整体材料已形成基本表达，可继续补充更多事实支撑。"], [
            "建议围绕目标、过程、结果与反思进一步补充证据，让评价依据更完整。"
        ]

    scores = [item["score"] for item in scored_dimensions]
    average_score = sum(scores) / len(scores)
    score_range = max(scores) - min(scores)
    strengths = [
        _limit(
            "整体材料在问题呈现、逻辑组织与行动支撑方面已有基础，能够支撑对汇报质量的综合判断。",
            120,
        )
    ]
    if average_score >= 7.5 and score_range <= 1.2:
        improvements = [
            "建议继续补充更具体的数据、案例和复盘闭环，让整体论证从完整走向更有说服力。"
        ]
    else:
        improvements = [
            "建议从材料完整度、证据颗粒度和表达连贯性三个方面补强，让整体评价更稳定。"
        ]
    return strengths, improvements


def _build_overall_comment(report_type, total_score, strengths, improvements, transcript_present):
    score_part = (
        "{}汇报当前综合评分已生成。".format(report_type)
        if total_score is None
        else "{}汇报当前综合评级为{}，总分{}分。".format(
            report_type, total_to_level(total_score), total_score
        )
    )
    strengths_text = strengths[0] if strengths else "整体材料已形成基本表达。"
    improvements_text = improvements[0] if improvements else "建议继续补充证据与复盘闭环。"
    transcript_text = (
        "当前未提供录音材料，录音相关维度暂按待补充处理。"
        if not transcript_present
        else "本次结果已同时综合文档与录音转写信息。"
    )
    return _limit(
        "{} {} {} {}".format(
            score_part, strengths_text, improvements_text, transcript_text
        ),
        220,
    )


def _split_sentences(text):
    return [segment.strip() for segment in re.split(r"[。！？\n\r]+", text) if segment.strip()]


def _strip_tail(text):
    return text.split("表现")[0].split("仍有")[0]


def _limit(text, size):
    if len(text) <= size:
        return text
    head_size = int(size * 0.6)
    tail_size = size - head_size - 1
    if tail_size < 10:
        return text[: size - 1].rstrip() + "…"
    return text[:head_size].rstrip() + "…" + text[-tail_size:].lstrip()
