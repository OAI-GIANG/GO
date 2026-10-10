from __future__ import annotations

from datetime import datetime, timezone

from runtime.go_kernel import Evidence, Kernel
from runtime.go_runtime.core import checkpoint, evidence
from runtime.go_runtime.core.store import RuntimeStore


def canonical(eid: str, claim: str = "claim") -> evidence.CanonicalEvidence:
    return evidence.CanonicalEvidence(
        evidence_id=eid,
        subject="task-1",
        producer="producer",
        claim=claim,
        observation={"source": "test"},
        integrity="sha256:integrity",
        provenance={"source": "test"},
        verification_status="INDEPENDENTLY_VERIFIED",
        truth_status="VERIFIED",
        assurance_status="ASSESSED",
        verifier="verifier-B",
        captured_at="2026-10-08T00:00:00+00:00",
    )


def test_kernel_wires_through_canonical_unify_and_detects_duplicates():
    captured = datetime.now(timezone.utc)
    e = Evidence("E1", "task-1", "MODEL_EXECUTION", "runtime", captured, "prov", "integrity", "UNVERIFIED", "claim")
    out = Kernel().unify_evidence([e, e])
    assert out["count"] == 1
    assert out["duplicate_representations"]["E1"] == 2


def test_store_wires_evidence_records_through_unify(tmp_path):
    store = RuntimeStore(tmp_path / "go.sqlite3")
    now = "2026-10-08T00:00:00+00:00"
    record = {
        "evidence_id": "E-STORE",
        "task_id": "task-1",
        "event_type": "MODEL_EXECUTION",
        "source": "runtime",
        "claim": "claim",
        "integrity": "sha256:integrity",
        "provenance": "store",
        "verification_status": "UNVERIFIED",
        "truth_status": "UNVERIFIED",
        "captured_at": now,
    }
    store.save_evidence(record, now)
    out = store.unified_evidence("task-1")
    assert out["count"] == 1
    assert out["canonical"][0]["evidence_id"] == "E-STORE"


def test_store_ledger_wires_audit_events_through_unify(tmp_path):
    store = RuntimeStore(tmp_path / "go.sqlite3")
    store.add_event("task-1", "EVIDENCE_EMITTED", {"evidence_id": "E-LEDGER", "claim": "claim"}, "2026-10-08T00:00:00+00:00")
    out = store.unified_audit_evidence("task-1")
    assert out["count"] == 1
    assert out["canonical"][0]["evidence_id"] == "E-LEDGER"


def test_checkpoint_wires_refs_through_unify():
    refs = [
        checkpoint.EvidenceReference("E1", "sha256:1", "VERIFIED"),
        checkpoint.EvidenceReference("E1", "sha256:2", "VERIFIED"),
    ]
    out = checkpoint.unify_evidence_refs(refs)
    assert out["count"] == 1
    assert out["duplicate_representations"]["E1"] == 2
    assert "E1" in out["conflicts"]


def test_unify_is_the_single_semantic_owner():
    items = [canonical("E1"), canonical("E1", claim="different")]
    out = evidence.unify(items)
    assert out["count"] == 1
    assert out["duplicate_representations"]["E1"] == 2
    assert "E1" in out["conflicts"]
