import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from scoring_app import create_app

from test.fixture_builder import (
    INPUT_ROOT,
    get_report_type_by_definition_id,
    write_real_fixture_files,
)


class LiveProviderFallbackTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="demo2-live-fallback-")
        self.data_dir = os.path.join(self.temp_dir, "data")
        self.upload_dir = os.path.join(self.temp_dir, "uploads")
        self.env_keys = [
            "SCORING_APP_DATA_DIR",
            "SCORING_APP_UPLOAD_DIR",
            "SCORING_APP_DB_PATH",
            "SCORING_LLM_MODE",
            "OPENAI_API_KEY",
            "OPENAI_BASE_URL",
            "OPENAI_MODEL",
        ]
        self.env_backup = {key: os.environ.get(key) for key in self.env_keys}
        os.environ["SCORING_APP_DATA_DIR"] = self.data_dir
        os.environ["SCORING_APP_UPLOAD_DIR"] = self.upload_dir
        os.environ["SCORING_APP_DB_PATH"] = os.path.join(self.data_dir, "scores.db")
        os.environ["SCORING_LLM_MODE"] = "live"
        os.environ["OPENAI_API_KEY"] = "dummy-key"
        os.environ["OPENAI_BASE_URL"] = "https://example.invalid"
        os.environ["OPENAI_MODEL"] = "dummy-model"

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

    def test_live_provider_exception_falls_back_and_still_persists_history(self):
        register_response = self.client.post(
            "/api/auth/register",
            json={
                "email": "fallback@example.com",
                "display_name": "Fallback User",
                "password": "Passw0rd!",
            },
        )
        self.assertEqual(register_response.status_code, 201)

        with open(INPUT_ROOT / "real_submission_report.pdf", "rb") as pdf_file, open(
            INPUT_ROOT / "real_submission_transcript.txt", "rb"
        ) as transcript_file, patch(
            "scoring_app.scoring.live_score_submission",
            side_effect=RuntimeError("provider timeout"),
        ):
            response = self.client.post(
                "/api/score",
                data={
                    "name": "LLM 回退样例",
                    "org": "培训交付中心",
                    "report_type": self.report_type,
                    "course_session": "第二次课 · 组织协同",
                    "date": "2026-05-25",
                    "note": "live-provider-fallback",
                    "transcript": "",
                    "pdf_file": (pdf_file, "real_submission_report.pdf"),
                    "transcript_file": (transcript_file, "real_submission_transcript.txt"),
                },
                content_type="multipart/form-data",
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["scoring_mode"], "heuristic")
        self.assertEqual(payload["llm_provider"], "")
        self.assertEqual(payload["llm_model"], "")

        history_response = self.client.get("/api/scores")
        self.assertEqual(history_response.status_code, 200)
        self.assertEqual(len(history_response.get_json()["items"]), 1)


if __name__ == "__main__":
    unittest.main()
