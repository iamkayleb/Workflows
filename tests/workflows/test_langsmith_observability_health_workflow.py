from pathlib import Path

WORKFLOW = Path(".github/workflows/health-84-langsmith-observability.yml")


def test_observability_health_is_independent_and_non_mutating() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert "schedule:" in source
    assert "workflow_run:" in source
    assert "LangSmith Metrics Dashboard" in source
    assert "LangSmith Fleet Conformance" in source
    assert "maint-80-langsmith-metrics-dashboard.yml" in source
    assert "maint-81-langsmith-fleet-conformance.yml" in source
    assert "contents: read" in source
    assert "contents: write" not in source
    assert "persist-credentials: false" in source
    assert "git push" not in source


def test_observability_health_has_visible_durable_escalation() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert 'title="🔭 LangSmith Observability Health"' in source
    assert "tracker:durable" in source
    assert "needs-human" in source
    assert "agent:needs-attention" in source
    assert "gh issue edit" in source
    assert "gh issue create" in source
    assert "gh issue comment" in source
    assert "LANGSMITH_API_KEY: ${{ secrets.LANGSMITH_API_KEY }}" in source
