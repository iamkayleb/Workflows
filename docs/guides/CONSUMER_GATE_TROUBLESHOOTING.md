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

## Key Lessons

1. **Gate templates must not assume Workflows-repo-only files exist in consumers.** Always guard with existence checks (`if [ -f ... ]`, `if ls ... 2>/dev/null`).

2. **Ruff relies on repo config for line-length.** Unlike black (which gets `--line-length` from the CLI), ruff has no CLI override in the reusable workflow. Consumer repos need a `pyproject.toml`.

3. **`sync_mode: create_only` blocks all updates.** When you need to push a critical fix to existing consumers, temporarily switch to `sync`, run the sync, then revert.

4. **`gh pr create` in shallow clones needs `--base` and `--repo`.** Never rely on branch inference in CI workflows that use `--depth=1`.

5. **Fine-grained PATs don't work with `gh pr create`.** Use classic PATs with `repo` scope for cross-repo PR creation.

6. **Separate label operations from PR creation.** Labels that don't exist in the target repo will fail the entire `gh pr create` command.

7. **Consumer repos with `src/` layout need `pythonpath = ["src"]` in pytest config.** Without it, test imports fail even though the package structure is correct.
