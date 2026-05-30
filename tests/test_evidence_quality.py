"""
Evidence quality tests for the scoring system.

Covers:
  1. _build_evidence() basic keyword selection
  2. Focus alignment (current vs planned behavior)
  3. LLM evidence grounding validation (when available)
  4. EvidenceRanker (when available)
  5. Regression: score_submission() return structure
  6. Boundary: empty/short/garbled/long text
"""

import os
import re
import sys
import unittest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Direct imports for unit-level tests (does NOT trigger the full app chain,
# so pypdf is not required).
# ---------------------------------------------------------------------------
from scoring_app.rules import REPORT_DEFINITIONS, get_report_definition
from scoring_app.scoring import (
    _build_evidence,
    _build_heuristic_dimensions,
    _build_evidence_summary,
    _build_comment,
    _calc_keyword_density,
    _calc_focus_alignment,
    _calc_position_bonus,
    _calc_exhaustivity_penalty,
    _score_dimension,
    _split_sentences,
    _limit,
    ScoringError,
    score_submission,
)

# Grab a known report definition for testing
WG_DEF = get_report_definition("温故知新")
XL_DEF = get_report_definition("行动学习")


# ======================================================================
#  1. Weighted scoring — _build_evidence() keyword selection
# ======================================================================

class BuildEvidenceBasicTest(unittest.TestCase):
    """Basic _build_evidence() tests — keyword-first-match logic."""

    def test_selects_sentence_containing_first_keyword(self):
        """_build_evidence picks the first sentence that contains a keyword,
        iterating keywords in order, then sentences."""
        text = (
            "战略规划是本次汇报的核心内容。"
            "团队执行情况良好。"
            "业务价值显著提升。"
        )
        keywords = ["战略", "业务"]
        evidence = _build_evidence(text, keywords)
        # The first keyword is "战略", which appears in sentence 1
        self.assertIn("战略", evidence)
        self.assertNotIn("业务", evidence)

    def test_selects_second_keyword_when_first_keyword_missing(self):
        """When the first keyword has no hits, uses the next keyword."""
        text = (
            "团队协作密切，沟通顺畅。"
            "业务数据表现良好。"
            "项目交付按时完成。"
        )
        keywords = ["创新", "业务"]
        evidence = _build_evidence(text, keywords)
        self.assertIn("业务", evidence)

    def test_returns_garbled_fallback_when_all_sentences_garbled(self):
        """When every sentence is detected as garbled, return fallback text."""
        from scoring_app.core.text_quality import looks_like_garbled_text

        text = "锟斤拷烫烫烫锟斤拷烫烫烫锟斤拷烫烫烫"
        keywords = ["战略"]
        evidence = _build_evidence(text, keywords)
        self.assertEqual(
            evidence, "文档文本提取质量不足，未找到可直接引用的有效证据。"
        )

    def test_limits_evidence_to_80_chars(self):
        """Evidence is truncated to at most 80 characters."""
        text = "战略" * 60 + "。"
        keywords = ["战略"]
        evidence = _build_evidence(text, keywords)
        self.assertLessEqual(len(evidence), 80)

    def test_returns_first_non_garbled_sentence_when_no_keyword_hits(self):
        """When no keyword matches, returns the first non-garbled sentence."""
        text = (
            "团队近期完成了项目交付。"
            "整体进展符合预期。"
        )
        evidence = _build_evidence(text, ["不存在的关键词"])
        self.assertIn("团队近期完成了项目交付", evidence)

    def test_keyword_in_middle_of_sentence(self):
        """Keyword matched mid-sentence still works."""
        text = "本次项目重点关注了客户的战略需求并制定了解决方案。"
        evidence = _build_evidence(text, ["战略"])
        self.assertIn("战略", evidence)

    def test_multiple_keywords_in_one_sentence(self):
        """Sentence containing multiple keywords still matches on first keyword."""
        text = (
            "战略目标和业务价值是本次汇报的重点。"
            "其他内容仅供参考。"
        )
        keywords = ["战略", "业务"]
        evidence = _build_evidence(text, keywords)
        self.assertIn("战略", evidence)
        # It should match the first keyword "战略" from keyword order,
        # so "业务" may or may not appear depending on the length limit


# ======================================================================
#  2. Focus alignment
# ======================================================================

class FocusAlignmentTest(unittest.TestCase):
    """Test focus-related behavior in _build_comment() and dimension scoring.

    The current _build_evidence() does NOT implement a separate
    focus_alignment function (that is planned for Phase 1 of the spec).
    These tests verify the current behavior and lay groundwork for the
    upcoming weighted scoring change.
    """

    def test_build_comment_includes_focus_text(self):
        """_build_comment references the dimension focus."""
        comment = _build_comment(8.0, "战略理解深度", transcript_present=True)
        self.assertIn("战略理解深度", comment)

    def test_build_comment_excellent_level(self):
        """Score >= 9.0 gets '卓越' level text."""
        comment = _build_comment(9.2, "战略理解深度", transcript_present=True)
        self.assertIn("表现突出", comment)
        self.assertIn("战略理解深度", comment)

    def test_build_comment_good_level(self):
        """Score 6.0-7.4 gets '良好' level text."""
        comment = _build_comment(6.5, "结果验证强度", transcript_present=True)
        self.assertIn("具备基础支撑", comment)

    def test_build_comment_without_transcript(self):
        """When no transcript, comment notes missing recording."""
        comment = _build_comment(8.0, "系统思维", transcript_present=False)
        self.assertIn("补充完整录音信息", comment)
        self.assertNotIn("系统思维", comment)


# ======================================================================
#  3. LLM evidence grounding validation
# ======================================================================

class ValidateEvidenceTest(unittest.TestCase):
    """Tests for _validate_evidence() — specified in the redesign spec
    but NOT YET IMPLEMENTED in the codebase.  Tests are structured so
    they pass once the function lands.

    The planned function signature is:
        _validate_evidence(evidence_text, source_text) -> bool
    """

    def _call_validate_evidence(self, evidence_text, source_text):
        """Try to call _validate_evidence if it exists; otherwise skip."""
        try:
            from scoring_app.scoring import _validate_evidence
            return _validate_evidence(evidence_text, source_text)
        except (ImportError, AttributeError):
            self.skipTest("_validate_evidence not yet implemented (Phase 1)")

    def test_evidence_present_in_source(self):
        """When evidence text is a substring of the source, return True."""
        source = "本次战略规划聚焦于客户的核心业务需求。"
        evidence = "战略规划聚焦于客户"
        result = self._call_validate_evidence(evidence, source)
        self.assertTrue(result)

    def test_evidence_not_present_in_source(self):
        """When evidence text is NOT in the source, return False."""
        source = "本次战略规划聚焦于客户的核心业务需求。"
        evidence = "团队协作效率大幅提升"
        result = self._call_validate_evidence(evidence, source)
        self.assertFalse(result)

    def test_empty_evidence_returns_false(self):
        """Empty or very short evidence should return False."""
        source = "本次战略规划聚焦于客户的核心业务需求。"
        result = self._call_validate_evidence("", source)
        self.assertFalse(result)

    def test_none_evidence_returns_false(self):
        """None evidence should return False."""
        source = "本次战略规划聚焦于客户的核心业务需求。"
        result = self._call_validate_evidence(None, source)
        self.assertFalse(result)


# ======================================================================
#  4. EvidenceRanker
# ======================================================================

class EvidenceRankerTest(unittest.TestCase):
    """Tests for EvidenceRanker — specified in the redesign spec
    (Phase 2 / TF-IDF semantic ranking) but NOT YET IMPLEMENTED.

    Tests are structured to pass once the module lands.
    """

    def test_ranker_available(self):
        """Check if EvidenceRanker can be imported."""
        try:
            from scoring_app.evidence_ranker import EvidenceRanker
            self.assertTrue(hasattr(EvidenceRanker, "rank_sentences"))
        except (ImportError, AttributeError):
            self.skipTest("EvidenceRanker not yet implemented (Phase 2)")

    def test_ranker_returns_ranked_sentences(self):
        """Verify rank_sentences returns a sorted list with scores."""
        try:
            from scoring_app.evidence_ranker import EvidenceRanker
            ranker = EvidenceRanker(WG_DEF)
            sentences = _split_sentences(
                "战略目标明确。业务价值突出。执行细节可进一步优化。"
            )
            results = ranker.rank_sentences(sentences, 1)  # dimension id=1
            self.assertTrue(len(results) > 0)
            for item in results:
                self.assertIn("sentence", item)
                # The ranker may use 'similarity' or 'score' as key
                self.assertTrue("score" in item or "similarity" in item)
        except (ImportError, AttributeError):
            self.skipTest("EvidenceRanker not yet implemented (Phase 2)")

    def test_ranker_best_evidence_returns_string(self):
        """Verify best_evidence returns a limited string."""
        try:
            from scoring_app.evidence_ranker import EvidenceRanker
            ranker = EvidenceRanker(WG_DEF)
            text = "战略目标明确。业务价值突出。执行细节可进一步优化。"
            evidence = ranker.best_evidence(text, WG_DEF["dimensions"][0])
            self.assertIsInstance(evidence, str)
        except (ImportError, AttributeError):
            self.skipTest("EvidenceRanker not yet implemented (Phase 2)")


# ======================================================================
#  5. Regression: score_submission() return structure
# ======================================================================

class ScoreSubmissionRegressionTest(unittest.TestCase):
    """Verify score_submission() return structure remains unchanged.

    These tests mock out the live LLM call so they always fall back to
    the heuristic path, which exercises _build_evidence() internally.
    """

    def test_result_contains_all_required_fields(self):
        """score_submission result has all top-level keys."""
        document_text = (
            "本次汇报围绕战略目标、业务痛点、关键任务推进与结果改善展开。"
            "团队通过协同完成了项目交付，执行节点清晰，阶段成效明显。"
            "下一步计划聚焦创新突破与资源优化。"
            * 8
        )
        transcript_text = (
            "大家好，我将按背景、问题、行动、结果四个部分完成汇报。"
            "首先解释战略相关性，其次展示执行过程。"
            * 8
        )
        metadata = {
            "name": "Regression Student",
            "org": "Test Team",
            "date": "2026-05-29",
            "course_session": "第二次课 · 组织协同",
            "note": "regression test",
            "pdf_filename": "report.pdf",
            "upload_path": "",
            "document_preview": document_text[:800],
        }

        with patch("scoring_app.scoring.live_score_submission",
                    side_effect=RuntimeError("mock fallback")):
            result = score_submission(
                "温故知新", document_text, transcript_text, metadata
            )

        required_keys = {
            "score_id", "name", "org", "report_type", "course_session",
            "date", "note", "pdf_filename", "upload_path", "document_preview",
            "transcript_present", "created_at", "total_score", "total_level",
            "doc_average", "audio_average", "lowest_dimension",
            "overall_comment", "strengths", "improvements", "disclaimer",
            "dimensions", "scoring_mode", "llm_provider", "llm_model",
        }
        self.assertEqual(required_keys, set(result.keys()))

    def test_scoring_mode_is_heuristic_when_live_fails(self):
        """When live LLM fails, scoring_mode indicates heuristic."""
        document_text = (
            "本次汇报围绕战略目标、业务痛点、关键任务推进。"
            * 12
        )
        transcript_text = "背景、问题、行动、结果。" * 8
        metadata = {
            "name": "Mode Test",
            "org": "Test",
            "date": "2026-05-29",
            "course_session": "第二次课 · 组织协同",
            "note": "",
            "pdf_filename": "report.pdf",
            "upload_path": "",
            "document_preview": document_text[:800],
        }

        with patch("scoring_app.scoring.live_score_submission",
                    side_effect=RuntimeError("mock fallback")):
            result = score_submission(
                "温故知新", document_text, transcript_text, metadata
            )

        self.assertEqual(result["scoring_mode"], "heuristic")
        self.assertEqual(result["llm_provider"], "")
        self.assertEqual(result["llm_model"], "")

    def test_each_dimension_has_required_fields(self):
        """Every dimension dict has all structural fields."""
        document_text = (
            "本次汇报围绕战略目标、业务痛点、关键任务推进与结果改善展开。"
            * 12
        )
        transcript_text = "背景、问题、行动、结果。" * 8
        metadata = {
            "name": "Dim Test",
            "org": "Test",
            "date": "2026-05-29",
            "course_session": "第二次课 · 组织协同",
            "note": "",
            "pdf_filename": "report.pdf",
            "upload_path": "",
            "document_preview": document_text[:800],
        }

        with patch("scoring_app.scoring.live_score_submission",
                    side_effect=RuntimeError("mock fallback")):
            result = score_submission(
                "温故知新", document_text, transcript_text, metadata
            )

        dim_required = {
            "id", "name", "group_name", "group_weight", "actual_weight",
            "material_source", "score", "level_label", "evidence", "comment",
        }
        for dim in result["dimensions"]:
            self.assertEqual(dim_required, set(dim.keys()))

    def test_total_score_is_float_between_0_and_100(self):
        """total_score is a float in the expected range."""
        document_text = (
            "本次汇报围绕战略目标、业务痛点、关键任务推进与结果改善展开。"
            * 12
        )
        transcript_text = "背景、问题、行动、结果。" * 8
        metadata = {
            "name": "Score Range",
            "org": "Test",
            "date": "2026-05-29",
            "course_session": "第二次课 · 组织协同",
            "note": "",
            "pdf_filename": "report.pdf",
            "upload_path": "",
            "document_preview": document_text[:800],
        }

        with patch("scoring_app.scoring.live_score_submission",
                    side_effect=RuntimeError("mock fallback")):
            result = score_submission(
                "温故知新", document_text, transcript_text, metadata
            )

        self.assertIsInstance(result["total_score"], float)
        self.assertGreaterEqual(result["total_score"], 0.0)
        self.assertLessEqual(result["total_score"], 100.0)

    def test_transcript_dimension_score_is_null_when_no_transcript(self):
        """When no transcript provided, transcript-source dimensions are null."""
        document_text = (
            "本次汇报围绕战略目标、业务痛点、关键任务推进与结果改善展开。"
            * 12
        )
        metadata = {
            "name": "No Transcript",
            "org": "Test",
            "date": "2026-05-29",
            "course_session": "第二次课 · 组织协同",
            "note": "",
            "pdf_filename": "report.pdf",
            "upload_path": "",
            "document_preview": document_text[:800],
        }

        with patch("scoring_app.scoring.live_score_submission",
                    side_effect=RuntimeError("mock fallback")):
            result = score_submission(
                "温故知新", document_text, "", metadata
            )

        for dim in result["dimensions"]:
            if dim["material_source"] == "录音转写":
                self.assertIsNone(dim["score"])
                self.assertIsNone(dim["level_label"])
                self.assertEqual(dim["evidence"], "录音材料未提供。")
            else:
                self.assertIsNotNone(dim["score"])

    def test_lowest_dimension_is_in_scored_dimensions(self):
        """lowest_dimension name matches one of the dimensions."""
        document_text = (
            "本次汇报围绕战略目标、业务痛点、关键任务推进与结果改善展开。"
            * 12
        )
        transcript_text = "背景、问题、行动、结果。" * 8
        metadata = {
            "name": "Lowest Dim",
            "org": "Test",
            "date": "2026-05-29",
            "course_session": "第二次课 · 组织协同",
            "note": "",
            "pdf_filename": "report.pdf",
            "upload_path": "",
            "document_preview": document_text[:800],
        }

        with patch("scoring_app.scoring.live_score_submission",
                    side_effect=RuntimeError("mock fallback")):
            result = score_submission(
                "温故知新", document_text, transcript_text, metadata
            )

        dim_names = {d["name"] for d in result["dimensions"]
                     if d["score"] is not None}
        self.assertIn(result["lowest_dimension"]["name"], dim_names)

    def test_strengths_and_improvements_are_strings(self):
        """strengths and improvements lists contain strings."""
        document_text = (
            "本次汇报围绕战略目标、业务痛点、关键任务推进与结果改善展开。"
            * 12
        )
        transcript_text = "背景、问题、行动、结果。" * 8
        metadata = {
            "name": "Takeaway Test",
            "org": "Test",
            "date": "2026-05-29",
            "course_session": "第二次课 · 组织协同",
            "note": "",
            "pdf_filename": "report.pdf",
            "upload_path": "",
            "document_preview": document_text[:800],
        }

        with patch("scoring_app.scoring.live_score_submission",
                    side_effect=RuntimeError("mock fallback")):
            result = score_submission(
                "温故知新", document_text, transcript_text, metadata
            )

        for s in result["strengths"]:
            self.assertIsInstance(s, str)
        for i in result["improvements"]:
            self.assertIsInstance(i, str)


# ======================================================================
#  6. Boundary tests
# ======================================================================

class BoundaryTest(unittest.TestCase):
    """Boundary and edge-case tests for scoring functions."""

    def test_empty_document_raises_error(self):
        """Empty document text should raise ScoringError."""
        metadata = {
            "name": "Empty Doc",
            "org": "Test",
            "date": "2026-05-29",
            "course_session": "第二次课 · 组织协同",
            "note": "",
            "pdf_filename": "report.pdf",
            "upload_path": "",
            "document_preview": "",
        }

        with self.assertRaises(ScoringError):
            score_submission("温故知新", "", "transcript", metadata)

    def test_very_short_document_raises_error(self):
        """Document shorter than 40 chars should raise ScoringError."""
        metadata = {
            "name": "Short Doc",
            "org": "Test",
            "date": "2026-05-29",
            "course_session": "第二次课 · 组织协同",
            "note": "",
            "pdf_filename": "report.pdf",
            "upload_path": "",
            "document_preview": "很短。",
        }

        with self.assertRaises(ScoringError):
            score_submission("温故知新", "很短。", "transcript", metadata)

    def test_garbled_document_still_produces_result(self):
        """Garbled document text produces a valid (low score) result."""
        metadata = {
            "name": "Garbled Doc",
            "org": "Test",
            "date": "2026-05-29",
            "course_session": "第二次课 · 组织协同",
            "note": "",
            "pdf_filename": "report.pdf",
            "upload_path": "",
            "document_preview": "",
        }

        garbled = "锟斤拷烫烫烫锟斤拷烫烫烫" * 20
        with patch("scoring_app.scoring.live_score_submission",
                    side_effect=RuntimeError("mock fallback")):
            result = score_submission("温故知新", garbled, "", metadata)

        self.assertIn("score_id", result)
        self.assertEqual(result["scoring_mode"], "heuristic")
        self.assertIsInstance(result["total_score"], float)

    def test_single_sentence_document(self):
        """A short one-sentence document produces a valid result."""
        metadata = {
            "name": "Single Sentence",
            "org": "Test",
            "date": "2026-05-29",
            "course_session": "第二次课 · 组织协同",
            "note": "",
            "pdf_filename": "report.pdf",
            "upload_path": "",
            "document_preview": "",
        }

        text = "本次汇报围绕战略目标、业务痛点、关键任务推进与结果改善展开，团队通过协同完成了项目交付。"
        with patch("scoring_app.scoring.live_score_submission",
                    side_effect=RuntimeError("mock fallback")):
            result = score_submission("温故知新", text, "", metadata)

        self.assertIn("score_id", result)
        self.assertGreater(result["total_score"], 0.0)

    def test_very_long_document(self):
        """An extremely long document is handled without error."""
        metadata = {
            "name": "Long Doc",
            "org": "Test",
            "date": "2026-05-29",
            "course_session": "第二次课 · 组织协同",
            "note": "",
            "pdf_filename": "report.pdf",
            "upload_path": "",
            "document_preview": "",
        }

        text = (
            "本次汇报围绕战略目标、业务痛点、关键任务推进与结果改善展开。"
            * 500
        )
        with patch("scoring_app.scoring.live_score_submission",
                    side_effect=RuntimeError("mock fallback")):
            result = score_submission("温故知新", text, "", metadata)

        self.assertIn("score_id", result)
        self.assertGreater(result["total_score"], 0.0)
        self.assertLessEqual(len(result["overall_comment"]), 220)

    def test_split_sentences_empty_text(self):
        """_split_sentences handles empty input gracefully."""
        self.assertEqual(_split_sentences(""), [])

    def test_split_sentences_no_delimiters(self):
        """_split_sentences handles text with no sentence delimiters."""
        result = _split_sentences("this has no delimiter")
        self.assertEqual(result, ["this has no delimiter"])

    def test_limit_no_truncation(self):
        """_limit returns original text when within limit."""
        text = "Short text"
        self.assertEqual(_limit(text, 80), text)

    def test_limit_truncation_with_ellipsis(self):
        """_limit truncates and adds ellipsis when over limit."""
        text = "A" * 100
        result = _limit(text, 10)
        self.assertEqual(len(result), 10)
        self.assertTrue(result.endswith("…"))


# ======================================================================
#  Helper tests
# ======================================================================

class HeuristicDimensionsTest(unittest.TestCase):
    """Tests for _build_heuristic_dimensions."""

    def test_dimensions_match_definition_order(self):
        """Heuristic dimensions are returned in definition order."""
        dimensions = _build_heuristic_dimensions(
            WG_DEF,
            "战略目标明确。业务价值突出。",
            "表达清晰。重点突出。",
            transcript_present=True,
        )
        expected_ids = [d["id"] for d in WG_DEF["dimensions"]]
        actual_ids = [d["id"] for d in dimensions]
        self.assertEqual(actual_ids, expected_ids)

    def test_heuristic_dimensions_action_learning(self):
        """Action learning report types also produce valid dimensions."""
        dimensions = _build_heuristic_dimensions(
            XL_DEF,
            "问题暴露充分，根因分析深入。创新方案有差异化价值。",
            "表达清晰，重点突出。",
            transcript_present=True,
        )
        self.assertEqual(len(dimensions), len(XL_DEF["dimensions"]))

    def test_document_dimensions_are_scored(self):
        """Document-source dimensions get numeric scores."""
        dimensions = _build_heuristic_dimensions(
            WG_DEF,
            "战略目标明确，业务价值突出，支撑到位，痛点清晰。",
            "",
            transcript_present=True,
        )
        doc_dims = [d for d in dimensions if d["material_source"] == "文档"]
        for dim in doc_dims:
            self.assertIsNotNone(dim["score"])
            self.assertIsNotNone(dim["level_label"])
            self.assertTrue(dim["evidence"])

    def test_transcript_dimensions_null_when_missing(self):
        """Transcript-source dimensions are null when no transcript."""
        dimensions = _build_heuristic_dimensions(
            WG_DEF,
            "战略目标明确，业务价值突出。",
            "",
            transcript_present=False,
        )
        transcript_dims = [d for d in dimensions
                           if d["material_source"] == "录音转写"]
        for dim in transcript_dims:
            self.assertIsNone(dim["score"])
            self.assertIsNone(dim["level_label"])
            self.assertEqual(dim["evidence"], "录音材料未提供。")


class ExactKeywordSelectionTest(unittest.TestCase):
    """Fine-grained tests ensuring keywords drive sentence selection."""

    def test_prefers_first_keyword_over_later_keywords(self):
        """When sentence A has keyword[0] and sentence B has keyword[1],
        the evidence should come from sentence A."""
        text = (
            "战略规划是本次汇报的重点内容。"
            "业务成果显著提升。"
        )
        # "战略" comes before "业务" in keyword list
        keywords = ["战略", "业务"]
        evidence = _build_evidence(text, keywords)
        self.assertIn("战略", evidence)

    def test_keyword_density_not_currently_used(self):
        """The current implementation does NOT use keyword density;
        it uses first-match. This test documents current behavior
        and will need updating when weighted scoring lands."""
        text = (
            "团队执行细节表现一般。"
            "战略目标明确，业务价值突出，支撑到位，痛点清晰。"
        )
        keywords = ["战略", "业务"]
        evidence = _build_evidence(text, keywords)
        # First sentence doesn't match any keyword.
        # Second sentence matches "战略" (first keyword that appears).
        self.assertIn("战略", evidence)

    def test_evidence_is_from_source_text(self):
        """Every evidence string should be a substring of the source text."""
        text = (
            "战略规划聚焦于客户的核心业务需求。"
            "团队协同完成了项目交付。"
        )
        keywords = ["战略", "核心"]
        evidence = _build_evidence(text, keywords)
        self.assertIn(evidence.rstrip("…。，"), text)

    def test_all_keywords_empty(self):
        """Empty keyword list falls through to first sentence."""
        text = "战略规划是本次汇报的核心内容。团队执行良好。"
        evidence = _build_evidence(text, [])
        self.assertIn("战略规划是本次汇报的核心内容", evidence)


# ======================================================================
#  API contract verification
# ======================================================================

class ApiContractTest(unittest.TestCase):
    """Verify API response structures match expected contracts.

    These tests mock the full Flask layer to verify the JSON shapes
    returned by the API endpoints.
    """

    def _make_app(self):
        """Create a fresh test app with temp directories."""
        import tempfile
        import shutil
        from scoring_app import create_app

        tmp_dir = tempfile.mkdtemp(prefix="demo2-contract-")
        self._contract_tmp_dir = tmp_dir
        data_dir = os.path.join(tmp_dir, "data")
        upload_dir = os.path.join(tmp_dir, "uploads")
        os.environ["SCORING_APP_DATA_DIR"] = data_dir
        os.environ["SCORING_APP_UPLOAD_DIR"] = upload_dir
        os.environ["SCORING_APP_DB_PATH"] = os.path.join(data_dir, "scores.db")

        app = create_app()
        app.testing = True
        return app.test_client()

    def tearDown(self):
        import shutil
        if hasattr(self, "_contract_tmp_dir"):
            shutil.rmtree(self._contract_tmp_dir, ignore_errors=True)

    def _register_user(self, client):
        """Register and return a user session."""
        resp = client.post(
            "/api/auth/register",
            json={"email": "contract@test.com", "display_name": "Contract",
                  "password": "Passw0rd!"},
        )
        self.assertEqual(resp.status_code, 201)

    def _create_score(self, client):
        """Create a test score via POST /api/score with mocked PDF/extraction."""
        from io import BytesIO
        from unittest.mock import patch

        with patch(
            "scoring_app.services.score_service.extract_text_from_pdf_bytes",
            return_value=(
                "本次汇报围绕战略目标、业务痛点、关键任务推进与结果改善展开。"
                * 12
            ),
        ), patch(
            "scoring_app.services.score_service.score_submission",
            return_value={
                "score_id": "contract-score-001",
                "name": "Contract Student",
                "org": "Test",
                "report_type": "温故知新",
                "course_session": "第二次课 · 组织协同",
                "date": "2026-05-29",
                "note": "",
                "pdf_filename": "report.pdf",
                "upload_path": "db://score_artifacts/contract-score-001/source_pdf",
                "document_preview": "preview",
                "transcript_present": True,
                "created_at": "2026-05-29T10:00:00Z",
                "total_score": 85.0,
                "total_level": "优秀",
                "doc_average": 8.5,
                "audio_average": 8.0,
                "lowest_dimension": {"name": "创新与突破性", "score": 7.5},
                "overall_comment": "Overall performance is steady.",
                "strengths": ["Clear structure"],
                "improvements": ["Add more evidence"],
                "disclaimer": "本报告由 AI 智能体自动生成...",
                "scoring_mode": "heuristic",
                "llm_provider": "",
                "llm_model": "",
                "dimensions": [
                    {
                        "id": 1,
                        "name": "战略链接与价值认知",
                        "group_name": "温故·实战复盘",
                        "group_weight": 55.0,
                        "actual_weight": 5.5,
                        "material_source": "文档",
                        "score": 8.5,
                        "level_label": "优秀",
                        "evidence": "战略规划聚焦于客户需求",
                        "comment": "该维度表现扎实。",
                    }
                ],
            },
        ):
            return client.post(
                "/api/score",
                data={
                    "name": "Contract Student",
                    "org": "Test",
                    "report_type": "温故知新",
                    "course_session": "第二次课 · 组织协同",
                    "date": "2026-05-29",
                    "note": "",
                    "transcript": "Test transcript.",
                    "pdf_file": (BytesIO(b"%PDF-1.4 test"), "report.pdf"),
                },
                content_type="multipart/form-data",
            )

    def test_post_score_result_structure(self):
        """POST /api/score returns expected structure."""
        client = self._make_app()
        self._register_user(client)
        resp = self._create_score(client)

        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()

        # Top-level fields
        self.assertIn("score_id", payload)
        self.assertIn("name", payload)
        self.assertIn("report_type", payload)
        self.assertIn("course_session", payload)
        self.assertIn("markdown_export_url", payload)
        self.assertIn("pdf_export_url", payload)

    def test_get_scores_list_structure(self):
        """GET /api/scores returns expected list structure."""
        client = self._make_app()
        self._register_user(client)
        self._create_score(client)

        resp = client.get("/api/scores")
        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        self.assertIn("items", payload)
        self.assertIsInstance(payload["items"], list)
        if payload["items"]:
            item = payload["items"][0]
            self.assertIn("score_id", item)
            self.assertIn("name", item)
            self.assertIn("report_type", item)
            self.assertIn("course_session", item)
            self.assertIn("total_score", item)
            self.assertIn("manual_score_status", item)

    def test_get_scores_detail_structure(self):
        """GET /api/scores/<id> returns expected detail structure."""
        client = self._make_app()
        self._register_user(client)
        resp = self._create_score(client)
        score_id = resp.get_json()["score_id"]

        detail_resp = client.get(f"/api/scores/{score_id}")
        self.assertEqual(detail_resp.status_code, 200)
        detail = detail_resp.get_json()

        self.assertIn("score_id", detail)
        self.assertIn("name", detail)
        self.assertIn("dimensions", detail)
        self.assertIn("transcript_present", detail)
        self.assertIn("total_score", detail)
        self.assertIn("overall_comment", detail)
        self.assertIn("pdf_export_url", detail)

        if detail["dimensions"]:
            dim = detail["dimensions"][0]
            self.assertIn("id", dim)
            self.assertIn("name", dim)
            self.assertIn("score", dim)
            self.assertIn("evidence", dim)
            self.assertIn("comment", dim)
            self.assertIn("level_label", dim)

    def test_export_md_returns_markdown(self):
        """GET /api/scores/<id>/export?format=md returns markdown."""
        client = self._make_app()
        self._register_user(client)
        resp = self._create_score(client)
        score_id = resp.get_json()["score_id"]

        md_resp = client.get(f"/api/scores/{score_id}/export?format=md")
        self.assertEqual(md_resp.status_code, 200)
        self.assertIn("text/markdown", md_resp.headers.get("Content-Type", ""))


# ======================================================================
#  10. Scoring helper functions — _calc_* and _build_evidence_summary
# ======================================================================


class ScoringHelperFunctionsTest(unittest.TestCase):
    """Direct tests for scoring helper functions."""

    # ----- _calc_keyword_density -----

    def test_keyword_density_all_hit(self):
        self.assertEqual(_calc_keyword_density("战略目标业务价值", ["战略", "目标", "价值"]), 1.0)

    def test_keyword_density_partial_hit(self):
        self.assertEqual(_calc_keyword_density("战略目标", ["战略", "价值", "业务"]), 1.0 / 3.0)

    def test_keyword_density_no_hit(self):
        self.assertEqual(_calc_keyword_density("无关内容", ["战略", "价值"]), 0.0)

    def test_keyword_density_empty_keywords(self):
        self.assertEqual(_calc_keyword_density("任意文本", []), 0.0)

    # ----- _calc_focus_alignment -----

    def test_focus_alignment_exact_focus_in_text(self):
        score = _calc_focus_alignment("问题穿透深度表现良好", "", "问题穿透深度")
        self.assertGreater(score, 0.0)

    def test_focus_alignment_name_in_text(self):
        score = _calc_focus_alignment("这个战略链接很清晰", "战略链接与价值认知", "")
        self.assertGreater(score, 0.0)

    def test_focus_alignment_no_match(self):
        score = _calc_focus_alignment("无关内容", "战略链接", "问题穿透深度")
        self.assertEqual(score, 0.0)

    def test_focus_alignment_empty_inputs(self):
        self.assertEqual(_calc_focus_alignment("文本", "", ""), 0.0)

    # ----- _calc_position_bonus -----

    def test_position_bonus_first_sentence(self):
        self.assertGreater(_calc_position_bonus(0, 10), 0.0)

    def test_position_bonus_last_sentence(self):
        self.assertGreater(_calc_position_bonus(9, 10), 0.0)

    def test_position_bonus_middle_sentence(self):
        first = _calc_position_bonus(0, 10)
        middle = _calc_position_bonus(5, 10)
        self.assertGreater(first, middle)

    def test_position_bonus_single_sentence(self):
        self.assertGreaterEqual(_calc_position_bonus(0, 1), 0.0)

    # ----- _calc_exhaustivity_penalty -----

    def test_exhaustivity_penalty_already_used(self):
        self.assertGreater(_calc_exhaustivity_penalty("已用句子", {"已用句子", "其他"}), 0.0)

    def test_exhaustivity_penalty_not_used(self):
        self.assertEqual(_calc_exhaustivity_penalty("新句子", {"已用句子"}), 0.0)

    def test_exhaustivity_penalty_empty_used(self):
        self.assertEqual(_calc_exhaustivity_penalty("任意句子", set()), 0.0)

    # ----- _build_evidence_summary -----

    def test_evidence_summary_excellent(self):
        s = _build_evidence_summary(9.5, "问题穿透深度")
        self.assertIn("问题穿透深度", s)
        self.assertLessEqual(len(s), 15)

    def test_evidence_summary_good(self):
        s = _build_evidence_summary(6.5, "战略理解深度")
        self.assertIn("战略理解深度", s)
        self.assertLessEqual(len(s), 15)

    def test_evidence_summary_unqualified(self):
        s = _build_evidence_summary(2.0, "方案差异化")
        self.assertIn("方案差异化", s)
        self.assertLessEqual(len(s), 15)

    def test_evidence_summary_empty_focus(self):
        self.assertEqual(_build_evidence_summary(8.0, ""), "")

    def test_evidence_summary_long_focus_truncated(self):
        s = _build_evidence_summary(7.0, "这是一个非常长的focus描述文本需要截断")
        self.assertLessEqual(len(s), 15)

    # ----- _limit smart truncation -----

    def test_limit_short_text_preserved(self):
        self.assertEqual(_limit("短文本", 80), "短文本")

    def test_limit_smart_truncation_preserves_head(self):
        text = "A" * 100
        result = _limit(text, 80)
        head_size = int(80 * 0.6)
        self.assertTrue(result.startswith("A" * head_size), f"Expected head {head_size} As, got: {result[:head_size+5]}")

    def test_limit_smart_truncation_preserves_tail(self):
        text = "A" * 50 + "B" * 50
        result = _limit(text, 80)
        self.assertIn("B", result.split("…")[-1])

    def test_limit_smart_truncation_has_ellipsis(self):
        text = "X" * 100
        result = _limit(text, 80)
        self.assertIn("…", result)

    def test_limit_very_short_limit_falls_back_to_head_only(self):
        text = "A" * 50
        result = _limit(text, 12)
        self.assertIn("…", result)
        self.assertLessEqual(len(result), 12)


# ======================================================================
#  11. Evidence deduplication across dimensions
# ======================================================================


class EvidenceDeduplicationTest(unittest.TestCase):
    """Evidence deduplication via used_sentences and exhaustivity penalty."""

    def test_different_dimensions_get_different_evidence(self):
        text = (
            "战略目标是提升业务价值。"
            "团队使用了RACI框架分析协同障碍。"
            "通过数据驱动方法改进了流程效率。"
            "创新方案解决了组织分工问题。"
        )
        dims = _build_heuristic_dimensions(
            XL_DEF, text, "", transcript_present=False
        )
        scored_dims = [d for d in dims if d["score"] is not None]
        evidence_texts = [d["evidence"] for d in scored_dims]
        # Remove summary prefix for dedup check
        raw_ev = [e.split("：", 1)[-1] if "：" in e else e for e in evidence_texts]
        duplicates = len(raw_ev) - len(set(raw_ev))
        # With few sentences per dimension, exhaustivity is a soft penalty,
        # not a hard block. Accept at most 1 duplicate in tight scenarios.
        self.assertLessEqual(
            duplicates, 1,
            f"Too many duplicate evidence: {raw_ev}, duplicates={duplicates}"
        )

    def test_evidence_summary_prepended_in_heuristic(self):
        text = (
            "战略目标是提升业务价值。团队使用了RACI框架分析协同障碍。"
            "通过数据驱动方法改进了流程效率。"
        ) * 3
        dims = _build_heuristic_dimensions(
            XL_DEF, text, "", transcript_present=False
        )
        scored_dims = [d for d in dims if d["score"] is not None]
        for dim in scored_dims:
            ev = dim["evidence"]
            self.assertTrue(
                "：" in ev or len(ev) <= 80,
                f"Evidence should have summary prefix or be short: {ev[:60]}"
            )

    def test_no_transcript_dimensions_have_placeholder(self):
        dims = _build_heuristic_dimensions(
            XL_DEF, "文档内容足够长。文档内容足够长。" * 5, "", transcript_present=False
        )
        for dim in dims:
            if dim["material_source"] == "录音转写":
                self.assertIsNone(dim["score"])
                self.assertIn("录音材料未提供", dim["evidence"])


# ======================================================================
#  12. _score_dimension() behavior
# ======================================================================


class ScoreDimensionTest(unittest.TestCase):
    """Direct tests for _score_dimension()."""

    def test_score_with_many_keywords_is_higher(self):
        dim_low = {"keywords": ["X"], "needs_numbers": False}
        dim_high = {"keywords": ["战略", "目标", "业务", "价值", "支撑", "痛点", "任务"], "needs_numbers": False}
        text = "战略目标与业务价值支撑痛点任务。战略目标与业务价值支撑痛点任务。" * 3
        low_score = _score_dimension(text, dim_low)
        high_score = _score_dimension(text, dim_high)
        self.assertGreater(high_score, low_score)

    def test_score_with_numbers_gets_bonus(self):
        dim = {"keywords": ["提升", "效率"], "needs_numbers": True}
        text_no_num = "提升了团队效率。" * 5
        text_with_num = "效率提升了30%，团队效果显著。提升了团队效率。" * 3
        score_no = _score_dimension(text_no_num, dim)
        score_yes = _score_dimension(text_with_num, dim)
        self.assertGreaterEqual(score_yes, score_no)

    def test_score_is_clamped_3_8_to_9_0(self):
        dim = {"keywords": [], "needs_numbers": False}
        self.assertGreaterEqual(_score_dimension("短", dim), 3.8)
        very_rich = "战略目标业务价值支撑痛点任务框架模型工具方法认知协同解题。" * 20
        self.assertLessEqual(_score_dimension(very_rich, dim), 9.0)

    def test_garbled_text_scores_low(self):
        dim = {"keywords": ["战略", "目标"], "needs_numbers": False}
        garbled = "\x00\x01\x02\x03\x04\x05\x06\x07\x08" * 10
        score = _score_dimension(garbled, dim)
        self.assertLessEqual(score, 4.2)


if __name__ == "__main__":
    unittest.main()
