"""DOMAIN-03: MTC-1.0 lifecycle enforcement, negative and gate tests."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime.go_runtime.core.governance_lifecycle import (  # noqa: E402
    LifecycleError, TERMINAL_STATES, enter, validate_transition,
)


class LifecycleTests(unittest.TestCase):
    def test_valid_path_to_closure(self):
        s = "DRAFT"
        s = enter(s, "CONTRACTED")
        s = enter(s, "FORENSIC_BASELINE")
        s = enter(s, "APPROVED", {"authority_record": "APR-1"})
        s = enter(s, "IMPLEMENTING")
        s = enter(s, "VERIFYING", {"test_evidence": "150 passed exit 0"})
        s = enter(s, "CLOSED", {"authority_record": "APR-1", "test_evidence": "150 passed",
                                "acceptance_criteria": {"A1": True, "A2": True},
                                "closure_evidence": "FINAL_ACCEPTANCE_REPORT.md"})
        self.assertEqual(s, "CLOSED")

    def test_gate_skipping_rejected(self):
        with self.assertRaisesRegex(LifecycleError, "ILLEGAL_TRANSITION"):
            validate_transition("DRAFT", "CLOSED")

    def test_skip_directly_to_implementing_rejected(self):
        with self.assertRaisesRegex(LifecycleError, "ILLEGAL_TRANSITION"):
            validate_transition("CONTRACTED", "IMPLEMENTING")

    def test_terminal_state_immutable(self):
        for t in TERMINAL_STATES:
            with self.assertRaisesRegex(LifecycleError, "TERMINAL_STATE_IMMUTABLE"):
                validate_transition(t, "IMPLEMENTING")

    def test_approved_requires_authority_record(self):
        with self.assertRaisesRegex(LifecycleError, "GATE_APPROVED_UNSATISFIED"):
            enter("FORENSIC_BASELINE", "APPROVED", {})

    def test_verifying_requires_test_evidence(self):
        with self.assertRaisesRegex(LifecycleError, "GATE_VERIFYING_UNSATISFIED"):
            enter("IMPLEMENTING", "VERIFYING", {})

    def test_closed_without_criteria_rejected(self):
        rec = {"authority_record": "A", "test_evidence": "T", "closure_evidence": "C"}
        with self.assertRaisesRegex(LifecycleError, "acceptance_criteria"):
            enter("VERIFYING", "CLOSED", rec)

    def test_closed_with_unmet_criteria_rejected(self):
        rec = {"authority_record": "A", "test_evidence": "T", "closure_evidence": "C",
               "acceptance_criteria": {"A1": True, "A2": False}}
        with self.assertRaisesRegex(LifecycleError, "A2"):
            enter("VERIFYING", "CLOSED", rec)

    def test_blocked_requires_blocker_record(self):
        with self.assertRaisesRegex(LifecycleError, "GATE_BLOCKED_UNSATISFIED"):
            enter("CONTRACTED", "BLOCKED", {})

    def test_blocked_with_record_then_resume(self):
        s = enter("CONTRACTED", "BLOCKED", {"blocker_record": "B-01"})
        self.assertEqual(s, "BLOCKED")
        self.assertEqual(enter(s, "CONTRACTED"), "CONTRACTED")

    def test_unknown_state_rejected(self):
        with self.assertRaisesRegex(LifecycleError, "UNKNOWN_STATE"):
            validate_transition("DRAFT", "PRODUCTION")
