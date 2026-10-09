import http.client
import json
import os
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "runtime"
sys.path.insert(0, str(RUNTIME))
sys.path.insert(0, str(ROOT))

from runtime_v1.engine import GovernanceLoadError
from go_runtime.core.tool_runtime import ToolAdapter, ToolContext, ToolRegistry, ToolSpec
from go_runtime.core.tool_governance import ToolGovernance
import go_runtime.core.tool_runtime as tool_runtime_module
import go_runtime.core.tool_governance as tool_governance_module
import hg_runtime


EXPECTED_SHA256 = "cc1a8b171b1c0e194923359b5b8b17ee9e9ff646b33693cc983f2a9984cc21af"


class CountingAdapter(ToolAdapter):
    calls = 0

    def spec(self):
        return ToolSpec(
            "test.v1.read",
            "Test-only read adapter",
            {"type": "object", "properties": {}, "additionalProperties": False},
            True, False, "test.v1",
        )

    def invoke(self, arguments, context):
        type(self).calls += 1
        return {"value": "ok"}


class V1SystemBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), hg_runtime.Handler)
        cls.server.phone_bridge = object()
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def test_model_gateway_injects_exact_v1_before_role_context(self):
        prompt = hg_runtime._v1_governance_prompt()
        self.assertIn("MASTER GOVERNANCE RULESET V1 - SOLE GOVERNING SOURCE", prompt)
        self.assertIn(EXPECTED_SHA256, prompt)
        self.assertIn("### G1 — TOÀN QUYỀN TỰ CHỦ THỰC THI", prompt)
        self.assertLess(
            prompt.index("Tính chính xác của nguồn và độ tin cậy"),
            prompt.index("Toàn quyền tự chủ thực thi và hoàn thành mục tiêu"),
        )
        self.assertLess(
            prompt.index("Toàn quyền tự chủ thực thi và hoàn thành mục tiêu"),
            prompt.index("Học hỏi, cải tiến và sáng tạo"),
        )

    def test_http_health_exposes_verified_governance_binding(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn.request("GET", "/api/health")
        response = conn.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        self.assertEqual(response.getheader("X-HG-Governance-Source-SHA256"), EXPECTED_SHA256)
        conn.close()
        self.assertEqual(response.status, 200)
        self.assertEqual(payload["governance"]["status"], "VERIFIED")
        self.assertEqual(payload["governance"]["source_sha256"], EXPECTED_SHA256)
        self.assertFalse(payload["governance"]["legacy_policy_fallback"])

    def test_model_gateway_sends_v1_in_actual_request(self):
        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self):
                return json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode("utf-8")
        with patch.dict(os.environ, {"HG_MODEL_API_KEY": "TEST-ONLY", "HG_MODEL_BASE_URL": "https://example.invalid", "HG_MODEL_ID": "test-model"}):
            with patch.object(hg_runtime, "urlopen", return_value=FakeResponse()) as mocked:
                model, message = hg_runtime._chat([{"role": "system", "content": "ROLE-CONTEXT"}, {"role": "user", "content": "hello"}])
        request = mocked.call_args.args[0]
        body = json.loads(request.data.decode("utf-8"))
        system = body["messages"][0]["content"]
        self.assertEqual(message.get("content"), "ok")
        self.assertIn("MASTER GOVERNANCE RULESET V1 - SOLE GOVERNING SOURCE", system)
        self.assertIn(EXPECTED_SHA256, system)
        self.assertIn("ROLE-CONTEXT", system)
        self.assertLess(system.index(EXPECTED_SHA256), system.index("SUPPLEMENTAL ROLE/TASK CONTEXT - SUBORDINATE TO V1"))

    def test_runtime_startup_fails_closed_if_v1_invalid(self):
        with patch.object(hg_runtime, "verify_policy", side_effect=GovernanceLoadError("tampered")):
            with self.assertRaisesRegex(SystemExit, "HG_RUNTIME_BLOCKED_V1_POLICY_INVALID"):
                hg_runtime.run(host="127.0.0.1", port=0)

    def test_http_request_fails_closed_if_v1_invalid(self):
        with patch.object(hg_runtime, "verify_policy", side_effect=GovernanceLoadError("tampered")):
            conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
            conn.request("GET", "/api/health")
            response = conn.getresponse()
            payload = json.loads(response.read().decode("utf-8"))
            conn.close()
        self.assertEqual(response.status, 503)
        self.assertEqual(payload["error"]["code"], "V1_POLICY_INVALID")

    def test_direct_registry_dispatch_is_bound_to_v1(self):
        CountingAdapter.calls = 0
        registry = ToolRegistry()
        registry.register(CountingAdapter())
        result = registry.dispatch("test.v1.read", {}, ToolContext("TEST-V1"))
        self.assertTrue(result.ok)
        self.assertEqual(CountingAdapter.calls, 1)
        self.assertEqual(result.witness["governance_source_sha256"], EXPECTED_SHA256)

    def test_direct_registry_dispatch_fails_closed_on_invalid_v1(self):
        CountingAdapter.calls = 0
        registry = ToolRegistry()
        registry.register(CountingAdapter())
        with patch.object(tool_runtime_module, "verify_policy", side_effect=GovernanceLoadError("tampered")):
            result = registry.dispatch("test.v1.read", {}, ToolContext("TEST-V1"))
        self.assertFalse(result.ok)
        self.assertEqual(result.output["error"], "V1_POLICY_INVALID")
        self.assertEqual(CountingAdapter.calls, 0)

    def test_governed_tool_executor_fails_closed_on_invalid_v1(self):
        CountingAdapter.calls = 0
        registry = ToolRegistry()
        registry.register(CountingAdapter())
        governance = ToolGovernance(registry)
        with patch.object(tool_governance_module, "verify_policy", side_effect=GovernanceLoadError("tampered")):
            result = governance.execute("TEST-V1", "test.v1.read", {}, call_id="TEST-V1-BLOCK")
        self.assertFalse(result.ok)
        self.assertEqual(result.output["error"], "V1_POLICY_INVALID")
        self.assertEqual(CountingAdapter.calls, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
