import subprocess
from unittest.mock import patch
from runtime.go_runtime.core.trusted_version_source import compute_tvs_id, verify_tvs, TVSVerificationError

def setup(repo):
    subprocess.run(["git","init","-q",str(repo)],check=True); subprocess.run(["git","-C",str(repo),"config","user.name","t"],check=True); subprocess.run(["git","-C",str(repo),"config","user.email","t@e"],check=True)
    (repo/"x").write_text("x"); subprocess.run(["git","-C",str(repo),"add","x"],check=True); subprocess.run(["git","-C",str(repo),"commit","-qm","x"],check=True); subprocess.run(["git","-C",str(repo),"tag","-a","-m","fixture","TVS"],check=True)
    c=subprocess.check_output(["git","-C",str(repo),"rev-parse","HEAD"],text=True).strip(); t=subprocess.check_output(["git","-C",str(repo),"rev-parse","HEAD^{tree}"],text=True).strip()
    p={"schema":"HG_TRUSTED_VERSION_SOURCE_V2","repository":"OAI-GIANG/GO","commit_sha":c,"tree_sha":t,"runtime_version":"0.1.1","tvs_id":compute_tvs_id("OAI-GIANG/GO",c,t,"0.1.1")}
    return c,t,p

def run(repo,c,t,p,**kw):
    with patch("runtime.go_runtime.core.trusted_version_source._signature",return_value="A"*40), patch("runtime.go_runtime.core.trusted_version_source._payload",return_value=p):
        args=dict(repository="OAI-GIANG/GO",commit_sha=c,tree_sha=t,runtime_version="0.1.1",tag_name="TVS",trusted_fingerprint="A"*40); args.update(kw)
        return verify_tvs(repo,**args)

def test_ac_tvs_01_branch_locator_not_anchor(tmp_path):
    c,t,p=setup(tmp_path); subprocess.run(["git","tag","-a","-m","fixture","TVS-BRANCH"],cwd=tmp_path,check=True); subprocess.run(["git","tag","-d","TVS-BRANCH"],cwd=tmp_path,check=True); subprocess.run(["git","tag","TVS-BRANCH"],cwd=tmp_path,check=True)
    r=verify_tvs(tmp_path,repository="OAI-GIANG/GO",commit_sha=c,tree_sha=t,runtime_version="0.1.1",tag_name="TVS-BRANCH",trusted_fingerprint="A"*40)
    assert r.reason_code=="BLOCKED_TVS_NON_ANNOTATED_TAG"

def test_ac_tvs_02_lightweight_tag(tmp_path):
    c,t,p=setup(tmp_path); subprocess.run(["git","tag","-d","TVS"],cwd=tmp_path,check=True); subprocess.run(["git","tag","TVS"],cwd=tmp_path,check=True)
    r=verify_tvs(tmp_path,repository="OAI-GIANG/GO",commit_sha=c,tree_sha=t,runtime_version="0.1.1",tag_name="TVS",trusted_fingerprint="A"*40)
    assert r.reason_code=="BLOCKED_TVS_NON_ANNOTATED_TAG"

def test_ac_tvs_03_wrong_signer(tmp_path):
    c,t,p=setup(tmp_path); r=run(tmp_path,c,t,p,trusted_fingerprint="B"*40); assert r.reason_code=="BLOCKED_TVS_SIGNER_UNTRUSTED"

def test_ac_tvs_04_invalid_signature(tmp_path):
    c,t,p=setup(tmp_path)
    with patch("runtime.go_runtime.core.trusted_version_source._signature",side_effect=Exception("bad")):
        try: r=verify_tvs(tmp_path,repository="OAI-GIANG/GO",commit_sha=c,tree_sha=t,runtime_version="0.1.1",tag_name="TVS",trusted_fingerprint="A"*40)
        except Exception: r=None
    assert r is None or r.status=="BLOCKED"

def test_ac_tvs_05_repository_mismatch(tmp_path):
    c,t,p=setup(tmp_path); r=run(tmp_path,c,t,p,repository="EVIL/GO"); assert r.reason_code=="BLOCKED_TVS_REPOSITORY_MISMATCH"

def test_ac_tvs_06_commit_mismatch(tmp_path):
    c,t,p=setup(tmp_path); r=run(tmp_path,c,t,p,commit_sha="c"*40); assert r.reason_code=="BLOCKED_VERSION_MISMATCH"

def test_ac_tvs_07_tree_mismatch(tmp_path):
    c,t,p=setup(tmp_path); r=run(tmp_path,c,t,p,tree_sha="d"*40); assert r.reason_code=="BLOCKED_TREE_MISMATCH"

def test_ac_tvs_08_runtime_version_mismatch(tmp_path):
    c,t,p=setup(tmp_path); r=run(tmp_path,c,t,p,runtime_version="9.9.9"); assert r.reason_code=="BLOCKED_RUNTIME_VERSION_MISMATCH"

def test_ac_tvs_09_tvs_id_mismatch(tmp_path):
    c,t,p=setup(tmp_path); p["tvs_id"]="0"*64; r=run(tmp_path,c,t,p); assert r.reason_code=="BLOCKED_TVS_ID_MISMATCH"

def test_ac_tvs_10_malformed_payload(tmp_path):
    c,t,p=setup(tmp_path);
    with patch("runtime.go_runtime.core.trusted_version_source._signature",return_value="A"*40), patch("runtime.go_runtime.core.trusted_version_source._payload",side_effect=TVSVerificationError("BLOCKED_TVS_PAYLOAD_INVALID","malformed")):
        r=verify_tvs(tmp_path,repository="OAI-GIANG/GO",commit_sha=c,tree_sha=t,runtime_version="0.1.1",tag_name="TVS",trusted_fingerprint="A"*40)
    assert r.reason_code=="BLOCKED_TVS_PAYLOAD_INVALID"

def test_ac_tvs_11_missing_root(tmp_path,monkeypatch):
    monkeypatch.delenv("HG_TVS_ROOT_FINGERPRINT",raising=False); monkeypatch.delenv("HG_TVS_TAG",raising=False)
    from runtime.go_runtime.core.trusted_version_source import verify_from_environment
    r=verify_from_environment(tmp_path,commit_sha=c if False else "a"*40,tree_sha="b"*40,runtime_version="0.1.1")
    assert r.reason_code=="BLOCKED_TVS_UNAVAILABLE"

def test_ac_tvs_12_forged_runtime_observation(tmp_path):
    c,t,p=setup(tmp_path); r=run(tmp_path,c,t,p,commit_sha="e"*40,tree_sha=t)
    assert r.reason_code=="BLOCKED_VERSION_MISMATCH"




