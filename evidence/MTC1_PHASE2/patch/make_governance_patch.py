#!/usr/bin/env python3
"""Generate the hardened toolplane module + unified diff for MTC-1.0 B5-a.

Reads the deployed hg_tool_plane.py (source of truth pulled from the phone via
`adb pull "/sdcard/Phần Mềm HG/toolplane"`) and produces:
  - hg_tool_plane.hardened.py   (governance_decide replaced, gap closed)
  - hg_tool_plane.governance.patch (unified diff, original -> hardened)

The ONLY semantic change is governance_decide(): every tool that can have a side
effect (i.e. not read-only) must be canonical-mapped AND available AND allowing.
An unmapped side-effect tool is DENIED by default instead of silently allowed.
No write capability is widened.
"""
from __future__ import annotations
import difflib
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "hg_tool_plane.original.py"
OUT_PY = HERE / "hg_tool_plane.hardened.py"
OUT_PATCH = HERE / "hg_tool_plane.governance.patch"

OLD = '''def governance_decide(tool, args, call_id):
    """Trả (allow: bool, lý do: str, quyết định canonical). Chính sách: fail-closed cho thao tác ghi."""
    dec = canonical_decision(tool, args, call_id)
    ro = tool in READ_ONLY or (tool == "github_api" and str(args.get("method", "GET")).upper() == "GET")
    if not (isinstance(dec, dict) and "mapped" in dec and "available" in dec):
        dec = {"available": False, "mapped": True, "ok": None, "error": "INVALID_CANONICAL_RESPONSE"}
    if dec.get("mapped") and dec.get("ok") is False and not ro:
        return False, "CANONICAL_GOVERNANCE_DENY: " + str(dec.get("denied") or dec.get("error") or dec.get("witness")), dec
    if dec.get("mapped") and not dec.get("available") and not ro:
        return False, "CANONICAL_GOVERNANCE_UNAVAILABLE (fail-closed)", dec
    return True, "ok", dec
'''

NEW = '''def is_read_only(tool, args):
    """A tool is read-only if it is declared read-only, or it is github_api with GET."""
    if tool in READ_ONLY:
        return True
    if tool == "github_api" and str((args or {}).get("method", "GET")).upper() == "GET":
        return True
    return False

def governance_decide(tool, args, call_id):
    """Fail-closed decision (MTC-1.0 B5-a).

    - Read-only tools may run even when canonical governance is unavailable
      (they cannot produce a side effect).
    - EVERY tool with a possible side effect (not read-only) MUST be:
        * canonically MAPPED  (else DENY: UNMAPPED_FAIL_CLOSED), AND
        * canonical AVAILABLE (else DENY), AND
        * canonically ALLOWING (else DENY).
    This closes the gap where an unmapped side-effect tool (vps_exec, github_api
    writes) was previously allowed while only a local deny-list applied.
    """
    ro = is_read_only(tool, args)
    dec = canonical_decision(tool, args, call_id)
    if not (isinstance(dec, dict) and "mapped" in dec and "available" in dec):
        dec = {"available": False, "mapped": True, "ok": None, "error": "INVALID_CANONICAL_RESPONSE"}
    if ro:
        return True, "read-only", dec
    if not dec.get("mapped"):
        return (False,
                "CANONICAL_GOVERNANCE_UNMAPPED_FAIL_CLOSED: " + str(tool) +
                " has side effects but no canonical adapter mapping", dec)
    if not dec.get("available"):
        return False, "CANONICAL_GOVERNANCE_UNAVAILABLE (fail-closed)", dec
    if dec.get("ok") is False:
        return False, "CANONICAL_GOVERNANCE_DENY: " + str(
            dec.get("denied") or dec.get("error") or dec.get("witness")), dec
    return True, "ok", dec
'''


def _write(path: pathlib.Path, text: str) -> None:
    """Write text WITHOUT newline translation (Windows default would emit CRLF,
    which breaks `git apply` against an LF file)."""
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def main() -> int:
    if not SRC.is_file():
        print("FATAL: missing source", SRC, file=sys.stderr)
        return 2
    src = SRC.read_bytes().decode("utf-8")
    nl = "\r\n" if "\r\n" in src else "\n"
    old = OLD.replace("\n", nl)
    new = NEW.replace("\n", nl)
    if old not in src:
        print("FATAL: governance_decide baseline not found verbatim", file=sys.stderr)
        return 3
    hardened = src.replace(old, new, 1)
    _write(OUT_PY, hardened)
    diff = difflib.unified_diff(
        src.splitlines(keepends=True), hardened.splitlines(keepends=True),
        fromfile="a/runtime/go_runtime/toolplane/hg_tool_plane.py",
        tofile="b/runtime/go_runtime/toolplane/hg_tool_plane.py",
    )
    _write(OUT_PATCH, "".join(diff))
    print("wrote", OUT_PY.name, "and", OUT_PATCH.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
