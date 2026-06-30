import json as _json
from uuid import uuid4

from ..assignment_insights import extract_assignment_insights
from ..live_scoring import LiveScoringError, live_score_submission
from ..pdf_extract import PdfExtractionError, extract_text_from_pdf_bytes
from ..repository import store_score_bundle
from ..rules import get_report_definition
from ..scoring import (
    ScoringError,
    _assemble_result,
    _build_heuristic_dimensions,
    _build_overall_comment,
    _build_takeaways,
)
from .state import EvalState


def validate_input(state: EvalState) -> EvalState:
    """Check that input is usable and load the report definition.

    * ``document_text`` must be at least 40 characters, OR ``pdf_bytes`` must
      be non-empty (so extraction can run later).
    * Sets ``transcript_present`` based on whether ``transcript_text`` has
      non-whitespace content.
    * Loads ``definition`` from ``get_report_definition()``.
    """
    has_text = bool(state.document_text and len(state.document_text.strip()) >= 1)
    has_pdf = bool(state.pdf_bytes)
    if not has_text and not has_pdf:
        state.error = "未能获取任何文档文本，无法生成评分结果。"
        return state

    state.transcript_present = bool(state.transcript_text.strip())

    try:
        state.definition = get_report_definition(state.report_type)
    except KeyError:
        state.error = f"无效的报告类型: {state.report_type}"

    return state


def extract_pdf(state: EvalState) -> EvalState:
    """If ``pdf_bytes`` is non-empty, extract document text from it.

    Sets ``extraction_error`` on failure.  The existing ``document_text`` is
    *not* overwritten on error (so a previously-submitted text survives).
    """
    if state.error:
        return state
    if not state.pdf_bytes:
        return state

    try:
        state.document_text = extract_text_from_pdf_bytes(state.pdf_bytes)
    except PdfExtractionError as exc:
        state.extraction_error = str(exc)

    return state


def route_strategy(state: EvalState) -> EvalState:
    """Try live (LLM-based) scoring; fall back to heuristic on failure.

    On success sets ``scoring_mode`` to ``"live"`` and populates
    ``dimension_results``, ``overall_comment``, ``llm_provider``,
    ``llm_model``.

    On ``LiveScoringError`` sets ``scoring_mode`` to ``"heuristic"`` and
    records the error message in ``llm_error``.
    """
    if state.error:
        return state

    definition = state.definition
    if not definition:
        state.error = "报告定义未加载，无法进行评分。"
        return state

    assignment_insights = extract_assignment_insights(state.document_text, state.transcript_text)
    try:
        payload = live_score_submission(
            report_type=state.report_type,
            definition=definition,
            document_text=state.document_text,
            transcript_text=state.transcript_text,
            assignment_insights=assignment_insights,
        )
        state.dimension_results = payload["dimensions"]
        state.overall_comment = payload["overall_comment"]
        state.strengths = payload.get("strengths") or []
        state.improvements = payload.get("improvements") or []
        state.scoring_mode = payload.get("mode", "live")
        state.llm_provider = payload.get("provider", "")
        state.llm_model = payload.get("model", "")
    except LiveScoringError as exc:
        state.scoring_mode = "heuristic"
        state.llm_error = str(exc)

    return state


def score_llm(state: EvalState) -> EvalState:
    """Assemble the live-scoring results into a final result dict.

    Calls ``_assemble_result()`` with the ``dimension_results`` already
    populated by ``route_strategy``.  Populates ``total_score``,
    ``total_level``, ``strengths``, ``improvements``, and stores the
    assembled dict in ``assembled_result``.
    """
    if state.error:
        return state

    assignment_insights = extract_assignment_insights(state.document_text, state.transcript_text)
    try:
        result = _assemble_result(
            report_type=state.report_type,
            metadata=state.metadata,
            transcript_present=state.transcript_present,
            dimension_results=state.dimension_results,
            overall_comment=state.overall_comment,
            report_strengths=state.strengths or None,
            report_improvements=state.improvements or None,
            assignment_insights=assignment_insights,
            clean_dimension_text=True,
        )
        state.total_score = result["total_score"]
        state.total_level = result["total_level"]
        state.strengths = result["strengths"]
        state.improvements = result["improvements"]
        state.overall_comment = result["overall_comment"]
        state.assembled_result = result
    except ScoringError as exc:
        state.error = str(exc)

    return state


