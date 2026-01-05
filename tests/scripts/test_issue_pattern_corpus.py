import json
from pathlib import Path

from scripts import issue_pattern_corpus as corpus


def _write_ndjson(path: Path, records: list[dict]) -> None:
    payload = "\n".join(json.dumps(record) for record in records) + "\n"
    path.write_text(payload, encoding="utf-8")


def test_build_corpus_filters_successful(tmp_path: Path) -> None:
    issues = [
        {
            "issue_number": 10,
            "pr_number": 101,
            "title": "Issue A",
            "body": "## Tasks\n- [ ] One\n## Acceptance Criteria\n- [ ] Done",
        },
        {
            "issue_number": 11,
            "pr_number": 102,
            "title": "Issue B",
            "body": "## Tasks\n- [ ] Two\n## Acceptance Criteria\n- [ ] Done",
        },
    ]
    metrics = [
        {
            "metric_type": "post-merge",
            "pr_number": 101,
            "completion_rate": 1.0,
            "human_interventions": 0,
            "tasks_total": 2,
            "iteration_count": 2,
        },
        {
            "metric_type": "post-merge",
            "pr_number": 102,
            "completion_rate": 0.5,
            "human_interventions": 0,
            "tasks_total": 2,
            "iteration_count": 3,
        },
    ]

    issues_path = tmp_path / "issues.ndjson"
    metrics_path = tmp_path / "metrics.ndjson"
    _write_ndjson(issues_path, issues)
    _write_ndjson(metrics_path, metrics)

    criteria = corpus.CorpusCriteria(
        min_completion_rate=1.0, max_human_interventions=None, min_tasks_total=None
    )
    issue_entries, _ = corpus._read_json_or_ndjson(issues_path)
    metric_entries, _ = corpus._read_json_or_ndjson(metrics_path)
    result = corpus.build_corpus(issue_entries, metric_entries, criteria)

    assert len(result["successful_issues"]) == 1
    assert result["successful_issues"][0]["issue_number"] == 10


def test_build_corpus_groups_patterns() -> None:
    issues = [
        {
            "issue_number": 20,
            "pr_number": 201,
            "title": "Issue C",
            "body": "## Tasks\n- [ ] One\n- [ ] Two\n## Acceptance Criteria\n- [ ] Done",
        },
        {
            "issue_number": 21,
            "pr_number": 202,
            "title": "Issue D",
            "body": "## Tasks\n- [ ] Three\n- [ ] Four\n## Acceptance Criteria\n- [ ] Done",
        },
    ]
    metrics = [
        {
            "metric_type": "post-merge",
            "pr_number": 201,
            "completion_rate": 1.0,
            "human_interventions": 0,
            "tasks_total": 2,
            "iteration_count": 1,
        },
        {
            "metric_type": "post-merge",
            "pr_number": 202,
            "completion_rate": 1.0,
            "human_interventions": 0,
            "tasks_total": 2,
            "iteration_count": 1,
        },
    ]

    criteria = corpus.CorpusCriteria(
        min_completion_rate=1.0, max_human_interventions=0, min_tasks_total=1
    )
    result = corpus.build_corpus(issues, metrics, criteria)

    assert len(result["successful_issues"]) == 2
    assert len(result["patterns"]) == 1
    assert result["patterns"][0]["count"] == 2
