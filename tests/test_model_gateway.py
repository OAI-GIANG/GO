import unittest

from runtime.go_runtime.core.contracts import ModelRequest, ModelResult
from runtime.go_runtime.core.model_gateway import (
    PLUGIN_CONTRACT_VERSION,
    PLUGIN_EXTENSION_POINT,
    EchoAdapter,
    ModelGateway,
    OpenAICompatibleAdapter,
    ProviderAdapter,
)

class PluginContractV1Tests(unittest.TestCase):
    def test_echo_exposes_canonical_contract(self):
        adapter = EchoAdapter()
        adapter.validate_contract()
        self.assertEqual(adapter.plugin_id, "go.local.echo")
        self.assertEqual(adapter.plugin_version, "1.0.0")
        self.assertEqual(adapter.contract_version, PLUGIN_CONTRACT_VERSION)
        self.assertEqual(adapter.extension_point, PLUGIN_EXTENSION_POINT)
        self.assertEqual(adapter.supported_operations, ("echo",))
        self.assertEqual(adapter.source, "runtime.go_runtime.core.model_gateway")
        self.assertTrue(adapter.provenance)

    def test_echo_old_constructor_and_gateway_path(self):
        gateway = ModelGateway()
        self.assertTrue(gateway.has("local", "local.echo.v1"))
        request = ModelRequest("P01", "local", "local.echo.v1", "echo", {"message": "hello"})
        result = gateway.invoke(request)
        self.assertEqual(result, ModelResult("local", "local.echo.v1", {"echo": "hello", "task_id": "P01"}, True))

    def test_openai_old_constructor_compatible(self):
        adapter = OpenAICompatibleAdapter("test-provider", "test-model", "http://127.0.0.1:9", "secret")
        adapter.validate_contract()
        self.assertEqual(adapter.provider_id, "test-provider")
        self.assertEqual(adapter.model_id, "test-model")
        self.assertEqual(adapter.timeout, 60)
        self.assertEqual(adapter.supported_operations, ("ask", "echo"))

    def test_model_request_and_result_shapes_unchanged(self):
        request = ModelRequest("T", "p", "m", "ask", {"message": "x"})
        result = ModelResult("p", "m", {"text": "y"}, True)
        self.assertEqual(request.__dataclass_fields__.keys(), {"task_id", "provider", "model", "operation", "payload"})
        self.assertEqual(result.__dataclass_fields__.keys(), {"provider", "model", "output", "success"})

    def test_invalid_contract_version_rejected(self):
        adapter = EchoAdapter()
        adapter.contract_version = "PLUGIN-CONTRACT-V0"
        with self.assertRaises(ValueError):
            adapter.validate_contract()

    def test_invalid_extension_point_rejected(self):
        adapter = EchoAdapter()
        adapter.extension_point = "memory.provider"
        with self.assertRaises(ValueError):
            adapter.validate_contract()

    def test_missing_plugin_identity_rejected(self):
        adapter = EchoAdapter()
        adapter.plugin_id = ""
        with self.assertRaises(ValueError):
            adapter.validate_contract()

    def test_missing_operations_rejected(self):
        adapter = EchoAdapter()
        adapter.supported_operations = ()
        with self.assertRaises(ValueError):
            adapter.validate_contract()

    def test_gateway_rejects_non_adapter(self):
        with self.assertRaises(TypeError):
            ModelGateway().register(object())

    def test_gateway_rejects_invalid_adapter_contract(self):
        class BadAdapter(ProviderAdapter):
            def __init__(self):
                super().__init__("bad", "bad.model", plugin_id="bad", supported_operations=("ask",),
                                 extension_point="not.model.provider")
            def invoke(self, request):
                return ModelResult(self.provider_id, self.model_id, {}, True)
        with self.assertRaises(ValueError):
            ModelGateway().register(BadAdapter())

    def test_unknown_provider_model_still_fails_at_gateway(self):
        request = ModelRequest("N01", "unknown", "unknown", "ask", {})
        with self.assertRaises(ValueError):
            ModelGateway().invoke(request)

    def test_plugin_does_not_gain_core_authority_surfaces(self):
        adapter = EchoAdapter()
        forbidden = {"authorize", "emit_evidence", "verify_evidence", "observe_memory",
                     "promote_memory", "enqueue", "claim", "finalize"}
        self.assertTrue(forbidden.isdisjoint(set(dir(adapter))))

    def test_missing_provider_or_model_rejected(self):
        for provider, model in (("", "m"), ("p", "")):
            adapter = ProviderAdapter(provider, model, plugin_id="test", supported_operations=("ask",))
            with self.assertRaises(ValueError):
                adapter.validate_contract()

    def test_empty_plugin_version_rejected(self):
        adapter = EchoAdapter()
        adapter.plugin_version = ""
        with self.assertRaises(ValueError):
            adapter.validate_contract()

    def test_empty_source_and_provenance_rejected(self):
        for field_name in ("source", "provenance"):
            adapter = EchoAdapter()
            setattr(adapter, field_name, "")
            with self.assertRaises(ValueError):
                adapter.validate_contract()

    def test_blank_supported_operation_rejected(self):
        adapter = EchoAdapter()
        adapter.supported_operations = ("ask", " ")
        with self.assertRaises(ValueError):
            adapter.validate_contract()

    def test_invalid_registration_is_not_inserted(self):
        class BadAdapter(ProviderAdapter):
            def __init__(self):
                super().__init__("atomic", "bad.model", plugin_id="bad", supported_operations=("ask",),
                                 extension_point="not.model.provider")
            def invoke(self, request):
                return ModelResult(self.provider_id, self.model_id, {}, True)
        gateway = ModelGateway()
        with self.assertRaises(ValueError):
            gateway.register(BadAdapter())
        self.assertFalse(gateway.has("atomic", "bad.model"))

    def test_valid_custom_adapter_registers(self):
        class CustomAdapter(ProviderAdapter):
            def __init__(self):
                super().__init__("custom", "custom.model", plugin_id="custom.plugin", supported_operations=("ask",))
            def invoke(self, request):
                return ModelResult(self.provider_id, self.model_id, {"text": "ok"}, True)
        gateway = ModelGateway()
        adapter = CustomAdapter()
        gateway.register(adapter)
        self.assertTrue(gateway.has("custom", "custom.model"))

    def test_openai_adapter_exposes_canonical_contract_metadata(self):
        adapter = OpenAICompatibleAdapter("test-provider", "test-model", "http://127.0.0.1:9", "secret")
        adapter.validate_contract()
        self.assertEqual(adapter.plugin_id, "go.test-provider.openai-compatible")
        self.assertEqual(adapter.plugin_version, "1.0.0")
        self.assertEqual(adapter.contract_version, PLUGIN_CONTRACT_VERSION)
        self.assertEqual(adapter.extension_point, PLUGIN_EXTENSION_POINT)
        self.assertEqual(adapter.supported_operations, ("ask", "echo"))
        self.assertEqual(adapter.source, "runtime.go_runtime.core.model_gateway")
        self.assertTrue(adapter.provenance)

    def test_configured_reasoning_provider_registers_without_network(self):
        import os
        names = ("GO_MODEL_BASE_URL", "GO_MODEL_PROVIDER", "GO_MODEL_ID", "GO_MODEL_API_KEY")
        previous = {name: os.environ.get(name) for name in names}
        try:
            os.environ.update({
                "GO_MODEL_BASE_URL": "http://127.0.0.1:9",
                "GO_MODEL_PROVIDER": "test-provider",
                "GO_MODEL_ID": "test-model",
                "GO_MODEL_API_KEY": "secret",
            })
            gateway = ModelGateway()
            self.assertTrue(gateway.has("test-provider", "test-model"))
            self.assertEqual(gateway.reasoning_provider, "test-provider")
            self.assertEqual(gateway.reasoning_model, "test-model")
        finally:
            for name, value in previous.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

    def test_incomplete_reasoning_configuration_preserves_default(self):
        import os
        names = ("GO_MODEL_BASE_URL", "GO_MODEL_PROVIDER", "GO_MODEL_ID", "GO_MODEL_API_KEY")
        previous = {name: os.environ.get(name) for name in names}
        try:
            for name in names:
                os.environ.pop(name, None)
            gateway = ModelGateway()
            self.assertEqual(gateway.default_provider, "local")
            self.assertEqual(gateway.default_model, "local.echo.v1")
            self.assertIsNone(gateway.reasoning_provider)
            self.assertIsNone(gateway.reasoning_model)
        finally:
            for name, value in previous.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

if __name__ == "__main__":
    unittest.main()
