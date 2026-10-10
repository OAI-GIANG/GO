import json, os, pathlib, subprocess, sys, tempfile
P, F = [], []
def rec(n, c, d=""): (P if c else F).append((n, d))
CORE = str(pathlib.Path(__file__).resolve().parents[1] / "runtime" / "go_runtime" / "core")
sb = tempfile.mkdtemp()
def run(req, sandbox=sb):
    cp = subprocess.run(["python3", "-c",
        f"import sys,json;sys.path.insert(0,{CORE!r});from phone_fileops import PhoneFileOps;"
        f"print(json.dumps(PhoneFileOps(sandbox=__import__('pathlib').Path({sandbox!r})).handle(json.loads(sys.argv[1]))))",
        json.dumps(req)], capture_output=True, text=True, timeout=60)
    return cp.returncode, (json.loads(cp.stdout) if cp.stdout.strip() else None), cp.stderr[:200]
# 1) HAI TIẾN TRÌNH ĐỘC LẬP, cùng request_id → cái thứ 2 bị từ chối
r1 = run({"request_id": "XP-1", "capability": "WRITE_FILE", "path": "a.txt", "content_b64": "aGk="})
r2 = run({"request_id": "XP-1", "capability": "WRITE_FILE", "path": "a.txt", "content_b64": "aGk="})
rec("cross_process_replay_rejected", r1[1]["ok"] and r2[1]["error"]["code"] == "REPLAY_REJECTED", f"p1={r1[1]['ok']} p2={r2[1].get('error')}")
# 2) replay Ở TIẾN TRÌNH THỨ 3 sau "restart" → vẫn bị chặn
r3 = run({"request_id": "XP-1", "capability": "READ_FILE", "path": "a.txt"})
rec("replay_after_restart_rejected", r3[1]["error"]["code"] == "REPLAY_REJECTED")
# 3) ĐỒNG THỜI: 5 tiến trình cùng id → đúng 1 thành công
import concurrent.futures as cf
sb2 = tempfile.mkdtemp()
with cf.ThreadPoolExecutor(max_workers=5) as ex:
    outs = list(ex.map(lambda i: run({"request_id": "CONC-1", "capability": "WRITE_FILE", "path": f"c{i}.txt", "content_b64": "eA=="}, sb2), range(5)))
okc = sum(1 for o in outs if o[1] and o[1].get("ok"))
rejc = sum(1 for o in outs if o[1] and o[1].get("error", {}).get("code") == "REPLAY_REJECTED")
rec("concurrent_same_id_exactly_one", okc == 1 and rejc == 4, f"ok={okc} rejected={rejc}")
# 4) TAMPER log → fail-closed
log = pathlib.Path(sb2) / ".hg_replay.jsonl"
lines = log.read_text().splitlines(); d = json.loads(lines[0]); d["capability"] = "TAMPERED"
lines[0] = json.dumps(d, sort_keys=True, separators=(",", ":")); log.write_text("\n".join(lines) + "\n")
rt = run({"request_id": "TAMPER-1", "capability": "WRITE_FILE", "path": "t.txt", "content_b64": "eA=="}, sb2)
rec("tamper_fail_closed", rt[1] and rt[1].get("error", {}).get("code") == "REPLAY_LOG_CORRUPT", str(rt[1].get("error") if rt[1] else rt[2]))
# 5) DONE vs FAILED đều chặn replay; id mới vẫn chạy
ran = run({"request_id": "NEW-1", "capability": "READ_FILE", "path": "a.txt"}, sb)
rec("new_id_still_works", ran[1] and ran[1].get("ok") is True)
v = run({"request_id": "MISSINGFILE-1", "capability": "READ_FILE", "path": "nope.txt"}, sb)
v2 = run({"request_id": "MISSINGFILE-1", "capability": "READ_FILE", "path": "nope.txt"}, sb)
rec("failed_then_replay_rejected", v[1]["error"]["code"] == "NOT_FOUND" and v2[1]["error"]["code"] == "REPLAY_REJECTED", f"{v[1]['error']['code']}→{v2[1]['error']['code']}")
for n, d in P: print(f"  PASS | {n:34} | {d}")
for n, d in F: print(f"  FAIL | {n:34} | {d}")
print(f"  ── TỔNG replay: PASS={len(P)} FAIL={len(F)}")
sys.exit(0 if not F else 1)
