import re
import unittest
from unittest.mock import patch


class ScoringQualityTestCase(unittest.TestCase):
    def test_rich_wenguzhixin_keeps_specific_assignment_signals(self):
        from scoring_app.scoring import score_submission

        payload = self._score("温故知新", self._wenguzhixin_doc(), self._wenguzhixin_transcript())
        combined = self._combined_text(payload)

        expected = (
            "钢材发料",
            "星链计划",
            "RACI",
            "5WHY",
            "ERP库存数据",
            "38%",
            "75%",
            "80%",
            "52天",
            "46天",
            "语速偏快",
            "90天",
        )
        for signal in expected:
            self.assertIn(signal, combined)
        self._assert_clean_report_text(combined)

    def test_rich_action_learning_beats_low_information_case(self):
        from scoring_app.scoring import score_submission

        rich = self._score("行动学习-组织协同", self._action_org_doc(), self._action_org_transcript())
        weak = self._score(
            "行动学习-问题解决",
            self._low_information_doc(),
            self._low_information_transcript(),
        )
        rich_text = self._combined_text(rich)
        weak_text = self._combined_text(weak)

        for signal in (
            "七大协同障碍",
            "双计双考",
            "RACI",
            "情感账户",
            "ERP库存数据",
            "18天",
            "13天",
            "42%",
            "62%",
            "81%",
            "语速偏快",
        ):
            self.assertIn(signal, rich_text)
        self.assertGreaterEqual(rich["total_score"], 60.0)
        self.assertGreaterEqual(rich["total_score"] - weak["total_score"], 15.0)
        for missing in ("缺少具体案例", "缺少量化数据", "缺少责任分工", "缺少资源规划"):
            self.assertIn(missing, weak_text)
        self.assertNotIn("时间管理得分", weak["overall_comment"])
        self._assert_clean_report_text(rich_text + weak_text)

    def _score(self, report_type, document_text, transcript_text):
        from scoring_app.scoring import score_submission

        with patch("scoring_app.scoring.live_score_submission", side_effect=RuntimeError("mock")):
            return score_submission(
                report_type,
                document_text,
                transcript_text,
                {
                    "name": "质量测试学员",
                    "org": "测试组织",
                    "date": "2026-06-12",
                    "course_session": "第二次课 · 组织协同",
                    "note": "",
                    "pdf_filename": "quality.pdf",
                    "upload_path": "",
                    "document_preview": document_text[:800],
                },
            )

    def _combined_text(self, payload):
        parts = [payload["overall_comment"]] + payload["strengths"] + payload["improvements"]
        parts.extend(
            "{}\n{}".format(item["evidence"], item["comment"])
            for item in payload["dimensions"]
        )
        return "\n".join(parts)

    def _assert_clean_report_text(self, text):
        for generic in ("表现较强", "支撑充分", "建议补充证据", "已有可保留线索"):
            self.assertNotIn(generic, text)
        self.assertIsNone(re.search(r"[�ÃÂ]|鈥", text))

    def _wenguzhixin_doc(self):
        return (
            "标题：从钢材发料差异到真实成本闭环的复盘与立项。"
            "背景：钢材发料与ERP库存数据长期存在口径差异，影响真实成本核算，"
            "直接关联公司星链计划中的降本和透明经营目标，也是业务痛点。"
            "问题识别：用5WHY复盘发现根因不是录入，而是采购、仓库、生产、财务对发料完成定义不同。"
            "工具应用：用RACI明确生产经理日清确认、仓库主管ERP库存数据回写、财务差异复核、采购异常审批。"
            "行动结果：发料差异闭环率从38%提升到75%，第二轮达到80%；钢材发料异常处理周期从52天降至46天。"
            "复盘反思：个人失误是前期只盯数据，没有处理协同关系；通过ASTRAL复盘形成认知迭代。"
            "课题规划：下一步在90天内建设真实成本预警机制，包含差异分类、RACI表和月度看板。"
        )

    def _wenguzhixin_transcript(self):
        return (
            "现场先用PPT展示星链计划和钢材发料痛点，再说明5WHY和RACI工具。"
            "整体逻辑清晰，但前3分钟语速偏快，讲到38%到75%到80%和52天到46天时停顿不足。"
            "答辩能回应ERP库存数据作为切入口的原因，时间控制在8分钟30秒。"
        )

    def _action_org_doc(self):
        return (
            "标题：备件交付周期缩短的组织协同方案。"
            "业务痛点：备件交付平均周期为18天，调研30个订单后发现计划、采购、仓库、维修没有共同优先级。"
            "直面问题：拆成七大协同障碍，包括目标不一致、信息不透明、责任边界模糊、异常升级慢、数据口径不统一、互信不足和复盘缺失。"
            "创新构想：建立双计双考机制，每个紧急备件单绑定RACI分工。"
            "结构性方法：用5WHY定位根因，用RACI明确权责，用情感账户降低协作阻力。"
            "系统层面把ERP库存数据、供应商交期和维修停线损失放到同一张看板。"
            "计划：2周清理历史未闭环订单，4周完成分类规则，6周上线红黄绿看板，资源包括IT半个人月。"
            "结果验证：试点20个订单后，平均交付周期从18天降到13天，紧急单重复催办次数下降42%，维修满意度从62%提升到81%。"
        )

    def _action_org_transcript(self):
        return (
            "PPT按问题、根因、方案、结果、复盘五段展开，表达清晰。"
            "评委追问双计双考是否制造新KPI冲突，回答能补充RACI和情感账户设计。"
            "第6分钟后语速偏快，但能在18天降到13天、满意度62%到81%处做总结。总时长9分钟10秒。"
        )

    def _low_information_doc(self):
        return (
            "标题：提升运营效率的思考。"
            "部门目前有一些效率问题，大家都很忙，流程也比较复杂。"
            "我认为需要加强沟通，后续会进一步优化流程，推动大家形成合力。"
            "方案准备先开会讨论，再根据实际情况持续改进。"
            "反思方面，我觉得自己还需要提高管理能力，后续会多学习、多沟通、多总结。"
        )

    def _low_information_transcript(self):
        return (
            "汇报主要围绕流程优化展开，但没有说明具体案例、数据、责任分工和完成时间。"
            "评委追问目标值和资源需求，回答比较笼统，只说会继续沟通。时间约5分钟。"
        )
