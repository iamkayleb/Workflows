# Integration Test CI Failure - Fix Documentation

## Issue Summary
Integration CI run #48 failed due to formatting and lint issues in newly added files in the `Workflows-Integration-Tests` repository.

### Failed Run Details
- **Run ID**: 20728361745
- **Commit**: 90e6912fcfdd2f629851836ad192db4a2890a087
- **Branch**: main
- **Trigger**: push

## Root Cause
The commit "feat: add comprehensive dependency testing setup" added two new files:
- `scripts/validate_dependency_test_setup.py`
- `tests/test_dependency_version_alignment.py`

The `validate_dependency_test_setup.py` file had multiple formatting issues that failed Black and Ruff checks.

## Lint/Format Errors Found

### Black Format Issues
- File needed reformatting: `scripts/validate_dependency_test_setup.py`

### Ruff Lint Issues
1. **W293**: Blank lines contained whitespace (33 instances)
2. **UP006**: Used `Tuple`, `List` instead of `tuple`, `list` (8 instances)
3. **F541**: f-strings without placeholders (2 instances)
4. **UP035**: Deprecated `typing.Dict` usage (1 instance)

## Solution Applied
Ran `black` formatter on the problematic file, which automatically fixed all issues:
- Removed whitespace from blank lines
- Reformatted string quotes consistently
- Fixed line continuations and indentation

## Files to Apply

### Fixed File: scripts/validate_dependency_test_setup.py
See the patch file: `0001-fix-Auto-format-files-to-meet-lint-standards.patch`

Or run the fix script:
```bash
./scripts/fix-integration-tests-formatting.sh /path/to/Workflows-Integration-Tests
```

## To Apply This Fix

### Option 1: Using the automated workflow (Recommended)
After merging this PR:
```bash
# Go to: https://github.com/stranske/Workflows/actions/workflows/maint-70-fix-integration-formatting.yml
# Click "Run workflow"
# The workflow will automatically apply and push the fixes
```

### Option 2: Using the fix script
```bash
cd /path/to/workflows/repo
./scripts/fix-integration-tests-formatting.sh /path/to/Workflows-Integration-Tests
cd /path/to/Workflows-Integration-Tests
git add -A
git commit -m "fix: Auto-format files to meet lint standards"
git push origin main
```

### Option 3: Using the patch file (may need manual adjustment)
```bash
cd /path/to/Workflows-Integration-Tests
git apply /path/to/workflows/0001-fix-Auto-format-files-to-meet-lint-standards.patch
# If patch fails, use Option 2 or 4 instead
git add scripts/validate_dependency_test_setup.py
git commit -m "fix: Auto-format files to meet lint standards"
git push origin main
```

### Option 4: Manual fix
```bash
cd /path/to/Workflows-Integration-Tests
python3 -m pip install black
black scripts/validate_dependency_test_setup.py
git add scripts/validate_dependency_test_setup.py
git commit -m "fix: Auto-format files to meet lint standards"
git push origin main
```

## Prevention

To prevent this in the future, consider:

1. **Add pre-commit hooks** to the Integration-Tests repository
2. **Run format check locally** before pushing:
   ```bash
   black --check scripts/ tests/
   ruff check scripts/ tests/
   ```
3. **Add autofix workflow** - Copy `templates/consumer-repo/.github/workflows/autofix.yml` to Integration-Tests repo

## Verification

After applying the fix, the CI should pass. Verify by:
1. Pushing the fix to main
2. Watching the CI run at: https://github.com/stranske/Workflows-Integration-Tests/actions
3. Confirming all jobs pass

## Related Files
- Patch file: `0001-fix-Auto-format-files-to-meet-lint-standards.patch`
- Fix script: `scripts/fix-integration-tests-formatting.sh`
