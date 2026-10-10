from __future__ import annotations

from pathlib import Path

from runtime.go_runtime.core.store import RuntimeStore


def test_completed_is_not_success_when_outcome_unknown(tmp_path: Path):
    store = RuntimeStore(tmp_path / "go.sqlite3")
    task = store.create_task("t1", "ask", {}, "idem-1", "2026-10-08T00:00:00+00:00")
    store.update_task("t1", "COMPLETED", "2026-10-08T00:01:00+00:00", result={"epistemics": {"task_outcome": "UNKNOWN"}})
    out = store.get_task("t1")
    assert out["state"] == "COMPLETED"
    assert out["task_outcome"] == "UNKNOWN"
    assert out["status"] == "UNKNOWN"


def test_completed_can_have_explicit_success(tmp_path: Path):
    store = RuntimeStore(tmp_path / "go.sqlite3")
    store.create_task("t2", "ask", {}, "idem-2", "2026-10-08T00:00:00+00:00")
    task = store.get_task("t2")
    task.update({"state": "COMPLETED", "task_outcome": "SUCCESS", "updated_at": "2026-10-08T00:01:00+00:00"})
    store.upsert_task(task)
    out = store.get_task("t2")
    assert out["state"] == "COMPLETED"
    assert out["task_outcome"] == "SUCCESS"


def test_failed_is_failure_not_completed(tmp_path: Path):
    store = RuntimeStore(tmp_path / "go.sqlite3")
    store.create_task("t3", "ask", {}, "idem-3", "2026-10-08T00:00:00+00:00")
    store.update_task("t3", "FAILED", "2026-10-08T00:01:00+00:00", error="boom")
    out = store.get_task("t3")
    assert out["state"] == "FAILED"
    assert out["task_outcome"] == "FAILURE"


def test_invalid_outcome_is_rejected(tmp_path: Path):
    store = RuntimeStore(tmp_path / "go.sqlite3")
    store.create_task("t4", "ask", {}, "idem-4", "2026-10-08T00:00:00+00:00")
    task = store.get_task("t4")
    task["task_outcome"] = "COMPLETED"
    try:
        store.upsert_task(task)
    except ValueError as exc:
        assert str(exc) == "invalid_task_outcome"
    else:
        raise AssertionError("invalid task outcome accepted")


def test_legacy_status_does_not_turn_completed_state_into_success(tmp_path: Path):
    store = RuntimeStore(tmp_path / "go.sqlite3")
    store.create_task("t5", "ask", {}, "idem-5", "2026-10-08T00:00:00+00:00")
    task = store.get_task("t5")
    task["state"] = "COMPLETED"
    task["status"] = "COMPLETED"
    task.pop("task_outcome", None)
    try:
        store.upsert_task(task)
    except ValueError as exc:
        assert str(exc) == "invalid_task_outcome"
    else:
        raise AssertionError("legacy COMPLETED status bypassed the outcome ontology")
