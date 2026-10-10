from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from runtime.go_runtime.core.reconciliation import ExternalState, classify, may_retry
from runtime.go_runtime.core.engine.durable_execution import request_fingerprint
from runtime.go_runtime.core.store import RuntimeStore


def test_negative_response_with_possible_side_effect_is_unknown():
    state = classify(sent_ok=True, authorized=True, response_received=True, response_ok=False, side_effect_possible=True)
    assert state == ExternalState.UNKNOWN
    assert may_retry(state) is False


def test_request_fingerprint_binds_semantic_fields():
    base = request_fingerprint("goal", 2, execution_mode="ASYNC", idempotency_scope="TASK_SUBMISSION", metadata={"x": 1})
    assert base != request_fingerprint("goal", 2, execution_mode="SYNC", idempotency_scope="TASK_SUBMISSION", metadata={"x": 1})
    assert base != request_fingerprint("goal", 2, execution_mode="ASYNC", idempotency_scope="TASK_SUBMISSION", metadata={"x": 2})


def test_replay_append_serializes_concurrent_sequence_and_verifies(tmp_path):
    store = RuntimeStore(Path(tmp_path) / "go.sqlite3")
    def append(i):
        return store.append_replay("t", "EVENT", {"i": i}, now=f"2026-10-10T00:00:{i:02d}+00:00")
    with ThreadPoolExecutor(max_workers=8) as pool:
        rows = list(pool.map(append, range(1, 17)))
    records = store.list_replay("t")
    assert sorted(r["sequence"] for r in rows) == list(range(1, 17))
    from runtime.go_runtime.core.replay_contract import verify_replay_chain
    assert verify_replay_chain(records)
    with pytest.raises(Exception):
        store.save_replay({**records[0], "sequence": 1, "payload": {"tampered": True}}, "now")


def test_string_approval_is_not_approval_evidence():
    from runtime.go_runtime.core.approval import verify_approval
    valid, reason = verify_approval("approved", subject="s", tool_name="danger", arguments_digest="d",
                                    policy_sha256="p", scope="tool:danger")
    assert valid is False
    assert reason == "APPROVAL_EVIDENCE_REQUIRED"


def test_authority_revocation_survives_restart(tmp_path, monkeypatch):
    import json
    from runtime.go_runtime.core.authority import AuthorityRoot
    key = tmp_path / "root.key"
    key.write_bytes(b"test-provisioned-authority-key")
    revoked = tmp_path / "revoked.json"
    monkeypatch.setenv("HG_AUTHORITY_ROOT_KEY_FILE", str(key))
    monkeypatch.setenv("HG_AUTHORITY_REVOCATION_FILE", str(revoked))
    AuthorityRoot._instance = None
    root = AuthorityRoot.instance()
    token = root.issue(subject="s", scope=["runtime"], action="execute", audience="kernel", ttl_s=60)
    root.revoke(token.token_id)
    assert json.loads(revoked.read_text()) == [token.token_id]
    AuthorityRoot._instance = None
    restarted = AuthorityRoot.instance()
    assert not restarted.verify(token, action="execute", scope=["runtime"], audience="kernel")
    AuthorityRoot._instance = None


def test_canonical_evidence_detects_mutation_after_digest_binding():
    from runtime.go_runtime.core.evidence import CanonicalEvidence
    from runtime.go_runtime.core.certification_firewall import _valid_canonical_evidence
    item = CanonicalEvidence("e", "s", "p", "c", {"v": 1}, "integrity", {"src": "x"},
                             "INDEPENDENTLY_VERIFIED", "VERIFIED", "ASSESSED", "verifier", "2026-10-10T00:00:00Z")
    assert _valid_canonical_evidence(item) is True
    item.observation["v"] = 2
    assert _valid_canonical_evidence(item) is False


def test_store_migration_stops_on_corrupt_legacy_replay_chain(tmp_path):
    import json, sqlite3
    path = Path(tmp_path) / "go.sqlite3"
    store = RuntimeStore(path)
    row = store.append_replay("legacy", "EVENT", {"v": 1}, now="2026-10-10T00:00:00+00:00")
    store._connection  # retain reference to documented connection factory; do not modify through API
    with sqlite3.connect(path) as conn:
        corrupted = dict(row); corrupted["payload"] = {"v": "tampered"}
        conn.execute("UPDATE replay_records SET record_json=? WHERE task_id=? AND sequence=?",
                     (json.dumps(corrupted, sort_keys=True), "legacy", row["sequence"]))
    with pytest.raises(ValueError, match="migration_stop_invalid_legacy_replay_chain"):
        RuntimeStore(path)


def test_destructive_tool_string_approval_is_denied_before_dispatch(tmp_path, monkeypatch):
    from runtime.go_runtime.core.authority import AuthorityRoot
    from runtime.go_runtime.core.tool_governance import ToolGovernance
    from runtime.go_runtime.core.tool_runtime import ToolAdapter, ToolRegistry, ToolSpec

    key = Path(tmp_path) / "authority.key"
    key.write_bytes(b"test-only-external-authority-key")
    monkeypatch.setenv("HG_AUTHORITY_ROOT_KEY_FILE", str(key))
    monkeypatch.setenv("HG_TOOL_AUTHORITY_SUBJECT", "HG_SESSION_TEST")
    AuthorityRoot._instance = None
    root = AuthorityRoot.instance()
    token = root.issue(subject="HG_SESSION_TEST", scope=["tool:danger", "task:task-1"], action="execute", audience="tool:danger", ttl_s=60)
    token_path = Path(tmp_path) / "authority-token.json"
    import json
    token_path.write_text(json.dumps(token.to_dict()), encoding="utf-8")
    monkeypatch.setenv("HG_TOOL_AUTHORITY_TOKEN_FILE", str(token_path))

    class Destructive(ToolAdapter):
        called = False
        def spec(self):
            return ToolSpec("danger", "test destructive tool", {"type": "object", "properties": {}, "additionalProperties": False}, False, True, "test")
        def invoke(self, arguments, context):
            self.called = True
            return {"side_effect": True}

    registry = ToolRegistry()
    adapter = Destructive()
    registry.register(adapter)
    result = ToolGovernance(registry, Path(tmp_path) / "events.jsonl").execute("task-1", "danger", {}, approval="approved")
    assert result.ok is False
    assert result.output["error"] == "APPROVAL_EVIDENCE_REQUIRED"
    assert adapter.called is False
    AuthorityRoot._instance = None


def test_checkpoint_replay_mismatch_is_rejected_atomically(tmp_path):
    store = RuntimeStore(Path(tmp_path) / "go.sqlite3")
    replay = store.preview_replay("t", "CHECKPOINT_CREATED", {"checkpoint_id": "cp"}, now="2026-10-10T00:00:00+00:00")
    checkpoint = {"identity": {"checkpoint_id": "cp", "task_id": "t", "checkpoint_revision": 1},
                  "schema": {"name": "HG", "version": "1"}, "repository": {}, "contract": {}, "task": {},
                  "phase": "test", "acceptance": {}, "evidence": {}, "blockers": [], "next_action": {}, "resume": {},
                  "replay_sequence": replay["sequence"], "replay_digest": "wrong", "canonical_payload_hash": "h"}
    with pytest.raises(ValueError, match="checkpoint_replay_digest_binding_mismatch"):
        store.save_checkpoint_with_replay(checkpoint, replay)
    assert store.list_replay("t") == []
    assert store.get_checkpoint("cp") is None
