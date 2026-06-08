# Multi-Agent Testing Retrospective

This document records every issue encountered during the end-to-end testing
cycle of the Codex and Claude agents on the `iamkayleb/bukay` consumer repo,
the root cause of each, and how it was fixed. It is meant as a field guide so
the next person evaluating agents does not have to rediscover these failures.

For the verification-specific issues (`verify:compare`), see the companion
doc: [`VERIFY_COMPARE_ISSUES.md`](./VERIFY_COMPARE_ISSUES.md). They are
summarized here for completeness but documented in full there.

## How to read this

The testing cycle breaks into phases. A failure in an early phase masks
everything downstream, so they were fixed roughly in this order:

1. **Auth** — can the agent authenticate at all?
2. **Loop dispatch** — does the keepalive loop run and dispatch the agent?
3. **Agent runtime** — does the agent's job get past setup?
4. **Loop state** — does the loop persist progress between rounds?
5. **Verification** — can `verify:compare` produce verdicts?
6. **Scoring** — how to read the results fairly.

## Summary table

| # | Phase | Symptom | Root cause | Fix commit |
|---|-------|---------|-----------|-----------|
| 1 | Auth | Codex fails: `CODEX_AUTH_JSON` expired | ChatGPT subscription token expired | `f25b2eb` |
| 2 | Auth | Codex still fails with `OPENAI_API_KEY` set | CLI needs `codex login --with-api-key`, not just the env var | `fc1e108` |
| 3 | Loop dispatch | Keepalive never runs; "duplicate `review_guard`" | Duplicated step ID broke YAML parse | `24dd9f6` |
| 4 | Loop dispatch | All keepalive jobs skipped | `vars.USE_CONSOLIDATED_WORKFLOWS` set to `true` | repo var change |
| 5 | Loop dispatch | Branch filter shows 0 keepalive runs | `workflow_run` runs appear under `main`, not the PR branch | (understanding) |
| 6 | Agent runtime | Codex dies at "Install Python dependencies": `'src' does not exist` | Consumer `pyproject.toml` assumed a `src/` layout that didn't exist | `a5bb4c2` |
| 7 | Loop state | Agent stops after one task; iteration frozen at 1 | `ReferenceError: agentType is not defined` crashed the summary job every round | `41d7f84` |
| 8 | Loop state | Implementation done but loop won't finish | Acceptance criteria never auto-check, so `allComplete` never trips | known quirk |
| 9 | Verify | Verifier stuck on old model | `config/llm_slots.json` overrides Python defaults | `1f5a1ea` |
| 10 | Verify | `verify:compare` label does nothing on eval branches | Label events unreliable on non-`main` merged PRs | use `workflow_dispatch` |
| 11 | Verify | Workflow green but no comparison comment | All LLM slots failed; `has_results` false → silent skip | `b403d1f` + billing |
| 12 | Verify | OpenAI slot: `insufficient_quota` | API key had no billing credits | add credits |
| 13 | Verify | Anthropic slot: `temperature is deprecated` | Opus rejects the `temperature` param | `b403d1f` |
| 14 | Auto-pilot | Auto-pilot verify step syntax error | Leftover `agentType`/`issueNumber` from a refactor | `f25b2eb` |
| 15 | Cost | OpenAI API budget drained | Codex fallback used `OPENAI_API_KEY` for **code production** (not just verify) | reverted |

---

## Phase 1 — Authentication

### Issue 1: `CODEX_AUTH_JSON` expired

**Symptom:** The Codex runner failed immediately; the auth step reported the
`CODEX_AUTH_JSON` token had expired (JWT `exp` in the past).

**Root cause:** `CODEX_AUTH_JSON` holds a ChatGPT-subscription token that
expires. There was no fallback when it lapsed.

**Fix (`f25b2eb`):** Added an `OPENAI_API_KEY` fallback path to
`reusable-codex-run.yml`. The auth step now tries `CODEX_AUTH_JSON` first,
checks its expiry, and falls back to `OPENAI_API_KEY` if missing/expired. The
agent registry lists both secrets with `required_secrets_mode: any`, and the
fallback is wired through every secret check (keepalive, gate-followups,
autofix).

**Lesson:** `CODEX_AUTH_JSON` (subscription auth) needs no API credits but
expires; `OPENAI_API_KEY` (API auth) needs billing credits but doesn't expire.
Keep both configured so one covers the other.

