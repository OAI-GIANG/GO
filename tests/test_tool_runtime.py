import os
import unittest

from runtime.go_runtime.core.tool_runtime import (
    TOOL_CONTRACT_VERSION,
    CredentialBroker,
    ToolContext,
    ToolRegistry,
    ToolSpec,
    VPS1HealthTool,
    VPS2HealthTool,
    GitHubRepoTool,
)


class ToolRuntimeV1Tests(unittest.TestCase):
    def test_contract_and_discovery(self):
        registry = ToolRegistry()
        registry.register(GitHubRepoTool())
        registry.register(VPS1HealthTool())
        registry.register(VPS2HealthTool())
        metadata = registry.metadata()
        self.assertEqual(len(metadata), 3)
        self.assertEqual({x["name"] for x in metadata},
                         {"github.repo.get", "vps1.edge.health", "vps2.health"})
        self.assertTrue(all(x["contract_version"] == TOOL_CONTRACT_VERSION for x in metadata))
        self.assertTrue(all(x["read_only"] for x in metadata))

    def test_duplicate_tool_is_rejected(self):
        registry = ToolRegistry()
        registry.register(VPS1HealthTool())
        with self.assertRaises(ValueError):
            registry.register(VPS1HealthTool())

    def test_direct_dispatch_emits_witness_without_secret(self):
        registry = ToolRegistry()
        class FakeTool(VPS1HealthTool):
            def invoke(self, arguments, context):
                return {"ok": True}
        registry.register(FakeTool())
        result = registry.dispatch("vps1.edge.health", {}, ToolContext("T-1"))
        self.assertTrue(result.ok)
        self.assertEqual(result.witness["tool_name"], "vps1.edge.health")
        self.assertIn("arguments_digest", result.witness)
        self.assertNotIn("Authorization", json_text(result.witness))

    def test_missing_github_credential_fails_closed(self):
        old = os.environ.pop("HG_GITHUB_TOKEN", None)
        try:
            tool = GitHubRepoTool()
            with self.assertRaises(PermissionError):
                tool.invoke({"owner": "OAI-GIANG", "repo": "GO"}, ToolContext("T-2"))
        finally:
            if old is not None:
                os.environ["HG_GITHUB_TOKEN"] = old

    def test_schema_is_structured(self):
        spec = GitHubRepoTool().spec()
        self.assertEqual(spec.input_schema["type"], "object")
        self.assertEqual(spec.input_schema["required"], ["owner", "repo"])
        spec.validate()


def json_text(value):
    import json
    return json.dumps(value, ensure_ascii=False)


if __name__ == "__main__":
    unittest.main()
