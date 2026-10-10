# Consolidated G2 / HG Remediation Report

Baseline: `de4a42b05025f5c1b245b348b0568cea1cbe5cb4` (branch `feature/g2-design-finalization-20261010`, PR #11).
Final: see commit SHA in the accompanying commit / evidence manifest.
Status legend: OBSERVED / INFERRED / PASS / FAIL / BLOCKED / NOT_RUN.

## Finding register & dispositions

| ID | Sev | Root cause | Files changed | Tests | Evidence | Disposition |
|---|---|---|---|---|---|---|
| **BLK-8 / HTTP approval contract** | High | `submit()` deserialized approval **inside** the execution `try` and after task enqueue/claim; malformed approval produced a FAILED task + HTTP 422 instead of rejecting before side effects. (Earlier: `str(body.get("approval")…)` coerced objects to strings.) | `runtime/go_runtime/core/server.py` (`_deserialize_approval` + moved validation before task creation) | `tests/test_g2_http_approval.py` (real ThreadingHTTPServer): malformed string/array/scalar/missing/unknown → **HTTP 400**, no task materialised; echo happy-path 200; auth 401; healthz 200 | `evidence/G2/G2_E2E_TESTS.txt` | **PASS/CLOSED** (OBSERVED via real handler) |
| **BLK-7 / atomic nonce** | High | Replay check was a non-atomic scan of the JSONL ledger (`any(...)`) ⇒ two concurrent requests with the same nonce + different call_id could both pass. | `runtime/go_runtime/core/tool_governance.py` (`ToolEventLedger.reserve_nonce` = `O_CREAT|O_EXCL` + `fsync`; durable; fail-closed on OSError; scan removed) | `tests/test_g2_approval_api.py`: concurrency (8 threads, barrier) → exactly 1 crosses; 7 × `APPROVAL_REPLAY_DETECTED`; durable across instances; store-failure → `APPROVAL_NONCE_STORE_UNAVAILABLE` (fail-closed) | `evidence/G2/G2_E2E_TESTS.txt` | **PASS/CLOSED** (unit/integration; single-process) |
| **HG-F1 / audit hash-chain** | High | Reported `integrity.ok=false`, 876 vs 851 records, prev/hash mismatch on lines 1–4 | none | none | — | **BLOCKED** — source artifact not reachable: `adb` device offline; the hash-chained `prev`/`h` audit is the Termux toolplane file (`~/.config/hg/toolplane_audit.jsonl`, private) and no local snapshot exists. Must not fabricate. |
| **HG-F2 / `go_health` mapping** | Med | Reported `mapped=true`, `canonical_ok=false` at 12:48Z | none | none | — | **BLOCKED (record)** — the exact record is phone-side (offline). Semantics (OBSERVED from `hg_tool_plane.py`): `mapped` = a canonical adapter mapping exists; `canonical_ok` = the canonical decision succeeded. `governance_decide` already **default-denies unmapped side-effect tools** and only lets read-only tools pass on canonical unavailability. No consumer was found in the GO repo that treats `mapped=true` as canonical validity. |
| **BLK-1 / PAG-1.0** | High | Canonical source not found | none | none | `evidence/G2/G2_RECONCILIATION_AND_PROVENANCE.md §3` | **BLOCKED (external/owner)** |
| **BLK-2 / D-G2-01..11** | High | Canonical definitions absent | none | none | `control/G2_WORKSTREAM_REGISTER_PROPOSED_V1.md` | **BLOCKED (owner)**; PROPOSED register present |
| **BLK-3 / trusted verifier** | High | `TRUSTED_VERIFIER_REGISTRY` empty | none | none | `evidence/HG_V2_PRODUCTION_IVV_GATE_BLOCKED.md` | **BLOCKED (external)**; not self-granted |
| **BLK-4 / trusted approval issuer** | High | `TRUSTED_APPROVAL_ISSUERS` empty (intentional) | none | test-only issuer via monkeypatch | `approval.py` | **BLOCKED (external)**; fail-closed preserved |
| **BLK-6 / runtime build identity** | Med | runtime build not mapped to source revision | none | none | — | **BLOCKED (ops)** |

## Policy V1 & approval binding
- Blob ids unchanged vs `hg-core`: policy `64862401e765e49a473b8f31f5e9411e58f8a03c`,
  binding `0e489463709d5e4a4775a2a3aa564cdebc460ec8` → **byte-identical**; protected-file diff empty.
- Policy content SHA-256 `cc1a8b171b1c0e194923359b5b8b17ee9e9ff646b33693cc983f2a9984cc21af`.
- Binding content SHA-256 `e8f1f6bbce850f12d04928143575af43bc00ab44c95e2bb5f0530caaea1c81be`.
  The earlier-reported `538c0b40…` is **not** the file's content sha256 — recorded as an
  unresolved documentation discrepancy (BLK-2-adjacent); **not** reconciled by editing the binding.

## Tests (final revision)
`python -m pytest -q tests` → **243 passed**, exit 0; `compileall -q runtime tests` exit 0;
`git diff --check` clean. Raw output + exit codes: `evidence/G2/G2_E2E_TESTS.txt`.

## Release gates
- Merge: **NOT performed** — BLK-3/BLK-4 unprovisioned; independent review absent; HG-F1/HG-F2 blocked.
- Deploy: **NOT performed** — no runtime target mapped (BLK-6) and merge gate unmet.
- No secrets committed; Policy V1/binding unchanged; no history rewrite.