### Issue 2: Codex CLI ignores `OPENAI_API_KEY` env var

**Symptom:** Even with `OPENAI_API_KEY` set, `codex exec` exited non-zero
after ~16s.

**Root cause:** The Codex CLI does not read `OPENAI_API_KEY` from the
environment for auth — it requires cached credentials in `~/.codex/auth.json`,
created via `codex login --with-api-key`.

**Fix (`fc1e108`):** The auth step now pipes the key into the CLI:
`printenv OPENAI_API_KEY | codex login --with-api-key`.

**Lesson:** Setting an env var is not the same as authenticating a CLI. Check
the tool's actual auth mechanism.

### Issue 15: OpenAI API budget drained by code production (reverted)

**Symptom:** The `OPENAI_API_KEY` hit `insufficient_quota` far faster than
verify:compare usage could explain. (For context: verify:compare has been run
tens of thousands of times over 6 months for well under $100.)

**Root cause:** Issues 1–2 "fixed" Codex auth by falling back to
`OPENAI_API_KEY` and logging the Codex CLI in with it
(`codex login --with-api-key`). That made **code production** run through the
metered API. Generating code burns tokens orders of magnitude faster than
verification, so it rapidly exhausted the API budget that is meant to be
reserved for verify:compare.

**Why this matters:** The two billing surfaces are deliberately separate:

| Purpose | Auth | Billing model |
|---|---|---|
| Code production (agent writing code) | ChatGPT **subscription** (`CODEX_AUTH_JSON`) | flat-rate |
| verify:compare (judging PRs) | OpenAI **API** key (`OPENAI_API_KEY`) | metered, but cheap |

Mixing code production into the API key collapses that separation and makes
verify costs unpredictable.

**Fix (this change):** Reverted the fallback. Codex code production now uses
`CODEX_AUTH_JSON` **only**; if it is missing/expired the runner fails with a
clear "refresh the subscription token" error instead of silently spending API
credits. `OPENAI_API_KEY` was removed from the Codex auth step, the `codex exec`
runtime env, the agent registry, and the keepalive/gate-followups secret
checks. It is now reserved for verify:compare (plus lightweight LLM
session-analysis, which falls back to free GitHub Models when the key is
absent).

**Claude, for comparison, was already correct:** the `Run Claude` step
authenticates with `CLAUDE_CODE_OAUTH_TOKEN` (subscription) and the Claude Code
CLI never receives `ANTHROPIC_API_KEY`, so Claude code production never touches
the metered API.

**Lesson:** Never authenticate a code-producing agent CLI with a metered API
key. Reserve API keys for verification/analysis; use subscription/OAuth tokens
for code production, and refresh those tokens when they expire rather than
falling back to the API.

---

## Phase 2 — Keepalive loop dispatch

### Issue 3: Duplicate `review_guard` step broke the loop

**Symptom:** The keepalive workflow failed to even queue:
`Failed to queue workflow run ... duplicate 'review_guard' identifier`.

**Root cause:** The consumer template's keepalive loop had the
"Evaluate whether to post review" step (`id: review_guard`) duplicated. GitHub
rejects duplicate step IDs at parse time, so the whole workflow never ran.

**Fix (`24dd9f6`):** Removed the duplicate step.

**Lesson:** A YAML parse error stops everything silently — the loop simply
"doesn't run" with no agent activity. Validate workflow YAML after edits.

### Issue 4: `USE_CONSOLIDATED_WORKFLOWS` disabled the loop

**Symptom:** After fixing the YAML, all keepalive jobs showed as **skipped**.

**Root cause:** The `evaluate` job guard is
`if: vars.USE_CONSOLIDATED_WORKFLOWS != 'true'`. The repo had that variable
set to `'true'`, which disables the standalone keepalive loop entirely.

**Fix:** Removed/changed the repository variable in repo Settings → Variables.

**Lesson:** Repo-level variables can silently gate whole workflows. When jobs
are "skipped" rather than "failed," check the job's `if:` conditions and repo
variables first.

### Issue 5: Keepalive runs are hidden by the branch filter

**Symptom:** Filtering the Actions page by `branch:codex/issue-NN` showed
0 (or 1) keepalive runs, suggesting the loop wasn't running — yet commits kept
appearing.

**Root cause:** The keepalive loop is triggered by `workflow_run` (the **Gate**
workflow completing). `workflow_run`-triggered runs always execute against the
**default branch (`main`)**, so they do not show under a PR-branch filter. Only
the `pull_request: labeled` trigger run shows on the branch.

