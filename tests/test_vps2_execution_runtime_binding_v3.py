from __future__ import annotations

import os
import uuid

import pytest

from runtime.go_runtime.core.server import GOApplication, RuntimeConfig
from runtime.go_runtime.core.vps2_execution_bridge import (
    BridgeReject,
    BridgeRequest,
    OperationTemplate,
    VPS2ExecutionBridge,
)


def configured_app() -> GOApplication:
    os.environ["GO_API_TOKEN"] = "test-token"
    os.environ["GO_ALLOW_ANONYMOUS"] = "false"
    os.environ["HG_VPS2_TARGET_ID"] = "vps-5ku1ry"
    os.environ["HG_VPS2_ALLOWLIST_VERSION"] = "AL-2026-10-07"
    os.environ["HG_VPS2_POLICY_VERSION"] = "POL-2026-10-07"
    return GOApplication(RuntimeConfig())


def request(**overrides):
    data = {
        "request_id": str(uuid.uuid4()),
        "target_id": "vps-5ku1ry",
        "operation_id": "vps2.health",
        "allowlist_version": "AL-2026-10-07",
        "policy_version": "POL-2026-10-07",
        "variables": {},
    }
    data.update(overrides)
    return data


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("target_id", "wrong-target", "TARGET_OPERATION_MISMATCH"),
        ("allowlist_version", "wrong-allowlist", "ALLOWLIST_VERSION_MISMATCH"),
        ("policy_version", "wrong-policy", "POLICY_VERSION_MISMATCH"),
    ],
)
def test_runtime_binding_n12_n13_n14_reject_before_network(field, value, reason):
    app = configured_app()
    with pytest.raises(BridgeReject) as exc:
        app.execute_vps2(request(**{field: value}))
    assert exc.value.reason_code == reason


def test_runtime_binding_n09_rejects_raw_command():
    app = configured_app()
    with pytest.raises(BridgeReject) as exc:
        app.execute_vps2(request(variables={"command": "uname -a"}))
    assert exc.value.reason_code == "OPAQUE_OPERATION_REQUIRED"


def test_runtime_binding_n10_unknown_operation_rejects_before_network():
    app = configured_app()
    with pytest.raises(BridgeReject) as exc:
        app.execute_vps2(request(operation_id="shell.anything"))
    assert exc.value.reason_code == "UNKNOWN_OPERATION_ID"


def test_runtime_binding_n11_non_read_only_operation_rejects():
    bridge = VPS2ExecutionBridge(
        target_id="vps-5ku1ry",
        allowlist_version="AL-2026-10-07",
        policy_version="POL-2026-10-07",
        registry_version="VPS2-REGISTRY-V3",
        templates={
            "vps2.write": OperationTemplate("vps2.write", "/backend/write", False, ())
        },
    )
    with pytest.raises(BridgeReject) as exc:
        bridge.authorize(
            BridgeRequest(
                request_id=str(uuid.uuid4()),
                target_id="vps-5ku1ry",
                operation_id="vps2.write",
                allowlist_version="AL-2026-10-07",
                policy_version="POL-2026-10-07",
                variables={},
            )
        )
    assert exc.value.reason_code == "NON_READ_ONLY_OPERATION"


@pytest.mark.parametrize("field", ["request_id", "target_id"])
def test_runtime_binding_missing_required_field_rejects(field):
    app = configured_app()
    payload = request()
    payload.pop(field)
    with pytest.raises(BridgeReject) as exc:
        app.execute_vps2(payload)
    assert exc.value.reason_code == "REQUEST_BINDING_INVALID"
    assert exc.value.decision is not None
    assert exc.value.decision.decision == "DENY"
    assert exc.value.decision.reason_code == "REQUEST_BINDING_INVALID"


def test_runtime_rejection_evidence_is_complete():
    bridge = VPS2ExecutionBridge(
        target_id="vps-5ku1ry",
        allowlist_version="AL-2026-10-07",
        policy_version="POL-2026-10-07",
        registry_version="VPS2-REGISTRY-V3",
        templates={
            "vps2.health": OperationTemplate("vps2.health", "/backend/health", True, ())
        },
    )
    payload = BridgeRequest(
        request_id="",
        target_id="vps-5ku1ry",
        operation_id="vps2.health",
        allowlist_version="AL-2026-10-07",
        policy_version="POL-2026-10-07",
        variables={},
    )
    result = bridge.reject(payload)
    assert result["state"] == "REJECTED"
    assert result["decision"].decision == "DENY"
    evidence = result["evidence"]
    assert evidence["reason_code"] == "REQUEST_BINDING_INVALID"
    assert evidence["authorization_decision_id"] == result["decision"].decision_id
    assert evidence["execution_status"] == "REJECTED"
    assert evidence["executing"] is False
    assert "rejected_at" in evidence


def test_runtime_success_evidence_contains_timestamps():
    bridge = VPS2ExecutionBridge(
        target_id="vps-5ku1ry",
        allowlist_version="AL-2026-10-07",
        policy_version="POL-2026-10-07",
        registry_version="VPS2-REGISTRY-V3",
        templates={
            "vps2.health": OperationTemplate("vps2.health", "/backend/health", True, ())
        },
    )
    payload = BridgeRequest(
        request_id=str(uuid.uuid4()),
        target_id="vps-5ku1ry",
        operation_id="vps2.health",
        allowlist_version="AL-2026-10-07",
        policy_version="POL-2026-10-07",
        variables={},
    )
    result = bridge.execute(payload, lambda template, variables: {"ok": True})
    evidence = result["evidence"]
    assert result["state"] == "CLOSED"
    assert evidence["execution_status"] == "COMPLETED"
    assert evidence["authorization_timestamp"] == result["decision"].timestamp
    assert evidence["execution_started_at"]
    assert evidence["evidence_emitted_at"]
    assert evidence["closed_at"]


def test_runtime_positive_gate_reaches_edge_executor_boundary():
    app = configured_app()
    os.environ["HG_EDGE_URL"] = "http://127.0.0.1:9"
    os.environ["HG_EDGE_TOKEN"] = "not-a-real-token"
    # V2: the boundary is reached and classified — never a fabricated success.
    out = app.execute_vps2(request())
    assert out["evidence"]["external_state"] in {"FAILED", "UNKNOWN"}
    assert out["evidence"]["execution_status"] != "COMPLETED"
    assert out["evidence"]["reconciliation_required"] in {True, False}
    assert "100" != str(out["evidence"]["result"].get("http_status", ""))
