"""PLAN-04: HG contract-identity migration, compatibility window and replay."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.go_runtime.core.contract_identity import (  # noqa: E402
    CANONICAL_IDENTIFIERS,
    COMPAT_WINDOW_ID,
    ContractIdentityError,
    LEGACY_TO_CANONICAL,
    is_accepted,
    is_legacy,
    normalize_identity_fields,
    require_accepted,
    to_canonical,
)
from runtime.go_runtime.core.engine.task_contract import TaskContract  # noqa: E402

LEGACY_TASK_PAYLOAD = {
    "schema_version": "LOVE-TASK-CONTRACT-1.0",
    "contract_name": "LOVE_TASK_CONTRACT",
    "contract_version": "1.0",
    "goal": "g",
    "metadata": {},
}


class WriteSideTests(unittest.TestCase):
    def test_new_task_contract_emits_hg_identity(self):
        p = TaskContract(goal="g").canonical_payload()
        self.assertEqual(p["schema_version"], "HG-TASK-CONTRACT-1.0")
        self.assertEqual(p["contract_name"], "HG_TASK_CONTRACT")

    def test_new_submission_emits_hg_identity(self):
        s = TaskContract(goal="g").submit(submission_id="s1", idempotency_key="k1")
        self.assertEqual(s.to_dict()["schema_version"], "HG-SUBMISSION-1.0")

    def test_submit_writes_hg_contract_name_in_metadata(self):
        s = TaskContract(goal="g").submit(submission_id="s1", idempotency_key="k1")
        self.assertEqual(s.metadata["_contract_name"], "HG_TASK_CONTRACT")

    def test_no_love_identifier_is_emitted_by_write_paths(self):
        for rel in ("runtime/go_runtime/core/engine/task_contract.py",
                    "runtime/go_runtime/core/engine/learning.py",
                    "runtime/go_runtime/core/engine/durable_execution.py"):
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertNotIn('"LOVE-', text, f"{rel} still emits a LOVE-* identity literal")
            self.assertNotIn('"LOVE_', text, f"{rel} still emits a LOVE_* identity literal")


class ReadSideAndReplayTests(unittest.TestCase):
    def test_legacy_payload_normalises_to_canonical_payload(self):
        self.assertEqual(normalize_identity_fields(LEGACY_TASK_PAYLOAD),
                         TaskContract(goal="g").canonical_payload())

    def test_legacy_and_canonical_hash_identically_after_normalisation(self):
        from runtime.go_runtime.core.checkpoint import canonical_json
        from hashlib import sha256
        canon = TaskContract(goal="g").canonical_payload()
        h_norm = sha256(canonical_json(normalize_identity_fields(LEGACY_TASK_PAYLOAD)).encode()).hexdigest()
        h_canon = sha256(canonical_json(canon).encode()).hexdigest()
        self.assertEqual(h_norm, h_canon)

    def test_migration_is_idempotent(self):
        self.assertEqual(normalize_identity_fields(normalize_identity_fields(LEGACY_TASK_PAYLOAD)),
                         normalize_identity_fields(LEGACY_TASK_PAYLOAD))

    def test_rollback_window_still_reads_legacy(self):
        self.assertTrue(is_legacy("LOVE-TASK-CONTRACT-1.0"))
        self.assertTrue(is_accepted("LOVE-TASK-CONTRACT-1.0"))
        self.assertEqual(to_canonical("LOVE-TASK-CONTRACT-1.0"), "HG-TASK-CONTRACT-1.0")

    def test_learning_and_hint_identifiers_are_mapped(self):
        self.assertEqual(to_canonical("LOVE-LEARNING-1.0"), "HG-LEARNING-1.0")
        self.assertEqual(to_canonical("LOVE-KNOWLEDGE-HINT-1.0"), "HG-KNOWLEDGE-HINT-1.0")

    def test_durable_execution_default_is_hg(self):
        text = (ROOT / "runtime/go_runtime/core/engine/durable_execution.py").read_text(encoding="utf-8")
        self.assertIn('"HG_TASK_CONTRACT"', text)
        self.assertIn("to_canonical(", text)

    def test_non_identity_fields_are_untouched(self):
        payload = {"schema_version": "LOVE-SUBMISSION-1.0", "goal": "x", "delay_s": 7}
        self.assertEqual(normalize_identity_fields(payload)["goal"], "x")
        self.assertEqual(normalize_identity_fields(payload)["delay_s"], 7)


class FailureTests(unittest.TestCase):
    def test_unknown_identity_rejected(self):
        with self.assertRaisesRegex(ContractIdentityError, "UNKNOWN_CONTRACT_IDENTITY"):
            require_accepted("HG-TASK-CONTRACT-9.9")

    def test_legacy_lookalike_rejected(self):
        with self.assertRaisesRegex(ContractIdentityError, "UNKNOWN_CONTRACT_IDENTITY"):
            require_accepted("LOVE-TASK-CONTRACT-2.0")

    def test_empty_identity_rejected(self):
        with self.assertRaises(ContractIdentityError):
            require_accepted("")

    def test_tampered_payload_rejected_via_identity(self):
        with self.assertRaises(ContractIdentityError):
            normalize_identity_fields(dict(LEGACY_TASK_PAYLOAD, schema_version="LOVE-TASK-CONTRACT-1.0-X"))

    def test_window_metadata_is_declared(self):
        self.assertEqual(COMPAT_WINDOW_ID, "HG-ID-COMPAT-1")
        self.assertEqual(len(CANONICAL_IDENTIFIERS), len(LEGACY_TO_CANONICAL))


if __name__ == "__main__":
    unittest.main()
