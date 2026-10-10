"""HG canonical objective router + failure policy.

Distils objective-driven autonomy into a single bounded, deterministic,
model-independent capability:

  OBJECTIVE -> normalize -> understand -> discover (ToolRegistry)
            -> filter -> bounded selection -> plan
            -> (orchestrator) govern -> broker -> durable execute
            -> observe -> classify failure -> bounded recovery/replan -> evidence

Design invariants:
  * model-independent: no model, no network, no subprocess, no hidden state
  * bounded: <= MAX_STEPS plan, <= MAX_RETRY retries, <= MAX_REPLAN replans
  * fail-closed: unknown -> NO_MATCH, ambiguous -> AMBIGUOUS, forbidden -> UNAUTHORIZED
  * no authority creation and no governance bypass: every step is executed by the
    caller through the existing ToolRegistry -> ToolGovernance -> CredentialBroker path
  * generic: selection is a policy over verbs/nouns discovered from the live registry,
    not a hard-coded single tool

Canonical owner: HG runtime engine (objective/planning policy capability).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any, Callable

from .. import epistemics

SCHEMA = "HG-OBJECTIVE-ROUTER-V1"
DEFAULT_REF = os.getenv("HG_DEFAULT_REF", "hg-core")
DEFAULT_REPO = os.getenv("HG_DEFAULT_REPO", "OAI-GIANG/GO")
MAX_STEPS = 3
MAX_RETRY = 1
MAX_REPLAN = 1

# ---------------------------------------------------------------- failure taxonomy
FAILURE_TAXONOMY: dict[str, dict[str, str]] = {
    "AUTHORIZATION_FAILURE": {"recoverable": "none"},
    "CREDENTIAL_FAILURE": {"recoverable": "none"},
    "ARGUMENT_FAILURE": {"recoverable": "none"},
    "CAPABILITY_UNAVAILABLE": {"recoverable": "replan"},
    "TRANSIENT_FAILURE": {"recoverable": "retry"},
    "TARGET_UNAVAILABLE": {"recoverable": "replan"},
    "POLICY_BLOCK": {"recoverable": "none"},
    "TIMEOUT": {"recoverable": "retry"},
    "IDEMPOTENCY_DUPLICATE": {"recoverable": "none"},
    "NON_RECOVERABLE": {"recoverable": "none"},
    "UNKNOWN": {"recoverable": "none"},
}

# ---------------------------------------------------------------- vocabulary
_VERBS: dict[str, str] = {}
for _syn, _canon in {
    "read": "read", "get": "read", "show": "read", "report": "read", "inspect": "read",
    "list": "read", "audit": "read", "check": "read", "verify": "read", "fetch": "read", "view": "read",
    "create": "create", "open": "create", "make": "create", "add": "create",
    "write": "write", "put": "write",
    "update": "update", "modify": "update",
    "comment": "comment", "reply": "comment",
    "dispatch": "dispatch", "trigger": "dispatch",
    "rerun": "rerun",
    "delete": "delete", "remove": "delete", "clean": "delete", "cleanup": "delete", "drop": "delete",
}.items():
    _VERBS[_syn] = _canon

_NOUNS: dict[str, str] = {}
for _syn, _canon in {
    "repository": "repository", "repo": "repository", "metadata": "repository", "project": "repository",
    "branch": "branch", "ref": "branch", "file": "file", "content": "file", "contents": "file",
    "pull": "pr", "pr": "pr", "release": "release", "releases": "release", "tag": "release",
    "issue": "issue", "commit": "commit", "workflow": "workflow", "action": "workflow",
    "ci": "checkrun", "checkrun": "checkrun", "check-runs": "checkrun",
    "health": "health", "healthy": "health", "edge": "health", "backend": "health", "vps": "health", "vps1": "health", "vps2": "health",
    "duplicate": "forensic", "duplicates": "forensic", "drift": "forensic", "parity": "forensic",
    "forensic": "forensic", "plane": "forensic", "planes": "forensic",
    "model": "model", "inference": "model", "summarise": "model", "summarize": "model",
    "summarise,": "model", "reason": "model", "prompt": "model", "ask": "model",
}.items():
    _NOUNS[_syn] = _canon

_DENY_PATTERNS = (
    r"delete\s+(the\s+)?repo(sitory)?\b",
    r"delete\s+(the\s+)?(organi[sz]ation)\b",
    r"merge\s+(the\s+)?(pull\s*request|pr)\b",
    r"force[-\s]?push",
    r"repository\s+settings",
    r"(org|organi[sz]ation)\s+admin",
    r"add\s+secret",
    r"change\s+permissions",
    r"make\s+(public|private)",
    r"transfer\s+ownership",
    r"delete\s+(the\s+)?(workflow|release)\b",
)


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


# ---------------------------------------------------------------- capability discovery
def operation_class(read_only: bool, destructive: bool) -> str:
    if destructive:
        return "DESTRUCTIVE"
    if read_only:
        return "READ_ONLY"
    return "MUTATING"


def discover(registry: Any, builtins: tuple[str, ...] = ("echo", "ask")) -> list[dict[str, Any]]:
    """Capability catalogue from the live ToolRegistry (+ builtin operations)."""
    caps: list[dict[str, Any]] = []
    for name, adapter in sorted(getattr(registry, "_tools", {}).items()):
        spec = adapter.spec()
        caps.append({
            "operation": name,
            "description": spec.description,
            "kind": "tool",
            "operation_class": operation_class(spec.read_only, spec.destructive),
            "read_only": spec.read_only,
            "destructive": spec.destructive,
            "required": list(spec.input_schema.get("required", [])),
            "signals": sorted(set(_tokens(name.replace(".", " ")) + _tokens(spec.description))),
        })
    for b in builtins:
        caps.append({
            "operation": b, "description": f"builtin {b}", "kind": "builtin",
            "operation_class": "READ_ONLY", "read_only": True, "destructive": False,
            "required": [], "signals": [b],
        })
    return caps


# ---------------------------------------------------------------- understanding
def understand(objective: str) -> dict[str, Any]:
    toks = _tokens(objective)
    return {
        "objective": objective,
        "tokens": toks,
        "verbs": [_VERBS[t] for t in toks if t in _VERBS],
        "nouns": [_NOUNS[t] for t in toks if t in _NOUNS],
        "entities": entities(objective),
        "forbidden": [p for p in _DENY_PATTERNS if re.search(p, objective.lower())],
    }


def entities(objective: str) -> dict[str, str]:
    def clean(v: str) -> str:
        return v.rstrip(".,;:!?)]}\"'")
    out: dict[str, str] = {}
    m = re.search(r"\b([A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*)\b", objective)
    if m:
        out["repository"] = clean(m.group(1))
    m = re.search(r"\bbranch\s+(?:named\s+|called\s+)?([A-Za-z0-9_./-]+)", objective)
    if m:
        out["branch"] = clean(m.group(1))
    m = re.search(r"\b(?:named|called)\s+([A-Za-z0-9_./-]+)", objective)
    if m and "branch" not in out:
        out["branch"] = clean(m.group(1))
    m = re.search(r"\b(?:file|files|contents?)\s+([A-Za-z0-9_./-]+\.[A-Za-z0-9]+)", objective)
    if m:
        out["path"] = clean(m.group(1))
    m = re.search(r"\b(?:pr|pull request|issue)\s*#?\s*(\d+)", objective)
    if m:
        out["number"] = m.group(1)
    return out


# ---------------------------------------------------------------- bounded selection
def _plan_step(verb: str, noun: str, e: dict[str, str]) -> dict[str, Any] | None:
    repo = e.get("repository", DEFAULT_REPO)
    ref = e.get("branch", DEFAULT_REF)
    if noun == "forensic":
        return {"operation": "hg.repo.forensics", "payload": {"root": e.get("root", "/opt/go"), "mode": "duplicates"}}
    if noun == "health":
        obj = e.get("_objective", "")
        if "vps1" in obj or "edge" in obj:
            return {"operation": "vps1.edge.health", "payload": {}}
        if "vps2" in obj or "backend" in obj:
            return {"operation": "vps2.health", "payload": {}}
        return {"operation": "vps2.health", "payload": {}}
    if noun == "model":
        return {"operation": "ask", "payload": {"prompt": e.get("_objective", "")}}
    if noun == "repository":
        return {"operation": "github.read_repo", "payload": {"repository": repo}} if verb == "read" else None
    if noun == "branch":
        if verb == "read":
            return {"operation": "github.read_branch", "payload": {"repository": repo, "branch": ref}}
        if verb == "create":
            return {"operation": "github.create_branch", "payload": {"repository": repo, "branch": ref, "from_ref": DEFAULT_REF}}
        if verb == "delete":
            return {"operation": "github.delete_branch", "payload": {"repository": repo, "branch": ref}}
        return None
    if noun == "file":
        if verb == "read":
            return {"operation": "github.read_file", "payload": {"repository": repo, "path": e.get("path", "README.md"), "ref": ref}}
        if verb in {"write", "create"}:
            return {"operation": "github.write_file", "payload": {"repository": repo, "branch": ref, "path": e.get("path", "CL6_PROOF.txt"), "content": "cl6 proof\n", "message": "cl6 objective"}}
        return None
    if noun == "pr":
        if verb == "read":
            return {"operation": "github.read_pr", "payload": {"repository": repo, "number": e.get("number", "1")}}
        if verb == "create":
            head = e.get("branch", ref)
            return {"operation": "github.create_pr", "payload": {"repository": repo, "title": "CL6 bounded change", "head": head, "base": DEFAULT_REF}}
        return None
    if noun == "issue":
        if verb == "read":
            return {"operation": "github.read_issue", "payload": {"repository": repo, "number": e.get("number", "1")}}
        if verb == "create":
            return {"operation": "github.create_issue", "payload": {"repository": repo, "title": "CL6 issue"}}
        if verb == "comment":
            return {"operation": "github.comment_issue", "payload": {"repository": repo, "number": e.get("number", "1"), "body": "cl6"}}
        return None
    if noun == "commit":
        return {"operation": "github.read_commit", "payload": {"repository": repo, "ref": ref}} if verb == "read" else None
    if noun == "release":
        return {"operation": "github.read_releases", "payload": {"repository": repo}} if verb == "read" else None
    if noun == "checkrun":
        return {"operation": "github.read_check_runs", "payload": {"repository": repo, "ref": ref}} if verb == "read" else None
    if noun == "workflow":
        if verb == "read":
            return {"operation": "github.read_workflow", "payload": {"repository": repo, "workflow_id": e.get("workflow_id", "ci.yml")}}
        if verb == "dispatch":
            return {"operation": "github.dispatch_workflow", "payload": {"repository": repo, "workflow_id": e.get("workflow_id", "ci.yml"), "ref": ref}}
        if verb == "rerun":
            return {"operation": "github.rerun_workflow", "payload": {"repository": repo, "run_id": e.get("run_id", "1")}}
        return None
    return None


def select(objective: str, catalogue: list[dict[str, Any]], *, default_ref: str = DEFAULT_REF) -> dict[str, Any]:
    """Bounded deterministic selection over the discovered catalogue."""
    u = understand(objective)
    e = dict(u["entities"])
    e["_objective"] = objective
    names = {c["operation"] for c in catalogue}
    result: dict[str, Any] = {"intent": {"verbs": u["verbs"], "nouns": u["nouns"]}, "candidates": [], "steps": []}
    if u["forbidden"]:
        result.update({"status": "UNAUTHORIZED", "refusal": {"code": "UNAUTHORIZED_OBJECTIVE", "matched": u["forbidden"]}})
        return result
    low = objective.lower()
    # composite: create a branch + write a file (+ bounded cleanup)
    if re.search(r"\bcreate\b.*\bbranch\b", low) and re.search(r"\b(write|create)\b.*\bfile\b", low):
        repo = e.get("repository", DEFAULT_REPO)
        branch = e.get("branch") or ("hg-cl6-" + hashlib.sha256(objective.encode()).hexdigest()[:10])
        steps = [
            {"operation": "github.create_branch", "payload": {"repository": repo, "branch": branch, "from_ref": default_ref}},
            {"operation": "github.write_file", "payload": {"repository": repo, "branch": branch, "path": e.get("path", "CL6_PROOF.txt"), "content": "cl6 proof\n", "message": "cl6 objective"}},
        ]
        if re.search(r"\b(clean|cleanup|remove|delete|drop)\b", low):
            steps.append({"operation": "github.delete_branch", "payload": {"repository": repo, "branch": branch}})
        steps = [s for s in steps if s["operation"] in names][:MAX_STEPS]
        if steps:
            result.update({"status": "SELECTED", "selected": steps[0], "steps": steps})
            return result
    # primary action = first explicit verb + first noun
    verb = u["verbs"][0] if u["verbs"] else "read"
    noun = u["nouns"][0] if u["nouns"] else None
    if noun is not None:
        step = _plan_step(verb, noun, e)
        if step and step["operation"] in names:
            result.update({"status": "SELECTED", "selected": step, "steps": [step]})
            return result
    # generic token-overlap fallback (never a single fixed tool)
    toks = set(u["tokens"])
    scored = sorted(
        ({"operation": c["operation"], "score": len(toks & set(c["signals"]))} for c in catalogue),
        key=lambda x: (-x["score"], x["operation"]),
    )
    result["candidates"] = [c for c in scored if c["score"] > 0][:3]
    top = [c for c in scored if c["score"] == scored[0]["score"] and c["score"] > 0]
    if not top:
        result.update({"status": "NO_MATCH", "refusal": {"code": "NO_CAPABILITY_MATCH"}})
    elif len(top) > 1:
        result.update({"status": "AMBIGUOUS", "refusal": {"code": "AMBIGUOUS_OBJECTIVE", "candidates": [c["operation"] for c in top]}})
    else:
        step = {"operation": top[0]["operation"], "payload": {}}
        result.update({"status": "SELECTED", "selected": step, "steps": [step], "rationale": "token_overlap"})
    return result


# ---------------------------------------------------------------- failure classification + recovery
def classify_failure(*, ok: bool, output: dict[str, Any] | None, witness: dict[str, Any] | None) -> dict[str, Any]:
    if ok:
        return {"class": "SUCCESS", "recoverable": "none"}
    wstatus = str((witness or {}).get("status") or "")
    text = json.dumps(output or {}).lower()
    if wstatus == "DENIED":
        if "approval_required" in text:
            return {"class": "POLICY_BLOCK", "recoverable": "none", "reason": "APPROVAL_REQUIRED"}
        if "authority_provenance_missing" in text or "kernel" in text:
            return {"class": "AUTHORIZATION_FAILURE", "recoverable": "none", "reason": "AUTHORIZATION_DENIED"}
        if "arguments_invalid" in text:
            return {"class": "ARGUMENT_FAILURE", "recoverable": "none", "reason": "SCHEMA"}
        return {"class": "POLICY_BLOCK", "recoverable": "none", "reason": wstatus}
    if "permissionerror" in text or "credential not configured" in text or "credential_failure" in text:
        return {"class": "CREDENTIAL_FAILURE", "recoverable": "none", "reason": "CREDENTIAL"}
    if "github_http_404" in text or "not found" in text or "404" in text:
        return {"class": "TARGET_UNAVAILABLE", "recoverable": "replan", "reason": "404"}
    if "github_http_403" in text or "github_http_401" in text:
        return {"class": "AUTHORIZATION_FAILURE", "recoverable": "none", "reason": "http_403_401"}
    if "github_http_422" in text:
        return {"class": "ARGUMENT_FAILURE", "recoverable": "none", "reason": "http_422"}
    if "github_http_5" in text or "timeout" in text or "timed out" in text:
        return {"class": "TRANSIENT_FAILURE", "recoverable": "retry", "reason": "transient"}
    if "supports only bounded echo" in text or "provider unavailable" in text or "no provider" in text or "not registered with the canonical gateway" in text:
        return {"class": "CAPABILITY_UNAVAILABLE", "recoverable": "replan", "reason": "MODEL_PROVIDER_UNAVAILABLE"}
    if "tool_not_found" in text or "unsupported operation" in text:
        return {"class": "CAPABILITY_UNAVAILABLE", "recoverable": "replan", "reason": "unavailable"}
    return {"class": "UNKNOWN", "recoverable": "none", "reason": "unknown"}


def classify_exception(exc: Exception) -> dict[str, Any]:
    text = f"{type(exc).__name__} {exc}".lower()
    if "credential" in text or "permissionerror" in text:
        return {"class": "CREDENTIAL_FAILURE", "recoverable": "none", "reason": "CREDENTIAL"}
    if "supports only bounded echo" in text or "provider" in text or "gateway" in text:
        return {"class": "CAPABILITY_UNAVAILABLE", "recoverable": "replan", "reason": "MODEL_PROVIDER_UNAVAILABLE"}
    if "denied" in text:
        return {"class": "AUTHORIZATION_FAILURE", "recoverable": "none", "reason": "DENIED"}
    if "timeout" in text:
        return {"class": "TIMEOUT", "recoverable": "retry", "reason": "TIMEOUT"}
    return {"class": "UNKNOWN", "recoverable": "none", "reason": type(exc).__name__}


def replan(objective: str, failed_step: dict[str, Any], classification: dict[str, Any], *, default_ref: str = DEFAULT_REF) -> dict[str, Any] | None:
    """Bounded alternative for a recoverable failure. Never escalates authority."""
    op = failed_step.get("operation", "")
    payload = dict(failed_step.get("payload") or {})
    if classification.get("class") == "TARGET_UNAVAILABLE" and op in {
        "github.read_file", "github.read_branch", "github.read_commit", "github.read_check_runs"
    }:
        if payload.get("ref") != default_ref and payload.get("branch") != default_ref:
            alt = {"operation": op, "payload": {**payload, "ref": default_ref}}
            alt["payload"].pop("branch", None)
            if op == "github.read_branch":
                alt["payload"]["branch"] = default_ref
            return {"status": "SELECTED", "selected": {"operation": op, "payload": alt["payload"], "rationale": "bounded_fallback_default_ref"}, "steps": [alt]}
    if classification.get("class") == "CAPABILITY_UNAVAILABLE":
        return None
    return None


def orchestrate(
    objective: str,
    *,
    catalogue: list[dict[str, Any]],
    execute: Callable[[str, dict[str, Any], str], tuple[bool, dict[str, Any], dict[str, Any]]],
    default_ref: str = DEFAULT_REF,
    max_retry: int = MAX_RETRY,
    max_replan: int = MAX_REPLAN,
) -> dict[str, Any]:
    """Bounded objective loop. `execute(operation, payload, approval) -> (ok, output, witness)`."""
    trace: dict[str, Any] = {
        "schema": SCHEMA, "objective": objective, "catalogue_size": len(catalogue),
        "understanding": understand(objective), "selection": None, "attempts": [], "replans": [],
        "classification": None, "status": "PENDING", "final": None,
    }
    plan = select(objective, catalogue, default_ref=default_ref)
    trace["selection"] = {k: plan.get(k) for k in ("status", "intent", "candidates", "refusal", "steps")}
    if plan["status"] != "SELECTED":
        trace["status"] = plan["status"]
        trace["final"] = "REFUSED"
        return trace
    steps = plan["steps"]
    retries = 0
    replans = 0
    step_index = 0
    results: list[dict[str, Any]] = []
    while step_index < len(steps):
        step = steps[step_index]
        try:
            ok, output, witness = execute(step["operation"], step.get("payload") or {}, step.get("approval", "not_required"))
            cls = classify_failure(ok=ok, output=output, witness=witness)
        except Exception as exc:
            ok, output, witness = False, {"error": type(exc).__name__, "message": str(exc)}, {"status": "FAILED"}
            cls = classify_exception(exc)
            trace.setdefault("exceptions", []).append({"operation": step["operation"], "error": f"{type(exc).__name__}: {exc}"})
        trace["attempts"].append({"step": step_index, "operation": step["operation"], "ok": ok, "classification": cls.get("class")})
        trace["classification"] = cls
        results.append({"operation": step["operation"], "ok": ok, "output": output})
        if ok:
            step_index += 1
            continue
        if cls["recoverable"] == "retry" and retries < max_retry:
            retries += 1
            trace["replans"].append({"type": "retry", "operation": step["operation"], "reason": cls.get("reason")})
            continue
        if cls["recoverable"] == "replan" and replans < max_replan:
            alt = replan(objective, step, cls, default_ref=default_ref)
            if alt and alt.get("steps"):
                replans += 1
                trace["replans"].append({"type": "replan", "from": step["operation"], "to": alt["steps"][0]["operation"], "reason": cls.get("class")})
                steps = steps[:step_index] + alt["steps"] + steps[step_index + 1:]
                continue
        trace["status"] = "FAILED"
        trace["final"] = "FAILED"
        trace["result"] = results
        trace["terminal_reason"] = cls.get("class")
        return trace
    trace["status"] = "ROUTED"
    trace["final"] = "ROUTED"  # orchestration/completion != task success
    trace["result"] = results
    trace["result_sha256"] = _digest(results)
    trace["epistemics"] = epistemics.envelope(
        execution_state="COMPLETED",
        truth_status=epistemics.TruthStatus.UNVERIFIED.value,
        verification_status=epistemics.VerificationStatus.SELF_OBSERVED.value,
    )
    return trace
