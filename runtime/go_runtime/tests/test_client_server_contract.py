"""Contract test for the real Android long-poll client and GO HTTP router."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
AGENT = ROOT / "phone_agent"
P, F = [], []


def rec(name, condition, detail=""):
    (P if condition else F).append((name, detail))


doc = (AGENT / "PROTOCOL_V2_LONGPOLL.md").read_text(encoding="utf-8")
java = (AGENT / "android/app/src/main/java/com/hg/phoneagent/LongPollClient.java").read_text(encoding="utf-8")
main = (AGENT / "android/app/src/main/java/com/hg/phoneagent/MainActivity.java").read_text(encoding="utf-8")
server = (ROOT / "runtime/go_runtime/core/server.py").read_text(encoding="utf-8")
router = (ROOT / "runtime/go_runtime/core/phone_agent_http.py").read_text(encoding="utf-8")
protocol = (ROOT / "runtime/go_runtime/core/phone_agent_server_v2.py").read_text(encoding="utf-8")

for route in ["/api/phone/register", "/api/phone/poll", "/api/phone/result"]:
    rec(f"doc_has_route[{route}]", route in doc)
    rec(f"server_mounts[{route}]", route in server or route in router)
    rec(f"client_uses[{route}]", route in java or route in main)
for field in ["request_id", "capability", "params", "wait_s", "idle", "result"]:
    rec(f"field_shared[{field}]", f'"{field}"' in java and field in doc)
rec("field_shared[device_token]", '"device_token"' in main and "device_token" in doc and "device_token" in protocol)
rec("router_internal_key_required", "X-Internal-Key" in router and "INTERNAL_FORBIDDEN" in router)
rec("statuses_documented", all(code in doc for code in ["403", "401", "400", "409"]))
rec("client_https_only", 'startsWith("https://")' in java)
rec("client_backoff_cap_30s", "Math.min(backoff * 2, 30000L)" in java)
rec("client_uses_request_id_for_dispatch", "exec.execute(rid, cap, params)" in java)
rec("main_wired_longpoll", "startLongPoll" in main and "LongPollClient" in main)
rec("main_lifecycle_cancel", "onDestroy" in main and "poller.stop()" in main)
rec("main_dispatch_allowlisted", "TermuxDispatch.dispatch" in main)
rec("server_hook_in_do_POST", 'def do_POST(self)->None:' in server and "/api/phone/" in server and "_phone_agent()" in server)
rec("server_secrets_from_env", "HG_PHONE_PAIRING_TOKENS" in server and "HG_PHONE_INTERNAL_KEY" in server)
rec("server_body_limit", "BODY_TOO_LARGE" in server and "2 * 1024 * 1024" in server)
rec("phone_router_defined_before_main", server.rfind('if __name__ == "__main__":') > server.find("def _phone_agent():"))

for name, detail in P:
    print(f"  PASS | {name:42} | {detail}")
for name, detail in F:
    print(f"  FAIL | {name:42} | {detail}")
print(f"  -- contract total: PASS={len(P)} FAIL={len(F)}")
sys.exit(0 if not F else 1)
