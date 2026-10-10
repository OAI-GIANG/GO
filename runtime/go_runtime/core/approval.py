"""Destructive-operation approval contract.

Approval is *evidence*, not a flag. A plain string such as "approved" is NEVER
accepted as approval evidence. Transport over HTTP must carry a JSON object that
is strictly validated (see ``ApprovalEvidence.from_json``). Production trust is
fail-closed until a trusted approval issuer is provisioned outside the runtime
package (``TRUSTED_APPROVAL_ISSUERS``).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Fields that MUST be present and be non-empty strings in an approval payload.
_STRING_FIELDS = (
    "approval_id", "approver_id", "subject", "tool_name", "arguments_digest",
    "policy_sha256", "scope", "expires_at", "nonce", "signature", "issuer_id",
)
# Optional string fields (may be empty).
_OPTIONAL_STRING_FIELDS = ("target",)


@dataclass(frozen=True)
class ApprovalEvidence:
    approval_id: str
    approver_id: str
    subject: str
    tool_name: str
    arguments_digest: str
    policy_sha256: str
    scope: str
    expires_at: str
    nonce: str
    signature: str
    issuer_id: str
    target: str = ""

    @classmethod
    def from_json(cls, value: Any) -> "ApprovalEvidence":
        """Strictly deserialize and validate a JSON approval object (fail-closed).

        Rejects: non-objects, unknown fields, missing fields, and non-string or
        empty-string fields. It validates *shape* only; cryptographic and binding
        verification is done by ``verify_approval`` under a trusted issuer.
        """
        if not isinstance(value, dict):
            raise ValueError("approval must be a JSON object")
        allowed = set(_STRING_FIELDS) | set(_OPTIONAL_STRING_FIELDS)
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise ValueError("approval has unknown fields: %s" % unknown)
        missing = [f for f in _STRING_FIELDS if f not in value]
        if missing:
            raise ValueError("approval missing fields: %s" % missing)
        for f in _STRING_FIELDS:
            v = value[f]
            if not isinstance(v, str) or not v.strip():
                raise ValueError("approval.%s must be a non-empty string" % f)
        target = value.get("target", "")
        if not isinstance(target, str):
            raise ValueError("approval.target must be a string")
        return cls(**{f: value[f] for f in _STRING_FIELDS}, target=target)

    def to_dict(self) -> dict[str, Any]:
        return {f: getattr(self, f) for f in _STRING_FIELDS + _OPTIONAL_STRING_FIELDS}


# Populated only by trusted bootstrap code outside the runtime package.
TRUSTED_APPROVAL_ISSUERS: tuple[Any, ...] = ()


def verify_approval(value: Any, *, subject: str, tool_name: str, arguments_digest: str,
                    policy_sha256: str, scope: str, target: str | None = None,
                    now_epoch: float | None = None) -> tuple[bool, str]:
    """Issuer-verified, fully bound approval check. Fail-closed.

    Only an object of type ``ApprovalEvidence`` can pass; strings/flags are rejected
    with ``APPROVAL_EVIDENCE_REQUIRED``. When no trusted issuer is provisioned the
    result is ``TRUSTED_APPROVAL_ISSUER_NOT_PROVISIONED``.
    """
    if not isinstance(value, ApprovalEvidence):
        return False, "APPROVAL_EVIDENCE_REQUIRED"
    issuer = next((x for x in TRUSTED_APPROVAL_ISSUERS if getattr(x, "issuer_id", None) == value.issuer_id), None)
    if issuer is None:
        return False, "TRUSTED_APPROVAL_ISSUER_NOT_PROVISIONED"
    try:
        result = issuer.verify(value)
    except Exception:
        return False, "APPROVAL_SIGNATURE_INVALID"
    if result is not True:
        return False, "APPROVAL_SIGNATURE_INVALID"
    if (value.subject != subject or value.tool_name != tool_name or value.arguments_digest != arguments_digest
        or value.policy_sha256 != policy_sha256 or value.scope != scope):
        return False, "APPROVAL_BINDING_MISMATCH"
    if target is not None and value.target != target:
        return False, "APPROVAL_TARGET_MISMATCH"
    import datetime
    try:
        expiry = datetime.datetime.fromisoformat(value.expires_at.replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return False, "APPROVAL_EXPIRY_INVALID"
    if expiry <= (now_epoch if now_epoch is not None else datetime.datetime.now(datetime.timezone.utc).timestamp()):
        return False, "APPROVAL_EXPIRED"
    if not value.approval_id or not value.approver_id or not value.nonce:
        return False, "APPROVAL_FIELDS_MISSING"
    return True, "APPROVAL_VALID"
