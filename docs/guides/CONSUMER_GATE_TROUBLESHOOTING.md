# Consumer Repo Gate Troubleshooting Guide

> Comprehensive record of all frictions encountered getting the Gate workflow
> to pass in consumer repos after sync, and how each was resolved.
> Written March 2026 after fixing Gate failures on `iamkayleb/Workflows-Integration-Tests` PR #34.

---

## Background

The **sync workflow** (`maint-68-sync-consumer-repos.yml`) pushes template files
from `templates/consumer-repo/` to registered consumer repos. After syncing,
the consumer repo's **Gate workflow** (`pr-00-gate.yml`) runs on the resulting
sync PR. Multiple Gate jobs failed because the Gate template assumed files that
only exist in the Workflows repo would also be present in consumer repos.

---

## Error 1: `gh: To use GitHub CLI... set the GH_TOKEN environment variable`

**Job:** Sync workflow matrix jobs (all repos)
**Exit code:** 4

### Root Cause

The sync workflow set `REPO_TOKEN` from `secrets.OWNER_PR_PAT || secrets.SERVICE_BOT_PAT`.
In forks, both secrets were empty, so `REPO_TOKEN` was blank. The `gh` CLI
requires a token and refuses to run without one.

### Fix

Added `github.token` as a fallback so clone/read operations succeed even
without PATs:

```yaml
REPO_TOKEN: ${{ secrets.OWNER_PR_PAT || secrets.SERVICE_BOT_PAT || github.token }}
```

Also added a **"Verify cross-repo token"** step before PR creation that fails
early with a clear error if no PAT is available (since `github.token` can't
create cross-repo PRs):

```yaml
- name: Verify cross-repo token
  if: steps.sync.outputs.has_changes == 'true' && inputs.dry_run != true
  run: |
    if [ -z "${{ secrets.OWNER_PR_PAT }}" ] && [ -z "${{ secrets.SERVICE_BOT_PAT }}" ]; then
      echo "::error::No cross-repo PAT available."
      exit 1
    fi
```

**Commit:** `5600b34`

---

## Error 2: `GraphQL: Resource not accessible by personal access token (createPullRequest)`

**Job:** Sync workflow — PR creation step

### Root Cause

Fine-grained PATs (`github_pat_*`) have known incompatibilities with GitHub's
GraphQL `createPullRequest` mutation. The `gh pr create` command uses GraphQL
internally.

### Fix

Switched from a fine-grained PAT to a **classic PAT** (`ghp_*`) with `repo`
scope. Classic PATs have full GraphQL API support.

**Key lesson:** Always use classic PATs for workflows that call `gh pr create`.
Fine-grained PATs may work for REST API calls but fail on GraphQL mutations.

---

## Error 3: `Head sha can't be blank, Base sha can't be blank, No commits between main and <branch>`

**Job:** Sync workflow — PR creation step
**Context:** The sync workflow uses `--depth=1` (shallow clone)

### Root Cause

`gh pr create` in a shallow clone cannot infer the base branch or compute
SHAs for the PR. The shallow clone doesn't have enough history for GitHub's
branch comparison logic.

### Fix

Added explicit `--base main` and `--repo` flags to `gh pr create`:

```yaml
gh pr create \
  --head "$branch_name" \
  --base main \
  --repo "${{ matrix.repo }}" \
  --title "chore: sync workflow templates" \
  --body "$pr_body"
```

**Key lesson:** Always pass `--base` and `--repo` explicitly when running
`gh pr create` in shallow clones or cross-repo contexts.

**Commit:** `325028c`

---

## Error 4: `could not add label: 'sync' not found`

**Job:** Sync workflow — PR creation step

### Root Cause

`gh pr create --label "sync,automated"` fails the entire command if the
labels don't exist in the target repo — even though the PR itself was
successfully created.

### Fix

Separated label application from PR creation. Labels are now added via
`gh pr edit` with error suppression:

```yaml
pr_url=$(gh pr create \
  --head "$branch_name" \
  --base main \
  --repo "${{ matrix.repo }}" \
  --title "chore: sync workflow templates" \
  --body "$pr_body")

echo "Created PR: $pr_url"

# Add labels separately so missing labels don't fail the step
gh pr edit "$pr_url" --add-label "sync" 2>/dev/null || echo "::warning::Could not add 'sync' label"
gh pr edit "$pr_url" --add-label "automated" 2>/dev/null || echo "::warning::Could not add 'automated' label"
```

**Commit:** `0abbd11`

---

## Error 5: `github-scripts-tests` Gate job failure

