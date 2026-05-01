# verify:compare Troubleshooting Log

This document records the issues encountered while setting up and running the `verify:compare` label on merged agent PRs, and how each was resolved.

## Issue 1: Verification model stuck on Sonnet 4.5

**Symptom:** After upgrading the Claude agent runner to Opus 4.7, the `verify:compare` evaluation still used `claude-sonnet-4-5-20250929`.

**Root cause:** The Python fallback in `tools/langchain_client.py` (`_default_slots()`) was updated, but the actual runtime config file `config/llm_slots.json` still had the old model. The JSON file takes priority over the Python defaults when it exists.

**Fix:** Updated `config/llm_slots.json` slot2 from `claude-sonnet-4-5-20250929` to `claude-opus-4-7` (commit `1f5a1ea`). Also updated `LANGCHAIN_MODEL` env vars in `agents-issue-optimizer.yml` and `agents-auto-pilot.yml`.

**Lesson:** `config/llm_slots.json` is the actual runtime config. Python `_default_slots()` is only a fallback for when the JSON file doesn't exist.

---

## Issue 2: Label trigger not firing on eval branch PRs

**Symptom:** After merging PR #33 into `eval/codex` (instead of `main`), adding the `verify:compare` label did nothing. No workflow run appeared.

**Root cause:** The `agents-verifier.yml` workflow uses `pull_request_target` with `types: [labeled]`. While there is no branch filter in the workflow definition, GitHub can be unreliable with label events on already-merged PRs targeting non-default branches.

**Workaround:** Use `workflow_dispatch` instead of the label trigger:
1. Go to Actions > `agents-verifier.yml` > Run workflow
2. Enter PR number and mode (`compare`)

This bypasses the label trigger and directly runs the verifier.

**Status:** The label trigger works reliably for PRs merged to `main`. For eval branches, use `workflow_dispatch`.

---

## Issue 3: OpenAI slot fails with `insufficient_quota`

**Symptom:** The `verify:compare` workflow succeeded (green check) but no comparison comment appeared on the PR. The "Run multi-provider comparison" step showed:

```
Error: LLM invocation failed: Error code: 429 -
'message': 'You exceeded your current quota, please check your plan and billing details.'
'code': 'insufficient_quota'
```

**Root cause:** The `OPENAI_API_KEY` repository secret had no billing credits attached. The key was valid for Codex CLI authentication but had no API quota for the GPT-5.2 verification slot.

**Fix:** Add billing credits at `https://platform.openai.com/settings/organization/billing`.

**Lesson:** The same `OPENAI_API_KEY` is used for both the Codex agent runner and the verification LLM slot. The Codex CLI uses ChatGPT subscription auth separately, but the verifier calls the OpenAI API directly and needs paid API credits.

---

## Issue 4: Anthropic slot fails with `temperature is deprecated`

**Symptom:** The Claude Opus 4.7 verification slot failed with:

```
Error: LLM invocation failed: Error code: 400 -
'type': 'invalid_request_error',
'message': '`temperature` is deprecated for this model.'
```

**Root cause:** `tools/langchain_client.py` hardcoded `temperature=0.1` in `_build_anthropic_client()` for all Anthropic models. Claude Opus 4.7 rejects the `temperature` parameter entirely.

**Fix:** Added `_anthropic_rejects_temperature()` guard function that checks for Opus models, mirroring the existing `_is_reasoning_model()` check for OpenAI o-series models. When the model name contains "opus", the temperature parameter is omitted (commit `b403d1f`).

```python
def _anthropic_rejects_temperature(model: str) -> bool:
    name = model.lower().strip()
    return "opus" in name
```

**Lesson:** When upgrading to newer model versions, check for deprecated parameters. Reasoning-class models (OpenAI o-series, Claude Opus) tend to reject temperature.

---

## Issue 5: No comparison comment posted despite workflow success

**Symptom:** The verifier workflow completed with a green check mark, but no comment appeared on the merged PR.

**Root cause:** The comparison step uses `continue-on-error: true`, so it shows green even when all LLM slots fail. The comment is only posted when `has_results == 'true'`, which requires at least one slot to successfully call an LLM. When both OpenAI (quota) and Anthropic (temperature) slots failed, `has_results` was `false` and the comment was silently skipped.

**Fix:** Resolve the individual slot failures (Issues 3 and 4 above). Once at least one slot succeeds, the comparison comment will be posted.

**Lesson:** A green check on the verifier workflow does NOT mean the comparison ran successfully. Always check the PR for the actual comparison comment.

---

## Summary of required secrets for verify:compare

| Secret | Purpose | Required? |
|--------|---------|-----------|
| `OPENAI_API_KEY` | GPT-5.2 verification slot + Codex CLI auth | Yes (needs billing credits) |
| `CLAUDE_API_KEY` | Claude Opus 4.7 verification slot | Yes (from console.anthropic.com) |
| `GITHUB_TOKEN` | GitHub Models gpt-4.1 slot | Automatic |

All three slots must have valid credentials for a complete comparison. If any slot fails, that provider's verdict will show as `CONCERNS` with an error message, but the comparison will still post if at least one slot succeeds.

---

## Quick reference: Running verify:compare

**Via label (PRs merged to main):**
1. Add `verify:compare` label to the merged PR

**Via workflow_dispatch (any branch):**
1. Actions > `agents-verifier.yml` > Run workflow
2. PR number: `<number>`
3. Mode: `compare`
