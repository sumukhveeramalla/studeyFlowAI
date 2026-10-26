"""Task-planning helper: LLM decomposition with deterministic fallback."""
from __future__ import annotations

from ..services import decomposition
from .llm import structured_json


def plan_tasks(
    title: str, description: str, estimated_hours: float, priority: str
) -> tuple[list[dict], str]:
    """Return (subtasks, mode). mode is 'llm' or 'demo'.

    LLM output is still reconciled so total minutes match the estimate (no
    double counting) and every field is validated.
    """
    prompt = (
        "You are an academic task-planning assistant. Break the assignment below "
        "into 3-6 ordered, concrete subtasks a student can act on.\n"
        f"Title: {title}\nDescription: {description}\n"
        f"Total estimated hours: {estimated_hours}\nPriority: {priority}\n"
        "Distribute minutes so they sum to roughly the total estimate."
    )
    schema = (
        '{"tasks": [{"title": "string", "estimated_minutes": 60, '
        '"priority": "low|medium|high"}]}'
    )
    data = structured_json(prompt, schema)
    if data and isinstance(data.get("tasks"), list) and data["tasks"]:
        out: list[dict] = []
        total_min = max(int(estimated_hours * 60), 30)
        raw = data["tasks"][:8]
        for idx, item in enumerate(raw):
            if not isinstance(item, dict) or not item.get("title"):
                continue
            minutes = item.get("estimated_minutes")
            try:
                minutes = int(minutes)
            except (TypeError, ValueError):
                minutes = total_min // len(raw)
            minutes = max(15, min(minutes, 1440))
            pr = item.get("priority", priority)
            if pr not in ("low", "medium", "high"):
                pr = priority
            out.append(
                {
                    "title": str(item["title"])[:200],
                    "estimated_minutes": minutes,
                    "priority": pr,
                    "order_index": idx,
                }
            )
        if out:
            # reconcile total to avoid double counting vs the assignment estimate
            diff = total_min - sum(t["estimated_minutes"] for t in out)
            out[-1]["estimated_minutes"] = max(15, out[-1]["estimated_minutes"] + diff)
            return out, "llm"

    # Deterministic fallback
    subtasks = decomposition.decompose(title, description, estimated_hours, priority)
    return (
        [
            {
                "title": s.title,
                "estimated_minutes": s.estimated_minutes,
                "priority": s.priority,
                "order_index": s.order_index,
            }
            for s in subtasks
        ],
        "demo",
    )