**Job:** `github-scripts-tests` in consumer repo Gate
**Error:** `node --test .github/scripts/__tests__/*.test.js` — no test files found (glob fails)
and `pytest tests/workflows/github_scripts` — directory not found

### Root Cause

The Gate template hardcoded two test commands:
1. `node --test .github/scripts/__tests__/*.test.js` — 60+ JS test files exist in the Workflows repo but are **not synced** to consumer repos
2. `pytest tests/workflows/github_scripts` — Python test directory exists only in the Workflows repo

### Fix

Wrapped both commands in existence guards:

```yaml
- name: Run JS tests (if present)
  run: |
    if ls .github/scripts/__tests__/*.test.js 1>/dev/null 2>&1; then
      node --test .github/scripts/__tests__/*.test.js
    else
      echo "No JS test files found in .github/scripts/__tests__/; skipping."
    fi

- name: Run Python workflow tests (if present)
  run: |
    if [ -d tests/workflows/github_scripts ]; then
      python -m pip install --upgrade pip pytest requests
      pytest tests/workflows/github_scripts
    else
      echo "No Python workflow tests found in tests/workflows/github_scripts/; skipping."
    fi
```

Applied to both `.github/workflows/pr-00-gate.yml` and `templates/consumer-repo/.github/workflows/pr-00-gate.yml`.

**Commit:** `d4cdedc`

---

## Error 6: `issue-consistency` Gate job failure

**Job:** `issue-consistency` in consumer repo Gate
**Error:** `python scripts/check_issue_consistency.py` — file not found

### Root Cause

`scripts/check_issue_consistency.py` exists in the Workflows repo but is
**not listed in the sync manifest** and therefore never synced to consumer repos.
The Gate template called it unconditionally.

### Fix

Added an existence guard:

```yaml
- name: Check issue number consistency
  run: |
    if [ -f scripts/check_issue_consistency.py ]; then
      python scripts/check_issue_consistency.py
    else
      echo "scripts/check_issue_consistency.py not found; skipping."
    fi
```

**Commit:** `d4cdedc`

---

## Error 7: `lint-ruff` Gate job failure

**Job:** `lint-ruff` (inside `python-ci` reusable workflow)
**Error:** Ruff flagging lines 89-100 characters as too long

### Root Cause

The reusable CI workflow runs:
- `black --check --line-length 100 ...` (explicit CLI flag — works fine)
- `ruff check ...` (**no** `--line-length` flag — relies on repo config)

Without a `pyproject.toml`, ruff defaults to `line-length = 88`. Any Python
line between 89-100 characters would pass black but **fail ruff**.

Consumer repos had no `pyproject.toml` because it wasn't in the sync manifest.

### Fix

Created `templates/consumer-repo/pyproject.toml` with lint/format config
matching the Workflows repo:

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "C4", "UP", "SIM"]
ignore = ["E501"]

[tool.ruff.lint.isort]
known-third-party = ["scripts", "tools"]

[tool.black]
line-length = 100
target-version = ["py311", "py312"]

[tool.isort]
profile = "black"
line_length = 100
```

Added `python_config` category to sync manifest and sync workflow processing.

**Commit:** `bc49c42`

---

## Error 8: `lint-format` Gate job failure

**Job:** `lint-format` (inside `python-ci` reusable workflow)

### Root Cause

Same as Error 7 — missing `pyproject.toml` caused tool configuration
mismatches. Resolved by the same fix.

**Commit:** `bc49c42`

---

## Error 9: `python 3.11` / `python 3.12` test failures

**Job:** `python-ci / python 3.11` and `python-ci / python 3.12`
**Error:** `ModuleNotFoundError: No module named 'example'`

### Root Cause

The consumer repo has a `src/` layout (`src/example/__init__.py`) and a test
file `tests/test_example.py` that does `from example import add`. Without `src`
on the Python path, the import fails.

The synced `pyproject.toml` initially had `packages = []` (copied from the
Workflows repo which has no `src/` layout) and no `pythonpath` in pytest config.

### Fix

Updated the consumer template `pyproject.toml`:

```toml
[tool.setuptools.packages.find]
where = ["src"]

[tool.setuptools.package-dir]
"" = "src"

[tool.pytest.ini_options]
pythonpath = ["src"]
```

**Commit:** `f2af6f5`

---

## Error 10: `sync_mode: create_only` preventing fixes from reaching consumers

**Problem:** Gate template and pyproject.toml fixes wouldn't propagate to
existing consumer repos because both had `sync_mode: create_only` in the
sync manifest.

### Fix

Temporarily changed `sync_mode` to `sync` for both files, ran the sync
workflow, then reverted to `create_only`:

```yaml
# Temporary (for one sync run):
sync_mode: sync

