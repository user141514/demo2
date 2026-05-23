import importlib.util
import os
from functools import lru_cache
from pathlib import Path


DEFAULT_KEY_FILE = Path(os.getenv("SCORING_APP_KEY_FILE", r"E:\company_work\demo\mykey.py"))

DEFAULT_SETTINGS = {
    "llm_mode": "mock",
    "openai_api_key": "",
    "openai_base_url": "",
    "openai_model": "",
    "llm_report_enabled": False,
    "llm_report_timeout_seconds": 60,
}


def _load_external_config(path):
    if not path.exists():
        return {}

    spec = importlib.util.spec_from_file_location("external_mykey", str(path))
    if spec is None or spec.loader is None:
        return {}

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    payload = getattr(module, "llm_config", {})
    return payload if isinstance(payload, dict) else {}


@lru_cache(maxsize=1)
def load_llm_settings():
    settings = dict(DEFAULT_SETTINGS)
    settings.update(_load_external_config(DEFAULT_KEY_FILE))

    env_overrides = {
        "llm_mode": os.getenv("SCORING_LLM_MODE"),
        "openai_api_key": os.getenv("OPENAI_API_KEY"),
        "openai_base_url": os.getenv("OPENAI_BASE_URL"),
        "openai_model": os.getenv("OPENAI_MODEL"),
    }
    for key, value in env_overrides.items():
        if value:
            settings[key] = value

    try:
        settings["llm_report_timeout_seconds"] = int(
            settings.get("llm_report_timeout_seconds") or DEFAULT_SETTINGS["llm_report_timeout_seconds"]
        )
    except Exception:
        settings["llm_report_timeout_seconds"] = DEFAULT_SETTINGS["llm_report_timeout_seconds"]

    settings["llm_mode"] = str(settings.get("llm_mode") or "mock").lower()
    settings["llm_report_enabled"] = bool(settings.get("llm_report_enabled"))
    settings["openai_base_url"] = str(settings.get("openai_base_url") or "").rstrip("/")
    return settings


def get_public_llm_status():
    settings = load_llm_settings()
    return {
        "llm_mode": settings["llm_mode"],
        "openai_base_url": settings["openai_base_url"],
        "openai_model": settings["openai_model"],
        "llm_report_enabled": settings["llm_report_enabled"],
        "llm_report_timeout_seconds": settings["llm_report_timeout_seconds"],
        "key_configured": bool(settings.get("openai_api_key")),
        "key_file": str(DEFAULT_KEY_FILE),
    }
