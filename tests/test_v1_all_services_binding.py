import http.client
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("HG_BACKEND_DATA", tempfile.mkdtemp(prefix="hg-v1-backend-test-"))

from core.runtime_v1.engine import GovernanceLoadError
from backend import hg_backend
from edge import edge
from authority import authority

EXPECTED_SHA256 = "cc1a8b171b1c0e194923359b5b8b17ee9e9ff646b33693cc983f2a9984cc21af"


class V1ServiceBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.servers = []
        cls.threads = []
        configs = [
            (hg_backend.H, "/backend/health"),
            (edge.H, "/edge/health"),
            (authority.H, "/authority/health"),
        ]
        cls.targets = []
        for handler, path in configs:
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            cls.servers.append(server)
            cls.threads.append(thread)
            cls.targets.append((server.server_address[1], path, handler.__module__))

    @classmethod
    def tearDownClass(cls):
        for server in cls.servers:
            server.shutdown()
            server.server_close()
        for thread in cls.threads:
            thread.join(timeout=2)

    def request(self, port, path):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        conn.request("GET", path)
        response = conn.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        status = response.status
        conn.close()
        return status, payload

    def test_all_service_health_endpoints_report_v1(self):
        for port, path, module_name in self.targets:
            status, payload = self.request(port, path)
            self.assertEqual(status, 200, module_name)
            governance = payload.get("governance", {})
            self.assertEqual(governance.get("status"), "VERIFIED", module_name)
            self.assertEqual(governance.get("source_sha256"), EXPECTED_SHA256, module_name)

    def test_backend_fails_closed_when_v1_invalid(self):
        with patch.object(hg_backend, "verify_policy", side_effect=GovernanceLoadError("tampered")):
            status, payload = self.request(self.targets[0][0], self.targets[0][1])
        self.assertEqual(status, 503)
        self.assertEqual(payload["error"]["code"], "V1_POLICY_INVALID")

    def test_edge_fails_closed_when_v1_invalid(self):
        with patch.object(edge, "verify_policy", side_effect=GovernanceLoadError("tampered")):
            status, payload = self.request(self.targets[1][0], self.targets[1][1])
        self.assertEqual(status, 503)
        self.assertEqual(payload["error"]["code"], "V1_POLICY_INVALID")

    def test_authority_fails_closed_when_v1_invalid(self):
        with patch.object(authority, "verify_policy", side_effect=GovernanceLoadError("tampered")):
            status, payload = self.request(self.targets[2][0], self.targets[2][1])
        self.assertEqual(status, 503)
        self.assertEqual(payload["error"]["code"], "V1_POLICY_INVALID")


if __name__ == "__main__":
    unittest.main(verbosity=2)
