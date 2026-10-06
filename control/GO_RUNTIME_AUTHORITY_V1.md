# GO Runtime Authority V1

## Canonical ownership
- Governance and policy are external to this repository.
- GO is the sole canonical runtime owner.
- LOVE remains the canonical source/project dependency where explicitly imported by contract.
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
- evidence chain

## Execution ownership
GO is the sole owner of DurableExecution and execution state for workloads submitted to the GO runtime. Governance may authorize or deny work but does not execute it.

## Evidence
Evidence remains a single authority domain, but every execution evidence record must bind to the GO runtime identity, source commit/tree, worktree, execution_id and evidence_id.

## Cutover invariant
No old runtime may remain an execution authority after GO cutover. Historical artifacts may be retained outside the GO runtime boundary, but GO source and runtime must not import, invoke, or identify the old runtime.
