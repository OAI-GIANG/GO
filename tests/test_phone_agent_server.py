import base64
import hashlib
import json
import os
import socket
import struct
import threading
import urllib.request
import uuid

from runtime.go_runtime.core.server import RuntimeConfig, create_server


def ws_frame(text: str) -> bytes:
    payload = text.encode()
    mask = b"abcd"
    head = bytearray([0x81, 0x80 | len(payload)])
    head.extend(mask)
    head.extend(bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))
    return bytes(head)


def read_ws(sock: socket.socket) -> dict:
    head = sock.recv(2)
    length = head[1] & 0x7F
    data = sock.recv(length)
    return json.loads(data.decode())


def test_phone_register_and_websocket_command(tmp_path, monkeypatch):
    monkeypatch.setenv("GO_API_TOKEN", "api-secret")
    monkeypatch.setenv("GO_PHONE_PAIRING_TOKEN", "pair-secret")
    cfg = RuntimeConfig()
    cfg.port = 0
    cfg.data_path = tmp_path / "phone.sqlite3"
    server = create_server(cfg)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]

    body = json.dumps({
        "pairing_token": "pair-secret",
        "device_id": "test-phone",
        "name": "Test Phone",
        "platform": "android",
        "capabilities": ["ping"],
    }).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/phone/register",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as response:
        registration = json.loads(response.read())
    token = registration["device_token"]

    sock = socket.create_connection(("127.0.0.1", port))
    key = base64.b64encode(os.urandom(16)).decode()
    handshake = (
        f"GET /v1/phone/ws?device_id=test-phone HTTP/1.1\r\n"
        f"Host: 127.0.0.1:{port}\r\n"
        "Upgrade: websocket\r\nConnection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n"
        f"Authorization: Bearer {token}\r\n\r\n"
    )
    sock.sendall(handshake.encode())
    response = sock.recv(4096).decode()
    assert "101 Switching Protocols" in response
    hello = read_ws(sock)
    assert hello["type"] == "hello"
    assert hello["device_id"] == "test-phone"

    command_body = json.dumps({
        "device_id": "test-phone",
        "command": {"type": "ping"},
    }).encode()
    command_req = urllib.request.Request(
        f"http://127.0.0.1:{port}/v1/phone/commands",
        data=command_body,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer api-secret",
        },
        method="POST",
    )
    with urllib.request.urlopen(command_req) as response:
        accepted = json.loads(response.read())
    assert accepted["accepted"] is True

    message = read_ws(sock)
    assert message["type"] == "command"
    assert message["command"]["type"] == "ping"

    sock.sendall(ws_frame(json.dumps({"type": "heartbeat"})))
    ack = read_ws(sock)
    assert ack["type"] == "heartbeat_ack"

    sock.close()
    server.shutdown()
    server.server_close()


def test_pairing_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("GO_API_TOKEN", "api-secret")
    monkeypatch.setenv("GO_PHONE_PAIRING_TOKEN", "pair-secret")
    cfg = RuntimeConfig()
    cfg.port = 0
    cfg.data_path = tmp_path / "phone.sqlite3"
    server = create_server(cfg)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]

    body = json.dumps({
        "pairing_token": "wrong",
        "device_id": "bad-phone",
        "capabilities": [],
    }).encode()
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/phone/register",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req)
        assert False, "pairing must be rejected"
    except urllib.error.HTTPError as exc:
        assert exc.code == 401
    finally:
        server.shutdown()
        server.server_close()
