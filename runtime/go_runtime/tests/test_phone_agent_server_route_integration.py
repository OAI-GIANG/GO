"""Real GO Handler HTTP test for Phone Agent v2 routes; uses only ephemeral loopback + test-only credentials."""
import json
import os
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
import socket

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from runtime.go_runtime.core import server as go_server

os.environ["HG_PHONE_PAIRING_TOKENS"] = "TEST-PAIRING-ONLY"
os.environ["HG_PHONE_INTERNAL_KEY"] = "TEST-INTERNAL-ONLY"
go_server._PHONE_AGENT = None

httpd = ThreadingHTTPServer(("127.0.0.1", 0), go_server.Handler)
httpd.app = None
thread = threading.Thread(target=httpd.serve_forever, daemon=True)
thread.start()
base = f"http://127.0.0.1:{httpd.server_address[1]}"
passed = []
failed = []


def call(path, body=None, token=None, internal=None, raw=None):
    payload = raw if raw is not None else json.dumps(body or {}).encode()
    req = urllib.request.Request(base + path, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    if internal:
        req.add_header("X-Internal-Key", internal)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def check(name, condition):
    (passed if condition else failed).append(name)


try:
    status, body = call("/api/phone/register", {"pairing_token": "WRONG-TEST", "device_id": "test-device"})
    check("go_handler_wrong_pairing_denied", status == 403 and body["error"]["code"] == "PAIRING_DENIED")

    status, body = call("/internal/phone/enqueue", {"device_id": "", "capability": "READ_FILE", "params": {"path": "x.py"}}, internal="TEST-INTERNAL-ONLY")
    check("go_handler_requires_registered_device", status == 409 and body["error"]["code"] == "DEVICE_NOT_REGISTERED")

    status, body = call("/api/phone/register", {"pairing_token": "TEST-PAIRING-ONLY", "device_id": "test-device", "name": "test"})
    token = body.get("device_token", "")
    check("go_handler_register", status == 200 and bool(token) and body.get("protocol") == "LONGPOLL_HTTPS_V2")

    status, body = call("/api/phone/poll", {"wait_s": 0}, token="invalid.test")
    check("go_handler_bad_device_token_denied", status == 401 and body["error"]["code"] == "TOKEN_INVALID")

    status, body = call("/internal/phone/enqueue", {"device_id": "test-device", "capability": "WRITE_FILE", "params": {"path": "../escape.txt"}})
    check("go_handler_internal_key_required", status == 403 and body["error"]["code"] == "INTERNAL_FORBIDDEN")

    status, body = call("/internal/phone/enqueue", {"device_id": "test-device", "capability": "WRITE_FILE", "params": {"path": "../escape.txt"}}, internal="TEST-INTERNAL-ONLY")
    check("go_handler_path_traversal_denied", status == 400 and body["error"]["code"] == "PATH_REJECTED")

    status, queued = call("/internal/phone/enqueue", {"device_id": "test-device", "capability": "WRITE_FILE", "params": {"path": "test.txt", "content_b64": "aGk="}}, internal="TEST-INTERNAL-ONLY")
    request_id = queued.get("request_id", "")
    check("go_handler_enqueue", status == 200 and request_id.startswith("CALL-"))

    status, delivered = call("/api/phone/poll", {"wait_s": 0}, token=token)
    check("go_handler_poll", status == 200 and delivered.get("request_id") == request_id and delivered.get("capability") == "WRITE_FILE")

    status, body = call("/api/phone/result", {"request_id": "CALL-not-this-device", "ok": True}, token=token)
    check("go_handler_result_correlation", status == 409 and body["error"]["code"] == "REQUEST_MISMATCH")

    status, body = call("/api/phone/result", {"request_id": request_id, "ok": True, "result": {"sha256": "sha256:test-only"}}, token=token)
    check("go_handler_result", status == 200 and body.get("state") == "DONE")

    status, body = call("/api/phone/result", {"request_id": request_id, "ok": True}, token=token)
    check("go_handler_replay_denied", status == 409 and body["error"]["code"] == "REPLAY_REJECTED")

    with socket.create_connection(httpd.server_address, timeout=5) as sock:
        oversized = (f"POST /api/phone/register HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                     f"Content-Length: {2 * 1024 * 1024 + 1}\r\nConnection: close\r\n\r\n").encode()
        sock.sendall(oversized)
        status_line = sock.recv(512).splitlines()[0]
    check("go_handler_body_limit", b" 413 " in status_line)

    status, body = call("/internal/phone/enqueue", {"device_id": "", "capability": "READ_FILE", "params": {"path": "x.py"}}, internal="TEST-INTERNAL-ONLY")
    check("go_handler_selects_only_registered_device", status == 200 and body.get("device_id") == "test-device")

    status, second = call("/api/phone/register", {"pairing_token": "TEST-PAIRING-ONLY", "device_id": "test-device-2", "name": "second"})
    check("go_handler_second_device_registers", status == 200 and bool(second.get("device_token")))
    status, body = call("/internal/phone/enqueue", {"device_id": "", "capability": "READ_FILE", "params": {"path": "x.py"}}, internal="TEST-INTERNAL-ONLY")
    check("go_handler_ambiguous_device_fails_closed", status == 409 and body["error"]["code"] == "DEVICE_ID_REQUIRED")

    check("go_handler_audit_chain", go_server._PHONE_AGENT.agent.verify_audit()["ok"])
finally:
    httpd.shutdown()
    httpd.server_close()

for name in passed:
    print(f"PASS | {name}")
for name in failed:
    print(f"FAIL | {name}")
print(f"GO_HANDLER_HTTP_E2E PASS={len(passed)} FAIL={len(failed)}")
raise SystemExit(0 if not failed else 1)
