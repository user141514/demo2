import json
import re

from .llm_config import load_llm_settings
from .rules import load_knowledge_base_text, score_to_level


class LiveScoringError(Exception):
    pass


def live_score_submission(report_type, definition, document_text, transcript_text):
    settings = load_llm_settings()
    if settings.get("llm_mode") != "live":
        raise LiveScoringError("Live LLM mode is disabled.")
    if not settings.get("openai_api_key"):
        raise LiveScoringError("OpenAI-compatible API key is not configured.")

    try:
        from openai import OpenAI
    except Exception as exc:
        raise LiveScoringError("openai package is unavailable: {}".format(exc))

    client = OpenAI(
        api_key=settings["openai_api_key"],
        base_url=settings.get("openai_base_url") or None,
        timeout=settings.get("llm_report_timeout_seconds") or 60,
    )

    prompt = _build_user_prompt(report_type, definition, document_text, transcript_text)
    response = client.chat.completions.create(
        model=settings["openai_model"],
        temperature=0.0,
        messages=[
            {"role": "system", "content": _build_system_prompt()},
            {"role": "user", "content": prompt},
        ],
    )
    content = (response.choices[0].message.content or "").strip()
    if not content:
        raise LiveScoringError("LLM returned empty content.")

    payload = _extract_json_payload(content)
    dimensions = _normalize_dimensions(
        payload=payload,
        definition=definition,
        transcript_present=bool(transcript_text.strip()),
        document_text=document_text,
        transcript_text=transcript_text,
    )
    overall_comment = str(payload.get("overall_comment") or "").strip()
    if not overall_comment:
        raise LiveScoringError("LLM output is missing overall_comment.")

    return {
        "dimensions": dimensions,
        "overall_comment": overall_comment,
        "mode": "live",
        "provider": settings.get("openai_base_url") or "openai-compatible",
        "model": settings.get("openai_model") or "",
    }


def _build_system_prompt():
    return (
        "You are a professional training evaluation assistant. "
        "Score each dimension strictly from 0.0 to 10.0 with one decimal place. "
        "Return JSON only. Evidence must quote or paraphrase a short supporting excerpt "
        "from the provided material. Comment must be concise and evaluative."
    )


def _build_user_prompt(report_type, definition, document_text, transcript_text):
    dimension_lines = []
    for item in definition["dimensions"]:
        dimension_lines.append(
            "- id={id}; name={name}; group={group}; source={source}; focus={focus}; actual_weight={weight}%".format(
                id=item["id"],
                name=item["name"],
                group=item["group"],
                source=item["material_source"],
                focus=item["focus"],
                weight=item["actual_weight"],
            )
        )

    knowledge_base_text = load_knowledge_base_text(definition)
    knowledge_base_section = knowledge_base_text or "未配置课程专用评分标准，请仅按维度清单和通用锚定规则评分。"
    transcript_section = transcript_text.strip() or "未提供"
    action_learning_prompt = _build_action_learning_prompt() if report_type.startswith("行动学习") else ""
    return """请对以下{report_type}材料进行逐维度评分。

评分要求：
1. 只输出 JSON，不要输出 Markdown 或解释。
2. JSON 结构：
{{
  "overall_comment": "3-5句整体评价",
  "dimensions": [
    {{
      "id": 1,
      "score": 8.3,
      "summary": "不超过15字的一句话总结",
      "evidence": "不超过80字",
      "comment": "不超过120字"
    }}
  ]
}}
3. 如果录音转写未提供，则所有 source=录音转写 的维度必须输出：
   score = null
   evidence = "录音材料未提供"
   comment = ""
4. 不要改动维度 id。
5. score 取值范围 0.0-10.0，保留 1 位小数。
6. 若存在课程专用评分标准，必须按其中的锚定区间、评分指引、常见误区和扣分规则判定分数。
7. 输出结构以维度清单为准；课程专用评分标准用于解释每个维度应看哪些证据、何时加分或扣分。

{action_learning_prompt}

维度清单：
{dimension_lines}

---课程专用评分标准开始---
{knowledge_base_section}
---课程专用评分标准结束---

---文档内容开始---
{document_text}
---文档内容结束---

---录音转写文本开始---
{transcript_text}
---录音转写文本结束---
""".format(
        report_type=report_type,
        dimension_lines="\n".join(dimension_lines),
        knowledge_base_section=knowledge_base_section,
        action_learning_prompt=action_learning_prompt,
        document_text=document_text[:14000],
        transcript_text=transcript_section[:8000],
    )


