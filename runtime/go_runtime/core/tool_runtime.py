from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any, Callable

TOOL_CONTRACT_VERSION = "TOOL-CONTRACT-V1"


def _digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]
    read_only: bool
    destructive: bool
    plugin_id: str
    plugin_version: str = "1.0.0"
    contract_version: str = TOOL_CONTRACT_VERSION

    def validate(self) -> None:
        if not self.name or not self.description or not self.plugin_id:
            raise ValueError("tool identity is required")
        if self.contract_version != TOOL_CONTRACT_VERSION:
            raise ValueError("unsupported tool contract version")
        if not isinstance(self.input_schema, dict) or self.input_schema.get("type") != "object":
            raise ValueError("tool input_schema must be an object schema")


@dataclass(frozen=True)
class ToolContext:
    task_id: str
    approval: str = "not_required"


@dataclass(frozen=True)
class ToolResult:
    call_id: str
    tool_name: str
    ok: bool
    output: dict[str, Any]
    witness: dict[str, Any]


class CredentialBroker:
    """Canonical credential boundary. Tools receive credentials; the model never does.

    Environment variables remain the primary runtime binding. For the canonical
    HG edge credential, a private service-owned file is the fallback source so
    the credential is not duplicated into the GO runtime configuration.
    """

    def get(self, credential_name: str) -> str:
        value = os.getenv(credential_name, "").strip()
        if value:
            return value
        path = os.getenv(credential_name + "_CREDENTIAL_FILE", "")
        if not path and credential_name == "HG_EDGE_TOKEN":
            path = "/etc/hg-edge/edge.env"
        if path:
            try:
                lines = [line.strip() for line in open(path, encoding="utf-8") if line.strip()]
                for line in lines:
                    if line.startswith(credential_name + "="):
                        value = line.split("=", 1)[1].strip().strip(chr(34)).strip(chr(39))
                        if value:
                            return value
                if len(lines) == 1 and "=" not in lines[0]:
                    return lines[0].strip().strip(chr(34)).strip(chr(39))
            except OSError:
                pass
        raise PermissionError("credential not configured: " + credential_name)


class ToolAdapter:
    def spec(self) -> ToolSpec:
        raise NotImplementedError

    def invoke(self, arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        raise NotImplementedError


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolAdapter] = {}

    def register(self, adapter: ToolAdapter) -> None:
        spec = adapter.spec()
        spec.validate()
        if spec.name in self._tools:
            raise ValueError("duplicate tool: " + spec.name)
        self._tools[spec.name] = adapter

    def specs(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": s.name,
                    "description": s.description,
                    "parameters": s.input_schema,
                },
            }
            for s in [self._tools[n].spec() for n in sorted(self._tools)]
        ]

    def metadata(self) -> list[dict[str, Any]]:
        return [
            {
                "name": s.name,
                "description": s.description,
                "input_schema": s.input_schema,
                "read_only": s.read_only,
                "destructive": s.destructive,
                "plugin_id": s.plugin_id,
                "plugin_version": s.plugin_version,
                "contract_version": s.contract_version,
            }
            for s in [self._tools[n].spec() for n in sorted(self._tools)]
        ]

    def dispatch(self, name: str, arguments: dict[str, Any], context: ToolContext, call_id: str | None = None) -> ToolResult:
        adapter = self._tools.get(name)
        if adapter is None:
            raise KeyError("tool not found: " + name)
        if not isinstance(arguments, dict):
            raise ValueError("tool arguments must be an object")
        cid = call_id or "CALL-" + uuid.uuid4().hex
        started = time.time()
        arg_digest = _digest(arguments)
        try:
            output = adapter.invoke(arguments, context)
            ok = True
            error = None
        except Exception as exc:
            output = {"error": type(exc).__name__, "message": str(exc)}
            ok = False
            error = type(exc).__name__
        witness = {
            "call_id": cid,
            "tool_name": name,
            "task_id": context.task_id,
            "arguments_digest": arg_digest,
            "output_digest": _digest(output),
            "status": "COMPLETED" if ok else "FAILED",
            "error_type": error,
            "latency_ms": int((time.time() - started) * 1000),
            "contract_version": TOOL_CONTRACT_VERSION,
        }
        return ToolResult(cid, name, ok, output, witness)


