"""HG canonical repository forensics (deterministic, model-independent capability).

This module distils the repository-engineering procedure used to audit and
canonicalize a source tree into a single reusable, bounded capability:

  inventory  -> module map -> semantic-duplicate candidates
             -> canonical-vs-runtime parity (drift) -> digested report

Design invariants (enforced by tests):
  * deterministic   : same tree => identical report bytes / digest
  * pure-stdlib     : no network, no subprocess, no model, no hidden state
  * bounded         : operates only under a caller-provided root
  * evidence-first  : every report carries a canonical SHA-256 digest
  * read-only       : never mutates the tree

Canonical owner: HG runtime engine (knowledge/procedure capability).
Governance: exposed only through ToolRegistry -> ToolGovernance -> CredentialBroker.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Iterator

SCHEMA = "HG-REPO-FORENSICS-V1"
DEFAULT_EXCLUDE_DIRS = frozenset(
    {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "node_modules", ".venv", "venv"}
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def digest(value: Any) -> str:
    return sha256_text(canonical_json(value))


def _combined_excludes(exclude_dirs: Iterable[str] | None) -> frozenset[str]:
    return DEFAULT_EXCLUDE_DIRS | frozenset(exclude_dirs or ())


def _iter_files(root: Path, exts: tuple[str, ...] | None, exclude_dirs: frozenset[str]) -> Iterator[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in exclude_dirs)
        for fn in sorted(filenames):
            p = Path(dirpath) / fn
            if exts is not None and p.suffix not in exts:
                continue
            yield p


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def file_inventory(
    root: str | os.PathLike[str],
    exts: tuple[str, ...] | None = None,
    exclude_dirs: Iterable[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Deterministic {relative_path: {sha256, bytes}} inventory of a tree."""
    base = Path(root)
    excludes = _combined_excludes(exclude_dirs)
    out: dict[str, dict[str, Any]] = {}
    for p in _iter_files(base, exts, excludes):
        data = p.read_bytes()
        out[_rel(base, p)] = {"sha256": sha256_bytes(data), "bytes": len(data), "bom": data[:3] == b"\xef\xbb\xbf"}
    return out


def _imports_of(tree: ast.AST) -> list[str]:
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mods.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mods.add("." * int(node.level) + (node.module or ""))
    return sorted(mods)


def module_imports(
    root: str | os.PathLike[str], exts: tuple[str, ...] = (".py",), exclude_dirs: Iterable[str] | None = None
) -> dict[str, Any]:
    """{relative_path: {imports: [...], parse: ok|error}} via AST (no execution)."""
    base = Path(root)
    excludes = _combined_excludes(exclude_dirs)
    out: dict[str, Any] = {}
    for p in _iter_files(base, exts, excludes):
        try:
            tree = ast.parse(p.read_text(encoding="utf-8-sig"))
        except (SyntaxError, UnicodeDecodeError, ValueError) as exc:
            out[_rel(base, p)] = {"parse": "error", "error": type(exc).__name__}
            continue
        out[_rel(base, p)] = {"parse": "ok", "imports": _imports_of(tree)}
    return out


def _strip_docstring(node: ast.AST) -> None:
    body = getattr(node, "body", None)
    if not body:
        return
    first = body[0]
    value = getattr(first, "value", None)
    if isinstance(first, ast.Expr) and isinstance(value, ast.Constant) and isinstance(value.value, str):
        node.body = body[1:] or [ast.Pass()]


def _callable_digest(node: ast.AST) -> str:
    clone = ast.parse(ast.unparse(node)).body[0]  # deterministic re-parse isolates the callable
    for sub in ast.walk(clone):
        if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
            _strip_docstring(sub)
    return sha256_text(ast.dump(clone, annotate_fields=True, include_attributes=False))


def duplicate_candidates(
    root: str | os.PathLike[str], exts: tuple[str, ...] = (".py",), exclude_dirs: Iterable[str] | None = None
) -> list[dict[str, Any]]:
    """Semantic-duplicate candidates: callables with identical normalized structure.

    Detects copy-pasted/duplicated implementation (the D2 "DUPLICATED" signal)
    without executing any code. Returns groups of {digest, locations}.
    """
    base = Path(root)
    excludes = _combined_excludes(exclude_dirs)
    buckets: dict[str, list[str]] = {}
    for p in _iter_files(base, exts, excludes):
        try:
            tree = ast.parse(p.read_text(encoding="utf-8-sig"))
        except (SyntaxError, UnicodeDecodeError, ValueError):
            continue
        rel = _rel(base, p)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                loc = f"{rel}:{getattr(node, 'lineno', 0)}:{node.name}"
                buckets.setdefault(_callable_digest(node), []).append(loc)
    return [
        {"digest": d, "locations": sorted(locs)}
        for d, locs in sorted(buckets.items())
        if len(locs) > 1
    ]


def parity(local_inventory: dict[str, Any], canonical_manifest: dict[str, Any]) -> dict[str, Any]:
    """Drift detection: compare a local inventory to a canonical manifest.

    manifest values may be a plain sha256 string or {"sha256": ...}.
    """
    mismatch: list[dict[str, Any]] = []
    missing: list[str] = []
    extra: list[str] = []
    for path, meta in sorted(canonical_manifest.items()):
        csha = meta if isinstance(meta, str) else (meta or {}).get("sha256")
        if path not in local_inventory:
            missing.append(path)
        elif local_inventory[path].get("sha256") != csha:
            mismatch.append({"path": path, "canonical": csha, "local": local_inventory[path].get("sha256")})
    for path in sorted(local_inventory):
        if path not in canonical_manifest:
            extra.append(path)
    return {"match": not (mismatch or missing or extra), "mismatch": mismatch, "missing": missing, "extra": extra}


def forensic_report(
    root: str | os.PathLike[str],
    canonical_manifest: dict[str, Any] | None = None,
    exts: tuple[str, ...] | None = None,
    exclude_dirs: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Full digested forensic report for a tree (optionally vs a canonical manifest)."""
    base = Path(root)
    inventory = file_inventory(base, exts, exclude_dirs)
    imports = module_imports(base, exclude_dirs=exclude_dirs)
    duplicates = duplicate_candidates(base, exclude_dirs=exclude_dirs)
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "root": base.as_posix(),
        "files": len(inventory),
        "bytes": sum(meta["bytes"] for meta in inventory.values()),
        "inventory_sha256": digest(inventory),
        "parse_errors": sorted(p for p, m in imports.items() if m.get("parse") == "error"),
        "bom_files": sorted(p for p, m in inventory.items() if m.get("bom")),
        "duplicate_groups": len(duplicates),
        "duplicate_candidates": duplicates,
    }
    if canonical_manifest is not None:
        report["parity"] = parity(inventory, canonical_manifest)
    report["report_sha256"] = digest({k: v for k, v in report.items() if k != "report_sha256"})
    return report
