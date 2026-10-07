import os
from pathlib import Path
from unittest.mock import patch
import pytest

from runtime.go_runtime.core.server import GOApplication, RuntimeConfig, VERSION
from runtime.go_runtime.core.trusted_version_source import TVSIdentity, TVSVerification

def _verified(commit="c"*40, tree="t"*40):
    identity=TVSIdentity("OAI-GIANG/GO",commit,tree,VERSION,"d"*64)
    return TVSVerification("VERIFIED",identity,"A"*40,"TVS-TEST",None,"verified")

def _config(tmp_path, env="production"):
    return RuntimeConfig()

def test_production_blocks_without_tvs(tmp_path, monkeypatch):
    monkeypatch.setenv("GO_ENV","production")
    monkeypatch.setenv("GO_API_TOKEN","test")
    monkeypatch.setenv("GO_COMMIT","c"*40)
    monkeypatch.setenv("GO_TREE_SHA","t"*40)
    monkeypatch.setenv("GO_DATA",str(tmp_path/"db.sqlite"))
    monkeypatch.setenv("HG_TVS_ENFORCE","1")
    with patch("runtime.go_runtime.core.server.verify_from_environment",return_value=TVSVerification("BLOCKED",None,None,None,"BLOCKED_TVS_ROOT_UNAVAILABLE","no root")):
        app=GOApplication(RuntimeConfig())
        assert app.status()["tvs"]["status"]=="BLOCKED"
        with pytest.raises(RuntimeError,match="BLOCKED_TVS_ROOT_UNAVAILABLE"):
            app.submit({"operation":"echo","payload":{"x":1}})

def test_verified_tvs_allows_submission_gate(tmp_path, monkeypatch):
    monkeypatch.setenv("GO_ENV","production")
    monkeypatch.setenv("GO_API_TOKEN","test")
    monkeypatch.setenv("GO_COMMIT","c"*40)
    monkeypatch.setenv("GO_TREE_SHA","t"*40)
    monkeypatch.setenv("GO_DATA",str(tmp_path/"db.sqlite"))
    monkeypatch.setenv("HG_TVS_ENFORCE","1")
    with patch("runtime.go_runtime.core.server.verify_from_environment",return_value=_verified()):
        app=GOApplication(RuntimeConfig())
        assert app.status()["tvs"]["status"]=="VERIFIED"
        assert app.status()["tvs"]["enforced"] is True

def test_runtime_tree_mismatch_is_not_promoted(tmp_path, monkeypatch):
    monkeypatch.setenv("GO_ENV","production")
    monkeypatch.setenv("GO_API_TOKEN","test")
    monkeypatch.setenv("GO_COMMIT","c"*40)
    monkeypatch.setenv("GO_TREE_SHA","t"*40)
    monkeypatch.setenv("GO_DATA",str(tmp_path/"db.sqlite"))
    monkeypatch.setenv("HG_TVS_ENFORCE","1")
    blocked=TVSVerification("BLOCKED",None,None,"TVS-TEST","BLOCKED_TREE_MISMATCH","tree mismatch")
    with patch("runtime.go_runtime.core.server.verify_from_environment",return_value=blocked):
        app=GOApplication(RuntimeConfig())
        with pytest.raises(RuntimeError,match="BLOCKED_TREE_MISMATCH"):
            app.execute("T1","echo",{"x":1})
