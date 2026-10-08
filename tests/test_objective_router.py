"""Tests for the HG canonical objective router + failure policy (CL6 capability).

Covers: discovery, bounded selection from an OBJECTIVE (no tool name), fail-closed
(unknown/ambiguous/unauthorized), composite plan, failure taxonomy and bounded
recovery/replan orchestration. Model-independent; no network.
"""
from __future__ import annotations

from runtime.go_runtime.core.engine import objective_router as orx
from runtime.go_runtime.core.tool_runtime import default_tool_registry

CAT = orx.discover(default_tool_registry())


def test_discovery_uses_registry_and_exposes_operation_class():
    names = {c["operation"] for c in CAT}
    assert "github.read_repo" in names and "hg.repo.forensics" in names and "vps2.health" in names
    classes = {c["operation"]: c["operation_class"] for c in CAT}
    assert classes["github.read_repo"] == "READ_ONLY"
    assert classes["github.create_branch"] == "MUTATING"
    assert classes["github.delete_branch"] == "DESTRUCTIVE"
    assert classes["github.update_branch"] == "DESTRUCTIVE"


def _sel(objective):
    r = orx.select(objective, CAT)
    return r


def test_select_read_repository():
    r = _sel("Read the repository metadata for OAI-GIANG/GO.")
    assert r["status"] == "SELECTED" and r["steps"][0]["operation"] == "github.read_repo"
    assert r["steps"][0]["payload"]["repository"] == "OAI-GIANG/GO"


def test_select_forensics():
    r = _sel("Audit the runtime for duplicate control planes.")
    assert r["status"] == "SELECTED" and r["steps"][0]["operation"] == "hg.repo.forensics"


def test_select_health_and_model():
    assert _sel("Check whether the VPS runtime is healthy.")["steps"][0]["operation"] in {"vps2.health", "vps1.edge.health"}
    assert _sel("Summarise the situation with the model.")["steps"][0]["operation"] == "ask"


def test_select_read_file_with_branch_modifier_is_single_step():
    r = _sel("Read the file README.md from branch hg-missing and report it.")
    assert r["status"] == "SELECTED"
    assert [s["operation"] for s in r["steps"]] == ["github.read_file"]
    assert r["steps"][0]["payload"]["ref"] == "hg-missing"


def test_select_composite_create_write_cleanup():
    r = _sel("Create a bounded test branch named hg-cl6-demo and write a proof file, then clean it up.")
    ops = [s["operation"] for s in r["steps"]]
    assert ops == ["github.create_branch", "github.write_file", "github.delete_branch"]
    assert r["steps"][0]["payload"]["branch"] == "hg-cl6-demo"


def test_fail_closed_unknown_ambiguous_unauthorized():
    assert _sel("zxcvbnm qwerty").get("status") in {"NO_MATCH", "AMBIGUOUS"}
    unauth = _sel("Delete the repository OAI-GIANG/GO.")
    assert unauth["status"] == "UNAUTHORIZED"
    assert unauth["refusal"]["code"] == "UNAUTHORIZED_OBJECTIVE"


def test_failure_taxonomy():
    assert orx.classify_failure(ok=True, output={}, witness={})["class"] == "SUCCESS"
    assert orx.classify_failure(ok=False, output={"message": "github_http_404"}, witness={"status": "FAILED"})["class"] == "TARGET_UNAVAILABLE"
    assert orx.classify_failure(ok=False, output={"message": "github_http_403"}, witness={"status": "FAILED"})["class"] == "AUTHORIZATION_FAILURE"
    assert orx.classify_failure(ok=False, output={"error": "PermissionError"}, witness={"status": "FAILED"})["class"] == "CREDENTIAL_FAILURE"
    assert orx.classify_failure(ok=False, output={"message": "github_http_500"}, witness={"status": "FAILED"})["class"] == "TRANSIENT_FAILURE"
    assert orx.classify_failure(ok=False, output={"error": "APPROVAL_REQUIRED"}, witness={"status": "DENIED"})["class"] == "POLICY_BLOCK"
    assert orx.classify_failure(ok=False, output={"error": "TOOL_ARGUMENTS_INVALID"}, witness={"status": "DENIED"})["class"] == "ARGUMENT_FAILURE"


def test_orchestrate_bounded_replan_on_target_unavailable():
    calls = []
    def execute(op, payload, approval):
        calls.append((op, dict(payload)))
        if len(calls) == 1:
            return False, {"message": "github_http_404"}, {"status": "FAILED"}
        return True, {"status": 200, "op": op}, {"status": "COMPLETED"}
    trace = orx.orchestrate("Read the file README.md from branch hg-missing and report it.", catalogue=CAT, execute=execute)
    assert trace["final"] == "SUCCESS"
    assert trace["replans"] and trace["replans"][0]["type"] == "replan"
    assert calls[0][1].get("ref") == "hg-missing" and calls[1][1].get("ref") == orx.DEFAULT_REF


def test_orchestrate_bounded_retry_on_transient():
    calls = []
    def execute(op, payload, approval):
        calls.append(op)
        if len(calls) == 1:
            return False, {"message": "github_http_500"}, {"status": "FAILED"}
        return True, {"status": 200}, {"status": "COMPLETED"}
    trace = orx.orchestrate("Read the repository metadata for OAI-GIANG/GO.", catalogue=CAT, execute=execute)
    assert trace["final"] == "SUCCESS" and len(calls) == 2 and trace["replans"][0]["type"] == "retry"


def test_orchestrate_terminal_failure_is_bounded():
    calls = []
    def execute(op, payload, approval):
        calls.append(op)
        return False, {"message": "github_http_500"}, {"status": "FAILED"}
    trace = orx.orchestrate("Read the repository metadata for OAI-GIANG/GO.", catalogue=CAT, execute=execute)
    assert trace["final"] == "FAILED"
    assert len(calls) <= 1 + orx.MAX_RETRY  # bounded
    assert trace["terminal_reason"] == "TRANSIENT_FAILURE"


def test_orchestrate_refuses_without_executing():
    calls = []
    trace = orx.orchestrate("Delete the repository OAI-GIANG/GO.", catalogue=CAT, execute=lambda *a: calls.append(a) or (True, {}, {}))
    assert trace["final"] == "REFUSED" and calls == []


def test_classify_provider_unavailable_is_explicit_not_faked():
    c = orx.classify_failure(ok=False, output={"message": "local adapter supports only bounded echo"}, witness={"status": "FAILED"})
    assert c["class"] == "CAPABILITY_UNAVAILABLE" and c["reason"] == "MODEL_PROVIDER_UNAVAILABLE"
    assert orx.classify_exception(RuntimeError("local adapter supports only bounded echo"))["reason"] == "MODEL_PROVIDER_UNAVAILABLE"


def test_router_has_no_network_or_model_dependency():
    import ast, pathlib
    tree = ast.parse(pathlib.Path(orx.__file__).read_text(encoding="utf-8"))
    banned = {"subprocess", "socket", "urllib", "requests", "http", "asyncio", "openai", "deepseek"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                assert a.name.split(".")[0] not in banned, a.name
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in banned, node.module