def score_heuristic(state: EvalState) -> EvalState:
    """Score using heuristic (rule-based) methods.

    Calls ``_build_heuristic_dimensions()``, ``_build_takeaways()``, and
    ``_build_overall_comment()`` from ``scoring.py``.  Populates
    ``dimension_results``, ``strengths``, ``improvements``, and
    ``overall_comment`` on the state.  (``_assemble_result`` is called later
    in ``assemble_result``.)
    """
    if state.error:
        return state

    definition = state.definition
    if not definition:
        state.error = "报告定义未加载，无法进行评分。"
        return state

    assignment_insights = extract_assignment_insights(state.document_text, state.transcript_text)
    try:
        dimension_results = _build_heuristic_dimensions(
            definition=definition,
            document_text=state.document_text,
            transcript_text=state.transcript_text,
            transcript_present=state.transcript_present,
            assignment_insights=assignment_insights,
        )
        scored = [d for d in dimension_results if d["score"] is not None]
        strengths, improvements = _build_takeaways(scored, assignment_insights=assignment_insights)
        overall_comment = _build_overall_comment(
            report_type=state.report_type,
            total_score=None,
            strengths=strengths,
            improvements=improvements,
            transcript_present=state.transcript_present,
            assignment_insights=assignment_insights,
        )
        state.dimension_results = dimension_results
        state.strengths = strengths
        state.improvements = improvements
        state.overall_comment = overall_comment
    except Exception as exc:
        state.error = str(exc)

    return state


def assemble_result(state: EvalState) -> EvalState:
    """Build the final assembled result dict and enrich it.

    If ``assembled_result`` is already set (live path), enriches it.
    Otherwise calls ``_assemble_result()`` with the heuristic results.

    Adds ``user_id``, ``upload_path``, ``scoring_mode``, export URLs, and
    ``data_completeness`` to the result dict.
    """
    if state.error:
        return state

    try:
        if state.assembled_result:
            result = state.assembled_result
        else:
            # Heuristic path: assemble from state fields
            assignment_insights = extract_assignment_insights(
                state.document_text,
                state.transcript_text,
            )
            result = _assemble_result(
                report_type=state.report_type,
                metadata=state.metadata,
                transcript_present=state.transcript_present,
                dimension_results=state.dimension_results,
                overall_comment=state.overall_comment,
                report_strengths=state.strengths or None,
                report_improvements=state.improvements or None,
                assignment_insights=assignment_insights,
            )

        # Enrich with user / session / export metadata
        result["user_id"] = state.user_id
        result["upload_path"] = state.upload_path
        result["scoring_mode"] = state.scoring_mode
        result["markdown_export_url"] = (
            f"/api/scores/{result['score_id']}/export?format=md"
        )
        result["pdf_export_url"] = (
            f"/api/scores/{result['score_id']}/export?format=pdf"
        )
        result["data_completeness"] = _json.dumps(
            {
                "has_document": bool(state.document_text.strip()),
                "has_transcript": state.transcript_present,
                "has_pdf": bool(state.pdf_bytes),
            },
            ensure_ascii=False,
        )

        # Enrich with confidence data if available
        if state.confidence:
            conf_by_id = {c["dimension_id"]: c for c in state.confidence}
            for dim in result.get("dimensions", []):
                c = conf_by_id.get(dim["id"])
                dim["confidence"] = c["level"] if c else "unknown"
            result["confidence"] = [c["level"] for c in state.confidence]
            result["review_required"] = state.review_required
            result["review_reason"] = state.review_reason if state.review_required else ""

        state.assembled_result = result
        state.total_score = result["total_score"]
        state.total_level = result["total_level"]
    except ScoringError as exc:
        state.error = str(exc)

    return state


