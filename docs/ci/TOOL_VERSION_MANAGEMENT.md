# CI/Autofix Tool Version Management

## Overview

All CI and autofix workflows use tool versions defined in a single source of truth to ensure consistency across:
- CI validation (formatting, linting, type checking)
- PR autofix commits
- CI autofix loop
- Local development

## Version File

**Location**: `.github/workflows/autofix-versions.env`

This file contains pinned versions for all formatting, linting, and testing tools:

```bash
BLACK_VERSION=25.11.0
RUFF_VERSION=0.14.7
ISORT_VERSION=7.0.0
DOCFORMATTER_VERSION=1.7.7
MYPY_VERSION=1.19.0
PYTEST_VERSION=9.0.1
PYTEST_COV_VERSION=7.0.0
PYTEST_XDIST_VERSION=3.8.0
COVERAGE_VERSION=7.12.0
```

## Workflows Using Version File

### 1. CI Python Validation (`reusable-10-ci-python.yml`)
- Sources `autofix-versions.env` before installing tools
- Runs `black --check`, `ruff check`, `mypy`, and `pytest`
- Falls back to latest versions if version file is missing

### 2. PR Autofix (`reusable-18-autofix.yml`)
- Reads version file to install Black and Ruff
- Applies fixes automatically when CI fails
- Uses same tool versions as CI validation

### 3. CI Autofix Loop (`autofix.yml`)
- Extracts Black and Ruff versions from version file
- Runs after Gate workflow failures
- Applies import ordering (Ruff) and formatting (Black)

### 4. Version Check (`maint-50-tool-version-check.yml`)
- Runs weekly on Mondays at 8:00 AM UTC
- Checks PyPI for latest versions of all tools
- Creates/updates issue when updates are available
- Manual dispatch available with `force_issue` option

## Update Process

### Automated Monitoring

