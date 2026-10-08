"""HG V2 remediation tests — epistemic, authority, IVV, reconciliation, provenance,
assurance, certification firewall, intelligence eval, and removal of self-promotion.

Each area has positive + negative + adversarial coverage.
"""
from __future__ import annotations

import os

import pytest

from runtime.go_kernel import Evidence, GateResult, Kernel
from runtime.go_runtime.core import epistemics, ivv, reconciliation, provenance, assurance, evidence, certification_firewall, intelligence_eval
from runtime.go_runtime.core.authority import AuthorityRoot, AuthorityError, AuthorityToken, require_authority


# ---------------------------------------------------------------- epistemics (GI-01/02/03/07)
def test_completed_does_not_imply_success():
    assert epistemics.derive_task_outcome("COMPLETED") == "UNKNOWN"
    assert epistemics.derive_task_outcome("COMPLETED", "UNVERIFIED", "SELF_OBSERVED") == "UNKNOWN"


def test_success_requires_independent_verified_truth():
    assert epistemics.derive_task_outcome("COMPLETED", "VERIFIED", "INDEPENDENTLY_VERIFIED") == "SUCCESS"
    assert epistemics.derive_task_outcome("FAILED") == "FAILURE"


def test_unknown_is_first_class_and_envelope_separates_states():
    env = epistemics.envelope(execution_state="COMPLETED", truth_status="UNVERIFIED", verification_status="SELF_OBSERVED")
    assert env == {"execution_state": "COMPLETED", "task_outcome": "UNKNOWN", "truth_status": "UNVERIFIED",
                   "verification_status": "SELF_OBSERVED", "assurance_status": "UNASSESSED"}


def test_integrity_is_not_truth():
    out = epistemics.integrity_is_not_truth(integrity_ok=True)
    assert out["truth_status"] == "UNVERIFIED"


# ---------------------------------------------------------------- authority (single root, one issuer)
def test_single_authority_root_and_no_self_authority():
    root = AuthorityRoot(secret=b"unit-secret")
    tok = root.issue(subject="s1", scope=["tool:x"], action="execute", audience="tool:x", ttl_s=60)
    assert root.verify(tok, action="execute", scope=["tool:x"], audience="tool:x")
    # impersonation: a different root cannot verify this token (one issuer)
    assert not AuthorityRoot(secret=b"other").verify(tok, action="execute", scope=["tool:x"], audience="tool:x")


def test_authority_expiry_audience_scope_revocation(monkeypatch):
    root = AuthorityRoot(secret=b"unit-secret")
    tok = root.issue(subject="s1", scope=["tool:x"], action="execute", audience="tool:x", ttl_s=10)
    monkeypatch.setenv("HG_AUTHORITY_NOW", str(tok.expires_at + 1))
    assert not root.verify(tok, action="execute", scope=["tool:x"], audience="tool:x")  # expired
    monkeypatch.delenv("HG_AUTHORITY_NOW")
    assert not root.verify(tok, action="execute", scope=["tool:x"], audience="tool:y")  # wrong audience
    assert not root.verify(tok, action="execute", scope=["tool:z"], audience="tool:x")  # out of scope
    root.revoke(tok.token_id)
    assert not root.verify(tok, action="execute", scope=["tool:x"], audience="tool:x")  # revoked


def test_delegation_narrowing_ok_widening_denied():
    root = AuthorityRoot(secret=b"unit-secret")
    parent = root.issue(subject="root", scope=["tool:a", "tool:b"], action="execute", audience="tool", ttl_s=600)
    child = root.delegate(parent, subject="child", scope=["tool:a"], action="execute", audience="tool", ttl_s=60)
    assert root.verify(child, action="execute", scope=["tool:a"], audience="tool")
    with pytest.raises(AuthorityError):
        root.delegate(parent, subject="child", scope=["tool:a", "tool:c"], action="execute", audience="tool", ttl_s=60)  # widening


def test_forged_token_and_credential_as_authority_denied():
    root = AuthorityRoot(secret=b"unit-secret")
    tok = root.issue(subject="s1", scope=["tool:x"], action="execute", audience="tool:x", ttl_s=60)
    forged = AuthorityToken(**{**tok.__dict__, "subject": "attacker"})
    assert not root.verify(forged, action="execute", scope=["tool:x"], audience="tool:x")  # signature mismatch
    with pytest.raises(AuthorityError):
        require_authority("ghp_somecredential", subject="s1", action="execute", scope=["tool:x"], audience="tool:x")  # credential != authority
    with pytest.raises(AuthorityError):
        require_authority(None, subject="s1", action="execute", scope=["tool:x"], audience="tool:x")


