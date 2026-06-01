from pathlib import Path


REPORT_DEFINITIONS = {
    "温故知新": {
        "id": "wg",
        "name": "温故知新",
        "description": "个人汇报 · 5个评估维度",
        "groups": [
            {"name": "温故·实战复盘", "weight": 55.0, "source": "文档"},
            {"name": "知新·课题立项", "weight": 25.0, "source": "文档"},
            {"name": "逻辑性与展现力", "weight": 20.0, "source": "录音转写"},
        ],
        "dimensions": [
            {
                "id": 1,
                "name": "战略链接与知行合一",
                "group": "温故·实战复盘",
                "group_weight": 55.0,
                "actual_weight": 30.0,
                "source_key": "document",
                "material_source": "文档",
                "focus": "战略理解、知识应用、行为结果闭环",
                "keywords": ["战略", "星链计划", "MBA", "业务痛点", "价值", "工具", "框架", "RACI", "5WHY", "行动", "结果", "成效", "指标"],
                "needs_numbers": True,
            },
            {
                "id": 2,
                "name": "复盘深度与认知迭代",
                "group": "温故·实战复盘",
                "group_weight": 55.0,
                "actual_weight": 25.0,
                "source_key": "document",
                "material_source": "文档",
                "focus": "反思深度、认知变化、行为改进",
                "keywords": ["复盘", "反思", "不足", "短板", "假设", "认知", "迭代", "改变", "改进", "习惯", "收获"],
                "needs_numbers": False,
            },
            {
                "id": 3,
                "name": "课题价值与创新",
                "group": "知新·课题立项",
                "group_weight": 25.0,
                "actual_weight": 15.0,
                "source_key": "document",
                "material_source": "文档",
                "focus": "战略价值、业务痛点、创新突破",
                "keywords": ["课题", "战略", "痛点", "价值", "创新", "突破", "优化", "改进", "业务", "需求", "贡献"],
                "needs_numbers": True,
            },
            {
                "id": 4,
                "name": "规划可行与前瞻",
                "group": "知新·课题立项",
                "group_weight": 25.0,
                "actual_weight": 10.0,
                "source_key": "document",
                "material_source": "文档",
                "focus": "目标输出、里程碑、资源规划、可落地性",
                "keywords": ["目标", "输出物", "规划", "里程碑", "资源", "团队", "数据", "预算", "实施", "落地", "时间"],
                "needs_numbers": True,
            },
            {
                "id": 5,
                "name": "逻辑严谨与展现力",
                "group": "逻辑性与展现力",
                "group_weight": 20.0,
                "actual_weight": 20.0,
                "source_key": "transcript",
                "material_source": "录音转写",
                "focus": "逻辑闭环、材料呈现、现场表达、时间把控",
                "keywords": ["逻辑", "闭环", "结构", "主线", "重点", "PPT", "图表", "表达", "时间", "节奏", "汇报"],
                "needs_numbers": False,
            },
        ],
    },
    "行动学习": {
        "id": "xl",
        "name": "行动学习",
        "description": "作业汇报 · 7个子维度",
        "groups": [
            {"name": "作业评价", "weight": 80.0, "source": "文档"},
            {"name": "呈现效果评价", "weight": 20.0, "source": "录音转写"},
        ],
        "dimensions": [
            {
                "id": 1,
                "name": "直面问题",
                "group": "作业评价",
                "group_weight": 80.0,
                "actual_weight": 16.0,
                "source_key": "document",
                "material_source": "文档",
                "focus": "问题穿透深度",
                "keywords": ["问题", "痛点", "根因", "现状", "数据", "矛盾", "挑战"],
                "needs_numbers": True,
            },
            {
                "id": 2,
                "name": "创新构想",
                "group": "作业评价",
                "group_weight": 80.0,
                "actual_weight": 12.0,
                "source_key": "document",
                "material_source": "文档",
                "focus": "方案差异化价值",
                "keywords": ["创新", "构想", "突破", "优化", "新方案", "改进"],
                "needs_numbers": False,
            },
            {
                "id": 3,
                "name": "结构性方法",
                "group": "作业评价",
                "group_weight": 80.0,
                "actual_weight": 12.0,
                "source_key": "document",
                "material_source": "文档",
                "focus": "方案严谨性",
                "keywords": ["结构", "框架", "模型", "分析", "方法", "逻辑", "系统"],
                "needs_numbers": False,
            },
            {
                "id": 4,
                "name": "可操作性",
                "group": "作业评价",
                "group_weight": 80.0,
                "actual_weight": 24.0,
                "source_key": "document",
                "material_source": "文档",
                "focus": "落地可行性",
                "keywords": ["步骤", "执行", "资源", "落地", "责任", "推进", "计划"],
                "needs_numbers": False,
            },
            {
                "id": 5,
                "name": "表达清晰",
                "group": "呈现效果评价",
                "group_weight": 20.0,
                "actual_weight": 2.0,
                "source_key": "transcript",
                "material_source": "录音转写",
                "focus": "信息传递效率",
                "keywords": ["表达", "清晰", "重点", "结构", "总结", "层次", "说明"],
                "needs_numbers": False,
            },
            {
                "id": 6,
                "name": "回答问题",
                "group": "呈现效果评价",
                "group_weight": 20.0,
                "actual_weight": 1.0,
                "source_key": "transcript",
                "material_source": "录音转写",
                "focus": "互动响应质量",
                "keywords": ["提问", "回答", "问题", "补充", "回应", "说明"],
                "needs_numbers": False,
            },
            {
                "id": 7,
                "name": "时间管理",
                "group": "呈现效果评价",
                "group_weight": 20.0,
                "actual_weight": 1.0,
                "source_key": "transcript",
                "material_source": "录音转写",
                "focus": "流程管控能力",
                "keywords": ["时间", "分钟", "节奏", "安排", "控制", "进度"],
                "needs_numbers": True,
            },
        ],
    },
}


