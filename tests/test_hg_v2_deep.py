"""HG V2 deep remediation tests — canonical evidence unification, freshness,
corroboration independence, and external authority-root provenance."""
from __future__ import annotations

from runtime.go_runtime.core import evidence, freshness, corroboration
from runtime.go_runtime.core.authority import AuthorityRoot


# ---------------------------------------------------------------- evidence unification (ONE owner)
def test_evidence_unifies_all_representations_into_one_canonical_owner():
    w = evidence.from_witness("CALL-1", "vps2.health", {"task_id": "t", "output_digest": "sha256:o", "scope": "tool:vps2.health", "witness_digest": "sha256:w"})
    s = evidence.from_store_record({"evidence_id": "EVD-1", "task_id": "t", "source": "runtime", "claim": "c", "integrity": "sha256:i", "verification_status": "UNVERIFIED"})
    c = evidence.from_checkpoint_ref({"evidence_id": "EVD-1", "evidence_digest": "sha256:i", "verification_status": "UNVERIFIED"})
    out = evidence.unify([w, s, c])
    assert out["schema"] == evidence.EVIDENCE_SCHEMA
    assert out["count"] == 2  # CALL-1 + EVD-1
    assert out["duplicate_representations"] == {"EVD-1": 2}  # store + checkpoint are two representations of one id


def test_canonical_evidence_keeps_integrity_truth_separate():
    w = evidence.from_witness("CALL-2", "t", {"task_id": "t", "output_digest": "sha256:o"})
    d = w.to_dict()
    assert d["integrity"] == "sha256:o"
    assert d["truth_status"] == "UNVERIFIED"       # integrity != truth
    assert d["verification_status"] == "SELF_OBSERVED"
    assert d["assurance_status"] == "UNASSESSED"


# ---------------------------------------------------------------- freshness (GI-08)
def test_freshness_binding():
    prov = {"source_commit": "C", "source_tree": "T"}
    assert freshness.status(prov, source_commit="C", source_tree="T", issued_ts=100.0, now_ts=150.0) == "CURRENT"
    assert freshness.status(prov, source_commit="X", source_tree="T", issued_ts=100.0, now_ts=150.0) == "STALE"
    assert freshness.status(prov, source_commit="C", source_tree="T", issued_ts=100.0, now_ts=10_000_000.0) == "STALE"
    assert freshness.status(None, source_commit="C", source_tree="T", issued_ts=1.0, now_ts=2.0) == "UNBOUND"


# ---------------------------------------------------------------- corroboration (independence)
def test_same_source_x2_is_not_corroboration():
    items = [
        {"claim": "c", "truth_status": "VERIFIED", "source_domain": "S", "authority_domain": "A", "failure_domain": "F", "observer_domain": "O"},
        {"claim": "c", "truth_status": "VERIFIED", "source_domain": "S", "authority_domain": "A", "failure_domain": "F", "observer_domain": "O"},
    ]
    out = corroboration.corroborate("c", items)
    assert out["corroborated"] is False and out["reason"] == "NOT_INDEPENDENT"


def test_independent_domains_corroborate():
    items = [
        {"claim": "c", "truth_status": "VERIFIED", "source_domain": "S1", "authority_domain": "A1", "failure_domain": "F1", "observer_domain": "O1"},
        {"claim": "c", "truth_status": "VERIFIED", "source_domain": "S2", "authority_domain": "A2", "failure_domain": "F2", "observer_domain": "O2"},
    ]
    assert corroboration.corroborate("c", items)["corroborated"] is True


# ---------------------------------------------------------------- external authority root
def test_authority_root_provenance_external_vs_self_provisioned(tmp_path, monkeypatch):
    AuthorityRoot._instance = None
    monkeypatch.delenv("HG_AUTHORITY_ROOT_KEY_FILE", raising=False)
    assert AuthorityRoot.instance().provenance() == "SELF_PROVISIONED"
    assert AuthorityRoot.instance().is_external() is False
    key = tmp_path / "root.key"
    key.write_bytes(b"external-secret")
    AuthorityRoot._instance = None
    monkeypatch.setenv("HG_AUTHORITY_ROOT_KEY_FILE", str(key))
    assert AuthorityRoot.instance().provenance() == "EXTERNAL_FILE"
    assert AuthorityRoot.instance().is_external() is True
    AuthorityRoot._instance = None
