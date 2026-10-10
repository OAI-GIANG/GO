# MTC-1.0 Phase 2 — Evidence & Reconciliation Set

Status: **INCOMPLETE** (nothing here claims runtime PASS without device evidence).
Branch: `feature/stt-b1-b5-reconciliation-20261010`
Canonical repo: `OAI-GIANG/GO`

This directory reconciles the "HG MTC-1.0 Phase 2 — close all remaining gates" mandate
with **measured reality**. It records what was verified on the real phone (OPPO PKC110,
`adb BIXSMFNBRCNN95T4`), on VPS1 edge (`160.191.242.198`), and in the canonical repo —
and it clearly separates `code-level / unit / replica` evidence from `runtime` evidence.

## Contents

| File | Purpose |
|---|---|
| `ACCEPTANCE_MATRIX.md` | Every gate: PASS / FAIL / BLOCKED / NOT_RUN + evidence + evidence-class |
| `CHECKPOINT.md` | Canonical execution checkpoint (objective…next action) |
| `PHASE2_GATE_CLASSIFICATION.md` | REQUIRED / CONDITIONAL / OUT_OF_SCOPE + minimal verifiable closure conditions |
| `EXTERNAL_RESEARCH.md` | External sources read (URL), verified content, decisions |
| `OWNER_RUNBOOK.md` | Exact minimal owner actions to unblock each gate |
| `IMPLEMENTATION_AND_TESTS.md` | Patches produced + how to run tests + raw results |
| `patch/` | Hardened supervisor + toolplane governance patch (originals + diffs) |
| `tests/` | Isolated tests + captured output |

## Provenance notes

- The mandate's checkpoint (branch `mtc1/legacy-decoupling-governance`, HEAD
  `6a259fb4747f`, `main` `2e75a6cbae2f`, files `stt-health-readonly.yaml`,
  `verify_b1_runtime.py`, `c_allow.sh`, `ACCEPTANCE_MATRIX.md`) **does not exist** in
  this environment. The real counterparts are mapped in `ACCEPTANCE_MATRIX.md`.
- No token/credential/private key value is stored anywhere in this directory.
- Historical evidence was NOT overwritten.
- Independent verification: clone with LF line endings and run the artifact check:
  `git -c core.autocrlf=false clone --branch feature/stt-b1-b5-reconciliation-20261010 https://github.com/OAI-GIANG/GO.git`
  then `bash evidence/MTC1_PHASE2/verify_artifacts.sh` (regenerates the manifest and
  re-checks the governance patch). Default Windows `core.autocrlf=true` rewrites endings on
  checkout and will make `sha256sum -c MANIFEST.sha256` mismatch — that is a checkout
  artifact, not a content change.
