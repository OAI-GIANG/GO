"""HG V2 build/runtime provenance binding (source -> build -> artifact -> runtime -> evidence).

A runtime self-report of GO_COMMIT is NOT independent proof. This module binds the
chain and can validate that a runtime/artifact corresponds to a declared source
commit/tree. External attestation is optional and, when absent, is explicitly BLOCKED.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()


def build_provenance(
    *,
    source_commit: str,
    source_tree: str,
    artifact_digests: dict[str, str],
    runtime_build: str,
    test_suite_version: str,
    environment: str,
    dependency_lock: str,
    timestamp: str,
    producer: str,
    verifier: str,
    authority: str,
) -> dict[str, Any]:
    payload = {
        "schema": "HG_BUILD_RUNTIME_PROVENANCE_V1",
        "source_commit": source_commit, "source_tree": source_tree,
        "artifact_digests": dict(sorted(artifact_digests.items())),
        "runtime_build": runtime_build, "test_suite_version": test_suite_version,
        "environment": environment, "dependency_lock": dependency_lock,
        "timestamp": timestamp, "producer": producer, "verifier": verifier, "authority": authority,
    }
    payload["provenance_digest"] = _digest(payload)
    return payload


def binds(
    provenance: dict[str, Any],
    *,
    source_commit: str,
    source_tree: str,
    runtime_build: str,
    artifact_digest: str | None = None,
) -> bool:
    """Fail-closed binding check (STOP-10 / STOP-34)."""
    if provenance.get("source_commit") != source_commit:
        return False
    if provenance.get("source_tree") != source_tree:
        return False
    if provenance.get("runtime_build") != runtime_build:
        return False
    if artifact_digest is not None:
        digests = provenance.get("artifact_digests") or {}
        if artifact_digest not in set(digests.values()):
            return False
    return True


def independent_attestation_status(provenance: dict[str, Any] | None) -> str:
    """Without an external attestation, provenance independence is BLOCKED (not VERIFIED)."""
    if not provenance:
        return "UNVERIFIED"
    if not provenance.get("external_attestation"):
        return "PROVENANCE_INDEPENDENT_ATTESTATION_BLOCKED"
    return "VERIFIED"
