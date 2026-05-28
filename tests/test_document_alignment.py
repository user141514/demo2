import unittest
from pathlib import Path

from scoring_app.rules import DISCLAIMER, LEVEL_RULES, REPORT_DEFINITIONS, TOTAL_LEVEL_RULES
from scoring_app.live_scoring import _build_user_prompt


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DocumentAlignmentTestCase(unittest.TestCase):
    def test_report_definitions_match_original_spec(self):
        expected = {
            "温故知新": {
                "groups": [
                    ("温故·实战复盘", 55.0, "文档"),
                    ("知新·课题立项", 25.0, "文档"),
                    ("逻辑性与展现力", 20.0, "录音转写"),
                ],
                "dimensions": [
                    ("战略链接与价值认知", 5.5, "文档"),
                    ("知识融合与框架应用", 8.25, "文档"),
                    ("行为的具体性与可观察性", 5.5, "文档"),
                    ("行动的有效性与结果导向", 5.5, "文档"),
                    ("反思深刻性与真诚度", 5.5, "文档"),
                    ("课题的战略价值", 2.5, "文档"),
                    ("目标与规划的前瞻性", 2.5, "文档"),
                    ("创新与突破性", 1.25, "文档"),
                    ("逻辑的严谨性和链条完整性", 2.0, "录音转写"),
                    ("材料与汇报的展现力", 2.0, "录音转写"),
                ],
            },
            "行动学习": {
                "groups": [
                    ("作业评价", 80.0, "文档"),
                    ("呈现效果评价", 20.0, "录音转写"),
                ],
                "dimensions": [
                    ("直面问题", 16.0, "文档"),
                    ("创新构想", 12.0, "文档"),
                    ("结构性方法", 12.0, "文档"),
                    ("可操作性", 24.0, "文档"),
                    ("表达清晰", 2.0, "录音转写"),
                    ("回答问题", 1.0, "录音转写"),
                    ("时间管理", 1.0, "录音转写"),
                ],
            },
            "行动学习-认知升级": {
                "groups": [
                    ("作业评价", 80.0, "文档"),
                    ("呈现效果评价", 20.0, "录音转写"),
                ],
                "dimensions": [
                    ("直面问题", 16.0, "文档"),
                    ("创新构想", 12.0, "文档"),
                    ("结构性方法", 12.0, "文档"),
                    ("可操作性", 24.0, "文档"),
                    ("表达清晰", 2.0, "录音转写"),
                    ("回答问题", 1.0, "录音转写"),
                    ("时间管理", 1.0, "录音转写"),
                ],
            },
            "行动学习-组织协同": {
                "groups": [
                    ("作业评价", 80.0, "文档"),
                    ("呈现效果评价", 20.0, "录音转写"),
                ],
                "dimensions": [
                    ("直面问题", 16.0, "文档"),
                    ("创新构想", 12.0, "文档"),
                    ("结构性方法", 12.0, "文档"),
                    ("可操作性", 24.0, "文档"),
                    ("表达清晰", 2.0, "录音转写"),
                    ("回答问题", 1.0, "录音转写"),
                    ("时间管理", 1.0, "录音转写"),
                ],
            },
            "行动学习-问题解决": {
                "groups": [
                    ("作业评价", 80.0, "文档"),
                    ("呈现效果评价", 20.0, "录音转写"),
                ],
                "dimensions": [
                    ("直面问题", 16.0, "文档"),
                    ("创新构想", 12.0, "文档"),
                    ("结构性方法", 12.0, "文档"),
                    ("可操作性", 24.0, "文档"),
                    ("表达清晰", 2.0, "录音转写"),
                    ("回答问题", 1.0, "录音转写"),
                    ("时间管理", 1.0, "录音转写"),
                ],
            },
        }

        self.assertEqual(set(REPORT_DEFINITIONS), set(expected))

        for report_type, report_expectation in expected.items():
            definition = REPORT_DEFINITIONS[report_type]
            actual_groups = [
                (group["name"], group["weight"], group["source"])
                for group in definition["groups"]
            ]
            actual_dimensions = [
                (
                    dimension["name"],
                    dimension["actual_weight"],
                    dimension["material_source"],
                )
                for dimension in definition["dimensions"]
            ]
            self.assertEqual(actual_groups, report_expectation["groups"])
            self.assertEqual(actual_dimensions, report_expectation["dimensions"])

    def test_scoring_anchors_and_disclaimer_match_original_spec(self):
        self.assertEqual(
            LEVEL_RULES,
            [
                (9.0, "卓越"),
                (7.5, "优秀"),
                (6.0, "良好"),
                (4.0, "合格"),
                (0.0, "不合格"),
            ],
        )
        self.assertEqual(
            TOTAL_LEVEL_RULES,
            [
                (90.0, "卓越"),
                (75.0, "优秀"),
                (60.0, "良好"),
                (40.0, "合格"),
                (0.0, "不合格"),
            ],
        )
        self.assertEqual(
            DISCLAIMER,
            "本报告由 AI 智能体自动生成，仅供参考，最终评定以培训导师意见为准。",
        )

    def test_course_specific_action_learning_definitions_use_knowledge_base(self):
        expected = {
            "行动学习-认知升级": ("xl_course_1", "知识库和评分标准/1.md", "ASTRAL领导力模型"),
            "行动学习-组织协同": ("xl_course_2", "知识库和评分标准/2.md", "七大协同障碍根源"),
            "行动学习-问题解决": ("xl_course_3", "知识库和评分标准/3.md", "根源拆解三层模型"),
        }

        for report_type, (definition_id, rubric_path, marker) in expected.items():
            with self.subTest(report_type=report_type):
                definition = REPORT_DEFINITIONS[report_type]
                self.assertEqual(definition["id"], definition_id)
                self.assertEqual(definition["knowledge_base_path"], rubric_path)
                rubric_text = (PROJECT_ROOT / rubric_path).read_text(encoding="utf-8")
                self.assertIn(marker, rubric_text)

                prompt = _build_user_prompt(
                    report_type,
                    definition,
                    "这是一份用于测试的汇报材料，内容包含具体问题、解决方案、行动计划与评估反馈。" * 20,
                    "",
                )
                self.assertIn(marker, prompt)
                self.assertIn("课程专用评分标准", prompt)


if __name__ == "__main__":
    unittest.main()