# Permanent (after consumers updated):
sync_mode: create_only
```

**Commits:** `b57af3c` (temporary sync), `53955b1` (revert to create_only)

---

## Summary of All Commits

| Commit | Description |
|--------|-------------|
| `5600b34` | Add `github.token` fallback + verify step for cross-repo token |
| `325028c` | Add explicit `--base main` and `--repo` to `gh pr create` |
| `0abbd11` | Separate label application from PR creation |
| `d4cdedc` | Guard test and consistency steps for consumer repos |
| `bc49c42` | Add `pyproject.toml` template + sync manifest `python_config` category |
| `b57af3c` | Temporarily force-sync Gate and pyproject.toml |
| `f2af6f5` | Add `src` to setuptools and pytest pythonpath |
| `53955b1` | Revert `sync_mode` back to `create_only` |

---

---

# Part 2: Keepalive System Troubleshooting

> Issues encountered while verifying the keepalive system end-to-end on
> `iamkayleb/WIT-Standalone`. Written April 2026 after testing the full
> keepalive flow from PR comment to agent dispatch.

---

## Background

The **keepalive system** detects `@codex` comments on PRs, evaluates
pre-conditions (labels, Gate status, issue reference, repo type), and dispatches
the Agents 70 Orchestrator to continue agent work. The flow is:

```
@codex comment → agents-pr-meta.yml → reusable-20-pr-meta.yml (keepalive gate)
  → keepalive dispatch → agents-70-orchestrator.yml → agent work
```

Testing was initially done on a fork (`iamkayleb/Workflows-Integration-Tests`)
before migrating to a standalone repo (`iamkayleb/WIT-Standalone`).

---

## Error 11: `reason=keepalive-label-missing`

**Step:** Evaluate keepalive gate (in `reusable-20-pr-meta.yml`)
**Dispatch summary:** `ok=false reason=gate-failed`

### Root Cause

The PR was missing the `agents:keepalive` label. The keepalive gate in
`keepalive_gate.js` requires this label before evaluating any other conditions.
The dispatch summary normalises this to `gate-failed`, which can be misleading.

### Fix

Add the `agents:keepalive` label to the PR. Create the label first if it
doesn't exist in the consumer repo.

---

## Error 12: `reason=no-human-activation`

**Step:** Evaluate keepalive gate
**Context:** `agents:keepalive` label present, but no agent alias labels

### Root Cause

The keepalive gate extracts agent aliases from labels with the `agent:` prefix
(e.g., `agent:codex`). Without any agent alias labels,
`shouldCheckHumanActivation` is false, and the gate skips human activation
detection entirely.

### Fix

Add the `agent:codex` label (or whichever agent you're activating) to the PR.
The gate uses these labels to build mention patterns like `@codex` for
scanning PR comments.

---

## Error 13: `reason=fork-pr`

**Step:** Evaluate keepalive gate (in `agents_pr_meta_keepalive.js`)
**Line:** ~637 in `agents_pr_meta_keepalive.js`

### Root Cause

The keepalive script checks `headRepo.fork` via the GitHub API. If the PR's
head repo is a GitHub fork (`repo.fork = true`), dispatch is blocked for
security reasons. This is a hard block — fork repos cannot run keepalive.

### Fix

Use a **standalone (non-fork) repo** as the consumer. If you forked the
integration tests repo, create a new repo via GitHub's "Import repository"
feature instead. Imported repos have `fork = false`.

**Key lesson:** GitHub's `fork` flag is permanent and cannot be changed.
The only workaround is to create a standalone repo.

---

## Error 14: Bot comment cancelling human comment's workflow run

**Step:** `agents-pr-meta.yml` triggered by `@codex` comment
**Symptom:** The workflow run from your comment is cancelled by a newer run

### Root Cause

The `agents-pr-meta.yml` has a concurrency group with
`cancel-in-progress: true`. When you post `@codex`, it triggers a workflow run.
If a bot then comments on the same PR (e.g., posting a status update), that
triggers a new `issue_comment` event, which starts a new run that cancels yours.

### Fix

The concurrency group in the consumer template uses `comment.id` for
`issue_comment` events, so each comment gets its own concurrency group. If
you're using an older template, update to the latest `agents-pr-meta.yml`.
Alternatively, post `@codex` again after the bot has finished commenting.

---

## Error 15: `reason=missing-issue-reference`

**Step:** Detect keepalive from activation (in `agents_pr_meta_keepalive.js`)

### Root Cause

The keepalive script requires the PR to be linked to an issue. If no issue
reference is found in the PR title or body, dispatch is blocked.

### Fix

Link the PR to an issue by either:
- Adding `Fix #N` or `Closes #N` to the PR title
- Adding `Closes #N` to the PR body

