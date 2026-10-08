# GO Runtime — Objective Router + Failure Policy (canonical capability)

CAPABILITY_ID: HG-CAP-OBJECTIVE-ROUTER-V1
STATUS: canonical
OWNER_MODULE: `runtime/go_runtime/core/engine/objective_router.py`
ENTRY POINT: operation `objective.run` (runtime `submit`) -> `ToolRegistry -> ToolGovernance -> CredentialBroker -> DurableExecution -> execute -> observe -> classify -> bounded recovery -> evidence`
REUSES (no duplicate control plane): ToolRegistry, ToolGovernance, CredentialBroker, DurableExecution, RuntimeStore, Kernel. No second registry/governance/executor/recovery engine.

## Purpose
Enter the runtime from an OBJECTIVE (never a tool name), discover capabilities from the live registry, select a bounded action, execute under governance, classify failures, recover within budget, and return an evidence-bearing result — deterministically and without any model.

## Flow
normalize -> understand (verbs/nouns/entities) -> discover(ToolRegistry) -> filter -> bounded select
-> (orchestrator) govern -> broker -> durable execute -> observe -> classify failure -> bounded recovery/replan -> final result.

## Invariants (tested)
1. **Model-independent** — no model, no network, no subprocess, no hidden state (AST-enforced).
2. **No preselected capability** — the caller supplies only an objective; selection is a policy over the discovered catalogue (never one fixed tool).
3. **Bounded** — ≤3 plan steps, ≤1 retry, ≤1 replan per step; retries use attempt-scoped step identity.
4. **Fail-closed** — unknown -> `NO_MATCH`, ambiguous -> `AMBIGUOUS`, forbidden -> `UNAUTHORIZED` (no execution).
5. **No authority creation / no bypass** — every step is executed by the caller through ToolGovernance + CredentialBroker; the router never executes anything itself.
6. **Objective preserved** — replans keep the original objective, task identity and evidence chain.

## Failure taxonomy
AUTHORIZATION_FAILURE, CREDENTIAL_FAILURE, ARGUMENT_FAILURE, CAPABILITY_UNAVAILABLE, TRANSIENT_FAILURE,
TARGET_UNAVAILABLE, POLICY_BLOCK, TIMEOUT, IDEMPOTENCY_DUPLICATE, NON_RECOVERABLE, UNKNOWN.
Recovery policy: TRANSIENT -> bounded retry; TARGET_UNAVAILABLE/CAPABILITY_UNAVAILABLE -> bounded replan; all others terminal.

## Operation classification (governance)
READ_ONLY / MUTATING / DESTRUCTIVE derived from tool semantics. `github.delete_branch` and `github.update_branch` are DESTRUCTIVE and require the canonical approval path (`approval=approved`); otherwise DENIED (`APPROVAL_REQUIRED`).

## Provider honesty
`ask`/model objectives route through the canonical ModelGateway only. With no reasoning provider configured the loop returns explicit `CAPABILITY_UNAVAILABLE: MODEL_PROVIDER_UNAVAILABLE` — success is never fabricated.

## Provenance
SOURCE_CLASS: objective-driven autonomy procedure
DESTINATION: `runtime/go_runtime/core/engine/objective_router.py` + `objective.run`
TRANSFORMATION: distilled to bounded pure policy; deduplicated against existing HG subsystems
TESTS: `tests/test_objective_router.py` (13 cases: discovery, selection, composite, fail-closed, taxonomy, bounded retry/replan, refusal-without-execute, no-network/model)
