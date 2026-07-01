# Agent Evaluation Runbook

How to run a fair, repeatable Codex-vs-Claude (or any agent) comparison on a
consumer repo, and how to record the result. Written after the issues in
`../troubleshooting/CODEX_COST_AND_RUNTIME_FIXES.md` and
`../troubleshooting/MULTI_AGENT_TESTING_RETROSPECTIVE.md`.

## Principles (why the early comparisons were unfair)

1. **Same task, separate issues/branches per agent** — one issue labelled
   `agent:codex`, an identical one labelled `agent:claude`.
2. **Clean base per comparison.** Reusing one long-lived `eval/<agent>` branch
   across issues accumulates conflicting scaffolds (that's what blocked merging
   PR #61). Start each comparison from `main`.
3. **Fixed infrastructure.** A run during an infra outage measures the infra,
   not the agent. Confirm the agent can actually execute before scoring (see the
   preflight check below).
4. **Trust cross-verdicts, not self-verdicts.** A model judging its own family's
   work is biased — weight the neutral judge (OpenAI `gpt-5.5`) most.

## Preflight (one-time / when infra changed)

Confirm the agent runtime is healthy before spending an evaluation on it. A
quick `agent:codex` smoke issue should show, in the "Keepalive next task (Codex)"
job:

- `Setup API client` ✅ (no `require is not defined` — needs the `.cjs` helper)
- `Run Codex` → `auth: codex_auth_json`, **no** `bwrap: loopback` error
- `codex-output-*.md` is **non-empty** (no `model ... not supported` / `requires
  a newer version` error)
- `Commit and push changes` produces a **real commit** on the PR

Current known-good config (see the troubleshooting docs):
`CODEX_AUTH_JSON` only · CLI `0.139.0` · sandbox `danger-full-access` · model
`gpt-5.5` (override per consumer via `CODEX_MODEL` / `CODEX_SANDBOX` repo vars).

## Per-comparison procedure

### 1. Reset the eval branches to a clean base

```bash
git fetch origin
for b in eval/codex eval/claude; do
  git checkout -B "$b" origin/main
  git push --force origin "$b"
done
```
⚠️ Only after the previous comparison's results are recorded (the reset discards
the prior scaffold from the eval branch). Alternatively use fresh per-issue
branches (`eval/codex-issue-NN`) and skip the reset.

### 2. File the identical task as two issues

- Issue A — body = the task spec — label **`agent:codex`**.
- Issue B — same body — label **`agent:claude`**.

Each agent opens its own PR (`codex/issue-A` → `eval/codex`,
`claude/issue-B` → `eval/claude`).

### 3. Let the keepalive loop run to completion

Watch the Work Log on each PR. Healthy completion ends at `tasks-complete` (or
all task checkboxes ticked). If it stalls, see the decision tree in
`MULTI_AGENT_TESTING_RETROSPECTIVE.md`. Nudge with `agent:retry` if needed.

### 4. Merge each PR into its eval branch

If conflicts appear, the eval branch wasn't clean — re-do step 1. The keepalive
conflict resolver handles *incidental* drift only, not competing scaffolds.
(Gate may be red if the consumer's CI is Python-oriented against a JS project;
for eval branches you can merge past failing checks.)

### 5. Run verify:compare on each merged PR

- PRs merged to `main`: the `verify:compare` **label** works.
- PRs on **eval branches**: use **Actions → `agents-verifier.yml` → Run
  workflow** (`workflow_dispatch`) with the PR number and mode `compare`. (The
  label is unreliable on non-`main` merges.)

Each run posts a multi-provider verdict (OpenAI `gpt-5.5` + Anthropic
`claude-opus-4-7` + GitHub Models). The metered slots only run because the
verifier sets `LLM_ALLOW_METERED` — no other workflow spends those keys.

### 6. Score with the scorecard

| Metric | Where |
|---|---|
| Verdicts (PASS/CONCERNS/FAIL + confidence) | verify:compare comment |
| Neutral-judge score (OpenAI `gpt-5.5`) | verify:compare comment — weight highest |
| Cycles | Work Log row count |
| Commits | PR header |
| Files changed / scope | PR → Files tab |
| Rate-limited rounds | `bypass-rate-limit` rows in the Work Log |

**Ranking:** correctness (cross-verdicts) first; then efficiency
(cycles/commits) — but only compare efficiency when **both ran on the same,
fixed infrastructure**; then scope tidiness; then resilience.

### 7. Record it

Add a dated report under `docs/evaluations/YYYY-MM-DD-<task>.md` (see
`2026-06-12-prisma-data-model.md` for the format).

### 8. (Optional) Close the loop on an eval branch

`verify:create-new-pr` is now eval-branch-aware. When you add it to a PR that
merged into an eval branch (e.g. `eval/codex`), the generated follow-up issue
carries a `<!-- base-branch: <ref> -->` marker, and the belt dispatcher /
auto-pilot resolve the follow-up PR's base to that same branch instead of the
repository default. So the fix round stays on the eval branch rather than
escaping to `main`. If the marked branch no longer exists, the tooling logs a
warning and falls back to the default branch (dispatch still succeeds).

## Immediate next action: clean Codex re-run (Prisma task)

To settle the efficiency question left open by the 2026-06-12 report:

1. Record/keep the current `eval/codex` (#61) result — already in
   `2026-06-12-prisma-data-model.md`.
2. Reset `eval/codex` to `main` (step 1 above).
3. Re-file the Prisma data-model spec as a new `agent:codex` issue.
4. Let it run on the fixed infra; merge; run verify:compare.
5. Compare its commit/round count against Claude's #63 (~8 commits / ~9 rounds)
   — now apples-to-apples.
