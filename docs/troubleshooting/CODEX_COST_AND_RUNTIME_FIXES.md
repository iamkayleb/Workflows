# Cost Isolation & Codex Runtime Fixes (Post-Review)

This document chronicles every issue tackled after the maintainer review that
raised two points:

1. **"Update Codex to 5.5, and have a system to keep agents current."**
2. **"The OpenAI API usage is too high — verify:compare is cheap; you must have
   used the API for code production. Keep the API key reserved for verify only."**

Point 2 was correct: an earlier change had wired the metered `OPENAI_API_KEY`
into Codex **code production**, which burns tokens fast and drained the budget
meant for verify:compare. Fixing that, then genuinely getting Codex current
(CLI + model) running in CI, took a chain of fixes documented below.

> For the earlier infrastructure issues (pip, keepalive `agentType` crash,
> `.cjs`/`type:module`, etc.) see
> [`MULTI_AGENT_TESTING_RETROSPECTIVE.md`](./MULTI_AGENT_TESTING_RETROSPECTIVE.md)
> (Issues 1–18). This doc focuses on the cost-isolation + Codex-runtime arc.

## TL;DR — the final working Codex configuration

| Setting | Value | Why |
|---|---|---|
| Code-production auth | `CODEX_AUTH_JSON` (ChatGPT subscription) **only** | API key is reserved for verify:compare; subscription auth is flat-rate |
| Codex CLI version | **`0.139.0`** | Needed for the `gpt-5.5` model |
| Codex sandbox | **`danger-full-access`** | Newer CLIs' bubblewrap sandbox can't init networking on GitHub runners; the runner is already isolated |
| Codex model | **`gpt-5.5`** (plain, not `-codex`) | The only flagship the ChatGPT plan exposes |
| Metered keys (`OPENAI_API_KEY`/`CLAUDE_API_KEY`) | Spent **only** by verify:compare | Gated behind `LLM_ALLOW_METERED` |

Per-consumer overrides (no code change): `CODEX_MODEL`, `CODEX_SANDBOX` repo
variables.

## Summary table

| # | Area | Symptom | Root cause | Fix commit |
|---|------|---------|-----------|-----------|
| A | Cost | OpenAI API budget drained | Codex fallback used `OPENAI_API_KEY` for code production | `ce62d97` |
| B | Cost | metered keys still reachable outside verify | analysis/review steps could use them | `8671fd4` |
| C | Currency | no way to know agents are stale | none existed | `8178ba0` |
| D | Verify | OpenAI slot on old model | `llm_slots.json` pinned `gpt-5.2` | `668c832` |
| E | Runtime | Run Codex skipped (`require is not defined`) | consumer `"type":"module"` broke a CJS helper | `031e2b5` |
| F | Runtime | Codex runs, no edits, no-op (`bwrap: loopback`) | CLI `0.137.0` bubblewrap sandbox fails in CI | `a3dd28a` → `4d1bbf0` |
| G | Runtime | empty output, exit 1 (`gpt-5.2-codex` unsupported) | no `--model`; CLI default rejected by ChatGPT auth | `56d892f` |
| H | Runtime | `gpt-5.1-codex` unsupported | guessed model still not on the plan | `3f55fea` |
| I | Runtime | `gpt-5.5 requires a newer Codex` | `0.101.0` too old for `gpt-5.5` | `4d1bbf0` |
| J | Eval | can't merge to `eval/codex` (conflicts) | competing scaffolds + stale eval branch | operational |

---

## A. API key was being spent on code production

**Symptom:** `OPENAI_API_KEY` hit `insufficient_quota` far faster than
verify:compare could explain (verify runs cost <$100 over months).

**Root cause:** An earlier "fix" let the Codex runner fall back to
`OPENAI_API_KEY` and log the CLI in with it (`codex login --with-api-key`), so
**code generation** ran through the metered API — orders of magnitude more
tokens than verification.

**Fix (`ce62d97`):** Codex code production uses `CODEX_AUTH_JSON` (subscription)
**only**; the runner fails clearly if it's missing/expired instead of falling
back to the API. Removed `OPENAI_API_KEY` from the Codex auth step, the
`codex exec` env, the agent registry, and the keepalive/gate-followups secret
checks. (Claude was already correct — it uses `CLAUDE_CODE_OAUTH_TOKEN` and
never receives an Anthropic API key.)

**Lesson:** Never authenticate a code-producing agent CLI with a metered API
key. Subscription/OAuth tokens for code; API keys for verification only.

## B. 100% isolation — metered providers gated

**Symptom:** Even after A, the metered keys were still reachable by other LLM
steps (session analysis, progress review, issue optimizer, dedup, auto-label).

**Root cause:** Those steps used the provider fallback chain, which would pick
OpenAI/Anthropic whenever the key env var was present.

**Fix (`8671fd4`):** Added a single gate in `tools/llm_provider.py` and
`tools/langchain_client.py`: the OpenAI and Anthropic providers report
themselves **unavailable unless `LLM_ALLOW_METERED` is set**. Only the
verify:compare steps (`reusable-agents-verifier.yml`) set that flag. Everything
else falls back to free GitHub Models. Defense-in-depth: even if a key leaks
into another workflow's env, the provider stays off. `grep LLM_ALLOW_METERED`
shows exactly where metered spend is allowed.

**Lesson:** Enforce cost boundaries in code (a single opt-in flag), not just by
hoping each of ~20 workflows omits the key.

## C. "Keep agents current" system — `maint-53`

**Fix (`8178ba0`):** Added `maint-53-agent-version-check.yml` — a weekly check
that compares the pinned Codex CLI version against the latest npm release and
opens a maintenance issue when behind (Claude/Gemini float to `latest`). Later
extended (`668c832`) to also flag when `config/llm_slots.json` verify models
drift from optional `LATEST_*` repo variables. It **notifies**, it does not
auto-bump — see F for why that matters.

