#!/usr/bin/env python3
"""Scan active repos for open enhancement/feature issues that fell between systems.

The opener cron selects work units by `priority:high|normal|low` label or by
presence in the weekly approved-issue-queue. Issues created manually with
`enhancement` or `feature` labels but no `priority:*` label are invisible to
both: the opener doesn't see them, and the repo-review's design-vs-impl
discovery doesn't promote them (they aren't a design gap, they're declared
work). They sit indefinitely.

The 2026-05-07 worked example: Inv-Man-Intake #25/#26/#27 were created
2026-03-01 with `enhancement` + `milestone:B-extraction-queue-images` labels
only. 70 days later, no activity, no agent ever picked them up.

This scanner is a SAFETY NET, not a primary mechanism. It surfaces issues
matching:

  - has `enhancement` OR `feature` label
  - does NOT have any `priority:*` label (opener would see them)
  - does NOT have any `agent:*` label (an agent already owns it)
  - does NOT have a dependabot/sync/process-eval label (those have their
    own automations and shouldn't bubble up here)
  - has NOT been updated in the past `--stale-days` days (default 7)

Output: JSON to `--out` with each item's repo, number, title, age_days,
labels, url. The weekly repo-review's notify step reads this and adds a
"Backlog needing your attention" section to the desktop reminder so the
human decides each week whether to: promote (`priority:normal`),
deprioritize (`priority:low`), or close (out of scope now).

Goal: an issue can sit in this state for at most 1-2 weekly cycles before
the human surfaces it.

Used by the coordinator's final notify step. Standalone CLI for manual
runs:

    python scripts/repo_review_backlog_scan.py \
        --registry config/repo_review_registry.json \
        --out docs/reports/repo-review/backlog-scan.json
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


# Labels that exclude an issue from the scan, organized by reason.

# Already visible to the opener (it queues priority-labeled issues directly).
PRIORITY_LABEL_PREFIXES = ("priority:",)

# An agent is already assigned/working — don't double-surface.
AGENT_LABEL_PREFIXES = ("agent:",)

# Handled by other crons (dependabot bridge, sync workers, process-eval cron).
EXCLUDE_LABELS_EXACT = {
    # Dependabot ecosystem
    "dependabot",
    "dependencies",
    # Sync automation (workflows / consumer template sync)
    "sync",
    "sync-pr",
    "sync-generated",
    "consumer-sync",
    "integration-sync",
    "workflows-sync",
    "template-sync",
    # Process-evaluation / observability automation
    "langsmith",
    "process-evaluation",
    "ops-data",
    "automation-metrics",
    # Tracker / campaign labels (handled by their own controller)
    "tracker:durable",
    "campaign:active",
    "campaign:sync-dependabot",
}
EXCLUDE_LABEL_PREFIXES = (
    "campaign:",  # all campaign:* are controller-owned
)

# Include only if at least one of these labels is present.
INCLUDE_LABELS = {"enhancement", "feature"}


def load_registry(registry_path: Path) -> list[str]:
    """Return the list of active repo full-names from the registry."""
    data = json.loads(registry_path.read_text(encoding="utf-8"))
    repos = data.get("repos", []) or []
    return [
        str(r.get("repo")) for r in repos
        if isinstance(r, dict) and r.get("status") == "active" and r.get("repo")
    ]


def gh_list_open_issues(repo: str) -> list[dict[str, Any]]:
    """Return all open issues for `repo`. Best-effort: on gh failure returns []."""
    if not shutil.which("gh"):
        print(f"[backlog-scan] gh not on PATH; skipping {repo}", file=sys.stderr)
        return []
    cmd = [
        "gh", "issue", "list",
        "--repo", repo,
        "--state", "open",
        "--limit", "500",
        "--json", "number,title,labels,updatedAt,createdAt,url",
    ]
    try:
        result = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        print(f"[backlog-scan] gh timed out on {repo}", file=sys.stderr)
        return []
    if result.returncode != 0:
        print(f"[backlog-scan] gh issue list failed on {repo}: {result.stderr[:200]}", file=sys.stderr)
        return []
    try:
        return json.loads(result.stdout or "[]")
    except json.JSONDecodeError:
        return []


def label_names(issue: dict[str, Any]) -> list[str]:
    return [
        str(label.get("name", ""))
        for label in (issue.get("labels") or [])
        if isinstance(label, dict)
    ]


def is_excluded(labels: list[str]) -> tuple[bool, str]:
    """Return (excluded, reason). reason is empty string when not excluded."""
    label_set = set(labels)
    for prefix in PRIORITY_LABEL_PREFIXES:
        for lbl in labels:
            if lbl.startswith(prefix):
                return True, f"has priority label: {lbl}"
    for prefix in AGENT_LABEL_PREFIXES:
        for lbl in labels:
            if lbl.startswith(prefix):
                return True, f"has agent label: {lbl}"
    for prefix in EXCLUDE_LABEL_PREFIXES:
        for lbl in labels:
            if lbl.startswith(prefix):
                return True, f"excluded prefix: {lbl}"
    overlap = label_set & EXCLUDE_LABELS_EXACT
    if overlap:
        return True, f"excluded label: {sorted(overlap)[0]}"
    return False, ""


def is_included(labels: list[str]) -> bool:
    return bool(set(labels) & INCLUDE_LABELS)


def days_since(timestamp: str | None) -> float:
    if not timestamp:
        return 0.0
    try:
        ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return 0.0
    return (datetime.now(tz=UTC) - ts).total_seconds() / 86400.0


def scan(repos: list[str], stale_days: int) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    scanned = 0
    repo_summary: dict[str, dict[str, int]] = {}

    for repo in repos:
        repo_total = 0
        repo_kept = 0
        for issue in gh_list_open_issues(repo):
            scanned += 1
            repo_total += 1
            labels = label_names(issue)
            if not is_included(labels):
                continue
            excluded, _reason = is_excluded(labels)
            if excluded:
                continue
            age = days_since(issue.get("updatedAt"))
            if age < stale_days:
                continue  # something recently happened to it
            items.append({
                "repo": repo,
                "number": issue.get("number"),
                "title": issue.get("title"),
                "url": issue.get("url"),
                "age_days": round(age, 1),
                "last_updated": issue.get("updatedAt"),
                "created_at": issue.get("createdAt"),
                "labels": labels,
            })
            repo_kept += 1
        repo_summary[repo] = {"open_issues": repo_total, "stale_unaddressed": repo_kept}

    # Sort oldest-stale-first so the user sees the worst-rotting items first.
    items.sort(key=lambda i: i.get("age_days", 0), reverse=True)

    return {
        "generated_on": datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stale_days_threshold": stale_days,
        "scanned_open_issues": scanned,
        "items": items,
        "by_repo": repo_summary,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry", type=Path, required=True,
        help="path to config/repo_review_registry.json",
    )
    parser.add_argument(
        "--out", type=Path, required=True,
        help="path to write backlog-scan.json",
    )
    parser.add_argument(
        "--stale-days", type=int, default=7,
        help="surface issues NOT updated in this many days (default: 7)",
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="suppress per-repo progress chatter",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        repos = load_registry(args.registry)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"[backlog-scan] cannot load registry: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(f"[backlog-scan] scanning {len(repos)} active repos for stale unaddressed enhancements")

    result = scan(repos, args.stale_days)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    n = len(result["items"])
    if not args.quiet:
        print(
            f"[backlog-scan] scanned {result['scanned_open_issues']} open issues, "
            f"surfaced {n} stale (>{args.stale_days}d) unaddressed enhancement(s)"
        )
        if n:
            print(f"[backlog-scan] wrote {args.out}")
            for item in result["items"][:5]:
                print(f"  - {item['repo']}#{item['number']} (age {item['age_days']}d): {item['title'][:80]}")
            if n > 5:
                print(f"  - ...and {n - 5} more")
    else:
        print(f"[backlog-scan] {n} stale unaddressed enhancement(s) → {args.out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
