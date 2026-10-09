# GO Runtime Authority V1

## Canonical ownership
- `control/MASTER_GOVERNANCE_RULESET_V1.md` is the sole governing policy source. The runtime verifies its pinned SHA-256 and the matching owner-direction binding before startup and before execution; no parallel policy file may override it.
- This document defines GO runtime ownership and identity only. It is subordinate to MASTER GOVERNANCE RULESET V1 and is not a competing governance ruleset.
- GO is the sole canonical runtime owner.
- LOVE remains a canonical source/project dependency only where explicitly imported by contract; it is not a second GO runtime or policy authority.
- GO owns runtime identity, execution state, runtime service, and runtime endpoint.
- A second execution runtime for the same canonical GO workload is prohibited.

## Runtime identity
A GO runtime identity binds:
- source commit SHA
- source tree SHA
- deployment worktree
- runtime version
- process identity
- endpoint/protocol
- environment
- governance source SHA-256
- evidence chain

## Execution ownership
GO is the sole owner of DurableExecution and execution state for workloads submitted to the GO runtime. MASTER GOVERNANCE RULESET V1 defines the governing requirements; GO enforces the executable authorization, safety, state, and evidence controls. Governance may authorize or deny work but does not execute it.

## Evidence
Evidence remains a single authority domain. Every execution evidence record must bind to the GO runtime identity, source commit/tree, worktree, execution_id, evidence_id, and `governance_source_sha256`. A source hash proves which policy bytes were loaded; it does not by itself prove that every semantic rule was satisfied.

## Cutover invariant
No old runtime may remain an execution authority after GO cutover. Historical artifacts may be retained outside the GO runtime boundary, but GO source and runtime must not import, invoke, or identify an old runtime as an execution authority. Legacy governance documents are not active policy sources; they may be retained only as historical records.
