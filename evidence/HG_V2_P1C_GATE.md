# HG V2 P1-C Gate Evidence

## Scope
Separate execution lifecycle completion from task success in durable persistence.

## Ontology
- state: execution lifecycle, including COMPLETED and FAILED.
- task_outcome: SUCCESS | FAILURE | UNKNOWN.
- status: compatibility projection of task_outcome only.
- COMPLETED no longer implies SUCCESS.

## Remediation
- Added durable tasks.task_outcome column with migration.
- RuntimeStore validates task_outcome and persists it independently from state.
- DurableExecution.finalize() derives UNKNOWN for COMPLETED when success is not proven, SUCCESS only when the report explicitly carries SUCCESS, and FAILURE for terminal failures.
- Legacy status=COMPLETED is rejected instead of being converted to success.
- Existing epistemics envelope already derives UNKNOWN when COMPLETED lacks independently verified truth.

## Duplicate/collision audit
No second task-state engine created. Existing DurableExecution remains lifecycle owner; RuntimeStore remains persistence owner; epistemics remains outcome semantics owner.

## Execution
COMPLETED_UNKNOWN = COMPLETED / UNKNOWN / UNKNOWN
COMPLETED_SUCCESS = COMPLETED / SUCCESS / SUCCESS
FAILED = FAILED / FAILURE / FAILURE
PERSISTED = COMPLETED / UNKNOWN / UNKNOWN

Reproduction SHA-256:
CE4707CB1764BA490D4B80DB66563A31F55A61E3499BA09C929B7432D3DA1D57

## Tests
- P1-A/P1-B/P1-C targeted: 16 passed
- Full regression: 170 passed in 7.99s
- diff check: PASS with CRLF-aware whitespace

## Artifact hashes
store.py: 91F716A90F56D9968ED89AB548AD36A174B455679BC64CEA3D6B32B6C3CEF6FE
durable_execution.py: 689761157C98127B871F0E60D3DA5E22D653CE8D76BF340FA37F2F6C48F27554
epistemics.py: 7107FECA13755115B88396EE7A8495F6A0C8BA3F69EF1AC1428DE252F2AE27D4

## Gate decision
P1-C = ENFORCED / CLOSED.
