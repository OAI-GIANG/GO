"""GOV-GAP-02: approval-binding integrity, schema and authority-binding tests."""
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime.go_runtime.core.governance_source import (
    BINDING_PINNED_SHA256,
    GovernanceSourceError,
    verify_governance_source,
)

ROOT = Path(__file__).resolve().parents[1]
BINDING_REL = "control/MASTER_GOVERNANCE_RULESET_V1_APPROVAL_BINDING.json"
SOURCE_REL = "control/MASTER_GOVERNANCE_RULESET_V1.md"
_MOD = "runtime.go_runtime.core.governance_source.BINDING_PINNED_SHA256"


class BindingIntegrityTests(unittest.TestCase):
    def _root(self, tmp):
        root = Path(tmp)
        (root / "control").mkdir()
        shutil.copyfile(ROOT / SOURCE_REL, root / SOURCE_REL)
        shutil.copyfile(ROOT / BINDING_REL, root / BINDING_REL)
        return root

    def _mutate(self, root, fn):
        p = root / BINDING_REL
        d = json.loads(p.read_text(encoding="utf-8"))
        fn(d)
        p.write_text(json.dumps(d, indent=2), encoding="utf-8")
        return p

    def _repin(self, p):
        return patch(_MOD, hashlib.sha256(p.read_bytes()).hexdigest())

    def test_pin_matches_committed_binding(self):
        raw = (ROOT / BINDING_REL).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), BINDING_PINNED_SHA256)

    def test_runtime_status_is_not_runtime_evidence(self):
        state = verify_governance_source(ROOT)
        self.assertFalse(state["runtime_status_claim"]["is_evidence"])
        self.assertEqual(state["approval_binding_sha256"], BINDING_PINNED_SHA256)

    def test_byte_tamper_rejected_by_integrity_pin(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            self._mutate(root, lambda d: d.__setitem__("runtime_status", "GENERATED_AND_ENFORCED"))
            with self.assertRaisesRegex(GovernanceSourceError, "BINDING_INTEGRITY_MISMATCH"):
                verify_governance_source(root)

    def test_unexpected_field_rejected_under_recomputed_pin(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            p = self._mutate(root, lambda d: d.__setitem__("injected", True))
            with self._repin(p), self.assertRaisesRegex(GovernanceSourceError, "UNEXPECTED_FIELD"):
                verify_governance_source(root)

    def test_missing_field_rejected_under_recomputed_pin(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            p = self._mutate(root, lambda d: d.pop("note"))
            with self._repin(p), self.assertRaisesRegex(GovernanceSourceError, "MISSING_FIELD"):
                verify_governance_source(root)

    def test_forged_approval_status_rejected_under_recomputed_pin(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            p = self._mutate(root, lambda d: d.__setitem__("approval_status", "OWNER_APPROVED_LATER"))
            with self._repin(p), self.assertRaisesRegex(GovernanceSourceError, "OWNER_DIRECTION_NOT_BOUND"):
                verify_governance_source(root)

    def test_field_level_source_hash_mismatch_rejected_under_recomputed_pin(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            p = self._mutate(root, lambda d: d.__setitem__("source_sha256", "0" * 64))
            with self._repin(p), self.assertRaisesRegex(GovernanceSourceError, "BINDING_HASH_MISMATCH"):
                verify_governance_source(root)

    def test_ruleset_mismatch_rejected_under_recomputed_pin(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            p = self._mutate(root, lambda d: d.__setitem__("ruleset", "SOME OTHER RULESET"))
            with self._repin(p), self.assertRaisesRegex(GovernanceSourceError, "RULESET_MISMATCH"):
                verify_governance_source(root)

    def test_source_path_mismatch_rejected_under_recomputed_pin(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._root(tmp)
            p = self._mutate(root, lambda d: d.__setitem__("source_path", "control/OTHER.md"))
            with self._repin(p), self.assertRaisesRegex(GovernanceSourceError, "SOURCE_PATH_MISMATCH"):
                verify_governance_source(root)
