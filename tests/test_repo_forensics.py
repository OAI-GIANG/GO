"""Tests for the HG canonical repository-forensics capability.

Covers: determinism, exclusions, module map, duplicate detection, parity/drift,
report digest stability, and the governed tool's root-bounded security boundary.
No network, no subprocess.
"""
from __future__ import annotations

import json
import os

import pytest

from runtime.go_runtime.core.engine import repo_forensics as rf
from runtime.go_runtime.core.tool_runtime import RepoForensicsTool, ToolContext


def _write(root, rel, text):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def test_inventory_is_deterministic(tmp_path):
    _write(tmp_path, "a.py", "x = 1\n")
    _write(tmp_path, "pkg/b.py", "def f():\n    return 2\n")
    first = rf.file_inventory(tmp_path)
    second = rf.file_inventory(tmp_path)
    assert first == second
    assert set(first) == {"a.py", "pkg/b.py"}
    assert first["a.py"]["sha256"].startswith("sha256:")
    assert first["a.py"]["bytes"] == os.path.getsize(tmp_path / "a.py")


def test_inventory_excludes_vcs_and_caches(tmp_path):
    _write(tmp_path, "keep.py", "y = 1\n")
    _write(tmp_path, "__pycache__/keep.cpython-314.pyc", "junk")
    _write(tmp_path, ".git/config", "junk")
    inv = rf.file_inventory(tmp_path)
    assert list(inv) == ["keep.py"]


def test_module_imports_and_parse_error(tmp_path):
    _write(tmp_path, "good.py", "import os\nfrom pkg import thing\n")
    _write(tmp_path, "bad.py", "def broken(:\n")
    mm = rf.module_imports(tmp_path)
    assert mm["good.py"]["parse"] == "ok"
    assert "os" in mm["good.py"]["imports"]
    assert mm["bad.py"]["parse"] == "error"


def test_duplicate_candidates_detects_copied_function(tmp_path):
    body = "def compute(a, b):\n    return a * b + 1\n"
    _write(tmp_path, "one.py", body + "\ndef unique_only(x):\n    return x - 7\n")
    _write(tmp_path, "two.py", body)
    dup = rf.duplicate_candidates(tmp_path)
    assert len(dup) == 1
    locs = dup[0]["locations"]
    assert any(l.startswith("one.py") for l in locs) and any(l.startswith("two.py") for l in locs)
    # the unique function must NOT be reported as duplicated
    assert not any("unique_only" in l for l in locs)


def test_duplicate_ignores_docstring_differences(tmp_path):
    _write(tmp_path, "a.py", 'def f():\n    """doc a"""\n    return 1\n')
    _write(tmp_path, "b.py", 'def f():\n    """doc b, different"""\n    return 1\n')
    dup = rf.duplicate_candidates(tmp_path)
    assert len(dup) == 1


def test_parity_detects_mismatch_missing_extra(tmp_path):
    _write(tmp_path, "same.py", "value = 10\n")
    _write(tmp_path, "drift.py", "value = 11\n")
    local = rf.file_inventory(tmp_path)
    canonical = {
        "same.py": local["same.py"]["sha256"],
        "drift.py": "sha256:" + "0" * 64,
        "absent.py": "sha256:" + "1" * 64,
    }
    result = rf.parity(local, canonical)
    assert result["match"] is False
    assert result["missing"] == ["absent.py"]
    assert [m["path"] for m in result["mismatch"]] == ["drift.py"]
    assert "drift.py" not in result["extra"]


def test_forensic_report_digest_is_stable_and_self_excluding(tmp_path):
    _write(tmp_path, "m.py", "def f():\n    return 1\n")
    r1 = rf.forensic_report(tmp_path)
    r2 = rf.forensic_report(tmp_path)
    assert r1["report_sha256"] == r2["report_sha256"]
    without = {k: v for k, v in r1.items() if k != "report_sha256"}
    assert r1["report_sha256"] == rf.digest(without)
    # any content change must change the digest (tamper-evidence)
    _write(tmp_path, "m.py", "def f():\n    return 2\n")
    assert rf.forensic_report(tmp_path)["report_sha256"] != r1["report_sha256"]


def test_repo_forensics_has_no_network_or_subprocess():
    import ast as _ast
    tree = _ast.parse(open(rf.__file__, encoding="utf-8").read())
    banned = {"subprocess", "socket", "urllib", "requests", "http", "ftplib", "asyncio"}
    for node in _ast.walk(tree):
        if isinstance(node, _ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in banned, alias.name
        elif isinstance(node, _ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in banned, node.module
        elif isinstance(node, _ast.Call):
            func = node.func
            assert not (isinstance(func, _ast.Attribute) and func.attr in {"system", "popen", "spawnl", "spawnv", "execv"}), _ast.dump(func)


def test_tool_root_bound_rejects_outside(tmp_path, monkeypatch):
    monkeypatch.setenv("HG_FORENSICS_ROOT", str(tmp_path))
    tool = RepoForensicsTool()
    allowed = tool.invoke({"root": str(tmp_path)}, ToolContext("T-BOUND-OK"))
    assert allowed["status"] == 200
    with pytest.raises(PermissionError):
        tool.invoke({"root": str(tmp_path.parent)}, ToolContext("T-BOUND-BAD"))


def test_tool_modes_return_bounded_output(tmp_path, monkeypatch):
    monkeypatch.setenv("HG_FORENSICS_ROOT", str(tmp_path))
    _write(tmp_path, "a.py", "def f():\n    return 1\n")
    _write(tmp_path, "b.py", "def f():\n    return 1\n")
    tool = RepoForensicsTool()
    inv = tool.invoke({"root": str(tmp_path), "mode": "inventory"}, ToolContext("T-M1"))
    assert inv["data"]["files"] == 2
    dup = tool.invoke({"root": str(tmp_path), "mode": "duplicates"}, ToolContext("T-M2"))
    assert dup["data"]["duplicate_groups"] == 1
    rep = tool.invoke({"root": str(tmp_path)}, ToolContext("T-M3"))
    assert rep["data"]["schema"] == rf.SCHEMA
    assert "report_sha256" in rep["data"]


def test_bom_file_is_parsed_and_reported(tmp_path):
    (tmp_path / "bom.py").write_bytes(b"\xef\xbb\xbf" + b"def f():\n    return 1\n")
    _write(tmp_path, "plain.py", "def g():\n    return 2\n")
    mm = rf.module_imports(tmp_path)
    assert mm["bom.py"]["parse"] == "ok"
    report = rf.forensic_report(tmp_path)
    assert report["parse_errors"] == []
    assert report["bom_files"] == ["bom.py"]


def test_exclude_dirs_keeps_digest_stable_over_volatile_subtree(tmp_path):
    _write(tmp_path, "src/a.py", "x = 1\n")
    _write(tmp_path, "data/audit.jsonl", "line\n")
    before = rf.forensic_report(tmp_path, exclude_dirs=("data",))
    _write(tmp_path, "data/audit.jsonl", "line\nline\n")  # volatile growth
    after = rf.forensic_report(tmp_path, exclude_dirs=("data",))
    assert before["report_sha256"] == after["report_sha256"]
    assert rf.forensic_report(tmp_path)["report_sha256"] != before["report_sha256"]
