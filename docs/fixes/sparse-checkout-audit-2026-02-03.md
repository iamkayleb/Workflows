# Sparse Checkout Dependency Audit (2026-02-03)

## Summary

An audit of workflows using `.github/scripts/github-api-with-retry.js` found missing sparse-checkout dependencies for `token_load_balancer.js`. This caused startup failures when token-aware retry logic executed.

**Status:** Fixed in the main Workflows repository by adding `token_load_balancer.js` wherever `github-api-with-retry.js` appears in sparse-checkout blocks.

## Root Cause

`github-api-with-retry.js` requires `./token_load_balancer` at runtime. Sparse checkouts that included the parent file but omitted `token_load_balancer.js` triggered module load failures.

## Fix Applied

All affected workflows in the main Workflows repository now include:

- `.github/scripts/github-api-with-retry.js`
- `.github/scripts/token_load_balancer.js`

## Spreadsheet (Affected Workflows)

| Repository | Workflow File | Status |
| --- | --- | --- |
| Workflows | agents-63-issue-intake.yml | Fixed |
| Workflows | agents-64-verify-agent-assignment.yml | Fixed |
| Workflows | agents-71-codex-belt-dispatcher.yml | Fixed |
| Workflows | agents-73-codex-belt-conveyor.yml | Fixed |
| Workflows | agents-autofix-loop.yml | Fixed |
| Workflows | agents-bot-comment-handler.yml | Fixed |
| Workflows | agents-capability-check.yml | Fixed |
| Workflows | agents-decompose.yml | Fixed |
| Workflows | agents-dedup.yml | Fixed |
| Workflows | agents-guard.yml | Fixed |
| Workflows | agents-moderate-connector.yml | Fixed |
| Workflows | agents-verifier.yml | Fixed |
| Workflows | agents-verify-to-issue-v2.yml | Fixed |
| Workflows | agents-verify-to-new-pr.yml | Fixed |
| Workflows | agents-weekly-metrics.yml | Fixed |
| Workflows | health-codex-auth-check.yml | Fixed |
| Workflows | maint-46-post-ci.yml | Fixed |
| Workflows | maint-50-tool-version-check.yml | Fixed |
| Workflows | maint-62-integration-consumer.yml | Fixed |
| Workflows | maint-69-sync-labels.yml | Fixed |
| Workflows | maint-72-fix-pr-body-conflicts.yml | Fixed |
| Workflows | maint-coverage-guard.yml | Fixed |
| Workflows | reusable-16-agents.yml | Fixed |
| Workflows | reusable-70-orchestrator-init.yml | Fixed |
| Workflows | reusable-70-orchestrator-main.yml | Fixed |
| Workflows | reusable-agents-issue-bridge.yml | Fixed |
| Workflows | reusable-bot-comment-handler.yml | Fixed |

## Cross-Repo Impact

The consumer-template workflows contained the same sparse-checkout pattern. Updating the main Workflows repo ensures downstream syncs carry the fix to:

- Manager-Database
- Trend_Model_Project
- templates/consumer-repo

## Verification

A dependency scan of all scripts under `.github/scripts` confirmed no other missing dependencies remain after the fix.
