import json
from datetime import UTC, datetime

from scripts import langsmith_observability_health as health

NOW = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)


def _run(created_at: str, conclusion: str) -> dict[str, str]:
    return {"created_at": created_at, "conclusion": conclusion, "status": "completed"}


def test_workflow_health_detects_repeated_failures_and_stale_success() -> None:
    component = health.evaluate_workflow_runs(
        [
            _run("2026-08-15T10:00:00Z", "failure"),
            _run("2026-08-14T10:00:00Z", "failure"),
            _run("2026-08-01T10:00:00Z", "success"),
        ],
        name="dashboard_publication",
        now=NOW,
        max_age_hours=192,
        failure_threshold=2,
    )

    assert component["status"] == "degraded"
    assert component["consecutive_failures"] == 2
    assert any("last success" in reason for reason in component["reasons"])
    assert any("consecutive" in reason for reason in component["reasons"])


def test_fresh_trace_is_healthy() -> None:
    component = health.evaluate_trace_freshness(
        {"id": "run-1", "trace_id": "trace-1", "start_time": "2026-08-15T11:00:00Z"},
        now=NOW,
        max_age_hours=24,
    )

    assert component["status"] == "healthy"
    assert component["latest_trace_id"] == "trace-1"
    assert component["hours_since_trace"] == 1.0


def test_overdue_pause_requires_attention() -> None:
    registry = {
        "repos": [
            {
                "repo": "stranske/Workflows",
                "rollout_status": "paused",
                "paused_at": "2026-06-13T13:36:33Z",
                "pause_reason": "artifact rollout paused",
                "pause_owner": "stranske/Workflows#2150",
                "resume_condition": "producer artifact is available",
                "review_by": "2026-08-01",
            }
        ]
    }

    component = health.evaluate_pauses(registry, now=NOW)

    assert component["status"] == "degraded"
    assert component["paused_entries"][0]["pause_owner"] == "stranske/Workflows#2150"
    assert component["reasons"] == [
        "stranske/Workflows pause review was due 2026-08-01"
    ]


def test_workflow_run_loader_preserves_fetch_failure(tmp_path) -> None:
    payload = tmp_path / "runs.json"
    payload.write_text(
        json.dumps({"workflow_runs": [], "fetch_error": "GitHub API unavailable"}),
        encoding="utf-8",
    )

    runs, error = health.load_workflow_runs(payload)

    assert runs == []
    assert error == "GitHub API unavailable"
