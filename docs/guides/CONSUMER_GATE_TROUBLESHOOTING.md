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

---

### Error 28b — Assignees Resolve But Don't Appear on PR

**Symptoms:**
- Debug logging shows assignees being resolved correctly from registry
- `addAssignees` API call succeeds (no error thrown)
- PR still shows no assignees

**Root cause:** GitHub's `addAssignees` API silently succeeds even when the specified accounts aren't actually assignable. An account must appear in the repo's **assignee dropdown** (Settings > Collaborators or repo member list) to be assigned. Being listed as a collaborator in a different role or being a bot account without proper permissions isn't sufficient.

To check: Go to the PR, click the "Assignees" gear icon, and see which accounts appear in the dropdown. Only those can be assigned.

**Fix:** Update the consumer's `registry.yml` to use an account that is a valid assignee. For example, if `kayleb-automation-bot` doesn't appear in the dropdown but `iamkayleb` does:

```yaml
# .github/agents/registry.yml
claude:
  automation_logins:
    - iamkayleb    # Must appear in repo's assignee dropdown
```

**Key point:** Bot/service accounts often need explicit collaborator invitations with write access before they appear as valid assignees.

---

### Error 28c — `agent:claude` Label Not Recognized by Issue Intake

**Symptoms:**
- Created an issue with `agent:claude` label
- Issue intake workflow either doesn't run or defaults to the codex agent
- No label matching `agent:claude` in the repo's label list

**Root cause:** The issue intake system routes work to agents based on labels matching the pattern `agent:<name>`. If the `agent:claude` label doesn't exist in the consumer repo, GitHub can't apply it to issues, and the intake workflow can't match on it.

**Fix (three parts):**

1. **Create the label** in the consumer repo. Go to Issues > Labels > New Label and create `agent:claude` (color: any, description: "Route to Claude agent").

2. **Add the label to the repo's label config** if one exists (`.github/labels.yml` or equivalent).

3. **Add a `runner:claude` label** if the consumer uses auto-pilot to let users request the Claude agent without triggering the full issue intake workflow.

**Verification:** After adding the label, create a test issue with `agent:claude` applied. The intake workflow should run and the bridge should create a PR with the claude agent assigned.

---

### Error 28d — `@claude start` Comment Doesn't Activate Agent

**Symptoms:**
- PR exists with the claude branch
- Posted `@claude start` as a comment on the PR
- No agent activation occurs
- `agents-bot-comment-handler.yml` doesn't react

**Root cause (investigation path):**

1. **`agents-bot-comment-handler.yml` is NOT the right workflow.** Despite the name, this workflow handles unresolved **review comments** from bots (e.g., lint suggestions), not `@claude start` activation comments.

2. **`agents-pr-meta.yml` handles activation.** This workflow listens for `issue_comment` events (`types: [created]`) and detects activation patterns like `@claude start`. It evaluates the keepalive gate and dispatches the orchestrator.

3. **`agents-80-pr-event-hub.yml` is an alternative path** but requires the `USE_CONSOLIDATED_WORKFLOWS` repository variable to be set to `true`. Without this variable, the event hub's `if:` condition skips all jobs.

**Fix:** Ensure `agents-pr-meta.yml` exists in the consumer repo. If using the consolidated event hub instead, add `USE_CONSOLIDATED_WORKFLOWS` as a repository variable set to `true` (Settings > Secrets and variables > Actions > Variables).

**Lesson:** When debugging "why doesn't my comment trigger anything," trace the exact event type (`issue_comment` vs `pull_request_review_comment`) and check which workflow files listen for that event.

---

### Issue Intake Lessons (continued)

26. **GitHub's `addAssignees` API is silently permissive.** It returns success even when accounts can't actually be assigned. Always verify assignments by checking the PR UI, not just the API response.

27. **The assignee dropdown is the source of truth.** Only accounts that appear in the repo's assignee dropdown (when editing a PR/issue) can be assigned. This is a stricter check than "is a collaborator."

