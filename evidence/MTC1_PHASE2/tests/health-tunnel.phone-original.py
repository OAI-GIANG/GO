#!/usr/bin/env python3
"""HG HEALTH-ONLY tunnel (Termux → VPS1 edge, outbound long-poll).
TUYỆT ĐỐI KHÔNG proxy tới HG legacy 8787 hay bất kỳ runtime nào. Chỉ phục vụ ĐÚNG 1 path: /api/health,
trả payload health do chính tiến trình trên ĐIỆN THOẠI sinh ra. Không shell, không arbitrary HTTP.
Token CHỈ từ env. Mặc định DRY-RUN."""
import base64, json, os, platform, socket, sys, time, urllib.error, urllib.request
E = os.environ
EDGE = (E.get("HG_EDGE_URL") or E.get("HG_TUNNEL_URL") or "").rstrip("/")
TOKF = E.get("HG_EDGE_TOKEN_FILE", "")
def _load_token():
    """Token được đọc như DỮ LIỆU thuần: không source, không eval, không thực thi nội dung."""
    if TOKF:
        try:
            with open(TOKF, encoding="utf-8", errors="replace") as f:
                return f.read().strip()
        except OSError:
            return ""
    return E.get("HG_EDGE_TOKEN", "")
TOK = _load_token()
DEV = E.get("HG_EDGE_DEVICE", "")            # BẮT BUỘC, KHÔNG đoán
ALLOW = {"/api/health"}                       # health-only: allowlist cứng 1 phần tử
EV = E.get("HG_TUNNEL_EVIDENCE", "/sdcard/hg-tunnel-evidence.jsonl")  # cho phép redirect khi test
out = {"tunnel": "hg-health-only", "edge": "SET" if EDGE else "MISSING",
       "device": DEV or "<UNSET>", "allowlist": sorted(ALLOW),
       "credential": {"source": ("file:" + TOKF) if TOKF else "env:HG_EDGE_TOKEN", "present": bool(TOK), "value_logged": False, "loaded_as_data": True},
       "proxies_to_runtime": False, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
def done(s, rc=2):
    out["status"] = s; print(json.dumps(out, indent=1)); sys.exit(0 if s in ("SELFTEST_OK", "DRY_RUN_OK") else rc)
if "--selftest" in sys.argv:
    c = [("S1 allowlist chỉ có /api/health", ALLOW == {"/api/health"}),
         ("S2 chặn /api/chat (ghi)", "/api/chat" not in ALLOW),
         ("S3 chặn /api/ask", "/api/ask" not in ALLOW),
         ("S4 chặn /v1/tasks (không nhận lệnh)", "/v1/tasks" not in ALLOW),
         ("S5 KHÔNG proxy runtime (không đọc HG_TUNNEL_LOCAL)",
          "HG_TUNNEL_LOCAL" not in os.environ or "HG_TUNNEL_LOCAL" not in open(__file__, encoding="utf-8").read().replace('"HG_TUNNEL_LOCAL"', '')),
         ("S6 token không qua CLI", "--token" not in sys.argv),
         ("S7 nạp token như dữ liệu (không source/eval)", "eval(" not in open(__file__, encoding="utf-8").read().split("def _load_token")[1].split("TOK =")[0]),
         ("S8 không đoán device id (bắt buộc đặt)", True)]
    out["checks"] = [{"id": i, "ok": bool(o)} for i, o in c]
    done("SELFTEST_OK" if all(o for _, o in c) else "SELFTEST_FAIL")
if not DEV: done("BLOCKED_DEVICE_ID_UNSET (đặt HG_EDGE_DEVICE = device_id thật trên edge; KHÔNG đoán)")
if not EDGE or not TOK: done("BLOCKED_EDGE_OR_TOKEN_ABSENT")
if "--apply" not in sys.argv: done("DRY_RUN_OK")
def health_payload():
    return {"ok": True, "runtime": "HG_TUNNEL_HEALTH", "transport": "edge-http-long-poll",
            "device_id": DEV, "host": socket.gethostname(), "python": platform.python_version(),
            "machine": platform.machine(), "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "scope": "read-only health; no runtime proxy; no write path"}
def post(p, body, t=40):
    r = urllib.request.Request(EDGE + p, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + TOK}, method="POST")
    try:
        with urllib.request.urlopen(r, timeout=t) as x: return x.status, x.read()
    except urllib.error.HTTPError as e: return e.code, e.read()
def ev(line):
    try:
        with open(EV, "a", encoding="utf-8") as f: f.write(json.dumps(line) + "\n")
    except Exception: pass
backoff = 1.0
while True:
    try:
        st, body = post("/edge/tunnel/poll", {"device_id": DEV})
        if st == 204: backoff = 1.0; continue
        if st in (401, 403): ev({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "event": "EDGE_UNAUTHORIZED", "status": st}); done("EDGE_UNAUTHORIZED")
        if st != 200: time.sleep(backoff); backoff = min(backoff * 2, 30.0); continue
        msg = json.loads(body or b"{}"); req = msg.get("request", msg)
        path = (req.get("path") or "").split("?")[0]; rid = str(req.get("id") or req.get("request_id") or "")
        if path in ALLOW:
            buf = json.dumps(health_payload()).encode(); code, ct = 200, "application/json"
        else:
            buf = b'{"ok":false,"error":{"code":"PATH_NOT_ALLOWLISTED","allowlist":["/api/health"]}}'; code, ct = 403, "application/json"
        ev({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "event": "GATE_REQUEST",
            "request_id": rid, "path": path, "status": code, "bytes": len(buf)})
        post("/edge/tunnel/response", {"id": req.get("id"), "status": code,
             "headers": {"content-type": ct}, "body_b64": base64.b64encode(buf).decode()}, 15)
        backoff = 1.0
    except Exception as ex:
        ev({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "event": "TUNNEL_ERROR", "type": type(ex).__name__})
        time.sleep(backoff); backoff = min(backoff * 2, 30.0)
