import os
import shutil
import tempfile
import unittest

from scoring_app import create_app
from scoring_app.repository import create_user, store_score
from scoring_app.rules import REPORT_DEFINITIONS
from scoring_app.services.score_service import build_score_export


class ScoreExportFormatsTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="demo2-export-formats-")
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

        self.app = create_app()
        self.app.testing = True
        self.report_type = self._find_report_type("wg")
        self.score_id = "score-export-format-001"
        self.user_id = "user-export-001"
        create_user(
            self.user_id,
            "export@example.com",
            "Export User",
            "test-password-hash",
            "2026-05-25T09:30:00Z",
        )
        self.score_result = self._build_score_result(self.user_id, self.score_id)
        store_score(self.score_result)

    def tearDown(self):
        for key, value in self.env_backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_markdown_export_case(self):
        export_info = build_score_export(self.score_id, self.user_id, "md")

        self.assertEqual(export_info["mimetype"], "text/markdown; charset=utf-8")
        self.assertTrue(export_info["filename"].endswith(".md"))
        markdown = export_info["content"].decode("utf-8")
        self.assertIn(str(self.score_result["name"]), markdown)
        self.assertIn(str(self.score_result["report_type"]), markdown)
        self.assertIn(str(self.score_result["total_score"]), markdown)

        cached_export = build_score_export(self.score_id, self.user_id, "md")
        self.assertEqual(cached_export["content"], export_info["content"])

    def test_pdf_export_case(self):
        export_info = build_score_export(self.score_id, self.user_id, "pdf")

        self.assertEqual(export_info["mimetype"], "application/pdf")
        self.assertTrue(export_info["filename"].endswith(".pdf"))
        pdf_bytes = export_info["content"]
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        self.assertGreater(len(pdf_bytes), 1024)

        cached_export = build_score_export(self.score_id, self.user_id, "pdf")
        self.assertEqual(cached_export["content"], export_info["content"])

    def _find_report_type(self, definition_id):
        for report_type, definition in REPORT_DEFINITIONS.items():
            if definition["id"] == definition_id:
                return report_type
        raise AssertionError("Missing report definition id: {}".format(definition_id))

    def _build_score_result(self, user_id, score_id):
        definition = REPORT_DEFINITIONS[self.report_type]
        dimensions = definition["dimensions"]
        selected = [dimensions[0], dimensions[2], dimensions[4]]
        scores = [8.8, 8.1, 7.9]
        evidence = [
            "Document shows clear linkage between target, action, and outcome.",
            "Document explains why the topic matters to the organization.",
            "Transcript keeps the reporting sequence and key conclusions clear.",
        ]
        comments = [
            "This dimension is well supported and logically complete.",
            "This dimension has a clear target and strong business value.",
            "This dimension is clear, but it still needs more chain details.",
        ]

        return {
            "score_id": score_id,
            "user_id": user_id,
            "name": "Export Sample",
            "org": "Delivery Team",
            "report_type": self.report_type,
            "date": "2026-05-25",
            "note": "export-format-test",
            "pdf_filename": "report.pdf",
            "upload_path": "uploads/report.pdf",
            "document_preview": "Sample preview for export tests.",
            "transcript_present": True,
            "total_score": 84.2,
            "total_level": "优秀",
            "doc_average": 8.5,
            "audio_average": 7.9,
            "lowest_dimension": {"name": selected[-1]["name"], "score": scores[-1]},
            "overall_comment": "Overall performance is stable and the structure is clear.",
            "strengths": [
                "Strategic linkage is relatively strong.",
                "Topic value is explained clearly.",
            ],
            "improvements": [
                "The logical chain can still be strengthened.",
            ],
            "disclaimer": "本报告由 AI 智能体自动生成，仅供参考，最终评定以培训导师意见为准。",
            "created_at": "2026-05-25T10:00:00Z",
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