## D. verify:compare OpenAI slot bumped to gpt-5.5

**Fix (`668c832`):** `config/llm_slots.json` slot1 `gpt-5.2` → `gpt-5.5`
(+ the `_default_slots()` fallback and `model_registry.json`).

---

## The Codex runtime gauntlet (PR bukay#61)

After the cost work, a fresh `agent:codex` issue exposed a chain of runtime
failures — each one masking the next. This is the most instructive part.

### E. Consumer `"type":"module"` broke the workflow's CommonJS helper

**Symptom:** "Setup API client" crashed and **"Run Codex" was skipped**:
`create_vendor_aliases.js: ReferenceError: require is not defined in ES module
scope` (because the repo's `package.json` had `"type":"module"`).

**Root cause:** The Codex Next.js scaffold set `"type":"module"` at the repo
root, so Node treated the workflow's CommonJS helper as an ES module.

**Fix (`031e2b5`):** Renamed the helper to `create_vendor_aliases.cjs` (always
CommonJS, independent of any `package.json`).

### F. Codex CLI 0.137.0 broke the sandbox in CI

**Symptom:** Codex ran (auth OK, exit 0) but made **no edits** in ~31s. Output:
`bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted` — every command
failed before touching the repo.

**Root cause:** The "keep current" bump to `0.137.0` (`ce62d97`). Codex sandboxes
commands with **bubblewrap**; in `workspace-write` it creates an isolated network
namespace and brings up loopback, which GitHub-hosted runners don't permit.

**Fix (interim `a3dd28a`, final `4d1bbf0`):** First reverted to `0.101.0`, but
that's too old for `gpt-5.5` (see I), so the real fix is to run the current CLI
with **`--sandbox danger-full-access`** — the runner is already an isolated,
ephemeral sandbox, so Codex's internal one is redundant and its netns setup is
exactly what fails.

### G. Default model `gpt-5.2-codex` rejected by ChatGPT auth

**Symptom:** Sandbox fixed, but Codex exited 1 in ~6s with **empty** output. The
session log: `"The 'gpt-5.2-codex' model is not supported when using Codex with
a ChatGPT account."`

**Root cause:** The runner never passed `--model`, so Codex used its built-in
default (`gpt-5.2-codex`), which ChatGPT-account auth doesn't allow.

**Fix (`56d892f`):** Pass `--model "$CODEX_MODEL"`, configurable via the
`CODEX_MODEL` repo variable.

### H. `gpt-5.1-codex` also unsupported

**Symptom:** Same error for `gpt-5.1-codex`.

**Root cause:** Guessed a `-codex` variant; the plan doesn't expose those.

**Resolution:** Read the account's `codex` → `/model` picker, which showed the
plain flagship **`gpt-5.5`** (no `-codex` suffix). Set the default accordingly
(`3f55fea`). **Lesson:** read the model picker for the exact id a plan exposes;
ChatGPT auth and API auth support different model sets.

### I. `gpt-5.5` requires a newer Codex CLI

**Symptom:** `"The 'gpt-5.5' model requires a newer version of Codex. Please
upgrade…"` on `0.101.0`.

**Root cause:** A catch-22 — `gpt-5.5` needs a recent CLI, but the recent CLI's
sandbox (F) breaks in CI.

**Fix (`4d1bbf0`):** Resolve both at once — move to CLI **`0.139.0`** *and* run
with **`danger-full-access`** so there's no bubblewrap. With `gpt-5.5` + `0.139`
+ `danger-full-access`, Codex authenticates, executes commands, and commits.

**Lesson:** Two independent "Codex versions" matter — the **CLI** (npm package)
and the **model** — and they have independent compatibility constraints. "Latest
CLI" can break the sandbox; "latest model" can require a newer CLI. Validate any
bump by running a real round (which is why `maint-53` notifies, not auto-bumps).

### J. Can't merge into `eval/codex` — conflicts

**Symptom:** PR #61 (`codex/issue-60` → `eval/codex`) shows conflicts in every
shared file (`package.json`, `app/*`, `prisma/schema.prisma`, …) and won't merge.

**Root cause:** `eval/codex` already held a *previous* Next.js scaffold (from the
issue-51 comparison). A second scaffold (issue-60) collides with it. Not an
infra bug — two competing scaffolds. (Separately, the Gate is red because the
consumer's Python CI runs against a JS/Next.js project.)

**Resolution (operational):** For per-issue agent comparisons, give each
comparison a **clean base** — reset `eval/codex` (and `eval/claude`) to `main`
before merging, or use fresh per-issue eval branches
(`eval/codex-issue-60`). The keepalive's conflict resolver
(`conflict_detector.js` + `fix_merge_conflicts.md`) is for *incidental* drift,
not for reconciling two full competing scaffolds.

**Lesson:** Reusing one long-lived eval branch across issues accumulates
conflicting scaffolds. Start each comparison from a clean base.

---

## Operating notes

- **Refresh `CODEX_AUTH_JSON`** in the **consumer** repo (e.g. bukay), not
  Workflows — secrets are per-repo. It does not self-refresh; the
  `health-codex-auth-check` workflow opens an issue before it expires.
- **Per-consumer model/sandbox** overrides without a code change: set the
  `CODEX_MODEL` and `CODEX_SANDBOX` repo variables.
- **Bumping Codex:** when `maint-53` flags a new version, run a real keepalive
  round and confirm the agent executes commands (watch for `bwrap`), and confirm
  the configured model is supported by the auth method, before merging the bump.
