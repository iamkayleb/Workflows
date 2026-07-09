#!/usr/bin/env python3
"""Pull one agent-evaluation data row for a PR.

Given a PR number in a consumer repo (e.g. iamkayleb/bukay), this collects the
efficiency metrics that the agent-eval template needs and that this system
actually records, then emits a single CSV row (or JSON):

  rounds, failures, wall-clock, run count, commits, diff stat, gate first-pass,
  verify:compare verdict/confidence per provider, plus a non-bot-comment proxy
  for human interventions.

It reads directly from the GitHub API:
  * PR object          -> commits, additions/deletions/changed_files, labels,
                          head/base ref, merged, issue link
  * issue comments     -> Keepalive Work Log (rounds, failures) and the
                          "Provider Comparison Report" (verify:compare verdicts)
  * Actions runs        -> wall-clock proxy + Gate first-pass

Cost note: neither agent has a per-token USD bill for code production (both use
flat-rate subscription auth; metered keys spend only on verify:compare). So the
cost proxies here are rounds / failures / wall-clock, not dollars. Raw token
counts, if you want them, live in the per-run agent session-log artifacts and
are intentionally not fetched here.

Auth: uses `gh auth token` when the GitHub CLI is available, else the
GITHUB_TOKEN / GH_TOKEN environment variable.

Usage:
  python scripts/agent_eval_pull.py 87 --repo iamkayleb/bukay --header
  python scripts/agent_eval_pull.py 87 --repo iamkayleb/bukay --out eval.csv
  python scripts/agent_eval_pull.py 87 --repo iamkayleb/bukay --json
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime

API_ROOT = "https://api.github.com"
WORK_LOG_MARKER = "<!-- keepalive-work-log -->"
VERIFY_MARKER = "## Provider Comparison Report"

# Column order for the CSV row (one row per PR == one agent run).
FIELDS = [
    "pr",
    "agent",
    "issue",
    "merged",
    "first_pass_gate",
    "rounds",
    "failures",
    "nonbot_comments",
    "run_count",
    "wall_clock_min",
    "commits",
    "files_changed",
    "additions",
    "deletions",
    "neutral_provider",
    "neutral_verdict",
    "neutral_confidence",
    "neutral_scores",
    "other_provider",
    "other_verdict",
    "other_confidence",
    "url",
]

# Logins we treat as automation, not humans, for the intervention proxy.
BOT_LOGIN_HINTS = (
    "[bot]",
    "workflows-integration-test",
    "stranske-automation",
    "github-actions",
)


def _log(msg: str) -> None:
    print(f"[agent-eval] {msg}", file=sys.stderr)


def get_token() -> str:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token.strip()
    if shutil.which("gh"):
        try:
            out = subprocess.run(
                ["gh", "auth", "token"],
                capture_output=True,
                text=True,
                check=True,
            )
            token = out.stdout.strip()
            if token:
                return token
        except subprocess.CalledProcessError:
            pass
    _log("No token found. Set GITHUB_TOKEN/GH_TOKEN or run `gh auth login`.")
    sys.exit(2)


def _request(url: str, token: str) -> tuple[object, dict[str, str]]:
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "agent-eval-pull")
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data, dict(resp.headers)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:300]
        _log(f"HTTP {exc.code} for {url}: {body}")
        sys.exit(1)


def api_get(path: str, token: str, params: dict | None = None) -> object:
    url = f"{API_ROOT}/{path.lstrip('/')}"
    if params:
        query = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{query}"
    data, _ = _request(url, token)
    return data


def api_paginate(
    path: str, token: str, params: dict | None = None, items_key: str | None = None
) -> list:
    """Follow Link-header pagination; return a flat list of items.

    items_key handles endpoints that wrap the array in an object
    (e.g. /actions/runs -> {"workflow_runs": [...]}).
    """
    params = dict(params or {})
    params.setdefault("per_page", 100)
    query = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{API_ROOT}/{path.lstrip('/')}?{query}"
    items: list = []
    while url:
        data, headers = _request(url, token)
        page = data.get(items_key, []) if items_key else data
        if isinstance(page, list):
            items.extend(page)
        url = _next_link(headers.get("Link", ""))
    return items


def _next_link(link_header: str) -> str | None:
    for part in link_header.split(","):
        segfrom = part.split(";")
        if len(segfrom) < 2:
            continue
        url_part = segfrom[0].strip().strip("<>")
        if 'rel="next"' in part:
            return url_part
    return None


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
            UTC
        )
    except ValueError:
        return None


# --------------------------------------------------------------------------
# Parsers
# --------------------------------------------------------------------------
def parse_worklog(comments: list[dict]) -> tuple[int, int]:
    """Return (rounds, failures) from the Keepalive Work Log comment.

    The table header is:
      | # | Time (UTC) | Agent | Action | Result | Files | Tasks | ... |
    Rounds = data rows. Failures = rows whose Result cell reads failure/❌.
    """
    body = ""
    for comment in comments:
        if WORK_LOG_MARKER in (comment.get("body") or ""):
            body = comment["body"]
            break
    if not body:
        return 0, 0

    rounds = 0
    failures = 0
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not cells:
            continue
        first = cells[0].lower()
        # Skip header and separator rows.
        if first in ("#", "") or set(cells[0]) <= set("-: "):
            continue
        if first.startswith("time") or first == "iteration":
            continue
        # Column index 4 is Result (0=#,1=Time,2=Agent,3=Action,4=Result).
        result_cell = cells[4].lower() if len(cells) > 4 else ""
        rounds += 1
        if "fail" in result_cell or "❌" in result_cell:
            failures += 1
    return rounds, failures


def _confidence_to_num(text: str) -> str:
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    return m.group(1) if m else text.strip()


def parse_verify(comments: list[dict]) -> dict:
    """Parse the latest Provider Comparison Report.

    Returns provider verdicts/confidences and the neutral (OpenAI) provider's
    dimension scores when present.
    """
    body = ""
    for comment in reversed(comments):  # latest wins
        if VERIFY_MARKER in (comment.get("body") or ""):
            body = comment["body"]
            break
    result = {
        "neutral_provider": "",
        "neutral_verdict": "",
        "neutral_confidence": "",
        "neutral_scores": "",
        "other_provider": "",
        "other_verdict": "",
        "other_confidence": "",
    }
    if not body:
        return result

    # Provider Summary table rows: | Provider | Model | Verdict | Confidence | Summary |
    rows = []
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 4:
            continue
        head = cells[0].lower()
        if head in ("provider", "") or set(cells[0]) <= set("-: "):
            continue
        provider, model, verdict, confidence = cells[0], cells[1], cells[2], cells[3]
        rows.append(
            {
                "provider": provider,
                "model": model,
                "verdict": verdict,
                "confidence": _confidence_to_num(confidence),
            }
        )

    def is_neutral(row: dict) -> bool:
        blob = f"{row['provider']} {row['model']}".lower()
        return "openai" in blob or blob.strip().startswith("gpt") or "gpt-5" in blob

    neutral = next((r for r in rows if is_neutral(r)), None)
    others = [r for r in rows if r is not neutral]
    if neutral:
        result["neutral_provider"] = neutral["model"] or neutral["provider"]
        result["neutral_verdict"] = neutral["verdict"]
        result["neutral_confidence"] = neutral["confidence"]
    if others:
        first = others[0]
        result["other_provider"] = first["model"] or first["provider"]
        result["other_verdict"] = first["verdict"]
        result["other_confidence"] = first["confidence"]

    # Neutral provider dimension scores from the details block.
    result["neutral_scores"] = _extract_neutral_scores(body, neutral)
    return result


def _extract_neutral_scores(body: str, neutral: dict | None) -> str:
    if not neutral:
        return ""
    dims = ["Correctness", "Completeness", "Quality", "Testing", "Risks"]
    # Grab the details section for the neutral provider, then the first
    # occurrence of each "  - Dim: N/10" after its header.
    label = neutral.get("provider") or neutral.get("model") or ""
    idx = body.lower().find(f"#### {label}".lower()) if label else -1
    scope = body[idx:] if idx >= 0 else body
    found = []
    for dim in dims:
        m = re.search(rf"{dim}:\s*([0-9.]+)\s*/\s*10", scope)
        if m:
            found.append(f"{dim[:4].lower()}={m.group(1)}")
    return ",".join(found)


def resolve_agent(labels: list[dict]) -> str:
    for label in labels:
        name = (label.get("name") or "").lower()
        if name.startswith("agent:") and name != "agent:retry":
            return name.split(":", 1)[1]
    for label in labels:
        name = (label.get("name") or "").lower()
        if name.startswith("from:") or name.startswith("runner:"):
            return name.split(":", 1)[1]
    return "unknown"


def resolve_issue(title: str, body: str) -> str:
    m = re.search(
        r"(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*#(\d+)", body or "", re.I
    )
    if m:
        return m.group(1)
    m = re.search(r"#(\d+)", title or "")
    return m.group(1) if m else ""


def summarize_runs(runs: list[dict]) -> tuple[str, int, float]:
    """Return (gate_first_pass Y/N/?, run_count, total_run_minutes)."""
    total_seconds = 0.0
    gate_runs = []
    for run in runs:
        start = _parse_iso(run.get("run_started_at") or run.get("created_at"))
        end = _parse_iso(run.get("updated_at"))
        if start and end and end > start:
            total_seconds += (end - start).total_seconds()
        if (run.get("name") or "") == "Gate":
            gate_runs.append(run)

    gate_first = "?"
    if gate_runs:
        gate_runs.sort(key=lambda r: r.get("run_number") or 0)
        first_concl = gate_runs[0].get("conclusion")
        gate_first = "Y" if first_concl == "success" else "N"
    return gate_first, len(runs), round(total_seconds / 60.0, 1)


def count_nonbot_comments(comments: list[dict]) -> int:
    count = 0
    for comment in comments:
        login = ((comment.get("user") or {}).get("login") or "").lower()
        if any(hint in login for hint in BOT_LOGIN_HINTS):
            continue
        if WORK_LOG_MARKER in (comment.get("body") or ""):
            continue
        count += 1
    return count


# --------------------------------------------------------------------------
def collect(pr: int, repo: str, token: str) -> dict:
    owner, name = repo.split("/", 1)
    pr_data = api_get(f"repos/{owner}/{name}/pulls/{pr}", token)
    head_ref = (pr_data.get("head") or {}).get("ref", "")

    comments = api_paginate(f"repos/{owner}/{name}/issues/{pr}/comments", token)
    runs = api_paginate(
        f"repos/{owner}/{name}/actions/runs",
        token,
        params={"branch": head_ref} if head_ref else None,
        items_key="workflow_runs",
    )

    rounds, failures = parse_worklog(comments)
    verify = parse_verify(comments)
    gate_first, run_count, wall_min = summarize_runs(runs)

    row = {
        "pr": pr,
        "agent": resolve_agent(pr_data.get("labels") or []),
        "issue": resolve_issue(pr_data.get("title", ""), pr_data.get("body", "")),
        "merged": "Y" if pr_data.get("merged") else "N",
        "first_pass_gate": gate_first,
        "rounds": rounds,
        "failures": failures,
        "nonbot_comments": count_nonbot_comments(comments),
        "run_count": run_count,
        "wall_clock_min": wall_min,
        "commits": pr_data.get("commits", 0),
        "files_changed": pr_data.get("changed_files", 0),
        "additions": pr_data.get("additions", 0),
        "deletions": pr_data.get("deletions", 0),
        "url": pr_data.get("html_url", ""),
    }
    row.update(verify)
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pr", type=int, help="PR number")
    parser.add_argument(
        "--repo", default="iamkayleb/bukay", help="owner/name (default iamkayleb/bukay)"
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of CSV")
    parser.add_argument("--header", action="store_true", help="Print CSV header first")
    parser.add_argument(
        "--out", help="Append a CSV row to this file (writes header if new)"
    )
    args = parser.parse_args()

    token = get_token()
    row = collect(args.pr, args.repo, token)

    if args.json:
        print(json.dumps(row, indent=2))
        return 0

    if args.out:
        new_file = not os.path.exists(args.out)
        with open(args.out, "a", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            if new_file:
                writer.writeheader()
            writer.writerow({k: row.get(k, "") for k in FIELDS})
        _log(f"Appended row for PR #{args.pr} to {args.out}")
        return 0

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=FIELDS)
    if args.header:
        writer.writeheader()
    writer.writerow({k: row.get(k, "") for k in FIELDS})
    sys.stdout.write(buffer.getvalue())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
