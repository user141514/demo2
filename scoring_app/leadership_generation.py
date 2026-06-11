import json
import re

from .leadership_contract import (
    context_summary,
    missing_context_fields,
    normalize_anchor,
    normalize_description,
    normalize_dimension_candidates,
    set_context_field,
)


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
    context["missing_fields"] = missing_context_fields(context)
    context["context_summary"] = context_summary(context)
    return context


def apply_context_message(context, field, message):
    field = field or _next_context_field(context)
    updated = set_context_field(context, field, message)
    conversation = list(updated.get("conversation") or [])
    conversation.append({"role": "user", "field": field, "content": str(message or "").strip()})
    next_field = _next_context_field(updated)
    assistant_message = (
        "已记录「{}」。{}".format(_field_label(field), _question_for_field(next_field))
        if next_field
        else "关键信息已基本齐备，请确认摘要后生成领导力维度。"
    )
    conversation.append({"role": "assistant", "content": assistant_message})
    updated["conversation"] = conversation[-24:]
    updated["collection_progress"] = _collection_progress(updated)
    updated["context_summary"] = context_summary(updated)
    return updated, assistant_message, next_field


def merge_source_text(context, source_text, filename):
    updated = dict(context or {})
    keywords = _document_keywords(source_text)
    existing_keywords = updated.get("document_keywords") or []
    merged_keywords = list(dict.fromkeys(existing_keywords + keywords))
    updated["document_keywords"] = merged_keywords[:12]
    excerpts = [item for item in [updated.get("source_excerpt"), (source_text or "")[:600]] if item]
    updated["source_excerpt"] = "\n".join(excerpts)[-1200:]
    source_files = list(updated.get("source_files") or [])
    source_files.append({"filename": filename, "keywords": keywords})
    updated["source_files"] = source_files[-10:]
    updated["context_summary"] = context_summary(updated)
    return updated


def build_dimension_candidates(context):
    recommended = build_dimension_drafts(context)
    alternatives = [
        _dimension(
            101,
            "客户洞察",
            "从客户场景、需求变化和服务反馈中识别机会，并转化为团队改进任务。",
            "supplementary",
            context,
            "用于补充外部市场和客户视角。",
        ),
        _dimension(
            102,
            "变革推动",
            "面对流程、技术或组织调整时，能拆解阻力、争取资源并推动团队完成转型动作。",
            "important",
            context,
            "适合数字化、组织变革或增长压力较强的场景。",
        ),
        _dimension(
            103,
            "风险预判",
            "在项目推进前识别质量、成本、交付和协同风险，并设置预警与补救机制。",
            "important",
            context,
            "用于强化复杂经营任务的前置管理。",
        ),
        _dimension(
            104,
            "文化共识",
            "将组织价值观转化为团队协作方式、评价标准和日常管理行为。",
            "supplementary",
            context,
            "适合组织文化整合或跨区域团队管理。",
        ),
        _dimension(
            105,
            "资源整合",
            "围绕关键任务识别内部外部资源，明确投入优先级并形成协同安排。",
            "important",
            context,
            "用于补充跨部门、跨区域和跨职能资源调度能力。",
        ),
    ]
    return normalize_dimension_candidates({"recommended": recommended, "alternatives": alternatives})


def build_dimension_drafts(context):
    return [
        _dimension(1, "战略承接", "将公司战略重点转化为团队目标、关键任务和执行节奏，确保管理动作与组织方向同频。", "core", context, "直接承接企业战略和目标拆解要求。"),
        _dimension(2, "组织协同", "围绕跨部门目标建立角色分工、沟通机制和冲突处理方式，推动复杂任务顺畅落地。", "core", context, "回应跨部门协同、责任边界和资源联动痛点。"),
        _dimension(3, "目标推进", "把业务痛点拆解为可衡量目标、里程碑和责任安排，并持续跟踪结果偏差。", "core", context, "保证管理者把问题转化为可执行项目。"),
        _dimension(4, "数据决策", "基于业务数据识别问题、验证判断和复盘成效，减少经验式和拍脑袋式管理。", "important", context, "强化ERP、库存、绩效等经营数据的使用。"),
        _dimension(5, "复盘迭代", "从项目结果、个人失误和团队反馈中提炼规律，并转化为下一轮管理改进。", "important", context, "让高绩效经验沉淀为可复制方法。"),
        _dimension(6, "人才激发", "通过授权、辅导和反馈激活团队成员，让关键任务不只依赖个人推动。", "supplementary", context, "补足目标层级带团队和培养人的要求。"),
    ]


def build_description_drafts(context, dimensions):
    target_group = context.get("target_group") or "目标管理群体"
    rows = []
    for dimension in dimensions:
        name = dimension.get("name") or "未命名维度"
        description = "{group}围绕「{name}」拆解战略任务、协同关键角色，并用结果数据复盘管理动作。".format(
            group=target_group,
            name=name,
        )
        rows.append(
            normalize_description(
                {
                    "dimension_id": dimension.get("id"),
                    "dimension_name": name,
                    "description": description,
                    "core_requirement": description,
                    "value_contribution": "帮助{}减少协同损耗，提升关键任务推进质量。".format(
                        context.get("company_name") or "企业"
                    ),
                    "quality_check": _quality_check(context, dimension),
                },
                dimension,
            )
        )
    return rows


