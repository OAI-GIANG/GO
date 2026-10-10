"""Phone Agent v2 — server protocol (stdlib-only, gắn được vào GO server.py).
GIAO THỨC v2 (THAY ĐỔI CÓ GHI NHẬN so với V1 WSS): long-poll HTTPS thay cho WSS.
Lý do kỹ thuật: server GO dùng stdlib Python, KHÔNG có WebSocket server; long-poll giữ được
outbound-only từ thiết bị (agent vẫn không mở listener) và không thêm dependency.
Bất biến: pairing token allowlist · device token HMAC có hạn · capability allowlist ·
tương quan request_id · chống replay kết quả · timeout · audit hash-chain."""
from __future__ import annotations
import base64, hashlib, hmac, json, secrets, threading, time
from dataclasses import dataclass, field
from typing import Any

ALLOW_CAPS = {"READ_FILE", "WRITE_FILE", "APPLY_PATCH", "GET_DIFF", "RUN_TEST"}
TERMINAL = {"DONE", "FAILED"}


class ProtoError(Exception):
    def __init__(self, code: str, message: str | None = None):
        self.code = code; super().__init__(message or code)


def _b64(b: bytes) -> str: return base64.urlsafe_b64encode(b).decode().rstrip("=")
def _ub64(s: str) -> bytes: return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


@dataclass
class PhoneAgentServer:
    pairing_tokens: set = field(default_factory=set)
    secret: bytes = field(default_factory=lambda: secrets.token_bytes(32))
    token_ttl_s: int = 3600
    audit: list = field(default_factory=list)
    devices: dict = field(default_factory=dict)     # device_id -> {token, name, created_at}
    commands: dict = field(default_factory=dict)    # request_id -> {device_id, capability, params, state, result}
    queue: dict = field(default_factory=dict)       # device_id -> [request_id, ...]
    _lock: Any = field(default_factory=threading.RLock)

    # ---- audit ----
    def _emit(self, event: str, **kw) -> None:
        rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "seq": len(self.audit) + 1, "event": event, **kw}
        rec["prev"] = self.audit[-1]["h"] if self.audit else "GENESIS"
        rec["h"] = hashlib.sha256(json.dumps(rec, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self.audit.append(rec)

    def verify_audit(self) -> dict:
        prev, bad = "GENESIS", []
        for i, r in enumerate(self.audit, 1):
            h = r.get("h"); c = {k: v for k, v in r.items() if k != "h"}
            if c.get("prev") != prev: bad.append({"seq": i, "reason": "prev"})
            if hashlib.sha256(json.dumps(c, sort_keys=True, separators=(",", ":")).encode()).hexdigest() != h:
                bad.append({"seq": i, "reason": "hash"})
            prev = h
        return {"ok": not bad, "records": len(self.audit), "bad": bad[:5]}

    # ---- token ----
    def _mint(self, device_id: str) -> str:
        exp = int(time.time()) + self.token_ttl_s
        nonce = secrets.token_hex(8)
        payload = f"{device_id}|{exp}|{nonce}"
        sig = hmac.new(self.secret, payload.encode(), hashlib.sha256).hexdigest()[:32]
        return _b64(payload.encode()) + "." + sig

    def _verify(self, token: str) -> str:
        try:
            body, sig = token.split(".", 1)
            payload = _ub64(body).decode()
            dev, exp, _ = payload.split("|")
        except Exception:
            raise ProtoError("TOKEN_INVALID")
        want = hmac.new(self.secret, payload.encode(), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(sig, want): raise ProtoError("TOKEN_INVALID")
        if int(exp) < int(time.time()): raise ProtoError("TOKEN_EXPIRED")
        return dev

    # ---- endpoints ----
    def register(self, body: dict) -> dict:
        pt = str(body.get("pairing_token") or ""); dev = str(body.get("device_id") or "")
        if not pt or not dev: raise ProtoError("INVALID_REGISTER")
        if not any(hmac.compare_digest(pt, t) for t in self.pairing_tokens):
            self._emit("REGISTER_DENIED", device_id=dev, reason="PAIRING_DENIED")
            raise ProtoError("PAIRING_DENIED")
        with self._lock:
            tok = self._mint(dev)
            self.devices[dev] = {"token": tok, "name": str(body.get("name") or ""), "created_at": time.time()}
            self.queue.setdefault(dev, [])
        self._emit("REGISTER_OK", device_id=dev)
        return {"ok": True, "device_id": dev, "device_token": tok, "protocol": "LONGPOLL_HTTPS_V2"}

    def enqueue(self, device_id: str, capability: str, params: dict) -> dict:
        """CHỈ server gọi. Allowlist capability; params không được chứa đường dẫn thoát sandbox."""
        if capability not in ALLOW_CAPS:
            self._emit("ENQUEUE_DENIED", device_id=device_id, capability=capability, reason="CAPABILITY_DENIED")
            raise ProtoError("CAPABILITY_DENIED")
        p = str(params.get("path") or "")
        if p.startswith("/") or ".." in p or "\\" in p:
            self._emit("ENQUEUE_DENIED", device_id=device_id, capability=capability, reason="PATH_REJECTED")
            raise ProtoError("PATH_REJECTED")
        rid = "CALL-" + secrets.token_hex(8)
        with self._lock:
            self.commands[rid] = {"device_id": device_id, "capability": capability, "params": params,
                                  "state": "QUEUED", "result": None, "created_at": time.time()}
            self.queue.setdefault(device_id, []).append(rid)
        self._emit("ENQUEUE", device_id=device_id, capability=capability, request_id=rid)
        return {"ok": True, "request_id": rid}

    def poll(self, token: str, wait_s: float = 1.0, max_wait_s: float = 25.0) -> dict:
        dev = self._verify(token)
        deadline = time.time() + max(0.0, min(wait_s, max_wait_s))
        while True:
            with self._lock:
                q = self.queue.get(dev, [])
                while q:
                    rid = q.pop(0)
                    c = self.commands.get(rid)
                    if c and c["state"] == "QUEUED":
                        c["state"] = "DISPATCHED"
                        self._emit("DISPATCH", device_id=dev, request_id=rid, capability=c["capability"])
                        return {"ok": True, "request_id": rid, "capability": c["capability"], "params": c["params"]}
            if time.time() >= deadline:
                self._emit("POLL_IDLE", device_id=dev)
                return {"ok": True, "idle": True}
            time.sleep(0.05)

    def submit_result(self, token: str, body: dict) -> dict:
        dev = self._verify(token)
        rid = str(body.get("request_id") or "")
        with self._lock:
            c = self.commands.get(rid)
            if not c or c["device_id"] != dev: raise ProtoError("REQUEST_MISMATCH")
            if c["state"] in TERMINAL:
                self._emit("RESULT_REPLAY_REJECTED", device_id=dev, request_id=rid)
                raise ProtoError("REPLAY_REJECTED")
            c["state"] = "DONE" if body.get("ok") else "FAILED"
            c["result"] = body.get("result")
        self._emit("RESULT", device_id=dev, request_id=rid, state=c["state"])
        return {"ok": True, "request_id": rid, "state": c["state"]}

    def fetch_result(self, device_id: str, request_id: str) -> dict:
        c = self.commands.get(request_id)
        if not c or c["device_id"] != device_id: raise ProtoError("REQUEST_MISMATCH")
        return {"ok": True, "request_id": request_id, "state": c["state"], "result": c["result"]}
