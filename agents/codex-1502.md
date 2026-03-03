<!--
needs-human:
Label: needs-human
Blocked by workflow protection: CI failure is caused by a malformed shell block in protected workflow `.github/workflows/reusable-10-ci-python.yml` (agent-standard cannot edit workflow files).

Failing jobs in Gate run `22029563699`:
- `python ci / python 3.11` -> step `Install dependencies`
- `python ci / python 3.12` -> step `Install dependencies`

Root cause:
- In `.github/workflows/reusable-10-ci-python.yml` around lines 1494-1506, a YAML expression was injected into a bash script:
  - `${{ inputs['working-directory'] ... }}`
- This replaced the dependency tool-add section and leaves a dangling `else`, which breaks shell execution in the install step.

Required workflow fix (minimal):
1. In the install script block near line 1494, restore:
   - lint tool gate:
     - `if [ "$lint_enabled" = "true" ]; then add_tool "$ruff_spec" "ruff"; else skip_tool "ruff (lint disabled)"; fi`
   - always-install test tools:
     - `add_tool "$pytest_spec" "pytest"`
     - `add_tool "$pytest_xdist_spec" "pytest-xdist"`
   - coverage gate:
     - `if [ "$coverage_enabled" = "true" ]; then add_tool "$pytest_cov_spec" "pytest-cov"; add_tool "$coverage_spec" "coverage"; else ... fi`
2. Remove the stray `${{ inputs['working-directory'] ... }}` lines from inside the bash script.

Verification after workflow patch:
- Re-run Gate on PR #1502.
- Expect both Python matrix jobs to pass the `Install dependencies` step.
-->
