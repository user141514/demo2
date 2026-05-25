import os
import shutil
import tempfile
import unittest

from scoring_app import create_app


class AppShellTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="demo2-app-")
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
        self.client = self.app.test_client()

    def tearDown(self):
        for key, value in self.env_backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_index_health_and_report_types_routes_are_registered(self):
        index_response = self.client.get("/")
        self.assertEqual(index_response.status_code, 200)

        health_response = self.client.get("/api/health")
        self.assertEqual(health_response.status_code, 200)
        self.assertEqual(health_response.get_json()["status"], "ok")

        types_response = self.client.get("/api/report-types")
        self.assertEqual(types_response.status_code, 200)
        payload = types_response.get_json()
        self.assertIn("items", payload)
        self.assertTrue(payload["items"])


if __name__ == "__main__":
    unittest.main()