28. **`agent:claude` label must exist before use.** The issue intake system matches on label names. If the label doesn't exist in the repo, it can't be applied to issues and the routing won't work.

29. **Know which workflow handles which event.** `agents-pr-meta.yml` handles `issue_comment` (including `@agent start`). `agents-bot-comment-handler.yml` handles review comments from bots. `agents-80-pr-event-hub.yml` consolidates multiple events but requires the `USE_CONSOLIDATED_WORKFLOWS` variable.

30. **The keepalive loop is the actual runner dispatcher.** After `@claude start` is posted, `agents-pr-meta.yml` evaluates the keepalive gate, then the keepalive loop dispatches the correct runner (`reusable-claude-run.yml` or `reusable-codex-run.yml`) based on `agent_type` from the evaluate step.

---

## Part 5: Agent Runner Failures (Claude and Codex)

> Errors encountered getting both agent runners (`reusable-claude-run.yml` and
> `reusable-codex-run.yml`) to execute successfully when dispatched from consumer
> repos via keepalive or autofix. Both runners share the same auth token pattern
> and had identical bugs.

---

### Error 29: `GITHUB_TOKEN: unbound variable` in "Select auth token" step

**Job:** `run-claude` or `run-codex` (via `agents-keepalive-loop.yml`, `agents-autofix-loop.yml`, or `agents-81-gate-followups.yml`)
**Exit code:** 1 (shell `set -u` violation)
**Affects:** Both `reusable-claude-run.yml` AND `reusable-codex-run.yml`

#### Root Cause

The "Select auth token" step in both runner workflows used `set -euo pipefail`, which includes `-u` (treat unset variables as errors). The shell script referenced `${GITHUB_TOKEN}` as a fallback:

```bash
checkout_token="${APP_TOKEN:-${GITHUB_TOKEN}}"
```

But `GITHUB_TOKEN` was not in the step's `env:` block — only `APP_TOKEN` was declared. When the GitHub App token minting step failed (no `WORKFLOWS_APP_ID` secret), `APP_TOKEN` was empty, so bash tried to expand `${GITHUB_TOKEN}`, which was unbound, and the step crashed.

#### Cascade Effect

This is the **real** root cause of the "Prompt preparation failed (missing prompt file)" error. When "Select auth token" fails:
1. Checkout step skips (depends on auth token output)
2. `setup-api-client` skips (no checkout)
3. Prompt assembly skips (no files available)
4. The "Run Claude" step sees an empty `PROMPT_FILE` variable and reports "missing prompt file"

The misleading error diverts attention from the actual auth token issue.

#### Fix

Added `GITHUB_TOKEN: ${{ github.token }}` to the step's `env:` block:

```yaml
- name: Select auth token
  id: auth_token
  env:
    APP_TOKEN: ${{ steps.app_token.outputs.token || '' }}
    GITHUB_TOKEN: ${{ github.token }}
  run: |
    set -euo pipefail
    checkout_token="${APP_TOKEN:-${GITHUB_TOKEN}}"
```

**Commits:**
- Claude runner: `a5c279d`
- Codex runner: same fix applied to `reusable-codex-run.yml` (line 223)

**Important:** This bug existed in BOTH runners because they share the same auth token pattern. When fixing one runner, always check the other for the same issue.

---

### Error 29b: Codex runner fails with identical `GITHUB_TOKEN: unbound variable`

**Job:** `run-codex` (via `agents-keepalive-loop.yml` or `agents-81-gate-followups.yml`)
**Symptom:** Codex runner fails at "Select auth token" step — same error as Error 29
**Tested on:** WIT-Standalone PR #42 (issue #41, `agent:codex` label)

#### Root Cause

The Codex runner (`reusable-codex-run.yml`) had the exact same bug as the Claude runner — `GITHUB_TOKEN` missing from the `env:` block at line 223. The fix for the Claude runner was not applied to the Codex runner because they are separate workflow files.

#### Fix