def _build_action_learning_prompt():
    return """【行动学习评分身份】
你是中集车辆MBA人才池二期培训项目的专业评分导师，依据项目量化评分标准对学员的行动学习小组作业进行评分。

【你的评分身份】
你同时具备两种视角：
1. 熟悉本项目课程内容的培训导师——你清楚各次课程讲授的工具和框架，能判断学员是否将所学方法论真正运用于作业方案设计，而非堆砌名词
2. 评估落地方案质量的业务专家——你关注方案的针对性、可行性和实操性，能识别方案是否真正直面问题核心，还是在回避关键矛盾

【本项目课程知识体系】
以下是学员学过的核心工具和方法，评分时须识别小组是否恰当引用：

■ 模块一：认知升级（第一次课）
- PEST宏观分析框架
- 行业生命周期四阶段（孵化/成长/成熟/转型）
- 战略四原则（内外并举/短长结合/知行合一/财与非财并重）
- ASTRAL领导力模型六维度
- 组织架构设计逻辑（结构/流程/信息/决策四要素）

■ 模块二：组织协同（第二次课）
- 七大协同障碍根源（分工不明/目标差异/部门墙/个体差异/沟通技能/横向机制/协同文化）
- 协同四原则：服务协同/指导协同/管控协同/情感协同
- RACI矩阵（R负责/A批准/C咨询/I通知）——明确跨部门责任分工的核心工具
- 目标对齐四步法：对齐→共创→聚焦→闭环
- 乔哈里视窗——扩大信息共识的沟通工具
- 流程优化六原则（边界明确/精简高效/职责完整/持续监督/价值导向/机制保障）
- 跨部门协作五方法（认可价值/扩大共识/以理服人/共赢激励/有效沟通）
- 双线管理与指标互锁机制

■ 模块三：问题解决（第三次课）
- 问题四象限矩阵（模糊决策/创新变革/突发危机/执行偏差）及各类问题特征
- 问题三层根源拆解（现象层/流程层/系统层）
- 六步通用解决框架：①界定问题边界→②诊断核心诱因→③制定目标策略→④形成执行方案→⑤驱动变革落地→⑥评估反馈闭环
- 各类问题的核心解决重点：
  模糊决策→快速获取信息+动态方案；
  创新变革→系统性规划+变革推动；
  突发危机→快速界定边界+极限动作；
  执行偏差→监控机制+防错措施
- 5WHY根因分析法
- 数据驱动诊断（OEE/不良品分类/节拍数据等）
- 试点验证-批量推广模式

【评分标准全文】

■ 第一部分：作业评价（一级权重80%）
核心评估逻辑：问题穿透深度→方案设计精度→落地可行性

维度1：直面问题（子维度权重20%，实际权重16%）
- 9.0-10.0分（卓越）：精准揭示业务核心、关键问题，完全不避重就轻，论据数据详实、逻辑严密，具备极强的说服力，能直接支撑后续方案设计
- 7.5-8.9分（优秀）：清晰识别核心问题，未停留于表面现象，论据充分合理，说服力较强，能有效支撑方案的针对性设计
- 6.0-7.4分（良好）：能识别主要问题，未刻意回避核心矛盾，论据基本合理，具备基本说服力，但问题挖掘不够深入，存在一定的表面化倾向
- 4.0-5.9分（合格）：问题识别模糊，存在避重就轻倾向，论据单薄，说服力不足，对核心问题的揭示不够明确，难以支撑方案设计
- 0.0-3.9分（不合格）：未揭示核心问题，完全停留在表面描述，刻意回避关键矛盾，论据缺失或无效，无任何说服力

维度2：创新构想（子维度权重15%，实际权重12%）
- 9.0-10.0分（卓越）：结合作业要求、所学知识与实际问题，提出突破性创新构想，方案打破常规、具备显著挑战性，能带来超出预期的价值提升
- 7.5-8.9分（优秀）：能结合所学知识与实际问题，提出明确的改进/优化构想，创新性与挑战性较强，能带来明显的价值提升，符合作业要求
- 6.0-7.4分（良好）：能结合作业要求提出基本构想，有一定的优化意识，但创新性不足，整体偏向常规思路，挑战性较弱，仅能满足基本要求
- 4.0-5.9分（合格）：构想照搬常规思路，无任何创新或改进思考，与作业要求结合度低，无差异化价值，仅能勉强完成基础任务
- 0.0-3.9分（不合格）：无明确构想，或构想脱离作业要求、所学知识与实际问题，无任何价值，甚至不符合作业基本要求

维度3：结构性方法（子维度权重15%，实际权重12%）
- 9.0-10.0分（卓越）：精准选择并应用恰当的结构化方法设计方案，逻辑链条完整闭环，方案严谨、系统、科学，无任何逻辑漏洞，体现极强的系统性思维
- 7.5-8.9分（优秀）：能正确选择并应用合适的结构化方法，方案逻辑清晰、结构完整，无明显逻辑漏洞，严谨性与系统性较强
- 6.0-7.4分（良好）：能选用基本的结构化方法设计方案，方案结构基本完整，逻辑基本通顺，但方法应用不够熟练，存在轻微的逻辑衔接问题
- 4.0-5.9分（合格）：未选用合适的结构化方法，或方法应用生硬、与方案不匹配，方案结构松散，逻辑链条存在断裂，严谨性不足
- 0.0-3.9分（不合格）：未使用任何结构化方法，方案无逻辑、无结构，内容混乱，无法体现系统性与科学性

维度4：可操作性（子维度权重30%，实际权重24%）
- 9.0-10.0分（卓越）：解决方案针对性极强，具备高度可行性与实操性，关键步骤清晰、资源要求明确，可直接落地推进，无明显落地障碍
- 7.5-8.9分（优秀）：解决方案针对性明确，可行性与实操性较强，关键步骤清晰，资源要求合理，稍加完善即可落地推进
- 6.0-7.4分（良好）：解决方案有一定针对性，具备基本可行性，但关键步骤不够细化，资源要求不够明确，落地存在一定难度，需大幅完善
- 4.0-5.9分（合格）：解决方案针对性较弱，可行性不足，关键步骤模糊，资源要求不清晰，难以落地推进，仅停留在概念层面
- 0.0-3.9分（不合格）：解决方案无针对性、无可行性，完全脱离实际，无法落地，甚至会带来负面风险

■ 第二部分：呈现效果评价（一级权重20%，依据录音转写评判）
注：若录音转写文本标注"未提供"，维度5/6/7的score填null

维度5：表达清晰（子维度权重10%，实际权重2%）
- 9.0-10.0分（卓越）：陈述逻辑清晰、表达精准专业，重点突出、层次分明，能高效传递核心信息，听众可快速理解报告核心内容，无任何歧义
- 7.5-8.9分（优秀）：陈述清晰准确，表达流畅，重点明确，层次较分明，能有效传递核心信息，听众无理解障碍
- 6.0-7.4分（良好）：陈述基本清晰，表达较流畅，重点较明确，能传递主要信息，但存在少量表述模糊或逻辑衔接不畅的问题
- 4.0-5.9分（合格）：陈述不够清晰，表达存在卡顿或歧义，重点不突出，信息传递效率低，听众需反复理解才能获取关键内容
- 0.0-3.9分（不合格）：陈述混乱、表达不清，逻辑完全断裂，无法传递有效信息，听众无法理解报告内容

维度6：回答问题（子维度权重5%，实际权重1%）
- 9.0-10.0分（卓越）：回答问题简练、精准，直击核心，能快速响应评委问题，补充信息详实且贴合问题，体现对内容的深度掌握
- 7.5-8.9分（优秀）：回答问题简练准确，能有效回应评委问题，补充信息合理，体现对内容的良好掌握
- 6.0-7.4分（良好）：能回答评委问题，表述基本准确，但不够简练，存在少量冗余信息，基本体现对内容的掌握
- 4.0-5.9分（合格）：回答问题不够准确，表述冗长或偏离问题核心，难以有效回应评委提问，对内容掌握不足
- 0.0-3.9分（不合格）：无法回答评委问题，或回答完全偏离问题、表述混乱，无法体现对内容的掌握

维度7：时间管理（子维度权重5%，实际权重1%）
- 9.0-10.0分（卓越）：严格在规定时间内完成成果呈现，时间分配合理，无超时或提前结束的情况，节奏把控精准
- 7.5-8.9分（优秀）：在规定时间内完成呈现，时间分配较合理，无严重超时或提前结束（误差≤30秒），节奏把控较好
- 6.0-7.4分（良好）：基本在规定时间内完成呈现，存在轻微超时或提前结束（误差≤1分钟），时间分配存在少量不合理之处
- 4.0-5.9分（合格）：呈现严重超时或提前结束（误差＞1分钟），时间分配混乱，影响整体呈现效果
- 0.0-3.9分（不合格）：未在规定时间内完成呈现，超时严重或提前结束大量内容，无法完整呈现成果

【权重与计分说明】
总分 = Σ（各子维度得分 × 实际权重 × 10）
各维度实际权重：维度1=16%，维度2=12%，维度3=12%，维度4=24%，维度5=2%，维度6=1%，维度7=1%
注：总分由系统后端计算，你只需输出各维度的0-10分制分数，不需要计算总分

【打分规则】
1. 各子维度独立评分，范围0.0-10.0，保留1位小数，尽量避免整数（最小计量单位0.1分）
2. 严格按照上述五级锚定标准判断区间
3. 结构性方法（维度3）评分时，须明确识别小组选用了哪种框架工具（如六步解决框架/RACI/问题四象限等），判断工具与问题类型是否匹配，以及应用是否熟练
4. evidence字段：直接引用汇报材料中的具体内容作为打分依据，1-2句，不超过80字；若该维度录音未提供，填"录音材料未提供"
5. comment字段：对该维度给出具体评价，2-3句，不超过120字

【输出格式】
只输出以下JSON，不输出任何其他内容，不加```代码块标记：

{
  "report_type": "行动学习",
  "dimensions": [
    {
      "id": 1,
      "name": "直面问题",
      "level": "一级维度：作业评价",
      "material_source": "文档",
      "score": 7.8,
      "level_label": "优秀",
      "evidence": "方案明确指出管报与法报数据协同的核心矛盾在于信息传递不及时、口径不一致，并引用月度超15号的量化数据佐证。",
      "comment": "小组能直击协同问题的核心症结，论据有事实支撑，未停留在\"沟通不畅\"等表面描述。建议补充因信息不一致导致的管理层决策偏差的具体案例，以加强论证说服力。"
    }
  ],
  "overall_comment": "整体综合评价，3-5句，结合课程知识体系对小组作业给出针对性建议"
}
"""


