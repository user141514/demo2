import os
import shutil
import tempfile
import unittest
from pathlib import Path

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
        index_html = index_response.get_data(as_text=True)
        self.assertIn("\u667a\u80fd\u4f53\u8bc4\u5206\u7cfb\u7edf", index_html)
        self.assertIn("AI SCORING \u00b7 \u7f8e\u592a\u54a8\u8be2", index_html)
        self.assertIn("\u8ba9\u6bcf\u4e00\u4efd\u6c47\u62a5\u90fd\u5f97\u5230\u4e13\u4e1a\u8bc4\u4ef7", index_html)
        self.assertIn("\u4e2d\u96c6\u8f66\u8f86 MBA \u4eba\u624d\u6c60\u57f9\u8bad\u9879\u76ee", index_html)
        self.assertNotIn("Cookie Session", index_html)
        self.assertNotIn("\u767b\u5f55\u6001\u53d7\u540c\u6e90 Cookie \u4fdd\u62a4", index_html)
        self.assertIn("对应课次", index_html)
        self.assertIn("name=\"course_session\"", index_html)
        self.assertIn("required", index_html)
        self.assertIn("第一次课 · 管理认知", index_html)
        self.assertIn("第二次课 · 组织协同", index_html)
        self.assertIn("第三次课 · 问题解决", index_html)
        self.assertIn("中期回顾工作坊", index_html)
        self.assertIn("<h1 id=\"result-title\">总体评价</h1>", index_html)
        self.assertIn("<div class=\"score-label\">分数/100</div>", index_html)
        self.assertLess(index_html.index("一级维度明细"), index_html.index("结论与建议"))
        self.assertNotIn("conclusion-card conclusion-summary", index_html)
        self.assertNotIn("id=\"result-comment\"", index_html)
        self.assertIn("conclusion-card conclusion-strengths", index_html)
        self.assertIn("conclusion-card conclusion-improvements", index_html)
        self.assertIn("<th>对应课次</th>", index_html)
        self.assertNotIn("<th>人工均分（待接入）</th>", index_html)

        app_js = (Path(__file__).resolve().parents[1] / "static" / "app.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("PUBLIC_REPORT_TYPE_KEYS", app_js)
        self.assertIn('key: "\u6e29\u6545\u77e5\u65b0"', app_js)
        self.assertIn('key: "\u884c\u52a8\u5b66\u4e60"', app_js)
        self.assertNotIn('key: "\u884c\u52a8\u5b66\u4e60-\u7ec4\u7ec7\u534f\u540c"', app_js)

        health_response = self.client.get("/api/health")
        self.assertEqual(health_response.status_code, 200)
        self.assertEqual(health_response.get_json()["status"], "ok")

        types_response = self.client.get("/api/report-types")
        self.assertEqual(types_response.status_code, 200)
        payload = types_response.get_json()
        self.assertIn("items", payload)
        self.assertTrue(payload["items"])
        report_type_keys = [item["key"] for item in payload["items"]]
        self.assertIn("行动学习-认知升级", report_type_keys)
        self.assertIn("行动学习-组织协同", report_type_keys)
        self.assertIn("行动学习-问题解决", report_type_keys)


if __name__ == "__main__":
    unittest.main()
