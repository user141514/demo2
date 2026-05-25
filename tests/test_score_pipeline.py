import os
import shutil
import tempfile
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
        register_response = self.client.post(
            "/api/auth/register",
            json={
                "email": "flow@example.com",
                "display_name": "Flow User",
                "password": "Passw0rd!",
            },
        )
        self.assertEqual(register_response.status_code, 201)

        with patch(
            "scoring_app.services.score_service.extract_text_from_pdf_bytes",
            return_value=("这是一份完整的文档内容，用于测试评分通路是否完备。") * 8,
        ), patch(
            "scoring_app.services.score_service.score_submission",
            return_value=self._build_score_result(),
        ):
            create_response = self.client.post(
                "/api/score",
                data={
                    "name": "测试学员",
                    "org": "交付一部",
                    "report_type": self.report_type,
                    "date": "2026-05-24",
                    "note": "通路测试",
                    "transcript": "这是录音转写内容，用于验证文档和录音双材料评分流程。",
                    "pdf_file": (BytesIO(b"%PDF-1.4 test content"), "report.pdf"),
                },
                content_type="multipart/form-data",
            )

        self.assertEqual(create_response.status_code, 200)
        score_payload = create_response.get_json()
        score_id = score_payload["score_id"]
        self.assertEqual(score_payload["name"], "测试学员")
        self.assertEqual(score_payload["org"], "交付一部")
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
        self.assertEqual(history_items[0]["manual_score_status"], "pending")

        detail_response = self.client.get("/api/scores/{}".format(score_id))
        self.assertEqual(detail_response.status_code, 200)
        detail_payload = detail_response.get_json()
        self.assertEqual(detail_payload["score_id"], score_id)
        self.assertEqual(detail_payload["pdf_export_url"], "/api/scores/{}/export?format=pdf".format(score_id))
        self.assertEqual(len(detail_payload["dimensions"]), 3)
        self.assertTrue(detail_payload["transcript_present"])

        export_response = self.client.get(
            "/api/scores/{}/export?format=md".format(score_id)
        )
        try:
            self.assertEqual(export_response.status_code, 200)
            self.assertIn("text/markdown", export_response.headers["Content-Type"])
            self.assertIn(".md", export_response.headers["Content-Disposition"])
            export_text = export_response.get_data(as_text=True)
            self.assertIn("测试学员", export_text)
            self.assertIn(self.report_type, export_text)
            self.assertIn("综合表现稳健", export_text)
        finally:
            export_response.close()

        pdf_response = self.client.get(
            "/api/scores/{}/export?format=pdf".format(score_id)
        )
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

    def _find_report_type(self, definition_id):
        for report_type, definition in REPORT_DEFINITIONS.items():
            if definition["id"] == definition_id:
                return report_type
        raise AssertionError("Missing report definition id: {}".format(definition_id))

    def _build_score_result(self):
        dimensions = self.report_definition["dimensions"]
        selected = [dimensions[0], dimensions[5], dimensions[8]]
        scores = [8.8, 8.1, 7.9]
        comments = [
            "该维度材料支撑充分，论证链路完整。",
            "该维度目标说明明确，具备较强的推进价值。",
            "该维度表达清楚，但还能补充更多链条细节。",
        ]
        evidence = [
            "材料中明确说明了目标、动作与结果之间的关系。",
            "文档对课题价值与组织收益给出了直接说明。",
            "录音转写中对汇报顺序和关键结论有清晰表达。",
        ]

        return {
            "score_id": "pipeline-score-001",
            "name": "测试学员",
            "org": "交付一部",
            "report_type": self.report_type,
            "date": "2026-05-24",
            "note": "通路测试",
            "pdf_filename": "report.pdf",
            "upload_path": "uploads/report.pdf",
            "document_preview": "测试文档预览",
            "transcript_present": True,
            "created_at": "2026-05-24T10:00:00Z",
            "total_score": 84.2,
            "total_level": "优秀",
            "doc_average": 8.5,
            "audio_average": 7.9,
            "lowest_dimension": {"name": selected[-1]["name"], "score": scores[-1]},
            "overall_comment": "综合表现稳健，结构清晰，建议继续补强低分维度的细节证据。",
            "strengths": ["战略链接与价值认知表现较强。", "课题的战略价值说明充分。"],
            "improvements": ["逻辑的严谨性和链条完整性仍可继续补充。"],
            "disclaimer": "本报告由 AI 智能体自动生成，仅供参考，最终评定以培训导师意见为准。",
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
