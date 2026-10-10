"""G2 — real HTTP handler tests for the approval transport contract.

Starts the actual ThreadingHTTPServer (GOApplication) and asserts exact HTTP status,
body, and the absence of task/event side effects for requests that must be rejected
before execution.
"""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

import pytest

TOKEN = "g2-http-test-token"


@pytest.fixture(scope="module")
def g2_server(tmp_path_factory):
    import os
    d = tmp_path_factory.mktemp("g2http")
    key = d / "root.key"
    key.write_bytes(b"g2-http-test-external-root-key")
    os.environ["HG_AUTHORITY_ROOT_KEY_FILE"] = str(key)
    os.environ["GO_HOST"] = "127.0.0.1"
    os.environ["GO_PORT"] = "0"
    os.environ["GO_ALLOW_ANONYMOUS"] = "false"
    os.environ["GO_API_TOKEN"] = TOKEN
    os.environ["GO_DATA"] = str(d / "go.sqlite3")
    os.environ["GO_COMMIT"] = "g2-test"
    os.environ["GO_TREE_SHA"] = "g2-test"
    os.environ["GO_ENV"] = "test"
    from runtime.go_runtime.core.server import create_server
    srv = create_server()
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield srv, port
    finally:
        srv.shutdown()
        srv.server_close()


def _post(port, body, *, token=True):
    req = urllib.request.Request("http://127.0.0.1:%d/v1/tasks" % port,
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json",
                                          **({"Authorization": "Bearer " + TOKEN} if token else {})},
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw or "{}")
        except Exception:
            return e.code, {"raw": raw}


def _get(port, path):
    req = urllib.request.Request("http://127.0.0.1:%d%s" % (port, path), method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, {}


def test_g2_http_healthz(g2_server):
    _srv, port = g2_server
    status, body = _get(port, "/healthz")
    assert status == 200 and body.get("status") == "ok"
    assert body.get("governance", {}).get("status") == "VERIFIED"


def test_g2_http_requires_auth(g2_server):
    _srv, port = g2_server
    status, _ = _post(port, {"operation": "echo", "payload": {}}, token=False)
    assert status == 401


def test_g2_http_echo_no_approval_ok(g2_server):
    _srv, port = g2_server
    status, body = _post(port, {"task_id": "T-ECHO", "operation": "echo", "payload": {"message": "hi"}})
    assert status == 200 and body.get("state") == "COMPLETED"


@pytest.mark.parametrize("approval", [
    "approved",                      # bare string is NOT approval evidence
    ["x"],                           # array
    123,                             # scalar
    {"approval_id": "A"},            # missing required fields
    {"approval_id": "A", "approver_id": "o", "subject": "s", "tool_name": "t",
     "arguments_digest": "d", "policy_sha256": "p", "scope": "sc", "expires_at": "e",
     "nonce": "n", "signature": "sig", "issuer_id": "i", "EXTRA": "x"},  # unknown field
])
def test_g2_http_malformed_approval_rejected_before_side_effect(g2_server, approval):
    srv, port = g2_server
    tid = "T-BAD-" + str(abs(hash(str(approval))))[:8]
    status, body = _post(port, {"task_id": tid, "operation": "echo", "payload": {}, "approval": approval})
    assert status == 400, (status, body)
    # no task materialised and no misleading execution event
    assert srv.app.store.get_task(tid) is None