def _extract_json_payload(content):
    try:
        return json.loads(content)
    except Exception:
        pass

    fenced = content.strip().strip("`")
    if fenced.lower().startswith("json"):
        fenced = fenced[4:].strip()
        try:
            return json.loads(fenced)
        except Exception:
            pass

    match = re.search(r"\{.*\}", content, re.S)
    if not match:
        raise LiveScoringError("LLM output is not valid JSON.")
    try:
        return json.loads(match.group(0))
    except Exception as exc:
        raise LiveScoringError("Failed to parse LLM JSON: {}".format(exc))


def _validate_evidence(evidence_text, source_text):
    """Check if LLM-generated evidence text is grounded in the source text."""
    if not evidence_text or len(evidence_text) < 5:
        return False
    # Strip leading/trailing ellipsis, punctuation, and whitespace
    evidence_clean = evidence_text.strip("…、。. ")
    if not evidence_clean:
        return False
    return evidence_clean in source_text


def _normalize_dimensions(payload, definition, transcript_present, document_text="", transcript_text=""):
    raw_dimensions = payload.get("dimensions")
    if not isinstance(raw_dimensions, list):
        raise LiveScoringError("LLM output is missing dimensions list.")

    by_id = {}
    for item in raw_dimensions:
        if not isinstance(item, dict):
            continue
        try:
            dim_id = int(item.get("id"))
        except Exception:
            continue
        by_id[dim_id] = item

    normalized = []
    for dimension in definition["dimensions"]:
        if dimension["source_key"] == "transcript" and not transcript_present:
            normalized.append(
                {
                    "id": dimension["id"],
                    "name": dimension["name"],
                    "group_name": dimension["group"],
                    "group_weight": dimension["group_weight"],
                    "actual_weight": dimension["actual_weight"],
                    "material_source": dimension["material_source"],
                    "score": None,
                    "level_label": None,
                    "evidence": "录音材料未提供",
                    "comment": "",
                }
            )
            continue

        item = by_id.get(dimension["id"])
        if item is None:
            raise LiveScoringError("LLM output is missing dimension id {}.".format(dimension["id"]))

        score = item.get("score")
        if score is None:
            raise LiveScoringError("LLM returned null score for required dimension {}.".format(dimension["id"]))

        try:
            numeric_score = round(float(score), 1)
        except Exception:
            raise LiveScoringError("LLM returned invalid score for dimension {}.".format(dimension["id"]))

        numeric_score = max(0.0, min(10.0, numeric_score))
        evidence = str(item.get("evidence") or "").strip()
        comment = str(item.get("comment") or "").strip()
        if not evidence:
            raise LiveScoringError("LLM output is missing evidence for dimension {}.".format(dimension["id"]))

        # Evidence grounding validation -- if LLM evidence is not found in source,
        # fall back to heuristic evidence extraction
        source_text = document_text if dimension["source_key"] == "document" else transcript_text
        if source_text and not _validate_evidence(evidence, source_text):
            from .scoring import _build_evidence  # lazy import avoids circular dependency

            heuristic_evidence = _build_evidence(
                source_text, dimension=dimension, definition=definition
            )
            evidence = heuristic_evidence

        evidence = _limit(evidence, 80)

        summary = str(item.get("summary") or "").strip()
        if summary:
            evidence = summary + "：" + evidence
            evidence = _limit(evidence, 80)

        comment = _limit(comment, 120)

        normalized.append(
            {
                "id": dimension["id"],
                "name": dimension["name"],
                "group_name": dimension["group"],
                "group_weight": dimension["group_weight"],
                "actual_weight": dimension["actual_weight"],
                "material_source": dimension["material_source"],
                "score": numeric_score,
                "level_label": score_to_level(numeric_score),
                "evidence": evidence,
                "comment": comment,
            }
        )
    return normalized


def _limit(text, size):
    if len(text) <= size:
        return text
    head_size = int(size * 0.6)
    tail_size = size - head_size - 1
    if tail_size < 10:
        return text[: size - 1].rstrip() + "…"
    return text[:head_size].rstrip() + "…" + text[-tail_size:].lstrip()
