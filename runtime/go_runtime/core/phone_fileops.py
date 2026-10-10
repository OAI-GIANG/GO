"""Phone Agent file operations — sandboxed + allowlisted + provenance (V1).
Bất biến: (1) mọi path qua _safe_path (canonicalize + containment); (2) allowlist extension;
(3) KHÔNG arbitrary shell — RUN_TEST chỉ chạy entry trong ALLOWED_TESTS; (4) mọi ghi có sha256 + audit."""
from __future__ import annotations
import base64, difflib, fcntl, hashlib, json, os, pathlib, re, subprocess, tempfile, time, uuid
from dataclasses import dataclass, field
from typing import Any

CAPABILITIES = ("LIST_FILES", "READ_FILE", "WRITE_FILE", "APPLY_PATCH", "GET_DIFF", "RUN_TEST")
SANDBOX_DEFAULT = pathlib.Path(os.getenv("HG_PHONE_SANDBOX", "/data/data/com.termux/files/home/.cache/hg-phone-agent/sandbox"))
ALLOW_EXT = {
    ".txt", ".md", ".json", ".py", ".sh", ".log", ".csv", ".yaml", ".yml", ".ini", ".cfg",
    ".java", ".kt", ".xml", ".gradle", ".kts", ".properties", ".toml", ".js", ".ts", ".tsx",
    ".jsx", ".html", ".css", ".scss", ".sql", ".go", ".rs", ".c", ".h", ".cpp", ".hpp",
    ".bat", ".ps1", ".mjs", ".cjs",
}
ALLOW_BASENAMES = {"Makefile", "Dockerfile", "Containerfile", "Justfile", "gradlew", "mvnw"}
EXCLUDED_DIRS = {".git", ".gradle", "build", "node_modules", "__pycache__", ".venv", "venv", "dist", "target",
                 ".ssh", ".aws", ".gnupg", "secrets", "credentials", "private_keys"}
SENSITIVE_NAMES = {".env", ".netrc", ".npmrc", ".pypirc", ".git-credentials", "id_rsa", "id_ed25519",
                   "credentials.json", "secrets.json", "keystore.jks"}
SENSITIVE_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".jks", ".keystore"}
MAX_BYTES = 1_048_576
MAX_LIST_ENTRIES = 500
MAX_LIST_DEPTH = 6
ALLOWED_TESTS = {"smoke": ["python3", "-c", "print('SMOKE_OK')"],
                 "selftest": ["python3", "-c", "import sys;print('SELFTEST_OK');sys.exit(0)"]}
AUDIT_EVENTS = ("LIST_FILES", "READ_FILE", "WRITE_FILE", "APPLY_PATCH", "GET_DIFF", "RUN_TEST", "DENIED")


class FileOpError(Exception):
    def __init__(self, code: str, message: str | None = None):
        self.code = code
        super().__init__(message or code)