def store_result(state: EvalState) -> EvalState:
    """Persist the assembled result to the database via ``store_score_bundle``.

    Catches exceptions and sets ``store_error`` rather than crashing.
    """
    if state.error:
        return state
    if not state.assembled_result:
        state.store_error = "没有可存储的评分结果。"
        return state

    try:
        store_score_bundle(result=state.assembled_result)
    except Exception as exc:
        state.store_error = str(exc)

    return state


def build_response(state: EvalState) -> EvalState:
    """Passthrough — returns the state unchanged."""
    return state


def compute_confidence(state: EvalState) -> EvalState:
    """Compute per-dimension confidence levels based on keyword coverage.

    For each dimension_result, matches against definition keywords, computes
    keyword coverage, and assigns a confidence level:

    * ``"insufficient_data"`` when score is ``None``
    * ``"high"`` for LLM-scored dimensions with coverage >= 0.5 and text >= 1000
    * ``"medium"`` for LLM with weaker signals, or heuristic with coverage >= 0.25
      and text >= 300
    * ``"low"`` for everything else

    Appends per-dimension dicts to ``state.confidence``.
    """
    if state.error:
        return state

    definition_dims = {d["id"]: d for d in state.definition.get("dimensions", [])}
    combined_text = (state.document_text or "") + " " + (state.transcript_text or "")
    text_length = len(combined_text.strip())
    is_llm = state.scoring_mode == "live"

    confidences = []
    for dim in state.dimension_results:
        dim_id = dim["id"]
        dim_name = dim.get("name", str(dim_id))

        if dim["score"] is None:
            confidences.append({
                "dimension_id": dim_id,
                "dimension_name": dim_name,
                "level": "insufficient_data",
                "keyword_coverage": 0.0,
            })
            continue

        def_dim = definition_dims.get(dim_id, {})
        keywords = def_dim.get("keywords", [])

        # Compute keyword coverage in the combined text
        if keywords:
            hits = sum(1 for kw in keywords if kw in combined_text)
            coverage = hits / len(keywords)
        else:
            coverage = 0.0

        # Assign confidence level
        if is_llm and coverage >= 0.5 and text_length >= 1000:
            level = "high"
        elif is_llm:
            level = "medium"
        elif coverage >= 0.25 and text_length >= 300:
            level = "medium"
        else:
            level = "low"

        confidences.append({
            "dimension_id": dim_id,
            "dimension_name": dim_name,
            "level": level,
            "keyword_coverage": round(coverage, 2),
        })

    state.confidence = confidences
    return state


def human_review_gate(state: EvalState) -> EvalState:
    """Check confidence and flag dimensions needing human review.

    If any dimension has confidence level ``"low"``, sets
    ``review_required`` to ``True``, populates ``review_reason``, and
    generates a ``pause_token``.
    """
    if state.error:
        return state

    low_dims = [c for c in state.confidence if c.get("level") == "low"]
    if low_dims:
        dim_names = [c.get("dimension_name", str(c["dimension_id"])) for c in low_dims]
        state.review_required = True
        state.review_reason = (
            f"Low confidence on dimensions: {', '.join(dim_names)}"
        )
        state.pause_token = uuid4().hex

    return state


def track_calibration(state: EvalState) -> EvalState:
    """Non-blocking calibration tracking.

    Wraps the ``CalibrationTracker`` import and update call in a
    try/except to avoid breaking the pipeline if the module is not yet
    available.
    """
    if state.error or not state.assembled_result:
        return state

    try:
        from ..calibration import CalibrationTracker  # noqa: PLC0415

        tracker = CalibrationTracker()
        for dim in state.dimension_results:
            if dim.get("score") is not None:
                tracker.update(state.report_type, dim["id"], dim["score"])
    except Exception:
        pass

    return state
