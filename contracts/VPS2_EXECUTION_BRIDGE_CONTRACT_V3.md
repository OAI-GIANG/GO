# VPS2 Execution Bridge Contract V3

Status: CANONICALIZED_BY_AUTHORIZATION
Version: DESIGN_HARDENED_V3
Authority: User authorization in ChatGPT session on 2026-10-07
Historical recovery: FALSE
Implementation binding: artifact SHA recorded in provenance

## 1. Purpose

This contract defines the HG -> VPS2 execution authorization boundary. HG may request an opaque operation identity and typed variables. HG MUST NOT submit shell commands or arbitrary command arguments.

The bridge is the Policy Decision Point (PDP) and authorization authority. The executor is the Policy Enforcement Point (PEP). No execution may begin without an explicit ALLOW decision bound to all required authorization dimensions.

## 2. Mandatory bind keys

Every authorization request MUST bind exactly these security-relevant dimensions:

- target_id
- operation_id
- allowlist_version
- policy_version

Missing, malformed, or mismatched values MUST result in REJECT.

## 3. Opaque operation identity

Requests contain operation_id plus typed variables only.

The bridge resolves operation_id against an immutable operation registry. The registry entry supplies the immutable execution template and variable schema.

Unknown operation_id MUST be rejected. No fallback, inference, shell passthrough, dynamic command construction, or alternate operation resolution is permitted.

## 4. Read-only guarantee

V3 permits only operations explicitly registered as read_only=true.

A template that is not explicitly read-only is ineligible for execution.

The bridge MUST reject an operation when its resolved template is absent, mutable, unregistered, or not read-only.

## 5. Authorization state machine

RECEIVED
-> VALIDATED
-> AUTHORIZATION_PENDING
-> ALLOW
-> AUTHORIZED
-> EXECUTING
-> EVIDENCE_EMITTED
-> CLOSED

Any validation or authorization failure terminates in REJECTED.

EXECUTING is reachable only from AUTHORIZED after an immutable ALLOW decision has been recorded.

## 6. Authorization decision record

Exactly one immutable decision record MUST be emitted for each authorization attempt.

Required fields:

- decision_id
- request_id
- target_id
- operation_id
- allowlist_version
- policy_version
- decision
- reason_code
- template_hash
- registry_version
- timestamp

An ALLOW decision is valid only when all bind keys match the resolved request and registry.

## 7. Evidence

A successful execution MUST emit evidence containing:

- request_id
- target_id
- operation_id
- template_hash
- allowlist_version
- policy_version
- authorization decision id
- readonly_attestation
- execution result/status
- timestamps

A rejected request MUST emit rejection evidence containing reason_code. It MUST NOT emit EXECUTING.

## 8. Negative controls

AC-N09: opaque operation identity — arbitrary command/args are rejected.

AC-N10: immutable template resolution — registry/template mutation after registration is rejected or impossible.

AC-N11: read-only forensic guarantee — non-read-only templates cannot execute.

AC-N12: target-operation mismatch — REJECT.

AC-N13: allowlist version mismatch — REJECT.

AC-N14: policy version mismatch — REJECT.

Additional invariant: no valid ALLOW means no EXECUTING state.

## 9. Trust boundary

HG is a requester, not an execution authority.

VPS2 bridge is the authorization authority.

The executor receives only a resolved immutable template and validated typed variables after authorization.

The bridge MUST NOT accept a raw shell command from HG.

## 10. Deterministic identity

template_hash is the SHA-256 digest of the canonical serialized immutable template.

Registry/version identifiers are explicit inputs to authorization and evidence.

The implementation MUST NOT silently substitute a different template, allowlist, policy, or target.

## 11. Provenance

This artifact is not claimed as historical recovery. It is a new canonical source created under explicit user authorization after forensic searches found no historical Contract V3 artifact.

The provenance record MUST identify:

- authorization basis
- source artifact blob SHA
- parent/base commit
- canonicalization status
- implementation branch
- resulting implementation commit(s)
