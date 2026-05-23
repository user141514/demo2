REPORT_DEFINITIONS = {
    "温故知新": {
        "id": "wg",
        "name": "温故知新",
        "description": "个人汇报 · 10个子维度",
        "groups": [
            {"name": "温故·实战复盘", "weight": 55.0, "source": "文档"},
            {"name": "知新·课题立项", "weight": 25.0, "source": "文档"},
            {"name": "逻辑性与展现力", "weight": 20.0, "source": "录音转写"},
        ],
        "dimensions": [
            {
                "id": 1,
                "name": "战略链接与价值认知",
                "group": "温故·实战复盘",
                "group_weight": 55.0,
                "actual_weight": 5.5,
                "source_key": "document",
                "material_source": "文档",
                "focus": "战略理解深度",
                "keywords": ["战略", "目标", "业务", "价值", "支撑", "痛点", "任务"],
                "needs_numbers": False,
            },
            {
                "id": 2,
                "name": "知识融合与框架应用",
                "group": "温故·实战复盘",
                "group_weight": 55.0,
                "actual_weight": 8.25,
                "source_key": "document",
                "material_source": "文档",
                "focus": "工具应用精度",
                "keywords": ["框架", "模型", "工具", "方法", "认知", "协同", "解题"],
                "needs_numbers": False,
            },
            {
                "id": 3,
                "name": "行为的具体性与可观察性",
                "group": "温故·实战复盘",
                "group_weight": 55.0,
                "actual_weight": 5.5,
                "source_key": "document",
                "material_source": "文档",
                "focus": "行为颗粒度",
                "keywords": ["动作", "场景", "步骤", "协同", "节点", "执行", "具体"],
                "needs_numbers": False,
            },
            {
                "id": 4,
                "name": "行动的有效性与结果导向",
                "group": "温故·实战复盘",
                "group_weight": 55.0,
                "actual_weight": 5.5,
                "source_key": "document",
                "material_source": "文档",
                "focus": "结果验证强度",
                "keywords": ["结果", "成效", "提升", "闭环", "达成", "效率", "指标"],
                "needs_numbers": True,
            },
            {
                "id": 5,
                "name": "反思深刻性与真诚度",
                "group": "温故·实战复盘",
                "group_weight": 55.0,
                "actual_weight": 5.5,
                "source_key": "document",
                "material_source": "文档",
                "focus": "反思迭代高度",
                "keywords": ["反思", "复盘", "不足", "改进", "认知", "迭代", "收获"],
                "needs_numbers": False,
            },
            {
                "id": 6,
                "name": "课题的战略价值",
                "group": "知新·课题立项",
                "group_weight": 25.0,
                "actual_weight": 2.5,
                "source_key": "document",
                "material_source": "文档",
                "focus": "价值贡献度",
                "keywords": ["课题", "价值", "战略", "效能", "需求", "痛点", "组织"],
                "needs_numbers": False,
            },
            {
                "id": 7,
                "name": "目标与规划的前瞻性",
                "group": "知新·课题立项",
                "group_weight": 25.0,
                "actual_weight": 2.5,
                "source_key": "document",
                "material_source": "文档",
                "focus": "落地可行性",
                "keywords": ["目标", "规划", "里程碑", "资源", "计划", "推进", "实施"],
                "needs_numbers": False,
            },
            {
                "id": 8,
                "name": "创新与突破性",
                "group": "知新·课题立项",
                "group_weight": 25.0,
                "actual_weight": 1.25,
                "source_key": "document",
                "material_source": "文档",
                "focus": "方案差异化",
                "keywords": ["创新", "突破", "优化", "改善", "尝试", "新", "升级"],
                "needs_numbers": False,
            },
            {
                "id": 9,
                "name": "逻辑的严谨性和链条完整性",
                "group": "逻辑性与展现力",
                "group_weight": 20.0,
                "actual_weight": 2.0,
                "source_key": "transcript",
                "material_source": "录音转写",
                "focus": "系统思维",
                "keywords": ["首先", "其次", "最后", "因为", "所以", "问题", "结果", "闭环"],
                "needs_numbers": False,
            },
            {
                "id": 10,
                "name": "材料与汇报的展现力",
                "group": "逻辑性与展现力",
                "group_weight": 20.0,
                "actual_weight": 2.0,
                "source_key": "transcript",
                "material_source": "录音转写",
                "focus": "信息传递效率",
                "keywords": ["表达", "重点", "总结", "时间", "展示", "汇报", "听众"],
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