Same as Error 29 — added `GITHUB_TOKEN: ${{ github.token }}` to the Codex runner's "Select auth token" step. Also updated the scripts checkout `repository:` from `stranske/Workflows` to `iamkayleb/Workflows` (same issue as Error 31).

**Lesson:** When both runners share the same code pattern, fixes must be applied to both. Search for the pattern across all runner files, not just the one that failed first.

---

### Error 30: Fix on `main` not picked up — wrong repo reference

**Job:** `autofix-claude` (via `agents-autofix-loop.yml`)
**Symptom:** Same `GITHUB_TOKEN: unbound variable` error after fix was merged to `main`

#### Root Cause

The fix was merged to `iamkayleb/Workflows@main`, but the consumer's `agents-autofix-loop.yml` still referenced `stranske/Workflows/.github/workflows/reusable-claude-run.yml@main` — the **upstream** repo without the fix. The keepalive loop had been updated to `iamkayleb/Workflows` but the autofix loop had not.

#### Fix

Updated **all** `uses:` declarations across both in-repo workflows (`.github/workflows/`) and consumer templates (`templates/consumer-repo/`) to reference `iamkayleb/Workflows` instead of `stranske/Workflows`. This ensures the fork's own fixes are always used.

**Affected files:** `agents-autofix-loop.yml`, `agents-keepalive-loop.yml`, `agents-bot-comment-handler.yml`, `agents-verifier.yml`, `agents-guard.yml`, `agents-80-pr-event-hub.yml`, `agents-81-gate-followups.yml`, `agents-issue-intake.yml`, `agents-orchestrator.yml`, `agents-pr-meta.yml`, `agents-pr-health.yml`, `autofix.yml`, `ci.yml`, `pr-00-gate.yml`.

---

### Error 31: Workflows scripts checkout referencing wrong repo

**Job:** `run-claude` or `run-codex` (Checkout Workflows scripts step)
**Symptom:** Checkout fails or pulls wrong scripts
**Affects:** Both `reusable-claude-run.yml` AND `reusable-codex-run.yml`

#### Root Cause

Both runners had `repository: stranske/Workflows` for the scripts checkout. In a fork, this pulls scripts from the upstream instead of the fork.

#### Fix

Changed `repository: stranske/Workflows` to `repository: iamkayleb/Workflows` in both runners.

**Commits:**
- Claude runner: `6a91a9c`
- Codex runner: same fix applied alongside Error 29b fix

---

### Agent Runner Lessons

26. **`set -euo pipefail` with `-u` requires all referenced variables in `env:`.** If a shell script references `${VAR}`, that variable must be in the step's `env:` block or it will cause an unbound variable error. `github.token` is only available via expressions — it's not automatically set as an environment variable.

27. **Cascade failures obscure root causes.** When an early step fails in a reusable workflow, all dependent steps skip. The error message from the last step (which runs unconditionally or with a fallback) may be completely misleading. Always check the **first** failing step.

28. **Fork repos must update cross-repo `uses:` references.** When forking a Workflows repository, all `uses: original-owner/Repo/...@ref` declarations in both the in-repo workflows AND consumer templates must be updated to point at the fork. Otherwise, changes to reusable workflows in the fork won't take effect.

29. **Autofix and keepalive are separate dispatch chains.** Even if the keepalive loop is correctly configured, the autofix loop may have different `uses:` references. Both must be checked when verifying cross-repo workflow references.

30. **Both runners share the same auth pattern — fix both.** `reusable-claude-run.yml` and `reusable-codex-run.yml` use an identical "Select auth token" step with the same `${APP_TOKEN:-${GITHUB_TOKEN}}` fallback. When a bug is found in one runner, always check the other. The Codex runner bug was only discovered after the Claude runner was fixed and a Codex test was run.

---

## Part 6: Consumer Repo Reference Migration (Fork Setup)

> When operating a fork of the Workflows repository, all cross-repo `uses:`
> references must point to the fork, not the upstream. This section covers
> the systematic migration required and the pitfalls encountered.

---

