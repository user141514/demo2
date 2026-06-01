import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scoring_app import create_app
from scoring_app.rules import REPORT_DEFINITIONS

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
        self.project_root = Path(__file__).resolve().parents[1]
        self.dotenv_path = self.project_root / ".env"
        self.dotenv_backup = (
            self.dotenv_path.read_text(encoding="utf-8")
            if self.dotenv_path.exists()
            else None
        )
        self.dotenv_path.unlink(missing_ok=True)
        self.env_keys = [
            "SCORING_APP_DATA_DIR",
            "SCORING_APP_UPLOAD_DIR",
            "SCORING_APP_DB_PATH",
            "SCORING_LLM_MODE",
            "OPENAI_API_KEY",
            "OPENAI_BASE_URL",
            "OPENAI_MODEL",
            "SCORING_LLM_REPORT_TIMEOUT_SECONDS",
        ]
        self.env_backup = {key: os.environ.get(key) for key in self.env_keys}
        os.environ["SCORING_APP_DATA_DIR"] = self.data_dir
        os.environ["SCORING_APP_UPLOAD_DIR"] = self.upload_dir
        os.environ["SCORING_APP_DB_PATH"] = os.path.join(self.data_dir, "scores.db")
        os.environ["SCORING_LLM_MODE"] = "live"
        os.environ["OPENAI_API_KEY"] = "dummy-key"
        os.environ["OPENAI_BASE_URL"] = "https://example.invalid"
        os.environ["OPENAI_MODEL"] = "dummy-model"

        from scoring_app.llm_config import load_llm_settings

        load_llm_settings.cache_clear()
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
        from scoring_app.llm_config import load_llm_settings

        load_llm_settings.cache_clear()
        if self.dotenv_backup is None:
            self.dotenv_path.unlink(missing_ok=True)
        else:
            self.dotenv_path.write_text(self.dotenv_backup, encoding="utf-8")
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_default_live_provider_targets_deepseek_without_key(self):
        for key in (
            "SCORING_LLM_MODE",
            "OPENAI_API_KEY",
            "OPENAI_BASE_URL",
            "OPENAI_MODEL",
            "SCORING_LLM_REPORT_TIMEOUT_SECONDS",
        ):
            os.environ.pop(key, None)

        from scoring_app.llm_config import load_llm_settings

        load_llm_settings.cache_clear()
        settings = load_llm_settings()

        self.assertEqual(settings["llm_mode"], "live")
        self.assertEqual(settings["openai_base_url"], "https://api.deepseek.com")
        self.assertEqual(settings["openai_model"], "deepseek-v4-pro")
        self.assertEqual(settings["llm_report_timeout_seconds"], 25)
        self.assertFalse(settings["openai_api_key"])

    def test_dotenv_values_are_loaded_before_process_env_overrides(self):
        for key in (
            "SCORING_LLM_MODE",
            "OPENAI_API_KEY",
            "OPENAI_BASE_URL",
            "OPENAI_MODEL",
            "SCORING_LLM_REPORT_TIMEOUT_SECONDS",
        ):
            os.environ.pop(key, None)

        try:
            self.dotenv_path.write_text(
                "\n".join(
                    [
                        "SCORING_LLM_MODE=mock",
                        "OPENAI_API_KEY=dotenv-key",
                        "OPENAI_BASE_URL=https://dotenv.example",
                        "OPENAI_MODEL=dotenv-model",
                        "SCORING_LLM_REPORT_TIMEOUT_SECONDS=17",
                    ]
                ),
                encoding="utf-8",
            )
            os.environ["OPENAI_MODEL"] = "process-env-model"
            os.environ["SCORING_LLM_REPORT_TIMEOUT_SECONDS"] = "11"

            from scoring_app.llm_config import load_llm_settings

            load_llm_settings.cache_clear()
            settings = load_llm_settings()

            self.assertEqual(settings["llm_mode"], "mock")
            self.assertEqual(settings["openai_api_key"], "dotenv-key")
            self.assertEqual(settings["openai_base_url"], "https://dotenv.example")
            self.assertEqual(settings["openai_model"], "process-env-model")
            self.assertEqual(settings["llm_report_timeout_seconds"], 11)
        finally:
            self.dotenv_path.unlink(missing_ok=True)

    def test_live_prompt_requires_user_facing_evidence_explanation(self):
        from scoring_app.live_scoring import _build_system_prompt, _build_user_prompt

        system_prompt = _build_system_prompt()
        user_prompt = _build_user_prompt(
            self.report_type,
            REPORT_DEFINITIONS[self.report_type],
            "Document text with goals, actions, outcomes, and reflection. " * 4,
            "Transcript text with sequence, highlights, and conclusion. " * 4,
        )

        self.assertIn("not merely quote a raw excerpt", system_prompt)
        self.assertIn("consultant-report style", system_prompt)
        self.assertIn("正式评估报告", user_prompt)
        self.assertIn("优势亮点", user_prompt)
        self.assertIn("改进空间", user_prompt)
        self.assertIn("不要仅复制原文", user_prompt)
        self.assertIn("补充结构化反思页", user_prompt)

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
