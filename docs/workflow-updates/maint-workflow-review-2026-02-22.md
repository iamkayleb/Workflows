# Maintenance Workflow Review — 2026-02-22

This log mirrors the health-workflow audit but targets the `maint-*` workflows. Each entry captures the current trigger model, purpose, optimizations, and any follow-up actions so we can track progress while iterating on the maintenance suite.

## Workflow Notes

### `maint-39-test-llm-providers.yml`
- **Purpose**: Manual dispatch harness that sanity-checks GitHub Models and OpenAI provider keys through `tools.llm_provider` helpers before running keepalive or agent updates.
- **Optimizations applied (2026-02-22)**: Dropped the unnecessary GitHub App token mint + checkout override, since the workflow only runs standalone provider checks and never calls the GitHub API directly. This keeps the manual test lightweight and avoids consuming app credentials just to read the repo.
- **Next steps**: Consider extending the summary step to reflect which providers were exercised (and why a provider was skipped) instead of always reporting success.

### `maint-45-cosmetic-repair.yml`
- **Purpose**: Manual pytest + hygiene runner that executes `scripts/ci_cosmetic_repair.py` to auto-fix formatting-only failures and open a helper PR when changes exist.
- **Optimizations applied (2026-02-22)**:
  - Removed the redundant GitHub App token mint + checkout override; the workflow already has `contents:write` and only needs the default token to push the cosmetic branch, so skipping the mint drops an API call from every run.
  - Guarded the PR-creation step behind `dry-run != true` so exploratory runs don't waste time/requests trying to open a no-op helper PR.
- **Next steps**: Extend the run summary to include whether pytest failed and whether fixes were applied so dispatchers know if a manual follow-up is still required.
