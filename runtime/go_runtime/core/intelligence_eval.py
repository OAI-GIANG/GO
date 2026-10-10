"""HG V2 intelligence evaluation infrastructure (harness + scorer + blind protocol).

Infrastructure can be COMPLETE while certification is BLOCKED: a real provider and a
held-out ground-truth dataset are required. local.echo is NOT intelligence evidence.
This module never fabricates a score.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

DIMENSIONS = (
    "FUNCTIONAL_CORRECTNESS", "REASONING_QUALITY", "GROUND_TRUTH_ACCURACY",
    "ROBUSTNESS", "GENERALIZATION", "TOOL_USE", "SAFETY", "COST", "LATENCY",
)


def benchmark_schema() -> dict[str, Any]:
    return {
        "schema": "HG_INTELLIGENCE_BENCHMARK_V1",
        "item": {"id": "str", "objective": "str", "ground_truth": "any", "held_out": "bool", "adversarial": "bool", "rubric": "str"},
        "dimensions": list(DIMENSIONS),
    }


def model_identity(*, provider: str | None, model: str | None, endpoint: str | None, version: str | None, sampling: dict[str, Any] | None, tool_policy: str | None) -> dict[str, Any]:
    return {
        "provider": provider, "model": model, "endpoint": endpoint, "version": version,
        "sampling": sampling or {}, "tool_policy": tool_policy,
        "is_real_provider": bool(provider and provider not in {"local", "echo", "local.echo"}),
    }


def run(
    *,
    items: list[dict[str, Any]],
    produce: Callable[[dict[str, Any]], Any],
    score: Callable[[dict[str, Any], Any], float],
    identity: dict[str, Any],
) -> dict[str, Any]:
    """Blind, ground-truth-graded run. Refuses to produce a score without a real
    provider and held-out ground truth (INTELLIGENCE_CERTIFICATION = BLOCKED)."""
    if not identity.get("is_real_provider"):
        return {"schema": "HG_INTELLIGENCE_EVALUATION_V1", "status": "INTELLIGENCE_CERTIFICATION_BLOCKED",
                "reason": "NO_REAL_PROVIDER", "identity": identity, "score": None}
    if not items or not all(("ground_truth" in i) for i in items):
        return {"schema": "HG_INTELLIGENCE_EVALUATION_V1", "status": "INTELLIGENCE_CERTIFICATION_BLOCKED",
                "reason": "NO_GROUND_TRUTH", "identity": identity, "score": None}
    results = []
    for item in items:
        out = produce(item)
        results.append({"id": item.get("id"), "score": float(score(item, out)), "held_out": bool(item.get("held_out"))})
    total = sum(r["score"] for r in results) / len(results)
    return {
        "schema": "HG_INTELLIGENCE_EVALUATION_V1", "status": "SCORED", "identity": identity,
        "items": len(results), "score": round(total, 6),
        "held_out_score": round(sum(r["score"] for r in results if r["held_out"]) / max(1, len([r for r in results if r["held_out"]])), 6),
        "result_digest": "sha256:" + hashlib.sha256(json.dumps(results, sort_keys=True).encode()).hexdigest(),
    }