Create an issue first if one doesn't exist.

---

## Error 16: `forbidden-token` (GITHUB_TOKEN fallback)

**Step:** Dispatch keepalive orchestrator (in `reusable-20-pr-meta.yml`)
**Log output:**
```
Token registry initialized with 1 tokens
Selected token: GITHUB_TOKEN (4989 remaining, 99.8% capacity)
Error: forbidden-token
```

### Root Cause

The orchestrator script at `agents_pr_meta_orchestrator.js` line 378 checks
for PAT secrets:

```js
const token = secrets.AGENTS_AUTOMATION_PAT || secrets.ACTIONS_BOT_PAT || secrets.SERVICE_BOT_PAT;
```

These are passed as booleans from environment variables. If the env vars are
empty (secrets not reaching the workflow), all booleans are `false`, and the
check fails.

`GITHUB_TOKEN` cannot trigger `workflow_dispatch` events — a PAT with `repo`
and `workflow` scopes is required.

### Fix

1. Add a classic PAT with `repo` and `workflow` scopes as `SERVICE_BOT_PAT`
   in the **consumer repo's** repository secrets (Settings → Secrets → Actions)
2. Ensure the PAT belongs to an account that has push access to the consumer repo
3. Do **not** use PATs from the upstream Workflows repo — they authenticate as
   a different user and won't have access to your repos

---

## Error 17: Reusable workflow reference pointing to wrong repo

**Step:** Consumer repo's `agents-pr-meta.yml` calling reusable workflow
**Symptom:** Secrets not reaching the reusable workflow; scripts checked out
from wrong repo

### Root Cause

The consumer template references `stranske/Workflows` for reusable workflows:

```yaml
uses: stranske/Workflows/.github/workflows/reusable-20-pr-meta.yml@main
```

If you're using a fork of the Workflows repo (e.g., `iamkayleb/Workflows`),
the consumer should reference your fork instead. While `secrets: inherit`
passes secrets from the caller regardless of where the reusable workflow lives,
the reusable workflow also checks out scripts from the referenced repo, which
may not match your fork's scripts.

### Fix

Update all reusable workflow references in the consumer's workflow files to
point to your Workflows fork:

```yaml
uses: iamkayleb/Workflows/.github/workflows/reusable-20-pr-meta.yml@main
```

---

## Error 18: `agents-70-orchestrator.yml` missing from consumer repo

**Step:** Dispatch keepalive orchestrator
**Error:** `Failed to dispatch agents-70-orchestrator.yml after 1 attempts (primary-token): Resource not accessible by integration`

### Root Cause

The keepalive dispatch script in `agents_pr_meta_orchestrator.js` triggers
`agents-70-orchestrator.yml` via `workflow_dispatch` on the **consumer repo**.
But this workflow file only exists in the Workflows repo — it's not included
in the consumer template or sync manifest.

### Fix

Copy `agents-70-orchestrator.yml` from the Workflows repo to the consumer
repo at `.github/workflows/agents-70-orchestrator.yml`. Update the local
reusable workflow references to cross-repo references:

```yaml
# From (local, only works in Workflows repo):
uses: ./.github/workflows/reusable-70-orchestrator-init.yml

# To (cross-repo, for consumer repos):
uses: iamkayleb/Workflows/.github/workflows/reusable-70-orchestrator-init.yml@main
```

Don't forget the `@main` suffix — cross-repo refs require a version/branch.

**Note:** This is a gap in the consumer template. The orchestrator template
(`agents-orchestrator.yml`) uses `reusable-16-agents.yml`, which is a
different workflow. The `agents-70-orchestrator.yml` variant is what the
keepalive dispatch targets.

---

## Error 19: `keepalive_instruction_segment.js` not found

**Step:** Execute / Prepare keepalive round (in `agents-70-orchestrator.yml`)
**Error:** `Cannot find module '/home/runner/work/WIT-Standalone/WIT-Standalone/scripts/keepalive_instruction_segment.js'`

### Root Cause