class GitHubRepoTool(ToolAdapter):
    def __init__(self, broker: CredentialBroker | None = None) -> None:
        self.broker = broker or CredentialBroker()

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="github.repo.get",
            description="Read metadata for a GitHub repository.",
            input_schema={
                "type": "object",
                "properties": {
                    "owner": {"type": "string"},
                    "repo": {"type": "string"},
                },
                "required": ["owner", "repo"],
                "additionalProperties": False,
            },
            read_only=True,
            destructive=False,
            plugin_id="go.github",
        )

    def invoke(self, arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        owner, repo = arguments["owner"].strip(), arguments["repo"].strip()
        if not owner or not repo or "/" in owner or "/" in repo:
            raise ValueError("invalid GitHub repository identity")
        token = self.broker.get("HG_GITHUB_TOKEN")
        req = urllib.request.Request(
            f"https://api.github.com/repos/{owner}/{repo}",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": "Bearer " + token,
                "X-GitHub-Api-Version": "2026-03-10",
                "User-Agent": "HG-Tool-Runtime/1.0",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.load(response)
                return {
                    "status": response.status,
                    "full_name": data.get("full_name"),
                    "default_branch": data.get("default_branch"),
                    "private": data.get("private"),
                    "permissions": data.get("permissions"),
                }
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"github_http_{exc.code}") from None


class VPS2HealthTool(ToolAdapter):
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="vps2.health",
            description="Read VPS2 durable backend health through the canonical edge path.",
            input_schema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            read_only=True,
            destructive=False,
            plugin_id="go.vps2",
        )

    def invoke(self, arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        base = os.getenv("HG_EDGE_URL", "").strip().rstrip("/")
        token = CredentialBroker().get("HG_EDGE_TOKEN")
        if not base:
            raise PermissionError("HG_EDGE_URL not configured")
        req = urllib.request.Request(
            base + "/backend/health",
            headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            return {"status": response.status, "body": json.load(response)}


class VPS1HealthTool(ToolAdapter):
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="vps1.edge.health",
            description="Read HG Edge health on VPS1.",
            input_schema={
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            read_only=True,
            destructive=False,
            plugin_id="go.vps1",
        )

    def invoke(self, arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        base = os.getenv("HG_EDGE_URL", "").strip().rstrip("/")
        if not base:
            raise PermissionError("HG_EDGE_URL not configured")
        req = urllib.request.Request(base + "/edge/health", headers={"Accept": "application/json"}, method="GET")
        with urllib.request.urlopen(req, timeout=15) as response:
            return {"status": response.status, "body": json.load(response)}


class RepoForensicsTool(ToolAdapter):
    """Governed, read-only, root-bounded repository forensics (deterministic, no network)."""

    def __init__(self) -> None:
        self._allowed_root = os.getenv("HG_FORENSICS_ROOT", "/opt/go").rstrip("/") or "/"
        self._spec = ToolSpec(
            name="hg.repo.forensics",
            description="Deterministic repository forensics: inventory / module_map / duplicates / parity(drift). Read-only, root-bounded, no network.",
            input_schema={
                "type": "object",
                "properties": {
                    "root": {"type": "string"},
                    "mode": {"type": "string"},
                    "exclude": {"type": "array"},
                    "canonical_manifest": {"type": "object"},
                },
                "required": ["root"],
                "additionalProperties": False,
            },
            read_only=True,
            destructive=False,
            plugin_id="go.hg",
        )

    def spec(self) -> ToolSpec:
        return self._spec

    def _resolve_root(self, root: str) -> str:
        from pathlib import Path
        base = Path(self._allowed_root).resolve()
        target = Path(root).resolve()
        if target != base and base not in target.parents:
            raise PermissionError("root_outside_HG_FORENSICS_ROOT")
        return str(target)

    def invoke(self, arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        from .engine import repo_forensics as rf
        root = self._resolve_root(str(arguments["root"]))
        mode = str(arguments.get("mode") or "report")
        raw_exclude = arguments.get("exclude")
        exclude = [str(x) for x in raw_exclude] if isinstance(raw_exclude, list) else None
        if mode == "inventory":
            inv = rf.file_inventory(root, exclude_dirs=exclude)
            return {"status": 200, "data": {"mode": mode, "files": len(inv), "inventory_sha256": rf.digest(inv)}}
        if mode == "module_map":
            mm = rf.module_imports(root, exclude_dirs=exclude)
            errors = sorted(p for p, m in mm.items() if m.get("parse") == "error")
            return {"status": 200, "data": {"mode": mode, "modules": len(mm), "parse_errors": errors}}
        if mode == "duplicates":
            dup = rf.duplicate_candidates(root, exclude_dirs=exclude)
            return {"status": 200, "data": {"mode": mode, "duplicate_groups": len(dup), "duplicate_candidates": dup}}
        manifest = arguments.get("canonical_manifest")
        report = dict(rf.forensic_report(root, manifest if isinstance(manifest, dict) else None, exclude_dirs=exclude))
        report["duplicate_candidates_count"] = len(report.pop("duplicate_candidates", []))
        return {"status": 200, "data": report}


def _github_get(path: str, broker: "CredentialBroker") -> dict[str, Any]:
    token = broker.get("HG_GITHUB_TOKEN")
    req = urllib.request.Request(
        "https://api.github.com" + path,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + token,
            "X-GitHub-Api-Version": "2026-03-10",
            "User-Agent": "HG-Tool-Runtime/1.0",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"github_http_{exc.code}") from None


def _split_repo(repository: str) -> tuple[str, str]:
    repository = str(repository or "").strip()
    if repository.count("/") != 1:
        raise ValueError("invalid repository identity (expected owner/repo)")
    owner, repo = repository.split("/")
    if not owner or not repo:
        raise ValueError("invalid repository identity (expected owner/repo)")
    return owner, repo


class GitHubReadRepoTool(ToolAdapter):
    def __init__(self, broker: CredentialBroker | None = None) -> None:
        self.broker = broker or CredentialBroker()

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="github.read_repo",
            description="Read bounded metadata for a GitHub repository.",
            input_schema={"type": "object", "properties": {"repository": {"type": "string"}},
                          "required": ["repository"], "additionalProperties": False},
            read_only=True, destructive=False, plugin_id="go.github",
        )

    def invoke(self, arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        owner, repo = _split_repo(arguments["repository"])
        status, data = _github_get(f"/repos/{owner}/{repo}", self.broker)
        return {"status": status, "repository": data.get("full_name"),
                "default_branch": data.get("default_branch"), "private": data.get("private"),
                "permissions": data.get("permissions")}


class GitHubReadBranchTool(ToolAdapter):
    def __init__(self, broker: CredentialBroker | None = None) -> None:
        self.broker = broker or CredentialBroker()

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="github.read_branch",
            description="Read a GitHub branch (name + head commit).",
            input_schema={"type": "object",
                          "properties": {"repository": {"type": "string"}, "branch": {"type": "string"}},
                          "required": ["repository", "branch"], "additionalProperties": False},
            read_only=True, destructive=False, plugin_id="go.github",
        )

    def invoke(self, arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        owner, repo = _split_repo(arguments["repository"])
        branch = str(arguments["branch"]).strip()
        if not branch:
            raise ValueError("branch is required")
        status, data = _github_get(f"/repos/{owner}/{repo}/branches/{branch}", self.broker)
        commit = data.get("commit") or {}
        return {"status": status, "branch": data.get("name"), "protected": data.get("protected"),
                "commit_sha": commit.get("sha")}


class GitHubReadFileTool(ToolAdapter):
    def __init__(self, broker: CredentialBroker | None = None) -> None:
        self.broker = broker or CredentialBroker()

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="github.read_file",
            description="Read a bounded file (contents metadata) from a GitHub repository ref.",
            input_schema={"type": "object",
                          "properties": {"repository": {"type": "string"}, "path": {"type": "string"},
                                         "ref": {"type": "string"}},
                          "required": ["repository", "path", "ref"], "additionalProperties": False},
            read_only=True, destructive=False, plugin_id="go.github",
        )

    def invoke(self, arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        owner, repo = _split_repo(arguments["repository"])
        path = str(arguments["path"]).strip().lstrip("/")
        ref = str(arguments["ref"]).strip()
        if not path or not ref:
            raise ValueError("path and ref are required")
        from urllib.parse import quote
        status, data = _github_get(f"/repos/{owner}/{repo}/contents/{quote(path)}?ref={quote(ref)}", self.broker)
        if isinstance(data, list):
            raise ValueError("path is a directory, not a file")
        content = data.get("content")
        try:
            import base64 as _b64
            decoded = _b64.b64decode((content or "").replace("\n", "")).decode("utf-8", errors="replace") if content else ""
        except Exception:
            decoded = ""
        return {"status": status, "path": data.get("path"), "sha": data.get("sha"),
                "size": data.get("size"), "encoding": data.get("encoding"),
                "content_sha256": "sha256:" + hashlib.sha256(decoded.encode()).hexdigest()}


class GitHubReadReleasesTool(ToolAdapter):
    def __init__(self, broker: CredentialBroker | None = None) -> None:
        self.broker = broker or CredentialBroker()

    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="github.read_releases",
            description="Read bounded release metadata (REST) for a GitHub repository.",
            input_schema={"type": "object", "properties": {"repository": {"type": "string"}},
                          "required": ["repository"], "additionalProperties": False},
            read_only=True, destructive=False, plugin_id="go.github",
        )

    def invoke(self, arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        owner, repo = _split_repo(arguments["repository"])
        status, data = _github_get(f"/repos/{owner}/{repo}/releases?per_page=5", self.broker)
        items = data if isinstance(data, list) else []
        return {"status": status, "count": len(items),
                "releases": [{"tag_name": r.get("tag_name"), "name": r.get("name"),
                              "draft": r.get("draft"), "prerelease": r.get("prerelease")} for r in items[:5]]}


def _github_call(method: str, path: str, broker: "CredentialBroker", body: dict | None = None) -> dict[str, Any]:
    token = broker.get("HG_GITHUB_TOKEN")
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Accept": "application/vnd.github+json", "Authorization": "Bearer " + token,
               "X-GitHub-Api-Version": "2026-03-10", "User-Agent": "HG-Tool-Runtime/1.0"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request("https://api.github.com" + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode()
            return {"status": resp.status, "data": json.loads(raw) if raw.strip() else {}}
    except urllib.error.HTTPError as exc:
        raise RuntimeError("github_http_%s" % exc.code) from None


def _branch_body(v: dict[str, Any], broker: "CredentialBroker") -> dict[str, Any]:
    o, r = _split_repo(v["repository"])
    d = _github_call("GET", f"/repos/{o}/{r}/branches/{v.get('from_ref', 'hg-core')}", broker)
    return {"ref": "refs/heads/" + str(v["branch"]).strip(), "sha": (d.get("data") or {}).get("commit", {}).get("sha")}


def _write_file_body(v: dict[str, Any], broker: "CredentialBroker") -> dict[str, Any]:
    import base64 as _b64
    b = {"message": str(v.get("message") or "hg self-repair"), "content": _b64.b64encode(str(v["content"]).encode()).decode(), "branch": str(v["branch"])}
    if v.get("sha"):
        b["sha"] = str(v["sha"])
    return b


class _GhTool(ToolAdapter):
    def __init__(self, name, desc, props, read_only, method, path_tmpl, body_fn=None, broker=None, required=None):
        self._spec = ToolSpec(name=name, description=desc,
                              input_schema={"type": "object",
                                            "properties": {p: {"type": "string"} for p in props},
                                            "required": required or props, "additionalProperties": False},
                              read_only=read_only, destructive=False, plugin_id="go.github")
        self._method = method; self._path = path_tmpl; self._body = body_fn
        self.broker = broker or CredentialBroker()

    def spec(self) -> ToolSpec:
        return self._spec

    def invoke(self, arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
        o, r = _split_repo(arguments["repository"])
        fmt = {k: str(v) for k, v in arguments.items() if k != "repository"}
        path = self._path.format(owner=o, repo=r, **fmt)
        body = self._body(arguments, self.broker) if self._body else None
        res = _github_call(self._method, path, self.broker, body)
        return res


def _extra_github_tools() -> list[ToolAdapter]:
    T = []
    R = lambda n, d, p, path: T.append(_GhTool(n, d, p, True, "GET", path))
    R("github.read_commit", "Read a commit by ref.", ["repository", "ref"], "/repos/{owner}/{repo}/commits/{ref}")
    R("github.read_issue", "Read an issue by number.", ["repository", "number"], "/repos/{owner}/{repo}/issues/{number}")
    R("github.read_pr", "Read a pull request by number.", ["repository", "number"], "/repos/{owner}/{repo}/pulls/{number}")
    R("github.read_workflow", "Read a workflow by id.", ["repository", "workflow_id"], "/repos/{owner}/{repo}/actions/workflows/{workflow_id}")
    R("github.read_actions_run", "Read an actions run by id.", ["repository", "run_id"], "/repos/{owner}/{repo}/actions/runs/{run_id}")
    R("github.read_check_runs", "Read check-runs for a ref.", ["repository", "ref"], "/repos/{owner}/{repo}/commits/{ref}/check-runs")
    T.append(_GhTool("github.create_branch", "Create a branch from a ref.", ["repository", "branch", "from_ref"], False, "POST", "/repos/{owner}/{repo}/git/refs", _branch_body))
    T.append(_GhTool("github.delete_branch", "Delete a branch ref (cleanup).", ["repository", "branch"], False, "DELETE", "/repos/{owner}/{repo}/git/refs/heads/{branch}", lambda v, b: None))
    T.append(_GhTool("github.write_file", "Create/update a file on a branch.", ["repository", "branch", "path", "content", "sha", "message"], False, "PUT", "/repos/{owner}/{repo}/contents/{path}", _write_file_body, required=["repository", "branch", "path", "content"]))
    T.append(_GhTool("github.update_branch", "Update a branch ref (fast-forward/force).", ["repository", "branch", "sha"], False, "PATCH", "/repos/{owner}/{repo}/git/refs/heads/{branch}", lambda v, b: {"sha": str(v["sha"])}))
    T.append(_GhTool("github.create_pr", "Create a pull request.", ["repository", "title", "head", "base"], False, "POST", "/repos/{owner}/{repo}/pulls", lambda v, b: {"title": str(v["title"]), "head": str(v["head"]), "base": str(v["base"])}))
    T.append(_GhTool("github.update_pr", "Update a pull request state/title/base.", ["repository", "number", "title", "state", "base"], False, "PATCH", "/repos/{owner}/{repo}/pulls/{number}", lambda v, b: {k: v[k] for k in ("title", "state", "base") if v.get(k)}, required=["repository", "number"]))
    T.append(_GhTool("github.comment_issue", "Comment on an issue/PR.", ["repository", "number", "body"], False, "POST", "/repos/{owner}/{repo}/issues/{number}/comments", lambda v, b: {"body": str(v["body"])}))
    T.append(_GhTool("github.create_issue", "Create an issue.", ["repository", "title"], False, "POST", "/repos/{owner}/{repo}/issues", lambda v, b: {"title": str(v["title"])}))
    T.append(_GhTool("github.update_issue", "Update an issue state/title.", ["repository", "number"], False, "PATCH", "/repos/{owner}/{repo}/issues/{number}", lambda v, b: {k: v[k] for k in ("title", "state") if v.get(k)}))
    T.append(_GhTool("github.dispatch_workflow", "Dispatch a workflow (workflow_dispatch).", ["repository", "workflow_id", "ref"], False, "POST", "/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches", lambda v, b: {"ref": str(v["ref"])}))
    T.append(_GhTool("github.rerun_workflow", "Re-run an actions run.", ["repository", "run_id"], False, "POST", "/repos/{owner}/{repo}/actions/runs/{run_id}/rerun", lambda v, b: None))
    T.append(_GhTool("github.read_actions_result", "Read an actions run (result).", ["repository", "run_id"], True, "GET", "/repos/{owner}/{repo}/actions/runs/{run_id}"))
    return T


def default_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(GitHubRepoTool())
    registry.register(GitHubReadRepoTool())
    registry.register(GitHubReadBranchTool())
    registry.register(GitHubReadFileTool())
    registry.register(GitHubReadReleasesTool())
    for t in _extra_github_tools():
        registry.register(t)
    registry.register(VPS1HealthTool())
    registry.register(VPS2HealthTool())
    registry.register(RepoForensicsTool())
    return registry
