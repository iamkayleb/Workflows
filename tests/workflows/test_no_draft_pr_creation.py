from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTOMATION_ROOTS = (
    REPO_ROOT / ".github" / "actions",
    REPO_ROOT / ".github" / "scripts",
    REPO_ROOT / ".github" / "workflows",
    REPO_ROOT / "templates" / "consumer-repo" / ".github",
)


def _automation_sources() -> list[Path]:
    suffixes = {".js", ".py", ".sh", ".yaml", ".yml"}
    return sorted(
        path
        for root in AUTOMATION_ROOTS
        for path in root.rglob("*")
        if path.is_file() and path.suffix in suffixes
    )


def test_automation_never_creates_or_restages_draft_pull_requests() -> None:
    violations: list[str] = []
    dynamic_draft = re.compile(
        r"\bdraft[ \t]*:[ \t]*(?:true\b|\$\{\{|(?!false\b)[A-Za-z_$][\w.$]*)"
    )

    for path in _automation_sources():
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(REPO_ROOT)
        if "--draft" in text:
            violations.append(f"{relative}: uses gh pr create --draft")
        if "convertPullRequestToDraft" in text:
            violations.append(f"{relative}: converts a ready PR back to draft")
        if ("pulls.create" in text or "gh pr create" in text) and dynamic_draft.search(text):
            violations.append(f"{relative}: supplies a non-false draft value")

    assert not violations, "\n".join(violations)


def test_pr_creators_state_the_ready_for_review_invariant() -> None:
    bootstrap = (
        REPO_ROOT / ".github" / "actions" / "codex-bootstrap-lite" / "action.yml"
    ).read_text(encoding="utf-8")
    bridge = (REPO_ROOT / ".github" / "workflows" / "reusable-agents-issue-bridge.yml").read_text(
        encoding="utf-8"
    )
    sync = (REPO_ROOT / ".github" / "workflows" / "maint-68-sync-consumer-repos.yml").read_text(
        encoding="utf-8"
    )

    assert "draft: false" in bootstrap
    assert "inputs.draft" not in bootstrap
    assert "inputs.auto_ready" not in bootstrap
    assert "draft: false" in bridge
    assert "sync:delivery-staging" in sync
    assert 'gh pr merge "$existing_pr" --disable-auto' in sync


def test_legacy_draft_inputs_are_inert_and_absent_from_operator_ui() -> None:
    bridge = (REPO_ROOT / ".github" / "workflows" / "reusable-agents-issue-bridge.yml").read_text(
        encoding="utf-8"
    )
    reusable_agents = (REPO_ROOT / ".github" / "workflows" / "reusable-16-agents.yml").read_text(
        encoding="utf-8"
    )
    intake = (REPO_ROOT / ".github" / "workflows" / "agents-63-issue-intake.yml").read_text(
        encoding="utf-8"
    )
    template_intake = (
        REPO_ROOT
        / "templates"
        / "consumer-repo"
        / ".github"
        / "workflows"
        / "agents-issue-intake.yml"
    ).read_text(encoding="utf-8")
    resolver = (REPO_ROOT / ".github" / "scripts" / "agents_orchestrator_resolve.js").read_text(
        encoding="utf-8"
    )

    assert "inputs.agent_pr_draft" not in bridge
    assert "inputs.draft_pr" not in reusable_agents
    dispatch_inputs = intake.split("workflow_dispatch:", 1)[1].split("workflow_call:", 1)[0]
    assert "bridge_draft_pr" not in dispatch_inputs
    assert "bridge_draft_pr" not in template_intake
    assert "merged.draft_pr" not in resolver
    assert "draft_pr: 'false'" in resolver
