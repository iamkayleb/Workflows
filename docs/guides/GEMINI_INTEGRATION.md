# Gemini Agent Integration

How the Gemini CLI agent was added to the Workflows automation pipeline alongside Codex and Claude.

## What Was Done

### 1. Registry Entry

Added `gemini` to `templates/consumer-repo/.github/agents/registry.yml`:

```yaml
gemini:
  display_name: Gemini
  runner_workflow: .github/workflows/reusable-gemini-run.yml
  required_secrets:
    - GEMINI_API_KEY
  branch_prefix: gemini/issue-
  automation_logins:
    - kayleb-automation-bot
  readiness_candidates:
    - kayleb-automation-bot
  preflight:
    assign_user: kayleb-automation-bot
    command_phrase: ''
    enabled: true
  capabilities:
    pr_keepalive: true
    pr_autofix: true
    belt: true
    verifier_checkbox: true
```

### 2. Reusable Runner Workflow

Created `.github/workflows/reusable-gemini-run.yml` modeled after the Codex and Claude runners. Key differences from other runners:

- Installs `@google/gemini-cli` via npm
- Authenticates via `GEMINI_API_KEY` (Google AI Studio key)
- Requires a `~/.gemini/settings.json` config for headless/CI mode
- Supports `--yolo` flag for auto-approving tool executions
- Emits the same output contract as Codex/Claude runners (`final-message`, `changes-made`, `commit-sha`, etc.)

### 3. Keepalive Pipeline (agents-81-gate-followups.yml)

Added three Gemini-specific jobs to the active keepalive workflow:

- **`run-gemini`**: Dispatches to `reusable-gemini-run.yml` when `agent_type == 'gemini'`
- **`autofix-gemini`**: Runs Gemini for autofix when the prepare step routes to Gemini
- Updated the **summary** job to collect outputs from all three agents
- Updated the **metrics** job to include `geminiAutofixResult`
- Added **agent-specific preflight** validation (case/esac) so each agent type checks only its own secrets

### 4. Labels

- `agent:gemini` — triggers Gemini routing via issue intake
- `from:gemini` — marks PRs created by/for Gemini

### 5. Consumer Secrets

The `GEMINI_API_KEY` secret must be set on each consumer repo that uses Gemini. Get the key from [Google AI Studio](https://aistudio.google.com/apikey).

## Gemini CLI in CI — Authentication

The Gemini CLI (`@google/gemini-cli`) does not auto-detect API keys from environment variables alone. In CI, it needs explicit configuration to avoid interactive OAuth prompts.

### Required Configuration

Create `~/.gemini/settings.json` before invoking the CLI:

```json
{
  "selectedAuthType": "api-key",
  "theme": "None"
}
```

The `selectedAuthType: "api-key"` tells the CLI to use the `GEMINI_API_KEY` environment variable instead of attempting browser-based OAuth (which fails in headless CI).

The reusable runner handles this automatically in the "Configure Gemini CLI for CI" step.

### Diagnostics Step

The runner includes a pre-run diagnostics step that logs:
- Gemini CLI version
- Whether `GEMINI_API_KEY` is present (length only, never the value)
- Config file contents
- TTY status

This helps debug auth or quota failures without exposing secrets.

## Issues Encountered and Fixes

### 1. Bash Syntax Error in Commit Step

**Symptom**: Workflow failed at the commit/push step with a bash parse error.

**Cause**: The string `Gemini (keepalive|autofix|verifier)_report_enriched.json` appeared unquoted in a `git reset HEAD --` command. Bash interpreted the `(` as subshell syntax.

**Fix**: Replaced the glob pattern with the specific filename (`autofix_report_enriched.json`).

### 2. Gemini CLI Silent Exit Code 1

**Symptom**: The "Run Gemini" step exited immediately with code 1, producing no stdout or stderr.

**Cause**: Without `~/.gemini/settings.json`, the CLI attempted interactive OAuth, detected no TTY, and exited silently.

**Fix**: Added the "Configure Gemini CLI for CI" step that writes `settings.json` with `"selectedAuthType": "api-key"`. Also added separate stderr capture (`2>gemini_stderr.txt`) so failures produce visible output.

### 3. TerminalQuotaError (Free Tier Limit)

**Symptom**: After auth was fixed, the CLI authenticated successfully but returned `TerminalQuotaError`.

**Cause**: The Google AI Studio free tier allows only ~20 requests/day for `gemini-3-flash`. The integration testing exhausted the daily quota.

**Resolution**: Not a code bug. Options: wait for daily reset, upgrade billing on the API key, or use a separate key for CI vs. local development.

## Preflight Validation

The keepalive workflow's preflight step validates agent-specific secrets before dispatching:

```yaml
run: |
  case "$AGENT_TYPE" in
    codex)
      if [ "$HAS_CODEX_AUTH" = "true" ] || [ "$HAS_APP_ID" = "true" ]; then
        agent_auth_ok=true
      fi ;;
    claude)
      if [ "$HAS_CLAUDE_AUTH" = "true" ] || [ "$HAS_CLAUDE_OAUTH" = "true" ]; then
        agent_auth_ok=true
      fi ;;
    gemini)
      if [ "$HAS_GEMINI_AUTH" = "true" ]; then
        agent_auth_ok=true
      fi ;;
    *)
      # fallback: any auth passes
  esac
```

This prevents dispatching a runner when its auth secrets are missing, giving a clear preflight failure instead of a cryptic CLI error.

## Consumer Repo Setup

To enable Gemini on a consumer repo:

1. **Set the secret**: `gh secret set GEMINI_API_KEY --repo owner/repo` (or use `scripts/bulk-set-secrets.sh`)
2. **Add the label**: Create the `agent:gemini` label (color: `4285f4`)
3. **Verify files exist**:
   - `.github/agents/registry.yml` must include the `gemini` entry
   - `.github/scripts/agent_registry.js` must be present (handles routing)
   - `.github/workflows/agents-81-gate-followups.yml` must include the `run-gemini` job

If any of these are missing, agent routing falls back to the `default_agent` (codex).

## Testing

1. Label an issue with `agent:gemini` on a consumer repo
2. Verify the intake workflow creates a PR with the `agent:gemini` label
3. Check the keepalive evaluate step output: `agent_type` should be `gemini`
4. Confirm the `run-gemini` job dispatches (not `run-codex`)
5. Monitor for auth/quota errors in the Gemini runner logs

## See Also

- [Adding a New Agent](ADD_NEW_AGENT.md) — general checklist for new agents
- [Agent Runner Implementation](AGENT_RUNNER_IMPLEMENTATION.md) — runner patterns
- [Consumer Gate Troubleshooting](CONSUMER_GATE_TROUBLESHOOTING.md)
