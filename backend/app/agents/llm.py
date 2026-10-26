"""LLM factory and availability helpers.

When no API key is configured, the agents run in deterministic demo mode.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from ..config import get_settings


def llm_available() -> bool:
    return get_settings().llm_enabled


@lru_cache
def get_llm():
    """Return a LangChain chat model, or None if not configured/importable."""
    settings = get_settings()
    if not settings.llm_enabled:
        return None
    try:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            timeout=settings.llm_timeout_seconds,
            temperature=0,
            max_retries=1,
        )
    except Exception:
        return None


def structured_json(prompt: str, schema_hint: str) -> Optional[dict]:
    """Ask the LLM for JSON. Returns parsed dict or None on any failure."""
    llm = get_llm()
    if llm is None:
        return None
    import json

    try:
        msg = (
            prompt
            + "\n\nRespond ONLY with valid JSON matching this shape:\n"
            + schema_hint
        )
        resp = llm.invoke(msg)
        text = resp.content if hasattr(resp, "content") else str(resp)
        if isinstance(text, list):  # some providers return content parts
            text = "".join(str(p) for p in text)
        text = text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
        return json.loads(text)
    except Exception:
        return None
