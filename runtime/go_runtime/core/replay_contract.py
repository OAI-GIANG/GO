"""Canonical Replay serialization, digest and legacy verification contract."""
from __future__ import annotations
import hashlib
import json
from typing import Any, Iterable

SCHEMA_VERSION = 2

def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)

def digest_payload(record: dict[str, Any]) -> str:
    payload = {k: v for k, v in record.items() if k != "record_digest"}
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()

def verify_replay_chain(records: Iterable[dict[str, Any]]) -> bool:
    previous = "GENESIS"
    for expected_sequence, record in enumerate(records, 1):
        try:
            if int(record.get("sequence", 0)) != expected_sequence or record.get("previous_digest") != previous:
                return False
            if int(record.get("schema_version", 1)) >= SCHEMA_VERSION:
                expected = digest_payload(record)
            else:
                # Two legacy writers existed: DurableExecution included occurred_at;
                # CognitiveService omitted it from the digest. Accept only an exact match.
                full = {k: v for k, v in record.items() if k != "record_digest"}
                no_time = {k: v for k, v in full.items() if k != "occurred_at"}
                digests = {hashlib.sha256(canonical_json(full).encode()).hexdigest(),
                           hashlib.sha256(canonical_json(no_time).encode()).hexdigest()}
                expected = record.get("record_digest") if record.get("record_digest") in digests else "__INVALID__"
            if expected != record.get("record_digest"):
                return False
            previous = str(record["record_digest"])
        except (KeyError, TypeError, ValueError):
            return False
    return True

def build_replay(task_id: str, sequence: int, event_type: str, payload: dict[str, Any], previous_digest: str, occurred_at: str) -> dict[str, Any]:
    record = {"schema_version": SCHEMA_VERSION, "replay_id": "RPL-" + __import__("uuid").uuid4().hex,
              "task_id": task_id, "sequence": sequence, "event_type": event_type, "payload": payload,
              "previous_digest": previous_digest, "occurred_at": occurred_at}
    record["record_digest"] = digest_payload(record)
    return record
