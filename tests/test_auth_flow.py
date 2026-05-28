import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scoring_app import create_app
from scoring_app.repository import store_score


class AuthFlowTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="demo2-auth-")
        self.data_dir = os.path.join(self.temp_dir, "data")
        self.upload_dir = os.path.join(self.temp_dir, "uploads")
        self.env_keys = [
            "SCORING_APP_DATA_DIR",
            "SCORING_APP_UPLOAD_DIR",
            "SCORING_APP_DB_PATH",
            "SCORING_APP_SMTP_SUPPRESS_SEND",
            "SCORING_APP_EXPOSE_RESET_TOKENS",
            "SCORING_APP_APP_BASE_URL",
        ]
        self.env_backup = {key: os.environ.get(key) for key in self.env_keys}
        os.environ["SCORING_APP_DATA_DIR"] = self.data_dir
        os.environ["SCORING_APP_UPLOAD_DIR"] = self.upload_dir
        os.environ["SCORING_APP_DB_PATH"] = os.path.join(self.data_dir, "scores.db")
        os.environ["SCORING_APP_SMTP_SUPPRESS_SEND"] = "1"
        os.environ["SCORING_APP_EXPOSE_RESET_TOKENS"] = "1"
        os.environ["SCORING_APP_APP_BASE_URL"] = "http://localhost:5000"

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

    def test_register_login_me_logout_flow(self):
        register_response = self.client.post(
            "/api/auth/register",
            json={
                "email": "alice@example.com",
                "display_name": "Alice",
                "password": "Passw0rd!",
            },
        )
        self.assertEqual(register_response.status_code, 201)
        register_payload = register_response.get_json()
        self.assertEqual(register_payload["user"]["email"], "alice@example.com")
        self.assertEqual(register_payload["user"]["display_name"], "Alice")

        me_response = self.client.get("/api/auth/me")
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.get_json()["user"]["email"], "alice@example.com")

        logout_response = self.client.post("/api/auth/logout")
        self.assertEqual(logout_response.status_code, 200)

        me_after_logout = self.client.get("/api/auth/me")
        self.assertEqual(me_after_logout.status_code, 401)

        login_response = self.client.post(
            "/api/auth/login",
            json={"email": "alice@example.com", "password": "Passw0rd!"},
        )
        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(login_response.get_json()["user"]["display_name"], "Alice")

    def test_https_proxy_sets_secure_session_cookie(self):
        response = self.client.post(
            "/api/auth/register",
            json={
                "email": "secure@example.com",
                "display_name": "Secure User",
                "password": "Passw0rd!",
            },
            base_url="http://public.example.com",
            headers={"X-Forwarded-Proto": "https"},
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("Secure", response.headers.get("Set-Cookie", ""))

    def test_protected_endpoints_require_auth(self):
        self.assertEqual(self.client.post("/api/score").status_code, 401)
        self.assertEqual(self.client.post("/api/score/stream").status_code, 401)
        self.assertEqual(self.client.get("/api/scores").status_code, 401)
        self.assertEqual(self.client.get("/api/scores/missing-id").status_code, 401)
        self.assertEqual(
            self.client.get("/api/scores/missing-id/export?format=md").status_code,
            401,
        )

    def test_cross_user_history_detail_and_export_isolation(self):
        user_a = self.register_user("alice@example.com", "Alice")
        score_id = "score-user-a"
        store_score(self.make_score_result(user_a["user_id"], score_id, "Alice Score"))
        self.client.post("/api/auth/logout")

        self.register_user("bob@example.com", "Bob")

        history_response = self.client.get("/api/scores")
        self.assertEqual(history_response.status_code, 200)
        self.assertEqual(history_response.get_json()["items"], [])

        detail_response = self.client.get("/api/scores/{}".format(score_id))
        self.assertEqual(detail_response.status_code, 404)

        export_response = self.client.get(
            "/api/scores/{}/export?format=md".format(score_id)
        )
        self.assertEqual(export_response.status_code, 404)

    def test_forgot_password_and_reset_password_flow(self):
        self.register_user("alice@example.com", "Alice")
        self.client.post("/api/auth/logout")

        forgot_response = self.client.post(
            "/api/auth/forgot-password",
            json={"email": "alice@example.com"},
        )
        self.assertEqual(forgot_response.status_code, 200)

        outbox_path = Path(self.data_dir) / "mail_outbox.log"
        self.assertTrue(outbox_path.exists())
        records = [
            json.loads(line)
            for line in outbox_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertTrue(records)
        reset_token = records[-1]["reset_token"]

        reset_response = self.client.post(
            "/api/auth/reset-password",
            json={"token": reset_token, "password": "N3wPassw0rd!"},
        )
        self.assertEqual(reset_response.status_code, 200)

        failed_login = self.client.post(
            "/api/auth/login",
            json={"email": "alice@example.com", "password": "Passw0rd!"},
        )
        self.assertEqual(failed_login.status_code, 401)

        new_login = self.client.post(
            "/api/auth/login",
            json={"email": "alice@example.com", "password": "N3wPassw0rd!"},
        )
        self.assertEqual(new_login.status_code, 200)

    def test_first_registered_user_claims_legacy_scores(self):
        store_score(self.make_score_result(None, "legacy-score", "Legacy Score"))

        self.register_user("alice@example.com", "Alice")

        history_response = self.client.get("/api/scores")
        self.assertEqual(history_response.status_code, 200)
        items = history_response.get_json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["score_id"], "legacy-score")

    def register_user(self, email, display_name):
        response = self.client.post(
            "/api/auth/register",
            json={
                "email": email,
                "display_name": display_name,
                "password": "Passw0rd!",
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.get_json()["user"]

    def make_score_result(self, user_id, score_id, name):
        return {
            "score_id": score_id,
            "user_id": user_id,
            "name": name,
            "org": "Engineering",
            "report_type": "温故知新",
            "date": "2026-05-23",
            "note": "",
            "pdf_filename": "report.pdf",
            "upload_path": "uploads/report.pdf",
            "document_preview": "preview",
            "transcript_present": True,
            "total_score": 85.0,
            "total_level": "优秀",
            "doc_average": 8.5,
            "audio_average": 8.5,
            "lowest_dimension": {"name": "Dimension A", "score": 8.0},
            "overall_comment": "Overall good.",
            "strengths": ["Clear structure"],
            "improvements": ["More evidence"],
            "disclaimer": "Test disclaimer",
            "created_at": "2026-05-23T10:00:00Z",
            "dimensions": [
                {
                    "id": 1,
                    "name": "Dimension A",
                    "group_name": "Group 1",
                    "group_weight": 50.0,
                    "actual_weight": 5.0,
                    "material_source": "文档",
                    "score": 8.0,
                    "level_label": "优秀",
                    "evidence": "Evidence A",
                    "comment": "Comment A",
                },
                {
                    "id": 2,
                    "name": "Dimension B",
                    "group_name": "Group 1",
                    "group_weight": 50.0,
                    "actual_weight": 5.0,
                    "material_source": "录音转写",
                    "score": 9.0,
                    "level_label": "优秀",
                    "evidence": "Evidence B",
                    "comment": "Comment B",
                },
            ],
        }


if __name__ == "__main__":
    unittest.main()
