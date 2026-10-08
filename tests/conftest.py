"""Pytest session fixture: provision an EXTERNAL authority root key.

P0-A makes AuthorityRoot.issue() hard-deny EPHEMERAL/SELF_PROVISIONED roots, so the
runtime requires an externally provisioned root in tests too (mirrors production).
"""
from __future__ import annotations

import pytest

from runtime.go_runtime.core.authority import AuthorityRoot


@pytest.fixture(autouse=True)
def external_authority_root(tmp_path_factory, monkeypatch):
    key = tmp_path_factory.mktemp("hg-authority") / "root.key"
    key.write_bytes(b"test-provisioned-external-root-key")
    monkeypatch.setenv("HG_AUTHORITY_ROOT_KEY_FILE", str(key))
    AuthorityRoot._instance = None
    yield
    AuthorityRoot._instance = None
