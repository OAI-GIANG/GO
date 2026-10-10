"""GO governed-tool adapter -> internal queue -> phone long-poll protocol -> sandbox fileops result."""
import base64
import hashlib
import json
import os
import pathlib
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from runtime.go_runtime.core import server as go_server
from runtime.go_runtime.core.phone_fileops import PhoneFileOps
from runtime.go_runtime.core.tool_runtime import default_tool_registry
from runtime.go_runtime.core.tool_governance import ToolGovernance

os.environ["HG_PHONE_PAIRING_TOKENS"] = "TOOL-TEST-PAIR"
os.environ["HG_PHONE_INTERNAL_KEY"] = "TOOL-TEST-INTERNAL"
os.environ["HG_TOOL_AUTHORITY_PROVENANCE"] = "PHONE-TOOL-TEST-PROVENANCE"
os.environ["HG_TOOL_AUTHORITY_PROVENANCE_EXPECTED"] = "PHONE-TOOL-TEST-PROVENANCE"
os.environ["HG_TOOL_AUTHORITY_SUBJECT"] = "HG_SESSION_PHONE_TOOL_TEST"
go_server._PHONE_AGENT = None

httpd = ThreadingHTTPServer(("127.0.0.1", 0), go_server.Handler)
httpd.app = None
threading.Thread(target=httpd.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{httpd.server_address[1]}"
os.environ["HG_PHONE_AGENT_INTERNAL_URL"] = base
passed, failed = [], []


def call(path, body=None, token=None):
    req = urllib.request.Request(base + path, data=json.dumps(body or {}).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def check(name, ok):
    (passed if ok else failed).append(name)


try:
    status, registration = call("/api/phone/register", {
        "pairing_token": "TOOL-TEST-PAIR", "device_id": "tool-device", "name": "test worker"
    })
    token = registration.get("device_token", "")
    check("test_device_registered", status == 200 and bool(token))

    with tempfile.TemporaryDirectory(prefix="hg-phone-tool-test-") as tmp:
        ops = PhoneFileOps(sandbox=pathlib.Path(tmp) / "sandbox")
        stop = threading.Event()

        def simulated_phone_agent():
            while not stop.is_set():
                status, command = call("/api/phone/poll", {"wait_s": 0.1}, token=token)
                rid = command.get("request_id")
                if status == 200 and rid:
                    request = {"request_id": rid, "capability": command["capability"], **command.get("params", {})}
                    result = ops.handle(request)
                    call("/api/phone/result", {
                        "request_id": rid, "ok": bool(result.get("ok")),
                        "result": result.get("result") if result.get("ok") else result.get("error"),
                    }, token=token)
                else:
                    time.sleep(0.03)

        worker = threading.Thread(target=simulated_phone_agent, daemon=True)
        worker.start()
        registry = default_tool_registry()
        governance = ToolGovernance(registry, pathlib.Path(tmp) / "tool-events.jsonl")
        content = b"HG_TOOL_PLANE_WRITE_OK\n"
        args = {"device_id": "tool-device", "path": "tool-plane.txt",
                "content_b64": base64.b64encode(content).decode()}

        denied = governance.execute("PHONE-TOOL-DENIED", "phone.agent.write_file", args, approval="not_required")
        check("governance_denies_unapproved_write", not denied.ok and denied.output.get("error") == "APPROVAL_REQUIRED")
        gh_denied = governance.execute("PHONE-GH-WRITE-DENIED", "github.write_file", {
            "repository": "OAI-GIANG/GO", "branch": "feature/phone-agent-v2-fileops",
            "path": "test-only.txt", "content": "must not be written",
        }, approval="not_required")
        check("governance_denies_unapproved_github_write",
              not gh_denied.ok and gh_denied.output.get("error") == "APPROVAL_REQUIRED")
        mutating_github = ["github.create_branch", "github.delete_branch", "github.write_file",
                           "github.update_branch", "github.create_pr", "github.update_pr",
                           "github.comment_issue", "github.create_issue", "github.update_issue",
                           "github.dispatch_workflow", "github.rerun_workflow"]
        check("all_github_mutations_require_approval", all(
            registry._tools[name].spec().destructive for name in mutating_github))

        write = governance.execute("PHONE-TOOL-APPROVED", "phone.agent.write_file", args, approval="approved")
        check("go_tool_write_completed", write.ok and write.output.get("state") == "DONE" and write.output["result"]["verified"])
        check("go_tool_write_hash", write.output["result"]["sha256_after"] == "sha256:" + hashlib.sha256(content).hexdigest())
        check("sandbox_contains_write", (pathlib.Path(tmp) / "sandbox" / "tool-plane.txt").read_bytes() == content)

        read = governance.execute("PHONE-TOOL-READ", "phone.agent.read_file",
                                  {"device_id": "tool-device", "path": "tool-plane.txt"})
        check("go_tool_read_completed", read.ok and read.output.get("state") == "DONE")
        check("go_tool_readback_text", read.output["result"].get("content") == content.decode())
        listing = governance.execute("PHONE-TOOL-LIST", "phone.agent.list_files", {"path": "."})
        check("go_tool_lists_workspace_files", listing.ok and any(
            item.get("path") == "tool-plane.txt" for item in listing.output.get("result", {}).get("entries", [])))

        write_spec = registry._tools["phone.agent.write_file"].spec()
        read_spec = registry._tools["phone.agent.read_file"].spec()
        list_spec = registry._tools["phone.agent.list_files"].spec()
        check("write_requires_governed_approval", write_spec.destructive is True)
        check("read_is_nonmutating", read_spec.read_only is True)
        check("list_is_nonmutating", list_spec.read_only is True)

        stop.set()
        worker.join(timeout=2)
finally:
    httpd.shutdown()
    httpd.server_close()

for name in passed:
    print("PASS | " + name)
for name in failed:
    print("FAIL | " + name)
print(f"PHONE_TOOL_PLANE PASS={len(passed)} FAIL={len(failed)}")
raise SystemExit(0 if not failed else 1)
