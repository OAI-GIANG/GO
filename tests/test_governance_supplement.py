"""HG governance supplement: enforcement, negative and tamper tests."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.go_runtime.core.governance_supplement import (  # noqa: E402
    CredentialContainmentError,
    HumanApprovalError,
    PatchGateError,
    assert_no_secrets,
    require_destructive_approval,
    scan_for_secrets,
    validate_patch_record,
    verify_approval_authority,
)


def complete_patch(**over):
    rec = {
        "FINDING": "F-1", "ROOT_CAUSE": "rc", "MINIMAL_PATCH": "diff",
        "POSITIVE_TEST": "p", "NEGATIVE_TEST": "n", "REGRESSION_TEST": "r",
        "EVIDENCE": {"TEST_EXECUTION": "pytest: 121 passed exit 0"},
        "CHECKPOINT": "cp", "STATUS": "TESTED",
    }
    rec.update(over)
    return rec


class ApprovalRuleTests(unittest.TestCase):
    def test_canonical_approval_verifies(self):
        self.assertEqual(verify_approval_authority(ROOT)["status"], "VERIFIED")

    def test_tampered_binding_fails_closed_in_supplement(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            (t / "control").mkdir()
            (t / "control" / "MASTER_GOVERNANCE_RULESET_V1.md").write_bytes(
                (ROOT / "control" / "MASTER_GOVERNANCE_RULESET_V1.md").read_bytes())
            (t / "control" / "MASTER_GOVERNANCE_RULESET_V1_APPROVAL_BINDING.json").write_text(
                '{"source_sha256":"' + "0" * 64 + '","approval_status":"OWNER_CONFIRMED_APPROVED_IN_CURRENT_CONVERSATION"}',
                encoding="utf-8")
            with self.assertRaises(Exception):
                verify_approval_authority(t)


class PatchGateTests(unittest.TestCase):
    def test_complete_tested_record_accepted(self):
        self.assertTrue(validate_patch_record(complete_patch())["accepted"])

    def test_missing_field_rejected(self):
        rec = complete_patch(); rec.pop("ROLLBACK", None); rec["NEGATIVE_TEST"] = ""
        with self.assertRaisesRegex(PatchGateError, "MISSING_FIELDS"):
            validate_patch_record(rec)

    def test_claim_verified_without_integration_rejected(self):
        with self.assertRaisesRegex(PatchGateError, "STATUS_VERIFIED_UNSUPPORTED"):
            validate_patch_record(complete_patch(STATUS="VERIFIED"))

    def test_claim_implemented_without_commit_rejected(self):
        with self.assertRaisesRegex(PatchGateError, "STATUS_IMPLEMENTED_UNSUPPORTED"):
            validate_patch_record(complete_patch(STATUS="IMPLEMENTED"))

    def test_claim_deployed_without_deployment_id_rejected(self):
        rec = complete_patch(STATUS="DEPLOYED")
        rec["EVIDENCE"] = {"TEST_EXECUTION": "x", "INTEGRATION_COMMIT": "abc"}
        with self.assertRaisesRegex(PatchGateError, "STATUS_DEPLOYED_UNSUPPORTED"):
            validate_patch_record(rec)

    def test_full_evidence_permits_verified(self):
        rec = complete_patch(STATUS="VERIFIED")
        rec["EVIDENCE"] = {"TEST_EXECUTION": "x", "INTEGRATION_COMMIT": "abc",
                           "VERIFICATION_EVIDENCE": "proof"}
        self.assertTrue(validate_patch_record(rec)["accepted"])

    def test_unknown_status_rejected(self):
        with self.assertRaisesRegex(PatchGateError, "UNKNOWN_STATUS"):
            validate_patch_record(complete_patch(STATUS="PRODUCTION"))

    def test_unstructured_evidence_rejected(self):
        with self.assertRaisesRegex(PatchGateError, "EVIDENCE_NOT_A_STRUCTURED_RECORD"):
            validate_patch_record(complete_patch(EVIDENCE="looks fine"))


class CredentialContainmentTests(unittest.TestCase):
    def test_clean_tree_passes(self):
        self.assertEqual(assert_no_secrets(ROOT)["status"], "CLEAN")

    def test_planted_synthetic_secret_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            planted = "sk-" + ("A" * 32)
            (t / "leak.py").write_text(f'KEY = "{planted}"\n', encoding="utf-8")
            v = scan_for_secrets(t)
            self.assertTrue(v, "scanner failed to detect a planted synthetic secret")
            self.assertIn("leak.py:1", v[0])

    def test_planted_private_key_header_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            (t / "k.pem").write_text("-----BEGIN RSA " + "PRIVATE KEY-----\n", encoding="utf-8")
            (t / "k.pem").rename(t / "k.txt")
            self.assertTrue(scan_for_secrets(t))

    def test_non_secret_file_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            (t / "ok.py").write_text('NAME = "not-a-secret"\n', encoding="utf-8")
            self.assertEqual(scan_for_secrets(t), [])


def complete_destructive(**over):
    rec = {f: "declared" for f in
           ("TARGET", "JUSTIFICATION", "BLAST_RADIUS", "BACKUP", "REVERSIBILITY",
            "APPROVAL_REQUIREMENT", "EXECUTION_PLAN", "VERIFICATION")}
    rec["approved_by"] = "owner"
    rec.update(over)
    return rec


class HumanApprovalTests(unittest.TestCase):
    def test_non_destructive_needs_no_approval(self):
        self.assertFalse(require_destructive_approval("READ_FILE", {})["approval_required"])

    def test_destructive_without_record_rejected(self):
        with self.assertRaisesRegex(HumanApprovalError, "INCOMPLETE_RECORD"):
            require_destructive_approval("DELETE_REPOSITORY", {})

    def test_destructive_record_without_approver_rejected(self):
        rec = complete_destructive(); rec.pop("approved_by")
        with self.assertRaisesRegex(HumanApprovalError, "NOT_APPROVED"):
            require_destructive_approval("HISTORY_REWRITE", rec)

    def test_irreversible_requires_explicit_approval_id(self):
        rec = complete_destructive(REVERSIBILITY="IRREVERSIBLE")
        with self.assertRaisesRegex(HumanApprovalError, "IRREVERSIBLE_REQUIRES_EXPLICIT_APPROVAL_ID"):
            require_destructive_approval("FORCE_PUSH", rec)

    def test_irreversible_with_approval_id_accepted(self):
        rec = complete_destructive(REVERSIBILITY="IRREVERSIBLE", approval_id="APR-001")
        out = require_destructive_approval("FORCE_PUSH", rec)
        self.assertTrue(out["approval_required"])

    def test_reversible_destructive_with_approver_accepted(self):
        rec = complete_destructive(REVERSIBILITY="REVERSIBLE")
        self.assertTrue(require_destructive_approval("ROTATE_CREDENTIAL", rec)["approval_required"])


if __name__ == "__main__":
    unittest.main()
