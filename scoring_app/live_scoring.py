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
        evidence = _limit(str(item.get("evidence") or "").strip(), 80)
        comment = _limit(str(item.get("comment") or "").strip(), 120)
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


def _limit(text, size):
    if len(text) <= size:
        return text
    return text[: size - 1].rstrip() + "…"
