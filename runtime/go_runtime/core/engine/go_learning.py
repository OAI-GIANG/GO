"""GO-native learning (ownership = GO).

Production learning path for HG. Deliberately free of LOVE media/publication
branches: it observes GO task outcomes and derives bounded, advisory hints.
"""
from __future__ import annotations
from typing import Any


def compute_go_learning(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    completed = failed = 0
    for task in tasks:
        state = str(task.get("state") or "")
        if state == "COMPLETED" or task.get("status") == "SUCCEEDED":
            completed += 1
        elif state in {"FAILED", "CANCELLED", "TIMED_OUT", "ABORTED_BY_KILL"}:
            failed += 1
    observations: list[str] = []
    recommendations: list[str] = []
    if completed and not failed:
        observations.append("observed_task_success_without_failure")
    if failed:
        observations.append("observed_task_failures")
        recommendations.append("review_failed_tasks")
    if completed == 0 and failed == 0:
        observations.append("no_task_history_yet")
    return {"schema_version": "GO-LEARNING-1.0", "observed_only": True, "authority": "none",
            "observations": observations, "recommendations": recommendations,
            "metrics": {"tasks_total": len(tasks), "tasks_completed": completed, "tasks_failed": failed}}


def build_go_hint(learning: dict[str, Any]) -> dict[str, Any]:
    return {"schema_version": "GO-KNOWLEDGE-HINT-1.0", "observed_only": True, "authority": "none",
            "observations": [str(x) for x in (learning.get("observations") or [])][:8],
            "recommendations": [str(x) for x in (learning.get("recommendations") or [])][:4],
            "metrics": learning.get("metrics") or {}}
