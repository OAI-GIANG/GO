"""Contract test (static + doc): field JSON/route/status giữa client Java ↔ server router ↔ PROTOCOL doc."""
import pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[3]          # .../phagent
P, F = [], []
def rec(n, c, d=""): (P if c else F).append((n, d))
doc = (ROOT / "PROTOCOL_V2_LONGPOLL.md").read_text()
java = (ROOT / "jout/LongPollClient.java").read_text()
main = (ROOT / "jout/MainActivity.java").read_text()
srv = (ROOT / "server_v2.py").read_text()
router = (ROOT / "runtime/go_runtime/core/phone_agent_http.py").read_text()
for f in ["/api/phone/register", "/api/phone/poll", "/api/phone/result"]:
    rec(f"doc_has_route{f}", f in doc)
    rec(f"server_mounts{f}", f in srv or f in router)
    rec(f"client_uses{f}", f in java)
for fld in ["request_id", "capability", "params", "wait_s", "idle", "result"]:
    rec(f"field_shared[{fld}]", f'"{fld}"' in java and fld in doc)
# device_token: client dùng ở bước ĐĂNG KÝ (MainActivity), server trả về, doc mô tả
rec("field_shared[device_token]", '"device_token"' in main and "device_token" in doc and "device_token" in (ROOT/"runtime/go_runtime/core/phone_agent_server_v2.py").read_text())
rec("router_internal_key_required", "X-Internal-Key" in router and "INTERNAL_FORBIDDEN" in router)
rec("statuses_documented", all(s in doc for s in ["403", "401", "400", "409"]))
rec("client_https_only", 'startsWith("https://")' in java)
rec("client_backoff_cap_30s", "Math.min(backoff * 2, 30000L)" in java)
rec("client_no_ws", "WebSocket" not in java and "SSLSocket" not in java)
rec("main_wired_longpoll", "startLongPoll" in main and "LongPollClient" in main)
rec("main_ws_removed", "startWs" not in main and "SSLSocket" not in main)
rec("main_lifecycle_cancel", "onDestroy" in main and "poller.stop()" in main)
rec("main_dispatch_allowlisted", "TermuxDispatch.dispatch" in main)
rec("server_hook_in_do_POST", 'def do_POST(self)->None:' in srv and "/api/phone/" in srv and "_phone_agent()" in srv)
rec("server_secrets_from_env", 'HG_PHONE_PAIRING_TOKENS' in srv and 'HG_PHONE_INTERNAL_KEY' in srv)
for n, d in P: print(f"  PASS | {n:38} | {d}")
for n, d in F: print(f"  FAIL | {n:38} | {d}")
print(f"  ── TỔNG contract: PASS={len(P)} FAIL={len(F)}")
sys.exit(0 if not F else 1)