### Error 32: Consumer workflows still referencing upstream after Workflows fix

**Symptoms:**
- Fix is confirmed on `iamkayleb/Workflows@main` (verified via raw GitHub URL)
- Consumer repo's keepalive loop correctly points to fork
- Claude runner STILL fails with the same pre-fix error
- Workflow run timestamp is AFTER the fix was merged

**Investigation:**

The workflow run metadata showed `event: workflow_run` — meaning this was an **autofix** run, not a keepalive run. The autofix loop and keepalive loop are independent workflow files with their own `uses:` declarations. Even though the keepalive loop was updated, the autofix loop still referenced the upstream.

**Root cause:** Multiple workflow files in the consumer repo call reusable workflows via `uses:` declarations. Each file independently specifies the source repository. Updating one file doesn't update the others.

**Workflows in WIT-Standalone that reference reusable runners:**

| Workflow | Calls | Status before fix |
|----------|-------|-------------------|
| `agents-keepalive-loop.yml` | `reusable-claude-run.yml`, `reusable-codex-run.yml` | Updated to fork |
| `agents-autofix-loop.yml` | `reusable-claude-run.yml`, `reusable-codex-run.yml` | Still upstream |
| `agents-81-gate-followups.yml` | `reusable-claude-run.yml` (x2), `reusable-codex-run.yml` (x2) | Still upstream |
| `agents-80-pr-event-hub.yml` | `reusable-pr-context.yml`, `reusable-20-pr-meta.yml`, `reusable-bot-comment-handler.yml` | Still upstream |
| `agents-verifier.yml` | `reusable-agents-verifier.yml` | Still upstream |
| `agents-orchestrator.yml` | `reusable-16-agents.yml` | Still upstream |
| `agents-guard.yml` | `setup-api-client` action (pinned SHA) | Still upstream |
| `pr-00-gate.yml` | `reusable-10-ci-python.yml`, `reusable-12-ci-docker.yml` | Still upstream |
| `ci.yml` | `reusable-10-ci-python.yml` (x4) | Still upstream |

**Fix (consumer repo):**

Bulk-replace all `stranske/Workflows` references in the consumer's workflow directory:

```bash
cd .github/workflows
sed -i 's|stranske/Workflows|iamkayleb/Workflows|g' *.yml
```

For `agents-guard.yml`, also update pinned SHAs that don't exist on the fork:

```bash
sed -i 's|@6deed4d3937adab2370b4ddf96046ed295efe68f|@main|g' agents-guard.yml
```

**Fix (Workflows repo — source of truth):**

Updated all `uses:` declarations in both in-repo workflows (`.github/workflows/`) and consumer templates (`templates/consumer-repo/.github/workflows/`) from `stranske/Workflows` to `iamkayleb/Workflows`. This ensures future template syncs propagate the correct references.

**Commit:** `05d6ffe`

---

### Error 33: Pinned SHA references don't exist on fork

**Symptoms:**
- `agents-guard.yml` references `stranske/Workflows/.github/actions/setup-api-client@6deed4d...`
- After changing `stranske` to `iamkayleb`, the action still fails
- The SHA `6deed4d` is a commit in the upstream repo that may not exist (or has a different SHA) in the fork

**Root cause:** When a workflow pins a cross-repo action to a specific commit SHA, that SHA is tied to the source repo's git history. Forks may not have the same SHA if the fork was created after a rebase, or if the commit predates the fork point.

**Fix:** Replace pinned SHA references with `@main` for fork workflows:

```yaml
# Before:
uses: "stranske/Workflows/.github/actions/setup-api-client@6deed4d3937adab2370b4ddf96046ed295efe68f"

# After:
uses: "iamkayleb/Workflows/.github/actions/setup-api-client@main"
```

**Trade-off:** Using `@main` instead of a pinned SHA means the action can change without warning. For production setups, pin to a known-good SHA from the fork instead.

---

### Error 34: Template sync reverts consumer customizations

