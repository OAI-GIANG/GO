# External Technical References & Decisions (G2 / HG remediation)

Access date for all: 2026-10-10. Only sources actually read are marked READ; others are
flagged as referenced-only (not independently read).

| Source | URL | Version/date | READ? | Principle used | Decision informed |
|---|---|---|---|---|---|
| RFC 8785 JCS | https://www.rfc-editor.org/rfc/rfc8785 | RFC 8785, 2020-06 | READ | Deterministic JSON serialization for repeatable hashing/signatures | Repo uses `"|".join(...)` for `canonical_payload`/digests, not JCS. **No silent migration**: a JCS switch would change every historical digest ⇒ would require explicit versioning + legacy verification. Left unchanged; recorded as BLK-5. |
| OWASP Logging Cheat Sheet | https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html | Cheat Sheet (current) | READ | Tamper detection for stored logs; protect integrity at rest; log failures must not silently break the app; treat event data from other trust zones as untrusted; test logging failure modes | Supports (a) fail-closed + explicit audit on approval/nonce storage failure, (b) verifier robustness, (c) not silently rewriting the corrupted audit chain. |
| SQLite — Atomic Commit | https://www.sqlite.org/atomiccommit.html | SQLite doc (current) | READ | Atomic commit = all-or-none; durability via journal + fsync; delete/truncate journal is the commit point | Chosen **not** to introduce a second SQLite store for nonces (tool ledger is file-based); used atomic `O_CREAT|O_EXCL` reservation in the ledger directory with `fsync`. Documented limitation (local FS only). |
| SQLite — CREATE TABLE (UNIQUE) | https://www.sqlite.org/lang_createtable.html | SQLite doc | referenced-only | UNIQUE constraint enforces uniqueness atomically inside a transaction | Considered for an alternative nonce store; not adopted (kept single source of truth). |
| SQLite — Transactions | https://www.sqlite.org/lang_transaction.html | SQLite doc | referenced-only | Transaction boundaries/isolation | Same consideration. |
| IETF Idempotency-Key | https://datatracker.ietf.org/doc/draft-ietf-httpapi-idempotency-key-header/ | draft-07, 2025-10-15; **expired 2026-04-18** | READ | Retry vs concurrent duplicate: respond with prior result on retry-after-completion; conflict on concurrent in-flight; key uniqueness; fingerprint | Informs idempotency/concurrency semantics of the task path and the nonce single-use design. Note: draft is **expired**, not an RFC. |
| NIST SP 800-92 | https://csrc.nist.gov/pubs/sp/800/92/final | 2006 (Guide to Computer Security Log Management) | referenced-only (via OWASP; page not fetched this session) | Log lifecycle, integrity protection, operational management | Cited for audit integrity intent only; **not independently verified**. |
| W3C PROV-Overview | https://www.w3.org/TR/prov-overview/ | Note 2013-04-30 | READ (earlier session) | Provenance of entities/activities | Provenance chain design (source→artifact→runtime→evidence). |

## Conflicts with repository constraints
- RFC 8785 vs the repo's `"|".join` digest: **conflict recorded, not silently resolved**. Migration
  would require versioning + legacy compatibility + canonical approval (see BLK-5). No change made.
- External references are **technical only**; they do not constitute HG governance authority or
  approval.
