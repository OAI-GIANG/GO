"""DOMAIN-05: evidence ladder enforcement - the anti-false-claim gate."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime.go_runtime.core.evidence_ladder import (  # noqa: E402
    EvidenceLadderError, assert_claim_supported, assert_monotonic, require_proof,
)


class ClaimSupportTests(unittest.TestCase):
    def test_verified_claim_unsupported_at_scratch_level(self):
        with self.assertRaisesRegex(EvidenceLadderError, "CLAIM_EXCEEDS_EVIDENCE"):
            assert_claim_supported("VERIFIED", 4, {"command": "pytest", "exit_code": 0})

    def test_self_report_cannot_reach_tested(self):
        with self.assertRaisesRegex(EvidenceLadderError, "CLAIM_EXCEEDS_EVIDENCE"):
            assert_claim_supported("TESTED", 2)

    def test_implemented_requires_integration(self):
        with self.assertRaisesRegex(EvidenceLadderError, "CLAIM_EXCEEDS_EVIDENCE"):
            assert_claim_supported("IMPLEMENTED", 4, {"command": "pytest", "exit_code": 0})

    def test_tested_supported_at_e4_with_proof(self):
        out = assert_claim_supported("TESTED", 4, {"command": "pytest tests/", "exit_code": 0})
        self.assertTrue(out["supported"])
        self.assertEqual(out["level"], "E4_TESTED_LOCALLY")

    def test_verified_supported_only_at_e7(self):
        out = assert_claim_supported("VERIFIED", 7, {
            "command": "pytest", "exit_code": 0, "integration_commit": "abc",
            "deployment_id": "d1", "target_environment": "vps2",
            "independent_verifier": "owner", "verification_evidence": "E2E report"})
        self.assertEqual(out["level"], "E7_INDEPENDENTLY_VERIFIED")

    def test_deployed_requires_full_proof_chain(self):
        with self.assertRaisesRegex(EvidenceLadderError, "PROOF_MISSING"):
            assert_claim_supported("DEPLOYED", 6, {"command": "x", "exit_code": 0})

    def test_unknown_status_rejected(self):
        with self.assertRaisesRegex(EvidenceLadderError, "UNKNOWN_STATUS"):
            assert_claim_supported("PRODUCTION_READY", 7)

    def test_invalid_level_rejected(self):
        with self.assertRaisesRegex(EvidenceLadderError, "INVALID_LEVEL"):
            assert_claim_supported("TESTED", 99)


class ProofAndMonotonicTests(unittest.TestCase):
    def test_level4_without_exit_code_rejected(self):
        with self.assertRaisesRegex(EvidenceLadderError, "E4_TESTED_LOCALLY_PROOF_MISSING"):
            require_proof(4, {"command": "pytest"})

    def test_level7_requires_independent_verifier(self):
        with self.assertRaisesRegex(EvidenceLadderError, "E7_INDEPENDENTLY_VERIFIED_PROOF_MISSING"):
            require_proof(7, {"independent_verifier": "owner"})

    def test_silent_downgrade_rejected(self):
        with self.assertRaisesRegex(EvidenceLadderError, "SILENT_DOWNGRADE"):
            assert_monotonic(5, 4)

    def test_explained_downgrade_allowed(self):
        self.assertEqual(assert_monotonic(5, 4, downgrade_reason="integration reverted"), 4)

    def test_upgrade_allowed(self):
        self.assertEqual(assert_monotonic(3, 4), 4)
