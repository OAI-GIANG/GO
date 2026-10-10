from __future__ import annotations

from datetime import datetime, timezone

import pytest

from runtime.go_kernel import Evidence, GateResult, Kernel
from runtime.go_runtime.core import ivv


def make_evidence() -> Evidence:
    captured = datetime.now(timezone.utc)
    base = Evidence(
        "ev-p0c",
        "producer-A",
        "MODEL_EXECUTION",
        "runtime",
        captured,
        "producer-proof",
        "",
        "UNVERIFIED",
        "claim",
    )
    return Evidence(
        base.evidence_id,
        base.subject,
        base.scope,
        base.source,
        base.captured_at,
        base.provenance,
        base.expected_integrity(),
        base.verification_status,
        base.claim,
    )


class TrustedVerifierFixture:
    verifier_id = "verifier-B"
    authority_domain = "ivv-external"
    failure_domain = "isolated-verifier"

    def verify(self, *, claim, evidence, producer_id):
        evidence_digest = ivv._digest({"claim": claim, "evidence": evidence})
        return ivv._issue_result(
            verification_status="INDEPENDENTLY_VERIFIED",
            truth_status="VERIFIED",
            verifier_id=self.verifier_id,
            method="trusted-fixture",
            reason="trusted-positive",
            evidence_digest=evidence_digest,
            freshness_status="CURRENT",
            corroboration_status="CORROBORATED",
            assurance_status="ASSESSED",
        )


@pytest.fixture
def trusted_handle(monkeypatch):
    verifier = TrustedVerifierFixture()
    spec = ivv.TrustedVerifierSpec(
        verifier_id=verifier.verifier_id,
        authority_domain=verifier.authority_domain,
        failure_domain=verifier.failure_domain,
        implementation=f"{verifier.__class__.__module__}:{verifier.__class__.__qualname__}",
    )
    binding = ivv.TrustedVerifierBinding(spec=spec, verifier=verifier)
    monkeypatch.setattr(ivv, "TRUSTED_VERIFIER_REGISTRY", (binding,))
    return ivv.get_trusted_verifier(verifier.verifier_id)


def test_public_verification_result_constructor_is_forbidden():
    with pytest.raises(ivv.IVVError, match="VERIFICATION_RESULT_CONSTRUCTION_FORBIDDEN"):
        ivv.VerificationResult(
            "INDEPENDENTLY_VERIFIED",
            "VERIFIED",
            "caller-forged",
            "forged",
            "forged",
            "sha256:forged",
        )


def test_public_trusted_handle_constructor_is_forbidden():
    verifier = TrustedVerifierFixture()
    spec = ivv.TrustedVerifierSpec(
        verifier.verifier_id,
        verifier.authority_domain,
        verifier.failure_domain,
        f"{verifier.__class__.__module__}:{verifier.__class__.__qualname__}",
    )
    with pytest.raises(ivv.IVVError, match="TRUSTED_VERIFIER_HANDLE_CONSTRUCTION_FORBIDDEN"):
        ivv.TrustedVerifierHandle(verifier, spec)


def test_caller_controlled_promotion_is_denied():
    kernel = Kernel()
    evidence = make_evidence()
    with pytest.raises(TypeError):
        kernel.verify_and_promote_evidence(
            evidence,
            "producer-A",
            "MODEL_EXECUTION",
            independent_verification="INDEPENDENTLY_VERIFIED",
        )


def test_forged_dict_result_is_denied():
    kernel = Kernel()
    evidence = make_evidence()
    status, promoted = kernel.verify_and_promote_evidence(
        evidence,
        "producer-A",
        "MODEL_EXECUTION",
        verification_result={"verification_status": "INDEPENDENTLY_VERIFIED"},
    )
    assert status is GateResult.BLOCKED
    assert promoted is None


def test_forged_object_result_is_denied():
    kernel = Kernel()
    evidence = make_evidence()
    forged = object.__new__(ivv.VerificationResult)
    object.__setattr__(forged, "verification_status", "INDEPENDENTLY_VERIFIED")
    object.__setattr__(forged, "truth_status", "VERIFIED")
    object.__setattr__(forged, "verifier_id", "caller-forged")
    object.__setattr__(forged, "method", "forged")
    object.__setattr__(forged, "reason", "forged")
    object.__setattr__(forged, "digest", "sha256:forged")
    object.__setattr__(forged, "anchor_id", "HG_IVV_TRUST_ANCHOR_FORGED")

    status, promoted = kernel.verify_and_promote_evidence(
        evidence, "producer-A", "MODEL_EXECUTION", verification_result=forged
    )
    assert status is GateResult.BLOCKED
    assert promoted is None


