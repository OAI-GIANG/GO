import json, os, subprocess
from pathlib import Path
from unittest.mock import patch
import pytest
from runtime.go_runtime.core.trusted_version_source import (
    canonical_identity, compute_tvs_id, verify_from_environment, verify_tvs,
)

def test_canonical_identity_is_deterministic():
    a=canonical_identity("OAI-GIANG/GO","a"*40,"b"*40,"0.1.1")
    b=canonical_identity("OAI-GIANG/GO","a"*40,"b"*40,"0.1.1")
    assert a==b
    assert a==b'{"commit_sha":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","repository":"OAI-GIANG/GO","runtime_version":"0.1.1","tree_sha":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"}'

def test_tvs_id_is_sha256_identity():
    v=compute_tvs_id("OAI-GIANG/GO","a"*40,"b"*40,"0.1.1")
    assert len(v)==64 and all(c in "0123456789abcdef" for c in v)

def test_missing_tag_blocks():
    old=os.environ.pop("HG_TVS_TAG",None); old2=os.environ.pop("HG_TVS_ROOT_FINGERPRINT",None)
    try:
        r=verify_from_environment(".",commit_sha="a"*40,tree_sha="b"*40,runtime_version="0.1.1")
        assert r.status=="BLOCKED" and r.reason_code=="BLOCKED_TVS_UNAVAILABLE"
    finally:
        if old is not None: os.environ["HG_TVS_TAG"]=old
        if old2 is not None: os.environ["HG_TVS_ROOT_FINGERPRINT"]=old2

def test_missing_root_blocks():
    old=os.environ.get("HG_TVS_TAG"); os.environ["HG_TVS_TAG"]="TVS"; os.environ.pop("HG_TVS_ROOT_FINGERPRINT",None)
    try:
        r=verify_from_environment(".",commit_sha="a"*40,tree_sha="b"*40,runtime_version="0.1.1")
        assert r.reason_code=="BLOCKED_TVS_ROOT_UNAVAILABLE"
    finally:
        if old is None: os.environ.pop("HG_TVS_TAG",None)
        else: os.environ["HG_TVS_TAG"]=old

def test_lightweight_tag_denied(tmp_path):
    subprocess.run(["git","init","-q",str(tmp_path)],check=True); subprocess.run(["git","-C",str(tmp_path),"config","user.name","t"],check=True); subprocess.run(["git","-C",str(tmp_path),"config","user.email","t@e"],check=True)
    (tmp_path/"x").write_text("x"); subprocess.run(["git","-C",str(tmp_path),"add","x"],check=True); subprocess.run(["git","-C",str(tmp_path),"commit","-qm","x"],check=True); subprocess.run(["git","-C",str(tmp_path),"tag","TVS"],check=True)
    r=verify_tvs(tmp_path,repository="OAI-GIANG/GO",commit_sha=subprocess.check_output(["git","-C",str(tmp_path),"rev-parse","HEAD"],text=True).strip(),tree_sha=subprocess.check_output(["git","-C",str(tmp_path),"rev-parse","HEAD^{tree}"],text=True).strip(),runtime_version="0.1.1",tag_name="TVS",trusted_fingerprint="A"*40)
    assert r.reason_code=="BLOCKED_TVS_NON_ANNOTATED_TAG"

@pytest.mark.parametrize("field,reason",[
    ("signer","BLOCKED_TVS_SIGNER_UNTRUSTED"),
    ("repository","BLOCKED_TVS_REPOSITORY_MISMATCH"),
    ("commit","BLOCKED_VERSION_MISMATCH"),
    ("tree","BLOCKED_TREE_MISMATCH"),
    ("version","BLOCKED_RUNTIME_VERSION_MISMATCH"),
    ("tvs_id","BLOCKED_TVS_ID_MISMATCH"),
])
def test_adversarial_identity_bindings(tmp_path,field,reason):
    repo=tmp_path; subprocess.run(["git","init","-q",str(repo)],check=True); subprocess.run(["git","-C",str(repo),"config","user.name","t"],check=True); subprocess.run(["git","-C",str(repo),"config","user.email","t@e"],check=True)
    (repo/"x").write_text("x"); subprocess.run(["git","-C",str(repo),"add","x"],check=True); subprocess.run(["git","-C",str(repo),"commit","-qm","x"],check=True); subprocess.run(["git","-C",str(repo),"tag","-a","-m","fixture","TVS"],check=True)
    c=subprocess.check_output(["git","-C",str(repo),"rev-parse","HEAD"],text=True).strip(); t=subprocess.check_output(["git","-C",str(repo),"rev-parse","HEAD^{tree}"],text=True).strip()
    payload={"schema":"HG_TRUSTED_VERSION_SOURCE_V2","repository":"OAI-GIANG/GO","commit_sha":c,"tree_sha":t,"runtime_version":"0.1.1","tvs_id":compute_tvs_id("OAI-GIANG/GO",c,t,"0.1.1")}
    with patch("runtime.go_runtime.core.trusted_version_source._signature",return_value="A"*40), patch("runtime.go_runtime.core.trusted_version_source._payload",return_value=payload):
        if field=="signer": result=verify_tvs(repo,repository="OAI-GIANG/GO",commit_sha=c,tree_sha=t,runtime_version="0.1.1",tag_name="TVS",trusted_fingerprint="B"*40)
        else:
            kwargs=dict(repository="OAI-GIANG/GO",commit_sha=c,tree_sha=t,runtime_version="0.1.1",tag_name="TVS",trusted_fingerprint="A"*40)
            if field=="repository": kwargs["repository"]="EVIL/GO"
            if field=="commit": kwargs["commit_sha"]="c"*40
            if field=="tree": kwargs["tree_sha"]="d"*40
            if field=="version": kwargs["runtime_version"]="9.9.9"
            if field=="tvs_id": payload["tvs_id"]="0"*64
            result=verify_tvs(repo,**kwargs)
    assert result.reason_code==reason



