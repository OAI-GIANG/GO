"""PHONE BRIDGE V1.1 - canonical bounded transport boundary for GO.

This adapter does NOT own execution, evidence, or authorization. It maps a
validated phone request onto GO's existing governed submission path:
authentication -> kernel.authorize -> TaskContract -> DurableExecution ->
Evidence Authority -> replay. No second execution/evidence authority exists here.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping

PROTOCOL_VERSION = "1.1"
MAX_CLOCK_SKEW_SECONDS = 300


class BridgeError(Exception):
    def __init__(self, code: str, message: str, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


def _now_ts() -> float:
    return datetime.now(timezone.utc).timestamp()


def parse_request(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise BridgeError("REQUEST_SCHEMA_INVALID", "Request schema invalid")
    required = ("protocol_version", "request_id", "operation", "timestamp", "nonce", "payload")
    if any(k not in raw for k in required) or raw.get("protocol_version") != PROTOCOL_VERSION:
        raise BridgeError("REQUEST_SCHEMA_INVALID", "Request schema invalid")
    try:
        rid = str(uuid.UUID(str(raw["request_id"])))
        ts = int(raw["timestamp"])
    except (ValueError, TypeError):
        raise BridgeError("REQUEST_SCHEMA_INVALID", "Request schema invalid") from None
    if not isinstance(raw["operation"], str) or not raw["operation"].strip():
        raise BridgeError("REQUEST_SCHEMA_INVALID", "Request schema invalid")
    if not isinstance(raw["nonce"], str) or not raw["nonce"].strip():
        raise BridgeError("REQUEST_SCHEMA_INVALID", "Request schema invalid")
    if not isinstance(raw["payload"], dict):
        raise BridgeError("REQUEST_SCHEMA_INVALID", "Request schema invalid")
    if abs(_now_ts() - ts) > MAX_CLOCK_SKEW_SECONDS:
        raise BridgeError("REQUEST_EXPIRED", "Request outside acceptance window")
    return {"request_id": rid, "operation": raw["operation"].strip().lower(),
            "timestamp": ts, "nonce": raw["nonce"], "payload": raw["payload"]}


def handle(app: Any, raw: Mapping[str, Any], token: str | None) -> dict[str, Any]:
    """Entry point. Reuses GO authentication/authorization/DurableExecution/Evidence."""
    request_id = str(raw.get("request_id", "")) if isinstance(raw, Mapping) else ""
    try:
        req = parse_request(raw)
        if not app.authenticate(token):
            raise BridgeError("AUTHENTICATION_FAILED", "Request authentication failed")
        idem = "PHONE:%s:%s" % (req["request_id"], req["nonce"])
        if app.store.get_by_idempotency(idem) is not None:
            raise BridgeError("REQUEST_REPLAYED", "Request replayed")
        authorization_id = app.cognitive.authorize(req["request_id"], req["operation"])
        final = app.submit({"task_id": req["request_id"], "operation": req["operation"],
                            "payload": req["payload"], "idempotency_key": idem})
        result = final.get("result") or {}
        submitted = final.get("state") == "COMPLETED"
        return {"request_id": req["request_id"],
                "status": "SUBMITTED" if submitted else str(final.get("state") or "REJECTED"),
                "authorization_id": authorization_id,
                "execution_id": final.get("run_id") or final.get("id"),
                "evidence_id": result.get("evidence_id"),
                "replay_id": result.get("replay_id"),
                "state": final.get("state"),
                "error": final.get("error")}
    except BridgeError as exc:
        return {"request_id": request_id, "status": "REJECTED",
                "error": {"code": exc.code, "message": exc.message, "retryable": exc.retryable}}
    except Exception:
        return {"request_id": request_id, "status": "REJECTED",
                "error": {"code": "INTERNAL_ERROR", "message": "Request rejected", "retryable": False}}
