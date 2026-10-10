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
    """Legacy helper name: prove unprovisioned root is denied, never self-created."""
    monkeypatch.delenv("HG_AUTHORITY_ROOT_KEY_FILE", raising=False)
    AuthorityRoot._instance = None
    with pytest.raises(AuthorityError, match="AUTHORITY_ROOT_NOT_PROVISIONED"):
        AuthorityRoot.instance()


def test_unprovisioned_root_fails_closed(monkeypatch):
    _runtime_owned_root(monkeypatch)


def test_cognitive_authorize_denied_without_provisioned_root(tmp_path, monkeypatch):
    _runtime_owned_root(monkeypatch)
    store = RuntimeStore(Path(tmp_path) / "go.sqlite3")
    cog = CognitiveService(store, "C", "T", "test")
    with pytest.raises(AuthorityError, match="AUTHORITY_ROOT_NOT_PROVISIONED"):
        cog.authorize("TASK-P0A-DENY", "echo")


def test_explicit_root_token_rejects_wrong_action():
    root = AuthorityRoot(secret=b"explicit-test-root")
    token = root.issue(subject="alice", scope=["runtime"], action="execute", audience="kernel", ttl_s=60)
    assert not root.verify(token, action="admin", scope=["runtime"], audience="kernel")
    with pytest.raises(AuthorityError):
        require_authority(token, subject="alice", action="admin", scope=["runtime"], audience="kernel")


def test_explicit_root_token_rejects_wrong_expected_subject():
    root = AuthorityRoot(secret=b"explicit-test-root")
    token = root.issue(subject="alice", scope=["runtime"], action="execute", audience="kernel", ttl_s=60)
    with pytest.raises(AuthorityError):
        require_authority(token, subject="mallory", action="execute", scope=["runtime"], audience="kernel")


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
    root = AuthorityRoot(secret=b"explicit-test-root")
    token = root.issue(subject="alice", scope=["runtime"], action="execute", audience="kernel", ttl_s=60)

    assert not root.verify(token, action="admin", scope=["runtime"], audience="kernel")
    with pytest.raises(AuthorityError) as exc:
        require_authority(token, subject="alice", action="admin", scope=["runtime"], audience="kernel")
    assert exc.value.code == "AUTHORITY_DENIED"


def test_runtime_owned_token_rejects_wrong_expected_subject(monkeypatch):
    root = AuthorityRoot(secret=b"explicit-test-root")
    token = root.issue(subject="alice", scope=["runtime"], action="execute", audience="kernel", ttl_s=60)

    with pytest.raises(AuthorityError) as exc:
        require_authority(token, subject="mallory", action="execute", scope=["runtime"], audience="kernel")
    assert exc.value.code == "AUTHORITY_REQUIRED"
