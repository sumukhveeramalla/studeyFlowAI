"""Shared LangGraph agent state."""
from __future__ import annotations

from typing import Any, Optional, TypedDict


class AgentState(TypedDict, total=False):
    user_id: int
    user_message: str
    intent: str
    params: dict[str, Any]
    context: dict[str, Any]
    proposal: Optional[dict]
    validation: Optional[dict]
    steps: list[dict]
    reply: str
    mode: str  # "llm" | "demo"
    retries: int
