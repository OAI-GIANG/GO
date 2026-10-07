"""VPS2 Execution Bridge Contract V3.

Bounded authorization layer only. It never accepts raw shell commands from HG.
A caller supplies an immutable operation registry and an executor that consumes
only the resolved template plus validated variables after ALLOW.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from types import MappingProxyType
from typing import Any, Callable, Mapping


class BridgeReject(Exception):
    def __init__(self, reason_code: str):
        super().__init__(reason_code)
        self.reason_code = reason_code


@dataclass(frozen=True)
class OperationTemplate:
    operation_id: str
    action: str
    read_only: bool
    variable_types: tuple[tuple[str, str], ...] = ()

    def canonical(self) -> str:
        return json.dumps(
            {
                "action": self.action,
                "operation_id": self.operation_id,
                "read_only": self.read_only,
                "variable_types": list(self.variable_types),
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    @property
    def template_hash(self) -> str:
        return hashlib.sha256(self.canonical().encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class BridgeRequest:
    request_id: str
    target_id: str
    operation_id: str
    allowlist_version: str
    policy_version: str
    variables: Mapping[str, Any]

    @property
    def forbidden_raw_command(self) -> bool:
        return any(k in self.variables for k in ("command", "cmd", "args", "shell"))


@dataclass(frozen=True)
class AuthorizationDecision:
    decision_id: str
    request_id: str
    target_id: str
    operation_id: str
    allowlist_version: str
    policy_version: str
    decision: str
    reason_code: str
    template_hash: str
    registry_version: str
    timestamp: str


class VPS2ExecutionBridge:
    """PDP/PEP gate for opaque VPS2 operations."""

    def __init__(
        self,
        *,
        target_id: str,
        allowlist_version: str,
        policy_version: str,
        registry_version: str,
        templates: Mapping[str, OperationTemplate],
    ) -> None:
        self._target_id = target_id
        self._allowlist_version = allowlist_version
        self._policy_version = policy_version
        self._registry_version = registry_version
        normalized = {}
        for key, template in templates.items():
            if key != template.operation_id:
                raise ValueError("REGISTRY_KEY_MISMATCH")
            normalized[key] = template
        self._templates = MappingProxyType(dict(normalized))

    @property
    def registry_version(self) -> str:
        return self._registry_version

    def resolve(self, operation_id: str) -> OperationTemplate:
        template = self._templates.get(operation_id)
        if template is None:
            raise BridgeReject("UNKNOWN_OPERATION_ID")
        if not template.read_only:
            raise BridgeReject("NON_READ_ONLY_OPERATION")
        return template

    def _validate_variables(self, template: OperationTemplate, variables: Mapping[str, Any]) -> None:
        if not isinstance(variables, Mapping):
            raise BridgeReject("VARIABLE_SCHEMA_INVALID")
        if any(k in variables for k in ("command", "cmd", "args", "shell")):
            raise BridgeReject("OPAQUE_OPERATION_REQUIRED")
        schema = dict(template.variable_types)
        if set(variables) != set(schema):
            raise BridgeReject("VARIABLE_SCHEMA_INVALID")
        for key, expected in schema.items():
            value = variables[key]
            if expected == "str" and not isinstance(value, str):
                raise BridgeReject("VARIABLE_TYPE_INVALID")
            if expected == "int" and (not isinstance(value, int) or isinstance(value, bool)):
                raise BridgeReject("VARIABLE_TYPE_INVALID")
            if expected == "bool" and not isinstance(value, bool):
                raise BridgeReject("VARIABLE_TYPE_INVALID")

    def authorize(self, request: BridgeRequest) -> AuthorizationDecision:
        if not request.request_id or not request.target_id or not request.operation_id:
            raise BridgeReject("REQUEST_BINDING_INVALID")
        if request.target_id != self._target_id:
            raise BridgeReject("TARGET_OPERATION_MISMATCH")
        if request.allowlist_version != self._allowlist_version:
            raise BridgeReject("ALLOWLIST_VERSION_MISMATCH")
        if request.policy_version != self._policy_version:
            raise BridgeReject("POLICY_VERSION_MISMATCH")
        if request.forbidden_raw_command:
            raise BridgeReject("OPAQUE_OPERATION_REQUIRED")
        template = self.resolve(request.operation_id)
        self._validate_variables(template, request.variables)

        decision_id = hashlib.sha256(
            "|".join(
                (
                    request.request_id,
                    request.target_id,
                    request.operation_id,
                    request.allowlist_version,
                    request.policy_version,
                    template.template_hash,
                    self._registry_version,
                )
            ).encode("utf-8")
        ).hexdigest()
        return AuthorizationDecision(
            decision_id=decision_id,
            request_id=request.request_id,
            target_id=request.target_id,
            operation_id=request.operation_id,
            allowlist_version=request.allowlist_version,
            policy_version=request.policy_version,
            decision="ALLOW",
            reason_code="AUTHORIZED",
            template_hash=template.template_hash,
            registry_version=self._registry_version,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def execute(
        self,
        request: BridgeRequest,
        executor: Callable[[OperationTemplate, Mapping[str, Any]], Mapping[str, Any]],
    ) -> dict[str, Any]:
        decision = self.authorize(request)
        template = self.resolve(request.operation_id)
        result = dict(executor(template, dict(request.variables)))
        return {
            "state": "CLOSED",
            "decision": decision,
            "evidence": {
                "request_id": request.request_id,
                "target_id": request.target_id,
                "operation_id": request.operation_id,
                "template_hash": decision.template_hash,
                "allowlist_version": decision.allowlist_version,
                "policy_version": decision.policy_version,
                "authorization_decision_id": decision.decision_id,
                "readonly_attestation": template.read_only is True,
                "execution_status": "COMPLETED",
                "result": result,
            },
        }

    def reject(self, request: BridgeRequest) -> dict[str, Any]:
        try:
            self.authorize(request)
        except BridgeReject as exc:
            return {
                "state": "REJECTED",
                "decision": "DENY",
                "reason_code": exc.reason_code,
                "executing": False,
            }
        raise AssertionError("reject() received an authorizable request")
