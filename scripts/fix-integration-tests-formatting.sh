#!/bin/bash
# Script to fix formatting issues in Workflows-Integration-Tests repository
# This applies the black formatter to the files that were causing CI failures

set -euo pipefail

REPO_DIR="${1:-.}"

cd "$REPO_DIR"

echo "Fixing formatting issues in Integration-Tests repository..."

# Install black if not available
if ! command -v black &> /dev/null; then
    echo "Installing black..."
    python3 -m pip install black --quiet
fi

# Format the problematic files
echo "Running black on scripts/validate_dependency_test_setup.py..."
black scripts/validate_dependency_test_setup.py

echo "Running black on tests/test_dependency_version_alignment.py..."
black tests/test_dependency_version_alignment.py

echo "✅ Formatting complete!"
echo ""
echo "Changes made:"
git --no-pager diff --stat

echo ""
echo "To commit and push these changes:"
echo "  git add -A"
echo "  git commit -m 'fix: Auto-format files to meet lint standards'"
echo "  git push"
