#!/usr/bin/env bash
# bulk-set-secrets.sh
#
# Push a batch of GitHub Actions secrets to a target repo in one command.
# Reads key/value pairs from a local .env-style file and uploads each one
# via `gh secret set`.  Values are never echoed; only names are printed.
#
# Usage:
#   scripts/bulk-set-secrets.sh <owner/repo> [env-file]
#
# Examples:
#   scripts/bulk-set-secrets.sh iamkayleb/NewConsumer
#   scripts/bulk-set-secrets.sh iamkayleb/NewConsumer .secrets/consumer.env
#
# Env-file format:
#   KEY=value
#   KEY="value with spaces"
#   # lines starting with '#' are comments
#
#   # For multi-line values (e.g., RSA private keys) use the @file syntax:
#   WORKFLOWS_APP_PRIVATE_KEY=@.secrets/workflows-app.pem
#
# Defaults:
#   env-file: .env (in the current working directory)
#
# Requirements:
#   - gh CLI installed and authenticated with repo admin scope
#   - Target repo exists and you have admin access

set -euo pipefail

TARGET_REPO="${1:-}"
ENV_FILE="${2:-.env}"

if [ -z "$TARGET_REPO" ]; then
  echo "Usage: $0 <owner/repo> [env-file]" >&2
  exit 2
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "error: gh CLI is not installed or not on PATH" >&2
  exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
  echo "error: gh is not authenticated. Run 'gh auth login' first." >&2
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "error: env file not found: $ENV_FILE" >&2
  exit 1
fi

# Verify the target repo exists and we have access before doing anything.
if ! gh repo view "$TARGET_REPO" >/dev/null 2>&1; then
  echo "error: cannot access repo '$TARGET_REPO' (does it exist? do you have admin access?)" >&2
  exit 1
fi

echo "Target repo: $TARGET_REPO"
echo "Source file: $ENV_FILE"
echo ""

success=0
failure=0
skipped=0
failed_keys=()

# Process the env file line-by-line.  Using `while read` with IFS= preserves
# leading/trailing whitespace inside values (important for indented keys).
while IFS= read -r line || [ -n "$line" ]; do
  # Strip trailing CR from CRLF files
  line="${line%$'\r'}"

  # Skip blank lines and comments
  case "$line" in
    ''|\#*) continue ;;
  esac

  # Require KEY=VALUE shape
  if [[ "$line" != *=* ]]; then
    echo "  skip: malformed line (no '='): ${line:0:40}..." >&2
    skipped=$((skipped + 1))
    continue
  fi

  key="${line%%=*}"
  value="${line#*=}"

  # Validate key: uppercase letters, digits, underscore only
  if [[ ! "$key" =~ ^[A-Z_][A-Z0-9_]*$ ]]; then
    echo "  skip: invalid key name '$key'" >&2
    skipped=$((skipped + 1))
    continue
  fi

  # Strip a single layer of matched quotes around the value
  if [[ "$value" =~ ^\".*\"$ ]] || [[ "$value" =~ ^\'.*\'$ ]]; then
    value="${value:1:${#value}-2}"
  fi

  # @file syntax: read value from a file (for multi-line secrets)
  if [[ "$value" == @* ]]; then
    value_file="${value:1}"
    if [ ! -f "$value_file" ]; then
      echo "  FAIL $key: referenced file not found: $value_file" >&2
      failure=$((failure + 1))
      failed_keys+=("$key")
      continue
    fi
    if gh secret set "$key" --repo "$TARGET_REPO" < "$value_file"; then
      echo "  OK   $key  (from $value_file)"
      success=$((success + 1))
    else
      echo "  FAIL $key" >&2
      failure=$((failure + 1))
      failed_keys+=("$key")
    fi
    continue
  fi

  # Normal value — pipe via stdin so it never appears in process args
  if printf '%s' "$value" | gh secret set "$key" --repo "$TARGET_REPO" >/dev/null 2>&1; then
    echo "  OK   $key"
    success=$((success + 1))
  else
    echo "  FAIL $key" >&2
    failure=$((failure + 1))
    failed_keys+=("$key")
  fi
done < "$ENV_FILE"

echo ""
echo "Done. Set $success secret(s), $failure failure(s), $skipped line(s) skipped."

if [ "$failure" -gt 0 ]; then
  echo "Failed keys: ${failed_keys[*]}" >&2
  exit 1
fi
