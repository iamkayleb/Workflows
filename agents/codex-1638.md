<!--
needs-human:
Label: needs-human
Blocked by workflow protection: the failing step is in protected workflow files (`.github/workflows/**`), which cannot be edited in `agent-standard`.

Failing Gate run:
- Run: `22291979366`
- PR: `#1638`
- Job: `python ci / lint-ruff`
- Step: `Install uv`

Observed root cause:
- The `lint-ruff` job installs uv via:
  - `curl -LsSf https://astral.sh/uv/install.sh | sh`
- This external installer call failed before lint execution, so Gate summary failed at `Enforce Gate success`.

Required workflow fix (agent-high-privilege):
1. Update uv installation in `.github/workflows/reusable-10-ci-python.yml` (at least the `lint-ruff` job block around `Install uv`) to avoid single-point failure from the remote installer.
2. Suggested minimal hardened install logic:
   - Try `uv --version` first; if present, skip install.
   - Otherwise run `curl -LsSf https://astral.sh/uv/install.sh | sh`.
   - If curl install fails, fall back to `python -m pip install --user uv`.
   - Append `"$HOME/.local/bin"` to `GITHUB_PATH`.
3. Mirror the same hardening in other duplicated `Install uv` blocks in the same workflow to prevent recurring failures.

Verification after workflow patch:
- Re-run Gate on PR #1638.
- Expect `python ci / lint-ruff` to pass `Install uv` and proceed to Ruff checks.
-->
