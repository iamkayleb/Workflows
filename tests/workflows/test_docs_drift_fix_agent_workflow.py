from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/maint-87-docs-drift-fix-agent.yml"
TEMPLATE = ROOT / "templates/consumer-repo/.github/workflows/maint-87-docs-drift-fix-agent.yml"


def test_docs_drift_workflow_is_exact_synced_and_pinned() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert TEMPLATE.read_text(encoding="utf-8") == source
    workflow = yaml.safe_load(source)
    uses = [
        step["uses"]
        for job in workflow["jobs"].values()
        for step in job["steps"]
        if "uses" in step and not step["uses"].startswith("./")
    ]
    assert uses
    assert all(re.fullmatch(r".+@[0-9a-f]{40}", reference) for reference in uses)
    assert 'python -m pip install "pyyaml==6.0.3"' in source


def test_docs_drift_workflow_preserves_expected_findings_exit() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert "agent_status=$?" in source
    assert 'if [ "${agent_status}" -gt 1 ]; then' in source
    assert "cat docs-drift-plan.json" in source


def test_docs_drift_apply_lane_is_not_cancelled() -> None:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    concurrency = workflow["concurrency"]

    assert "inputs.apply && 'apply' || 'plan'" in concurrency["group"]
    assert concurrency["cancel-in-progress"] == (
        "${{ !(github.event_name == 'workflow_dispatch' && inputs.apply) }}"
    )
    steps = workflow["jobs"]["docs-drift-fix-agent"]["steps"]
    apply_step = next(
        step for step in steps if step["name"] == "Create repair issues (dispatch-only)"
    )
    assert "github.event_name == 'workflow_dispatch'" in apply_step["if"]
    assert "inputs.apply" in apply_step["if"]
    assert "steps.plan.outputs.findings != '0'" in apply_step["if"]
