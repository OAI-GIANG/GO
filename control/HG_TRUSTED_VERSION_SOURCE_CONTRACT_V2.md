# HG Trusted Version Source Contract V2

Status: DESIGN-CLOSED / IMPLEMENTATION-FROZEN-PENDING
Base canonical commit: 4346afdb775e68e7f1499896920a894b8a6e6878

## 1. Purpose
TVS establishes source/version trust for the GO runtime without allowing the runtime to make its own source claim authoritative.
TVS is a source-trust gate only. It MUST NOT authorize execution.

## 2. Resolved trust-anchor contradiction
V1 is rejected because a manifest stored inside the Git tree cannot simultaneously contain the exact commit/tree identity of the same tree as its independent trust anchor.
V2 MUST NOT place the trust anchor inside the snapshot being verified.
The canonical trust object is a cryptographically signed OpenPGP annotated Git tag. The tag object is outside the commit's tree and points to an immutable commit object.
The signature key is the TVS root of trust and MUST be pinned/provisioned outside the GO source tree.

## 3. Authority model
1. TVS Root Key: external trust anchor; public key/fingerprint provisioned outside GO; private key never enters repository/runtime.
2. Signed OpenPGP TVS Tag: annotated, cryptographically signed Git tag pointing directly to the intended GO commit. Tag name is a locator, not authority.
3. GO Commit: immutable Git commit referenced by the signed tag; tree SHA is derived independently.
4. GO Runtime: verifier only; self-report is observation, never source trust.
5. VPS2 Bridge: execution authorization only; VPS2 ALLOW never implies TVS verification.

## 4. Canonical TVS identity
TVS_ID = SHA-256(canonical(repository, commit_sha, tree_sha, runtime_version))
Canonicalization: UTF-8, LF, deterministic key ordering, deterministic separators, no BOM, no insignificant whitespace.
runtime_version is carried in the signed tag payload and is not inferred from a mutable branch/tag name.

## 5. Signed tag payload
The signed annotated tag message MUST contain canonical JSON:
{
  "schema": "HG_TRUSTED_VERSION_SOURCE_V2",
  "repository": "OAI-GIANG/GO",
  "commit_sha": "<FULL_COMMIT_SHA>",
  "tree_sha": "<EXACT_TREE_SHA>",
  "runtime_version": "<EXPLICIT_RUNTIME_VERSION>",
  "tvs_id": "<SHA256_SOURCE_IDENTITY>"
}
Verifier MUST verify signature, signer against pinned root, tag target, commit tree, repository identity, and recomputed TVS_ID. Malformed/duplicate/conflicting fields MUST be rejected.

## 6. No mutable reference trust
MUST NOT accept branch name, lightweight tag, deployment label, GO_COMMIT, GO_TREE_SHA, runtime self-attestation, or VPS2 authorization as TVS trust.

## 7. Runtime attestation
After TVS verification, evidence MAY bind the verified TVS_ID to observed runtime commit/tree/version/worktree/process/endpoint/protocol/environment. Observed runtime identity MUST match verified source identity before trusted workload execution is reported successful.

## 8. Mandatory failure behavior
Any missing/unsigned/invalid tag, unknown signer, signer mismatch, repository mismatch, tag-target mismatch, commit/tree/version/TVS_ID mismatch, malformed payload, or unavailable trust root MUST BLOCK with no fallback.

Reason codes:
BLOCKED_TVS_UNAVAILABLE
BLOCKED_TVS_SIGNATURE_INVALID
BLOCKED_TVS_SIGNER_UNTRUSTED
BLOCKED_TVS_NON_ANNOTATED_TAG
BLOCKED_TVS_REPOSITORY_MISMATCH
BLOCKED_VERSION_MISMATCH
BLOCKED_TREE_MISMATCH
BLOCKED_RUNTIME_VERSION_MISMATCH
BLOCKED_TVS_ID_MISMATCH
BLOCKED_TVS_PAYLOAD_INVALID
BLOCKED_TVS_ROOT_UNAVAILABLE
BLOCKED_RUNTIME_ATTESTATION_UNVERIFIED

## 9. Authority separation
TVS verification MUST complete before trusted workload execution.
TVS MUST NOT depend on VPS2 execution authorization.
VPS2 MUST NOT establish TVS trust.
Evidence MUST distinguish source trust, runtime observation, execution authorization, and execution result.

## 10. Threat boundary
The TVS root public key/fingerprint is provisioned by a trusted deployment/control plane outside GO.
Compromise of that external trust root is a root-of-trust compromise.
Key rotation requires explicit trust-root authorization and MUST NOT be performed by the runtime.

## 11. Closure
Positive closure requires valid signed annotated tag, trusted signer, exact commit/tree, signed runtime version, matching TVS_ID, matching runtime observation, and evidence bound to TVS_ID.