The `maint-50-tool-version-check.yml` workflow automatically:
1. Checks PyPI weekly for new tool versions
2. Compares with current pinned versions
3. Creates an issue titled "🔧 CI/Autofix Tool Updates Available"
4. Lists all available updates in the issue
5. Updates the issue if already exists (doesn't spam with duplicates)

### Manual Update Steps

When an update issue is created:

1. **Review the update issue** to see which tools have new versions

2. **Update the version file**:
   ```bash
   # Edit .github/workflows/autofix-versions.env
   vim .github/workflows/autofix-versions.env
   
   # Example: Update Black from 25.9.0 to 25.11.0
   BLACK_VERSION=25.11.0
   ```

3. **Test locally**:
   ```bash
   # Source the version file
   source .github/workflows/autofix-versions.env
   
   # Install with pinned versions
   pip install "black==${BLACK_VERSION}" "ruff==${RUFF_VERSION}" "mypy==${MYPY_VERSION}"
   
   # Run validation
   black --check .
   ruff check .
   mypy src tests
   ```

4. **Create a PR**:
   ```bash
   git checkout -b chore/update-tool-versions
   git add .github/workflows/autofix-versions.env
   git commit -m "chore(ci): update tool versions

   - Black: X.X.X → Y.Y.Y
   - Ruff: X.X.X → Y.Y.Y
   - MyPy: X.X.X → Y.Y.Y
   
   Addresses: issue #NNNN"
   git push -u origin chore/update-tool-versions
   ```

5. **Verify CI passes**:
   - All Gate checks should pass
   - Autofix should use new versions if it runs
   - No formatting conflicts should occur

6. **Merge and close issue**:
   - Merge the PR
   - Close the version update issue

## Why Version Pinning?

### Problems Without Version Pinning

1. **Formatter Drift**: Autofix uses Ruff 0.6.2, CI validates with Ruff 0.6.3
   - Result: Autofix commits fail CI validation
   
2. **Breaking Changes**: Tool updates can introduce breaking changes
   - Result: Sudden CI failures across all PRs
   
3. **Inconsistent Local Development**: Developers use different versions
   - Result: "Works on my machine" formatting issues

### Benefits of Centralized Pinning

1. **Consistency**: Same tool versions across all environments
2. **Reproducibility**: Results are deterministic
3. **Controlled Updates**: Updates are deliberate and tested
4. **Clear History**: Git shows when/why versions changed

## Troubleshooting

### Autofix Commits Fail CI

**Symptom**: Autofix creates a commit but CI still reports formatting errors

**Cause**: Autofix and CI are using different tool versions

**Solution**:
1. Check both workflows source `autofix-versions.env`
2. Verify version variables are read correctly
3. Ensure both use the same formatter (Black, not `ruff format`)

### Version File Not Found

**Symptom**: Warning in CI logs about missing version file

**Cause**: Workflow can't find `.github/workflows/autofix-versions.env`

**Solution**:
1. Verify file exists in repository
2. Check workflow is checking out repository code
3. Ensure path is correct (relative to repo root)

### Weekly Check Not Running

**Symptom**: No version update issues being created

**Cause**: Workflow may be disabled or scheduled incorrectly

**Solution**:
1. Check workflow is enabled in Actions UI
2. Verify cron schedule is correct (`0 8 * * 1`)
3. Manually trigger with workflow_dispatch to test

## Architecture Decisions

### Why Shell Sourcing (CI) vs Python Parsing (Autofix)?

- **CI** (`reusable-10-ci-python.yml`): Uses `source` for simplicity
  - Single line: `source .github/workflows/autofix-versions.env`
  - Shell variables are immediately available
  
- **Autofix** (`reusable-18-autofix.yml`, `autofix.yml`): Uses Python parser
  - More complex error handling
  - Needs to set outputs for later steps
  - Works in environments where source may not behave correctly

Both approaches read the same file and produce identical results.

### Why Black Instead of Ruff Format?

While Ruff includes a formatter compatible with Black, there are subtle differences in:
- Line breaking decisions
- Comment handling
- Edge case formatting

To ensure CI validation and autofix produce identical output, both must use the same formatter. We chose Black as the canonical formatter because:
1. It's the established standard in the Python ecosystem
2. More mature and stable
3. Explicit formatting rules prevent ambiguity

## Keeping the Coding Agents Current

The Python lint/test tools above are pinned in `autofix-versions.env`. The
**coding agent CLIs** are installed from npm and tracked separately:

| Agent | Package | Pinning |
|-------|---------|---------|
| Codex | `@openai/codex` | **Exact pin** (for stability) in `reusable-codex-run.yml` (`codex_cli_version` default) and `reusable-agents-verifier.yml` (`npm install -g`) |
| Claude | `@anthropic-ai/claude-code` | `latest` (no pin) — floats automatically |
| Gemini | `@google/gemini-cli` | `latest` (no pin) — floats automatically |

### Automated monitoring (`maint-53-agent-version-check.yml`)

Runs weekly (Mondays 09:00 UTC) and on demand. It:

1. Reads the pinned Codex version from both workflow files.
2. Compares against the latest published `@openai/codex` release.
3. Flags **drift** if the two Codex pins disagree.
4. Opens/updates a `maintenance,dependencies` issue when a newer Codex
   version is available, with the exact files to update.
5. Reports Claude/Gemini latest versions for visibility (they self-update).

### Updating the Codex pin

Because Codex is pinned in two places, **update both together**:

1. Review the release notes: <https://github.com/openai/codex/releases>
2. Bump `codex_cli_version` default in `reusable-codex-run.yml`.
3. Bump the `@openai/codex@X.Y.Z` install in `reusable-agents-verifier.yml`.
4. Open a PR; let the keepalive/verify health checks run before merging.

Claude and Gemini require no pin maintenance — they install `latest` on each
run. Pin them (via the `*_cli_version` inputs) only if you need to freeze a
known-good version for a controlled reason.

## Related Documentation

- [Autofix System](AUTOFIX.md) - How automatic fixes work
- [Gate Workflow](GATE.md) - CI validation pipeline
- [Ledger System](LEDGER.md) - Agent progress tracking

## Maintenance Schedule

- **Weekly**: Automated tool version check (`maint-50`, Mondays 8:00 AM UTC)
- **Weekly**: Automated agent CLI version check (`maint-53`, Mondays 9:00 AM UTC)
- **As Needed**: Manual updates when security issues arise
- **Quarterly**: Review and update this documentation
