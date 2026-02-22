# Workflow Review Checklist
This checklist will track optimization, consolidation, or archival work for every workflow under `.github/workflows`. Mark each workflow as you finish reviewing it and capture notes on required changes.

| Review | Workflow | Notes |
| --- | --- | --- |
| [ ] | `agents-63-issue-intake.yml` | |
| [ ] | `agents-64-verify-agent-assignment.yml` | |
| [ ] | `agents-70-orchestrator.yml` | |
| [ ] | `agents-71-codex-belt-dispatcher.yml` | |
| [ ] | `agents-72-codex-belt-worker-dispatch.yml` | |
| [ ] | `agents-72-codex-belt-worker.yml` | |
| [ ] | `agents-73-codex-belt-conveyor.yml` | |
| [ ] | `agents-auto-label.yml` | |
| [ ] | `agents-auto-pilot.yml` | |
| [ ] | `agents-autofix-dispatcher.yml` | |
| [ ] | `agents-autofix-loop.yml` | |
| [ ] | `agents-belt-conveyor.yml` | |
| [ ] | `agents-belt-dispatcher.yml` | |
| [ ] | `agents-belt-worker.yml` | |
| [ ] | `agents-bot-comment-handler.yml` | |
| [ ] | `agents-capability-check.yml` | |
| [ ] | `agents-debug-issue-event.yml` | |
| [ ] | `agents-decompose.yml` | |
| [ ] | `agents-dedup.yml` | |
| [ ] | `agents-guard.yml` | |
| [ ] | `agents-issue-optimizer.yml` | |
| [ ] | `agents-keepalive-branch-sync.yml` | |
| [ ] | `agents-keepalive-dispatch-handler.yml` | |
| [ ] | `agents-keepalive-loop-reporter.yml` | |
| [ ] | `agents-keepalive-loop.yml` | |
| [ ] | `agents-moderate-connector.yml` | |
| [ ] | `agents-pr-meta-v4.yml` | |
| [ ] | `agents-verifier.yml` | |
| [ ] | `agents-verify-to-issue-v2.yml` | |
| [ ] | `agents-verify-to-issue.yml` | |
| [ ] | `agents-verify-to-new-pr-autopilot.yml` | |
| [ ] | `agents-verify-to-new-pr.yml` | |
| [ ] | `agents-weekly-metrics.yml` | |
| [ ] | `autofix.yml` | |
| [x] | `health-40-repo-selfcheck.yml` | Weekly label + branch-protection snapshot still valuable; consider deduping shared helper scripts if more health jobs need the same token plumbing. |
| [x] | `health-40-sweep.yml` | Keeps actionlint + guard coverage; manual runs can now skip guard to save API calls via `run_branch_protection=false`. |
| [x] | `health-41-repo-health.yml` | Added manual inputs to skip branch/PR scans and fixed the env wiring so dispatch overrides no longer break scheduled runs. |
| [x] | `health-42-actionlint.yml` | Removed unused GitHub App token mint so lint reruns skip an extra API call. |
| [x] | `health-43-ci-signature-guard.yml` | Signature fixtures now verified without minting an extra GitHub App token each run. |
| [x] | `health-44-gate-branch-protection.yml` | Removed redundant GitHub App token mint; enforcement already uses `BRANCH_PROTECTION_TOKEN`. |
| [x] | `health-50-security-scan.yml` | Dropped redundant GitHub App token mint; CodeQL already uses PAT fallback chain. |
| [x] | `health-67-integration-sync-check.yml` | Manual runs can toggle CI/version/input checks to avoid unnecessary clone/compare passes. |
| [x] | `health-68-consumer-sync-drift.yml` | Shared helper now lists registered repos, removing inline parsing + easing reuse. |
| [x] | `health-70-validate-sync-manifest.yml` | Switched to shared validator script (now emits summaries + reuse with Health 73). |
| [x] | `health-71-sync-health-check.yml` | Shares the consumer repo helper + no longer mints an app token; only the needed checks run per dispatch knobs. |
| [ ] | `health-72-template-sync.yml` | Review pending (no workflow updates landed yet). |
| [x] | `health-73-template-completeness.yml` | Already uses the shared validator script; dropped the unused GitHub App token mint. |
| [x] | `health-74-template-drift.yml` | Drift mapping now includes every agents workflow; still warning-only until residual drift is cleared. |
| [x] | `health-75-api-rate-diagnostic.yml` | Hourly snapshots only; consumer repo scans + load-sharing/access probes now manual inputs to avoid constant PAT/app churn, and the alert job finally reads the correct summary keys. |
| [x] | `health-claude-cli-auth-debug.yml` | Archived under `archives/diagnostics/` so the active health roster only contains automated monitors. |
| [x] | `health-codex-auth-check.yml` | Removed the extra GitHub App token mint so the twice-daily expiry check only makes the issue list/create calls it actually needs. |
| [x] | `health-keepalive-auth-diagnostic.yml` | Archived alongside the Claude CLI diagnostic so the health roster only tracks automated monitors; manual keepalive auth drills now live under `archives/diagnostics/`. |
| [x] | `health-keepalive-e2e.yml` | Dropped the duplicate GitHub App token mints so orchestration-only runs stick to the default installation token while keeping the Codex ping path unchanged. |
| [x] | `maint-39-test-llm-providers.yml` | Manual LLM credential test no longer mints a GitHub App token or overrides checkout auth, so the diagnostic run stays lightweight. |
| [x] | `maint-45-cosmetic-repair.yml` | Dropped the App token mint and only create PRs when not in dry-run mode to save API calls. |
| [x] | `maint-46-post-ci.yml` | Only boots the helper checkout + token-balanced client when Gate's summary is missing, removing the extra app-token mint. |
| [x] | `maint-47-disable-legacy-workflows.yml` | Removed the unused App-token mint; the disable helper now relies on the default workflow token only. |
| [x] | `maint-50-tool-version-check.yml` | Dropped the app-token mint + duplicate checkout; now relies on the default token + load-balanced client for issuing updates. |
| [x] | `maint-51-dependency-refresh.yml` | Removed the extra App token mint; dependency refresh now relies on the default workflow token for checkout + PR pushes. |
| [x] | `maint-52-sync-dev-versions.yml` | Removed all App-token mints and now reuse `list_registered_consumer_repos.py` for repo discovery. |
| [x] | `maint-52-validate-workflows.yml` | Removed the App-token mint; actionlint now runs with repo-only access since it never hits the API. |
| [x] | `maint-60-release.yml` | Floating-tag update + release now uses only the default token (removed the App-token mint). |
| [x] | `maint-61-create-floating-v1-tag.yml` | Deprecated fallback—removed the redundant App-token mint; consider archiving since maint-73 owns floating tags. |
| [x] | `maint-62-integration-consumer.yml` | Removed the extra App-token mint; issue updates now rely on the reusable API client already in the job. |
| [x] | `maint-65-sync-label-docs.yml` | Reused the registered-repo helper and dropped the App-token mint for the doc sync. |
| [x] | `maint-66-monthly-audit.yml` | Dropped the App-token mint + redundant npm install; audit uses the shared API client only. |
| [x] | `maint-68-sync-consumer-repos.yml` | Removed all App-token mints; sync jobs rely on PATs + the shared API client now. |
| [x] | `maint-69-sync-integration-repo.yml` | Removed the App-token mint; integration sync now relies on the default token + PAT used for pushes. |
| [x] | `maint-69-sync-labels.yml` | Removed the App-token mint + duplicate checkout and now reuse the registered-repo helper for targets. |
| [x] | `maint-70-fix-integration-formatting.yml` | Uses the shared API client + PAT discovery; skips safely when no integration token is available. |
| [x] | `maint-71-auto-fix-integration.yml` | Uses the shared API client + PAT discovery and skips safely when no integration token exists. |
| [x] | `maint-71-merge-sync-prs.yml` | Uses the shared repo helper + PATs; no App-token mints and cleaner repo parsing. |
| [x] | `maint-72-fix-pr-body-conflicts.yml` | Uses shared repo list + PAT detection; skips safely when no push token exists. |
| [x] | `maint-73-refresh-reusable-tags.yml` | Deprecated; workflow now exits immediately with a notice instead of touching tags. |
| [x] | `maint-74-ledger-base-sync.yml` | No longer mints an App token; relies on the default token + shared client. |
| [x] | `maint-80-langsmith-metrics-dashboard.yml` | Reviewed; no changes needed—the dashboard already aggregates autopilot artifacts + refreshes docs weekly. |
| [x] | `maint-auto-update-pypi-versions.yml` | Removed the App-token mint; workflow now relies on the default token for repo operations. |
| [x] | `maint-coverage-guard.yml` | Removed rate-limit + guard job App-token mints; shared API client handles retries. |
| [x] | `maint-dependabot-auto-label.yml` | Reviewed – already minimal (gh CLI adds label via default token). |
| [x] | `maint-dependabot-auto-lock.yml` | Reviewed – regenerates requirements.lock via uv when Dependabot touches pyproject. |
| [ ] | `maint-dependabot-weekly-sweep.yml` | |
| [ ] | `maint-sync-action-versions.yml` | |
| [ ] | `maint-sync-env-from-pyproject.yml` | |
| [ ] | `pr-00-gate.yml` | |
| [ ] | `pr-11-ci-smoke.yml` | |
| [ ] | `reusable-10-ci-python.yml` | |
| [ ] | `reusable-11-ci-node.yml` | |
| [ ] | `reusable-12-ci-docker.yml` | |
| [ ] | `reusable-16-agents.yml` | |
| [ ] | `reusable-18-autofix.yml` | |
| [ ] | `reusable-20-pr-meta.yml` | |
| [ ] | `reusable-70-orchestrator-init.yml` | |
| [ ] | `reusable-70-orchestrator-main.yml` | |
| [ ] | `reusable-agents-issue-bridge.yml` | |
| [ ] | `reusable-agents-verifier.yml` | |
| [ ] | `reusable-bot-comment-handler.yml` | |
| [ ] | `reusable-claude-run.yml` | |
| [ ] | `reusable-codex-run.yml` | |
| [ ] | `reusable-pr-context.yml` | |
| [ ] | `selftest-ci.yml` | |
| [ ] | `selftest-reusable-ci.yml` | |
