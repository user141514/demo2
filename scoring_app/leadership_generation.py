import json
import re


STANDARD_LIBRARY_OPTIONS = [
    "美世领导力模型",
    "DDI领导力模型",
    "富兰克林柯维领导力模型",
    "情境领导力模型",
    "综合基线（内置）",
]


def parse_context_from_form(form, source_text):
    context = {
        "company_name": _field(form, "company_name"),
        "industry": _field(form, "industry"),
        "business_type": _field(form, "business_type"),
        "company_size": _field(form, "company_size"),
        "strategy_keywords": _list_field(form, "strategy_keywords"),
        "management_pains": _list_field(form, "management_pains"),
        "target_group": _field(form, "target_group"),
        "role_positioning": _field(form, "role_positioning"),
        "excellent_behaviors": _list_field(form, "excellent_behaviors"),
        "differentiation_summary": _field(form, "differentiation_summary"),
        "standard_refs": _list_field(form, "standard_refs") or ["综合基线（内置）"],
        "document_keywords": _document_keywords(source_text),
        "high_performance_traits": _high_performance_traits(form, source_text),
        "source_excerpt": (source_text or "")[:600],
    }
    context["missing_fields"] = [
        label
        for key, label in [
            ("industry", "行业/业务类型"),
            ("strategy_keywords", "当前战略重点"),
            ("management_pains", "主要管理痛点"),
            ("target_group", "建模对象层级/群体"),
            ("excellent_behaviors", "优秀管理者画像"),
        ]
        if not context.get(key)
    ]
    return context


def build_dimension_drafts(context):
    dimensions = [
        (
            "战略承接",
            "将公司战略重点转化为团队目标、关键任务和执行节奏，确保管理动作与组织方向同频。",
            "核心维度",
        ),
        (
            "组织协同",
            "围绕跨部门目标建立角色分工、沟通机制和冲突处理方式，推动复杂任务顺畅落地。",
            "核心维度",
        ),
        (
            "目标推进",
            "把业务痛点拆解为可衡量目标、里程碑和责任安排，并持续跟踪结果偏差。",
            "核心维度",
        ),
        (
            "数据决策",
            "基于业务数据识别问题、验证判断和复盘成效，减少经验式和拍脑袋式管理。",
            "重要维度",
        ),
        (
            "复盘迭代",
            "能从项目结果、个人失误和团队反馈中提炼规律，并转化为下一轮管理改进。",
            "重要维度",
        ),
        (
            "人才激发",
            "通过授权、辅导和反馈激活团队成员，让关键任务不只依赖个人推动。",
            "补充维度",
        ),
    ]
    return [
        {
            "id": index + 1,
            "name": name,
            "definition": definition,
            "sources": _sources_for_dimension(context, name),
            "priority": priority,
        }
        for index, (name, definition, priority) in enumerate(dimensions)
    ]


def build_description_drafts(context, dimensions):
    target_group = context.get("target_group") or "目标管理群体"
    rows = []
    for dimension in dimensions:
        name = dimension.get("name") or "未命名维度"
        rows.append(
            {
                "dimension_id": dimension.get("id"),
                "name": name,
                "core_requirement": (
                    "{group}需要在「{name}」上把战略、问题和团队动作连接起来，"
                    "形成可跟踪、可复盘的管理闭环。"
                ).format(group=target_group, name=name),
                "value_contribution": (
                    "该能力能帮助{company}减少跨部门损耗，提高关键任务推进质量，"
                    "并让优秀管理经验沉淀为组织能力。"
                ).format(company=context.get("company_name") or "企业"),
                "quality_status": _quality_status(context, dimension),
            }
        )
    return rows


def build_anchor_drafts(context, descriptions):
    rows = []
    for item in descriptions:
        name = item.get("name") or "未命名维度"
        rows.append(
            {
                "dimension_id": item.get("dimension_id"),
                "name": name,
                "excellent": [
                    "主动识别{pain}中的关键阻力，提前组织相关角色对齐目标、资源和时间表。".format(
                        pain=_first(context.get("management_pains"), "复杂任务")
                    ),
                    "持续跟踪{keyword}相关指标变化，并用数据复盘管理动作的有效性。".format(
                        keyword=_first(context.get("strategy_keywords"), name)
                    ),
                ],
                "pass": [
                    "拆解{keyword}相关任务，明确责任人、完成标准和阶段节点。".format(
                        keyword=_first(context.get("strategy_keywords"), name)
                    ),
                    "定期同步推进进展，对明显偏差及时提出调整建议。",
                    "记录项目过程中的关键问题和处理结果，形成可复用经验。",
                ],
                "negative": [
                    "面对跨部门分歧时只做被动传递，未推动责任边界和决策机制明确。",
                    "汇报结果时停留在过程描述，缺少指标、案例或复盘证据支撑。",
                    "发现目标偏差后等待上级安排，未主动提出补救动作。",
                ],
            }
        )
    return rows


def _field(form, key):
    return (form.get(key) or "").strip()


def _list_field(form, key):
    raw = (form.get(key) or "").strip()
    if not raw:
        return []
    if raw.startswith("["):
        try:
            payload = json.loads(raw)
            return [str(item).strip() for item in payload if str(item).strip()]
        except Exception:
            pass
    return [
        item.strip()
        for item in re.split(r"[\n,，;；、]+", raw)
        if item and item.strip()
    ]


def _document_keywords(source_text):
    text = source_text or ""
    candidates = [
        "战略",
        "协同",
        "数字化",
        "ERP",
        "库存",
        "客户",
        "成本",
        "增长",
        "人才",
        "复盘",
        "绩效",
        "跨部门",
        "高绩效",
    ]
    found = [item for item in candidates if item.lower() in text.lower()]
    return found[:10]


def _high_performance_traits(form, source_text):
    behaviors = _list_field(form, "excellent_behaviors")
    if behaviors:
        return behaviors[:6]
    if source_text:
        return ["能从上传材料中提炼战略重点", "能围绕业务痛点推动协同", "能用结果反馈改进管理动作"]
    return []


def _sources_for_dimension(context, dimension_name):
    sources = []
    keyword = _first(context.get("strategy_keywords") or context.get("document_keywords"), "")
    if keyword:
        sources.append(
            {
                "type": "战略映射",
                "text": "结合「{}」判断该维度需要承接业务方向。".format(keyword),
            }
        )
    ref = _first(context.get("standard_refs"), "综合基线（内置）")
    sources.append({"type": "标准库参照", "text": "参考{}的通用领导力框架。".format(ref)})
    behavior = _first(context.get("excellent_behaviors"), "")
    if behavior:
        sources.append(
            {
                "type": "访谈归纳",
                "text": "用户提到「{}」，可归入{}。".format(behavior, dimension_name),
            }
        )
    if not sources:
        sources.append({"type": "信息缺口", "text": "材料不足，需补充战略、痛点或优秀行为证据。"})
    return sources


def _quality_status(context, dimension):
    issues = []
    if not context.get("target_group"):
        issues.append("缺少单一层级/群体定位")
    if not dimension.get("sources"):
        issues.append("缺少来源依据")
    return {"status": "review" if issues else "passed", "issues": issues}


def _first(items, fallback):
    if isinstance(items, list) and items:
        return str(items[0])
    return fallback
