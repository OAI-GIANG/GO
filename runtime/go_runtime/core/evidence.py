"""HG V2 canonical evidence model — ONE semantic owner.

All other evidence representations (tool witness, ledger event, store record,
checkpoint reference, kernel Evidence) are ADAPTERS that project into this shape.
The fields OBSERVATION / INTEGRITY / PROVENANCE / VERIFICATION / TRUTH / ASSURANCE
are kept SEPARATE — never collapsed into a single `verified = true`.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

EVIDENCE_SCHEMA = "HG_EVIDENCE_CANONICAL_V2"


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class CanonicalEvidence:
    evidence_id: str
    subject: str
    producer: str
    claim: str
    observation: dict[str, Any]
    integrity: str            # digest of the artifact (integrity ONLY)
    provenance: dict[str, Any]
    verification_status: str  # SELF_OBSERVED | INDEPENDENTLY_VERIFIED | VERIFICATION_FAILED | UNVERIFIED
    truth_status: str         # UNVERIFIED | VERIFIED | REFUTED | UNKNOWN
    assurance_status: str     # UNASSESSED | ASSESSED | BLOCKED
    verifier: str | None
    captured_at: str

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema": EVIDENCE_SCHEMA, "evidence_id": self.evidence_id, "subject": self.subject,
            "producer": self.producer, "claim": self.claim, "observation": self.observation,
            "integrity": self.integrity, "provenance": self.provenance,
            "verification_status": self.verification_status, "truth_status": self.truth_status,
            "assurance_status": self.assurance_status, "verifier": self.verifier, "captured_at": self.captured_at,
        }
        payload["evidence_digest"] = _digest(payload)
        return payload


def from_kernel_evidence(e: Any) -> CanonicalEvidence:
    return CanonicalEvidence(
        evidence_id=str(getattr(e, "evidence_id", "")), subject=str(getattr(e, "subject", "")),
        producer=str(getattr(e, "source", "unknown")), claim=str(getattr(e, "claim", "")),
        observation={}, integrity=str(getattr(e, "integrity", "")),
        provenance={"value": str(getattr(e, "provenance", "")), "captured_at": str(getattr(e, "captured_at", ""))},
        verification_status=str(getattr(e, "verification_status", "UNVERIFIED")), truth_status="UNVERIFIED",
        assurance_status="UNASSESSED", verifier=None,
        captured_at=str(getattr(e, "captured_at", "")),
    )


def from_witness(call_id: str, tool_name: str, witness: dict[str, Any]) -> CanonicalEvidence:
    return CanonicalEvidence(
        evidence_id=str(call_id), subject=str(witness.get("task_id", "")), producer=f"tool:{tool_name}",
        claim=f"tool {tool_name} produced output", observation={"output_digest": witness.get("output_digest")},
        integrity=str(witness.get("output_digest", "")), provenance={"scope": witness.get("scope")},
        verification_status="SELF_OBSERVED", truth_status="UNVERIFIED", assurance_status="UNASSESSED",
        verifier=None, captured_at=str(witness.get("witness_digest", "")),
    )


def from_store_record(rec: dict[str, Any]) -> CanonicalEvidence:
    return CanonicalEvidence(
        evidence_id=str(rec.get("evidence_id", "")), subject=str(rec.get("task_id", "")),
        producer=str(rec.get("source", "runtime")), claim=str(rec.get("claim", "")),
        observation={"event_type": rec.get("event_type")}, integrity=str(rec.get("integrity", "")),
        provenance={"value": str(rec.get("provenance", ""))},
        verification_status=str(rec.get("verification_status", "UNVERIFIED")),
        truth_status=str(rec.get("truth_status", "UNVERIFIED")), assurance_status="UNASSESSED",
        verifier=rec.get("verifier"), captured_at=str(rec.get("captured_at", "")),
    )


def from_checkpoint_ref(ref: dict[str, Any]) -> CanonicalEvidence:
    return CanonicalEvidence(
        evidence_id=str(ref.get("evidence_id", "")), subject="", producer="checkpoint",
        claim="checkpoint evidence reference", observation={},
        integrity=str(ref.get("evidence_digest", "")), provenance={"checkpoint": True},
        verification_status=str(ref.get("verification_status", "UNVERIFIED")), truth_status="UNVERIFIED",
        assurance_status="UNASSESSED", verifier=None, captured_at="",
    )


def unify(items: list[CanonicalEvidence]) -> dict[str, Any]:
    """Project heterogeneous evidence into one canonical set + duplicate detection."""
    by_id: dict[str, list[CanonicalEvidence]] = {}
    for it in items:
        by_id.setdefault(it.evidence_id, []).append(it)
    duplicates = {k: len(v) for k, v in by_id.items() if len(v) > 1}
    return {
        "schema": EVIDENCE_SCHEMA,
        "canonical": [v[0].to_dict() for v in by_id.values()],
        "count": len(by_id),
        "duplicate_representations": duplicates,
        "unified_digest": _digest([sorted(v[0].to_dict().items()) for v in by_id.values()]),
    }