The orchestrator's "Extract instruction payload" step requires
`scripts/keepalive_instruction_segment.js` in the consumer repo. This script
exists in the Workflows repo at `scripts/keepalive_instruction_segment.js`
but is not in the consumer template or sync manifest.

### Fix

Copy `scripts/keepalive_instruction_segment.js` from the Workflows repo to
the consumer repo at the same path: `scripts/keepalive_instruction_segment.js`.

**Important:** The file must be on the `main` branch. The orchestrator runs
on `main` (dispatched via `workflow_dispatch`), not on the PR branch.

---

## Error 20: `@octokit/rest` and `@octokit/auth-app` import failures

**Step:** Detect keepalive comments (token load balancer)
**Error:** `Cannot find package '@octokit/rest' imported from .../token_load_balancer.js`
**Severity:** Warning (non-blocking)

### Root Cause

The `setup-api-client` action installs `@octokit/*` packages, but the token
load balancer script may attempt imports before the packages are fully
available, or from a different path than where they were installed.

The `@octokit/auth-app` failures are for GitHub App token minting
(`KEEPALIVE_APP`, `WORKFLOWS_APP`). If those App secrets are from the upstream
repo, they won't work on your consumer repo.

### Fix

These warnings are **non-blocking** — the system falls back to PATs when App
tokens can't be minted. No action required unless you need GitHub App
authentication. You can safely ignore these warnings as long as `SERVICE_BOT_PAT`
or `ACTIONS_BOT_PAT` is configured.

---

## Keepalive Verification Checklist

After resolving all the above issues, the successful keepalive flow is:

1. **PR setup:** PR has `agents:keepalive` and `agent:codex` labels, linked
   to an issue (`Fix #N` in title)
2. **Gate passes:** `pr-00-gate.yml` completes successfully on the PR
3. **Human activation:** Post `@codex` comment on the PR
4. **PR Meta detects:** `agents-pr-meta.yml` triggers, calls
   `reusable-20-pr-meta.yml`
5. **Keepalive gate:** Evaluates to `ok=true reason=ok`
6. **Dispatch:** Triggers `agents-70-orchestrator.yml` on the consumer repo
7. **Orchestrator runs:** Initialize + Execute jobs complete
8. **Agent work:** Belt dispatch triggers agent work on the PR branch

---

## Summary of Keepalive-Specific Commits

All keepalive fixes were made directly in the consumer repo
(`iamkayleb/WIT-Standalone`), not in the Workflows repo. This section
documents the consumer-side changes:

| Change | Location | Description |
|--------|----------|-------------|
| Add labels | PR settings | `agents:keepalive` and `agent:codex` labels |
| Link issue | PR title | `Fix #N` in PR title |
| Add `SERVICE_BOT_PAT` | Repo secrets | Classic PAT with `repo` + `workflow` scopes |
| Update workflow refs | `agents-pr-meta.yml` | Point to `iamkayleb/Workflows` fork |
| Add orchestrator | `.github/workflows/agents-70-orchestrator.yml` | With cross-repo refs + `@main` |
| Add script | `scripts/keepalive_instruction_segment.js` | Required by orchestrator |

---

---

# Part 3: Autofix System Troubleshooting

> Issues encountered while verifying the autofix system end-to-end on
> `iamkayleb/WIT-Standalone`. Written April 2026 after testing the full
> autofix flow from lint failure to automated fix commit.

---

## Background

The **autofix system** detects lint/format failures on PRs and automatically
pushes fix commits. The flow is:

```
Gate fails (lint-format / lint-ruff) → autofix.yml triggers via workflow_run
  → resolve context → reusable-18-autofix.yml → bot pushes fix commit
```

Autofix can also be triggered manually by adding the `autofix` or
`autofix:clean` label to a PR.

---

## Error 21: Autofix workflow not appearing in Actions sidebar

**Symptom:** `autofix.yml` exists on `main` but doesn't appear in the Actions
sidebar workflow list. No autofix runs appear.

### Root Cause

The `autofix.yml` template includes a `workflow_job` trigger:

```yaml
on:
  workflow_run:
    workflows: ["Gate", "CI", "Python CI"]
    types: [completed]
  workflow_job:
    types: [completed]
  pull_request_target:
    types:
      - labeled
```

GitHub rejects the entire workflow file when it encounters `workflow_job` as
a trigger in a regular repository context. The error is:

```
Invalid workflow file: .github/workflows/autofix.yml#L1
(Line: 23, Col: 3): Unexpected value 'workflow_job'
```

This error is **silent** — the workflow doesn't appear in the sidebar at all,
and no error is surfaced unless you navigate to a specific failed run.

