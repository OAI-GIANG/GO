"""Pytest fixture: provide a file-backed authority root for tests by default.

The current Personal Production contract permits the canonical runtime-owned
SELF_PROVISIONED root. P0-A tests explicitly remove this fixture setting to
exercise that path; unrelated tests use the file-backed root for isolation.
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