# ---------------------------------------------------------------- IVV (producer != verifier)
class _Verifier:
    def __init__(self, vid, ad, fd):
        self.verifier_id, self.authority_domain, self.failure_domain = vid, ad, fd

    def verify(self, *, claim, evidence, producer_id):
        evidence_digest = ivv._digest({"claim": claim, "evidence": evidence})
        return ivv._issue_result(
            verification_status="INDEPENDENTLY_VERIFIED",
            truth_status="VERIFIED",
            verifier_id=self.verifier_id,
            method="external-check",
            reason="OK",
            evidence_digest=evidence_digest,
        )


def _trusted_handle(monkeypatch, verifier):
    spec = ivv.TrustedVerifierSpec(
        verifier_id=verifier.verifier_id,
        authority_domain=verifier.authority_domain,
        failure_domain=verifier.failure_domain,
        implementation=f"{verifier.__class__.__module__}:{verifier.__class__.__qualname__}",
    )
    monkeypatch.setattr(ivv, "TRUSTED_VERIFIER_REGISTRY", (ivv.TrustedVerifierBinding(spec, verifier),))
    return ivv.get_trusted_verifier(verifier.verifier_id)


def test_no_verifier_is_unverified_and_not_promotable():
    r = ivv.verify_evidence(claim="c", evidence={}, producer_id="p", producer_authority_domain="a", producer_failure_domain="f", verifier=None)
    assert r.verification_status == "UNVERIFIED"
    assert ivv.promotion_gate(r)["promotable"] is False


def test_producer_cannot_verify_itself(monkeypatch):
    v = _Verifier("p", "a", "f")  # same id AND same domains as producer
    r = ivv.verify_evidence(claim="c", evidence={}, producer_id="p", producer_authority_domain="a", producer_failure_domain="f", verifier=_trusted_handle(monkeypatch, v))
    assert r.verification_status == "VERIFICATION_FAILED" and r.reason == "PRODUCER_EQUALS_VERIFIER"


def test_verifier_sharing_domain_is_rejected(monkeypatch):
    v = _Verifier("v1", "a", "f")  # different id, same authority+failure domain
    r = ivv.verify_evidence(claim="c", evidence={}, producer_id="p", producer_authority_domain="a", producer_failure_domain="f", verifier=_trusted_handle(monkeypatch, v))
    assert r.verification_status == "VERIFICATION_FAILED" and r.reason == "VERIFIER_SHARES_AUTHORITY_DOMAIN"


def test_independent_verifier_promotes(monkeypatch):
    v = _Verifier("external-1", "ext-auth", "ext-fail")
    r = ivv.verify_evidence(claim="c", evidence={}, producer_id="p", producer_authority_domain="a", producer_failure_domain="f", verifier=_trusted_handle(monkeypatch, v))
    assert r.verification_status == "INDEPENDENTLY_VERIFIED"
    assert ivv.promotion_gate(r)["truth_status"] == "VERIFIED"


# ---------------------------------------------------------------- circular verification removed (kernel)
def test_kernel_requires_trusted_verification_result():
    ev = Evidence("EVD-1", "t1", "runtime", "src", __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
                  "prov", "integrity", "UNVERIFIED", "claim")
    blocked, promoted = Kernel().verify_and_promote_evidence(ev, "t1", "runtime",
                                                               verification_result=None)
    assert blocked is GateResult.BLOCKED and promoted is None
    try:
        Kernel().verify_and_promote_evidence(
            ev, "t1", "runtime", independent_verification="INDEPENDENTLY_VERIFIED"
        )
    except TypeError:
        pass
    else:
        raise AssertionError("caller-controlled promotion argument must be rejected")


# ---------------------------------------------------------------- reconciliation
def test_lost_response_with_possible_side_effect_is_unknown_not_success():
    st = reconciliation.classify(sent_ok=True, authorized=True, response_received=False, side_effect_possible=True)
    assert st == reconciliation.ExternalState.UNKNOWN
    assert reconciliation.may_retry(st) is False  # never blind-retry after a possible side effect
    assert reconciliation.reconcile(observed=st, recovered_response_ok=None) == reconciliation.ExternalState.RECONCILIATION_PENDING
    assert reconciliation.reconcile(observed=st, recovered_response_ok=True) == reconciliation.ExternalState.COMPLETED


