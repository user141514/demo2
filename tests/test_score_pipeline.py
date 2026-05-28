import json
import os
import shutil
import tempfile
import time
import unittest
from io import BytesIO
from unittest.mock import patch

from scoring_app import create_app
from scoring_app.rules import REPORT_DEFINITIONS


class ScorePipelineTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="demo2-pipeline-")
        self.data_dir = os.path.join(self.temp_dir, "data")
        self.upload_dir = os.path.join(self.temp_dir, "uploads")
        self.env_keys = [
            "SCORING_APP_DATA_DIR",
            "SCORING_APP_UPLOAD_DIR",
            "SCORING_APP_DB_PATH",
            "SCORING_SCORE_STREAM_HEARTBEAT_SECONDS",
        ]
        self.env_backup = {key: os.environ.get(key) for key in self.env_keys}
        os.environ["SCORING_APP_DATA_DIR"] = self.data_dir
        os.environ["SCORING_APP_UPLOAD_DIR"] = self.upload_dir
        os.environ["SCORING_APP_DB_PATH"] = os.path.join(self.data_dir, "scores.db")

        self.report_type = self._find_report_type("wg")
        self.report_definition = REPORT_DEFINITIONS[self.report_type]
        self.app = create_app()
        self.app.testing = True
        self.client = self.app.test_client()

    def tearDown(self):
        for key, value in self.env_backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_authenticated_score_submission_history_detail_and_export_flow(self):
        self._register_flow_user()

        with patch(
            "scoring_app.services.score_service.extract_text_from_pdf_bytes",
            return_value=("This is a complete document body used to verify the score pipeline. " * 8),
        ), patch(
            "scoring_app.services.score_service.score_submission",
            return_value=self._build_score_result(),
        ):
            create_response = self.client.post(
                "/api/score",
                data={
                    "name": "Pipeline Student",
                    "org": "Delivery Team",
                    "report_type": self.report_type,
                    "course_session": "第二次课 · 组织协同",
                    "date": "2026-05-24",
                    "note": "Pipeline smoke test",
                    "transcript": "This transcript is used to validate the end-to-end score flow.",
                    "pdf_file": (BytesIO(b"%PDF-1.4 test content"), "report.pdf"),
                },
                content_type="multipart/form-data",
            )

        self.assertEqual(create_response.status_code, 200)
        score_payload = create_response.get_json()
        score_id = score_payload["score_id"]
        self.assertEqual(score_payload["course_session"], "第二次课 · 组织协同")
        self.assertEqual(score_payload["name"], "Pipeline Student")
        self.assertEqual(score_payload["org"], "Delivery Team")
        self.assertEqual(
            score_payload["markdown_export_url"],
            "/api/scores/{}/export?format=md".format(score_id),
        )
        self.assertEqual(
            score_payload["pdf_export_url"],
            "/api/scores/{}/export?format=pdf".format(score_id),
        )

        history_response = self.client.get("/api/scores")
        self.assertEqual(history_response.status_code, 200)
        history_items = history_response.get_json()["items"]
        self.assertEqual(len(history_items), 1)
        self.assertEqual(history_items[0]["score_id"], score_id)
        self.assertEqual(history_items[0]["course_session"], "第二次课 · 组织协同")
        self.assertEqual(history_items[0]["manual_score_status"], "pending")

        detail_response = self.client.get("/api/scores/{}".format(score_id))
        self.assertEqual(detail_response.status_code, 200)
        detail_payload = detail_response.get_json()
        self.assertEqual(detail_payload["score_id"], score_id)
        self.assertEqual(detail_payload["course_session"], "第二次课 · 组织协同")
        self.assertEqual(detail_payload["pdf_export_url"], "/api/scores/{}/export?format=pdf".format(score_id))
        self.assertEqual(len(detail_payload["dimensions"]), 3)
        self.assertTrue(detail_payload["transcript_present"])

        markdown_response = self.client.get("/api/scores/{}/export?format=md".format(score_id))
        try:
            self.assertEqual(markdown_response.status_code, 200)
            self.assertIn("text/markdown", markdown_response.headers["Content-Type"])
            self.assertIn(".md", markdown_response.headers["Content-Disposition"])
            export_text = markdown_response.get_data(as_text=True)
            self.assertIn(self.report_type, export_text)
            self.assertIn("第二次课 · 组织协同", export_text)
            self.assertIn("Pipeline Student", export_text)
            self.assertIn("Overall performance is steady", export_text)
            self.assertLess(export_text.index("## 一级维度明细"), export_text.index("## 结论与建议"))
            self.assertLess(export_text.index("### 总评"), export_text.index("### 优势与亮点"))
            self.assertLess(export_text.index("### 优势与亮点"), export_text.index("### 改进方向"))
        finally:
            markdown_response.close()

        pdf_response = self.client.get("/api/scores/{}/export?format=pdf".format(score_id))
        try:
            self.assertEqual(pdf_response.status_code, 200)
            self.assertEqual(pdf_response.headers["Content-Type"], "application/pdf")
            self.assertIn(".pdf", pdf_response.headers["Content-Disposition"])
            pdf_bytes = pdf_response.get_data()
            self.assertTrue(pdf_bytes.startswith(b"%PDF"))
            self.assertGreater(len(pdf_bytes), 1024)
        finally:
            pdf_response.close()

        logout_response = self.client.post("/api/auth/logout")
        self.assertEqual(logout_response.status_code, 200)
        self.assertEqual(self.client.get("/api/scores").status_code, 401)

    def test_generic_action_learning_uses_course_rubric_and_keeps_public_type(self):
        self._register_flow_user(email="course-map@example.com", display_name="Course Map")
        captured = {}

        def fake_score_submission(report_type, document_text, transcript_text, metadata):
            captured["report_type"] = report_type
            result = self._build_score_result(score_id="pipeline-score-course-map")
            result["report_type"] = report_type
            return result

        with patch(
            "scoring_app.services.score_service.extract_text_from_pdf_bytes",
            return_value=("This is a complete document body used to verify course mapping. " * 8),
        ), patch(
            "scoring_app.services.score_service.score_submission",
            side_effect=fake_score_submission,
        ):
            response = self.client.post(
                "/api/score",
                data={
                    "name": "Course Map Student",
                    "org": "Delivery Team",
                    "report_type": "\u884c\u52a8\u5b66\u4e60",
                    "course_session": "\u7b2c\u4e8c\u6b21\u8bfe \u00b7 \u7ec4\u7ec7\u534f\u540c",
                    "date": "2026-05-28",
                    "note": "Course mapping",
                    "transcript": "Transcript for course mapping.",
                    "pdf_file": (BytesIO(b"%PDF-1.4 test content"), "report.pdf"),
                },
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(captured["report_type"], "\u884c\u52a8\u5b66\u4e60-\u7ec4\u7ec7\u534f\u540c")
        self.assertEqual(payload["report_type"], "\u884c\u52a8\u5b66\u4e60")

        history_response = self.client.get("/api/scores")
        self.assertEqual(history_response.status_code, 200)
        history_items = history_response.get_json()["items"]
        self.assertEqual(history_items[0]["report_type"], "\u884c\u52a8\u5b66\u4e60")

    def test_heuristic_takeaways_are_single_overall_sentences(self):
        from scoring_app.scoring import score_submission

        document_text = (
            "This report explains the problem, root cause, structure, plan, action, "
            "result, metrics, reflection, innovation, collaboration, and next steps. "
            * 12
        )
        transcript_text = (
            "The presentation is clear, structured, responsive to questions, and keeps time. "
            * 8
        )

        with patch("scoring_app.scoring.live_score_submission", side_effect=RuntimeError("mock")):
            payload = score_submission(
                self.report_type,
                document_text,
                transcript_text,
                {
                    "name": "Takeaway Student",
                    "org": "Delivery Team",
                    "date": "2026-05-28",
                    "course_session": "\u7b2c\u4e8c\u6b21\u8bfe \u00b7 \u7ec4\u7ec7\u534f\u540c",
                    "note": "",
                    "pdf_filename": "report.pdf",
                    "upload_path": "",
                    "document_preview": document_text[:800],
                },
            )

        self.assertEqual(len(payload["strengths"]), 1)
        self.assertEqual(len(payload["improvements"]), 1)
        for dimension in self.report_definition["dimensions"]:
            self.assertNotIn(dimension["name"], payload["strengths"][0])
            self.assertNotIn(dimension["name"], payload["improvements"][0])

    def test_streaming_score_submission_sends_heartbeat_and_result(self):
        self._register_flow_user(email="stream@example.com", display_name="Stream User")
        os.environ["SCORING_SCORE_STREAM_HEARTBEAT_SECONDS"] = "0.01"

        def slow_score_submission(report_type, document_text, transcript_text, metadata):
            time.sleep(0.04)
            return self._build_score_result(score_id="pipeline-stream-001")

        with patch(
            "scoring_app.services.score_service.extract_text_from_pdf_bytes",
            return_value=("This is a complete document body used to verify stream scoring. " * 8),
        ), patch(
            "scoring_app.services.score_service.score_submission",
            side_effect=slow_score_submission,
        ):
            response = self.client.post(
                "/api/score/stream",
                data={
                    "name": "Stream Student",
                    "org": "Delivery Team",
                    "report_type": self.report_type,
                    "course_session": "\u7b2c\u4e8c\u6b21\u8bfe \u00b7 \u7ec4\u7ec7\u534f\u540c",
                    "date": "2026-05-24",
                    "note": "Streaming smoke test",
                    "transcript": "Transcript for streaming score flow.",
                    "pdf_file": (BytesIO(b"%PDF-1.4 test content"), "stream-report.pdf"),
                },
                content_type="multipart/form-data",
                buffered=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("application/x-ndjson", response.headers["Content-Type"])
        events = [
            json.loads(line)
            for line in response.get_data(as_text=True).splitlines()
            if line.strip()
        ]
        event_types = [event["type"] for event in events]
        self.assertEqual(event_types[0], "status")
        self.assertIn("heartbeat", event_types)
        self.assertEqual(event_types[-1], "result")
        self.assertEqual(events[-1]["result"]["score_id"], "pipeline-stream-001")

        history_response = self.client.get("/api/scores")
        self.assertEqual(history_response.status_code, 200)
        history_items = history_response.get_json()["items"]
        self.assertEqual(len(history_items), 1)
        self.assertEqual(history_items[0]["score_id"], "pipeline-stream-001")

    def test_garbled_inline_transcript_falls_back_to_uploaded_file_text(self):
        self._register_flow_user(email="fallback@example.com", display_name="Fallback User")
        captured = {}

        def fake_score_submission(report_type, document_text, transcript_text, metadata):
            captured["transcript_text"] = transcript_text
            return self._build_score_result(score_id="pipeline-score-002")

        clean_transcript = "第一段说明当前问题。\n第二段说明后续行动。".encode("gb18030")
        with patch(
            "scoring_app.services.score_service.extract_text_from_pdf_bytes",
            return_value=("This is a complete document body used to verify transcript fallback. " * 8),
        ), patch(
            "scoring_app.services.score_service.score_submission",
            side_effect=fake_score_submission,
        ):
            response = self.client.post(
                "/api/score",
                data={
                    "name": "Transcript Fallback",
                    "org": "Delivery Team",
                    "report_type": self.report_type,
                    "course_session": "第二次课 · 组织协同",
                    "date": "2026-05-24",
                    "note": "Encoding fallback",
                    "transcript": "閿焃 閸?鐠?閺?閻?瑜?",
                    "transcript_file": (BytesIO(clean_transcript), "transcript.txt"),
                    "pdf_file": (BytesIO(b"%PDF-1.4 test content"), "report.pdf"),
                },
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("第一段", captured["transcript_text"])
        self.assertIn("第二段", captured["transcript_text"])

    def test_history_and_exports_survive_restart_without_upload_directory(self):
        self._register_flow_user(email="restart@example.com", display_name="Restart User")

        with patch(
            "scoring_app.services.score_service.extract_text_from_pdf_bytes",
            return_value=("This is a complete document body used to verify persistence. " * 8),
        ), patch(
            "scoring_app.services.score_service.score_submission",
            return_value=self._build_score_result(score_id="pipeline-score-003"),
        ):
            create_response = self.client.post(
                "/api/score",
                data={
                    "name": "Restart Student",
                    "org": "Delivery Team",
                    "report_type": self.report_type,
                    "course_session": "第二次课 · 组织协同",
                    "date": "2026-05-24",
                    "note": "Restart persistence",
                    "transcript": "Transcript for persistence verification.",
                    "pdf_file": (BytesIO(b"%PDF-1.4 test content"), "report.pdf"),
                },
                content_type="multipart/form-data",
            )

        self.assertEqual(create_response.status_code, 200)
        score_id = create_response.get_json()["score_id"]
        shutil.rmtree(self.upload_dir, ignore_errors=True)

        restarted_app = create_app()
        restarted_app.testing = True
        restarted_client = restarted_app.test_client()
        login_response = restarted_client.post(
            "/api/auth/login",
            json={"email": "restart@example.com", "password": "Passw0rd!"},
        )
        self.assertEqual(login_response.status_code, 200)

        history_response = restarted_client.get("/api/scores")
        self.assertEqual(history_response.status_code, 200)
        history_items = history_response.get_json()["items"]
        self.assertEqual(len(history_items), 1)
        self.assertEqual(history_items[0]["score_id"], score_id)

        markdown_response = restarted_client.get("/api/scores/{}/export?format=md".format(score_id))
        try:
            self.assertEqual(markdown_response.status_code, 200)
            self.assertIn("text/markdown", markdown_response.headers["Content-Type"])
        finally:
            markdown_response.close()

        pdf_response = restarted_client.get("/api/scores/{}/export?format=pdf".format(score_id))
        try:
            self.assertEqual(pdf_response.status_code, 200)
            self.assertEqual(pdf_response.headers["Content-Type"], "application/pdf")
            self.assertTrue(pdf_response.get_data().startswith(b"%PDF"))
        finally:
            pdf_response.close()

    def _find_report_type(self, definition_id):
        for report_type, definition in REPORT_DEFINITIONS.items():
            if definition["id"] == definition_id:
                return report_type
        raise AssertionError("Missing report definition id: {}".format(definition_id))

    def _register_flow_user(self, email="flow@example.com", display_name="Flow User"):
        register_response = self.client.post(
            "/api/auth/register",
            json={
                "email": email,
                "display_name": display_name,
                "password": "Passw0rd!",
            },
        )
        self.assertEqual(register_response.status_code, 201)
        return register_response.get_json()["user"]

    def _build_score_result(self, score_id="pipeline-score-001"):
        dimensions = self.report_definition["dimensions"]
        selected = [dimensions[0], dimensions[5], dimensions[8]]
        scores = [8.8, 8.1, 7.9]
        comments = [
            "Strong support from the submitted material.",
            "The goal and business value are described clearly.",
            "The expression is clear but could use more chain detail.",
        ]
        evidence = [
            "The material explains the link between goals, actions, and outcomes.",
            "The document gives a direct explanation of topic value and team impact.",
            "The transcript describes sequence, highlights, and a conclusion clearly.",
        ]

        return {
            "score_id": score_id,
            "name": "Pipeline Student",
            "org": "Delivery Team",
            "report_type": self.report_type,
            "date": "2026-05-24",
            "note": "Pipeline smoke test",
            "pdf_filename": "report.pdf",
            "upload_path": "db://score_artifacts/{}/source_pdf".format(score_id),
            "document_preview": "Pipeline preview",
            "transcript_present": True,
            "created_at": "2026-05-24T10:00:00Z",
            "total_score": 84.2,
            "total_level": "优秀",
            "doc_average": 8.5,
            "audio_average": 7.9,
            "lowest_dimension": {"name": selected[-1]["name"], "score": scores[-1]},
            "overall_comment": "Overall performance is steady and the structure is clear.",
            "strengths": ["Clear structure", "Strong business alignment"],
            "improvements": ["Add more direct evidence"],
            "disclaimer": "Test disclaimer",
            "dimensions": [
                {
                    "id": dimension["id"],
                    "name": dimension["name"],
                    "group_name": dimension["group"],
                    "group_weight": dimension["group_weight"],
                    "actual_weight": dimension["actual_weight"],
                    "material_source": dimension["material_source"],
                    "score": score,
                    "level_label": "优秀",
                    "evidence": evidence[index],
                    "comment": comments[index],
                }
                for index, (dimension, score) in enumerate(zip(selected, scores))
            ],
        }


if __name__ == "__main__":
    unittest.main()
