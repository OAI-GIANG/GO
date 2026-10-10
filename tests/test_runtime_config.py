"""CFG-01 / CFG-02: bind port contract and GO_DATA semantics."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime.go_runtime.core.server import DEFAULT_PORT, LEGACY_PORT, RuntimeConfig  # noqa: E402

_CLEARED = ("GO_PORT", "GO_DATA", "GO_ALLOW_LEGACY_PORT", "GO_API_TOKEN", "GO_HOST", "GO_ENV")


def cfg(**env):
    base = {k: v for k, v in os.environ.items() if k not in _CLEARED}
    base.update({"GO_API_TOKEN": "t"})
    base.update(env)
    with patch.dict(os.environ, base, clear=True):
        # construct AND validate inside the patched environment; otherwise the env
        # is restored before validate() runs and the test silently checks nothing.
        c = RuntimeConfig()
        c.validate()
        return c


class PortContractTests(unittest.TestCase):
    def test_default_port_is_canonical_not_legacy(self):
        self.assertEqual(DEFAULT_PORT, 8877)
        self.assertEqual(cfg().port, 8877)

    def test_legacy_port_is_rejected_by_default(self):
        with self.assertRaisesRegex(ValueError, "8787 is the legacy port"):
            cfg(GO_PORT=str(LEGACY_PORT))

    def test_legacy_port_allowed_only_when_explicitly_enabled(self):
        c = cfg(GO_PORT=str(LEGACY_PORT), GO_ALLOW_LEGACY_PORT="1")
        self.assertEqual(c.port, LEGACY_PORT)

    def test_env_override_still_works(self):
        self.assertEqual(cfg(GO_PORT="9999").port, 9999)

    def test_out_of_range_rejected(self):
        with self.assertRaisesRegex(ValueError, "0..65535"):
            cfg(GO_PORT="70000")


class DataPathTests(unittest.TestCase):
    def test_directory_rejected_with_clear_error(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, "GO_DATA must be a FILE path"):
                cfg(GO_DATA=d)

    def test_file_path_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            c = cfg(GO_DATA=str(Path(d) / "go_runtime.sqlite3"))
            self.assertEqual(c.data_path.name, "go_runtime.sqlite3")

    def test_nonexistent_path_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            cfg(GO_DATA=str(Path(d) / "sub" / "db.sqlite3"))


class RequiredTokenTests(unittest.TestCase):
    def test_token_required_unless_anonymous(self):
        base = {k: v for k, v in os.environ.items() if k not in ("GO_API_TOKEN", "GO_ALLOW_ANONYMOUS")}
        with patch.dict(os.environ, base, clear=True):
            with self.assertRaisesRegex(ValueError, "GO_API_TOKEN is required"):
                RuntimeConfig().validate()
