import os
import tempfile
import unittest

from runtime.go_runtime.core.server import RuntimeConfig, GOApplication


class GoRuntimeContractTests(unittest.TestCase):
    def test_application_identity_and_echo_execution(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ.update({
                "GO_API_TOKEN": "test",
                "GO_ALLOW_ANONYMOUS": "false",
                "GO_DATA": os.path.join(td, "go.sqlite3"),
                "GO_COMMIT": "TEST_COMMIT",
                "GO_TREE_SHA": "TEST_TREE",
                "GO_ENV": "test",
                "GO_PORT": "0",
            })
            app = GOApplication(RuntimeConfig())
            self.assertEqual(app.status()["name"], "GO")
            self.assertEqual(app.status()["commit"], "TEST_COMMIT")
            result = app.submit({
                "task_id": "UNIT-GO-001",
                "operation": "echo",
                "payload": {"message": "hello"},
            })
            self.assertEqual(result["state"], "COMPLETED")
            self.assertEqual(result["result"]["echo"], "hello")
            self.assertTrue(result["result"]["evidence_id"].startswith("EVD-"))

    def test_authentication(self):
        os.environ.update({"GO_API_TOKEN": "secret", "GO_ALLOW_ANONYMOUS": "false"})
        config = RuntimeConfig()
        self.assertTrue(config.api_token == "secret")
        app = GOApplication.__new__(GOApplication)
        app.config = config
        self.assertTrue(app.authenticate("secret"))
        self.assertFalse(app.authenticate("wrong"))
        self.assertFalse(app.authenticate(None))


if __name__ == "__main__":
    unittest.main()
