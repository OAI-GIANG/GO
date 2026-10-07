from __future__ import annotations

import base64
import hashlib
import json
import secrets
import struct
import threading
import uuid
from typing import Any

PHONE_WS_PATH = "/v1/phone/ws"
PHONE_REGISTER_PATH = "/api/phone/register"
PHONE_COMMAND_PATH = "/v1/phone/commands"
MAX_FRAME = 256 * 1024


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class PhoneSessionRegistry:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sessions: dict[str, Any] = {}

    def attach(self, device_id: str, handler: Any) -> None:
        with self._lock:
            old = self._sessions.get(device_id)
            if old is not None and old is not handler:
                try:
                    old.close_connection = True
                    old.connection.close()
                except Exception:
                    pass
            self._sessions[device_id] = handler

    def detach(self, device_id: str, handler: Any) -> None:
        with self._lock:
            if self._sessions.get(device_id) is handler:
                self._sessions.pop(device_id, None)

    def get(self, device_id: str) -> Any | None:
        with self._lock:
            return self._sessions.get(device_id)


def _accept_key(key: str) -> str:
    raw = hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()
    return base64.b64encode(raw).decode("ascii")


def _read_exact(stream: Any, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = stream.read(size - len(data))
        if not chunk:
            raise ConnectionError("websocket closed")
        data.extend(chunk)
    return bytes(data)


def read_frame(stream: Any) -> tuple[int, bytes]:
    first, second = _read_exact(stream, 2)
    opcode = first & 0x0F
    length = second & 0x7F
    masked = bool(second & 0x80)
    if length == 126:
        length = struct.unpack("!H", _read_exact(stream, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", _read_exact(stream, 8))[0]
    if length > MAX_FRAME:
        raise ValueError("websocket frame too large")
    mask = _read_exact(stream, 4) if masked else b""
    payload = bytearray(_read_exact(stream, length))
    if masked:
        for i in range(length):
            payload[i] ^= mask[i % 4]
    return opcode, bytes(payload)


def send_frame(stream: Any, opcode: int, payload: bytes) -> None:
    if len(payload) > MAX_FRAME:
        raise ValueError("websocket frame too large")
    head = bytearray([0x80 | (opcode & 0x0F)])
    if len(payload) < 126:
        head.append(len(payload))
    elif len(payload) < 65536:
        head.append(126)
        head.extend(struct.pack("!H", len(payload)))
    else:
        head.append(127)
        head.extend(struct.pack("!Q", len(payload)))
    stream.write(bytes(head) + payload)
    stream.flush()


def send_json(handler: Any, value: dict[str, Any]) -> None:
    send_frame(handler.wfile, 1, json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def register(app: Any, body: dict[str, Any]) -> dict[str, Any]:
    pairing = str(body.get("pairing_token") or "")
    expected = str(__import__("os").getenv("GO_PHONE_PAIRING_TOKEN", ""))
    if not expected or not secrets.compare_digest(pairing, expected):
        raise PermissionError("PHONE_PAIRING_FAILED")
    device_id = str(body.get("device_id") or "").strip()
    if not device_id or len(device_id) > 200:
        raise ValueError("device_id is required")
    capabilities = body.get("capabilities") or []
    if not isinstance(capabilities, list) or any(not isinstance(x, str) for x in capabilities):
        raise ValueError("capabilities must be a string list")
    token = secrets.token_urlsafe(32)
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
    app.store.upsert_phone_device({
        "device_id": device_id,
        "name": str(body.get("name") or "HG Phone"),
        "platform": str(body.get("platform") or "unknown"),
        "capabilities": capabilities,
        "token_hash": token_hash(token),
        "created_at": now,
        "updated_at": now,
    })
    return {"device_id": device_id, "device_token": token, "protocol_version": "1.1"}


def authenticate_device(app: Any, device_id: str, token: str) -> bool:
    record = app.store.get_phone_device(device_id)
    return bool(record and secrets.compare_digest(str(record.get("token_hash")), token_hash(token)))


def websocket_session(app: Any, handler: Any, device_id: str, token: str, sessions: PhoneSessionRegistry) -> None:
    if not authenticate_device(app, device_id, token):
        raise PermissionError("PHONE_AUTHENTICATION_FAILED")
    sessions.attach(device_id, handler)
    handler.close_connection = False
    send_json(handler, {"type": "hello", "protocol_version": "1.1", "device_id": device_id})
    try:
        while not handler.close_connection:
            opcode, payload = read_frame(handler.rfile)
            if opcode == 8:
                break
            if opcode == 9:
                send_frame(handler.wfile, 10, payload)
                continue
            if opcode != 1:
                continue
            try:
                message = json.loads(payload.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                send_json(handler, {"type": "error", "code": "MESSAGE_SCHEMA_INVALID"})
                continue
            if message.get("type") == "heartbeat":
                send_json(handler, {"type": "heartbeat_ack"})
            elif message.get("type") == "result":
                app.store.add_event(
                    None, "PHONE_COMMAND_RESULT",
                    {"device_id": device_id, "message": message},
                    __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
                )
    finally:
        sessions.detach(device_id, handler)


def send_command(app: Any, sessions: PhoneSessionRegistry, device_id: str, command: dict[str, Any]) -> dict[str, Any]:
    handler = sessions.get(device_id)
    if handler is None:
        raise ConnectionError("PHONE_NOT_CONNECTED")
    command_id = str(command.get("id") or uuid.uuid4())
    message = {"type": "command", "id": command_id, "command": command}
    send_json(handler, message)
    return {"accepted": True, "device_id": device_id, "command_id": command_id}
