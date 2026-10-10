"""HG V2 threat-model / adversarial tests + structural regression guards.

Guards against reintroducing the resolved collisions, and exercises attack classes:
authority confusion, credential-as-authority, model-output-as-authorization,
evidence poisoning, cross-target delegation, lost-response, and self-promotion.
"""
from __future__ import annotations

import pathlib

import pytest

from runtime.go_runtime.core.authority import AuthorityRoot, AuthorityError, require_authority
from runtime.go_runtime.core.vps2_execution_bridge import VPS2ExecutionBridge, OperationTemplate

RUNTIME = pathlib.Path(__file__).resolve().parents[1] / "runtime"


def _read(rel: str) -> str:
    return (RUNTIME / rel).read_text(encoding="utf-8-sig")


# ---------------- structural guards (regression) ----------------
def test_no_runtime_self_certification_in_cognitive():
    src = _read("go_runtime/core/cognitive.py")
    assert 'evaluator_kind="runtime"' not in src
    assert 'evaluator_id="go_runtime-runtime"' not in src
    assert 'confidence=1.0 if' not in src


def test_no_second_authority_issuer():
    cog = _read("go_runtime/core/cognitive.py")
    tg = _read("go_runtime/core/tool_governance.py")
    assert 'issuer="go_runtime"' not in cog
    assert '"HG_KERNEL"' not in tg
    assert "AUTHORITY_ROOT_ID" in cog and "AUTHORITY_ROOT_ID" in tg


def test_kernel_requires_trusted_verification_result():
    src = _read("go_kernel.py")
    assert "independent_verification:" not in src
    assert "verification_result" in src
    assert "VerificationResult" in src


def test_objective_router_does_not_claim_success():
    src = _read("go_runtime/core/engine/objective_router.py")
    assert 'trace["final"] = "SUCCESS"' not in src
    assert 'trace["final"] = "ROUTED"' in src


# ---------------- attack classes ----------------
def test_authority_confusion_cross_target_denied():
    root = AuthorityRoot(secret=b"tm")
    tok = root.issue(subject="s", scope=["tool:a"], action="execute", audience="tool:a", ttl_s=60)
    assert root.verify(tok, action="execute", scope=["tool:a"], audience="tool:a")
    assert not root.verify(tok, action="execute", scope=["tool:b"], audience="tool:b")  # cannot cross target


def test_model_output_is_not_authorization():
    with pytest.raises(AuthorityError):
        require_authority({"decision": "ALLOW", "authorized": True}, subject="s", action="execute", scope=["tool:a"], audience="tool:a")
    with pytest.raises(AuthorityError):
        require_authority("ALLOW", subject="s", action="execute", scope=["tool:a"], audience="tool:a")


def test_credential_is_not_authority():
    with pytest.raises(AuthorityError):
        require_authority("ghp_token_value", subject="s", action="execute", scope=["tool:a"], audience="tool:a")


def test_lost_response_is_unknown_not_success():
    bridge = VPS2ExecutionBridge(
        target_id="t", allowlist_version="AL", policy_version="POL", registry_version="VPS2-REGISTRY-V3",
        templates={"vps2.health": OperationTemplate("vps2.health", "/backend/health", True, ())},
    )
    request = __import__("runtime.go_runtime.core.vps2_execution_bridge", fromlist=["BridgeRequest"]).BridgeRequest(
        request_id="r1", target_id="t", operation_id="vps2.health", allowlist_version="AL", policy_version="POL", variables={},
    )

    def lost_response(template, variables):
        raise RuntimeError("response lost after send")

    out = bridge.execute(request, lost_response)
    assert out["evidence"]["external_state"] == "UNKNOWN"
    assert out["evidence"]["execution_status"] == "UNKNOWN"
    assert out["evidence"]["reconciliation_required"] is True


def test_vps2_success_path_has_external_state_completed():
    bridge = VPS2ExecutionBridge(
        target_id="t", allowlist_version="AL", policy_version="POL", registry_version="VPS2-REGISTRY-V3",
        templates={"vps2.health": OperationTemplate("vps2.health", "/backend/health", True, ())},
    )
    request = __import__("runtime.go_runtime.core.vps2_execution_bridge", fromlist=["BridgeRequest"]).BridgeRequest(
        request_id="r2", target_id="t", operation_id="vps2.health", allowlist_version="AL", policy_version="POL", variables={},
    )
    out = bridge.execute(request, lambda t, v: {"http_status": 200, "body": {"ok": True}})
    assert out["evidence"]["execution_status"] == "COMPLETED"
    assert out["evidence"]["external_state"] == "COMPLETED"
    assert out["evidence"]["reconciliation_required"] is False
