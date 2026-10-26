"""Deterministic assignment decomposition templates (demo-mode fallback).

Produces an ordered list of subtasks with estimated minutes and priority.
The total estimated minutes are distributed from the assignment's estimated
hours so scheduling demand is not double counted.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SubTask:
    title: str
    priority: str
    estimated_minutes: int
    order_index: int


# Keyword -> ordered step templates with relative weights.
_TEMPLATES: dict[str, list[tuple[str, float]]] = {
    "coding": [
        ("Review relevant lecture notes and requirements", 0.15),
        ("Design the solution and set up the project", 0.15),
        ("Implement the core logic", 0.30),
        ("Test and debug", 0.20),
        ("Write up results and submit", 0.20),
    ],
    "writing": [
        ("Research and gather sources", 0.25),
        ("Create an outline", 0.15),
        ("Write the first draft", 0.30),
        ("Revise and edit", 0.20),
        ("Finalize formatting and submit", 0.10),
    ],
    "problem_set": [
        ("Review related concepts", 0.20),
        ("Work through the first half of problems", 0.30),
        ("Work through the second half of problems", 0.30),
        ("Check answers and clean up", 0.20),
    ],
    "reading": [
        ("Skim the material for structure", 0.20),
        ("Read in depth and take notes", 0.50),
        ("Summarize key takeaways", 0.30),
    ],
    "generic": [
        ("Understand the requirements", 0.20),
        ("Plan the approach", 0.15),
        ("Do the main work", 0.40),
        ("Review and finalize", 0.25),
    ],
}

_KEYWORDS = {
    "coding": ["code", "coding", "program", "implement", "model", "algorithm", "software", "ml", "machine learning", "neural", "data structure"],
    "writing": ["essay", "paper", "report", "write", "writing", "article", "review"],
    "problem_set": ["problem", "homework", "pset", "exercise", "worksheet", "math", "calculus"],
    "reading": ["read", "reading", "chapter", "textbook", "notes"],
}


def _pick_template(title: str, description: str) -> list[tuple[str, float]]:
    text = f"{title} {description}".lower()
    for category, words in _KEYWORDS.items():
        if any(w in text for w in words):
            return _TEMPLATES[category]
    return _TEMPLATES["generic"]


def decompose(title: str, description: str, estimated_hours: float, priority: str) -> list[SubTask]:
    template = _pick_template(title, description)
    total_min = max(int(estimated_hours * 60), 30)
    subtasks: list[SubTask] = []
    allocated = 0
    for idx, (step, weight) in enumerate(template):
        minutes = max(int(round(total_min * weight)), 15)
        allocated += minutes
        subtasks.append(
            SubTask(
                title=step,
                priority=priority,
                estimated_minutes=minutes,
                order_index=idx,
            )
        )
    # reconcile rounding so totals match assignment estimate
    if subtasks:
        diff = total_min - allocated
        subtasks[-1].estimated_minutes = max(15, subtasks[-1].estimated_minutes + diff)
    return subtasks
