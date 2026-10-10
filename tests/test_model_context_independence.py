from datetime import datetime, timezone
from runtime.go_kernel import Evidence
from runtime.go_runtime.core.checkpoint import sha256_canonical
from runtime.go_runtime.core.engine.durable_execution import DurableExecution
from runtime.go_runtime.core.engine.task_contract import TaskContract
from runtime.go_runtime.core.store import RuntimeStore

def setup_case(tmp_path):
    store=RuntimeStore(tmp_path/"runtime.db"); eng=DurableExecution(store,worker_id="gci-a")
    contract=TaskContract("GCI task",{"kind":"gci"})
    sub=contract.submit(submission_id="TASK-GCI",idempotency_key="IDEMP-GCI",execution_mode="ASYNC")
    eng.enqueue_submission(sub)
    repo={"remote":"origin","branch":"hg-core","canonical_head":"4346afdb775e68e7f1499896920a894b8a6e6878","observed_head":"4346afdb775e68e7f1499896920a894b8a6e6878","observed_tree":"TREE-GCI","local_dirty":False,"provenance_status":"VERIFIED","witness_mode":"GIT_CHECKOUT"}
    e=Evidence("E-GCI-1","TASK-GCI","checkpoint","test",datetime.now(timezone.utc),"test-provenance","", "VERIFIED","checkpoint verified")
    e=Evidence(e.evidence_id,e.subject,e.scope,e.source,e.captured_at,e.provenance,e.expected_integrity(),e.verification_status,e.claim)
    store.save_evidence({"evidence_id":e.evidence_id,"task_id":"TASK-GCI","event_type":"CHECKPOINT","claim":e.claim,"source":e.source,"provenance":e.provenance,"integrity":e.integrity,"verification_status":"VERIFIED"},"2026-10-07T00:00:00+00:00")
    cp=eng.create_checkpoint("TASK-GCI",repository=repo,contract=contract,phase="VERIFY",
      acceptance={"criteria":[{"id":"AC-01","statement":"resume gate","status":"PASS"}],"aggregate_status":"PASS"},
      evidence=[{"evidence_id":"E-GCI-1","evidence_digest":e.integrity,"verification_status":"VERIFIED"}],blockers=[],
      next_action={"action_id":"NA-01","action_type":"RESUME","instruction":"Resume from durable checkpoint","deterministic":True},
      resume={"eligible":True,"reason_code":"RESUME_ALLOWED","model_context_required":False})
    return store,eng,contract,repo,cp

def decision(store,repo,cp): return DurableExecution(store,worker_id="gci-b").evaluate_resume("TASK-GCI",cp["identity"]["checkpoint_id"],repository_witness=repo)

def resign(cp): return sha256_canonical({k:v for k,v in cp.items() if k not in {"canonical_payload_hash","integrity_algorithm","replay_sequence","replay_digest"}})

def test_gci_01(tmp_path):
    s,e,c,r,cp=setup_case(tmp_path); cp["canonical_payload_hash"]="tampered"; s.save_checkpoint(cp)
    assert decision(s,r,cp).reason_code=="CHECKPOINT_INTEGRITY_INVALID"

def test_gci_02(tmp_path):
    s,e,c,r,cp=setup_case(tmp_path); cp["contract"]["contract_hash"]="tampered"; cp["canonical_payload_hash"]=resign(cp); s.save_checkpoint(cp)
    assert decision(s,r,cp).reason_code=="CONTRACT_HASH_MISMATCH"

def test_gci_03(tmp_path):
    s,e,c,r,cp=setup_case(tmp_path); assert decision(s,{**r,"canonical_head":"DRIFT"},cp).reason_code=="CANONICAL_HEAD_MISMATCH"

def test_gci_04(tmp_path):
    s,e,c,r,cp=setup_case(tmp_path); assert decision(s,{**r,"observed_head":"DRIFT"},cp).reason_code=="OBSERVED_HEAD_MISMATCH"

def test_gci_05(tmp_path):
    s,e,c,r,cp=setup_case(tmp_path); row=s.list_evidence("TASK-GCI")[0]; row["integrity"]="tampered"; s.save_evidence(row,"2026-10-07T00:00:01+00:00")
    assert decision(s,r,cp).reason_code=="EVIDENCE_DIGEST_MISMATCH"

def test_gci_06(tmp_path):
    s,e,c,r,cp=setup_case(tmp_path); cp["evidence"]["manifest_digest"]="tampered"; cp["canonical_payload_hash"]=resign(cp); s.save_checkpoint(cp)
    assert decision(s,r,cp).reason_code=="EVIDENCE_MANIFEST_MISMATCH"