def test_server_ignores_caller_injected_verifier(monkeypatch, tmp_path):
    from runtime.go_runtime.core.server import GOApplication, RuntimeConfig

    monkeypatch.setenv("GO_API_TOKEN", "test-token")
    monkeypatch.setenv("GO_DATA", str(tmp_path / "go.sqlite3"))
    app = GOApplication(RuntimeConfig())
    app._ivv_verifier = TrustedVerifierFixture()

    seen = {}
    original_verify = ivv.verify_evidence

    def capture_verify(**kwargs):
        seen["verifier"] = kwargs["verifier"]
        return original_verify(**kwargs)

    monkeypatch.setattr(ivv, "verify_evidence", capture_verify)
    monkeypatch.setattr(
        app.cognitive,
        "advise",
        lambda request: type("Advice", (), {"recommendation": "ok", "memory_ids": [], "evidence_ids": []})(),
    )
    monkeypatch.setattr(app.cognitive, "authorize", lambda task_id, operation: None)
    monkeypatch.setattr(app.cognitive, "reasoning_context", lambda advice: {})
    monkeypatch.setattr(app.cognitive, "invoke_model", lambda task_id, operation, payload: {"output": "ok"})
    monkeypatch.setattr(
        app.cognitive,
        "emit_evidence",
        lambda task_id, scope, claim: {
            "evidence_id": "server-p0c",
            "task_id": task_id,
            "event_type": "MODEL_EXECUTION",
            "source": "runtime",
            "captured_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
            "provenance": "runtime-proof",
            "integrity": "runtime-integrity",
            "claim": claim,
        },
    )
    monkeypatch.setattr(app.cognitive, "emit_replay", lambda *args, **kwargs: {"replay_id": "replay-p0c"})
    monkeypatch.setattr(app.cognitive, "observe_memory", lambda *args, **kwargs: None)
    monkeypatch.setattr(app.cognitive, "build_learning_artifact", lambda *args, **kwargs: {"artifact_id": "learn-p0c"})
    monkeypatch.setattr(ivv, "TRUSTED_VERIFIER_REGISTRY", ())

    result = app.execute("task-p0c", "ask", {})
    assert seen["verifier"] is None
    assert result["epistemics"]["verification_status"] == "UNVERIFIED"


def test_raw_caller_verifier_object_is_rejected():
    verifier = TrustedVerifierFixture()
    result = ivv.verify_evidence(
        claim="claim",
        evidence={"claim": "claim"},
        producer_id="producer-A",
        producer_authority_domain="runtime",
        producer_failure_domain="runtime",
        verifier=verifier,
    )
    assert result.verification_status == "VERIFICATION_FAILED"
    assert result.reason == "TRUSTED_VERIFIER_HANDLE_REQUIRED"


def test_unknown_registry_handle_is_rejected():
    verifier = TrustedVerifierFixture()
    spec = ivv.TrustedVerifierSpec(
        verifier.verifier_id,
        verifier.authority_domain,
        verifier.failure_domain,
        f"{verifier.__class__.__module__}:{verifier.__class__.__qualname__}",
    )
    with pytest.raises(ivv.IVVError, match="TRUSTED_VERIFIER_HANDLE_CONSTRUCTION_FORBIDDEN"):
        ivv.TrustedVerifierHandle(verifier, spec)


def test_same_producer_verifier_is_denied(trusted_handle):
    result = ivv.verify_evidence(
        claim="claim",
        evidence={"claim": "claim"},
        producer_id="verifier-B",
        producer_authority_domain="runtime",
        producer_failure_domain="runtime",
        verifier=trusted_handle,
    )
    assert result.verification_status == "VERIFICATION_FAILED"
    assert result.reason == "PRODUCER_EQUALS_VERIFIER"


def test_trusted_verification_result_allows_promotion(trusted_handle):
    kernel = Kernel()
    evidence = make_evidence()
    result = ivv.verify_evidence(
        claim=evidence.claim,
        evidence={"claim": evidence.claim},
        producer_id="producer-A",
        producer_authority_domain="runtime",
        producer_failure_domain="runtime",
        verifier=trusted_handle,
    )
    status, promoted = kernel.verify_and_promote_evidence(
        evidence, "producer-A", "MODEL_EXECUTION", verification_result=result,
        evidence_payload={"claim": evidence.claim}
    )
    assert result.anchor_id == ivv.TRUST_ANCHOR_ID
    assert status is GateResult.ALLOW
    assert promoted is not None
    assert promoted.verification_status == "VERIFIED"


def test_result_tampering_is_denied_at_promotion_gate(trusted_handle):
    evidence = make_evidence()
    result = ivv.verify_evidence(
        claim=evidence.claim,
        evidence={"claim": evidence.claim},
        producer_id="producer-A",
        producer_authority_domain="runtime",
        producer_failure_domain="runtime",
        verifier=trusted_handle,
    )
    forged = object.__new__(ivv.VerificationResult)
    for field in ("verification_status", "truth_status", "verifier_id", "method", "reason", "digest", "evidence_digest", "anchor_id", "freshness_status", "corroboration_status", "assurance_status"):
        object.__setattr__(forged, field, getattr(result, field))
    object.__setattr__(forged, "verifier_id", "attacker")
    assert ivv.promotion_gate(forged)["promotable"] is False