**Fix:** Understanding, not code. To see real loop activity, view the
"Agents Keepalive Loop" workflow runs **without** a branch filter.

**Lesson:** Event-driven loops don't appear where you expect in the Actions UI.
Don't conclude "the loop isn't running" from a branch-filtered view.

---

## Phase 3 — Agent runtime

### Issue 6: `pip install -e .` crashed on non-Python product repos

**Symptom:** Codex died at "Install Python dependencies":
`error in 'egg_base' option: 'src' does not exist or is not a directory` and
`Failed to build 'file:///home/runner/work/bukay/bukay'`.

**Root cause:** The consumer template `pyproject.toml` declared
`[tool.setuptools.packages.find] where = ["src"]`. When that file exists on a
consumer repo with no `src/` directory (e.g., a Next.js product repo),
`pip install -e .` fails — and `set -euo pipefail` killed the agent run before
Codex ever started.

**Fix (`a5bb4c2`):**
- Made the editable install non-fatal in all three reusable runners
  (`reusable-codex-run.yml`, `reusable-claude-run.yml`,
  `reusable-gemini-run.yml`) — it now logs a warning and continues.
- Changed the consumer template `pyproject.toml` to `packages = []` (matching
  the Workflows repo's own approach), with a comment on how to switch to a
  `src/` layout if the repo becomes a Python project.

**Lesson:** Reusable workflows run against repos that aren't necessarily Python
projects. Setup steps that assume a project shape must degrade gracefully.

---

## Phase 4 — Keepalive loop state (the big one)

### Issue 7: `agentType is not defined` crashed the summary job every round

**Symptom:** The agent "ran but stopped after one task." Iteration was frozen
at **1 of 5** across many rounds, task progress stuck at **1/9**, no Work Log
table was written, and the "agent actively working" status never updated.

**Root cause:** In `agents-keepalive-loop.yml`, the `summary` job's
`update-summary` inline script built the `inputs` object with
`agent_type: agentType` — but `agentType` was **never declared in that
script's scope** (only a different job declared it). Every round threw
`ReferenceError: agentType is not defined`, crashing the summary job **before
it persisted state**. Because state never saved:

- `nextIteration` was computed but never written → iteration frozen.
- `appendWorkLogEntry` never ran → no Work Log.
- The "actively working" status comment was never updated.
- `rounds_without_task_completion`, zero-activity counters, task reconciliation
  — none advanced. The loop had no memory, so it could not progress past the
  first task.

**Diagnosis path:** The decisive clue came from the failing run's job list:
the `evaluate` job succeeded but **"Update keepalive summary" failed** with the
ReferenceError. Reproducing it locally showed every neighboring field used a
declared `const` or a `${{ needs.evaluate.outputs.* }}` expression — only
`agent_type` pointed at a bare, undeclared variable.

**Fix (`41d7f84`):** Use the evaluate job's output like every other field:
`agent_type: '${{ needs.evaluate.outputs.agent_type }}'`. Applied to both the
canonical and consumer-template workflows. (Confirmed the other
`agent_type: agentType` references in `reusable-agents-pr-health.yml` are
legitimate — `agentType` is declared locally there.)

**Result:** Iteration began advancing (1 → 5+), tasks moved 1/9 → 6/9, the Work
Log populated, and the loop walked the task list as designed.

**Lesson:** The summary job is where the loop persists its state. If it
crashes, the loop *looks* alive (the agent runs) but has amnesia — it repeats
or stops after one task. This was the same class of bug as the auto-pilot
`agentType` error (Issue 14); a second instance was hiding on the summary path.

### Issue 8: Loop won't finish when only acceptance criteria remain

**Symptom:** All implementation tasks were checked, but the loop kept doing
productive-but-non-completing `ready-extended` rounds (adding incidental files)
instead of converging to `tasks-complete`.

**Root cause:** `allComplete` requires *every* checkbox checked, including the
**acceptance criteria**. By design, acceptance criteria are not auto-cascaded
(they must be independently verified — see `cascadeParentCheckboxes`). So when
only acceptance criteria remained unchecked, `allComplete` stayed false, the
verification path never triggered, and the loop kept running normal task rounds
that couldn't "complete" a criterion by coding.

**Workaround:** Manually verify and tick the acceptance-criteria checkboxes
(when genuinely met — e.g., CI/Gate green satisfies "CI passes"), which lets
the loop run a verification round and stop with `tasks-complete`. Or merge the
PR if the work is done.

**Status:** Known convergence quirk. A candidate improvement: when all
*implementation tasks* are complete but only acceptance criteria remain,
trigger a verification round instead of more `ready-extended` rounds.

---

## Phase 5 — Verification (`verify:compare`)

These are documented in full in
[`VERIFY_COMPARE_ISSUES.md`](./VERIFY_COMPARE_ISSUES.md). In brief:

- **Issue 9 — wrong model:** `config/llm_slots.json` overrides the Python
  `_default_slots()` fallback; updating only the Python file left the verifier
  on the old model (`1f5a1ea`).
- **Issue 10 — label trigger:** the `verify:compare` label is unreliable on
  PRs merged to non-`main` (eval) branches. Use Actions →
  `agents-verifier.yml` → Run workflow (`workflow_dispatch`) with the PR number.
- **Issue 11 — silent skip:** the workflow uses `continue-on-error`, so it goes
  green even when all LLM slots fail; the comparison comment is only posted when
  `has_results == 'true'`.
- **Issue 12 — OpenAI `insufficient_quota`:** the `OPENAI_API_KEY` secret had
  no billing credits. Add credits at platform.openai.com.
- **Issue 13 — Anthropic `temperature is deprecated`:** Opus models reject the
  `temperature` param. Fixed with an `_anthropic_rejects_temperature()` guard
  in `langchain_client.py` (`b403d1f`).

### Issue 14: Auto-pilot verify step syntax error

**Symptom:** `agents-auto-pilot.yml` verify step failed to parse.

**Root cause:** A refactor left dangling `}));` and stale `agentKey`/
`issueNumber` references after a capability-check block was removed.

**Fix (`f25b2eb`):** Cleaned up the leftover code so the dispatch call closes
correctly.

---

## Phase 6 — Scoring methodology (lessons, not bugs)

These aren't failures but hard-won lessons about reading the results:

1. **Trust cross-verdicts, not self-verdicts.** A model judging its own work is
   biased toward PASS. Score Codex's PR by how Claude/GPT judged it, and vice
   versa. `verify:compare` deliberately runs multiple judges for this reason,
   and the loop switches verifier agents for the same reason.

2. **Self-reported checkboxes are not trustworthy.** In one run, Codex marked
   6/9 tasks "done," but both independent judges FAILed the PR — the actual app
   code was missing and the diff was polluted with vendored `node_modules` and
   automation-script edits. Always cross-check checkboxes against an independent
   verdict.

3. **Watch for confounds.** A run that happened *during* a broken-infra window
   (e.g., the `agentType` crash) reflects "agent on broken infra," not the
   agent's true capability. For a fair head-to-head, re-run both agents on a
   fresh issue after the infrastructure is fixed.

4. **The scorecard.** Quality (independent verdicts) outranks everything; then
   efficiency (cycles, workflow minutes), tidiness (files changed, scope
   compliance), and resilience (rate-limited rounds). A PR that PASSES with more
   cycles beats one that FAILS quickly.

| Metric | Where to read it |
|---|---|
| Verdicts (PASS/FAIL + reasoning) | the `verify:compare` comment |
| Cycles | Work Log table row count |
| Workflow minutes | sum of Actions run durations |
| Files changed | PR → Files tab |
| Rate-limited rounds | count of `bypass-rate-limit` rows in the Work Log |

---

## Quick reference: "the agent isn't working" decision tree

1. **Job failed at auth?** → Issues 1–2. Check `CODEX_AUTH_JSON` expiry and the
   `OPENAI_API_KEY` fallback.
2. **Loop never ran / jobs skipped?** → Issues 3–4. Check workflow YAML and
   `USE_CONSOLIDATED_WORKFLOWS`.
3. **Can't find the loop runs?** → Issue 5. Look under `main`, not the PR
   branch.
4. **Job died at "Install Python dependencies"?** → Issue 6. Non-Python repo
   hitting the `src/` assumption.
5. **Runs but stops after one task / iteration frozen?** → Issue 7. Check the
   `summary` job for a crash (this was the headline bug).
6. **Implementation done but won't finish?** → Issue 8. Acceptance criteria need
   manual ticking or a verification round.
7. **`verify:compare` green but no comment?** → Issues 11–13. All slots failed;
   check OpenAI billing and the Anthropic temperature guard.
