#!/usr/bin/env python3
"""CLI: query the HG retrieval index. Every hit cites source_commit + source_hash."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hg_retrieval import search  # noqa: E402

IDX = Path(__file__).resolve().parents[1] / "index" / "knowledge.jsonl"


def load():
    if not IDX.is_file():
        print(json.dumps({"error": "INDEX_MISSING", "path": str(IDX)}))
        raise SystemExit(2)
    return [json.loads(l) for l in IDX.read_text(encoding="utf-8").splitlines() if l.strip()]


def main(argv):
    if "--list" in argv:
        docs = load()
        print(f"{len(docs)} documents")
        for d in docs:
            print(f"  {d['path']}  {d['source_commit'][:12]}  {d['source_hash'][:12]}")
        return 0
    kind = path = None
    limit = 8
    q = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--kind": kind = argv[i + 1]; i += 2; continue
        if a == "--path": path = argv[i + 1]; i += 2; continue
        if a == "--limit": limit = int(argv[i + 1]); i += 2; continue
        q.append(a); i += 1
    hits = search(load(), " ".join(q), limit=limit, path_prefix=path, kind=kind)
    for h in hits:
        print(f"{h['score']:5}  {h['path']}")
        print(f"       source_commit={h['source_commit']} source_hash={h['source_hash']}")
    if not hits:
        print("no matches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
