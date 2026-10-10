"""Mount 3 endpoint Phone Agent v2 lên HTTP server thật (stdlib) để nhúng vào GO server.py.
Không expose endpoint enqueue cho client: enqueue yêu cầu header nội bộ X-Internal-Key."""
from __future__ import annotations
import hmac, json, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable

from phone_agent_server_v2 import PhoneAgentServer, ProtoError

STATUS = {"PAIRING_DENIED": 403, "TOKEN_INVALID": 401, "TOKEN_EXPIRED": 401, "CAPABILITY_DENIED": 400,
          "PATH_REJECTED": 400, "REQUEST_MISMATCH": 409, "REPLAY_REJECTED": 409, "INVALID_REGISTER": 400}
MAX_BODY = 262144


class PhoneAgentHTTP:
    """Router thuần (không phụ thuộc framework) để có thể test và nhúng."""

    def __init__(self, agent: PhoneAgentServer, internal_key: str,
                 enqueue_hook: Callable[[str, str, dict], dict] | None = None):
        self.agent = agent
        self.internal_key = internal_key
        self.enqueue_hook = enqueue_hook

    def _bearer(self, headers: dict) -> str:
        a = headers.get("authorization") or headers.get("Authorization") or ""
        return a[7:] if a.lower().startswith("bearer ") else ""

    def handle(self, method: str, path: str, headers: dict, body: bytes) -> tuple[int, dict]:
        try:
            data = json.loads(body.decode() or "{}") if body else {}
        except Exception:
            return 400, {"ok": False, "error": {"code": "INVALID_JSON"}}
        try:
            if method == "POST" and path == "/api/phone/register":
                return 200, self.agent.register(data)
            if method == "POST" and path == "/api/phone/poll":
                return 200, self.agent.poll(self._bearer(headers), float(data.get("wait_s", 1.0)))
            if method == "POST" and path == "/api/phone/result":
                return 200, self.agent.submit_result(self._bearer(headers), data)
            if method == "POST" and path == "/internal/phone/enqueue":
                key = headers.get("x-internal-key") or headers.get("X-Internal-Key") or ""
                if not key or not hmac.compare_digest(key, self.internal_key):
                    return 403, {"ok": False, "error": {"code": "INTERNAL_FORBIDDEN"}}
                if self.enqueue_hook:
                    return 200, self.enqueue_hook(str(data.get("device_id") or ""),
                                                   str(data.get("capability") or ""), data.get("params") or {})
                return 200, self.agent.enqueue(str(data.get("device_id") or ""),
                                               str(data.get("capability") or ""), data.get("params") or {})
            return 404, {"ok": False, "error": {"code": "NOT_FOUND"}}
        except ProtoError as e:
            return STATUS.get(e.code, 400), {"ok": False, "error": {"code": e.code}}


class _Handler(BaseHTTPRequestHandler):
    router: PhoneAgentHTTP = None  # type: ignore

    def _run(self, method: str):
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            return self._send(413, {"ok": False, "error": {"code": "BODY_TOO_LARGE"}})
        body = self.rfile.read(n) if n else b""
        status, payload = self.router.handle(method, self.path, dict(self.headers), body)
        self._send(status, payload)

    def _send(self, status: int, payload: dict):
        raw = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self): self._run("POST")
    def do_GET(self): self._run("GET")
    def log_message(self, *a): pass


def make_http_server(agent: PhoneAgentServer, internal_key: str, host: str = "127.0.0.1", port: int = 0):
    router = PhoneAgentHTTP(agent, internal_key)
    handler = type("H", (_Handler,), {"router": router})
    srv = ThreadingHTTPServer((host, port), handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, router
