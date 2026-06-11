import json
import re

from .leadership_prompts import build_stage_prompt
from .llm_config import load_llm_settings


class LeadershipLLMError(Exception):
    pass


def generate_stage_with_llm(stage, model_data):
    settings = load_llm_settings()
    if settings.get("llm_mode") != "live" or not settings.get("openai_api_key"):
        raise LeadershipLLMError("Live LLM mode is not configured.")

    try:
        from openai import OpenAI
    except Exception as exc:
        raise LeadershipLLMError("openai package is unavailable: {}".format(exc))

    client = OpenAI(
        api_key=settings["openai_api_key"],
        base_url=settings.get("openai_base_url") or None,
        timeout=settings.get("llm_report_timeout_seconds") or 25,
    )
    response = client.chat.completions.create(
        model=settings["openai_model"],
        temperature=0.2,
        messages=[
            {
                "role": "system",
                "content": "你是专业领导力建模顾问。只输出符合要求的 JSON。",
            },
            {"role": "user", "content": build_stage_prompt(stage, model_data)},
        ],
    )
    content = (response.choices[0].message.content or "").strip()
    payload = _extract_json(content)
    key = {"dimensions": "dimensions", "descriptions": "descriptions", "anchors": "anchors"}[stage]
    items = payload.get(key)
    if not isinstance(items, list) or not items:
        raise LeadershipLLMError("LLM output missing {} list.".format(key))
    return items


def _extract_json(content):
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
        raise LeadershipLLMError("LLM output is not JSON.")
    try:
        return json.loads(match.group(0))
    except Exception as exc:
        raise LeadershipLLMError("Failed to parse LLM JSON: {}".format(exc))
