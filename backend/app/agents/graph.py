"""LangGraph workflow wiring the supervisor + specialist agents.

START → supervisor ──(intent)──┐
   ├ decompose → task_planner → END
   ├ schedule  → scheduler → validate ─(ok)→ finalize → END
   │                              └(fail, retries<2)→ scheduler
   ├ replan    → replanner → validate ─(ok)→ finalize → END
   │                              └(fail, retries<2)→ replanner
   ├ query     → academic → END
   └ clarify   → clarify → END
"""
from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from . import nodes
from .state import AgentState


@lru_cache
def build_graph():
    g = StateGraph(AgentState)

    g.add_node("supervisor", nodes.supervisor)
    g.add_node("academic", nodes.academic)
    g.add_node("task_planner", nodes.task_planner)
    g.add_node("scheduler", nodes.scheduler)
    g.add_node("replanner", nodes.replanner)
    g.add_node("validate", nodes.validate)
    g.add_node("finalize", nodes.finalize)
    g.add_node("clarify", nodes.clarify)

    g.add_edge(START, "supervisor")
    g.add_conditional_edges(
        "supervisor",
        nodes.route_from_supervisor,
        {
            "decompose": "task_planner",
            "schedule": "scheduler",
            "replan": "replanner",
            "query": "academic",
            "clarify": "clarify",
        },
    )
    g.add_edge("task_planner", END)
    g.add_edge("academic", END)
    g.add_edge("clarify", END)
    g.add_edge("scheduler", "validate")
    g.add_edge("replanner", "validate")
    g.add_conditional_edges(
        "validate",
        nodes.route_after_validate,
        {"finalize": "finalize", "schedule": "scheduler", "replan": "replanner"},
    )
    g.add_edge("finalize", END)
    return g.compile()
