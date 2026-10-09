"""P0-A: canonical runtime-owned authority issuance + optional external provenance.

Core HGV2 does not require external trust-domain provisioning. The canonical
runtime-owned root may issue authority; the security invariant is single-root
ownership plus fail-closed token verification.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from runtime.go_runtime.core.authority import AuthorityRoot, AuthorityError, require_authority
from runtime.go_runtime.core.cognitive import CognitiveService
from runtime.go_runtime.core.store import RuntimeStore


def _runtime_owned_root(monkeypatch):
    """Force a SELF_PROVISIONED runtime-owned root and reset the singleton."""
    monkeypatch.delenv("HG_AUTHORITY_ROOT_KEY_FILE", raising=False)
    AuthorityRoot._instance = None
    return AuthorityRoot.instance()


# ---------------- runtime-owned root positive path ----------------
def test_direct_issue_allowed_for_runtime_owned_root(monkeypatch):
    root = _runtime_owned_root(monkeypatch)
    assert root.provenance() == "SELF_PROVISIONED"
    assert root.is_external() is False
    tok = root.issue(subject="s", scope=["runtime"], action="execute", audience="kernel", ttl_s=60)
    assert root.verify(tok, action="execute", scope=["runtime"], audience="kernel")


def test_delegation_allowed_for_runtime_owned_root(monkeypatch):
    root = _runtime_owned_root(monkeypatch)
    parent = root.issue(subject="root", scope=["runtime"], action="execute", audience="kernel", ttl_s=60)
    child = root.delegate(parent, subject="child", scope=["runtime"], action="execute", audience="kernel", ttl_s=30)
    assert root.verify(child, action="execute", scope=["runtime"], audience="kernel")


# ---------------- execution-path positive (caller -> callee -> root) ----------------
def test_cognitive_authorize_allowed_without_external_root(tmp_path, monkeypatch):
    _runtime_owned_root(monkeypatch)
    store = RuntimeStore(Path(tmp_path) / "go.sqlite3")
    cog = CognitiveService(store, "C", "T", "test")
    auth_id = cog.authorize("TASK-P0A-POS", "echo")
    assert auth_id
    store.close() if hasattr(store, "close") else None


def test_restart_rotates_runtime_owned_root_and_invalidates_old_token(monkeypatch):
    root = _runtime_owned_root(monkeypatch)
    token = root.issue(subject="s", scope=["runtime"], action="execute", audience="kernel", ttl_s=60)
    AuthorityRoot._instance = None
    restarted = AuthorityRoot.instance()
    assert restarted.provenance() == "SELF_PROVISIONED"
    assert restarted.is_external() is False
    assert restarted is not root
    assert not restarted.verify(token, action="execute", scope=["runtime"], audience="kernel")
    fresh = restarted.issue(subject="s", scope=["runtime"], action="execute", audience="kernel", ttl_s=60)
    assert restarted.verify(fresh, action="execute", scope=["runtime"], audience="kernel")


# ---------------- external-root positive path ----------------
def test_external_root_positive_path_explicit_secret():
    root = AuthorityRoot(secret=b"externally-injected-secret")   # EXPLICIT (injected)
    tok = root.issue(subject="s", scope=["runtime"], action="execute", audience="kernel", ttl_s=60)
    assert root.verify(tok, action="execute", scope=["runtime"], audience="kernel")  # issue -> verify -> ALLOW


def test_external_root_positive_path_via_key_file(tmp_path, monkeypatch):
    key = Path(tmp_path) / "root.key"
    key.write_bytes(b"file-provisioned-root-secret")
    monkeypatch.setenv("HG_AUTHORITY_ROOT_KEY_FILE", str(key))
    AuthorityRoot._instance = None
    root = AuthorityRoot.instance()
    assert root.provenance() == "EXTERNAL_FILE"
    tok = root.issue(subject="s", scope=["tool:vps2.health"], action="execute", audience="tool:vps2.health", ttl_s=60)
    assert root.verify(tok, action="execute", scope=["tool:vps2.health"], audience="tool:vps2.health")


def test_execution_path_positive_with_external_root(tmp_path):
    # autouse fixture provides an EXTERNAL_FILE root (no override here)
    store = RuntimeStore(Path(tmp_path) / "go.sqlite3")
    cog = CognitiveService(store, "C", "T", "test")
    auth_id = cog.authorize("TASK-P0A-POS", "echo")   # caller -> callee -> external root -> ALLOW
    assert auth_id
    store.close() if hasattr(store, "close") else None


# ---------------- explicit negative acceptance cases ----------------
def test_runtime_owned_token_rejects_wrong_action(monkeypatch):
    root = _runtime_owned_root(monkeypatch)
    token = root.issue(subject="alice", scope=["runtime"], action="execute", audience="kernel", ttl_s=60)

    assert not root.verify(token, action="admin", scope=["runtime"], audience="kernel")
    with pytest.raises(AuthorityError) as exc:
        require_authority(token, subject="alice", action="admin", scope=["runtime"], audience="kernel")
    assert exc.value.code == "AUTHORITY_DENIED"


def test_runtime_owned_token_rejects_wrong_expected_subject(monkeypatch):
    root = _runtime_owned_root(monkeypatch)
    token = root.issue(subject="alice", scope=["runtime"], action="execute", audience="kernel", ttl_s=60)

    with pytest.raises(AuthorityError) as exc:
        require_authority(token, subject="mallory", action="execute", scope=["runtime"], audience="kernel")
    assert exc.value.code == "AUTHORITY_REQUIRED"