**Symptoms:**
- Consumer repo manually updated to point to fork
- Template sync runs and creates a PR
- Sync PR overwrites consumer's `iamkayleb/Workflows` references back to `stranske/Workflows`

**Root cause:** The sync workflow pushes files from `templates/consumer-repo/` to consumers. If the templates still reference `stranske/Workflows`, the sync will overwrite any manual consumer fixes.

**Fix:** Always update the **Workflows repo templates first**, then sync. The source of truth for consumer workflow files is `templates/consumer-repo/`. Editing the consumer directly is a temporary measure — the next sync will revert it unless the template matches.

**Prevention:** The `sync_mode: create_only` setting in `.github/sync-manifest.yml` prevents overwrites for specific files (like `ci.yml`). But most workflow files use the default `sync` mode, meaning they're always overwritten on sync.

---

### How Template Sync Works

The sync mechanism (`maint-68-sync-consumer-repos.yml`) pushes template files to registered consumer repos:

1. **Trigger:** Automatic on push to `main` when `templates/consumer-repo/**` changes, or manual via `workflow_dispatch`
2. **Manifest:** `.github/sync-manifest.yml` declares every file to sync, with optional `sync_mode: create_only` for repo-specific files
3. **Consumer list:** Registered repos are listed in the workflow's `REGISTERED_CONSUMER_REPOS` env variable (includes `iamkayleb/WIT-Standalone`)
4. **Process:** For each consumer, the workflow clones both repos, compares files, and creates a sync PR if changes are detected
5. **Branch pattern:** `sync/workflows-<HASH>` — idempotent, won't create duplicates

**To manually trigger sync:**
- Go to `iamkayleb/Workflows` > Actions > `maint-68-sync-consumer-repos`
- Click "Run workflow"
- Optionally set `repos` to `iamkayleb/WIT-Standalone` to sync only that consumer

---

### Fork Migration Lessons

31. **Fork setup requires a full reference audit.** When forking a Workflows repo, do a global search for the upstream owner in all `*.yml` files and replace with the fork owner. This includes `uses:` declarations, `repository:` checkout parameters, and JavaScript code that constructs API paths.

32. **Each dispatch chain is independent.** Keepalive, autofix, gate-followups, and verifier are separate workflow files that each independently call reusable runners. Fixing one doesn't fix the others.

33. **Pinned SHA references break across forks.** Commit SHAs are repo-specific. When migrating to a fork, replace pinned SHAs with `@main` or a known-good SHA from the fork's own history.

34. **Always fix templates first, then sync.** Editing consumer repos directly is a stopgap. The next template sync will overwrite manual changes. Make the authoritative change in `templates/consumer-repo/` and let the sync propagate it.

35. **`sed` is your friend for bulk migrations.** A single `sed -i 's|old-owner/Repo|new-owner/Repo|g' *.yml` in the workflows directory handles most references. Follow up by checking for pinned SHAs and `repository:` parameters that need manual attention.

36. **Verify with raw GitHub URLs.** After pushing a fix, confirm the actual file content on `main` using `https://raw.githubusercontent.com/<owner>/<repo>/main/<path>`. Don't trust local state or cached workflow run logs.

---

## Part 7: End-to-End Success — Full Agent Pipeline Verified

> After resolving all issues in Parts 4-6, the complete agent pipeline was
> verified working end-to-end on `iamkayleb/WIT-Standalone`.

### The Complete Chain (What Works)

The following pipeline was verified as functional:

1. **Issue created** with `agent:claude` label on WIT-Standalone
2. **`agents-issue-intake.yml`** triggers on the issue event
3. **`reusable-agents-issue-bridge.yml`** (from `iamkayleb/Workflows@main`):
   - Creates a branch (`claude/issue-<number>-<slug>`)
   - Creates a PR linked to the issue
   - Resolves assignees from `registry.yml` `automation_logins`
   - Assigns the correct account
