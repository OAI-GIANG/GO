# HG AUTHORITY MODEL V1

## Canonical owner
`HG/core` is the canonical owner of the governed operating process, generated runtime, evolution semantics, and HG-owned evidence interpretation.

## Authority layers
1. MASTER GOVERNANCE RULESET V1 — sole governing source.
2. HG Core — canonical implementation and enforcement boundary for V1.
3. Generated Runtime — derived operational state created by the new operating process; no legacy runtime is required.
4. Evidence — verification records bound to the identified source, workspace, generated runtime, and execution.
5. Knowledge — derived or selected information, never authority by itself.
6. Secrets — protected credentials, never authority.

## Required binding
MASTER GOVERNANCE RULESET V1 -> HG CORE -> GENERATED RUNTIME -> EXECUTION EVIDENCE

## Promotion rule
No alternative policy or secondary authority may override V1. Any implementation must be bound to the exact approved V1 source and verified against its hash and required invariants.

## Runtime rule
The new operating process creates its own runtime. No prior runtime is a prerequisite, authority, fallback, or dependency.

## Safety gates
Changes to production services, credentials, network exposure, or remote infrastructure require explicit target identification and a verified execution plan. No action may be claimed complete without post-change evidence.


## V1 runtime binding — implementation status (2026-10-10)

The canonical V1 source is hash-pinned to `cc1a8b171b1c0e194923359b5b8b17ee9e9ff646b33693cc983f2a9984cc21af`. The current implementation binds the following locally accessible execution surfaces to that exact source:

- `core/runtime/hg_runtime.py`: startup and HTTP-request fail-closed checks; health and response headers expose the governing hash; the central model gateway prepends the exact V1 text before subordinate role/task context.
- `core/runtime/go_runtime/core/tool_governance.py` and `tool_runtime.py`: governed and direct registry dispatch verify V1 before tool execution; successful tool witnesses carry the source hash.
- `backend/hg_backend.py`, `edge/edge.py`, and `authority/authority.py`: request handlers verify V1, reject requests with HTTP 503 when the source/binding is invalid, and expose the governing hash in health/evidence/response headers.
- `core/runtime/hg_cap_payload.py`: the optional phone capability payload now requires the exact V1 source and approval binding under the phone user's `~/hg/` directory; it fails closed if either is absent or mismatched.

This status describes code and tests on the connected laptop workspace only. It does not claim that the phone payload was installed on a device, or that VPS1/VPS2 services were deployed/restarted. Those external execution environments must have the same exact source and binding provisioned before their service can start under this contract.
