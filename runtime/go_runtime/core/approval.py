"""Destructive-operation approval contract. Production trust is fail-closed until an issuer is provisioned."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

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

# Populated only by trusted bootstrap code outside the runtime package.
TRUSTED_APPROVAL_ISSUERS: tuple[Any, ...] = ()

def verify_approval(value: Any, *, subject: str, tool_name: str, arguments_digest: str,
                    policy_sha256: str, scope: str, now_epoch: float | None = None) -> tuple[bool, str]:
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
