"""Shared router dependencies."""
from __future__ import annotations

from .seed import DEMO_USER_ID


def current_user_id() -> int:
    """MVP: single demo student profile."""
    return DEMO_USER_ID
