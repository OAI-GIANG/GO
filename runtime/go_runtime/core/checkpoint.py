"""HG-GCI V1 checkpoint contracts and deterministic serialization."""
from __future__ import annotations
from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime, time
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Mapping

SCHEMA_NAME="HG_MODEL_CONTEXT_INDEPENDENCE_CHECKPOINT"
SCHEMA_VERSION="1.0"
HASH_ALGORITHM="SHA-256"

def _primitive(v: Any)->Any:
    if is_dataclass(v): return {k:_primitive(x) for k,x in asdict(v).items()}
    if isinstance(v,Enum): return v.value
    if isinstance(v,Mapping): return {str(k):_primitive(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)): return [_primitive(x) for x in v]
    if isinstance(v,(set,frozenset)): return sorted((_primitive(x) for x in v),key=lambda x:canonical_json(x))
    if isinstance(v,(datetime,date,time)): return v.isoformat()
    return v

def canonical_json(value:Any)->str:
    return json.dumps(_primitive(value),ensure_ascii=False,sort_keys=True,separators=(",",":"))

def sha256_canonical(value:Any)->str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()

@dataclass(frozen=True)
class CheckpointSchema: name:str=SCHEMA_NAME; version:str=SCHEMA_VERSION
@dataclass(frozen=True)
class CheckpointIdentity: checkpoint_id:str; task_id:str; checkpoint_revision:int
@dataclass(frozen=True)
class RepositoryWitness:
    remote:str=""; branch:str=""; canonical_head:str=""; observed_head:str=""; observed_tree:str=""
    local_dirty:bool|None=None; provenance_status:str="UNVERIFIED"; witness_mode:str="REMOTE_RUNTIME"
@dataclass(frozen=True)
class ContractBinding:
    contract_name:str; contract_version:str; contract_hash:str; contract_status:str="VALID"
@dataclass(frozen=True)
class AcceptanceCriterion:
    id:str; statement:str; status:str="UNTESTED"
@dataclass(frozen=True)
class AcceptanceSnapshot:
    criteria:tuple[AcceptanceCriterion,...]=(); aggregate_status:str="UNTESTED"
@dataclass(frozen=True)
class EvidenceReference:
    evidence_id:str; evidence_digest:str; verification_status:str
@dataclass(frozen=True)
class EvidenceManifest:
    refs:tuple[EvidenceReference,...]=(); manifest_digest:str=""
@dataclass(frozen=True)
class Blocker:
    blocker_id:str; code:str; description:str; blocking:bool=True; unblock_condition:str=""
@dataclass(frozen=True)
class NextAction:
    action_id:str; action_type:str; instruction:str; prerequisites:tuple[str,...]=(); deterministic:bool=True
@dataclass(frozen=True)
class ResumeState:
    eligible:bool; reason_code:str=""; required_context_refs:tuple[str,...]=(); model_context_required:bool=False

@dataclass(frozen=True)
class Checkpoint:
    identity:CheckpointIdentity
    schema:CheckpointSchema
    created_at:str
    source_runtime:str
    repository:RepositoryWitness
    contract:ContractBinding
    goal:str
    operation:str
    execution_mode:str
    lifecycle_state:str
    runtime_revision:int
    attempt_no:int
    run_id:str|None
    attempt_id:str|None
    phase:str
    acceptance:AcceptanceSnapshot
    evidence:EvidenceManifest
    blockers:tuple[Blocker,...]
    next_action:NextAction
    resume:ResumeState
    replay_sequence:int=0
    replay_digest:str=""
    canonical_payload_hash:str=""
    integrity_algorithm:str=HASH_ALGORITHM
    def payload_without_integrity(self)->dict[str,Any]:
        p=_primitive(self)
        for k in ("canonical_payload_hash","integrity_algorithm","replay_sequence","replay_digest"): p.pop(k,None)
        return p
    def computed_hash(self)->str: return sha256_canonical(self.payload_without_integrity())
    def to_dict(self)->dict[str,Any]:
        p=_primitive(self); p["evidence"]["refs"]=sorted(p["evidence"]["refs"],key=lambda x:x["evidence_id"]); return p
    def validated(self)->"Checkpoint":
        if self.schema.name!=SCHEMA_NAME or self.schema.version!=SCHEMA_VERSION: raise ValueError("checkpoint_schema_unsupported")
        if self.identity.checkpoint_revision<1: raise ValueError("checkpoint_revision_invalid")
        if not self.contract.contract_hash: raise ValueError("contract_hash_required")
        if not self.next_action.instruction.strip() or self.next_action.deterministic is not True: raise ValueError("next_action_nondeterministic")
        refs=sorted((_primitive(x) for x in self.evidence.refs),key=lambda x:x["evidence_id"])
        if self.evidence.manifest_digest!=sha256_canonical(refs): raise ValueError("evidence_manifest_mismatch")
        unified=unify_evidence_refs(self.evidence.refs)
        if unified["duplicate_representations"]: raise ValueError("evidence_duplicate_representations")
        if unified["conflicts"]: raise ValueError("evidence_conflict")
        return self

def canonical_contract_hash(contract_payload:Any)->str: return sha256_canonical(contract_payload)
def canonical_evidence_manifest(refs:Any)->tuple[list[dict[str,Any]],str]:
    p=sorted((_primitive(x) for x in refs),key=lambda x:x["evidence_id"]); return p,sha256_canonical(p)


def unify_evidence_refs(refs: Any) -> dict[str, Any]:
    from .evidence import from_checkpoint_ref, unify
    return unify([from_checkpoint_ref(_primitive(ref)) for ref in refs])
def canonical_checkpoint_payload(checkpoint:Checkpoint)->str: return canonical_json(checkpoint.payload_without_integrity())
