"""HG V2 canonical authority root (single semantic owner).

ONE issuer. Runtime components are authority *consumers* only: they must obtain a
signed AuthorityToken and present it; they must never mint authority ad-hoc.

Invariants:
  - authority_root_count = 1 (this module holds the only issuing key)
  - runtime_self_authority = 0 (issuance is policy-gated, no free authority)
  - credential != authority (a credential is an input to the root, not the root)
  - delegation cannot widen scope nor outlive its parent
  - revocation is authoritative; revoked/expired/wrong-audience tokens fail closed
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
import uuid
from dataclasses import dataclass
from typing import Any, Iterable

AUTHORITY_ROOT_ID = "HG_AUTHORITY_ROOT_V2"


class AuthorityError(Exception):
    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(message or code)


@dataclass(frozen=True)
class AuthorityToken:
    token_id: str
    subject: str
    scope: frozenset[str]
    action: str
    audience: str
    issued_at: float
    expires_at: float
    nonce: str
    parent: str | None
    sig: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "token_id": self.token_id, "subject": self.subject, "scope": sorted(self.scope),
            "action": self.action, "audience": self.audience, "issued_at": self.issued_at,
            "expires_at": self.expires_at, "nonce": self.nonce, "parent": self.parent, "sig": self.sig,
        }


class AuthorityRoot:
    """The only component permitted to issue authority."""

    _instance: "AuthorityRoot | None" = None
    _lock = threading.RLock()

    def __init__(self, secret: bytes | None = None) -> None:
        self._secret = secret or os.urandom(32)
        self._provenance = "EXPLICIT" if secret else "EPHEMERAL"
        self._revoked: set[str] = set()
        self._issued: list[dict[str, Any]] = []

    @classmethod
    def instance(cls) -> "AuthorityRoot":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls._load()
            return cls._instance

    @classmethod
    def _load(cls) -> "AuthorityRoot":
        """A durable root key must be provisioned EXTERNALLY (owned by another
        principal). If absent, the process only holds an EPHEMERAL key and MUST
        NOT be treated as an external authority root."""
        path = os.getenv("HG_AUTHORITY_ROOT_KEY_FILE", "/etc/hg/authority/root.key")
        try:
            secret = open(path, "rb").read().strip()
            if secret:
                root = cls(secret)
                root._provenance = "EXTERNAL_FILE"
                return root
        except OSError:
            pass
        root = cls()
        root._provenance = "SELF_PROVISIONED"
        return root

    def provenance(self) -> str:
        return getattr(self, "_provenance", "SELF_PROVISIONED")

    def is_external(self) -> bool:
        return self.provenance() == "EXTERNAL_FILE"

    # ---- internal signature ----
    def _payload(self, t: AuthorityToken) -> bytes:
        return json.dumps(
            {"token_id": t.token_id, "subject": t.subject, "scope": sorted(t.scope), "action": t.action,
             "audience": t.audience, "issued_at": t.issued_at, "expires_at": t.expires_at,
             "nonce": t.nonce, "parent": t.parent},
            sort_keys=True, separators=(",", ":"),
        ).encode()

    def _sign(self, t: AuthorityToken) -> str:
        return hmac.new(self._secret, self._payload(t), hashlib.sha256).hexdigest()

    def _mint(self, *, subject: str, scope: Iterable[str], action: str, audience: str, ttl_s: float, parent: str | None) -> AuthorityToken:
        now = os.environ.get("HG_AUTHORITY_NOW")
        issued = float(now) if now else __import__("time").time()
        t = AuthorityToken(
            token_id="AUTH-" + uuid.uuid4().hex, subject=str(subject),
            scope=frozenset(str(s) for s in scope), action=str(action), audience=str(audience),
            issued_at=issued, expires_at=issued + float(ttl_s), nonce=uuid.uuid4().hex, parent=parent, sig="",
        )
        t = AuthorityToken(**{**t.__dict__, "sig": self._sign(t)})
        self._issued.append(t.to_dict())
        return t

    # ---- public issuance (policy-gated) ----
    def issue(self, *, subject: str, scope: Iterable[str], action: str, audience: str, ttl_s: float = 300.0) -> AuthorityToken:
        if not subject or not audience or ttl_s <= 0 or ttl_s > 3600:
            raise AuthorityError("AUTHORITY_ISSUE_POLICY_VIOLATION")
        return self._mint(subject=subject, scope=scope, action=action, audience=audience, ttl_s=ttl_s, parent=None)

    def delegate(self, parent: AuthorityToken, *, subject: str, scope: Iterable[str], action: str, audience: str, ttl_s: float) -> AuthorityToken:
        """ROOT -> DELEGATION -> EXECUTOR. Child scope must be a subset of parent
        scope; child expiry must not exceed parent; action/audience must be covered."""
        if not self.verify(parent, action=parent.action, scope=parent.scope, audience=parent.audience):
            raise AuthorityError("DELEGATION_PARENT_INVALID")
        child = frozenset(str(s) for s in scope)
        if not child.issubset(parent.scope):
            raise AuthorityError("DELEGATION_WIDENING_DENIED")
        if action != parent.action or audience != parent.audience:
            raise AuthorityError("DELEGATION_SCOPE_DENIED")
        if parent.expires_at - parent.issued_at is not None and ttl_s > (parent.expires_at - __import__("time").time()):
            raise AuthorityError("DELEGATION_EXPIRY_WIDENING_DENIED")
        return self._mint(subject=subject, scope=child, action=action, audience=audience, ttl_s=ttl_s, parent=parent.token_id)

    def revoke(self, token_id: str) -> None:
        self._revoked.add(str(token_id))

    def is_revoked(self, token_id: str) -> bool:
        return str(token_id) in self._revoked

    def verify(self, token: AuthorityToken, *, action: str, scope: Iterable[str], audience: str, now: float | None = None) -> bool:
        if token is None or token.sig != self._sign(token):
            return False
        if self.is_revoked(token.token_id):
            return False
        if token.parent and self.is_revoked(token.parent):
            return False
        t = float(now) if now is not None else __import__("time").time()
        env_now = os.environ.get("HG_AUTHORITY_NOW")
        if env_now:
            t = float(env_now)
        if not (token.issued_at <= t < token.expires_at):
            return False
        if token.action != action:
            return False
        if token.audience != audience:
            return False
        if not frozenset(str(s) for s in scope).issubset(token.scope):
            return False
        return True


def require_authority(token: AuthorityToken | None, *, subject: str, action: str, scope: Iterable[str], audience: str) -> None:
    """Fail-closed gate for consumers. A missing/invalid token is a hard denial.

    A raw credential (string) is NOT authority (GI-06)."""
    root = AuthorityRoot.instance()
    if not isinstance(token, AuthorityToken) or token.subject != subject:
        raise AuthorityError("AUTHORITY_REQUIRED")
    if not root.verify(token, action=action, scope=scope, audience=audience):
        raise AuthorityError("AUTHORITY_DENIED")
