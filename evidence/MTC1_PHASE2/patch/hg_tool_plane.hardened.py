#!/usr/bin/env python3
"""HG TOOL PLANE — cấp tool thật cho runtime HG (HG_LOCAL).
Nguyên tắc: token đọc từ FILE (không inline, không log) · fail-closed · audit mọi lần gọi.
Tích hợp (2 dòng) trong hg_runtime.py:
    from toolplane.hg_tool_plane import tool_ask
    ... model, txt = tool_ask(cfg, text, s.get("memory", []))   # thay cho model_ask(...)
"""
import base64, hashlib, json, os, pathlib, sys, time, urllib.request, urllib.error

# ---------- cấu hình: ĐỌC TOKEN TỪ FILE (data-only, KHÔNG exec file) ----------
def _from_env_file(path, key):
    """Đọc KEY=value từ file dạng env NHƯ DỮ LIỆU (không source, không eval)."""
    try:
        t = pathlib.Path(os.path.expanduser(path)).read_text(errors="replace")
    except OSError:
        return ""
    for ln in t.splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"): continue
        if ln.startswith("export "): ln = ln[7:]
        if ln.startswith(key + "="):
            return ln.split("=", 1)[1].strip().strip('"').strip("'")
    return ""

SECRET = "~/.config/hg/secret.env"
def _tok(path, env=None):
    p = pathlib.Path(os.path.expanduser(path))
    if p.exists():
        try: return p.read_text(errors="replace").strip()
        except OSError: pass
    return os.getenv(env, "") if env else ""

AUDIT_ERRORS = []

CFG = {
    "model_base": os.getenv("HG_MODEL_BASE_URL") or _from_env_file(SECRET,"HG_MODEL_BASE_URL") or "https://api.deepseek.com",
    "model_id":   os.getenv("HG_MODEL_ID") or _from_env_file(SECRET,"HG_MODEL_ID") or "deepseek-chat",
    "model_key":  os.getenv("HG_MODEL_API_KEY") or _from_env_file(SECRET,"HG_MODEL_API_KEY"),
    "ops_vps1":   {"url": "https://160.191.242.198/ops",  "tok": _tok("~/.config/hg/ops_vps1_token")},
    "ops_vps2":   {"url": "https://160.191.242.198/ops2", "tok": _tok("~/.config/hg/ops_vps2_token")},
    "go_status":  "https://160.191.242.198/go/status",     # nếu expose; nếu chưa -> tool trả lỗi rõ
    "audit":      os.path.expanduser("~/.config/hg/toolplane_audit.jsonl"),
    "max_iters":  int(os.getenv("HG_TOOL_MAX_ITERS", "6")),
}

def _last_hash(path):
    try:
        lines = pathlib.Path(path).read_text(errors="replace").strip().splitlines()
        return json.loads(lines[-1]).get("h", "GENESIS") if lines else "GENESIS"
    except Exception:
        return "GENESIS"

