#!/usr/bin/env python3
"""Build post-merge metrics records from keepalive metrics logs."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts import keepalive_metrics_collector as collector


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed
    return None


def _read_ndjson(path: Path) -> tuple[list[dict[str, Any]], int]:
    entries: list[dict[str, Any]] = []
    errors = 0
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return entries, 1
    for line in content.splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            errors += 1
            continue
        if isinstance(parsed, dict):
            entries.append(parsed)
        else:
            errors += 1
    return entries, errors


def _is_keepalive_record(record: dict[str, Any]) -> bool:
    metric_type = record.get("metric_type")
    if metric_type is None:
        return True
    return str(metric_type).strip().lower() == "keepalive"


def _filter_keepalive_records(
    records: Iterable[dict[str, Any]],
    pr_number: int,
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for record in records:
        if not _is_keepalive_record(record):
            continue
        record_pr = _safe_int(record.get("pr_number"))
        if record_pr == pr_number:
            filtered.append(record)
    return filtered


def _latest_record(records: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    best_ts: datetime | None = None
    best_iteration = -1

    for record in records:
        timestamp = _parse_timestamp(record.get("timestamp"))
        iteration = _safe_int(record.get("iteration")) or -1
        if timestamp is not None:
            if best_ts is None or timestamp > best_ts:
                best = record
                best_ts = timestamp
                best_iteration = iteration
            continue
        if best_ts is None and iteration > best_iteration:
            best = record
            best_iteration = iteration

    return best


def build_post_merge_record(
    records: Iterable[dict[str, Any]],
    *,
    pr_number: int,
    merged_at: str,
    human_interventions: int,
    timestamp: str | None = None,
    iteration_count: int | None = None,
    tasks_total: int | None = None,
    tasks_complete: int | None = None,
) -> dict[str, Any]:
    keepalive = _filter_keepalive_records(records, pr_number)
    latest = _latest_record(keepalive) if keepalive else None

    if iteration_count is None:
        iterations = [_safe_int(record.get("iteration")) for record in keepalive]
        iteration_values = [value for value in iterations if value is not None]
        if iteration_values:
            iteration_count = max(iteration_values)
        else:
            raise ValueError(f"no keepalive iterations found for PR #{pr_number}")

    if tasks_total is None:
        tasks_total = _safe_int(latest.get("tasks_total") if latest else None)
    if tasks_complete is None:
        tasks_complete = _safe_int(latest.get("tasks_complete") if latest else None)
    if tasks_total is None or tasks_complete is None:
        raise ValueError(f"missing task counts for PR #{pr_number}")

    completion_rate = float(tasks_complete) / float(tasks_total) if tasks_total > 0 else 0.0
    record = {
        "metric_type": "post-merge",
        "pr_number": pr_number,
        "timestamp": timestamp or _utc_now_iso(),
        "merged_at": merged_at,
        "iteration_count": iteration_count,
        "tasks_total": tasks_total,
        "tasks_complete": tasks_complete,
        "completion_rate": completion_rate,
        "human_interventions": human_interventions,
    }
    return record


def _coerce_int(value: str, field: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer") from exc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build post-merge metrics records from keepalive logs."
    )
    parser.add_argument(
        "--metrics-path", default="keepalive-metrics.ndjson", help="Keepalive NDJSON log path"
    )
    parser.add_argument(
        "--output-path",
        help="NDJSON output path (defaults to metrics path)",
    )
    parser.add_argument("--pr-number", required=True, help="Pull request number")
    parser.add_argument("--merged-at", required=True, help="Merged timestamp (ISO 8601)")
    parser.add_argument(
        "--human-interventions", default="0", help="Human intervention count (integer)"
    )
    parser.add_argument(
        "--timestamp", help="Record timestamp (ISO 8601, defaults to now)"
    )
    parser.add_argument("--iteration-count", help="Override iteration count")
    parser.add_argument("--tasks-total", help="Override tasks total")
    parser.add_argument("--tasks-complete", help="Override tasks complete")
    return parser


def main(argv: list[str]) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    metrics_path = Path(args.metrics_path)
    output_path = Path(args.output_path) if args.output_path else metrics_path

    pr_number = _coerce_int(args.pr_number, "pr_number")
    human_interventions = _coerce_int(args.human_interventions, "human_interventions")
    iteration_override = (
        _coerce_int(args.iteration_count, "iteration_count") if args.iteration_count else None
    )
    tasks_total_override = (
        _coerce_int(args.tasks_total, "tasks_total") if args.tasks_total else None
    )
    tasks_complete_override = (
        _coerce_int(args.tasks_complete, "tasks_complete") if args.tasks_complete else None
    )

    records, errors = _read_ndjson(metrics_path)
    if errors:
        print(
            f"keepalive_post_merge_metrics: {errors} parse error(s) in {metrics_path}",
            file=sys.stderr,
        )

    try:
        record = build_post_merge_record(
            records,
            pr_number=pr_number,
            merged_at=args.merged_at,
            human_interventions=human_interventions,
            timestamp=args.timestamp,
            iteration_count=iteration_override,
            tasks_total=tasks_total_override,
            tasks_complete=tasks_complete_override,
        )
        collector.validate_record(record)
        collector.append_record(output_path, record)
    except Exception as exc:
        print(f"keepalive_post_merge_metrics: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote post-merge metrics record to {output_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main(sys.argv[1:]))