### Fix

Remove the `workflow_job` trigger from `autofix.yml`:

```yaml
on:
  workflow_dispatch:    # optional, useful for testing
  workflow_run:
    workflows: ["Gate", "CI", "Python CI"]
    types: [completed]
  pull_request_target:
    types:
      - labeled
```

**Key lesson:** The `workflow_job` event is not universally supported. When
GitHub silently rejects a workflow file, it won't appear in the Actions
sidebar. Navigate to the direct URL
(`/actions/workflows/autofix.yml`) to find hidden runs with error annotations.

---

## Error 22: Autofix reusable workflow reference not found

**Symptom:** Editor shows "Unable to find reusable workflow" for the
`reusable-18-autofix.yml` reference.

### Root Cause

The consumer template defaults to `stranske/Workflows`:

```yaml
uses: stranske/Workflows/.github/workflows/reusable-18-autofix.yml@main
```

If you're using a fork (e.g., `iamkayleb/Workflows`), the reference needs
to point to your fork.

### Fix

Update the `uses:` line in the consumer's `autofix.yml`:

```yaml
uses: iamkayleb/Workflows/.github/workflows/reusable-18-autofix.yml@main
```

Also ensure your fork's `main` branch is synced with the upstream repo so
the reusable workflow file actually exists. Use GitHub's "Sync fork" button
if your fork is behind.

---

## Error 23: Autofix not triggering automatically after Gate failure

**Symptom:** Gate fails with `lint-format` and `lint-ruff` failures, but
autofix doesn't run automatically.

### Root Cause

Multiple possible causes:

1. **`autofix.yml` not on `main`**: The `workflow_run` trigger only works
   when the workflow file exists on the default branch at the time the
   upstream workflow completes.

2. **`workflow_job` trigger causing silent rejection** (see Error 21): If
   the entire file is invalid, no triggers work — including `workflow_run`
   and `pull_request_target`.

3. **Gate workflow name mismatch**: The `workflow_run` trigger specifies
   `workflows: ["Gate", "CI", "Python CI"]`. If the Gate workflow's `name:`
   field doesn't exactly match `"Gate"`, autofix won't trigger.

### Fix

1. Ensure `autofix.yml` is on `main` with the `workflow_job` trigger removed
2. Verify the Gate workflow name matches: check `pr-00-gate.yml`'s `name:` field
3. As a workaround, manually trigger by adding the `autofix` label to the PR

---

## Error 24: Resolve job fails — missing `.github/actions/setup-api-client`

**Symptom:** The resolve job in `autofix.yml` fails during the "Setup API
client" step.

### Root Cause

The resolve job checks out `.github/actions/setup-api-client` and
`.github/scripts/` from the **consumer repo itself** (not from the Workflows
repo). If these files don't exist in the consumer repo, the setup step fails.

### Fix

The consumer repo needs these files. They should be delivered via the sync
workflow. If they're missing, either:
- Run the sync workflow to deliver them
- Copy `.github/actions/setup-api-client/` and the required scripts from the
  Workflows repo

---

## Autofix Verification Checklist

After resolving all issues, the successful autofix flow is:

1. **Prerequisites:** `autofix.yml` and `autofix-versions.env` on `main`,
   `SERVICE_BOT_PAT` secret configured, `autofix` and `autofix:clean` labels exist
2. **Trigger:** Gate fails with `lint-format` or `lint-ruff` failures
   (automatic), or `autofix` label added to PR (manual)
3. **Resolve:** Autofix workflow evaluates whether the PR needs fixing
4. **Fix:** Reusable autofix workflow runs formatters (black, ruff, isort)
5. **Commit:** Bot pushes `chore(autofix): formatting/lint` commit to PR branch
6. **Comment:** Bot comments on PR listing fixed files
7. **Re-run:** Gate re-runs on the new commit; lint checks should now pass

---

## Summary of Autofix-Specific Changes

All autofix fixes were made in the consumer repo (`iamkayleb/WIT-Standalone`):

| Change | Location | Description |
|--------|----------|-------------|
| Remove `workflow_job` | `autofix.yml` `on:` section | Unsupported trigger causing silent rejection |
| Update workflow ref | `autofix.yml` `uses:` line | Point to `iamkayleb/Workflows` fork |
| Add `workflow_dispatch` | `autofix.yml` `on:` section | Optional, enables manual "Run workflow" testing |
| Create labels | Repository labels | `autofix` and `autofix:clean` |
| Sync fork | `iamkayleb/Workflows` | Ensure `reusable-18-autofix.yml` exists on `main` |

