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

### `maint-46-post-ci.yml`
- **Purpose**: Gate follower that rebuilds/post the coverage + CI summary whenever the Gate run's own summary leg fails or is missing, then reapplies the commit status.
- **Optimizations applied (2026-02-22)**:
  - Removed the unconditional GitHub App token mint plus the always-on checkout; the workflow now inspects the Gate summary first and only checks out helper scripts if recovery is actually required.
  - Moved the `setup-api-client` install behind the same condition so we only install Octokit dependencies and load-balance additional tokens when there is real recovery work to do.
- **Next steps**: Hook the coverage artifact download into `run-id` detection for other required workflows so Maint 46 can heal more than just Gate summaries.

### `maint-47-disable-legacy-workflows.yml`
- **Purpose**: Manual dispatch shim that disables legacy workflows left in the Actions UI after archival, with dry-run and allowlist overrides.
- **Optimizations applied (2026-02-22)**: Removed the redundant GitHub App token mint. The helper script only reads repository files plus the default installation token for API writes, so minting a separate App token wasted an API call without providing extra capabilities.
- **Next steps**: Flesh out `tools/disable_legacy_workflows.py` so it actually hits the Actions REST API before re-enabling automatic disablement.

### `maint-50-tool-version-check.yml`
- **Purpose**: Weekly/manual audit that reads `autofix-versions.env`, hits PyPI for the latest formatter/test tool versions, and opens/refreshes the maintenance issue when drift exists.
- **Optimizations applied (2026-02-22)**:
  - Removed the redundant GitHub App token mint + duplicate sparse checkout; the workflow now relies on the default token and the existing `setup-api-client` load balancer for issue API traffic.
  - Simplified the GitHub Script invocation to use one checkout, keeping the repo workspace hot for both the Python env file and helper scripts.
- **Next steps**: Cache the PyPI JSON responses (or add timeouts/backoffs) so transient PyPI outages don't fail the entire run.

### `maint-51-dependency-refresh.yml`
- **Purpose**: Twice-monthly/manual dependency refresh that compiles `requirements.lock`, verifies tool pins, and (when not in dry-run) opens a helper PR with the refreshed snapshot.
- **Optimizations applied (2026-02-22)**: Removed the GitHub App token mint + checkout override so the workflow now reuses the default workflow token for both checkout and the PR helper (the run already needs `fetch-depth: 0` for branch pushes).
- **Next steps**: Capture the normalized compile output during the upgrade step so the verification leg can diff against a temp file instead of running `uv pip compile` twice.

### `maint-52-sync-dev-versions.yml`
- **Purpose**: Keeps consumer repos' dev-tool pins aligned with `autofix-versions.env` by verifying versions, building a repo matrix, and pushing PRs via PAT-backed clones.
- **Optimizations applied (2026-02-22)**:
  - Dropped all GitHub App token mint steps; the workflow now relies on the existing PAT inputs (`OWNER_PR_PAT`/`SERVICE_BOT_PAT`) and the default token for read-only operations.
  - Replaced the inline YAML parsing logic with the shared `scripts/list_registered_consumer_repos.py` helper so repo discovery stays consistent with other health/maint workflows.
- **Next steps**: Emit a structured run summary that lists which repos were updated vs. skipped (pyproject missing) to make dry-run reviews faster.
