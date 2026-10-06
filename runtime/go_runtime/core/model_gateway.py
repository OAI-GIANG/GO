"""Canonical model/provider boundary (GO-owned).

A registry of adapters. Default is the deterministic local echo adapter. A real
OpenAI-compatible provider can be registered through environment variables
without becoming a state, policy, or evidence owner.
"""
from __future__ import annotations
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .contracts import ModelRequest, ModelResult


@dataclass
class ProviderAdapter:
    provider_id: str
    model_id: str

    def invoke(self, request: ModelRequest) -> ModelResult:
        raise NotImplementedError


class EchoAdapter(ProviderAdapter):
    """Deterministic local fallback; bounded to the echo operation."""

    def __init__(self) -> None:
        super().__init__("local", "local.echo.v1")

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

    def __init__(self, provider_id: str, model_id: str, base_url: str, api_key: str, timeout: int = 30) -> None:
        super().__init__(provider_id, model_id)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def invoke(self, request: ModelRequest) -> ModelResult:
        body = {"model": self.model_id,
                "messages": [{"role": "user", "content": json.dumps(request.payload, ensure_ascii=False)}],
                "temperature": 0.2}
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
        return ModelResult(self.provider_id, self.model_id,
                           {"text": text, "task_id": request.task_id}, True)


class ModelGateway:
    """Single execution boundary for model/provider calls with a pluggable registry."""

    def __init__(self) -> None:
        self._adapters: dict[tuple[str, str], ProviderAdapter] = {}
        echo = EchoAdapter()
        self.register(echo)
        self.default_provider = echo.provider_id
        self.default_model = echo.model_id
        base = os.getenv("GO_MODEL_BASE_URL")
        pid = os.getenv("GO_MODEL_PROVIDER")
        mid = os.getenv("GO_MODEL_ID")
        key = os.getenv("GO_MODEL_API_KEY") or os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
        if base and pid and mid and key:
            self.register(OpenAICompatibleAdapter(pid, mid, base, key, int(os.getenv("GO_MODEL_TIMEOUT", "30"))))
            self.default_provider = pid
            self.default_model = mid

    def register(self, adapter: ProviderAdapter) -> None:
        self._adapters[(adapter.provider_id, adapter.model_id)] = adapter

    def has(self, provider: str, model: str) -> bool:
        return (provider, model) in self._adapters

    def invoke(self, request: ModelRequest) -> ModelResult:
        adapter = self._adapters.get((request.provider, request.model))
        if adapter is None:
            raise ValueError("provider/model is not registered with the canonical gateway")
        return adapter.invoke(request)
