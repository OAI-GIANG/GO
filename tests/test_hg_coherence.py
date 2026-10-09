from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class HGCoherenceTests(unittest.TestCase):
    def test_canonical_v1_source_is_present(self):
        source = ROOT / "control" / "MASTER_GOVERNANCE_RULESET_V1.md"
        self.assertTrue(source.is_file(), "Canonical V1 source is missing")
        self.assertGreater(source.stat().st_size, 0)

    def test_authority_model_names_v1_as_sole_source(self):
        authority = (ROOT / "control" / "AUTHORITY_MODEL_V1.md").read_text(encoding="utf-8-sig")
        self.assertIn("MASTER GOVERNANCE RULESET V1 — sole governing source.", authority)
        self.assertIn("GENERATED RUNTIME", authority)

    def test_architecture_defers_to_v1(self):
        architecture = (ROOT / "control" / "HG_CORE_FINAL_ARCHITECTURE_SPEC.md").read_text(encoding="utf-8-sig")
        self.assertIn("MASTER GOVERNANCE RULESET V1 is the only governing source.", architecture)
        self.assertIn("Runtime is an operational result of the new process", architecture)


if __name__ == "__main__":
    unittest.main(verbosity=2)
