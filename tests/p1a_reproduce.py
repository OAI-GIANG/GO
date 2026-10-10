from datetime import datetime, timezone

from runtime.go_kernel import Evidence, Kernel
from runtime.go_runtime.core import checkpoint, evidence
from runtime.go_runtime.core.store import RuntimeStore


e = Evidence("E1", "task-1", "MODEL_EXECUTION", "runtime", datetime.now(timezone.utc), "prov", "integrity", "UNVERIFIED", "claim")
kernel = Kernel()
k = kernel.unify_evidence([e, e])
print("KERNEL_UNIFY=", k["count"], k["duplicate_representations"])
assert k["count"] == 1 and k["duplicate_representations"]["E1"] == 2

import tempfile
store = RuntimeStore(tempfile.mktemp(suffix="-p1a.sqlite3"))
now = "2026-10-08T00:00:00+00:00"
store.save_evidence({"evidence_id":"E-STORE","task_id":"task-1","event_type":"MODEL_EXECUTION","source":"runtime","claim":"claim","integrity":"sha256:i","provenance":"p","verification_status":"UNVERIFIED","truth_status":"UNVERIFIED","captured_at":now}, now)
print("STORE_UNIFY=", store.unified_evidence("task-1")["count"])
assert store.unified_evidence("task-1")["count"] == 1

store.add_event("task-1", "EVIDENCE_EMITTED", {"evidence_id":"E-LEDGER","claim":"claim"}, now)
print("LEDGER_UNIFY=", store.unified_audit_evidence("task-1")["count"])
assert store.unified_audit_evidence("task-1")["count"] == 1

refs = [checkpoint.EvidenceReference("E1","sha256:1","VERIFIED"), checkpoint.EvidenceReference("E1","sha256:2","VERIFIED")]
cu = checkpoint.unify_evidence_refs(refs)
print("CHECKPOINT_UNIFY=", cu["count"], cu["duplicate_representations"], bool(cu["conflicts"]))
assert cu["count"] == 1 and cu["duplicate_representations"]["E1"] == 2 and "E1" in cu["conflicts"]

a = evidence.unify([
    evidence.CanonicalEvidence("E1","task","p","claim",{}, "i", {"p":"x"},"INDEPENDENTLY_VERIFIED","VERIFIED","ASSESSED","v","t"),
    evidence.CanonicalEvidence("E1","task","p","different",{}, "i", {"p":"x"},"INDEPENDENTLY_VERIFIED","VERIFIED","ASSESSED","v","t"),
])
print("CANONICAL_UNIFY=", a["count"], a["duplicate_representations"], bool(a["conflicts"]))
assert a["count"] == 1 and "E1" in a["conflicts"]
