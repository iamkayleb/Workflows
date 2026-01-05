from pathlib import Path

import yaml

WORKFLOW_PATH = Path(".github/workflows/agents-issue-optimizer.yml")


def _load_workflow() -> dict:
    assert WORKFLOW_PATH.exists(), "agents-issue-optimizer.yml must exist"
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


def test_issue_optimizer_triggers_on_labeled_event() -> None:
    workflow = _load_workflow()
    triggers = workflow.get("on") or workflow.get(True) or {}
    issues = triggers.get("issues") or {}
    types = issues.get("types") or []
    assert "labeled" in types


def test_issue_optimizer_checks_for_format_label() -> None:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "agents:format" in text
    assert "phase=format" in text
