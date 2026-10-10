# G2 — Reconciliation, Provenance & Research (READ-ONLY analysis record)

Revisions (verified present on GitHub): BASE=`a4d453519ea8994650cb520606eb013ddca8896e`,
HC=`6a700ede39d2118fb2e5289ce1f0f49070877a17` (current hg-core HEAD=`955d9a5e…`);
PR8=`cecfb72052f0041d79ec4c5146f59f76b621be70` (branch `HG-V2-REMEDIATION`, base=BASE).
`merge-base(HC,PR8)=BASE`. Reconciled working branch is a clean descendant of `hg-core` HEAD.

## 1. Three-way semantic conflict matrix (4 overlapping files)
Blob SHAs BASE→HC→PR8:
- go_kernel.py `274dd69`→`f4a2869`→`63c625a`
- cognitive.py `df8d32b`→`5d4a64c`→`834c59b`
- server.py `d5a55a8`→`142b84a`→`bbdcdc8`
- tool_governance.py `dfc7490`→`c8cf9f5`→`c80433b`

| # | Topic | HC | PR8 | Decision | Test |
|---|---|---|---|---|---|
| C1 | Authority issuance | self-issued from env provenance | `AuthorityRoot.issue()` | **COMBINE** (root + provenance gate) | `test_g2_*authority*` |
| C2 | Evidence policy binding | adds `governance_source_sha256` | — | **KEEP (HC)** | `test_g2_policy_source_hash_pinned` |
| C3 | Promotion gate | integrity-based | requires `VerificationResult` | **REPLACE with PR8** | `test_g2_evidence_promotion_requires_verifier` |
| C4 | server guards/epistemics | `verify_governance_source()` at entries; healthz 503 | kernel+ivv+epistemics; `vps2_target_id` | **COMBINE** | `test_g2_server_entrypoints_guard_governance` |
| C5 | emit_evidence binding | binds policy sha | — | **KEEP (HC)** | (covered by evidence tests) |
| C6 | ledger/witness binding | adds governance_source_sha256 | — | **KEEP (HC)** | `test_g2_tool_witness_binds_governance_hash` |
| C7 | idempotency | unchanged | unchanged | **NOT_APPLICABLE** | `test_g2_request_fingerprint_binds_fields` |
| C8 | memory/learning trust | — | independent evaluator; confidence 0 | **KEEP (PR8)** | (design) |
| C9 | vps2_target_id | — | `req.target_id or env` | **KEEP (PR8)** | `test_g2_server_entrypoints_guard_governance` |
| C10 | bypass paths | guards at entries | — | **COMBINE** | route-coverage test |

## 2. External research register (accessed 2026-10-10)
| Name / org | URL | Version/date | Clause | Maps to |
|---|---|---|---|---|
| W3C PROV-Overview | https://www.w3.org/TR/prov-overview/ | Note 2013-04-30 | §1–2 | G2-W11 provenance |
| IETF Idempotency-Key | https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-idempotency-key-header | draft-07, 2025-10-15 | §2.4,§2.6,§2.7 | G2-W7/W8 |
| RFC 8785 JCS | https://www.rfc-editor.org/rfc/rfc8785.txt | RFC 8785, 2020-06 | §3.2,§3.2.3,§5 | canonical hashing (BLK-5) |
| IANA HTTP Status | https://www.iana.org/assignments/http-status-codes/http-status-codes.xhtml | upd. 2025-09-15 | 200/401/409/422/5xx | oracles |
Findings/limits: repo canonical hashing uses `"|".join(...)` (not RFC 8785 JCS) ⇒ potential separator
ambiguity; **no silent change made** (would break historical evidence). External docs are technical
references only, not HG governance authority.

## 3. PAG-1.0 provenance search report
Searched: git `--all --grep/-S PAG|D-G2`; all branch trees; tags/refs; PRs/issues (`gh`); local
`E:\OAI\HG` + temp; filename globs `*PAG*|*D-G2*`; web variants. Result: **`NOT_FOUND_IN_SCANNED_SCOPE`**
(only reference: `evidence/B1_B5_RECONCILIATION_IMPLEMENTATION_20261010.md:78` "PAG-1.0 remains BLOCKED").
No issuing authority/version/hash/approval recoverable. Not fabricated.

## 4. Provenance
- Reconciled branch: `feature/stt-b1-b5-reconciliation-20261010` @ `5c76aab…` → new working branch
  `feature/g2-design-finalization-20261010` (0 behind / 34 ahead of `hg-core` HEAD).
- Runtime VPS1 (`/opt/go`, `d635e883…`) is **not** asserted to equal any of BASE/HC/PR8 (BLK-6).
- Policy V1 `cc1a8b17…` / binding `538c0b40…` unchanged (not modified).
