"""Phone Agent file operations — sandboxed + allowlisted + provenance (V1).
Bất biến: (1) mọi path qua _safe_path (canonicalize + containment); (2) allowlist extension;
(3) KHÔNG arbitrary shell — RUN_TEST chỉ chạy entry trong ALLOWED_TESTS; (4) mọi ghi có sha256 + audit."""
from __future__ import annotations
import base64, difflib, fcntl, hashlib, json, os, pathlib, re, subprocess, time, uuid
from dataclasses import dataclass, field
from typing import Any

CAPABILITIES = ("READ_FILE", "WRITE_FILE", "APPLY_PATCH", "GET_DIFF", "RUN_TEST")
SANDBOX_DEFAULT = pathlib.Path(os.getenv("HG_PHONE_SANDBOX", "/data/data/com.termux/files/home/.cache/hg-phone-agent/sandbox"))
ALLOW_EXT = {".txt", ".md", ".json", ".py", ".sh", ".log", ".csv", ".yaml", ".yml", ".ini", ".cfg"}
MAX_BYTES = 1_048_576
ALLOWED_TESTS = {"smoke": ["python3", "-c", "print('SMOKE_OK')"],
                 "selftest": ["python3", "-c", "import sys;print('SELFTEST_OK');sys.exit(0)"]}
AUDIT_EVENTS = ("READ_FILE", "WRITE_FILE", "APPLY_PATCH", "GET_DIFF", "RUN_TEST", "DENIED")


class FileOpError(Exception):
    def __init__(self, code: str, message: str | None = None):
        self.code = code
        super().__init__(message or code)


