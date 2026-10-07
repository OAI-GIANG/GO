from __future__ import annotations
import hashlib, json, os, re, subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

class TVSVerificationError(RuntimeError):
    def __init__(self, reason_code: str, message: str):
        super().__init__(message); self.reason_code = reason_code

@dataclass(frozen=True)
class TVSIdentity:
    repository: str
    commit_sha: str
    tree_sha: str
    runtime_version: str
    tvs_id: str

@dataclass(frozen=True)
class TVSVerification:
    status: str
    identity: TVSIdentity | None
    signer_fingerprint: str | None
    tag_name: str | None
    reason_code: str | None
    message: str

_PAYLOAD_KEYS = ("schema","repository","commit_sha","tree_sha","runtime_version","tvs_id")
_HEX40 = re.compile(r"^[0-9a-fA-F]{40}$")
_HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")

def canonical_identity(repository: str, commit_sha: str, tree_sha: str, runtime_version: str) -> bytes:
    return json.dumps({"repository":repository,"commit_sha":commit_sha,"runtime_version":runtime_version,"tree_sha":tree_sha},
                      ensure_ascii=False, sort_keys=True, separators=(",",":")).encode("utf-8")

def compute_tvs_id(repository: str, commit_sha: str, tree_sha: str, runtime_version: str) -> str:
    return hashlib.sha256(canonical_identity(repository,commit_sha,tree_sha,runtime_version)).hexdigest()

def _git(repo: Path, *args: str, check: bool=True, raw_status: bool=False) -> str:
    try:
        p=subprocess.run(["git","-C",str(repo),*args],capture_output=True,text=True,encoding="utf-8",errors="replace")
    except OSError as exc:
        raise TVSVerificationError("BLOCKED_TVS_UNAVAILABLE",f"git unavailable: {exc}") from exc
    if check and p.returncode:
        raise TVSVerificationError("BLOCKED_TVS_UNAVAILABLE",(p.stderr or p.stdout).strip() or "git command failed")
    return p.stdout + p.stderr if raw_status else p.stdout

def _annotated_tag(repo: Path, tag: str) -> str:
    typ=_git(repo,"cat-file","-t",f"refs/tags/{tag}").strip()
    if typ!="tag": raise TVSVerificationError("BLOCKED_TVS_NON_ANNOTATED_TAG",f"{tag!r} is not an annotated tag")
    return _git(repo,"rev-parse",f"refs/tags/{tag}").strip()

def _signature(repo: Path, tag: str) -> str:
    raw=_git(repo,"verify-tag","--raw",tag,check=False,raw_status=True)
    if "[GNUPG:] GOODSIG " not in raw or "[GNUPG:] VALIDSIG " not in raw:
        raise TVSVerificationError("BLOCKED_TVS_SIGNATURE_INVALID","tag signature is not valid")
    m=re.search(r"\[GNUPG:\] VALIDSIG ([0-9A-Fa-f]{40})",raw)
    if not m: raise TVSVerificationError("BLOCKED_TVS_SIGNATURE_INVALID","signer fingerprint unavailable")
    return m.group(1).upper()

def _payload(repo: Path, tag: str) -> dict[str,Any]:
    raw=_git(repo,"cat-file","-p",f"refs/tags/{tag}")
    if "-----BEGIN PGP SIGNATURE-----" not in raw:
        raise TVSVerificationError("BLOCKED_TVS_SIGNATURE_INVALID","annotated tag is unsigned")
    pre=raw.split("-----BEGIN PGP SIGNATURE-----",1)[0]
    lines=pre.splitlines()
    try: i=next(i for i,x in enumerate(lines) if x=="")
    except StopIteration as exc: raise TVSVerificationError("BLOCKED_TVS_PAYLOAD_INVALID","missing tag message") from exc
    try: obj=json.loads("\n".join(lines[i+1:]).strip())
    except json.JSONDecodeError as exc: raise TVSVerificationError("BLOCKED_TVS_PAYLOAD_INVALID",str(exc)) from exc
    if not isinstance(obj,dict) or set(obj)!=set(_PAYLOAD_KEYS):
        raise TVSVerificationError("BLOCKED_TVS_PAYLOAD_INVALID","signed payload keys are not exact")
    if obj.get("schema")!="HG_TRUSTED_VERSION_SOURCE_V2":
        raise TVSVerificationError("BLOCKED_TVS_PAYLOAD_INVALID","wrong TVS schema")
    return obj