---

## Key Lessons

### Gate / Sync Lessons

1. **Gate templates must not assume Workflows-repo-only files exist in consumers.** Always guard with existence checks (`if [ -f ... ]`, `if ls ... 2>/dev/null`).

2. **Ruff relies on repo config for line-length.** Unlike black (which gets `--line-length` from the CLI), ruff has no CLI override in the reusable workflow. Consumer repos need a `pyproject.toml`.

3. **`sync_mode: create_only` blocks all updates.** When you need to push a critical fix to existing consumers, temporarily switch to `sync`, run the sync, then revert.

4. **`gh pr create` in shallow clones needs `--base` and `--repo`.** Never rely on branch inference in CI workflows that use `--depth=1`.

5. **Fine-grained PATs don't work with `gh pr create`.** Use classic PATs with `repo` scope for cross-repo PR creation.

6. **Separate label operations from PR creation.** Labels that don't exist in the target repo will fail the entire `gh pr create` command.

7. **Consumer repos with `src/` layout need `pythonpath = ["src"]` in pytest config.** Without it, test imports fail even though the package structure is correct.

### Keepalive Lessons

8. **Fork repos cannot run keepalive.** The `headRepo.fork` check is a hard block. Use standalone repos (created via import, not fork) for consumer testing.

9. **`GITHUB_TOKEN` cannot dispatch workflows.** The keepalive orchestrator needs a classic PAT with `repo` + `workflow` scopes stored as `SERVICE_BOT_PAT` or `ACTIONS_BOT_PAT`.

10. **PATs must belong to a user with repo access.** Don't copy PATs from the upstream Workflows repo — they authenticate as a different user. Use your own PAT.

11. **Reusable workflow refs need `@main` (or a branch/tag).** Cross-repo `uses:` references without a version suffix are invalid. GitHub will reject them at parse time.

12. **The orchestrator runs on `main`, not on the PR branch.** Files required by the orchestrator (like `keepalive_instruction_segment.js`) must be committed to `main` to be found.

13. **Consumer repos need `agents-70-orchestrator.yml`.** The keepalive dispatch targets this workflow via `workflow_dispatch`, but it's not in the consumer template. This is a known gap.

14. **Keepalive requires three PR labels.** `agents:keepalive`, `agent:codex` (or the relevant agent), and the PR must be linked to an issue. Missing any of these produces different `reason` values that can be confusing.

15. **App token warnings are non-blocking.** `KEEPALIVE_APP` and `WORKFLOWS_APP` failures are expected when those GitHub Apps aren't installed on your repo. The system falls back to PATs.

### Autofix Lessons

16. **`workflow_job` trigger causes silent workflow rejection.** GitHub rejects the entire workflow file without surfacing errors in the Actions sidebar. The only way to find the error is navigating to the direct workflow URL (`/actions/workflows/<file>.yml`).

17. **Use the direct URL to find hidden workflows.** If a workflow doesn't appear in the sidebar, go to `https://github.com/<owner>/<repo>/actions/workflows/<filename>.yml` — it may show runs with error annotations.

18. **Autofix requires lint-specific check failures.** The resolve job only proceeds if it finds checks named `lint-format` or `lint-ruff` with a `failure` conclusion. Other failures (tests, type checks) don't trigger autofix.

19. **Consumer `autofix.yml` checks out scripts from itself.** Unlike other workflows that get scripts from the Workflows repo, the autofix resolve job checks out `.github/actions/setup-api-client` from the consumer repo. These files must exist locally.

20. **Add `workflow_dispatch` for testing.** Adding a temporary `workflow_dispatch` trigger to `autofix.yml` lets you manually trigger runs via "Run workflow" button, making it much easier to debug issues.

---

## Part 4: Issue Intake System Troubleshooting

The issue intake system (`agents-issue-intake.yml`) reacts to issue events, creates a branch and PR for the agent to work on, and assigns the relevant automation accounts.

### Error 25 — Issue Intake Workflow Not Appearing in Actions Sidebar

**Symptoms:**
- Created an issue with `agent:codex` label
- No workflow run appeared
- The workflow doesn't show in the Actions sidebar

**Root cause:** Workflows that only use `issues` and `workflow_dispatch` triggers don't appear in the sidebar until they've had at least one successful run. GitHub only lists workflows that have run recently.

**Fix:** Navigate directly to `/actions/workflows/agents-issue-intake.yml`. If the page loads, the workflow is registered — it just hasn't run yet. If you see a YAML error, fix it first.

