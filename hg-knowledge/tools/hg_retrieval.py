"""HG-owned retrieval index and search.

Independent of LOVE and PARADISE by construction: the index is built only from the
HG canonical tree, and every record carries source_path + source_commit + source_hash.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

SYSTEM_IDENTITY = "OAI-GIANG/HG"
SOURCE_REPOSITORY = "OAI-GIANG/GO"
SOURCE_BRANCH = "hg-core"
INDEX_SUFFIXES = (".md", ".py", ".json", ".yaml", ".yml", ".toml", ".txt", ".csv")
SKIP_DIRS = frozenset({"__pycache__", ".git", ".pytest_cache", "node_modules", "hg-knowledge"})
FORBIDDEN_ORIGINS = ("stt_love", "projects/LOVE", "paradise", "runtime_v1")


class RetrievalError(ValueError):
    """A retrieval or provenance rule was violated."""


def repository_identity(source_commit: str) -> dict:
    return {"system_identity": SYSTEM_IDENTITY, "source_repository": SOURCE_REPOSITORY,
            "source_branch": SOURCE_BRANCH, "source_commit": source_commit}


def iter_documents(root: str | Path):
    root = Path(root)
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.suffix not in INDEX_SUFFIXES:
            continue
        rel = p.relative_to(root).as_posix()
        if SKIP_DIRS & set(p.parts):
            continue
        yield rel, p


def build_index(root: str | Path, source_commit: str) -> list[dict]:
    docs = []
    for rel, p in iter_documents(root):
        raw = p.read_bytes()
        docs.append({
            "id": rel, "path": rel, "kind": p.suffix.lstrip("."),
            "source_commit": source_commit,
            "source_hash": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
            "text": raw.decode("utf-8", errors="replace"),
        })
    return docs


def index_digest(docs: list[dict]) -> str:
    h = hashlib.sha256()
    for d in docs:
        h.update(d["path"].encode("utf-8"))
        h.update(b"\0")
        h.update(d["source_hash"].encode("utf-8"))
    return h.hexdigest()


def verify_provenance(docs: list[dict], root: str | Path) -> dict:
    """Independently re-hash each indexed file and confirm the record matches."""
    root = Path(root)
    checked, mismatched, forbidden = 0, [], []
    for d in docs:
        p = root / d["path"]
        if not p.is_file():
            mismatched.append(d["path"])
            continue
        if hashlib.sha256(p.read_bytes()).hexdigest() != d["source_hash"]:
            mismatched.append(d["path"])
        if any(f in d["path"] for f in FORBIDDEN_ORIGINS):
            forbidden.append(d["path"])
        checked += 1
    if mismatched:
        raise RetrievalError("PROVENANCE_HASH_MISMATCH:" + ",".join(mismatched[:5]))
    if forbidden:
        raise RetrievalError("FOREIGN_ORIGIN_IN_INDEX:" + ",".join(forbidden[:5]))
    return {"verified": True, "checked": checked, "mismatched": 0, "foreign_origin": 0}


def search(docs, query="", limit=8, path_prefix=None, kind=None) -> list[dict]:
    terms = [t for t in (query or "").lower().split() if t]
    hits = []
    for d in docs:
        if path_prefix and not d["path"].startswith(path_prefix):
            continue
        if kind and d["kind"] != kind:
            continue
        text, path = d["text"].lower(), d["path"].lower()
        score = sum(text.count(t) + 3 * path.count(t) for t in terms)
        if terms and score == 0:
            continue
        hits.append({k: d[k] for k in ("id", "path", "kind", "source_commit", "source_hash", "bytes")}
                    | {"score": score})
    hits.sort(key=lambda r: (-r["score"], r["path"]))
    return hits[:limit]


def write_index(root: str | Path, source_commit: str, out_dir: str | Path) -> dict:
    root, out_dir = Path(root), Path(out_dir)
    docs = build_index(root, source_commit)
    manifest = verify_provenance(docs, root)
    (out_dir / "index").mkdir(parents=True, exist_ok=True)
    (out_dir / "manifests").mkdir(parents=True, exist_ok=True)
    with (out_dir / "index" / "knowledge.jsonl").open("w", encoding="utf-8") as fh:
        for d in docs:
            fh.write(json.dumps(d, ensure_ascii=False) + "\n")
    ident = repository_identity(source_commit) | {
        "document_count": len(docs), "index_digest": index_digest(docs),
        "provenance": manifest, "retrieval_tool": "hg-knowledge/tools/hg_retrieval.py",
    }
    (out_dir / "manifests" / "repository-identity.json").write_text(
        json.dumps(ident, indent=2, ensure_ascii=False), encoding="utf-8")
    with (out_dir / "manifests" / "file-inventory.jsonl").open("w", encoding="utf-8") as fh:
        for d in docs:
            fh.write(json.dumps({"path": d["path"], "sha256": d["source_hash"], "bytes": d["bytes"]}) + "\n")
    return ident
