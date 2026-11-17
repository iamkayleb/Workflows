#!/usr/bin/env bash
# Disable the evaluation pipeline on iamkayleb/bukay.
#
# Keeps ordinary repo CI: CI, Gate, Maint Coverage Guard, Lighthouse, Dependabot.
# Disables everything else — the belt, keepalive, issue intake and optimizer,
# autofix, the eval-lane automation, and the base guard that rewrites the base
# of any PR on a `<agent>/issue-N` branch to `eval/<agent>`.
#
# Reversible: swap `disable` for `enable` on any line, or use the Actions tab.
set -u
REPO="${REPO:-iamkayleb/bukay}"
KEEP='ci\.yml|lighthouse|dependabot|coverage|pr-00-gate'

ok=0; fail=0
while IFS=$'\t' read -r id path; do
  case "$path" in "") continue;; esac
  if printf '%s' "$path" | grep -qiE "$KEEP"; then
    printf '  keeping   %s\n' "$path"; continue
  fi
  if gh api -X PUT "repos/$REPO/actions/workflows/$id/disable" >/dev/null 2>&1; then
    ok=$((ok+1)); printf '  disabled  %s\n' "$path"
  else
    fail=$((fail+1)); printf '  FAILED    %s\n' "$path"
  fi
done < <(gh api "repos/$REPO/actions/workflows?per_page=100" \
           --jq '.workflows[]|select(.state=="active")|"\(.id)\t\(.path)"')

printf '\ndisabled: %s   failed: %s\n' "$ok" "$fail"
printf '\nstill active:\n'
gh api "repos/$REPO/actions/workflows?per_page=100" \
  --jq '.workflows[]|select(.state=="active")|"  \(.name)"'
