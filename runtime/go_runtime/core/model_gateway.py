"""Canonical model/provider boundary (GO-owned, pluggable).

Default stays the deterministic local echo adapter so bounded `echo` execution
is unchanged. A real OpenAI-compatible reasoning provider can be registered via
environment (GO_MODEL_*), exposed as the reasoning target for non-echo
operations, without becoming a state/policy/evidence owner.

Plugin Contract V1 is metadata on the existing ProviderAdapter boundary. It does
not introduce a second registry, lifecycle owner, or execution authority.
"""
from __future__ import annotations
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from .contracts import ModelRequest, ModelResult

PLUGIN_CONTRACT_VERSION = "PLUGIN-CONTRACT-V1"
PLUGIN_EXTENSION_POINT = "model.provider"

@dataclass
class ProviderAdapter:
    provider_id: str
    model_id: str
    plugin_id: str = ""
    plugin_version: str = "1.0.0"
    contract_version: str = PLUGIN_CONTRACT_VERSION
    extension_point: str = PLUGIN_EXTENSION_POINT
    supported_operations: tuple[str, ...] = field(default_factory=tuple)
    source: str = "runtime.go_runtime.core.model_gateway"
    provenance: str = "GO_RUNTIME_CANONICAL"

    def validate_contract(self) -> None:
        if not self.provider_id.strip() or not self.model_id.strip():
            raise ValueError("provider_id and model_id are required")
        if not self.plugin_id.strip():
            raise ValueError("plugin_id is required")
        if not self.plugin_version.strip():
            raise ValueError("plugin_version is required")
        if self.contract_version != PLUGIN_CONTRACT_VERSION:
            raise ValueError("unsupported plugin contract version")
        if self.extension_point != PLUGIN_EXTENSION_POINT:
            raise ValueError("unsupported plugin extension point")
        if not self.supported_operations or any(not op.strip() for op in self.supported_operations):
            raise ValueError("supported_operations is required")
        if not self.source.strip() or not self.provenance.strip():
            raise ValueError("source and provenance are required")

    def invoke(self, request: ModelRequest) -> ModelResult:
        raise NotImplementedError

class EchoAdapter(ProviderAdapter):
    def __init__(self) -> None:
        super().__init__("local", "local.echo.v1",
                     plugin_id="go.local.echo", supported_operations=("echo",))

    def invoke(self, request: ModelRequest) -> ModelResult:
        if request.operation != "echo":
            raise ValueError("local adapter supports only bounded echo")
        message = request.payload.get("message")
        if not isinstance(message, str):
            raise ValueError("model payload.message must be a string")
        if len(message) > 10000:
            raise ValueError("model payload.message exceeds 10000 characters")
        return ModelResult(self.provider_id, self.model_id,
                           {"echo": message, "task_id": request.task_id}, True)

class OpenAICompatibleAdapter(ProviderAdapter):
    """Real model provider behind an OpenAI-compatible /chat/completions API."""
    def __init__(self, provider_id: str, model_id: str, base_url: str, api_key: str, timeout: int = 60) -> None:
        super().__init__(provider_id, model_id,
                         plugin_id=f"go.{provider_id}.openai-compatible",
                         supported_operations=("ask", "echo"))
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def invoke(self, request: ModelRequest) -> ModelResult:
        msg = request.payload.get("message")
        if isinstance(msg, str):
            extra = {k: v for k, v in request.payload.items() if k != "message"}
            content = msg + (("\n\n[GO_CONTEXT]\n" + json.dumps(extra, ensure_ascii=False)) if extra else "")
        else:
            content = json.dumps(request.payload, ensure_ascii=False)
        body = {"model": self.model_id, "messages": [{"role": "user", "content": content}], "temperature": 0.2}
        req = urllib.request.Request(
            self.base_url + "/chat/completions", data=json.dumps(body).encode(), method="POST",
            headers={"Authorization": "Bearer " + self.api_key, "Content-Type": "application/json",
                     "User-Agent": "GO-Runtime/1.0", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = json.load(resp)
        except urllib.error.HTTPError as exc:
            raise ValueError("provider http %s" % exc.code) from None
        except urllib.error.URLError as exc:
            raise ValueError("provider unreachable: %s" % getattr(exc, "reason", exc)) from None
        try:
            text = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise ValueError("provider malformed response") from None
        return ModelResult(self.provider_id, self.model_id, {"text": text, "task_id": request.task_id}, True)

class ModelGateway:
    """Single execution boundary for model calls. Registry + reasoning target."""
    def __init__(self) -> None:
        self._adapters: dict[tuple[str, str], ProviderAdapter] = {}
        echo = EchoAdapter()
        self.register(echo)
        self.default_provider = echo.provider_id
        self.default_model = echo.model_id
        self.reasoning_provider: str | None = None
        self.reasoning_model: str | None = None
        base = os.getenv("GO_MODEL_BASE_URL")
        pid = os.getenv("GO_MODEL_PROVIDER")
        mid = os.getenv("GO_MODEL_ID")
        key = os.getenv("GO_MODEL_API_KEY") or os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
        if base and pid and mid and key:
            self.register(OpenAICompatibleAdapter(pid, mid, base, key, int(os.getenv("GO_MODEL_TIMEOUT", "60"))))
            self.reasoning_provider = pid
            self.reasoning_model = mid

    def register(self, adapter: ProviderAdapter) -> None:
        if not isinstance(adapter, ProviderAdapter):
            raise TypeError("adapter must be a ProviderAdapter")
        adapter.validate_contract()
        self._adapters[(adapter.provider_id, adapter.model_id)] = adapter

    def has(self, provider: str, model: str) -> bool:
        return (provider, model) in self._adapters

    def invoke(self, request: ModelRequest) -> ModelResult:
        adapter = self._adapters.get((request.provider, request.model))
        if adapter is None:
            raise ValueError("provider/model is not registered with the canonical gateway")
        return adapter.invoke(request)
