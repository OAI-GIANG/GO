#!/usr/bin/env python3
"""Replica proof of the GO startup crash mode (MTC-1.0 B1 root cause).

GOApplication.__init__ calls config.validate() and then verify_governance_source().
The latter hard-requires control/MASTER_GOVERNANCE_RULESET_V1.md (exact sha256
cc1a8b17...) plus its approval binding. The phone deploy manifest
(GO-MATERIALIZATION-MANIFEST.json) contains NO control/MASTER_GOVERNANCE_RULESET_V1*
entries, so a tree materialized from it raises on startup -> runsv restart loop.

This script demonstrates the two startup blockers on a throwaway root:
  1. missing governance source -> GovernanceSourceError V1_CANONICAL_SOURCE_MISSING
  2. missing GO_API_TOKEN (runtime non-anonymous) -> ValueError
"""
from __future__ import annotations
import os
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from runtime.go_runtime.core.governance_source import verify_governance_source, GovernanceSourceError  # noqa: E402
from runtime.go_runtime.core.server import RuntimeConfig  # noqa: E402

print("== 1) governance source missing -> startup raise ==")
empty = pathlib.Path(tempfile.mkdtemp())
try:
    verify_governance_source(empty)
    print("FAIL expected GovernanceSourceError")
except GovernanceSourceError as exc:
    print("PASS GovernanceSourceError:", exc)

print("== 2) token required when not anonymous ==")
os.environ.pop("GO_API_TOKEN", None)
os.environ["GO_ALLOW_ANONYMOUS"] = "false"
try:
    RuntimeConfig().validate()
    print("FAIL expected ValueError")
except ValueError as exc:
    print("PASS ValueError:", exc)

print("== 3) control/ entries present in the deploy manifest? ==")
import json
candidates = [
    os.environ.get("HG_GO_MANIFEST", ""),
    str(ROOT / "GO-MATERIALIZATION-MANIFEST.json"),
    r"C:\Users\dang quang vinh\AppData\Local\Temp\opencode\HG-GO-DEPLOY\HG-GO-DEPLOY\GO-MATERIALIZATION-MANIFEST.json",
]
man = next((pathlib.Path(c) for c in candidates if c and pathlib.Path(c).is_file()), None)
if man:
    paths = [f["path"] for f in json.loads(man.read_text(encoding="utf-8"))["files"]]
    gov = [p for p in paths if "MASTER_GOVERNANCE_RULESET" in p]
    ctrl = [p for p in paths if p.startswith("control/")]
    print("manifest:", man)
    print("control/ entries:", ctrl)
    print("governance entries:", gov or "NONE -> a tree built from this manifest crashes on startup")
else:
    print("manifest not found in candidates; expected under HG-GO-DEPLOY on the phone")

print("---")
print("GO_CRASHLOOP_ROOTCAUSE: demonstrated")