def atomic_write(path: pathlib.Path, data: bytes) -> None:
    """Replace a sandbox file atomically; a failed write leaves the old file intact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".hg-write-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
        try:
            dir_fd = os.open(str(path.parent), os.O_RDONLY)
            try: os.fsync(dir_fd)
            finally: os.close(dir_fd)
        except OSError:
            pass
    finally:
        try: os.unlink(tmp_name)
        except FileNotFoundError: pass


def sha256_of(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def is_sensitive_path(rel: str) -> bool:
    parts = pathlib.PurePosixPath(rel).parts
    for part in parts:
        name = part.lower()
        if name in SENSITIVE_NAMES or name.startswith(".env."):
            return True
        if pathlib.Path(name).suffix.lower() in SENSITIVE_SUFFIXES:
            return True
    return False


def safe_path(sandbox: pathlib.Path, rel: str, *, must_exist: bool = False) -> pathlib.Path:
    """Canonicalize + containment + symlink resolution + extension and secret-path allowlists."""
    sb = pathlib.Path(sandbox).resolve()
    sb.mkdir(parents=True, exist_ok=True)
    if not isinstance(rel, str) or not rel or rel.startswith("/") or "\x00" in rel or "\\" in rel:
        raise FileOpError("INVALID_PATH")
    if is_sensitive_path(rel):
        raise FileOpError("SENSITIVE_PATH_DENIED")
    p = (sb / rel).resolve()
    if not (p == sb or str(p).startswith(str(sb) + os.sep)):
        raise FileOpError("PATH_OUTSIDE_SANDBOX")
    if p.suffix.lower() not in ALLOW_EXT and p.name not in ALLOW_BASENAMES:
        raise FileOpError("EXTENSION_NOT_ALLOWED")
    if must_exist and not p.is_file():
        raise FileOpError("NOT_FOUND")
    return p


def safe_dir(sandbox: pathlib.Path, rel: str = ".") -> pathlib.Path:
    """Resolve a directory under the workspace without requiring a file extension."""
    sb = pathlib.Path(sandbox).resolve()
    sb.mkdir(parents=True, exist_ok=True)
    rel = rel or "."
    if not isinstance(rel, str) or rel.startswith("/") or "\x00" in rel or "\\" in rel:
        raise FileOpError("INVALID_PATH")
    if any(part == ".." for part in pathlib.PurePosixPath(rel).parts):
        raise FileOpError("PATH_OUTSIDE_SANDBOX")
    if is_sensitive_path(rel):
        raise FileOpError("SENSITIVE_PATH_DENIED")
    p = (sb / rel).resolve()
    if not (p == sb or str(p).startswith(str(sb) + os.sep)):
        raise FileOpError("PATH_OUTSIDE_SANDBOX")
    if not p.is_dir():
        raise FileOpError("NOT_DIRECTORY")
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
    def list_files(self, rel: str = ".") -> dict:
        sb = pathlib.Path(self.sandbox).resolve()
        root = safe_dir(sb, rel)
        entries = []
        truncated = False
        for current_raw, dirs, files in os.walk(root, topdown=True, followlinks=False):
            current = pathlib.Path(current_raw)
            depth = len(current.relative_to(root).parts)
            dirs[:] = sorted(d for d in dirs
                             if d not in EXCLUDED_DIRS and not (current / d).is_symlink()
                             and depth < MAX_LIST_DEPTH)
            for name in dirs:
                q = current / name
                entries.append({"path": q.relative_to(sb).as_posix(), "kind": "directory"})
                if len(entries) >= MAX_LIST_ENTRIES:
                    truncated = True
                    break
            if truncated:
                break
            for name in sorted(files):
                q = current / name
                rel_path = q.relative_to(sb).as_posix()
                if q.is_symlink() or is_sensitive_path(rel_path) or (q.suffix.lower() not in ALLOW_EXT and q.name not in ALLOW_BASENAMES):
                    continue
                try:
                    size = q.stat().st_size
                except OSError:
                    continue
                item = {"path": rel_path, "kind": "file", "bytes": size}
                if size <= 65536:
                    try: item["sha256"] = sha256_of(q.read_bytes())
                    except OSError: continue
                entries.append(item)
                if len(entries) >= MAX_LIST_ENTRIES:
                    truncated = True
                    break
            if truncated:
                break
        entries.sort(key=lambda x: (x["path"], x["kind"]))
        self._emit("LIST_FILES", path=rel or ".", entries=len(entries), truncated=truncated)
        return {"path": rel or ".", "entries": entries, "truncated": truncated}

    def read_file(self, rel: str) -> dict:
        p = safe_path(self.sandbox, rel, must_exist=True)
        raw = p.read_bytes()
        if len(raw) > MAX_BYTES: raise FileOpError("TOO_LARGE")
        h = sha256_of(raw)
        self._emit("READ_FILE", path=rel, bytes=len(raw), sha256=h)
        return {"path": rel, "bytes": len(raw), "sha256": h, "content_b64": base64.b64encode(raw).decode()}

    def write_file(self, rel: str, content_b64: str, expect_sha256: str | None = None,
                   expected_current_sha256: str | None = None) -> dict:
        try: raw = base64.b64decode(content_b64, validate=True)
        except Exception: raise FileOpError("INVALID_BASE64")
        if len(raw) > MAX_BYTES: raise FileOpError("TOO_LARGE")
        p = safe_path(self.sandbox, rel)
        if expect_sha256 and sha256_of(raw) != expect_sha256: raise FileOpError("SHA256_MISMATCH")
        before = sha256_of(p.read_bytes()) if p.is_file() else None
        if before is not None and expected_current_sha256 is None:
            raise FileOpError("PRECONDITION_REQUIRED")
        if expected_current_sha256 is not None and before != expected_current_sha256:
            raise FileOpError("CURRENT_SHA256_MISMATCH")
        atomic_write(p, raw)
        after = sha256_of(p.read_bytes())
        self._emit("WRITE_FILE", path=rel, bytes=len(raw), sha256_before=before, sha256_after=after)
        return {"path": rel, "bytes": len(raw), "sha256_before": before, "sha256_after": after, "verified": after == sha256_of(raw)}

    def apply_patch(self, rel: str, patch_text: str, expected_current_sha256: str | None = None) -> dict:
        p = safe_path(self.sandbox, rel, must_exist=True)
        raw = p.read_bytes()
        before = sha256_of(raw)
        if not expected_current_sha256:
            raise FileOpError("PRECONDITION_REQUIRED")
        if before != expected_current_sha256:
            raise FileOpError("CURRENT_SHA256_MISMATCH")
        src = raw.decode("utf-8", errors="replace")
        if not re.search(r"^[+-]", patch_text, re.M): raise FileOpError("INVALID_PATCH")
        out = src.splitlines()
        minus = [l[1:] for l in patch_text.splitlines() if l.startswith("-") and not l.startswith("---")]
        plus = [l[1:] for l in patch_text.splitlines() if l.startswith("+") and not l.startswith("+++")]
        if not minus: raise FileOpError("INVALID_PATCH")
        matches = [i for i in range(len(out) - len(minus) + 1) if out[i:i + len(minus)] == minus]
        if len(matches) == 0: raise FileOpError("PATCH_CONTEXT_NOT_FOUND")
        if len(matches) > 1: raise FileOpError("PATCH_CONTEXT_AMBIGUOUS")
        i = matches[0]
        new = out[:i] + plus + out[i + len(minus):]
        new_text = "\n".join(new) + ("\n" if src.endswith("\n") else "")
        atomic_write(p, new_text.encode("utf-8"))
        after = sha256_of(p.read_bytes())
        self._emit("APPLY_PATCH", path=rel, hunks=1, sha256_before=before, sha256_after=after)
        return {"path": rel, "hunks": 1, "sha256_before": before, "sha256_after": after}

    def get_diff(self, rel: str, new_content_b64: str) -> dict:
        p = safe_path(self.sandbox, rel, must_exist=False)
        if p.exists() and not p.is_file(): raise FileOpError("NOT_FILE")
        try: raw = base64.b64decode(new_content_b64, validate=True)
        except Exception: raise FileOpError("INVALID_BASE64")
        old = p.read_text(errors="replace").splitlines(keepends=True) if p.is_file() else []
        new = raw.decode(errors="replace").splitlines(keepends=True)
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
        configured = os.getenv("HG_PHONE_REPLAY_LOG", "").strip()
        path = pathlib.Path(configured) if configured else pathlib.Path(self.sandbox) / ".hg_replay.jsonl"
        return ReplayGuard(path)

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
            if cap == "LIST_FILES":       r = self.list_files(req.get("path", ".") or ".")
            elif cap == "READ_FILE":      r = self.read_file(req["path"])
            elif cap == "WRITE_FILE":     r = self.write_file(req["path"], req["content_b64"], req.get("expect_sha256"), req.get("expected_current_sha256"))
            elif cap == "APPLY_PATCH":    r = self.apply_patch(req["path"], req["patch"], req.get("expected_current_sha256"))
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
        except Exception:
            g.finalize(rid, "FAILED", {"code": "INTERNAL_ERROR"})
            self._emit("DENIED", capability=cap, reason="INTERNAL_ERROR", request_id=rid)
            return {"ok": False, "request_id": rid, "capability": cap, "error": {"code": "INTERNAL_ERROR"}}


def json_dumps(o: Any) -> str:
    import json
    return json.dumps(o, sort_keys=True, separators=(",", ":"))
