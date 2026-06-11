import os
import shutil
import tempfile
import unittest
from io import BytesIO

from scoring_app import create_app


class LeadershipModelingTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="demo2-leadership-")
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

        self.app = create_app()
        self.app.testing = True
        self.client = self.app.test_client()
        self._register_user()

    def tearDown(self):
        for key, value in self.env_backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_full_leadership_modeling_flow_and_exports(self):
        create_response = self.client.post(
            "/api/leadership-models",
            data={
                "company_name": "中集车辆",
                "industry": "高端制造",
                "business_type": "商用车制造与供应链协同",
                "company_size": "上市公司，5000人以上",
                "strategy_keywords": "星链计划\n海外增长\n数字化运营",
                "management_pains": "跨部门协同慢\n库存数据割裂\n一线管理者战略承接不足",
                "target_group": "中层管理者",
                "role_positioning": "承接战略、带团队解决复杂经营问题的关键管理层。",
                "excellent_behaviors": "主动拆解目标\n跨部门推动资源\n用数据复盘结果",
                "differentiation_summary": "优秀管理者能把战略语言转化为可执行项目。",
                "standard_refs": "美世领导力模型\nDDI领导力模型",
                "source_file": (
                    BytesIO(
                        "战略文档强调星链计划、ERP库存数据、跨部门协同和高绩效管理者画像。".encode(
                            "utf-8"
                        )
                    ),
                    "strategy.txt",
                ),
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(create_response.status_code, 201)
        payload = create_response.get_json()
        model_id = payload["model_id"]
        self.assertEqual(payload["current_step"], "dimensions")
        self.assertEqual(payload["context"]["company_name"], "中集车辆")
        self.assertEqual(payload["workflow"][0]["key"], "context")
        self.assertEqual(payload["workflow"][0]["state"], "done")
        self.assertEqual(payload["workflow"][1]["state"], "available")

        dimensions_response = self.client.post(
            "/api/leadership-models/{}/dimensions:generate".format(model_id)
        )
        self.assertEqual(dimensions_response.status_code, 200)
        payload = dimensions_response.get_json()
        self.assertEqual(payload["workflow"][1]["state"], "pending-review")
        self.assertGreaterEqual(len(payload["dimensions"]), 4)
        self.assertLessEqual(len(payload["dimensions"]), 8)
        first_dimension = payload["dimensions"][0]
        self.assertIn("sources", first_dimension)
        self.assertTrue(first_dimension["sources"])

        save_dimensions = self.client.patch(
            "/api/leadership-models/{}/dimensions".format(model_id),
            json={"dimensions": payload["dimensions"]},
        )
        self.assertEqual(save_dimensions.status_code, 200)
        self.assertEqual(save_dimensions.get_json()["workflow"][1]["state"], "done")
        self.assertEqual(save_dimensions.get_json()["workflow"][2]["state"], "available")

        descriptions_response = self.client.post(
            "/api/leadership-models/{}/descriptions:generate".format(model_id)
        )
        self.assertEqual(descriptions_response.status_code, 200)
        descriptions_payload = descriptions_response.get_json()
        self.assertEqual(descriptions_payload["workflow"][2]["state"], "pending-review")
        self.assertEqual(
            len(descriptions_payload["descriptions"]),
            len(descriptions_payload["dimensions"]),
        )
        self.assertIn("quality_status", descriptions_payload["descriptions"][0])

        save_descriptions = self.client.patch(
            "/api/leadership-models/{}/descriptions".format(model_id),
            json={"descriptions": descriptions_payload["descriptions"]},
        )
        self.assertEqual(save_descriptions.status_code, 200)
        self.assertEqual(save_descriptions.get_json()["workflow"][3]["state"], "available")

        anchors_response = self.client.post(
            "/api/leadership-models/{}/anchors:generate".format(model_id)
        )
        self.assertEqual(anchors_response.status_code, 200)
        anchors_payload = anchors_response.get_json()
        self.assertEqual(anchors_payload["workflow"][3]["state"], "pending-review")
        first_anchor = anchors_payload["anchors"][0]
        self.assertTrue(first_anchor["excellent"])
        self.assertTrue(first_anchor["pass"])
        self.assertTrue(first_anchor["negative"])

        save_anchors = self.client.patch(
            "/api/leadership-models/{}/anchors".format(model_id),
            json={"anchors": anchors_payload["anchors"]},
        )
        self.assertEqual(save_anchors.status_code, 200)
        saved_payload = save_anchors.get_json()
        self.assertEqual(saved_payload["current_step"], "export")
        self.assertEqual(saved_payload["workflow"][4]["state"], "available")
        self.assertIn("docx", saved_payload["export_urls"])
        self.assertIn("pdf", saved_payload["export_urls"])

        list_response = self.client.get("/api/leadership-models")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(list_response.get_json()["items"][0]["model_id"], model_id)

        docx_response = self.client.get(
            "/api/leadership-models/{}/export?format=docx".format(model_id)
        )
        self.assertEqual(docx_response.status_code, 200)
        self.assertIn(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            docx_response.headers["Content-Type"],
        )
        self.assertTrue(docx_response.get_data().startswith(b"PK"))

        pdf_response = self.client.get(
            "/api/leadership-models/{}/export?format=pdf".format(model_id)
        )
        self.assertEqual(pdf_response.status_code, 200)
        self.assertEqual(pdf_response.headers["Content-Type"], "application/pdf")
        self.assertTrue(pdf_response.get_data().startswith(b"%PDF"))

    def test_leadership_modeling_requires_auth(self):
        self.client.post("/api/auth/logout")

        self.assertEqual(self.client.get("/api/leadership-models").status_code, 401)
        self.assertEqual(self.client.post("/api/leadership-models").status_code, 401)

    def test_conversational_flow_candidates_regeneration_and_compatibility(self):
        create_response = self.client.post(
            "/api/leadership-models",
            data={"company_name": "中集车辆"},
            content_type="multipart/form-data",
        )
        self.assertEqual(create_response.status_code, 201)
        payload = create_response.get_json()
        model_id = payload["model_id"]
        self.assertEqual(payload["current_step"], "context")

        upload_response = self.client.post(
            "/api/leadership-models/{}/source-files".format(model_id),
            data={
                "source_file": (
                    BytesIO("战略文档包含ERP库存数据、跨部门协同和海外增长。".encode("utf-8")),
                    "strategy.txt",
                )
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(upload_response.status_code, 200)
        self.assertIn("ERP", upload_response.get_json()["context"]["document_keywords"])

        for field, message in [
            ("industry", "高端制造与商用车供应链"),
            ("company_size", "上市公司，5000人以上"),
            ("strategy_keywords", "星链计划；海外增长；数字化运营"),
            ("management_pains", "跨部门协同慢；库存数据割裂"),
            ("target_group", "中层管理者"),
            ("excellent_behaviors", "主动拆解目标；跨部门推动资源；用数据复盘结果"),
        ]:
            message_response = self.client.post(
                "/api/leadership-models/{}/context/message".format(model_id),
                json={"field": field, "message": message},
            )
            self.assertEqual(message_response.status_code, 200)
            self.assertIn("assistant_message", message_response.get_json())

        confirm_response = self.client.post(
            "/api/leadership-models/{}/context/confirm".format(model_id)
        )
        self.assertEqual(confirm_response.status_code, 200)
        confirmed = confirm_response.get_json()
        self.assertEqual(confirmed["current_step"], "dimensions")
        self.assertIn("dimension_candidates", confirmed)
        self.assertGreaterEqual(len(confirmed["dimension_candidates"]["recommended"]), 4)
        self.assertGreaterEqual(len(confirmed["dimension_candidates"]["alternatives"]), 5)

        selected_dimensions = confirmed["dimension_candidates"]["recommended"][:3]
        save_dimensions = self.client.patch(
            "/api/leadership-models/{}/dimensions".format(model_id),
            json={"dimensions": selected_dimensions},
        )
        self.assertEqual(save_dimensions.status_code, 200)
        self.assertEqual(len(save_dimensions.get_json()["dimensions"]), 3)

        descriptions_response = self.client.post(
            "/api/leadership-models/{}/descriptions:generate".format(model_id)
        )
        self.assertEqual(descriptions_response.status_code, 200)
        descriptions_payload = descriptions_response.get_json()
        first_description = descriptions_payload["descriptions"][0]
        self.assertIn("description", first_description)
        self.assertIn("quality_check", first_description)

        dimension_id = first_description["dimension_id"]
        regenerate_description = self.client.post(
            "/api/leadership-models/{}/descriptions/{}:regenerate".format(model_id, dimension_id),
            json={"direction": "更强调ERP库存数据和跨部门推进"},
        )
        self.assertEqual(regenerate_description.status_code, 200)
        regenerated_description = regenerate_description.get_json()["descriptions"][0]
        self.assertIn("ERP库存数据", regenerated_description["description"])

        save_descriptions = self.client.patch(
            "/api/leadership-models/{}/descriptions".format(model_id),
            json={"descriptions": regenerate_description.get_json()["descriptions"]},
        )
        self.assertEqual(save_descriptions.status_code, 200)

        anchors_response = self.client.post(
            "/api/leadership-models/{}/anchors:generate".format(model_id)
        )
        self.assertEqual(anchors_response.status_code, 200)
        anchors_payload = anchors_response.get_json()
        first_anchor = anchors_payload["anchors"][0]
        self.assertIn("anchors", first_anchor)
        self.assertTrue(first_anchor["anchors"]["standard"])
        self.assertTrue(first_anchor["anchors"]["below"])
        self.assertTrue(first_anchor["pass"])
        self.assertTrue(first_anchor["negative"])

        anchor_id = first_anchor["anchors"]["standard"][0]["id"]
        regenerate_anchor = self.client.post(
            "/api/leadership-models/{}/anchors/{}:regenerate".format(model_id, anchor_id),
            json={"direction": "补充跨部门周会节奏"},
        )
        self.assertEqual(regenerate_anchor.status_code, 200)
        updated_anchor = regenerate_anchor.get_json()["anchors"][0]["anchors"]["standard"][0]
        self.assertIn("跨部门周会", updated_anchor["text"])

    def test_leadership_prompt_contains_mvp_contract(self):
        from scoring_app.leadership_prompts import build_stage_prompt

        prompt = build_stage_prompt(
            "anchors",
            {
                "context": {"target_group": "中层管理者"},
                "dimensions": [{"name": "战略承接", "definition": "承接战略"}],
                "descriptions": [{"dimension_id": 1, "core_requirement": "拆解战略"}],
            },
        )

        self.assertIn("4-8 个推荐维度", prompt)
        self.assertIn("5-10 个备选维度", prompt)
        self.assertIn("单一层级/群体", prompt)
        self.assertIn("行为动词开头", prompt)
        self.assertIn("优秀", prompt)
        self.assertIn("达标", prompt)
        self.assertIn("不达标", prompt)

    def _register_user(self):
        response = self.client.post(
            "/api/auth/register",
            json={
                "email": "leadership@example.com",
                "display_name": "Leadership User",
                "password": "Passw0rd!",
            },
        )
        self.assertEqual(response.status_code, 201)


if __name__ == "__main__":
    unittest.main()
