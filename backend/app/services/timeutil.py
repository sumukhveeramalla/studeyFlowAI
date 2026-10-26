"""Timezone helpers. All stored datetimes are UTC-aware."""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def to_utc(dt: datetime) -> datetime:
    """Normalize any datetime to timezone-aware UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def ensure_aware(dt: datetime) -> datetime:
    """Ensure a datetime read from the DB is tz-aware (SQLite drops tzinfo)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def local_tz(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("UTC")
