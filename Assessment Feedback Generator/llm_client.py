"""LLM client — supports free Groq / Gemini, or OpenRouter / OpenAI."""

from __future__ import annotations

import json
import os
import re

from openai import OpenAI

# Presets for free / paid providers (OpenAI-compatible chat API)
PROVIDERS = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        # Current Groq free catalog (llama-3.3-70b-versatile is no longer available)
        "model": "openai/gpt-oss-120b",
        "max_tokens": 4000,
        "json_mode": True,
        "key_env": "GROQ_API_KEY",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "model": "gemini-2.0-flash",
        "max_tokens": 4000,
        "json_mode": False,  # more reliable with prompt-only JSON
        "key_env": "GEMINI_API_KEY",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "model": "openai/gpt-4o-mini",
        "max_tokens": 4500,
        "json_mode": True,
        "key_env": "OPENAI_API_KEY",
    },
    "openai": {
        "base_url": None,
        "model": "gpt-4o-mini",
        "max_tokens": 4000,
        "json_mode": True,
        "key_env": "OPENAI_API_KEY",
    },
}


def _provider_name() -> str:
    return os.environ.get("LLM_PROVIDER", "groq").strip().lower() or "groq"


def _resolve_config() -> dict:
    name = _provider_name()
    preset = PROVIDERS.get(name, PROVIDERS["groq"]).copy()

    # Explicit overrides always win
    if os.environ.get("OPENAI_BASE_URL", "").strip():
        preset["base_url"] = os.environ["OPENAI_BASE_URL"].strip()
    if os.environ.get("OPENAI_MODEL", "").strip():
        preset["model"] = os.environ["OPENAI_MODEL"].strip()
    if os.environ.get("OPENAI_MAX_TOKENS", "").strip():
        preset["max_tokens"] = int(os.environ["OPENAI_MAX_TOKENS"])

    key = (
        os.environ.get(preset["key_env"], "").strip()
        or os.environ.get("OPENAI_API_KEY", "").strip()
        or os.environ.get("GROQ_API_KEY", "").strip()
        or os.environ.get("GEMINI_API_KEY", "").strip()
    )
    if not key:
        raise ValueError(
            "No LLM API key found. For free usage set GROQ_API_KEY "
            "(https://console.groq.com/keys) or GEMINI_API_KEY, "
            "and LLM_PROVIDER=groq or gemini in .env"
        )
    preset["api_key"] = key
    preset["name"] = name
    return preset


def get_client() -> OpenAI:
    cfg = _resolve_config()
    return OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"] or None)


def get_model() -> str:
    return _resolve_config()["model"]


def _parse_json(text: str) -> dict:
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def chat_json(system: str, user: str, temperature: float = 0.3) -> dict:
    cfg = _resolve_config()
    client = OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"] or None)

    system_msg = system
    if not cfg.get("json_mode"):
        system_msg = system + "\n\nRespond with a single valid JSON object only. No markdown."

    kwargs = {
        "model": cfg["model"],
        "temperature": temperature,
        "max_tokens": cfg["max_tokens"],
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user},
        ],
    }
    if cfg.get("json_mode"):
        kwargs["response_format"] = {"type": "json_object"}

    print(f"[LLM] provider={cfg['name']} model={cfg['model']}", flush=True)
    resp = client.chat.completions.create(**kwargs)
    return _parse_json(resp.choices[0].message.content or "{}")
