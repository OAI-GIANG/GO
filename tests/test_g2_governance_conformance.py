"""G2 governance conformance / negative tests (PROPOSED).

These execute against the reconciled runtime modules (hg-core governance line + PR#8 V2 line).
They map to the G2 negative-test matrix. They are unit/conformance tests, NOT runtime/production
evidence. No secrets are used; authority roots are unique per-test temp files.
"""
from __future__ import annotations
import datetime as _dt
import json
from pathlib import Path

import pytest


def test_g2_policy_source_hash_pinned():
    from runtime.go_runtime.core.governance_source import verify_governance_source, PINNED_SOURCE_SHA256
    state = verify_governance_source()
    assert state["source_sha256"] == PINNED_SOURCE_SHA256
    assert state["status"] == "VERIFIED"


def test_g2_policy_source_missing_fails_closed(tmp_path):
    from runtime.go_runtime.core.governance_source import verify_governance_source, GovernanceSourceError
    with pytest.raises(GovernanceSourceError):
        verify_governance_source(tmp_path)  # empty dir -> canonical source missing


def test_g2_string_approval_is_not_evidence():
    from runtime.go_runtime.core.approval import verify_approval
    valid, reason = verify_approval("approved", subject="s", tool_name="danger",
                                    arguments_digest="d", policy_sha256="p", scope="tool:danger")
    assert valid is False and reason == "APPROVAL_EVIDENCE_REQUIRED"


def test_g2_missing_authority_root_not_provisioned(tmp_path, monkeypatch):
    from runtime.go_runtime.core.authority import AuthorityRoot, AuthorityError
    monkeypatch.delenv("HG_AUTHORITY_ROOT_KEY_FILE", raising=False)
    AuthorityRoot._instance = None
    # Hardened contract: absence of an external root is a hard blocker (no self-provisioned root).
    with pytest.raises(AuthorityError, match="AUTHORITY_ROOT_NOT_PROVISIONED"):
        AuthorityRoot.instance()
    AuthorityRoot._instance = None


def test_g2_evidence_promotion_requires_verifier(tmp_path):
    from runtime.go_kernel import Kernel, Evidence, GateResult
    now = _dt.datetime.now(_dt.timezone.utc)
    ev = Evidence("E-G2", "subj", "scope", "src", now, "prov", "integrity", "UNVERIFIED", "claim")
    gate, promoted = Kernel().verify_and_promote_evidence(ev, "subj", "scope", verification_result=None)
    assert gate is GateResult.BLOCKED and promoted is None


def test_g2_replay_tamper_detected(tmp_path):
    from runtime.go_runtime.core.store import RuntimeStore
    store = RuntimeStore(Path(tmp_path) / "go.sqlite3")
    row = store.append_replay("t", "EVENT", {"v": 1}, now="2026-10-10T00:00:00+00:00")
    import sqlite3
    with sqlite3.connect(Path(tmp_path) / "go.sqlite3") as conn:
        tampered = dict(row); tampered["payload"] = {"v": "tampered"}
        conn.execute("UPDATE replay_records SET record_json=? WHERE task_id=? AND sequence=?",
                     (json.dumps(tampered, sort_keys=True), "t", row["sequence"]))
    with pytest.raises(ValueError, match="migration_stop_invalid_legacy_replay_chain"):
        RuntimeStore(Path(tmp_path) / "go.sqlite3")


def test_g2_request_fingerprint_binds_fields():
    from runtime.go_runtime.core.engine.durable_execution import request_fingerprint
    a = request_fingerprint("goal", 2, execution_mode="ASYNC", idempotency_scope="TASK_SUBMISSION", metadata={"x": 1})
    assert a != request_fingerprint("goal", 2, execution_mode="SYNC", idempotency_scope="TASK_SUBMISSION", metadata={"x": 1})
    assert a != request_fingerprint("goal", 2, execution_mode="ASYNC", idempotency_scope="TASK_SUBMISSION", metadata={"x": 2})


