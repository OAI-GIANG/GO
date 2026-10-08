"""P0-A: authority-root issuance hard-deny (EPHEMERAL/SELF_PROVISIONED) +
external-root positive path, proven on the REAL execution path (caller -> callee ->
root provenance -> decision) as well as directly.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from runtime.go_runtime.core.authority import AuthorityRoot, AuthorityError
from runtime.go_runtime.core.cognitive import CognitiveService
from runtime.go_runtime.core.store import RuntimeStore


def _deny_provenance(monkeypatch):
    """Force a SELF_PROVISIONED (in-process) root and reset the singleton."""
    monkeypatch.delenv("HG_AUTHORITY_ROOT_KEY_FILE", raising=False)
    AuthorityRoot._instance = None
    return AuthorityRoot.instance()


# ---------------- direct issue() negatives ----------------
def test_direct_issue_denied_for_ephemeral_root():
    root = AuthorityRoot()  # no injected secret -> EPHEMERAL
    assert root.provenance() in {"EPHEMERAL", "SELF_PROVISIONED"}
    with pytest.raises(AuthorityError) as exc:
        root.issue(subject="s", scope=["runtime"], action="execute", audience="kernel")
    assert exc.value.code == "AUTHORITY_ROOT_NOT_EXTERNAL"


def test_direct_issue_denied_for_self_provisioned_root(monkeypatch):
    root = _deny_provenance(monkeypatch)
    assert root.provenance() == "SELF_PROVISIONED"
    with pytest.raises(AuthorityError) as exc:
        root.issue(subject="s", scope=["runtime"], action="execute", audience="kernel")
    assert exc.value.code == "AUTHORITY_ROOT_NOT_EXTERNAL"


def test_delegation_denied_for_non_external_root(monkeypatch):
    root = _deny_provenance(monkeypatch)
    # even a fabricated parent cannot be used to mint via a non-external root
    with pytest.raises(AuthorityError) as exc:
        root.delegate(None, subject="s", scope=["runtime"], action="execute", audience="kernel", ttl_s=60)
    assert exc.value.code == "AUTHORITY_ROOT_NOT_EXTERNAL"


# ---------------- execution-path negative (caller -> callee -> root) ----------------
def test_cognitive_authorize_denied_without_external_root(tmp_path, monkeypatch):
    _deny_provenance(monkeypatch)
    store = RuntimeStore(Path(tmp_path) / "go.sqlite3")
    cog = CognitiveService(store, "C", "T", "test")
    with pytest.raises(AuthorityError) as exc:
        cog.authorize("TASK-P0A-NEG", "echo")   # caller -> CognitiveService.authorize -> root.issue -> DENY
    assert exc.value.code == "AUTHORITY_ROOT_NOT_EXTERNAL"
    store.close() if hasattr(store, "close") else None


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