4. **`@claude start`** comment posted on the PR (manually or by the intake system)
5. **`agents-pr-meta.yml`** detects the activation comment
6. **Keepalive gate** evaluates and dispatches the orchestrator
7. **`agents-keepalive-loop.yml`** dispatches the Claude runner:
   - `uses: iamkayleb/Workflows/.github/workflows/reusable-claude-run.yml@main`
8. **`reusable-claude-run.yml`** executes:
   - Mints GitHub App token (or falls back to `github.token`)
   - Checks out the PR branch
   - Installs API client and dependencies
   - Assembles prompt from `.github/codex/prompts/`
   - Runs Claude agent with the prompt
   - Commits and pushes changes
9. **Autofix loop** triggers on CI results, dispatches Claude for fixes
10. **PR #40** on WIT-Standalone — Claude successfully created `src/example/hello.py` with the requested `hello_world` function, ran autofix iterations, and completed all tasks.

**Verification PR:** `iamkayleb/WIT-Standalone#40` (co-authored by Claude Sonnet 4.6)

### Key Files in the Working Pipeline

| Component | File | Location |
|-----------|------|----------|
| Issue intake (consumer) | `agents-issue-intake.yml` | WIT-Standalone |
| Bridge (reusable) | `reusable-agents-issue-bridge.yml` | iamkayleb/Workflows |
| PR activation (consumer) | `agents-pr-meta.yml` | WIT-Standalone |
| Keepalive loop (consumer) | `agents-keepalive-loop.yml` | WIT-Standalone |
| Claude runner (reusable) | `reusable-claude-run.yml` | iamkayleb/Workflows |
| Autofix loop (consumer) | `agents-autofix-loop.yml` | WIT-Standalone |
| Agent registry (consumer) | `.github/agents/registry.yml` | WIT-Standalone |
| Prompts (consumer) | `.github/codex/prompts/*.md` | WIT-Standalone |

### Prerequisites for a Working Consumer Repo

Based on all issues encountered, here is the complete checklist for a consumer repo to support the Claude agent:

1. **Labels exist:** `agent:claude`, `runner:claude` (optional), `agent:needs-attention`
2. **Registry configured:** `.github/agents/registry.yml` has a `claude` entry with `automation_logins` set to a valid repo collaborator
3. **Workflow references point to fork:** All `uses:` declarations reference `iamkayleb/Workflows` (not `stranske/Workflows`)
4. **Prompt files present:** `.github/codex/prompts/` contains the required prompt files (`keepalive_next_task.md`, `autofix_from_ci_failure.md`, etc.)
5. **Secrets configured:** `CLAUDE_CODE_OAUTH_TOKEN` (or equivalent auth) available as a repo or org secret
6. **API client action available:** `.github/actions/setup-api-client/` exists locally (synced from templates)
7. **Agent scripts present:** `.github/scripts/agent_registry.js` and related helpers exist locally
8. **Collaborator access:** The account listed in `automation_logins` has write access and appears in the repo's assignee dropdown

### Summary of All Fixes Applied

| # | Error | Fix | Commit |
|---|-------|-----|--------|
| 25 | Intake not in sidebar | Use direct URL | (workflow exists, just hidden) |
| 26 | Bridge permissions | Add job-level `permissions` block | (prior session) |
| 27 | `agentKey` undefined | Replace with `agent` (correct scope variable) | (prior session) |
| 28 | Empty assignees (hardcoded) | Use `cfg.automation_logins` from registry | `d50bdce` |
| 28b | Assignees resolve but don't stick | Use account that appears in assignee dropdown | (consumer registry change) |
| 28c | `agent:claude` not recognized | Create the label in consumer repo | (manual) |
| 28d | `@claude start` doesn't activate | Use `agents-pr-meta.yml` (not bot-comment-handler) | (investigation, no code change) |
| 29 | `GITHUB_TOKEN: unbound variable` (Claude) | Add `GITHUB_TOKEN` to step `env:` block | `a5c279d` |
| 29b | `GITHUB_TOKEN: unbound variable` (Codex) | Same fix applied to Codex runner | `15707b5` |
| 30 | Fix not picked up (wrong repo) | Update all `uses:` to fork references | `05d6ffe` |
| 31 | Scripts checkout wrong repo (both runners) | Change `repository:` to fork | `6a91a9c` + `15707b5` |
| 32 | Consumer still on upstream | Bulk `sed` replace in consumer workflows | (consumer-side) |
| 33 | Pinned SHA doesn't exist on fork | Replace with `@main` | `05d6ffe` |
| 34 | Sync reverts consumer changes | Fix templates first, then sync | `05d6ffe` |
| 35 | `CODEX_AUTH_JSON` secret missing | Add secret via `codex login --device-auth` | (consumer secret) |
| 36 | No `@codex start` comment on PR | By design — Codex uses keepalive loop directly | (no code change) |