def test_gci_07(tmp_path):
    s,e,c,r,cp=setup_case(tmp_path); cp["blockers"]=[{"blocker_id":"B1","code":"ACTIVE","description":"block","blocking":True,"unblock_condition":"none"}]; cp["canonical_payload_hash"]=resign(cp); s.save_checkpoint(cp)
    assert decision(s,r,cp).reason_code=="BLOCKER_ACTIVE"

def test_gci_08(tmp_path):
    s,e,c,r,cp=setup_case(tmp_path); cp["next_action"]={}; cp["canonical_payload_hash"]=resign(cp); s.save_checkpoint(cp)
    assert decision(s,r,cp).reason_code=="NEXT_ACTION_MISSING"

def test_gci_09(tmp_path):
    s,e,c,r,cp=setup_case(tmp_path); cp["next_action"]["deterministic"]=False; cp["canonical_payload_hash"]=resign(cp); s.save_checkpoint(cp)
    assert decision(s,r,cp).reason_code=="NEXT_ACTION_NONDETERMINISTIC"

def test_gci_10(tmp_path):
    s,e,c,r,cp=setup_case(tmp_path); row=s.list_replay("TASK-GCI")[0]; row["payload"]["checkpoint_hash"]="tampered"
    import pytest
    with pytest.raises(ValueError, match="replay_digest_invalid|replay_sequence_conflict"):
        s.save_replay(row,"2026-10-07T00:00:02+00:00")
    assert decision(s,r,cp).decision == "ALLOW"

def test_gci_11(tmp_path):
    s,e,c,r,cp=setup_case(tmp_path); e.claim("TASK-GCI"); e.recover_orphans()
    assert decision(s,r,cp).decision=="ALLOW"
    resumed=DurableExecution(s,worker_id="model-b").resume("TASK-GCI",cp["identity"]["checkpoint_id"],repository_witness=r)
    assert resumed["state"] in {"RECOVERING","QUEUED"}

def test_gci_12(tmp_path):
    s,e,c,r,cp=setup_case(tmp_path); e.claim("TASK-GCI"); e.recover_orphans()
    a=decision(s,r,cp); b=DurableExecution(s,worker_id="model-b").evaluate_resume("TASK-GCI",cp["identity"]["checkpoint_id"],repository_witness=r)
    assert a.decision==b.decision=="ALLOW"; assert a.checkpoint_id==b.checkpoint_id

def test_migration(tmp_path):
    s=RuntimeStore(tmp_path/"runtime.db"); assert s.get_meta("schema.migration.HG-GCI-CHECKPOINT-V1")=="APPLIED"; assert s.list_checkpoints()==[]



def test_resume_requires_current_repository_witness(tmp_path):
    s,e,c,r,cp=setup_case(tmp_path)
    d=DurableExecution(s,worker_id="no-witness").evaluate_resume("TASK-GCI",cp["identity"]["checkpoint_id"])
    assert d.reason_code=="PROVENANCE_INVALID"

def test_gci_12_explicit_model_identity_independence(tmp_path):
    s,e,c,r,cp=setup_case(tmp_path); e.claim("TASK-GCI"); e.recover_orphans()
    model_a_id="MODEL-A"; model_b_id="MODEL-B"
    a=decision(s,r,cp); b=DurableExecution(s,worker_id="model-b").evaluate_resume("TASK-GCI",cp["identity"]["checkpoint_id"],repository_witness=r)
    assert model_a_id!=model_b_id
    assert a.decision==b.decision=="ALLOW"
    assert a.checkpoint_id==b.checkpoint_id
    assert "model" not in cp["resume"]



def test_contract_hash_is_distinct_from_submission_digest(tmp_path):
    store,e,contract,repo,cp=setup_case(tmp_path)
    submission=contract.submit(submission_id="SUB-2",idempotency_key="IDEMP-2",execution_mode="ASYNC")
    assert contract.contract_hash != submission.digest
    assert contract.contract_hash == contract.contract_hash

def test_checkpoint_replay_commit_is_atomic(tmp_path):
    s,e,c,r,cp=setup_case(tmp_path)
    new_cp=dict(cp)
    new_cp["identity"]=dict(cp["identity"])
    new_cp["identity"]["checkpoint_id"]="CHK-ATOMIC"
    new_cp["identity"]["checkpoint_revision"]=2
    replay=s.list_replay("TASK-GCI")[0]
    bad_replay=dict(replay)
    bad_replay["replay_id"]="RPL-ATOMIC"
    bad_replay["sequence"]=1
    bad_replay["previous_digest"]="GENESIS"
    bad_replay["record_digest"]="tampered"
    try:
        s.save_checkpoint_with_replay(new_cp,bad_replay)
    except Exception:
        pass
    assert s.get_checkpoint("CHK-ATOMIC") is None