def _audit(rec):
    """Append-only + hash-chain (tamper-evident)."""
    rec["ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        p = pathlib.Path(CFG["audit"]); p.parent.mkdir(parents=True, exist_ok=True)
        rec["prev"] = _last_hash(p)
        rec["h"] = hashlib.sha256(json.dumps(rec, sort_keys=True).encode()).hexdigest()
        with open(p, "a", encoding="utf-8") as f: f.write(json.dumps(rec, sort_keys=True) + "\n")
    except Exception as ex:
        AUDIT_ERRORS.append({"ts": rec.get("ts"), "event": rec.get("event"), "err": type(ex).__name__})
        print("[tool_plane] AUDIT_WRITE_FAILED %s %s" % (type(ex).__name__, rec.get("event")), file=sys.stderr)

def audit_health():
    """Số lỗi ghi audit đã bị bắt (KHÔNG im lặng)."""
    return {"errors": len(AUDIT_ERRORS), "last": AUDIT_ERRORS[-1] if AUDIT_ERRORS else None}

def verify_audit(path=None):
    """Kiểm tra tính toàn vẹn chuỗi audit (B5)."""
    p = pathlib.Path(path or CFG["audit"]); prev = "GENESIS"; bad = []
    try: lines = p.read_text(errors="replace").strip().splitlines()
    except OSError: return {"ok": True, "records": 0, "note": "no audit file"}
    for i, l in enumerate(lines, 1):
        try:
            r = json.loads(l); h = r.pop("h", None)
            if r.get("prev") != prev: bad.append({"line": i, "reason": "prev mismatch"})
            if hashlib.sha256(json.dumps(r, sort_keys=True).encode()).hexdigest() != h:
                bad.append({"line": i, "reason": "hash mismatch"})
            prev = h
        except Exception as e: bad.append({"line": i, "reason": type(e).__name__})
    return {"ok": not bad, "records": len(lines), "bad": bad[:5]}

# ---------- thực thi tool (allowlist cứng) ----------
def _http(method, url, tok=None, body=None, timeout=40, extra=None):
    h = {"Content-Type": "application/json"}
    if tok: h["Authorization"] = "Bearer " + tok
    if extra: h.update(extra)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return 0, f"NETWORK_ERROR {type(e).__name__}: {e}"

def tool_vps_exec(host: str, cmd: str):
    """Chạy lệnh trên VPS1/VPS2 qua ops-agent (đã deploy, có audit + kill-switch)."""
    ep = CFG["ops_vps1"] if host == "vps1" else CFG["ops_vps2"] if host == "vps2" else None
    if not ep: return {"ok": False, "error": "host phải là vps1|vps2"}
    if not ep["tok"]: return {"ok": False, "error": f"thiếu token {host} (đặt file ~/.config/hg/ops_{host}_token)"}
    st, txt = _http("POST", ep["url"] + "/exec", ep["tok"], {"cmd": cmd, "timeout": 120}, 180)
    try: j = json.loads(txt)
    except Exception: j = {"raw": txt[:400]}
    return {"ok": st == 200, "http": st, **j}

def tool_go_health(_=None):
    """B1: probe GO trên VPS1 qua kênh đã uỷ quyền (ops-agent) — KHÔNG thêm route nginx.
    Trả 2 mức: liveness (/healthz) và authenticated status (/v1/status, token đọc tại chỗ trên VPS1)."""
    if not CFG["ops_vps1"]["tok"]:
        return {"ok": False, "error": "thiếu token ops VPS1 (~/.config/hg/ops_vps1_token)"}
    cmd = ("echo LIVE:; curl -s -m 5 http://127.0.0.1:8877/healthz; echo; echo AUTH:; "
           "T=$(grep -m1 '^GO_API_TOKEN=' /etc/go/go-runtime.env 2>/dev/null | cut -d= -f2- | tr -d '\"'); "
           "curl -s -m 5 -o /dev/null -w '%{http_code}' ${T:+-H \"Authorization: Bearer $T\"} "
           "http://127.0.0.1:8877/v1/status")
    r = tool_vps_exec("vps1", cmd)
    out = (r.get("stdout") or "")
    live_ok = '"status": "ok"' in out or '"status":"ok"' in out
    auth_code = ""
    if "AUTH:" in out:
        tail = out.split("AUTH:", 1)[1].strip().split("\n")[-1]
        auth_code = tail.strip()
    return {"ok": bool(live_ok) and r.get("ok"), "liveness": live_ok,
            "authenticated_status_http": auth_code, "channel": "vps_exec->127.0.0.1:8877",
            "raw": out[:300]}

def tool_phone_health(_=None):
    """Đọc health runtime HG local (read-only)."""
    st, txt = _http("GET", "http://127.0.0.1:8787/api/health", None, None, 10)
    return {"ok": st == 200, "http": st, "body": txt[:300]}

# ---------- GITHUB ----------
GH_TOKEN = (os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
            or _tok("~/.config/hg/github_pat")            # PAT có quyền GHI (ưu tiên)
            or _tok("/sdcard/DeepSeekHarness/github_pat")) # canonical: KHÔNG fallback legacy
GH_ALLOW = ("/user", "/rate_limit",
            "/repos/OAI-GIANG/GO", "/repos/OAI-GIANG/hg-ops")
GH_HDR = {"Accept": "application/vnd.github+json", "User-Agent": "hg-toolplane"}

def tool_github_whoami(_=None):
    """Cho biết token GitHub đang là tài khoản nào + có scope gì (để biết đọc/ghi được không)."""
    if not GH_TOKEN: return {"ok": False, "error": "thiếu token GitHub canonical (~/.config/hg/github_pat hoặc /sdcard/DeepSeekHarness/github_pat)"}
    st, txt = _http("GET", "https://api.github.com/user", GH_TOKEN, None, 20, GH_HDR)
    import json as _j
    try: login = _j.loads(txt).get("login")
    except Exception: login = None
    return {"ok": st == 200, "http": st, "login": login}

def tool_github_api(a):
    """Gọi GitHub REST API. Allowlist repo cố định; ghi được nếu token có quyền."""
    method = str(a.get("method") or "GET").upper()
    path = str(a.get("path") or "")
    if method not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
        return {"ok": False, "error": "method không hợp lệ"}
    if not any(path == p or path.startswith(p + "/") or path.startswith(p + "?") for p in GH_ALLOW):
        return {"ok": False, "error": "path ngoài allowlist", "allow": list(GH_ALLOW)}
    if not GH_TOKEN: return {"ok": False, "error": "thiếu token GitHub"}
    st, txt = _http(method, "https://api.github.com" + path, GH_TOKEN, a.get("body"), 60, GH_HDR)
    return {"ok": 200 <= st < 300, "http": st, "body": txt[:4000]}

def tool_audit_tail(a=None):
    """READ-ONLY: đọc N dòng cuối audit của tool plane + verify hash-chain (để kiểm toán từ xa)."""
    n = int((a or {}).get("lines") or 20)
    p = pathlib.Path(CFG["audit"]); recs = []
    try:
        for l in p.read_text(errors="replace").strip().splitlines()[-n:]:
            try:
                r = json.loads(l); r.pop("h", None); recs.append(r)
            except Exception: pass
    except OSError: pass
    return {"ok": True, "audit_path": CFG["audit"], "records": len(recs),
            "events": recs, "integrity": verify_audit(), "audit_health": audit_health()}

TOOLS = {
    "vps_exec":      {"fn": lambda a: tool_vps_exec(a.get("host", ""), a.get("cmd", "")),
                      "schema": {"type": "function", "function": {"name": "vps_exec",
                        "description": "Chạy lệnh shell trên VPS1 hoặc VPS2 (đã xác thực, có audit).",
                        "parameters": {"type": "object", "properties": {
                          "host": {"type": "string", "enum": ["vps1", "vps2"]},
                          "cmd":  {"type": "string"},
                          "approved": {"type": "boolean", "description": "true khi Chủ nhân đã cho phép lệnh nguy hiểm"}}, "required": ["host", "cmd"]}}}},
    "go_health":     {"fn": tool_go_health, "schema": {"type": "function", "function": {"name": "go_health",
                        "description": "Trạng thái GO canonical runtime (read-only).", "parameters": {"type": "object", "properties": {}}}}},
    "github_whoami": {"fn": tool_github_whoami, "schema": {"type": "function", "function": {"name": "github_whoami",
                        "description": "Cho biết token GitHub đang là tài khoản nào (kiểm tra quyền đọc/ghi).", "parameters": {"type": "object", "properties": {}}}}},
    "github_api":    {"fn": tool_github_api, "schema": {"type": "function", "function": {"name": "github_api",
                        "description": "Gọi GitHub REST API (allowlist: OAI-GIANG/GO, OAI-GIANG/hg-ops, /user). Thao tác DELETE cần approved=true.",
                        "parameters": {"type": "object", "properties": {
                          "method": {"type": "string", "enum": ["GET","POST","PUT","PATCH","DELETE"]},
                          "path":   {"type": "string", "description": "vd /repos/OAI-GIANG/GO/git/ref/heads/hg-core"},
                          "body":   {"type": "object", "description": "JSON body cho POST/PUT/PATCH"},
                          "approved": {"type": "boolean", "description": "true khi Chủ nhân đã cho phép DELETE"}},
                          "required": ["method","path"]}}}},
    "audit_tail":    {"fn": tool_audit_tail, "schema": {"type": "function", "function": {"name": "audit_tail",
                        "description": "READ-ONLY: đọc audit gần nhất của tool plane + kiểm tra tính toàn vẹn hash-chain.",
                        "parameters": {"type": "object", "properties": {"lines": {"type": "integer"}}}}}},
    "phone_health":  {"fn": tool_phone_health, "schema": {"type": "function", "function": {"name": "phone_health",
                        "description": "Trạng thái runtime HG trên điện thoại (read-only).", "parameters": {"type": "object", "properties": {}}}}},
}
# ---------- GOVERNANCE (P3/B5): deny-list + approval cho thao tác nguy hiểm ----------
DESTRUCTIVE = ("rm -rf", "rm -fr", "mkfs", "dd if=", "dd of=/dev", "shutdown", "reboot", "poweroff",
               "halt", "iptables -f", "iptables -x", "nft flush", "systemctl disable", "systemctl mask",
               "passwd ", "userdel", "groupdel", "chmod -r 777", "truncate -s 0", ":(){", "> /dev/sd")

def governance_check(tool, args):
    """Trả lý do TỪ CHỐI, hoặc None nếu được phép. Fail-closed."""
    if tool == "vps_exec":
        cmd = str(args.get("cmd", "")).lower()
        for pat in DESTRUCTIVE:
            if pat in cmd: return f"lệnh khớp mẫu nguy hiểm {pat!r}"
    if tool == "github_api":
        if str(args.get("method", "GET")).upper() == "DELETE":
            return "DELETE cần approved=true"
    return None

# ---------- B5-b: CẦU TỚI CANONICAL GOVERNANCE THẬT (GO trên VPS1) ----------
CANON_MAP = {"go_health": "vps1.edge.health"}      # tool ↔ adapter canonical tương đương
READ_ONLY = {"go_health", "phone_health", "github_whoami", "audit_tail"}

CANON_SRC = """import sys, os, json
sys.path.insert(0, "/opt/go")
from runtime.go_runtime.core.tool_governance import ToolGovernance, ToolGovernanceError
from runtime.go_runtime.core.tool_runtime import ToolRegistry, VPS1HealthTool
tool, call_id, args = sys.argv[1], sys.argv[2], json.loads(sys.argv[3] or "{}")
m = {"vps1.edge.health": VPS1HealthTool}
cls = m.get(tool)
if not cls:
    print(json.dumps({"mapped": False, "ok": None})); raise SystemExit(0)
reg = ToolRegistry(); reg.register(cls()); gov = ToolGovernance(reg)
try:
    r = gov.execute("HG-TOOLPLANE", tool, args, call_id=call_id)
    print(json.dumps({"mapped": True, "ok": bool(r.ok), "witness": r.witness, "output": str(r.output)[:200]}))
except ToolGovernanceError as e:
    print(json.dumps({"mapped": True, "ok": False, "denied": e.code}))
except Exception as e:
    print(json.dumps({"mapped": True, "ok": False, "error": type(e).__name__ + ": " + str(e)[:120]}))
"""

def canonical_decision(tool, args, call_id):
    """Gọi canonical ToolGovernance.execute() THẬT trên VPS1. Trả dict có: available, mapped, ok."""
    cname = CANON_MAP.get(tool)
    if not cname:
        return {"available": True, "mapped": False, "ok": None}
    if not CFG["ops_vps1"]["tok"]:
        return {"available": False, "mapped": True, "ok": None, "error": "no ops token"}
    b64 = base64.b64encode(CANON_SRC.encode()).decode()
    cmd = ("echo %s | base64 -d > /tmp/hg_cangov.py && cd /opt/go && PYTHONPATH=/opt/go "
           "python3 /tmp/hg_cangov.py %s %s '%s'") % (b64, cname, call_id, json.dumps(args))
    r = tool_vps_exec("vps1", cmd)
    try:
        last = [x for x in (r.get("stdout") or "").strip().splitlines() if x.strip()][-1]
        return {"available": True, **json.loads(last)}
    except Exception:
        return {"available": False, "mapped": True, "ok": None, "error": (r.get("stderr") or "rpc/parse fail")[:120]}

def is_read_only(tool, args):
    """A tool is read-only if it is declared read-only, or it is github_api with GET."""
    if tool in READ_ONLY:
        return True
    if tool == "github_api" and str((args or {}).get("method", "GET")).upper() == "GET":
        return True
    return False

def governance_decide(tool, args, call_id):
    """Fail-closed decision (MTC-1.0 B5-a).

    - Read-only tools may run even when canonical governance is unavailable
      (they cannot produce a side effect).
    - EVERY tool with a possible side effect (not read-only) MUST be:
        * canonically MAPPED  (else DENY: UNMAPPED_FAIL_CLOSED), AND
        * canonical AVAILABLE (else DENY), AND
        * canonically ALLOWING (else DENY).
    This closes the gap where an unmapped side-effect tool (vps_exec, github_api
    writes) was previously allowed while only a local deny-list applied.
    """
    ro = is_read_only(tool, args)
    dec = canonical_decision(tool, args, call_id)
    if not (isinstance(dec, dict) and "mapped" in dec and "available" in dec):
        dec = {"available": False, "mapped": True, "ok": None, "error": "INVALID_CANONICAL_RESPONSE"}
    if ro:
        return True, "read-only", dec
    if not dec.get("mapped"):
        return (False,
                "CANONICAL_GOVERNANCE_UNMAPPED_FAIL_CLOSED: " + str(tool) +
                " has side effects but no canonical adapter mapping", dec)
    if not dec.get("available"):
        return False, "CANONICAL_GOVERNANCE_UNAVAILABLE (fail-closed)", dec
    if dec.get("ok") is False:
        return False, "CANONICAL_GOVERNANCE_DENY: " + str(
            dec.get("denied") or dec.get("error") or dec.get("witness")), dec
    return True, "ok", dec

TOOL_SCHEMAS = [t["schema"] for t in TOOLS.values()]

# ---------- model call + tool loop ----------
def _model(messages, tools=None):
    if not CFG["model_key"]: return None, "THIẾU HG_MODEL_API_KEY"
    body = {"model": CFG["model_id"], "messages": messages, "temperature": 0.2}
    if tools: body["tools"] = tools
    st, txt = _http("POST", CFG["model_base"].rstrip("/") + "/chat/completions", CFG["model_key"], body, 90)
    if st != 200: return None, f"model HTTP {st}: {txt[:200]}"
    try: return json.loads(txt)["choices"][0]["message"], None
    except Exception as e: return None, f"parse: {e}"

def tool_ask(cfg, text, memories=None, *args, **kwargs):
    """Chấp nhận thêm tham số (context/attachments...) để vá được mọi call-site."""
    max_iters = kwargs.get('max_iters') or (args[0] if args and isinstance(args[0], int) else None)
    """Trả (model, text) như model_ask cũ, nhưng có tool loop. Fail-closed: lỗi tool -> trả lỗi rõ, không bịa."""
    C = {**CFG, **(cfg or {})}
    sys = "Bạn là HG. Dùng tool khi cần dữ liệu thật; không bịa. Luôn nêu rõ nguồn (tool nào, khi nào)."
    msgs = [{"role": "system", "content": sys}]
    if memories: msgs.append({"role": "system", "content": "Bộ nhớ liên quan:\n" + json.dumps(memories)[:4000]})
    msgs.append({"role": "user", "content": text})
    iters = max_iters or C.get("max_iters", 6)
    seen = []
    for i in range(iters):
        m, err = _model(msgs, TOOL_SCHEMAS)
        if err: return C.get("model_id", "?"), f"[tool_plane] {err}"
        calls = m.get("tool_calls") or []
        if not calls:
            return C.get("model_id", "?"), m.get("content", "")
        sig = [(c["function"]["name"], c["function"].get("arguments")) for c in calls]
        if seen and seen[-1] == sig:
            _audit({"event": "LOOP_BREAK", "iter": i, "tools": [x[0] for x in sig]})
            break
        seen.append(sig)
        msgs.append(m)
        for c in calls:
            name = c["function"]["name"]; 
            try: args = json.loads(c["function"].get("arguments") or "{}")
            except Exception: args = {}
            fn = TOOLS.get(name)
            deny = governance_check(name, args)   # LUÔN kiểm; approved KHÔNG bỏ qua
            if deny:
                out = {"ok": False, "error": "GOVERNANCE_DENY: " + deny,
                       "approved_flag": bool(args.get("approved")),
                       "remedy": "mẫu nguy hiểm bị chặn tuyệt đối; cần đường governed của canonical"}
                _audit({"event": "GOVERNANCE_DENY", "tool": name, "why": deny,
                        "approved_flag": bool(args.get("approved"))})
            elif not fn: out = {"ok": False, "error": f"tool không tồn tại: {name}"}
            else:
                allow, why, dec = governance_decide(name, args, f"CALL-{int(time.time())}-{i}")
                _audit({"event": "CANONICAL_DECISION", "tool": name, "allow": allow,
                        "mapped": dec.get("mapped"), "available": dec.get("available"),
                        "canonical_ok": dec.get("ok"), "why": why[:80]})
                if not allow:
                    out = {"ok": False, "error": "GOVERNANCE_BLOCK: " + why, "canonical": dec}
                else:
                    try: out = fn["fn"](args)
                    except Exception as e: out = {"ok": False, "error": f"{type(e).__name__}: {e}"}
            _audit({"tool": name, "args_keys": sorted(args.keys()), "ok": out.get("ok"), "http": out.get("http")})
            msgs.append({"role": "tool", "tool_call_id": c.get("id"), "content": json.dumps(out)[:6000]})
    # HẾT NGÂN SÁCH VÒNG -> buộc model tóm tắt (gọi KHÔNG kèm tools)
    _audit({"event": "FORCE_SUMMARY", "iters_used": len(seen)})
    note = {"role": "system", "content": ("Đã hết ngân sách gọi tool. Hãy TÓM TẮT kết quả đã thu được: "
            "nêu rõ tool nào đã dùng, dữ liệu nhận được, và còn thiếu gì. Không gọi thêm tool.")}
    m2, err2 = _model(msgs + [note], None)
    if m2 and m2.get("content"):
        return C.get("model_id", "?"), m2["content"]
    return C.get("model_id", "?"), f"[tool_plane] hết {len(seen)} vòng mà không tóm tắt được ({err2 or 'no content'})"

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        print(json.dumps({"tools": list(TOOLS), "model_key_present": bool(CFG["model_key"]),
                          "ops_vps1_tok": bool(CFG["ops_vps1"]["tok"]), "ops_vps2_tok": bool(CFG["ops_vps2"]["tok"])}, indent=1))
    elif len(sys.argv) > 1 and sys.argv[1] == "exec":
        print(json.dumps(tool_vps_exec(sys.argv[2], sys.argv[3]), indent=1)[:800])