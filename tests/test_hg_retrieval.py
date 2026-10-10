"""HG retrieval: provenance, independence and search behaviour."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hg-knowledge" / "tools"))
from hg_retrieval import (  # noqa: E402
    FORBIDDEN_ORIGINS, RetrievalError, build_index, index_digest,
    repository_identity, search, verify_provenance, write_index,
)

COMMIT = "955d9a5e1a0b217f756c4f443354dc7b02ecc22a"


class BuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = build_index(ROOT, COMMIT)

    def test_index_is_not_empty(self):
        self.assertGreater(len(self.docs), 40)

    def test_every_record_carries_provenance(self):
        for d in self.docs:
            self.assertTrue(d["source_commit"]); self.assertTrue(d["source_hash"])
            self.assertEqual(d["source_commit"], COMMIT)
            self.assertEqual(len(d["source_hash"]), 64)

    def test_canonical_documents_are_indexed(self):
        paths = {d["path"] for d in self.docs}
        self.assertIn("control/MASTER_GOVERNANCE_RULESET_V1.md", paths)
        self.assertIn("runtime/go_runtime/core/governance_source.py", paths)

    def test_no_foreign_origin_paths(self):
        for d in self.docs:
            for f in FORBIDDEN_ORIGINS:
                self.assertNotIn(f, d["path"])

    def test_index_dir_self_excluded(self):
        for d in self.docs:
            self.assertFalse(d["path"].startswith("hg-knowledge/"))

    def test_deterministic(self):
        self.assertEqual(index_digest(self.docs), index_digest(build_index(ROOT, COMMIT)))

    def test_provenance_verifies_against_disk(self):
        self.assertTrue(verify_provenance(self.docs, ROOT)["verified"])

    def test_tampered_record_detected(self):
        docs = [dict(d) for d in self.docs]
        docs[0]["source_hash"] = "0" * 64
        with self.assertRaisesRegex(RetrievalError, "PROVENANCE_HASH_MISMATCH"):
            verify_provenance(docs, ROOT)

    def test_identity_declares_hg(self):
        i = repository_identity(COMMIT)
        self.assertEqual(i["source_repository"], "OAI-GIANG/GO")
        self.assertEqual(i["system_identity"], "OAI-GIANG/HG")


class SearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = build_index(ROOT, COMMIT)

    def test_relevant_hit_for_governance(self):
        hits = search(self.docs, "governance", limit=5)
        self.assertTrue(hits)
        self.assertTrue(any("governance" in h["path"] or "MASTER" in h["path"] for h in hits))

    def test_hits_carry_provenance(self):
        for h in search(self.docs, "policy", limit=3):
            self.assertEqual(h["source_commit"], COMMIT); self.assertEqual(len(h["source_hash"]), 64)

    def test_limit_respected(self):
        self.assertLessEqual(len(search(self.docs, "", limit=3)), 3)

    def test_path_prefix_filter(self):
        for h in search(self.docs, "", limit=50, path_prefix="control/"):
            self.assertTrue(h["path"].startswith("control/"))

    def test_kind_filter(self):
        for h in search(self.docs, "", limit=50, kind="md"):
            self.assertEqual(h["kind"], "md")

    def test_no_match_returns_empty(self):
        # The corpus includes this test file, so the sentinel must be generated at
        # runtime; a literal would be indexed and would match itself.
        import uuid
        self.assertEqual(search(self.docs, "sentinel-" + uuid.uuid4().hex), [])

    def test_empty_query_lists_deterministically(self):
        a = [h["path"] for h in search(self.docs, "", limit=10)]
        b = [h["path"] for h in search(self.docs, "", limit=10)]
        self.assertEqual(a, b)


class WriteTests(unittest.TestCase):
    def test_write_index_and_reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            ident = write_index(ROOT, COMMIT, tmp)
            self.assertEqual(ident["source_repository"], "OAI-GIANG/GO")
            p = Path(tmp) / "index" / "knowledge.jsonl"
            self.assertTrue(p.is_file())
            rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
            self.assertEqual(len(rows), ident["document_count"])
            self.assertTrue((Path(tmp) / "manifests" / "repository-identity.json").is_file())


class IndexArtifactTests(unittest.TestCase):
    """The stored index must not be stale relative to the tree it describes."""

    def _rows(self):
        p = ROOT / "hg-knowledge" / "index" / "knowledge.jsonl"
        if not p.is_file():
            self.skipTest("index not built")
        return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]

    def test_stored_index_matches_fresh_build(self):
        rows = self._rows()
        self.assertEqual([r["path"] for r in rows],
                         [d["path"] for d in build_index(ROOT, COMMIT)])

    def test_stored_hashes_match_fresh_build(self):
        rows = self._rows()
        self.assertEqual({r["path"]: r["source_hash"] for r in rows},
                         {d["path"]: d["source_hash"] for d in build_index(ROOT, COMMIT)})

    def test_manifest_digest_matches_fresh_build(self):
        p = ROOT / "hg-knowledge" / "manifests" / "repository-identity.json"
        if not p.is_file():
            self.skipTest("manifest not built")
        m = json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual(m["index_digest"], index_digest(build_index(ROOT, COMMIT)))

    def test_retrieval_module_depends_only_on_stdlib(self):
        # Structural, not substring: a deny-list necessarily NAMES what it denies.
        import ast
        src = (ROOT / "hg-knowledge" / "tools" / "hg_retrieval.py").read_text(encoding="utf-8")
        mods = set()
        for n in ast.walk(ast.parse(src)):
            if isinstance(n, ast.Import):
                for a in n.names:
                    mods.add(a.name.split(".")[0])
            elif isinstance(n, ast.ImportFrom) and n.module:
                mods.add(n.module.split(".")[0])
        non_std = mods - set(sys.stdlib_module_names)
        self.assertFalse(non_std, f"non-stdlib imports found: {sorted(non_std)}")

    def test_retrieval_module_has_no_path_into_legacy_trees(self):
        src = (ROOT / "hg-knowledge" / "tools" / "hg_retrieval.py").read_text(encoding="utf-8")
        for banned in ("Sauthienthu89", "/LOVE/", "love-knowledge/"):
            self.assertNotIn(banned, src)


class IndependenceTests(unittest.TestCase):
    def test_no_record_originates_outside_hg(self):
        for d in build_index(ROOT, COMMIT):
            for f in FORBIDDEN_ORIGINS:
                self.assertNotIn(f, d["path"])
            self.assertFalse(d["path"].startswith("hg-knowledge/"))