def test_g2_canonical_evidence_mutation_detected():
    from runtime.go_runtime.core.evidence import CanonicalEvidence
    from runtime.go_runtime.core.certification_firewall import _valid_canonical_evidence
    item = CanonicalEvidence("e", "s", "p", "c", {"v": 1}, "integrity", {"src": "x"},
                             "INDEPENDENTLY_VERIFIED", "VERIFIED", "ASSESSED", "verifier", "2026-10-10T00:00:00Z")
    assert _valid_canonical_evidence(item) is True
    item.observation["v"] = 2
    assert _valid_canonical_evidence(item) is False


def test_g2_unify_evidence_present():
    from runtime.go_kernel import Kernel
    assert hasattr(Kernel, "unify_evidence")


def test_g2_entrypoints_fail_closed_on_invalid_governance(monkeypatch):
    from runtime.go_runtime.core import server as srv

    def _boom():
        raise RuntimeError("V1_CANONICAL_SOURCE_MISSING")

    monkeypatch.setattr(srv, "verify_governance_source", _boom)
    app = object.__new__(srv.GOApplication)  # bypass __init__; the guard runs before other attrs
    calls = [
        (app.execute_tool, ("t", "x", {})),
        (app.execute, ("t", "echo", {})),
        (app.run_objective, ("t", {"objective": "x"})),
        (app.submit, ({"operation": "echo", "payload": {}},)),
        (app.execute_vps2, ({},)),
    ]
    for fn, args in calls:
        with pytest.raises(RuntimeError):
            fn(*args)


def test_g2_unify_evidence_behavior():
    import datetime as _dt
    from runtime.go_kernel import Kernel, Evidence
    now = _dt.datetime.now(_dt.timezone.utc)
    e1 = Evidence("E1", "s", "sc", "src", now, "prov", "h1", "UNVERIFIED", "c")
    out = Kernel().unify_evidence([e1])
    assert out["count"] == 1 and out["schema"] and out["conflicts"] == {}
    dup = Kernel().unify_evidence([e1, e1])
    assert dup["duplicate_representations"].get("E1") == 2


def test_g2_tool_witness_binds_governance_hash(tmp_path, monkeypatch):
    from runtime.go_runtime.core.authority import AuthorityRoot
    from runtime.go_runtime.core.tool_governance import ToolGovernance
    from runtime.go_runtime.core.tool_runtime import ToolAdapter, ToolRegistry, ToolSpec

    key = tmp_path / "authority.key"
    key.write_bytes(b"g2-test-external-authority-key")
    monkeypatch.setenv("HG_AUTHORITY_ROOT_KEY_FILE", str(key))
    monkeypatch.setenv("HG_TOOL_AUTHORITY_SUBJECT", "HG_SESSION_G2")
    AuthorityRoot._instance = None
    root = AuthorityRoot.instance()
    token = root.issue(subject="HG_SESSION_G2", scope=["tool:g2.echo", "task:t"],
                       action="execute", audience="tool:g2.echo", ttl_s=60)
    tok_path = tmp_path / "authority-token.json"
    tok_path.write_text(json.dumps(token.to_dict()), encoding="utf-8")
    monkeypatch.setenv("HG_TOOL_AUTHORITY_TOKEN_FILE", str(tok_path))

    class Echo(ToolAdapter):
        def spec(self):
            return ToolSpec("g2.echo", "g2 echo", {"type": "object", "properties": {}, "additionalProperties": False},
                            True, False, "g2")
        def invoke(self, arguments, context):
            return {"ok": True}

    reg = ToolRegistry(); reg.register(Echo())
    gov = ToolGovernance(reg, tmp_path / "events.jsonl")
    result = gov.execute("t", "g2.echo", {}, call_id="CALL-G2-1")
    assert result.ok is True
    assert result.witness.get("governance_source_sha256")
    AuthorityRoot._instance = None
