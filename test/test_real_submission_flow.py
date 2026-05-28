import os
import shutil
import tempfile
import unittest

from scoring_app import create_app

from test.fixture_builder import (
    INPUT_ROOT,
    get_report_type_by_definition_id,
    write_real_fixture_files,
)


class RealSubmissionFlowTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="demo2-real-flow-")
        self.data_dir = os.path.join(self.temp_dir, "data")
        self.upload_dir = os.path.join(self.temp_dir, "uploads")
        self.env_keys = [
            "SCORING_APP_DATA_DIR",
            "SCORING_APP_UPLOAD_DIR",
            "SCORING_APP_DB_PATH",
            "SCORING_LLM_MODE",
        ]
        self.env_backup = {key: os.environ.get(key) for key in self.env_keys}
        os.environ["SCORING_APP_DATA_DIR"] = self.data_dir
        os.environ["SCORING_APP_UPLOAD_DIR"] = self.upload_dir
        os.environ["SCORING_APP_DB_PATH"] = os.path.join(self.data_dir, "scores.db")
        os.environ["SCORING_LLM_MODE"] = "mock"

        from scoring_app.markdown_export import build_markdown

        write_real_fixture_files(build_markdown)
        self.report_type = get_report_type_by_definition_id("wg")
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

    def test_real_fixture_submission_produces_result_history_and_exports(self):
        register_response = self.client.post(
            "/api/auth/register",
            json={
                "email": "real-flow@example.com",
                "display_name": "Real Flow",
                "password": "Passw0rd!",
            },
        )
        self.assertEqual(register_response.status_code, 201)

        with open(INPUT_ROOT / "real_submission_report.pdf", "rb") as pdf_file, open(
            INPUT_ROOT / "real_submission_transcript.txt", "rb"
        ) as transcript_file:
            response = self.client.post(
                "/api/score",
                data={
                    "name": "真实提交流程",
                    "org": "培训交付中心",
                    "report_type": self.report_type,
                    "course_session": "第二次课 · 组织协同",
                    "date": "2026-05-25",
                    "note": "真实样例接口测试",
                    "transcript": "",
                    "pdf_file": (pdf_file, "real_submission_report.pdf"),
                    "transcript_file": (transcript_file, "real_submission_transcript.txt"),
                },
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["score_id"])
        self.assertEqual(payload["scoring_mode"], "heuristic")
        self.assertTrue(payload["transcript_present"])
        self.assertGreaterEqual(len(payload["dimensions"]), 3)
        self.assertGreater(float(payload["total_score"]), 0.0)

        history_response = self.client.get("/api/scores")
        self.assertEqual(history_response.status_code, 200)
        history_items = history_response.get_json()["items"]
        self.assertEqual(len(history_items), 1)
        self.assertEqual(history_items[0]["score_id"], payload["score_id"])

        detail_response = self.client.get("/api/scores/{}".format(payload["score_id"]))
        self.assertEqual(detail_response.status_code, 200)
        detail_payload = detail_response.get_json()
        self.assertTrue(detail_payload["document_preview"])
        self.assertEqual(detail_payload["name"], "真实提交流程")

        markdown_response = self.client.get(
            "/api/scores/{}/export?format=md".format(payload["score_id"])
        )
        try:
            self.assertEqual(markdown_response.status_code, 200)
            self.assertIn("text/markdown", markdown_response.headers["Content-Type"])
            self.assertIn("真实提交流程", markdown_response.get_data(as_text=True))
        finally:
            markdown_response.close()

        pdf_response = self.client.get(
            "/api/scores/{}/export?format=pdf".format(payload["score_id"])
        )
        try:
            self.assertEqual(pdf_response.status_code, 200)
            self.assertEqual(pdf_response.headers["Content-Type"], "application/pdf")
            self.assertTrue(pdf_response.get_data().startswith(b"%PDF"))
        finally:
            pdf_response.close()


if __name__ == "__main__":
    unittest.main()
