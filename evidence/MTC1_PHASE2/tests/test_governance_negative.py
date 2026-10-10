#!/usr/bin/env python3
"""Negative/contract tests for hardened toolplane governance (MTC-1.0 B5-a).

Exercises governance_decide() with injected canonical responses (no network) and
governance_check() for the destructive deny-list. Verifies:
  * read-only tools are allowed even when canonical governance is unavailable;
  * a side-effect tool is DENIED when canonical DENIES;
  * a side-effect tool is DENIED (fail-closed) when canonical is UNAVAILABLE;
  * a side-effect tool is DENIED on a MALFORMED canonical response;
  * an UNMAPPED side-effect tool is DENIED by default (gap closed);
  * the destructive deny-list blocks regardless of approved=true.
"""
from __future__ import annotations
import importlib.util
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
HARD = HERE.parent / "patch" / "hg_tool_plane.hardened.py"

spec = importlib.util.spec_from_file_location("hgtp_hardened", HARD)
H = importlib.util.module_from_spec(spec)
spec.loader.exec_module(H)  # type: ignore[union-attr]

MAPPED_OK = {"available": True, "mapped": True, "ok": True}
MAPPED_DENY = {"available": True, "mapped": True, "ok": False, "denied": "AUTHORITY_DENIED"}
MAPPED_UNAVAIL = {"available": False, "mapped": True, "ok": None, "error": "no ops token"}
MALFORMED = {"weird": 1}  # no 'mapped'/'available' keys
UNMAPPED = {"available": True, "mapped": False, "ok": None}

results = []


def decide_with(dec, tool, args=None):
    H.canonical_decision = lambda t, a, c, _d=dec: _d
    return H.governance_decide(tool, args or {}, "CALL-TEST")


def case(name, dec, tool, args, want_allow, want_prefix=None):
    allow, why, _d = decide_with(dec, tool, args)
    ok = (allow == want_allow) and (want_prefix is None or why.startswith(want_prefix))
    results.append((name, ok, allow, why))
    print(("PASS " if ok else "FAIL ") + name + " -> allow=%s why=%s" % (allow, why))


# read-only surfaces are never blocked by canonical state
case("ro_go_health_unavailable_allowed", MAPPED_UNAVAIL, "go_health", {}, True)
case("ro_phone_health_unavailable_allowed", MAPPED_UNAVAIL, "phone_health", {}, True)
case("ro_github_get_unavailable_allowed", MAPPED_UNAVAIL, "github_api", {"method": "GET", "path": "/user"}, True)

# side-effect tools: mapped + allow / deny / unavailable / malformed
case("write_mapped_allow", MAPPED_OK, "vps_exec", {"host": "vps1", "cmd": "ls"}, True)
case("write_mapped_deny", MAPPED_DENY, "vps_exec", {"host": "vps1", "cmd": "ls"}, False, "CANONICAL_GOVERNANCE_DENY")
case("write_mapped_unavailable_failclosed", MAPPED_UNAVAIL, "vps_exec", {"host": "vps1", "cmd": "ls"}, False, "CANONICAL_GOVERNANCE_UNAVAILABLE")
case("write_malformed_failclosed", MALFORMED, "vps_exec", {"host": "vps1", "cmd": "ls"}, False, "CANONICAL_GOVERNANCE_UNAVAILABLE")

# side-effect tools with NO canonical mapping: default-deny (gap closed)
case("write_unmapped_default_deny", UNMAPPED, "vps_exec", {"host": "vps1", "cmd": "ls"}, False, "CANONICAL_GOVERNANCE_UNMAPPED_FAIL_CLOSED")
case("github_write_unmapped_default_deny", UNMAPPED, "github_api", {"method": "POST", "path": "/repos/OAI-GIANG/GO/git/refs"}, False, "CANONICAL_GOVERNANCE_UNMAPPED_FAIL_CLOSED")

# destructive deny-list is independent of approved flag
dl = [
    ("denylist_rmrf", H.governance_check("vps_exec", {"cmd": "rm -rf /", "approved": True}) is not None),
    ("denylist_dd", H.governance_check("vps_exec", {"cmd": "dd if=/dev/zero of=/dev/sda", "approved": True}) is not None),
    ("denylist_delete", H.governance_check("github_api", {"method": "DELETE", "path": "/repos/OAI-GIANG/GO", "approved": True}) is not None),
    ("allow_benign", H.governance_check("vps_exec", {"cmd": "ls -la"}) is None),
]
for name, ok in dl:
    results.append((name, ok, "-", "-"))
    print(("PASS " if ok else "FAIL ") + name)

bad = [r for r in results if not r[1]]
print("---")
print("GOVERNANCE_NEGATIVE: %s (%d/%d)" % ("PASS" if not bad else "FAIL", len(results) - len(bad), len(results)))
sys.exit(0 if not bad else 1)