# ---------------------------------------------------------------- provenance
def test_provenance_binding_and_independent_attestation():
    p = provenance.build_provenance(source_commit="C", source_tree="T", artifact_digests={"a": "sha256:1"},
                                    runtime_build="B", test_suite_version="v", environment="prod",
                                    dependency_lock="lock", timestamp="t", producer="p", verifier="v", authority="root")
    assert provenance.binds(p, source_commit="C", source_tree="T", runtime_build="B", artifact_digest="sha256:1")
    assert not provenance.binds(p, source_commit="X", source_tree="T", runtime_build="B")
    assert provenance.independent_attestation_status(p) == "PROVENANCE_INDEPENDENT_ATTESTATION_BLOCKED"


# ---------------------------------------------------------------- assurance + firewall
def test_assurance_profile_and_case():
    prof = assurance.profile({"EPISTEMIC": assurance.dimension(status="VERIFIED", evidence="e", freshness="t", verifier="v", strength="high", limitations="none")})
    assert prof["complete"] is False and "AUTHORITY" in prof["missing"]
    step = assurance.case_step(claim="c", risk="r", control="k", test="t", evidence="e", verifier="v", assurance="a")
    assert assurance.assurance_case([step])["complete"] is True
    with pytest.raises(ValueError):
        assurance.case_step(claim="", risk="r", control="k", test="t", evidence="e", verifier="v", assurance="a")


def _firewall_evidence(check: str, value: bool, status: str = "INDEPENDENTLY_VERIFIED", truth: str = "VERIFIED"):
    return evidence.CanonicalEvidence(
        evidence_id="fw-" + check,
        subject="certification",
        producer="independent-certifier",
        claim="firewall criterion " + check,
        observation={"firewall_check": check, "value": value},
        integrity="sha256:fixture",
        provenance={"source": "independent-test"},
        verification_status=status,
        truth_status=truth,
        assurance_status="ASSESSED",
        verifier="verifier-B",
        captured_at="2026-10-08T00:00:00+00:00",
    )


def test_certification_firewall_blocks_unverified_or_missing_evidence():
    items = [_firewall_evidence(name, True) for name in certification_firewall.REQUIRED_CHECKS[:-1]]
    out = certification_firewall.evaluate_evidence_backed(items)
    assert out["result"] == "CERTIFICATION_BLOCKED"
    assert "assurance_case_complete" in out["failed"]
    assert out["self_assertion_permitted"] is False


def test_certification_firewall_blocks_false_verified_evidence():
    items = [_firewall_evidence(name, True) for name in certification_firewall.REQUIRED_CHECKS]
    items[0] = _firewall_evidence(certification_firewall.REQUIRED_CHECKS[0], False)
    out = certification_firewall.evaluate_evidence_backed(items)
    assert out["result"] == "CERTIFICATION_BLOCKED"
    assert certification_firewall.REQUIRED_CHECKS[0] in out["failed"]


def test_certification_firewall_ready_only_from_complete_verified_evidence():
    items = [_firewall_evidence(name, True) for name in certification_firewall.REQUIRED_CHECKS]
    out = certification_firewall.evaluate_evidence_backed(items)
    assert out["result"] == "CERTIFICATION_READY"
    assert len(out["evidence_refs"]) == len(certification_firewall.REQUIRED_CHECKS)


def test_certification_firewall_rejects_self_observed_certification_evidence():
    items = [_firewall_evidence(name, True) for name in certification_firewall.REQUIRED_CHECKS]
    items[0] = _firewall_evidence(certification_firewall.REQUIRED_CHECKS[0], True, status="SELF_OBSERVED")
    out = certification_firewall.evaluate_evidence_backed(items)
    assert out["result"] == "CERTIFICATION_BLOCKED"


# ---------------------------------------------------------------- intelligence evaluation
def test_intelligence_eval_refuses_without_real_provider_or_ground_truth():
    ident = intelligence_eval.model_identity(provider="local", model="local.echo.v1", endpoint=None, version=None, sampling={}, tool_policy="none")
    assert ident["is_real_provider"] is False
    out = intelligence_eval.run(items=[{"id": "x", "ground_truth": 1}], produce=lambda i: 1, score=lambda i, o: 1.0, identity=ident)
    assert out["status"] == "INTELLIGENCE_CERTIFICATION_BLOCKED" and out["reason"] == "NO_REAL_PROVIDER"
