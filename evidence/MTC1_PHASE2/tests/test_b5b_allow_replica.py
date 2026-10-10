#!/usr/bin/env python3
"""B5-b replica test: canonical ALLOW mechanics + DENY fail-closed (MTC-1.0).

Runs the REAL canonical components (AuthorityRoot, ToolGovernance, go_kernel,
tool_runtime) against a locally provisioned EXTERNAL root key file — the same
pattern used by tests/test_b1_b5_contracts.py. Proves the mechanics the phone must
exhibit once an external owner provisions the root. REPLICA evidence only, NOT a
phone runtime PASS.

Proven:
  DENY  : no external root key -> AuthorityRoot.instance() raises AUTHORITY_ROOT_NOT_PROVISIONED.
  DENY  : an ephemeral (self) root cannot issue -> AUTHORITY_ROOT_NOT_TRUSTED.
  DENY  : revocation requested without HG_AUTHORITY_REVOCATION_FILE -> store not configured.
  DENY  : no authority token file -> AUTHORITY_PROVENANCE_MISSING (fail-closed).
  ALLOW : external root + issued task/tool-scoped token -> COMPLETED + witness,
          ledger ACCEPTED..STARTED..COMPLETED, governance_source_sha256 bound.
  IDEMP : duplicate semantic call denied (IDEMPOTENT_RESULT_REUSE_DENIED).
"""
from __future__ import annotations
import json
import os
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from runtime.go_runtime.core.authority import AuthorityRoot, AuthorityError  # noqa: E402
from runtime.go_runtime.core.tool_governance import ToolGovernance          # noqa: E402
from runtime.go_runtime.core.tool_runtime import ToolAdapter, ToolRegistry, ToolSpec  # noqa: E402

results: list[tuple[str, bool]] = []


def check(name: str, cond: bool, extra: str = "") -> None:
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + ((" " + extra) if extra else ""))


class EchoTool(ToolAdapter):
    def spec(self) -> ToolSpec:
        return ToolSpec("echo.tool", "replica echo tool",
                        {"type": "object", "properties": {"v": {"type": "string"}},
                         "additionalProperties": False}, True, False, "test.replica")

    def invoke(self, arguments, context):
        return {"echo": arguments.get("v")}


tmp = pathlib.Path(tempfile.mkdtemp())
key = tmp / "root.key"
key.write_bytes(b"replica-external-authority-key")
token_file = tmp / "authority-token.json"
ledger = tmp / "events.jsonl"

# --- 1) DENY: no external root key -> hard blocker ---
os.environ.pop("HG_AUTHORITY_ROOT_KEY_FILE", None)
AuthorityRoot._instance = None
try:
    AuthorityRoot.instance()
    check("deny_root_not_provisioned", False, "(instance unexpectedly constructed)")
except AuthorityError as exc:
    check("deny_root_not_provisioned", "AUTHORITY_ROOT_NOT_PROVISIONED" in str(exc), str(exc))

# --- 2) DENY: an ephemeral (self) root cannot issue ---
ephemeral = AuthorityRoot()
check("deny_ephemeral_not_external", ephemeral.is_external() is False, ephemeral.provenance())
try:
    ephemeral.issue(subject="HG_SESSION_T", scope=["tool:x"], action="execute", audience="tool:x", ttl_s=60)
    check("deny_issue_not_trusted", False, "(issue unexpectedly allowed)")
except AuthorityError as exc:
    check("deny_issue_not_trusted", "AUTHORITY_ROOT_NOT_TRUSTED" in str(exc), str(exc))

# --- 3) DENY: revocation without a configured store ---
try:
    ephemeral.revoke("AUTH-x")
    check("deny_revocation_store_unconfigured", False, "(revoke unexpectedly allowed)")
except AuthorityError as exc:
    check("deny_revocation_store_unconfigured", "REVOCATION_STORE_NOT_CONFIGURED" in str(exc), str(exc))

# --- 4) DENY: no token file -> AUTHORITY_PROVENANCE_MISSING ---
os.environ["HG_AUTHORITY_ROOT_KEY_FILE"] = str(key)
os.environ["HG_TOOL_AUTHORITY_SUBJECT"] = "HG_SESSION_T"
os.environ["HG_TOOL_AUTHORITY_TOKEN_FILE"] = str(tmp / "absent.json")
AuthorityRoot._instance = None
reg = ToolRegistry()
reg.register(EchoTool())
r = ToolGovernance(reg, ledger).execute("TASK-1", "echo.tool", {"v": "hi"})
check("deny_provenance_missing", r.ok is False and r.output.get("error") == "AUTHORITY_PROVENANCE_MISSING",
      str(r.output.get("error")))

# --- 5) ALLOW: external root + issued scoped token -> COMPLETED + witness + ledger ---
root = AuthorityRoot.instance()
check("allow_root_external", root.is_external() is True, root.provenance())
token = root.issue(subject="HG_SESSION_T", scope=["tool:echo.tool", "task:TASK-2"],
                   action="execute", audience="tool:echo.tool", ttl_s=60)
token_file.write_text(json.dumps(token.to_dict()), encoding="utf-8")
os.environ["HG_TOOL_AUTHORITY_TOKEN_FILE"] = str(token_file)
reg2 = ToolRegistry()
reg2.register(EchoTool())
gov = ToolGovernance(reg2, ledger)
r2 = gov.execute("TASK-2", "echo.tool", {"v": "hi"}, "not_required", "CALL-ALLOW-1")
check("allow_completed", r2.ok is True and r2.output.get("echo") == "hi", json.dumps(r2.output))
check("allow_witness_bound", r2.witness.get("scope") == "tool:echo.tool" and "witness_digest" in r2.witness)
check("allow_governance_source_bound", bool(gov._governance_source_sha256), str(gov._governance_source_sha256))
states = [e["state"] for e in gov.ledger.events("CALL-ALLOW-1")]
check("allow_ledger_started_completed",
      states[:1] == ["ACCEPTED"] and "STARTED" in states and states[-1] == "COMPLETED", str(states))

# --- 6) idempotency: same semantic call, new call_id -> denied ---
r3 = gov.execute("TASK-2", "echo.tool", {"v": "hi"}, "not_required", "CALL-ALLOW-2")
check("allow_idempotent_denied",
      r3.ok is False and r3.output.get("error") == "IDEMPOTENT_RESULT_REUSE_DENIED",
      str(r3.output.get("error")))

print("---")
print("B5B_ALLOW_REPLICA: %s" % ("PASS" if all(c for _, c in results) else "FAIL"))
sys.exit(0 if all(c for _, c in results) else 1)
