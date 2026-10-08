# GO Runtime — Repository Forensics (canonical capability)

CAPABILITY_ID: HG-CAP-REPO-FORENSICS-V1
STATUS: canonical (absorbed from the engineering procedure used to audit, canonicalize, and verify HG itself)
OWNER_MODULE: `runtime/go_runtime/core/engine/repo_forensics.py`
GOVERNANCE: exposed only via `ToolRegistry -> ToolGovernance -> CredentialBroker` as the read-only tool `hg.repo.forensics`
EVIDENCE: every report carries a canonical SHA-256 digest (`inventory_sha256`, `report_sha256`); tool calls are recorded in the ToolEventLedger with a witness.

## Purpose

Turn the repository-engineering workflow (inspect → map → detect duplication → detect drift → prove parity) into a deterministic, model-independent HG capability, so HG can audit a source tree and prove canonical↔runtime parity without external assistance.

## Interface

Pure functions (no network, no subprocess, no model):

| function | input | output |
|---|---|---|
| `file_inventory(root, exts=None)` | tree | `{path: {sha256, bytes}}` |
| `module_imports(root)` | tree | `{path: {parse, imports[]}}` |
| `duplicate_candidates(root)` | tree | `[{digest, locations[]}]` (semantic-duplicate callables) |
| `parity(local_inventory, canonical_manifest)` | inventories | `{match, mismatch[], missing[], extra[]}` |
| `forensic_report(root, canonical_manifest=None)` | tree (+manifest) | digested report incl. `report_sha256` |

Governed tool: `hg.repo.forensics({root, mode?})`, `mode ∈ {report, inventory, module_map, duplicates}`.

## Invariants (enforced by tests)

1. **Deterministic** — the same tree yields byte-identical inventories and report digests.
2. **Tamper-evident** — any content change changes `report_sha256`.
3. **Self-excluding digest** — `report_sha256 = sha256(canonical_json(report without report_sha256))`.
4. **Pure stdlib** — no `subprocess`/`socket`/`urllib`/`http`/`asyncio` (AST-checked).
5. **Root-bounded** — the tool refuses any `root` outside `HG_FORENSICS_ROOT` (default `/opt/go`).
6. **Read-only** — never mutates the tree.
7. **Parse-safe** — unparsable files are reported (`parse=error`), never raised.
8. **BOM/encoding-tolerant** — files decoded as `utf-8-sig`; leading BOMs are reported via `bom_files`, never mis-flagged as parse errors.
9. **Volatile-safe** — callers may pass `exclude` dirs (e.g. live `data/`) so digests stay stable over append-only subtrees.

## Placement rationale

* It is a *knowledge/procedure* capability, so it belongs in `engine/` alongside `durable_execution`, `learning`, `memory_trust` — not in the model gateway (no reasoning) and not in `store` (no persistence).
* Its only authority is read access to an allowlisted root, so it is a **read_only** tool: it needs `ToolGovernance` (provenance/session binding) but no destructive-approval gate.
* It composes with existing capabilities: callers may feed `github.read_*` results into `parity()` for canonical↔runtime drift checks.

## Provenance

SOURCE_CLASS: engineering procedure (repository audit / canonicalization workflow)
SOURCE_REFERENCE: HG runtime canonicalization + identity-migration audit procedure
DESTINATION: `runtime/go_runtime/core/engine/repo_forensics.py` (+ `hg.repo.forensics` tool)
TRANSFORMATION: distilled to pure, typed, stdlib-only functions; deduplicated against existing HG (no second registry/governance/executor/memory/evidence system)
REASON: HG had raw `github.read_*` adapters but no deterministic repository-forensic composition
TESTS: `tests/test_repo_forensics.py` (10 cases: determinism, exclusions, module map, duplicate detection, docstring-insensitive duplicates, parity/drift, digest stability, no-network/no-subprocess, root-bound, tool modes)
