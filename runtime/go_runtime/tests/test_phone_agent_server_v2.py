import pathlib, sys, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "go_runtime" / "core"))
from phone_agent_server_v2 import PhoneAgentServer, ProtoError   # noqa
P, F = [], []
def rec(n, c, d=""): (P if c else F).append((n, d))
def code(fn):
    try: fn(); return None
    except ProtoError as e: return e.code
s = PhoneAgentServer(pairing_tokens={"PAIR-OK"}, token_ttl_s=2)
rec("register_wrong_pairing_denied", code(lambda: s.register({"pairing_token": "WRONG", "device_id": "d1"})) == "PAIRING_DENIED")
r = s.register({"pairing_token": "PAIR-OK", "device_id": "d1", "name": "Phone"})
tok = r["device_token"]
rec("register_ok_returns_token", r["ok"] and r["protocol"] == "LONGPOLL_HTTPS_V2" and len(tok) > 20)
rec("poll_bad_token_rejected", code(lambda: s.poll("garbage.aaa", 0)) == "TOKEN_INVALID")
rec("enqueue_unknown_capability_denied", code(lambda: s.enqueue("d1", "SHELL_EXEC", {})) == "CAPABILITY_DENIED")
rec("enqueue_traversal_path_denied", code(lambda: s.enqueue("d1", "WRITE_FILE", {"path": "../../x"})) == "PATH_REJECTED")
e = s.enqueue("d1", "WRITE_FILE", {"path": "a.txt", "content_b64": "aGk="})
p = s.poll(tok, 0.2)
rec("poll_delivers_command", p.get("ok") and p.get("request_id") == e["request_id"] and p["capability"] == "WRITE_FILE")
rec("result_mismatch_rejected", code(lambda: s.submit_result(tok, {"request_id": "CALL-nope", "ok": True})) == "REQUEST_MISMATCH")
ok = s.submit_result(tok, {"request_id": e["request_id"], "ok": True, "result": {"sha256": "sha256:aa"}})
rec("result_accepted", ok["state"] == "DONE")
rec("result_replay_rejected", code(lambda: s.submit_result(tok, {"request_id": e["request_id"], "ok": True})) == "REPLAY_REJECTED")
fr = s.fetch_result("d1", e["request_id"])
rec("fetch_result_correlated", fr["state"] == "DONE" and fr["result"]["sha256"] == "sha256:aa")
rec("poll_idle_on_empty", s.poll(tok, 0.1).get("idle") is True)
time.sleep(2.2)
rec("expired_token_rejected", code(lambda: s.poll(tok, 0)) == "TOKEN_EXPIRED")
rec("audit_chain_valid", s.verify_audit()["ok"] and s.verify_audit()["records"] >= 8)
for n, d in P: print(f"  PASS | {n:36} | {d}")
for n, d in F: print(f"  FAIL | {n:36} | {d}")
print(f"  ── TỔNG server: PASS={len(P)} FAIL={len(F)}")
sys.exit(0 if not F else 1)