def sha256_of(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def safe_path(sandbox: pathlib.Path, rel: str, *, must_exist: bool = False) -> pathlib.Path:
    """Canonicalize + containment + symlink resolution + allowlist extension."""
    sb = pathlib.Path(sandbox).resolve()
    sb.mkdir(parents=True, exist_ok=True)
    if not isinstance(rel, str) or not rel or rel.startswith("/") or "\x00" in rel or "\\" in rel:
        raise FileOpError("INVALID_PATH")
    p = (sb / rel).resolve()                      # phá ../ và symlink
    if not (p == sb or str(p).startswith(str(sb) + os.sep)):
        raise FileOpError("PATH_OUTSIDE_SANDBOX")
    if p.suffix.lower() not in ALLOW_EXT:
        raise FileOpError("EXTENSION_NOT_ALLOWED")
    if must_exist and not p.is_file():
        raise FileOpError("NOT_FOUND")
    return p




class ReplayError(FileOpError):
    pass


class ReplayGuard:
    """Bền vững xuyên tiến trình: append-only + hash-chain + flock.
    Giao thức: reserve(INFLIGHT) → thực thi → finalize(DONE|FAILED); replay mọi trạng thái đều bị TỪ CHỐI.
    Log hỏng/tamper ⇒ fail-closed (REPLAY_LOG_CORRUPT)."""

    def __init__(self, path: pathlib.Path):
        self.path = pathlib.Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _records(self):
        """Trả (recs, bad, hashes). Hash được tính TRƯỚC khi thêm _line (khớp lúc ghi)."""
        recs, bad, hashes = [], [], []
        if not self.path.exists():
            return recs, bad, hashes
        for i, line in enumerate(self.path.read_text(errors="replace").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
                h = r.pop("h", None)
                calc = hashlib.sha256(json_dumps(r).encode()).hexdigest()
                prev = r.get("prev")
                if calc != h:
                    bad.append({"line": i, "reason": "hash"})
                if not hashes and prev != "GENESIS":
                    bad.append({"line": i, "reason": "genesis"})
                if hashes and prev != hashes[-1]:
                    bad.append({"line": i, "reason": "chain"})
                hashes.append(h)
                r["_line"] = i
                recs.append(r)
            except Exception:
                bad.append({"line": i, "reason": "parse"})
        return recs, bad, hashes

    def _append_locked(self, f, rec: dict, hashes: list) -> None:
        rec["prev"] = hashes[-1] if hashes else "GENESIS"
        rec["h"] = hashlib.sha256(json_dumps(rec).encode()).hexdigest()
        f.write(json_dumps(rec) + "\n")
        f.flush()
        os.fsync(f.fileno())

    def _lock(self):
        f = open(self.path, "a+", encoding="utf-8")
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        return f

    def status(self, rid: str):
        recs, bad, _ = self._records()
        if bad:
            raise ReplayError("REPLAY_LOG_CORRUPT")
        for r in reversed(recs):
            if r.get("request_id") == rid:
                return r.get("state")
        return None

    def reserve(self, rid: str, capability: str) -> None:
        """Kiểm tra trùng + ghi INFLIGHT trong MỘT vùng khoá (chống đua giữa các tiến trình)."""
        with self._lock() as f:
            recs, bad, hashes = self._records()
            if bad:
                raise ReplayError("REPLAY_LOG_CORRUPT")
            for r in recs:
                if r.get("request_id") == rid:
                    raise ReplayError("REPLAY_REJECTED")
            self._append_locked(f, {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                    "request_id": rid, "capability": capability, "state": "INFLIGHT"}, hashes)

    def finalize(self, rid: str, state: str, detail: dict | None = None) -> None:
        with self._lock() as f:
            recs, bad, hashes = self._records()
            if bad:
                return                      # không phá log hỏng; giữ fail-closed ở lần reserve sau
            self._append_locked(f, {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                    "request_id": rid, "state": state, "detail": detail or {}}, hashes)

    def verify(self) -> dict:
        recs, bad, _ = self._records()
        return {"ok": not bad, "records": len(recs), "bad": bad[:5]}


@dataclass
class PhoneFileOps:
    sandbox: pathlib.Path = SANDBOX_DEFAULT
    audit: list = field(default_factory=list)
    _seen: dict = field(default_factory=dict)

    # ---- audit (append-only, hash-chain đơn giản) ----
    def _emit(self, event: str, **kw) -> dict:
        rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "seq": len(self.audit) + 1, "event": event, **kw}
        rec["prev"] = self.audit[-1]["h"] if self.audit else "GENESIS"
        rec["h"] = hashlib.sha256(json_dumps(rec).encode()).hexdigest()
        self.audit.append(rec)
        return rec

    def verify_audit(self) -> dict:
        prev, bad = "GENESIS", []
        for i, r in enumerate(self.audit, 1):
            h = r.get("h"); c = {k: v for k, v in r.items() if k != "h"}
            if c.get("prev") != prev: bad.append({"seq": i, "reason": "prev"})
            if hashlib.sha256(json_dumps(c).encode()).hexdigest() != h: bad.append({"seq": i, "reason": "hash"})
            prev = h
        return {"ok": not bad, "records": len(self.audit), "bad": bad[:5]}

    # ---- capabilities ----
    def read_file(self, rel: str) -> dict:
        p = safe_path(self.sandbox, rel, must_exist=True)
        raw = p.read_bytes()
        if len(raw) > MAX_BYTES: raise FileOpError("TOO_LARGE")
        h = sha256_of(raw)
        self._emit("READ_FILE", path=rel, bytes=len(raw), sha256=h)
        return {"path": rel, "bytes": len(raw), "sha256": h, "content_b64": base64.b64encode(raw).decode()}

    def write_file(self, rel: str, content_b64: str, expect_sha256: str | None = None) -> dict:
        try: raw = base64.b64decode(content_b64, validate=True)
        except Exception: raise FileOpError("INVALID_BASE64")
        if len(raw) > MAX_BYTES: raise FileOpError("TOO_LARGE")
        p = safe_path(self.sandbox, rel)
        p.parent.mkdir(parents=True, exist_ok=True)   # p đã được xác nhận nằm TRONG sandbox
        if expect_sha256 and sha256_of(raw) != expect_sha256: raise FileOpError("SHA256_MISMATCH")
        before = sha256_of(p.read_bytes()) if p.is_file() else None
        p.write_bytes(raw)
        after = sha256_of(p.read_bytes())          # đọc lại ngay, không tin buffer
        self._emit("WRITE_FILE", path=rel, bytes=len(raw), sha256_before=before, sha256_after=after)
        return {"path": rel, "bytes": len(raw), "sha256_before": before, "sha256_after": after, "verified": after == sha256_of(raw)}

    def apply_patch(self, rel: str, patch_text: str) -> dict:
        p = safe_path(self.sandbox, rel, must_exist=True)
        src = p.read_text(errors="replace")
        # chỉ chấp nhận unified diff đơn giản: các dòng +/- ; từ chối hunk header lạ
        if not re.search(r"^[+-]", patch_text, re.M): raise FileOpError("INVALID_PATCH")
        out, changed = [], 0
        for line in src.splitlines():
            out.append(line)
        # áp theo kiểu thay thế dòng '-' bằng dòng '+'
        minus = [l[1:] for l in patch_text.splitlines() if l.startswith("-") and not l.startswith("---")]
        plus = [l[1:] for l in patch_text.splitlines() if l.startswith("+") and not l.startswith("+++")]
        if not minus: raise FileOpError("INVALID_PATCH")
        new = []
        i = 0
        while i < len(out):
            if out[i] == minus[0]:
                new.extend(plus); i += len(minus); changed += 1
            else:
                new.append(out[i]); i += 1
        if changed == 0: raise FileOpError("PATCH_CONTEXT_NOT_FOUND")
        before = sha256_of(src.encode())
        p.write_text("\n".join(new) + ("\n" if src.endswith("\n") else ""))
        after = sha256_of(p.read_bytes())
        self._emit("APPLY_PATCH", path=rel, hunks=changed, sha256_before=before, sha256_after=after)
        return {"path": rel, "hunks": changed, "sha256_before": before, "sha256_after": after}

    def get_diff(self, rel: str, new_content_b64: str) -> dict:
        p = safe_path(self.sandbox, rel, must_exist=True)
        old = p.read_text(errors="replace").splitlines(keepends=True)
        new = base64.b64decode(new_content_b64).decode(errors="replace").splitlines(keepends=True)
        d = "".join(difflib.unified_diff(old, new, fromfile=rel, tofile=rel))
        self._emit("GET_DIFF", path=rel, lines=len(d.splitlines()))
        return {"path": rel, "diff": d, "changed": bool(d)}

    def run_test(self, name: str) -> dict:
        if name not in ALLOWED_TESTS: raise FileOpError("TEST_NOT_ALLOWED")
        cp = subprocess.run(ALLOWED_TESTS[name], capture_output=True, text=True, timeout=60, cwd=str(self.sandbox))
        self._emit("RUN_TEST", test=name, exit=cp.returncode)
        return {"test": name, "exit": cp.returncode, "stdout": cp.stdout[:2000], "stderr": cp.stderr[:1000]}

    # ---- dispatcher (correlation + replay bền vững + validation) ----
    def _guard(self) -> ReplayGuard:
        return ReplayGuard(pathlib.Path(self.sandbox) / ".hg_replay.jsonl")

    def handle(self, req: dict) -> dict:
        rid = str(req.get("request_id") or "")
        cap = str(req.get("capability") or "")
        if not rid: return {"ok": False, "error": {"code": "MISSING_REQUEST_ID"}}
        if cap not in CAPABILITIES:
            self._emit("DENIED", capability=cap or None, reason="UNKNOWN_CAPABILITY", request_id=rid)
            return {"ok": False, "request_id": rid, "error": {"code": "UNKNOWN_CAPABILITY"}}
        g = self._guard()
        try:
            g.reserve(rid, cap)                      # INFLIGHT trước khi thực thi (an toàn đua)
        except ReplayError as e:
            self._emit("DENIED", capability=cap, reason=e.code, request_id=rid)
            return {"ok": False, "request_id": rid, "capability": cap, "error": {"code": e.code}}
        try:
            if cap == "READ_FILE":        r = self.read_file(req["path"])
            elif cap == "WRITE_FILE":     r = self.write_file(req["path"], req["content_b64"], req.get("expect_sha256"))
            elif cap == "APPLY_PATCH":    r = self.apply_patch(req["path"], req["patch"])
            elif cap == "GET_DIFF":       r = self.get_diff(req["path"], req["content_b64"])
            else:                          r = self.run_test(req["test"])
            g.finalize(rid, "DONE", {"capability": cap})
            return {"ok": True, "request_id": rid, "capability": cap, "result": r}
        except FileOpError as e:
            g.finalize(rid, "FAILED", {"code": e.code})
            self._emit("DENIED", capability=cap, reason=e.code, request_id=rid)
            return {"ok": False, "request_id": rid, "capability": cap, "error": {"code": e.code}}
        except KeyError as e:
            g.finalize(rid, "FAILED", {"code": "MISSING_FIELD"})
            return {"ok": False, "request_id": rid, "error": {"code": "MISSING_FIELD", "field": str(e)}}


def json_dumps(o: Any) -> str:
    import json
    return json.dumps(o, sort_keys=True, separators=(",", ":"))
