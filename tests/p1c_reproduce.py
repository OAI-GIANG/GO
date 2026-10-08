from pathlib import Path
from tempfile import TemporaryDirectory

from runtime.go_runtime.core.engine.durable_execution import DurableExecution
from runtime.go_runtime.core.store import RuntimeStore


with TemporaryDirectory() as d:
    store = RuntimeStore(Path(d) / "go.sqlite3")
    durable = DurableExecution(store)

    store.create_task("unknown", "ask", {}, "idem-unknown", "2026-10-08T00:00:00+00:00")
    claimed = durable.claim("unknown")
    assert claimed is not None
    out = durable.finalize(
        "unknown", int(claimed["fence_token"]), "COMPLETED",
        report={"epistemics": {"task_outcome": "UNKNOWN"}},
    )
    print("COMPLETED_UNKNOWN=", out["state"], out["task_outcome"], out["status"])
    assert out["state"] == "COMPLETED" and out["task_outcome"] == "UNKNOWN"

    store.create_task("success", "ask", {}, "idem-success", "2026-10-08T00:00:00+00:00")
    claimed = durable.claim("success")
    assert claimed is not None
    out = durable.finalize(
        "success", int(claimed["fence_token"]), "COMPLETED",
        report={"epistemics": {"task_outcome": "SUCCESS"}},
    )
    print("COMPLETED_SUCCESS=", out["state"], out["task_outcome"], out["status"])
    assert out["state"] == "COMPLETED" and out["task_outcome"] == "SUCCESS"

    store.create_task("failed", "ask", {}, "idem-failed", "2026-10-08T00:00:00+00:00")
    claimed = durable.claim("failed")
    assert claimed is not None
    out = durable.finalize("failed", int(claimed["fence_token"]), "FAILED", error={"message": "boom"})
    print("FAILED=", out["state"], out["task_outcome"], out["status"])
    assert out["state"] == "FAILED" and out["task_outcome"] == "FAILURE"

    task = store.get_task("unknown")
    print("PERSISTED=", task["state"], task["task_outcome"], task["status"])
