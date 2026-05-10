#!/usr/bin/env python3
"""Surface the weekly repo-review cycle's outcome to the human reviewer.

The cron writes the packet + queue, but does NOT auto-upload — humans must
review the packet, optionally update `config/repo_review_feedback.json`, then
run `upload_repo_review_issues.py --apply`. Without an active reminder, the
packet sits unread.

This helper produces two surfaces:

A. macOS user notification (osascript "display notification") with a one-line
   summary the moment the cycle ends. Lands in Notification Center; visible
   if the user is at their desk.

B. Persistent desktop file at `~/Desktop/REPO-REVIEW-ACTION-NEEDED.md`. Stays
   until the user deletes it (typically after running --apply). Survives any
   away period, can't be missed when the user opens their desk.

Both surfaces include the packet path, uploadable issue count, and the exact
command to run. The desktop file overwrites each weekly cycle; only the most
recent week is on disk.

Usage (from coordinator or manually):

    python scripts/repo_review_notify.py \
        --output-dir docs/reports/repo-review \
        --queue docs/reports/repo-review/approved-issue-queue.json
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESKTOP_FILENAME = "REPO-REVIEW-ACTION-NEEDED.md"


def load_queue(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"issues": [], "skipped": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"issues": [], "skipped": []}


def summarize_queue(queue: dict[str, Any]) -> dict[str, Any]:
    issues = queue.get("issues", []) or []
    skipped = queue.get("skipped", []) or []
    by_repo: dict[str, int] = {}
    for issue in issues:
        repo = str(issue.get("repo", "?"))
        by_repo[repo] = by_repo.get(repo, 0) + 1
    return {
        "total": len(issues),
        "by_repo": by_repo,
        "skipped_count": len(skipped),
        "issue_titles": [str(i.get("title", "?"))[:80] for i in issues],
    }


def display_notification(title: str, subtitle: str, message: str) -> None:
    """Show a macOS user notification via osascript.

    Best-effort: failures are logged and ignored — notification is a courtesy
    surface, not a hard dependency.
    """
    if not shutil.which("osascript"):
        print("[notify] osascript not on PATH; skipping macOS notification", file=sys.stderr)
        return

    # Escape double quotes for AppleScript string
    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace('"', '\\"')

    script = (
        f'display notification "{esc(message)}" '
        f'with title "{esc(title)}" '
        f'subtitle "{esc(subtitle)}" '
        f'sound name "Glass"'
    )
    try:
        subprocess.run(
            ["osascript", "-e", script],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"[notify] osascript failed: {exc}", file=sys.stderr)


def load_backlog_scan(path: Path | None) -> dict[str, Any]:
    """Load the backlog-scan.json output, or return empty if absent/malformed."""
    if path is None or not path.is_file():
        return {"items": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"items": []}


def format_backlog_section(backlog: dict[str, Any]) -> str:
    """Return a markdown section listing the unaddressed-backlog items.

    Empty if no items. The section gives the user the EXACT gh commands to
    promote / deprioritize / close each one, so they can resolve every entry
    inline without context-switching.
    """
    items = backlog.get("items", []) or []
    if not items:
        return ""

    threshold = backlog.get("stale_days_threshold", 7)
    header = (
        f"\n\n## Backlog needing your attention ({len(items)} item"
        f"{'s' if len(items) != 1 else ''})\n\n"
        f"These open issues are labeled `enhancement` or `feature` but have NO "
        f"`priority:*` label, NO `agent:*` label, and NO activity in the past "
        f"{threshold}+ days. The opener cron cannot see them (it selects by "
        "priority label). Without action, they sit indefinitely.\n\n"
        "Decide each: **promote** to opener queue, **deprioritize**, or **close**.\n\n"
    )

    lines: list[str] = []
    for item in items:
        repo = item["repo"]
        num = item["number"]
        title = item["title"]
        age = item.get("age_days", 0)
        url = item.get("url", "")
        last_label_hint = ""
        labels = item.get("labels", []) or []
        relevant = [l for l in labels if l not in {"enhancement", "feature"}][:2]
        if relevant:
            last_label_hint = f"  _(also labeled: {', '.join(f'`{l}`' for l in relevant)})_\n"
        lines.append(
            f"### {repo}#{num}: {title}\n"
            f"  ({age:.0f} days since last update — {url})\n"
            f"{last_label_hint}"
            f"  - Promote: `gh issue edit {num} --repo {repo} --add-label priority:normal`\n"
            f"  - Deprioritize: `gh issue edit {num} --repo {repo} --add-label priority:low`\n"
            f"  - Close: `gh issue close {num} --repo {repo} --comment \"Out of scope; closing per backlog scan.\"`\n"
        )

    return header + "\n".join(lines) + "\n"


def write_desktop_reminder(
    *,
    queue_summary: dict[str, Any],
    backlog: dict[str, Any],
    packet_path: Path,
    queue_path: Path,
    output_dir: Path,
    workflows_steward_root: Path,
) -> Path:
    """Write a persistent reminder file to the user's desktop.

    Overwrites any prior file (we keep only the latest cycle's reminder).
    Includes both upload-ready issues AND the unaddressed backlog (issues
    that fell between the opener and the design-vs-impl review).
    """
    desktop = Path(os.path.expanduser("~/Desktop"))
    desktop.mkdir(parents=True, exist_ok=True)
    target = desktop / DESKTOP_FILENAME

    today = datetime.now(tz=UTC).strftime("%Y-%m-%d")
    total = queue_summary["total"]
    by_repo = queue_summary["by_repo"]
    skipped_count = queue_summary["skipped_count"]
    titles = queue_summary["issue_titles"]
    backlog_count = len(backlog.get("items", []) or [])

    if total == 0 and backlog_count == 0:
        headline = (
            "## ✓ No issues queued, no backlog rot\n\n"
            "The cron ran, found no fresh design-vs-implementation gaps, "
            "and detected no unaddressed enhancement issues across the fleet. "
            "No action required — the system will run again next Thursday."
        )
    elif total == 0:
        headline = (
            "## No fresh issues queued this week\n\n"
            "The cron found no new design-vs-implementation gaps. See the "
            "**Backlog needing your attention** section below for older "
            "enhancement issues that fell between the opener and the review."
        )
    else:
        repo_lines = "\n".join(f"- **{r}**: {n}" for r, n in sorted(by_repo.items()))
        title_lines = "\n".join(f"  - {t}" for t in titles)
        headline = (
            f"## {total} issue{'s' if total != 1 else ''} ready to upload\n\n"
            f"{repo_lines}\n\n"
            "### Titles\n"
            f"{title_lines}\n"
        )

    skipped_note = (
        f"\n_{skipped_count} repo decision(s) skipped uploading (defer / no-new-work / sync failure)._\n"
        if skipped_count
        else ""
    )

    backlog_section = format_backlog_section(backlog)

    next_action = "" if total == 0 else f"""

## Next action — upload the queued issues

1. Open the packet to review the candidate set:

   ```
   open "{packet_path}"
   ```

2. (Optional) edit `config/repo_review_feedback.json` to revise/drop/defer specific candidates.

3. Upload the approved issues to the remote repos:

   ```
   cd "{workflows_steward_root}"
   python scripts/upload_repo_review_issues.py \\
       --queue "{queue_path}" \\
       --apply
   ```
"""

    body = f"""# Weekly repo-review packet ready — {today}

{headline}
{skipped_note}{next_action}{backlog_section}
## When you're done

Delete this file once you've acted on the queued issues AND the backlog:

```
rm "{target}"
```

---

## Cycle artifacts

- Packet: `{packet_path}`
- Queue: `{queue_path}`
- Output dir: `{output_dir}`
- Generated: {today} (UTC)

If this file isn't deleted by next Thursday's cron run, that run will overwrite it with the next cycle's summary.
"""
    target.write_text(body, encoding="utf-8")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="path to <output_dir>/ (where packet + queue live)",
    )
    parser.add_argument(
        "--queue",
        type=Path,
        required=True,
        help="path to approved-issue-queue.json",
    )
    parser.add_argument(
        "--workflows-steward-root",
        type=Path,
        default=None,
        help="path to Workflows-steward checkout (default: 3 parents up from --output-dir, i.e. <root>/docs/reports/repo-review/.. = <root>/docs/reports = .. = <root>/docs = .. = <root>)",
    )
    parser.add_argument(
        "--backlog-scan",
        type=Path,
        default=None,
        help="path to backlog-scan.json from scripts/repo_review_backlog_scan.py "
             "(default: <output_dir>/backlog-scan.json if present); when present, "
             "adds a 'Backlog needing your attention' section to the desktop file",
    )
    parser.add_argument(
        "--skip-notification",
        action="store_true",
        help="suppress the macOS notification (still writes the desktop file)",
    )
    parser.add_argument(
        "--skip-desktop",
        action="store_true",
        help="suppress the desktop file (still shows the notification)",
    )
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    queue_path = args.queue.resolve()
    packet_path = output_dir / "human-decision-packet.md"
    # output_dir is typically <root>/docs/reports/repo-review/, so the steward
    # root is 3 levels up. Walk parents safely instead of guessing.
    workflows_steward_root = (
        args.workflows_steward_root.resolve()
        if args.workflows_steward_root
        else output_dir.parent.parent.parent.resolve()
    )

    queue = load_queue(queue_path)
    summary = summarize_queue(queue)

    # Default backlog path is alongside the queue; coordinator writes it there.
    backlog_path = (
        args.backlog_scan if args.backlog_scan is not None
        else output_dir / "backlog-scan.json"
    )
    backlog = load_backlog_scan(backlog_path)
    backlog_count = len(backlog.get("items", []) or [])

    total = summary["total"]
    by_repo_str = ", ".join(
        f"{r.split('/')[-1]} ({n})" for r, n in sorted(summary["by_repo"].items())
    )

    if not args.skip_notification:
        if total == 0 and backlog_count == 0:
            display_notification(
                title="Repo-review: clean week",
                subtitle="No issues queued, no backlog rot",
                message="See packet for details. Next run: next Thursday.",
            )
        elif total == 0:
            display_notification(
                title=f"Repo-review: {backlog_count} backlog item{'s' if backlog_count != 1 else ''} need attention",
                subtitle="No fresh upload queue this week",
                message="Action required — see ~/Desktop/REPO-REVIEW-ACTION-NEEDED.md",
            )
        else:
            backlog_suffix = f" + {backlog_count} backlog" if backlog_count else ""
            display_notification(
                title=f"Repo-review: {total} issue{'s' if total != 1 else ''} ready to upload{backlog_suffix}",
                subtitle=by_repo_str or "Review packet for details",
                message="Action required — see ~/Desktop/REPO-REVIEW-ACTION-NEEDED.md",
            )

    if not args.skip_desktop:
        target = write_desktop_reminder(
            queue_summary=summary,
            backlog=backlog,
            packet_path=packet_path,
            queue_path=queue_path,
            output_dir=output_dir,
            workflows_steward_root=workflows_steward_root,
        )
        print(f"[notify] wrote {target}")

    print(
        f"[notify] {total} issue(s) ready, {summary['skipped_count']} repo decision(s) skipped, "
        f"{backlog_count} backlog item(s) need attention"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
