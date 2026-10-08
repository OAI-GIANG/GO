from __future__ import annotations

from pathlib import Path

from runtime.go_runtime.core.tool_governance import ToolGovernance
from runtime.go_runtime.core.tool_runtime import ToolAdapter, ToolSpec, default_tool_registry


class FakeReadRepo(ToolAdapter):
    def spec(self):
        return ToolSpec(
            name="github.read_repo",
            description="fake read repo",
            input_schema={
                "type": "object",
                "properties": {"repository": {"type": "string"}},
                "required": ["repository"],
                "additionalProperties": False,
            },
            read_only=True,
            destructive=False,
            plugin_id="test",
        )

    def invoke(self, arguments, context):
        return {"status": 200, "repository": arguments["repository"]}


def _governance(monkeypatch, tmp_path: Path, profile: str | None):
    monkeypatch.setenv("HG_TOOL_AUTHORITY_SUBJECT", "HG_SESSION_TEST")
    monkeypatch.setenv("HG_TOOL_AUTHORITY_PROVENANCE", "HG_SESSION_TEST:proof")
    monkeypatch.setenv("HG_TOOL_AUTHORITY_PROVENANCE_EXPECTED", "HG_SESSION_TEST:proof")
    if profile is None:
        monkeypatch.delenv("HG_TOOL_CAPABILITY_PROFILE", raising=False)
    else:
        monkeypatch.setenv("HG_TOOL_CAPABILITY_PROFILE", profile)
    registry = default_tool_registry()
    registry._tools["github.read_repo"] = FakeReadRepo()
    return ToolGovernance(registry, tmp_path / "tool-events.jsonl")


def test_hg_session_fails_closed_without_capability_profile(monkeypatch, tmp_path):
    governance = _governance(monkeypatch, tmp_path, None)
    result = governance.execute("TASK-1", "github.read_repo", {"repository": "OAI-GIANG/GO"})
    assert result.ok is False
    assert result.output["error"] == "CAPABILITY_PROFILE_MISSING"


def test_readonly_profile_allows_delegated_read_tool(monkeypatch, tmp_path):
    governance = _governance(monkeypatch, tmp_path, "HG_READONLY_V1")
    result = governance.execute("TASK-2", "github.read_repo", {"repository": "OAI-GIANG/GO"})
    assert result.ok is True
    assert result.output["repository"] == "OAI-GIANG/GO"
    assert result.witness["status"] == "COMPLETED"
    assert result.witness["scope"] == "tool:github.read_repo"


def test_readonly_profile_denies_ungranted_mutation_before_adapter(monkeypatch, tmp_path):
    governance = _governance(monkeypatch, tmp_path, "HG_READONLY_V1")
    result = governance.execute(
        "TASK-3",
        "github.create_issue",
        {"repository": "OAI-GIANG/GO", "title": "must not execute"},
    )
    assert result.ok is False
    assert result.output["error"] == "CAPABILITY_NOT_GRANTED"
    assert result.witness["status"] == "DENIED"


def test_capability_profile_is_server_side_not_request_selectable(monkeypatch, tmp_path):
    governance = _governance(monkeypatch, tmp_path, "HG_READONLY_V1")
    result = governance.execute(
        "TASK-4",
        "github.delete_branch",
        {"repository": "OAI-GIANG/GO", "branch": "hg-core"},
        approval="approved",
    )
    assert result.ok is False
    assert result.output["error"] == "CAPABILITY_NOT_GRANTED"


def test_capability_profile_digest_is_stable(monkeypatch, tmp_path):
    governance = _governance(monkeypatch, tmp_path, "HG_READONLY_V1")
    info = governance.capability_profile_info()
    assert info["name"] == "HG_READONLY_V1"
    assert info["digest"].startswith("sha256:")
    assert set(info["allowed"]) >= {
        "github.read_repo",
        "github.read_branch",
        "github.read_file",
        "github.read_releases",
        "vps1.edge.health",
        "vps2.health",
    }


def test_objective_selection_cannot_downgrade_ungranted_action(monkeypatch):
    from runtime.go_runtime.core.engine import objective_router as router
    catalogue = [
        c for c in router.discover(default_tool_registry())
        if c["operation"] in {"github.read_branch", "github.read_repo"}
    ]
    result = router.select("Create a branch named hg-forbidden", catalogue)
    assert result["status"] == "CAPABILITY_UNAVAILABLE"
    assert result["refusal"]["requested_operation"] == "github.create_branch"


def test_server_objective_catalogue_is_capability_filtered(monkeypatch):
    from runtime.go_runtime.core.server import GOApplication

    monkeypatch.setenv("HG_TOOL_AUTHORITY_SUBJECT", "HG_SESSION_TEST")
    monkeypatch.setenv("HG_TOOL_CAPABILITY_PROFILE", "HG_READONLY_V1")
    app = object.__new__(GOApplication)
    app.tools = default_tool_registry()
    app.store = type("Store", (), {"add_event": lambda self, *args: None})()
    calls = []

    def fake_execute(task_id, operation, payload, approval="not_required"):
        calls.append(operation)
        return {"ok": True, "output": {"status": 200}, "witness": {"status": "COMPLETED"}}

    app.execute_tool = fake_execute
    result = app.run_objective("TASK-OBJECTIVE-1", {"objective": "Read the repository metadata for OAI-GIANG/GO."})
    assert result["final"] == "SUCCESS"
    assert calls == ["github.read_repo"]