---

## Part 8: Codex Agent — Activation and Authentication

> Issues specific to the Codex agent runner that differ from the Claude runner.
> The Codex agent shares the same auth token pattern as Claude but has additional
> requirements around CLI authentication and a different activation model.

---

### Error 35: `CODEX_AUTH_JSON secret is not set or empty`

**Job:** `run-codex` (via keepalive or gate-followups)
**Step:** "Setup Codex auth"
**Exit code:** 1

#### Symptoms

After the `GITHUB_TOKEN` fix (Error 29b), the Codex runner progresses past the "Select auth token" step but fails at "Setup Codex auth":

```
Error: CODEX_AUTH_JSON secret is not set or empty.
Error: Please add it to repository secrets.
Go to: https://github.com/<owner>/<repo>/settings/secrets/actions
```

#### Root Cause

The Codex CLI requires OpenAI authentication credentials stored in `~/.codex/auth.json`. The runner reads this from the `CODEX_AUTH_JSON` repository secret, writes it to disk, and validates the token expiration. Without this secret, the Codex CLI cannot authenticate with OpenAI's API.

This is different from the Claude runner, which uses `CLAUDE_CODE_OAUTH_TOKEN`.

#### Fix

Two options:

**Option A — ChatGPT Subscription (free with Plus/Pro, ~10-day refresh cycle):**

```bash
# 1. Install Codex CLI
npm install -g @openai/codex

# 2. Authenticate with device code flow
codex login --device-auth
#    Follow prompts: open URL, enter code, authenticate

# 3. Copy the auth file
cat ~/.codex/auth.json

# 4. Add as GitHub secret: CODEX_AUTH_JSON
#    Paste the raw JSON content
```

**Option B — OpenAI API Key (pay-as-you-go, no expiration):**

Set `OPENAI_API_KEY` as a repository secret instead. This is the recommended approach for long-running CI since subscription tokens expire every ~10 days and require manual re-authentication.

**Reference:** See `docs/ci/CHATGPT_SUBSCRIPTION_CI.md` for full details on token lifecycle, refresh rotation issues, and expiration monitoring.

---

### Error 36: No `@codex start` Comment Posted on PR

**Job:** Bridge (`reusable-agents-issue-bridge.yml`)
**Symptom:** PR is created by intake but no activation comment appears

#### Root Cause

This is **by design**, not a bug. The issue intake workflow (`agents-issue-intake.yml`) explicitly suppresses `post_agent_comment` for the Codex agent:

```yaml
# Skip post_agent_comment for codex - CLI keepalive loop handles it,
# posting @codex would trigger UI agent alongside CLI causing conflicts
post_agent_comment: >-
  ${{ needs.check_labels.outputs.agent != 'codex' && 'true' || 'false' }}
```

The rationale: posting `@codex start` would trigger both the UI agent and the CLI keepalive loop simultaneously, causing conflicts. Instead, the keepalive loop detects the PR directly and dispatches the Codex runner without needing an activation comment.

**How each agent activates:**

| Agent | Activation | Comment posted? |
|-------|-----------|----------------|
| Claude | `@claude start` comment on PR | Yes (auto-posted by bridge) |
| Codex | Keepalive loop detects PR exists | No (suppressed to avoid conflicts) |