---

### Error 26 — Bridge Job Permissions Error

**Symptoms:**
```
Error: Resource not accessible by integration
```
The `bridge` job fails because it can't create branches, PRs, or write to issues.

**Root cause:** The `bridge` job in `agents-issue-intake.yml` was missing a `permissions` block. Without job-level permissions, it inherits restrictive defaults (especially when top-level permissions are intentionally omitted from the template).

**Fix:** Add explicit permissions to the `bridge` job at the same indentation level as `needs:` and `if:`:

```yaml
bridge:
  needs: [triage]
  if: <condition>
  permissions:
    contents: write
    issues: write
    pull-requests: write
    actions: write
  uses: ...
```

**Common mistake:** Indenting the `permissions` block inside the `if:` block instead of at job level. This causes a YAML syntax error like `"mapping values are not allowed in this context"`.

---

### Error 27 — `ReferenceError: agentKey is not defined`

**Symptoms:**
- Bridge job partially succeeds (branch and PR are created)
- PR has no assignees
- Workflow logs show `ReferenceError: agentKey is not defined`

**Root cause:** In `reusable-agents-issue-bridge.yml`, the PR assignee section referenced `agentKey` — a variable defined in a different `github-script` step (the agent resolution step). In the PR creation step, the variable is named `agent`, not `agentKey`. Each `github-script` step runs in its own scope.

**Fix:** Replace all `agentKey` references in the assignee block with `agent` (the in-scope variable):

```javascript
// Before (buggy):
const cfg = getAgentConfig(agentKey || 'codex');

// After (fixed):
const cfg = getAgentConfig(agent || 'codex');
```

**Lesson:** Variables defined in one `actions/github-script@v8` step are NOT shared with other steps. Each step has its own JavaScript scope. Always verify which variables are defined in the current step's `script:` block.

---

### Error 28 — PR Assignees Are Empty

**Symptoms:**
- Bridge succeeds, PR is created
- PR shows no assignees despite the workflow not logging errors

**Root cause (two layers):**

1. **Hardcoded assignees.** The bridge code originally hardcoded `['chatgpt-codex-connector', 'stranske-automation-bot']` as assignees for the `codex` agent. These accounts don't exist as collaborators on consumer/fork repos, so GitHub silently drops the assignment (the code catches the API error).

2. **Registry not consulted.** The code checked for a `cfg.assignees` field in the agent registry, but the registry uses `automation_logins` instead. Since `cfg.assignees` was always undefined, the hardcoded fallback ran.

**Fix:** Updated the bridge to use `cfg.automation_logins` from the consumer's agent registry as the assignee source. This way each consumer controls which accounts get assigned via their own `registry.yml`:

```javascript
let assignees = [];
try {
  const { getAgentConfig } = require('./.github/scripts/agent_registry.js');
  const cfg = getAgentConfig(agent || 'codex');
  if (cfg.assignees && cfg.assignees.length) {
    assignees = cfg.assignees;
  } else if (Array.isArray(cfg.automation_logins) && cfg.automation_logins.length) {
    assignees = cfg.automation_logins.map(String);
  }
} catch (_) {
  core.warning('Could not load agent registry for assignees');
}
```

**Key point:** The accounts in `automation_logins` must be collaborators on the consumer repo for assignment to work. GitHub's API silently ignores non-collaborator assignees.

---

### Issue Intake Lessons

21. **Workflow triggers don't guarantee sidebar visibility.** Workflows using only `issues` + `workflow_dispatch` triggers may not appear in the Actions sidebar. Use the direct URL pattern: `/actions/workflows/<filename>.yml`.

22. **Each `github-script` step has its own scope.** Variables defined in one step's `script:` block don't carry over to other steps. Don't reference variables from other steps without re-deriving them (typically from `process.env` or step outputs).

23. **Job-level permissions are required for cross-repo reusable workflows.** When a consumer workflow calls a reusable workflow that needs write access, the calling job must declare its own `permissions` block. Top-level permissions (or lack thereof) don't automatically propagate to jobs correctly.

24. **PR assignees must be repo collaborators.** GitHub silently drops assignees that aren't collaborators. The bridge code wraps the `addAssignees` call in try/catch, so you won't see a hard failure — just an empty assignee list. Check repo collaborator settings if assignees are missing.

25. **Use `automation_logins` from the agent registry.** The consumer's `.github/agents/registry.yml` is the right place to define which accounts handle each agent's work. The bridge reads this registry to determine assignees, so keep it in sync with your repo's actual bot collaborators.
