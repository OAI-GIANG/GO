import base64, hashlib, os, pathlib, sys, tempfile
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "core"))
from phone_fileops import PhoneFileOps, FileOpError, CAPABILITIES, sha256_of   # noqa
P, F = [], []
def rec(n, c, d=""): (P if c else F).append((n, d))
sb = pathlib.Path(tempfile.mkdtemp())
ops = PhoneFileOps(sandbox=sb / "sandbox")
b = lambda s: base64.b64encode(s if isinstance(s, bytes) else s.encode()).decode()

# 1) WRITE → READ roundtrip + sha khớp
w = ops.write_file("a/note.txt", b("HELLO-1"))
r = ops.read_file("a/note.txt")
rec("write_read_roundtrip", r["content_b64"] == b("HELLO-1") and r["sha256"] == w["sha256_after"])
# 2) hash nội dung sai → chặn; ghi đè phải có precondition hash hiện tại
try: ops.write_file("a/x.txt", b("Z"), expect_sha256="sha256:deadbeef"); rec("expect_sha256_mismatch_blocked", False)
except FileOpError as e: rec("expect_sha256_mismatch_blocked", e.code == "SHA256_MISMATCH")
try: ops.write_file("a/note.txt", b("HELLO-2")); rec("overwrite_without_precondition_blocked", False)
except FileOpError as e: rec("overwrite_without_precondition_blocked", e.code == "PRECONDITION_REQUIRED")
w2 = ops.write_file("a/note.txt", b("HELLO-2"), expected_current_sha256=r["sha256"])
rec("overwrite_with_current_hash", w2["verified"] and w2["sha256_before"] == r["sha256"])
try: ops.write_file("a/note.txt", b("HELLO-3"), expected_current_sha256="sha256:stale"); rec("stale_hash_blocked", False)
except FileOpError as e: rec("stale_hash_blocked", e.code == "CURRENT_SHA256_MISMATCH")
# 3) traversal bị chặn
for bad in ["../escape.txt", "../../../../etc/hosts.txt", "/etc/hosts.txt", "..\\win.txt"]:
    try: ops.write_file(bad, b("X")); rec(f"traversal_blocked[{bad[:14]}]", False)
    except FileOpError as e: rec(f"traversal_blocked[{bad[:14]}]", e.code in ("PATH_OUTSIDE_SANDBOX", "INVALID_PATH"))
# 4) symlink escape bị chặn
outside = sb / "outside"; outside.mkdir(exist_ok=True); (outside / "t.txt").write_text("SECRET")
link = sb / "sandbox" / "link.txt"
try:
    link.symlink_to(outside / "t.txt")
    try: ops.read_file("link.txt"); rec("symlink_escape_blocked", False)
    except FileOpError as e: rec("symlink_escape_blocked", e.code == "PATH_OUTSIDE_SANDBOX")
except OSError: rec("symlink_escape_blocked", True, "nền tảng không tạo được symlink")
# 5) extension ngoài allowlist
try: ops.write_file("evil.exe", b("MZ")); rec("ext_allowlist_blocked", False)
except FileOpError as e: rec("ext_allowlist_blocked", e.code == "EXTENSION_NOT_ALLOWED")
# 6) APPLY_PATCH + GET_DIFF
ops.write_file("p.txt", b("line1\nline2\nline3\n"))
ap = ops.apply_patch("p.txt", "-line2\n+LINE2-changed\n", expected_current_sha256=ops.read_file("p.txt")["sha256"])
rec("apply_patch_ok", ap["hunks"] == 1 and ops.read_file("p.txt")["content_b64"] == b("line1\nLINE2-changed\nline3\n"))
gd = ops.get_diff("p.txt", b("line1\nline2\nline3\n"))
rec("get_diff_detects", gd["changed"] is True)
listing = ops.list_files(".")
rec("list_files_finds_code_files", any(x["path"] == "p.txt" for x in listing["entries"]))
ops.write_file("src/Example.java", b("class Example {}\n"))
rec("java_extension_allowed", ops.read_file("src/Example.java")["verified"] if "verified" in ops.read_file("src/Example.java") else ops.read_file("src/Example.java")["bytes"] > 0)
rec("list_files_finds_java", any(x["path"] == "src/Example.java" for x in ops.list_files("src")["entries"]))
try: ops.read_file("secrets.json"); rec("sensitive_path_denied", False)
except FileOpError as e: rec("sensitive_path_denied", e.code == "SENSITIVE_PATH_DENIED")
try: ops.list_files("../"); rec("list_traversal_denied", False)
except FileOpError as e: rec("list_traversal_denied", e.code == "PATH_OUTSIDE_SANDBOX")
gdnew = ops.get_diff("new-file.py", b("print('new')\n"))
rec("get_diff_new_file", gdnew["changed"] and "+print('new')" in gdnew["diff"])
ops.write_file("dup.txt", b("same\nsame\n"))
try:
    ops.apply_patch("dup.txt", "-same\n+changed\n", expected_current_sha256=ops.read_file("dup.txt")["sha256"])
    rec("ambiguous_patch_blocked", False)
except FileOpError as e: rec("ambiguous_patch_blocked", e.code == "PATCH_CONTEXT_AMBIGUOUS")
# 7) RUN_TEST allowlist (không arbitrary shell)
rt = ops.run_test("smoke")
rec("run_test_allowlisted", rt["exit"] == 0 and "SMOKE_OK" in rt["stdout"])
try: ops.run_test("rm -rf /"); rec("run_test_no_arbitrary_shell", False)
except FileOpError as e: rec("run_test_no_arbitrary_shell", e.code == "TEST_NOT_ALLOWED")
# 8) dispatcher: correlation + replay + capability lạ
h1 = ops.handle({"request_id": "R1", "capability": "READ_FILE", "path": "a/note.txt"})
h2 = ops.handle({"request_id": "R1", "capability": "READ_FILE", "path": "a/note.txt"})
h3 = ops.handle({"request_id": "R2", "capability": "DROP_TABLE"})
h4 = ops.handle({"capability": "READ_FILE", "path": "a/note.txt"})
rec("dispatch_ok_correlated", h1["ok"] and h1["request_id"] == "R1")
rec("dispatch_replay_rejected", h2["error"]["code"] == "REPLAY_REJECTED")
rec("dispatch_unknown_cap_denied", h3["error"]["code"] == "UNKNOWN_CAPABILITY")
rec("dispatch_missing_rid", h4["error"]["code"] == "MISSING_REQUEST_ID")
# 9) kích thước
try: ops.write_file("big.txt", base64.b64encode(b"x" * 2_000_000).decode()); rec("size_limit_blocked", False)
except FileOpError as e: rec("size_limit_blocked", e.code == "TOO_LARGE")
# 10) audit chain + ghi ngoài sandbox không tồn tại
v = ops.verify_audit()
rec("audit_chain_valid", v["ok"] and v["records"] > 8, f"records={v['records']}")
rec("no_file_outside_sandbox", not any(x for x in (sb / "..").rglob("escape.txt")))
for n, d in P: print(f"  PASS | {n:34} | {d}")
for n, d in F: print(f"  FAIL | {n:34} | {d}")
print(f"  ── TỔNG: PASS={len(P)} FAIL={len(F)}")
sys.exit(0 if not F else 1)
