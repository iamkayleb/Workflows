# Maintenance Workflow Review — 2026-02-22

This log mirrors the health-workflow audit but targets the `maint-*` workflows. Each entry captures the current trigger model, purpose, optimizations, and any follow-up actions so we can track progress while iterating on the maintenance suite.

## Workflow Notes

### `maint-39-test-llm-providers.yml`
- **Purpose**: Manual dispatch harness that sanity-checks GitHub Models and OpenAI provider keys through `tools.llm_provider` helpers before running keepalive or agent updates.
- **Optimizations applied (2026-02-22)**: Dropped the unnecessary GitHub App token mint + checkout override, since the workflow only runs standalone provider checks and never calls the GitHub API directly. This keeps the manual test lightweight and avoids consuming app credentials just to read the repo.
- **Next steps**: Consider extending the summary step to reflect which providers were exercised (and why a provider was skipped) instead of always reporting success.