**Verification:** Check the keepalive status comment on the PR. If it shows iteration counts and agent status (even "agent-run-failed"), the keepalive loop IS running — the agent is activated, the runner just hasn't succeeded yet.

---

### Codex-Specific Lessons

37. **Each agent has different auth secrets.** Claude uses `CLAUDE_CODE_OAUTH_TOKEN`, Codex uses `CODEX_AUTH_JSON` (or `OPENAI_API_KEY`). When enabling a new agent, check the runner workflow's `secrets:` block to see what credentials it needs.

38. **Codex subscription tokens expire.** Unlike API keys, ChatGPT subscription auth tokens last ~10 days and refresh tokens are single-use (rotation). Plan for periodic manual refresh or use `OPENAI_API_KEY` instead.

39. **Not all agents use activation comments.** The `post_agent_comment` input on the bridge controls this per-agent. Codex skips it to avoid UI/CLI conflicts. Don't assume a missing `@agent start` comment means activation failed — check the keepalive status instead.

40. **Debug agent runners step-by-step.** The runner steps execute sequentially: auth token -> checkout -> setup API client -> install CLI -> setup agent auth -> assemble prompt -> run agent. When the runner fails, check the **first** failing step, not the last one.

---

## Part 9: Both Agents Verified — End-to-End Success

> After resolving all issues in Parts 4-8, both the Claude and Codex agent
> pipelines were verified working end-to-end on `iamkayleb/WIT-Standalone`.

### Verification Results

| Agent | Test Issue | PR | Result | Key Commit |
|-------|-----------|-----|--------|-----------|
| Claude | #39 | [#40](https://github.com/iamkayleb/WIT-Standalone/pull/40) | 2/2 tasks complete | `86d0a2d` (feat: add hello_world function) |
| Codex | #45 | [#46](https://github.com/iamkayleb/WIT-Standalone/pull/46) | 2/2 tasks complete | `c74be7c` (Add example2 hello function) |

### Complete Pipeline — Both Agents

```
Issue created with agent:<name> label
  │
  ├─ agents-issue-intake.yml triggers
  │
  ├─ reusable-agents-issue-bridge.yml creates branch + PR
  │    ├─ Resolves assignees from registry.yml automation_logins
  │    ├─ Claude: posts @claude start comment
  │    └─ Codex: skips comment (keepalive detects PR directly)
  │
  ├─ Keepalive loop dispatches runner
  │    ├─ Claude: reusable-claude-run.yml
  │    └─ Codex: reusable-codex-run.yml
  │
  ├─ Runner executes:
  │    ├─ Auth token selection (GITHUB_TOKEN fallback)
  │    ├─ Checkout PR branch
  │    ├─ Setup API client + Workflows scripts
  │    ├─ Agent-specific auth (CLAUDE_CODE_OAUTH_TOKEN / CODEX_AUTH_JSON)
  │    ├─ Assemble prompt from .github/codex/prompts/
  │    ├─ Run agent CLI
  │    └─ Commit and push changes
  │
  ├─ Autofix loop runs on CI results
  │
  └─ Keepalive summary updates PR status
```

### Full Prerequisites Checklist (Both Agents)

| Requirement | Claude | Codex |
|-------------|--------|-------|
| Label | `agent:claude` | `agent:codex` |
| Auth secret | `CLAUDE_CODE_OAUTH_TOKEN` | `CODEX_AUTH_JSON` or `OPENAI_API_KEY` |
| Registry entry | `claude` in `registry.yml` | `codex` in `registry.yml` |
| `automation_logins` | Valid repo collaborator | Valid repo collaborator |
| Workflow references | `iamkayleb/Workflows@main` | `iamkayleb/Workflows@main` |
| Prompt files | `.github/codex/prompts/*.md` | `.github/codex/prompts/*.md` |
| API client action | `.github/actions/setup-api-client/` | `.github/actions/setup-api-client/` |
| Agent scripts | `.github/scripts/agent_registry.js` | `.github/scripts/agent_registry.js` |