_ACTION_LEARNING_GROUPS = [
    {"name": "作业评价", "weight": 80.0, "source": "文档"},
    {"name": "呈现效果评价", "weight": 20.0, "source": "录音转写"},
]


_ACTION_LEARNING_DIMENSIONS = [
    (1, "直面问题", "作业评价", 80.0, 16.0, "document", "文档", "问题穿透深度", True),
    (2, "创新构想", "作业评价", 80.0, 12.0, "document", "文档", "方案差异化价值", False),
    (3, "结构性方法", "作业评价", 80.0, 12.0, "document", "文档", "方案严谨性", False),
    (4, "可操作性", "作业评价", 80.0, 24.0, "document", "文档", "落地可行性", False),
    (5, "表达清晰", "呈现效果评价", 20.0, 2.0, "transcript", "录音转写", "信息传递效率", False),
    (6, "回答问题", "呈现效果评价", 20.0, 1.0, "transcript", "录音转写", "互动响应质量", False),
    (7, "时间管理", "呈现效果评价", 20.0, 1.0, "transcript", "录音转写", "流程管控能力", True),
]


_ACTION_LEARNING_PRESENTATION_KEYWORDS = {
    "表达清晰": ["表达", "清晰", "重点", "结构", "层次", "PPT", "图表"],
    "回答问题": ["提问", "回答", "问题", "补充", "回应", "质疑"],
    "时间管理": ["时间", "分钟", "节奏", "安排", "控制", "进度"],
}


def _build_action_learning_course_definition(
    definition_id,
    name,
    description,
    knowledge_base_path,
    dimension_keywords,
):
    dimensions = []
    for (
        dim_id,
        dim_name,
        group,
        group_weight,
        actual_weight,
        source_key,
        material_source,
        focus,
        needs_numbers,
    ) in _ACTION_LEARNING_DIMENSIONS:
        dimensions.append(
            {
                "id": dim_id,
                "name": dim_name,
                "group": group,
                "group_weight": group_weight,
                "actual_weight": actual_weight,
                "source_key": source_key,
                "material_source": material_source,
                "focus": focus,
                "keywords": dimension_keywords.get(
                    dim_name, _ACTION_LEARNING_PRESENTATION_KEYWORDS.get(dim_name, [])
                ),
                "needs_numbers": needs_numbers,
            }
        )

    return {
        "id": definition_id,
        "name": name,
        "description": description,
        "knowledge_base_path": knowledge_base_path,
        "groups": list(_ACTION_LEARNING_GROUPS),
        "dimensions": dimensions,
    }


