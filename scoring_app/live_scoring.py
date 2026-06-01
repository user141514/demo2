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
        temperature=0.2,
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
    )
    overall_comment = str(payload.get("overall_comment") or "").strip()
    if not overall_comment:
        raise LiveScoringError("LLM output is missing overall_comment.")

    return {
        "dimensions": dimensions,
        "overall_comment": overall_comment,
        "strengths": _normalize_text_list(payload.get("strengths"), 3, 160),
        "improvements": _normalize_text_list(payload.get("improvements"), 6, 180),
        "mode": "live",
        "provider": settings.get("openai_base_url") or "openai-compatible",
        "model": settings.get("openai_model") or "",
    }


def _build_system_prompt():
    return (
        "You are a professional management-training evaluation consultant. "
        "Score each dimension strictly from 0.0 to 10.0 with one decimal place. "
        "Return JSON only. Write in polished Chinese consultant-report style, "
        "close to a final MBA talent-pool evaluation report. Evidence must explain "
        "why the material supports the dimension score, not merely quote a raw excerpt. "
        "Dimension evidence should emphasize strengths and concrete signals; comments "
        "should state improvement space and next actions."
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
    return """请对以下{report_type}材料进行逐维度评分，并把输出内容写成可直接进入正式评估报告的文字。

评分要求：
1. 只输出 JSON，不要输出 Markdown 或解释。
2. JSON 结构：
{{
  "overall_comment": "5-7句总体评价，先概括汇报完整性和主案例，再指出最强亮点、关键量化证据、主要短板，最后给出管理潜力/后续提升判断",
  "strengths": [
    "3条优势亮点；每条必须点名具体维度、案例/工具/数据或现场表现，避免泛泛表扬"
  ],
  "improvements": [
    "5-6条结论与改进建议；每条用动作化标题开头，包含明确补充内容或表达动作"
  ],
  "dimensions": [
    {{
      "id": 1,
      "score": 8.3,
      "evidence": "120-220字；以“优势亮点：”开头，说明命中了哪些评价要点、具体案例/工具/数据是什么、为什么支撑该分数",
      "comment": "80-180字；以“改进空间：”开头，指出缺口和下一步应补充的材料、页面、数据或表达方式"
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
8. evidence 面向用户展示，必须改写为可理解的评分依据：说明材料命中了哪些评价要点、支撑强弱和对应分数原因；不要仅复制原文或使用省略号截断原文。
9. 输出风格对齐正式评估报告：少用“当前材料支撑较充分”这类模板句，多写具体对象，例如战略背景、RACI/5WHY/逻辑树等工具、百分比/天数/阶段数据、跨部门角色、现场表达节奏。
10. 维度文字采用“优势亮点 + 改进空间”的二段逻辑：肯定必须具体，批评必须可执行。复盘类维度要追问个人失误、能力短板、认知变化和行为改变；规划类维度要追问资源、数据权限、里程碑和协同机制；展现类维度要区分书面材料和现场表达。
11. improvements 是最终结论建议，不要只重复低分维度名称；写成类似“补充结构化反思页，直面个人不足”“将关键量化成效做成视觉冲击页”“完善资源规划与跨部门协同安排”的动作建议。

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
        document_text=document_text[:14000],
        transcript_text=transcript_section[:8000],
    )


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


def _normalize_dimensions(payload, definition, transcript_present):
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
        evidence = _limit(str(item.get("evidence") or "").strip(), 220)
        comment = _limit(str(item.get("comment") or "").strip(), 180)
        if not evidence:
            raise LiveScoringError("LLM output is missing evidence for dimension {}.".format(dimension["id"]))

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


def _normalize_text_list(value, max_items, item_size):
    if not isinstance(value, list):
        return []
    items = []
    for item in value:
        text = _limit(str(item or "").strip(), item_size)
        if text:
            items.append(text)
        if len(items) >= max_items:
            break
    return items


def _limit(text, size):
    if len(text) <= size:
        return text
    return text[: size - 1].rstrip() + "…"
