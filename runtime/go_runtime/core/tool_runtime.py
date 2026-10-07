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
    """Credential boundary. Tools receive credentials; the model never does."""

    def get(self, credential_name: str) -> str:
        value = os.getenv(credential_name, "").strip()
        if not value:
            raise PermissionError("credential not configured: " + credential_name)
        return value


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
        token = os.getenv("HG_EDGE_TOKEN", "").strip()
        if not base or not token:
            raise PermissionError("VPS2 edge credentials not configured")
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


def default_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(GitHubRepoTool())
    registry.register(VPS1HealthTool())
    registry.register(VPS2HealthTool())
    return registry