REPORT_DEFINITIONS.update(
    {
        "行动学习-认知升级": _build_action_learning_course_definition(
            "xl_course_1",
            "行动学习-认知升级",
            "第一次课程《趋势变局下MBA管理者的认知升级》专用",
            "知识库和评分标准/1.md",
            {
                "直面问题": [
                    "测评",
                    "商业综合推理",
                    "管理技能",
                    "管理个性",
                    "管理风格",
                    "职业锚",
                    "PEST",
                    "短板",
                    "瓶颈",
                ],
                "创新构想": [
                    "ASTRAL",
                    "IDP",
                    "轮岗",
                    "项目历练",
                    "AI",
                    "第三次创业",
                    "组织发展",
                ],
                "结构性方法": [
                    "IDP七步法",
                    "自我评估",
                    "环境评估",
                    "职业选择",
                    "确定目标",
                    "行动计划",
                    "7-2-1",
                    "现状",
                    "目标",
                    "能力",
                ],
                "可操作性": [
                    "行动步骤",
                    "时间节点",
                    "责任人",
                    "交付物",
                    "1年",
                    "2年",
                    "3年",
                    "资源",
                    "评价",
                    "反馈闭环",
                ],
            },
        ),
        "行动学习-组织协同": _build_action_learning_course_definition(
            "xl_course_2",
            "行动学习-组织协同",
            "第二次课程《组织协同》专用",
            "知识库和评分标准/2.md",
            {
                "直面问题": [
                    "七大协同障碍",
                    "组织分工",
                    "目标差异",
                    "部门墙",
                    "横向沟通",
                    "协作文化",
                    "流程",
                    "机制",
                    "案例",
                ],
                "创新构想": [
                    "服务协同",
                    "指导协同",
                    "管控协同",
                    "情感协同",
                    "RACI",
                    "双计双考",
                    "满意度",
                    "共同目标",
                ],
                "结构性方法": [
                    "七大障碍",
                    "RACI",
                    "流程优化",
                    "冲突处理",
                    "情感账户",
                    "组织",
                    "流程",
                    "目标",
                    "机制",
                    "影响力",
                    "聚焦",
                    "共创",
                    "对齐",
                    "闭环",
                ],
                "可操作性": [
                    "行动步骤",
                    "时间节点",
                    "责任人",
                    "交付物",
                    "1-2周",
                    "1-3个月",
                    "风险",
                    "里程碑",
                    "资源",
                ],
            },
        ),
        "行动学习-问题解决": _build_action_learning_course_definition(
            "xl_course_3",
            "行动学习-问题解决",
            "第三次课程《问题解决能力提升》专用",
            "知识库和评分标准/3.md",
            {
                "直面问题": [
                    "现象层",
                    "流程层",
                    "系统层",
                    "风险面",
                    "机会面",
                    "问题类型",
                    "边界",
                    "根因",
                ],
                "创新构想": [
                    "问题导向",
                    "创新思维",
                    "AI辅助",
                    "差异化",
                    "业务特性",
                    "价值提升",
                ],
                "结构性方法": [
                    "六步框架",
                    "发现",
                    "分析",
                    "目标",
                    "方案",
                    "执行",
                    "评估",
                    "模糊决策",
                    "PrOACT",
                    "5W2H",
                    "5Why",
                    "数据驱动",
                ],
                "可操作性": [
                    "行动步骤",
                    "时间节点",
                    "责任人",
                    "交付物",
                    "资源",
                    "风险",
                    "应对措施",
                    "阶段性目标",
                    "最终目标",
                ],
            },
        ),
    }
)


def load_knowledge_base_text(definition, max_chars=20000):
    knowledge_base_path = definition.get("knowledge_base_path")
    if not knowledge_base_path:
        return ""

    path = Path(__file__).resolve().parents[1] / knowledge_base_path
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""

    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n\n[评分标准内容已按长度截断]"


LEVEL_RULES = [
    (9.0, "卓越"),
    (7.5, "优秀"),
    (6.0, "良好"),
    (4.0, "合格"),
    (0.0, "不合格"),
]


TOTAL_LEVEL_RULES = [
    (90.0, "卓越"),
    (75.0, "优秀"),
    (60.0, "良好"),
    (40.0, "合格"),
    (0.0, "不合格"),
]


DISCLAIMER = "本报告由 AI 智能体自动生成，仅供参考，最终评定以培训导师意见为准。"


def get_report_definition(report_type):
    return REPORT_DEFINITIONS[report_type]


def score_to_level(score):
    if score is None:
        return None
    for threshold, label in LEVEL_RULES:
        if score >= threshold:
            return label
    return LEVEL_RULES[-1][1]


def total_to_level(score):
    for threshold, label in TOTAL_LEVEL_RULES:
        if score >= threshold:
            return label
    return TOTAL_LEVEL_RULES[-1][1]
