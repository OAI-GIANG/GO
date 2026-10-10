"""G2 approval contract — unit + transport + integration tests.

Provides a TEST-ONLY trusted issuer fixture (never production trust). The issuer is
registered via monkeypatch of ``approval.TRUSTED_APPROVAL_ISSUERS``; production trust
remains fail-closed when no issuer is provisioned.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import hmac
import json

import pytest


class _TestIssuer:
    """Test-only approval issuer (deterministic HMAC). NOT production trust."""
    issuer_id = "issuer-g2-test"
    _key = b"g2-test-issuer-hmac-key"

    @classmethod
    def sign(cls, ev) -> str:
        msg = "|".join([ev.approval_id, ev.approver_id, ev.subject, ev.tool_name,
                        ev.arguments_digest, ev.policy_sha256, ev.scope, ev.expires_at,
                        ev.nonce, ev.target, ev.issuer_id]).encode()
        return hmac.new(cls._key, msg, hashlib.sha256).hexdigest()

    def verify(self, ev) -> bool:
        return ev.signature == self.sign(ev)


def _future(sec: int = 300) -> str:
    return (_dt.datetime.now(_dt.timezone.utc) + _dt.timedelta(seconds=sec)).isoformat()


def _make(**over):
    from runtime.go_runtime.core.approval import ApprovalEvidence
    base = dict(approval_id="AP-1", approver_id="owner", subject="HG_SESSION_G2",
                tool_name="g2.delete", arguments_digest="d0", policy_sha256="p0",
                scope="tool:g2.delete", expires_at=_future(), nonce="n-1",
                signature="", issuer_id=_TestIssuer.issuer_id, target="g2.delete")
    base.update(over)
    unsigned = ApprovalEvidence(**base)
    if base.get("signature"):
        return unsigned
    return ApprovalEvidence(**{**unsigned.__dict__, "signature": _TestIssuer.sign(unsigned)})


def _payload(**over) -> dict:
    return _make(**over).to_dict()


# ---- from_json validation ------------------------------------------------
def test_g2_from_json_valid():
    from runtime.go_runtime.core.approval import ApprovalEvidence
    ev = ApprovalEvidence.from_json(_payload())
    assert ev.tool_name == "g2.delete" and ev.target == "g2.delete"


def test_g2_from_json_rejects_missing():
    from runtime.go_runtime.core.approval import ApprovalEvidence
    p = _payload(); del p["nonce"]
    with pytest.raises(ValueError, match="missing fields"):
        ApprovalEvidence.from_json(p)


def test_g2_from_json_rejects_unknown():
    from runtime.go_runtime.core.approval import ApprovalEvidence
    p = _payload(); p["extra"] = "x"
    with pytest.raises(ValueError, match="unknown fields"):
        ApprovalEvidence.from_json(p)


def test_g2_from_json_rejects_empty_field():
    from runtime.go_runtime.core.approval import ApprovalEvidence
    p = _payload(); p["signature"] = ""
    with pytest.raises(ValueError, match="non-empty"):
        ApprovalEvidence.from_json(p)


def test_g2_from_json_rejects_non_object():
    from runtime.go_runtime.core.approval import ApprovalEvidence
    with pytest.raises(ValueError, match="must be a JSON object"):
        ApprovalEvidence.from_json(["x"])


# ---- verify_approval (issuer fixture) ------------------------------------
OK = dict(subject="HG_SESSION_G2", tool_name="g2.delete", arguments_digest="d0",
          policy_sha256="p0", scope="tool:g2.delete", target="g2.delete")


@pytest.fixture
def issuer(monkeypatch):
    from runtime.go_runtime.core import approval
    monkeypatch.setattr(approval, "TRUSTED_APPROVAL_ISSUERS", (_TestIssuer(),))


def test_g2_approval_valid(issuer):
    from runtime.go_runtime.core.approval import verify_approval
    ok, reason = verify_approval(_make(), **OK)
    assert ok is True and reason == "APPROVAL_VALID"


def test_g2_approval_string_not_evidence(issuer):
    from runtime.go_runtime.core.approval import verify_approval
    ok, reason = verify_approval("approved", **OK)
    assert ok is False and reason == "APPROVAL_EVIDENCE_REQUIRED"


def test_g2_approval_bad_signature(issuer):
    from runtime.go_runtime.core.approval import verify_approval
    ok, reason = verify_approval(_make(signature="00" * 32), **OK)
    assert ok is False and reason == "APPROVAL_SIGNATURE_INVALID"


def test_g2_approval_wrong_subject(issuer):
    from runtime.go_runtime.core.approval import verify_approval
    ok, reason = verify_approval(_make(subject="HG_SESSION_OTHER"), **OK)
    assert ok is False and reason == "APPROVAL_BINDING_MISMATCH"


def test_g2_approval_wrong_tool(issuer):
    from runtime.go_runtime.core.approval import verify_approval
    ok, reason = verify_approval(_make(tool_name="g2.other"), **OK)
    assert ok is False and reason == "APPROVAL_BINDING_MISMATCH"


def test_g2_approval_wrong_scope(issuer):
    from runtime.go_runtime.core.approval import verify_approval
    ok, reason = verify_approval(_make(scope="tool:g2.other"), **OK)
    assert ok is False and reason == "APPROVAL_BINDING_MISMATCH"


def test_g2_approval_wrong_fingerprint(issuer):
    from runtime.go_runtime.core.approval import verify_approval
    ok, reason = verify_approval(_make(arguments_digest="dX"), **OK)
    assert ok is False and reason == "APPROVAL_BINDING_MISMATCH"


def test_g2_approval_wrong_policy_hash(issuer):
    from runtime.go_runtime.core.approval import verify_approval
    ok, reason = verify_approval(_make(policy_sha256="pX"), **OK)
    assert ok is False and reason == "APPROVAL_BINDING_MISMATCH"


def test_g2_approval_wrong_target(issuer):
    from runtime.go_runtime.core.approval import verify_approval
    ok, reason = verify_approval(_make(target="g2.other"), **OK)
    assert ok is False and reason == "APPROVAL_TARGET_MISMATCH"


def test_g2_approval_expired(issuer):
    from runtime.go_runtime.core.approval import verify_approval
    ok, reason = verify_approval(_make(expires_at=_future(-60)), **OK)
    assert ok is False and reason == "APPROVAL_EXPIRED"


def test_g2_approval_missing_issuer(monkeypatch):
    from runtime.go_runtime.core import approval
    monkeypatch.setattr(approval, "TRUSTED_APPROVAL_ISSUERS", ())
    ok, reason = approval.verify_approval(_make(), **OK)
    assert ok is False and reason == "TRUSTED_APPROVAL_ISSUER_NOT_PROVISIONED"


# ---- HTTP transport deserialization --------------------------------------
def test_g2_transport_none_and_sentinel():
    from runtime.go_runtime.core.server import GOApplication
    assert GOApplication._deserialize_approval(None) == "not_required"
    assert GOApplication._deserialize_approval("not_required") == "not_required"
    assert GOApplication._deserialize_approval("") == "not_required"


def test_g2_transport_rejects_string_approval():
    from runtime.go_runtime.core.server import GOApplication
    with pytest.raises(ValueError, match="JSON object"):
        GOApplication._deserialize_approval("approved")


def test_g2_transport_rejects_non_object():
    from runtime.go_runtime.core.server import GOApplication
    with pytest.raises(ValueError):
        GOApplication._deserialize_approval(["x"])


def test_g2_transport_deserializes_object():
    from runtime.go_runtime.core.server import GOApplication
    from runtime.go_runtime.core.approval import ApprovalEvidence
    ev = GOApplication._deserialize_approval(_payload())
    assert isinstance(ev, ApprovalEvidence) and ev.target == "g2.delete"


# ---- integration through ToolGovernance (destructive tool) ---------------
class _DestructiveTool:
    def __init__(self):
        from runtime.go_runtime.core.tool_runtime import ToolAdapter, ToolSpec
        self.called = False
        self._Adapter = ToolAdapter
        self._Spec = ToolSpec

    def as_adapter(self):
        outer = self

        class _D(self._Adapter):
            def spec(self):
                return outer._Spec("g2.delete", "g2 delete",
                                   {"type": "object", "properties": {}, "additionalProperties": False},
                                   False, True, "g2")
            def invoke(self, arguments, context):
                outer.called = True
                return {"ok": True}
        return _D()


def _setup_auth(tmp_path, monkeypatch):
    from runtime.go_runtime.core.authority import AuthorityRoot
    key = tmp_path / "auth.key"
    key.write_bytes(b"g2-approval-test-external-key-32b")
    monkeypatch.setenv("HG_AUTHORITY_ROOT_KEY_FILE", str(key))
    monkeypatch.setenv("HG_TOOL_AUTHORITY_SUBJECT", "HG_SESSION_G2")
    AuthorityRoot._instance = None
    root = AuthorityRoot.instance()
    tok = root.issue(subject="HG_SESSION_G2", scope=["tool:g2.delete", "task:t"],
                     action="execute", audience="tool:g2.delete", ttl_s=120)
    tp = tmp_path / "tok.json"
    tp.write_text(json.dumps(tok.to_dict()))
    monkeypatch.setenv("HG_TOOL_AUTHORITY_TOKEN_FILE", str(tp))


def _gov(tmp_path):
    from runtime.go_runtime.core.tool_governance import ToolGovernance
    from runtime.go_runtime.core.tool_runtime import ToolRegistry
    tool = _DestructiveTool()
    reg = ToolRegistry(); reg.register(tool.as_adapter())
    return ToolGovernance(reg, tmp_path / "ev.jsonl"), tool


def _bound_approval(monkeypatch, **over):
    from runtime.go_runtime.core.tool_runtime import _digest
    from runtime.go_runtime.core.governance_source import verify_governance_source
    from runtime.go_runtime.core import approval
    monkeypatch.setattr(approval, "TRUSTED_APPROVAL_ISSUERS", (_TestIssuer(),))
    pol = verify_governance_source()["source_sha256"]
    base = dict(subject="HG_SESSION_G2", tool_name="g2.delete", scope="tool:g2.delete",
                arguments_digest=_digest({}), policy_sha256=pol, target="g2.delete")
    base.update(over)
    return _make(**base)


def test_g2_integration_valid_approval_executes(tmp_path, monkeypatch):
    _setup_auth(tmp_path, monkeypatch)
    gov, tool = _gov(tmp_path)
    appr = _bound_approval(monkeypatch)
    r = gov.execute("t", "g2.delete", {}, approval=appr, call_id="CALL-AP-OK")
    assert r.ok is True and tool.called is True


def test_g2_integration_string_approval_denied(tmp_path, monkeypatch):
    _setup_auth(tmp_path, monkeypatch)
    gov, tool = _gov(tmp_path)
    appr = _bound_approval(monkeypatch)
    r = gov.execute("t", "g2.delete", {}, approval="approved", call_id="CALL-AP-STR")
    assert r.ok is False and r.output["error"] == "APPROVAL_EVIDENCE_REQUIRED" and tool.called is False


def test_g2_integration_wrong_binding_denied(tmp_path, monkeypatch):
    _setup_auth(tmp_path, monkeypatch)
    gov, tool = _gov(tmp_path)
    appr = _bound_approval(monkeypatch, subject="HG_SESSION_OTHER")
    r = gov.execute("t", "g2.delete", {}, approval=appr, call_id="CALL-AP-MIS")
    assert r.ok is False and r.output["error"] == "APPROVAL_BINDING_MISMATCH" and tool.called is False


def test_g2_integration_replayed_nonce_denied(tmp_path, monkeypatch):
    _setup_auth(tmp_path, monkeypatch)
    gov, tool = _gov(tmp_path)
    appr = _bound_approval(monkeypatch)
    r1 = gov.execute("t", "g2.delete", {}, approval=appr, call_id="CALL-AP-R1")
    assert r1.ok is True
    r2 = gov.execute("t", "g2.delete", {}, approval=appr, call_id="CALL-AP-R2")
    assert r2.ok is False and r2.output["error"] == "APPROVAL_REPLAY_DETECTED"


def test_g2_integration_nonce_reservation_is_durable_across_instances(tmp_path, monkeypatch):
    """Replay protection survives a fresh governance instance (durable reservation)."""
    _setup_auth(tmp_path, monkeypatch)
    gov, tool = _gov(tmp_path)
    appr = _bound_approval(monkeypatch)
    assert gov.execute("t", "g2.delete", {}, approval=appr, call_id="CALL-DUR-1").ok is True
    ledger_path = tmp_path / "ev.jsonl"
    from runtime.go_runtime.core.tool_governance import ToolGovernance
    from runtime.go_runtime.core.tool_runtime import ToolRegistry
    tool2 = _DestructiveTool(); reg2 = ToolRegistry(); reg2.register(tool2.as_adapter())
    gov2 = ToolGovernance(reg2, ledger_path)
    r = gov2.execute("t", "g2.delete", {}, approval=appr, call_id="CALL-DUR-2")
    assert r.ok is False and r.output["error"] == "APPROVAL_REPLAY_DETECTED" and tool2.called is False


def test_g2_integration_concurrent_nonce_single_execution(tmp_path, monkeypatch):
    """Concurrency oracle: at most one request crosses the destructive boundary per nonce."""
    import threading
    from concurrent.futures import ThreadPoolExecutor
    _setup_auth(tmp_path, monkeypatch)
    gov, tool = _gov(tmp_path)
    appr = _bound_approval(monkeypatch)
    barrier = threading.Barrier(8)

    def call(i):
        barrier.wait()
        r = gov.execute("t", "g2.delete", {}, approval=appr, call_id="CALL-CONC-%d" % i)
        return r.ok, r.output.get("error")

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(call, range(8)))
    wins = [r for r in results if r[0] is True]
    losses = [r for r in results if r[0] is False]
    assert len(wins) == 1, results
    assert tool.called is True
    assert len(losses) == 7 and all(e == "APPROVAL_REPLAY_DETECTED" for _, e in losses), results


def test_g2_integration_nonce_store_failure_fails_closed(tmp_path, monkeypatch):
    _setup_auth(tmp_path, monkeypatch)
    gov, tool = _gov(tmp_path)
    appr = _bound_approval(monkeypatch)

    def _boom(*a, **k):
        raise OSError("simulated nonce-store failure")

    monkeypatch.setattr(gov.ledger, "reserve_nonce", _boom)
    r = gov.execute("t", "g2.delete", {}, approval=appr, call_id="CALL-STORE-FAIL")
    assert r.ok is False and r.output["error"] == "APPROVAL_NONCE_STORE_UNAVAILABLE" and tool.called is False