def verify_tvs(repo: str|Path, *, repository:str, commit_sha:str, tree_sha:str, runtime_version:str,
               tag_name:str, trusted_fingerprint:str) -> TVSVerification:
    repo=Path(repo).resolve()
    try:
        tag_obj=_annotated_tag(repo,tag_name)
        signer=_signature(repo,tag_name)
        if signer != trusted_fingerprint.replace(" ","").upper():
            raise TVSVerificationError("BLOCKED_TVS_SIGNER_UNTRUSTED","signer does not match pinned root")
        p=_payload(repo,tag_name)
        actual=_git(repo,"rev-list","-n","1",f"refs/tags/{tag_name}").strip()
        if actual!=p["commit_sha"]: raise TVSVerificationError("BLOCKED_VERSION_MISMATCH","tag target differs from signed commit")
        if p["repository"]!=repository: raise TVSVerificationError("BLOCKED_TVS_REPOSITORY_MISMATCH","repository mismatch")
        if not _HEX40.fullmatch(str(p["commit_sha"])) or not _HEX40.fullmatch(str(p["tree_sha"])):
            raise TVSVerificationError("BLOCKED_TVS_PAYLOAD_INVALID","invalid commit/tree SHA")
        derived=_git(repo,"rev-parse",f"{p['commit_sha']}^{{tree}}").strip()
        if derived!=p["tree_sha"]: raise TVSVerificationError("BLOCKED_TREE_MISMATCH","signed tree differs from commit tree")
        if p["commit_sha"]!=commit_sha: raise TVSVerificationError("BLOCKED_VERSION_MISMATCH","runtime commit differs")
        if p["tree_sha"]!=tree_sha: raise TVSVerificationError("BLOCKED_TREE_MISMATCH","runtime tree differs")
        if p["runtime_version"]!=runtime_version: raise TVSVerificationError("BLOCKED_RUNTIME_VERSION_MISMATCH","runtime version differs")
        tvs=compute_tvs_id(p["repository"],p["commit_sha"],p["tree_sha"],p["runtime_version"])
        if not _HEX64.fullmatch(str(p["tvs_id"])) or p["tvs_id"]!=tvs:
            raise TVSVerificationError("BLOCKED_TVS_ID_MISMATCH","TVS_ID mismatch")
        return TVSVerification("VERIFIED",TVSIdentity(p["repository"],p["commit_sha"],p["tree_sha"],p["runtime_version"],p["tvs_id"]),
                               signer,tag_name,None,f"verified tag object {tag_obj}")
    except TVSVerificationError as exc:
        return TVSVerification("BLOCKED",None,None,tag_name,exc.reason_code,str(exc))

def verify_from_environment(repo: str|Path, *, commit_sha:str, tree_sha:str, runtime_version:str) -> TVSVerification:
    tag=os.getenv("HG_TVS_TAG","").strip(); root=os.getenv("HG_TVS_ROOT_FINGERPRINT","").strip()
    repository=os.getenv("HG_TVS_REPOSITORY","OAI-GIANG/GO").strip()
    if not tag: return TVSVerification("BLOCKED",None,None,None,"BLOCKED_TVS_UNAVAILABLE","HG_TVS_TAG is not configured")
    if not root: return TVSVerification("BLOCKED",None,None,tag,"BLOCKED_TVS_ROOT_UNAVAILABLE","HG_TVS_ROOT_FINGERPRINT is not configured")
    return verify_tvs(repo,repository=repository,commit_sha=commit_sha,tree_sha=tree_sha,runtime_version=runtime_version,
                      tag_name=tag,trusted_fingerprint=root)


