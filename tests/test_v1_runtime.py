import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime_v1"))
from engine import GovernanceLoadError, authorize_action, execute_governed_action, verify_policy


class V1RuntimeTests(unittest.TestCase):
    def test_canonical_source_hash_and_pillars(self):
        state = verify_policy(ROOT / "control")
        self.assertEqual(state["source_sha256"], "cc1a8b171b1c0e194923359b5b8b17ee9e9ff646b33693cc983f2a9984cc21af")
        self.assertEqual(state["g1_count"], 1)
        self.assertTrue(state["pillars_in_required_order"])
        self.assertFalse(state["legacy_policy_fallback"])

    def test_modified_policy_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            shutil.copyfile(ROOT / "control" / "MASTER_GOVERNANCE_RULESET_V1.md", target / "MASTER_GOVERNANCE_RULESET_V1.md")
            shutil.copyfile(ROOT / "control" / "MASTER_GOVERNANCE_RULESET_V1_APPROVAL_BINDING.json", target / "MASTER_GOVERNANCE_RULESET_V1_APPROVAL_BINDING.json")
            p = target / "MASTER_GOVERNANCE_RULESET_V1.md"
            p.write_bytes(p.read_bytes() + b"tamper")
            with self.assertRaisesRegex(GovernanceLoadError, "SHA-256 mismatch"):
                verify_policy(target)

    def test_mismatched_binding_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            shutil.copyfile(ROOT / "control" / "MASTER_GOVERNANCE_RULESET_V1.md", target / "MASTER_GOVERNANCE_RULESET_V1.md")
            binding = json.loads((ROOT / "control" / "MASTER_GOVERNANCE_RULESET_V1_APPROVAL_BINDING.json").read_text(encoding="utf-8"))
            binding["source_sha256"] = "0" * 64
            (target / "MASTER_GOVERNANCE_RULESET_V1_APPROVAL_BINDING.json").write_text(json.dumps(binding), encoding="utf-8")
            with self.assertRaisesRegex(GovernanceLoadError, "does not match"):
                verify_policy(target)

    def test_action_gate_fails_closed(self):
        result = authorize_action(action="delete", target="target", delegated_scope="", capability_available=True, authorization_evidence="")
        self.assertEqual(result["decision"], "DENY")
        self.assertIn("delegated_scope", result["missing"])
        self.assertIn("authorization_evidence", result["missing"])
        self.assertFalse(result["execution_performed"])

    def test_action_gate_does_not_claim_execution(self):
        result = authorize_action(action="inspect", target="repo", delegated_scope="read-only repo audit", capability_available=True, authorization_evidence="AUTH-TEST")
        self.assertEqual(result["decision"], "ALLOW_TO_PROCEED_TO_EXECUTOR")
        self.assertFalse(result["execution_performed"])

    def test_governed_executor_runs_and_hashes_evidence(self):
        result = execute_governed_action(
            action="test-operation",
            target="in-memory-test",
            delegated_scope="explicit test scope",
            capability_available=True,
            authorization_evidence="TEST-AUTH-001",
            executor=lambda: "controlled-test-success",
            policy_base=ROOT / "control",
        )
        self.assertEqual(result["status"], "EXECUTED")
        self.assertTrue(result["execution_performed"])
        self.assertEqual(len(result["evidence_sha256"]), 64)
        self.assertEqual(result["source_sha256"], "cc1a8b171b1c0e194923359b5b8b17ee9e9ff646b33693cc983f2a9984cc21af")

    def test_denied_action_never_calls_executor(self):
        called = []
        result = execute_governed_action(
            action="delete",
            target="in-memory-test",
            delegated_scope="",
            capability_available=True,
            authorization_evidence="",
            executor=lambda: called.append("executed"),
            policy_base=ROOT / "control",
        )
        self.assertEqual(result["status"], "DENIED")
        self.assertFalse(result["execution_performed"])
        self.assertEqual(called, [])

    def test_generated_runtime_end_to_end(self):
        run = subprocess.run(
            [sys.executable, str(ROOT / "runtime_v1" / "bootstrap.py")],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=20,
        )
        self.assertEqual(run.returncode, 0, msg=run.stdout + run.stderr)
        manifest_path = ROOT / "runtime_v1" / "generated" / "runtime-manifest.json"
        self.assertTrue(manifest_path.is_file())
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["runtime_status"], "GENERATED")
        self.assertEqual(manifest["source_sha256"], "cc1a8b171b1c0e194923359b5b8b17ee9e9ff646b33693cc983f2a9984cc21af")
        self.assertFalse(manifest["legacy_runtime_fallback"])
        self.assertIn('"runtime_self_test_exit": 0', run.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
