from datetime import UTC, datetime
from pathlib import Path

from scripts import keepalive_post_merge_metrics as post_merge


def _sample_keepalive(pr_number: int, iteration: int, timestamp: str, total: int, complete: int) -> dict:
    return {
        "pr_number": pr_number,
        "iteration": iteration,
        "timestamp": timestamp,
        "tasks_total": total,
        "tasks_complete": complete,
        "action": "run",
        "error_category": "none",
        "duration_ms": 100,
    }


def test_build_post_merge_record_computes_from_keepalive_records() -> None:
    records = [
        _sample_keepalive(
            7,
            1,
            datetime(2025, 1, 1, tzinfo=UTC).isoformat().replace("+00:00", "Z"),
            4,
            1,
        ),
        _sample_keepalive(
            7,
            3,
            datetime(2025, 1, 2, tzinfo=UTC).isoformat().replace("+00:00", "Z"),
            4,
            4,
        ),
        _sample_keepalive(
            9,
            2,
            datetime(2025, 1, 3, tzinfo=UTC).isoformat().replace("+00:00", "Z"),
            6,
            2,
        ),
    ]

    record = post_merge.build_post_merge_record(
        records,
        pr_number=7,
        merged_at="2025-01-03T00:00:00Z",
        human_interventions=2,
        timestamp="2025-01-03T01:00:00Z",
    )

    assert record["iteration_count"] == 3
    assert record["tasks_total"] == 4
    assert record["tasks_complete"] == 4
    assert record["completion_rate"] == 1.0
    assert record["human_interventions"] == 2


def test_build_post_merge_record_rejects_missing_records() -> None:
    try:
        post_merge.build_post_merge_record(
            [],
            pr_number=11,
            merged_at="2025-01-04T00:00:00Z",
            human_interventions=0,
        )
    except ValueError as exc:
        assert "no keepalive iterations" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing records")


def test_main_writes_post_merge_record(tmp_path: Path, capsys) -> None:
    log_path = tmp_path / "metrics.ndjson"
    log_path.write_text(
        "\n".join(
            [
                '{"pr_number": 12, "iteration": 1, "timestamp": "2025-02-01T00:00:00Z",'
                ' "tasks_total": 3, "tasks_complete": 1, "action": "run",'
                ' "error_category": "none", "duration_ms": 100}',
                '{"pr_number": 12, "iteration": 2, "timestamp": "2025-02-02T00:00:00Z",'
                ' "tasks_total": 3, "tasks_complete": 3, "action": "run",'
                ' "error_category": "none", "duration_ms": 100}',
            ]
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "out.ndjson"

    result = post_merge.main(
        [
            "--metrics-path",
            str(log_path),
            "--output-path",
            str(output_path),
            "--pr-number",
            "12",
            "--merged-at",
            "2025-02-03T00:00:00Z",
            "--human-interventions",
            "1",
            "--timestamp",
            "2025-02-03T01:00:00Z",
        ]
    )

    captured = capsys.readouterr()
    assert result == 0
    assert output_path.exists()
    output = output_path.read_text(encoding="utf-8").splitlines()
    assert len(output) == 1
    assert "post-merge" in output[0]
    assert "Wrote post-merge metrics record" in captured.out
