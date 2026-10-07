from __future__ import annotations

import pytest

from runtime.go_runtime.core.vps2_execution_bridge import (
    BridgeReject,
    BridgeRequest,
    OperationTemplate,
    VPS2ExecutionBridge,
)


TARGET = "vps2-dr-01"
ALLOWLIST = "AL-2026-10-07"
POLICY = "POL-2026-10-07"
REGISTRY = "REG-1"

TEMPLATE = OperationTemplate(
    operation_id="forensic.status",
    action="GET /status",
    read_only=True,
    variable_types=(("scope", "str"),),
)


def bridge() -> VPS2ExecutionBridge:
    return VPS2ExecutionBridge(
        target_id=TARGET,
        allowlist_version=ALLOWLIST,
        policy_version=POLICY,
        registry_version=REGISTRY,
        templates={TEMPLATE.operation_id: TEMPLATE},
    )


def req(**overrides) -> BridgeRequest:
    data = dict(
        request_id="req-001",
        target_id=TARGET,
        operation_id=TEMPLATE.operation_id,
        allowlist_version=ALLOWLIST,
        policy_version=POLICY,
        variables={"scope": "health"},
    )
    data.update(overrides)
    return BridgeRequest(**data)


def test_positive_allow_binds_all_four_keys():
    d = bridge().authorize(req())
    assert d.decision == "ALLOW"
    assert d.target_id == TARGET
    assert d.operation_id == TEMPLATE.operation_id
    assert d.allowlist_version == ALLOWLIST
    assert d.policy_version == POLICY


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("target_id", "wrong-target", "TARGET_OPERATION_MISMATCH"),
        ("allowlist_version", "wrong-al", "ALLOWLIST_VERSION_MISMATCH"),
        ("policy_version", "wrong-pol", "POLICY_VERSION_MISMATCH"),
    ],
)
def test_ac_n12_n13_n14(field, value, reason):
    with pytest.raises(BridgeReject) as exc:
        bridge().authorize(req(**{field: value}))
    assert exc.value.reason_code == reason


def test_ac_n09_raw_command_rejected():
    with pytest.raises(BridgeReject) as exc:
        bridge().authorize(req(variables={"scope": "health", "command": "uname -a"}))
    assert exc.value.reason_code == "OPAQUE_OPERATION_REQUIRED"


def test_unknown_operation_rejected():
    with pytest.raises(BridgeReject) as exc:
        bridge().authorize(req(operation_id="shell.anything"))
    assert exc.value.reason_code == "UNKNOWN_OPERATION_ID"


def test_non_read_only_template_rejected():
    b = VPS2ExecutionBridge(
        target_id=TARGET,
        allowlist_version=ALLOWLIST,
        policy_version=POLICY,
        registry_version=REGISTRY,
        templates={
            "write.bad": OperationTemplate("write.bad", "POST /write", False, ())
        },
    )
    with pytest.raises(BridgeReject) as exc:
        b.authorize(req(operation_id="write.bad", variables={}))
    assert exc.value.reason_code == "NON_READ_ONLY_OPERATION"


def test_variable_type_rejected():
    with pytest.raises(BridgeReject) as exc:
        bridge().authorize(req(variables={"scope": 123}))
    assert exc.value.reason_code == "VARIABLE_TYPE_INVALID"


def test_template_hash_is_deterministic():
    assert TEMPLATE.template_hash == OperationTemplate(
        "forensic.status", "GET /status", True, (("scope", "str"),)
    ).template_hash


def test_registry_is_immutable():
    b = bridge()
    with pytest.raises(TypeError):
        b._templates["forensic.status"] = OperationTemplate(
            "forensic.status", "GET /changed", True, (("scope", "str"),)
        )


def test_execute_requires_authorization_before_executor():
    seen = []
    result = bridge().execute(req(), lambda t, v: seen.append((t, v)) or {"ok": True})
    assert seen == [(TEMPLATE, {"scope": "health"})]
    assert result["evidence"]["readonly_attestation"] is True
    assert result["evidence"]["authorization_decision_id"]


def test_reject_never_executes():
    rejected = bridge().reject(req(target_id="wrong"))
    assert rejected["state"] == "REJECTED"
    assert rejected["executing"] is False


def test_reject_contains_reason():
    rejected = bridge().reject(req(policy_version="wrong"))
    assert rejected["reason_code"] == "POLICY_VERSION_MISMATCH"


def test_decision_id_binds_template_hash():
    d = bridge().authorize(req())
    assert d.template_hash == TEMPLATE.template_hash
    assert d.decision_id


def test_no_allow_means_no_execution_path():
    with pytest.raises(BridgeReject):
        bridge().execute(req(allowlist_version="wrong"), lambda *_: {"executed": True})


def test_evidence_contains_all_security_bind_keys():
    result = bridge().execute(req(), lambda *_: {"ok": True})
    evidence = result["evidence"]
    assert evidence["target_id"] == TARGET
    assert evidence["operation_id"] == TEMPLATE.operation_id
    assert evidence["allowlist_version"] == ALLOWLIST
    assert evidence["policy_version"] == POLICY