def build_anchor_drafts(context, descriptions):
    rows = []
    for item in descriptions:
        name = item.get("dimension_name") or item.get("name") or "未命名维度"
        rows.append(
            normalize_anchor(
                {
                    "dimension_id": item.get("dimension_id"),
                    "dimension_name": name,
                    "anchors": {
                        "excellent": [
                            "识别{pain}中的关键阻力，提前组织相关角色对齐目标、资源和时间表。".format(
                                pain=_first(context.get("management_pains"), "复杂任务")
                            ),
                            "跟踪{keyword}相关指标变化，并用数据复盘管理动作的有效性。".format(
                                keyword=_first(context.get("strategy_keywords"), name)
                            ),
                        ],
                        "standard": [
                            "拆解{keyword}相关任务，明确责任人、完成标准和阶段节点。".format(
                                keyword=_first(context.get("strategy_keywords"), name)
                            ),
                            "同步推进进展，对明显偏差及时提出调整建议。",
                            "记录项目过程中的关键问题和处理结果，形成可复用经验。",
                        ],
                        "below": [
                            "传递跨部门分歧但未推动责任边界和决策机制明确。",
                            "汇报结果停留在过程描述，缺少指标、案例或复盘证据支撑。",
                            "等待上级安排目标偏差处理，未提出补救动作。",
                        ],
                    },
                }
            )
        )
    return rows


def build_single_description_draft(context, dimension, direction):
    signal = _direction_signal(direction) or _first(context.get("document_keywords"), "")
    phrase = "，并围绕{}补充判断依据".format(signal) if signal else ""
    return normalize_description(
        {
            "dimension_id": dimension.get("id"),
            "dimension_name": dimension.get("name"),
            "description": "{}需要在「{}」中拆解任务、协同资源、追踪结果{}。".format(
                context.get("target_group") or "目标管理群体",
                dimension.get("name") or "该维度",
                phrase,
            ),
            "quality_check": _quality_check(context, dimension),
        },
        dimension,
    )


def build_single_anchor_text(level, direction):
    signal = _direction_signal(direction) or "关键任务"
    templates = {
        "excellent": "设计{}的前置协同方案，并用阶段结果校验资源投入有效性。",
        "standard": "组织{}，同步责任人、时间表和阶段风险。",
        "below": "汇报{}停留在现象描述，未明确责任边界和后续动作。",
    }
    return templates.get(level, templates["standard"]).format(signal)


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


def _dimension(dim_id, name, definition, priority, context, rationale):
    return {
        "id": dim_id,
        "name": name,
        "definition": definition,
        "source_refs": _source_refs_for_dimension(context, name),
        "priority": priority,
        "rationale": rationale,
    }


def _source_refs_for_dimension(context, dimension_name):
    keyword = _first(context.get("strategy_keywords") or context.get("document_keywords"), "")
    ref = _first(context.get("standard_refs"), "综合基线（内置）")
    behavior = _first(context.get("excellent_behaviors"), "")
    return {
        "strategy": "结合「{}」判断该维度需要承接业务方向。".format(keyword) if keyword else None,
        "framework": "参考{}的通用领导力框架。".format(ref) if ref else None,
        "interview": "用户提到「{}」，可归入{}。".format(behavior, dimension_name) if behavior else None,
    }


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


def _quality_check(context, dimension):
    issues = []
    if not context.get("target_group"):
        issues.append("[层级不匹配] 缺少单一层级/群体定位")
    if not dimension.get("sources"):
        issues.append("[过于笼统] 缺少来源依据")
    return {"passed": not issues, "issues": issues}


def _next_context_field(context):
    for key in ["industry", "company_size", "strategy_keywords", "management_pains", "target_group", "excellent_behaviors"]:
        if not (context or {}).get(key):
            return key
    return None


def _question_for_field(field):
    questions = {
        "industry": "请先说明企业所在行业、主营业务或产品服务。",
        "company_size": "请补充企业规模或当前发展阶段。",
        "strategy_keywords": "请列出未来1-2年的战略重点，可用分号分隔。",
        "management_pains": "请说明当前最需要解决的管理痛点。",
        "target_group": "请选择一个建模对象层级，例如基层、中层或高层管理者。",
        "excellent_behaviors": "请描述2个以上优秀管理者的具体行为表现。",
    }
    return questions.get(field, "请确认信息摘要是否准确。")


def _field_label(field):
    labels = {
        "industry": "行业/业务",
        "company_size": "规模阶段",
        "strategy_keywords": "战略重点",
        "management_pains": "管理痛点",
        "target_group": "建模对象",
        "excellent_behaviors": "优秀画像",
    }
    return labels.get(field, field or "信息")


def _collection_progress(context):
    keys = ["industry", "company_size", "strategy_keywords", "management_pains", "target_group", "excellent_behaviors"]
    completed = [key for key in keys if (context or {}).get(key)]
    return {"completed": completed, "missing": [key for key in keys if key not in completed]}


def _direction_signal(direction):
    text = str(direction or "")
    for signal in ["ERP库存数据", "跨部门周会", "跨部门推进", "资源协同", "量化成效", "复盘"]:
        if signal in text:
            return signal
    cleaned = text.replace("更强调", "").replace("补充", "").strip(" ，。")
    return cleaned[:18]


def _first(items, fallback):
    if isinstance(items, list) and items:
        return str(items[0])
    return fallback
