# Health Workflow Review — 2026-02-22

The goal of this pass was to catalogue every workflow under `.github/workflows` with the `health-*` prefix, verify its purpose, and decide whether it should be optimized, archived, or condensed. Notes below capture the current trigger model, what each job validates, and the immediate follow-ups (if any).

## Portfolio Observations

- **Coverage overlaps** exist between `health-70-validate-sync-manifest.yml` and `health-73-template-completeness.yml`; both gate template/manifest drift via the same Python helper. Consider merging them into a single manifest enforcement workflow to cut the duplicated runners.
- **Diagnostics vs. automation**: `health-claude-cli-auth-debug.yml` and `health-keepalive-auth-diagnostic.yml` are manual one-off troubleshooting harnesses, not automated health checks. If the debugging window has closed, move them into `archives/` (or an `ops/diagnostics` folder) to stop the health namespace from ballooning.
- **Template drift guardrails**: `health-74-template-drift.yml` only warns today. Once existing drift is eliminated, it should fail the job (or block merges via Gate) so regressions do not slip back in.
- **Consumer sync monitoring** is spread across `health-68`, `health-70`, `health-71`, and `health-72`. Centralising the registered repo parsing logic (each workflow re-parses `maint-68` today) would simplify maintenance.

## Workflow Notes

### `health-40-repo-selfcheck.yml`
- **Purpose**: Weekly repo health summary that checks required labels and enforces default-branch protection when `BRANCH_PROTECTION_TOKEN` is configured.
- **Key mechanics**: Runs every Monday at 06:20 UTC, snapshots enforcement state, and can optionally post to a PR via `workflow_dispatch`.
- **Next steps**: Confirm the admin token secret stays fresh; without it the workflow silently drops to read-only verification.

### `health-40-sweep.yml`
- **Purpose**: Gatekeeper for workflow edits; fans out to actionlint (`health-42`) and branch-protection verification (`health-44`) when `.github/workflows/**` changes.
- **Triggers**: Pull requests touching workflows, pushes to `main`, and a weekly cron at 05:05 UTC.
- **Optimizations applied**: Added a `run_branch_protection` manual-dispatch input plus downstream gating so maintainers can skip the API-heavy branch guard leg when they only need to re-run actionlint. The detect job now parses the dispatch inputs once and reuses the flag across jobs, avoiding unnecessary workflow invocations and API calls on ad-hoc lint runs.

### `health-41-repo-health.yml`
- **Purpose**: Monday sweep for stale branches/PRs with rate-limit awareness.
- **Highlights**: Skips automatically if API quota drops below 2,000 to avoid starving keepalive; writes summaries to `GITHUB_STEP_SUMMARY`.
- **Next steps**: None; consider wiring summary output into `/Projects` tracker if we want historical trends.

### `health-42-actionlint.yml`
- **Purpose**: Central actionlint runner (v1.7.3) with reviewdog integration.
- **Observations**: Supports workflow_call + manual dispatch + PR review. Cache plumbing + allowlist already in place.
- **Next steps**: Review actionlint/reviewdog version pins quarterly; no additional optimizations needed right now.

### `health-43-ci-signature-guard.yml`
- **Purpose**: Ensures `pr-00-gate` stays wired to `signature-verify` fixtures whenever guard logic changes.
- **Next steps**: None — minimal job that feeds summaries through `health_summarize.py`.

### `health-44-gate-branch-protection.yml`
- **Purpose**: Enforces and verifies required contexts for the default branch using `tools/enforce_gate_branch_protection.py`.
- **Observations**: Supports both workflow_call (for reuse) and PR events. Admin token optional but required for enforcement.
- **Next steps**: None beyond ensuring `BRANCH_PROTECTION_TOKEN` remains configured; snapshots already restored post-run.

### `health-50-security-scan.yml`
- **Purpose**: CodeQL Python scan on push/PR plus weekly schedule.
- **Next steps**: None — continues to run with PAT fallback order; we can revisit languages if repo expands.

### `health-67-integration-sync-check.yml`
- **Purpose**: Validates `Workflows-Integration-Tests` stays aligned with template workflows + `autofix-versions.env`.
- **Observations**: Automatically files `integration-sync` drift issues with clear action lists.
- **Next steps**: Factor repo list parsing (currently shell/grep) into a helper script shared with related workflows.

### `health-68-consumer-sync-drift.yml`
- **Purpose**: Compares registered consumer repos against the template files and opens/updates `consumer-sync` drift issues.
- **Next steps**: Same repo list parsing refactor as above; otherwise healthy.

### `health-70-validate-sync-manifest.yml`
- **Purpose**: Enforces that templates, prompts, scripts, and workflows are represented in `.github/sync-manifest.yml`.
- **Observation**: Uses inline Python identical to `scripts/validate_template_completeness.py` (see health-73). Opportunity to convert both workflows to call the shared script instead of embedding almost-identical validation logic.

### `health-71-sync-health-check.yml`
- **Purpose**: Daily monitor for the `maint-68-sync-consumer-repos` workflow; creates/updates GitHub issues when the sync fails repeatedly or goes stale.
- **Next steps**: None — leverages Octokit + grouped outputs effectively.

### `health-72-template-sync.yml`
- **Purpose**: Ensures `.github/scripts/**/*.js` in the repo stay synced to `templates/consumer-repo/.github/scripts`.
- **Extras**: Autocommits template deltas back onto PR branches.
- **Next steps**: None; script is already pip-installing `pyyaml` and re-using `validate_template_sync.py`.

### `health-73-template-completeness.yml`
- **Purpose**: Runs `scripts/validate_template_completeness.py --strict` on pushes/PRs.
- **Next steps**: Merge with `health-70` (same validation domain) or at least shift both to use the script rather than duplicating Python inline.

### `health-74-template-drift.yml`
- **Purpose**: Compares production `agents-*` workflows with their template counterparts and warns if they diverge by >50 lines.
- **Next steps**: After the outstanding drift is cleared, flip the workflow to fail instead of warn so regressions are blocked earlier.

### `health-75-api-rate-diagnostic.yml`
- **Purpose**: Every 30 minutes, reports rate-limit usage across all configured PATs and GitHub Apps; optionally hydrates historical summaries.
- **Next steps**: Leave in place; ensure summaries are rotated/archived so the `Summary` tab does not balloon indefinitely.

### `health-claude-cli-auth-debug.yml`
- **Purpose**: Manual debugging harness for the Claude Code CLI auth path (explicitly labelled “delete after debugging”).
- **Recommendation**: Move to `archives/` or delete once Claude auth is stable; keeping it in active health workflows dilutes the signal.

### `health-codex-auth-check.yml`
- **Purpose**: Twice-daily guard that inspects `CODEX_AUTH_JSON` JWT expiry, filing `auth-expiring` issues before tokens lapse.
- **Next steps**: None — script already masks secrets and respects `force_check`.

### `health-keepalive-auth-diagnostic.yml`
- **Purpose**: Manual runner that validates GitHub App PATs (WORKFLOWS_APP/KEEPALIVE_APP) and Claude auth secrets end-to-end.
- **Recommendation**: Similar to the Claude CLI debug workflow, consider relocating it to a diagnostics folder so health workflows remain strictly automated monitors.

### `health-keepalive-e2e.yml`
- **Purpose**: Validates keepalive orchestration logic and (optionally) executes a real Codex CLI ping when labeled with `e2e:codex-ping`.
- **Next steps**: None — provides strong coverage for keepalive loop regression testing.
