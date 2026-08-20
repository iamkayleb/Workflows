from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/maint-87-docs-drift-fix-agent.yml"
TEMPLATE = ROOT / "templates/consumer-repo/.github/workflows/maint-87-docs-drift-fix-agent.yml"


def test_docs_drift_workflow_is_exact_synced_and_pinned() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert TEMPLATE.read_text(encoding="utf-8") == source
    assert "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1" in source
    assert "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97" in source
    assert "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" in source
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
    assert "!" in concurrency["cancel-in-progress"]
