import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

_HOME = tempfile.mkdtemp(prefix="hg-v1-phone-payload-test-")
os.environ.setdefault("USERPROFILE", _HOME)
from core.runtime import hg_cap_payload

SOURCE = ROOT / "control" / "MASTER_GOVERNANCE_RULESET_V1.md"
BINDING = ROOT / "control" / "MASTER_GOVERNANCE_RULESET_V1_APPROVAL_BINDING.json"
EXPECTED = "cc1a8b171b1c0e194923359b5b8b17ee9e9ff646b33693cc983f2a9984cc21af"


class V1PhonePayloadTests(unittest.TestCase):
    def test_payload_accepts_exact_v1_and_binding(self):
        hg_cap_payload.V1_SOURCE_PATH = str(SOURCE)
        hg_cap_payload.V1_BINDING_PATH = str(BINDING)
        state = hg_cap_payload._verify_v1_local()
        self.assertEqual(state["status"], "VERIFIED")
        self.assertEqual(state["source_sha256"], EXPECTED)
        self.assertFalse(state["legacy_policy_fallback"])

    def test_payload_fails_closed_on_modified_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "MASTER_GOVERNANCE_RULESET_V1.md"
            shutil.copyfile(SOURCE, target)
            target.write_bytes(target.read_bytes() + b"tamper")
            hg_cap_payload.V1_SOURCE_PATH = str(target)
            hg_cap_payload.V1_BINDING_PATH = str(BINDING)
            with self.assertRaisesRegex(RuntimeError, "V1_POLICY_HASH_MISMATCH"):
                hg_cap_payload._verify_v1_local()


if __name__ == "__main__":
    unittest.main(verbosity=2)
