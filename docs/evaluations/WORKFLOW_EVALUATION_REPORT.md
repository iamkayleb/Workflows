# Multi-Agent Workflow Evaluation Report

**Author:** iamkayleb  ·  **System under test:** `iamkayleb/Workflows` multi-agent architecture
**Consumer project:** Booking System for African businesses (`iamkayleb/bukay`)
**Agents compared:** Claude and Codex

---

## 1. Executive summary

Over several months I built a production booking application using the Workflows
multi-agent pipeline, running **Claude** and **Codex** as the coding agents to
determine which better achieves my goals. This report records the per-issue
verdicts, analyses what actually drives throughput, and documents the concrete
failures hit when **creating follow-up issues** and **dispatching agents** — with
the fixes applied to each.

**Headline findings:**

1. **Quality is close; the differentiator is *convergence behaviour*.** Codex
   tends to open with concerns but **iterates to a clean pass** over 2–3 runs.
   Claude is **bimodal** — either a clean first-pass or stuck with persistent
   concerns from the neutral judge.
2. **Operational reliability, not model quality, was the dominant bottleneck.**
   Nearly every stall was infrastructure — auth expiry, dispatch plumbing, or
   oversized generated issues — not the model writing bad code.
3. **The follow-up + dispatch machinery needed substantial hardening** (Section 6).

> ⚠️ **Data caveat:** runs are imbalanced (Codex was run on more tasks than
> Claude) and some outcomes are infra-confounded. Treat the comparison as
> **directional**, not statistically conclusive.

## 2. Methodology

- **Same task, separate branches per agent.** Each issue was run by an agent to a
  PR, then graded.
- **Grading — `verify:compare`** posts a multi-provider verdict. Two judge roles
  matter:
  - **Neutral / cross judge** — the *other* model family grading the work
    (OpenAI grading Claude, Anthropic grading Codex). **This is the trustworthy
    signal.**
  - **Self judge** — the *same* family grading its own work (Anthropic→Claude,
    OpenAI→Codex). Biased toward PASS; **discounted**.
- **Weighting:** a *cross-judge concern* is a real problem; a *self-judge PASS*
  is weak evidence; a *self-judge concern* is notable (even the friendly judge
  objected).

**Legend:** ✅ PASS · ⚠️ CONCERNS · ❌ FAIL/halted · *(cross)* neutral judge ·
*(self)* same-family judge · *(both)* both judges.

## 3. Results — head-to-head (both agents run)

| Task | Codex (run-by-run) | Claude (run-by-run) | Read |
|---|---|---|---|
| **Multi-tenancy middleware** | ⚠️(cross) → ⚠️(self) → ✅(both) | ⚠️(cross) → ⚠️(cross) → ⚠️(cross) | Codex converged by R3; Claude never cleared the neutral judge in 3 runs |
| **Auth (phone + OTP)** | ⚠️(self) → ✅(both) | ✅(both) R1 | Both good; Claude clean first-pass, Codex cleared in 2 |
| **Service CRUD** | ⚠️(self) → ✅(both) | ⚠️(cross) → ⚠️(cross) → ⚠️(cross) | Codex converged by R2; Claude persistent neutral-judge concerns |
| **Dashboard shell** | ⚠️(both) → ⚠️(cross) → ⚠️(both) → ⚠️(self) | ⚠️(both) R1, then **halted** (issue-scoping + rate-limiting) | Hardest task for both; Codex never cleared in 4; Claude halted on infra |
| **Database schema** | ✅(all) R1 | ✅(all) R1 | Both clean first-pass *(see data note)* |

> **Data note — Database schema:** this task was recorded twice for Claude with
> differing outcomes — one clean first-round pass, and one attempt where the
> **follow-up chain-depth limit** was reached and manual fixing was required.
> These are separate attempts; reconcile which represents the canonical run
> before publishing.

## 4. Results — Codex-only tasks

| Task | Codex (run-by-run) | Outcome |
|---|---|---|
| **Business hours + blackout dates** | ⚠️(self) → ⚠️(cross) → ✅(both) | Converged by R3 |
| **Manual booking entry** | ⚠️(self) → ⚠️(self) → ✅ | Converged by R3 |
| **Calendar view** | ✅(all) R1 | Clean first-pass |
| **Clients CRM** | ⚠️(self) → ⚠️(self) → ⚠️(self) | Never cleared (self-judge concerns across 3 runs) |

*(Claude was not run on these four, so no head-to-head is possible here.)*

## 5. Patterns observed

- **Codex — iterative improver.** Frequently opens with concerns, then converges
  to a clean pass (7 of 9 tasks reached ✅). Fails to converge on the hardest
  UI-heavy task (Dashboard) and on Clients CRM (persistent *self*-judge concerns —
  worth investigating, since even its friendly judge objected).
- **Claude — bimodal.** Either a clean first-pass (Auth, Database schema) or
  **stuck with persistent *cross*-judge concerns** (Multi-tenancy, Service CRUD)
  that never cleared across 3 runs. On Dashboard it **halted on infrastructure**
  (issue-scoping + rate-limiting) before it could iterate.
- **The trustworthy signal favours neither cleanly, but flags Claude's
  persistence.** Claude's unresolved concerns came from the *neutral* judge (the
  signal we weight highest) on 2 of its 5 tasks; Codex's unresolved concerns were
  more often self-judge or mixed. However, some of Claude's "stuck" runs were cut
  short by rate-limiting, so it may not have had a fair chance to iterate —
  an infra confound, not necessarily a quality gap.

## 6. What determines throughput

### 6.1 Variables that matter most

- **Auth durability & rate limits (#1 by a wide margin).** Treat token freshness
  as a first-class operational concern. `CODEX_AUTH_JSON` expires and does not
  self-refresh; Claude hits session caps. When auth is down, nothing runs — and
  it *looks* like agent failure.
- **Trigger reliability.** The keepalive loop only advances when something wakes
  it (gate completion, a label event). Fragile triggers cause silent parking.
- **Issue scoping.** Follow-up issues generated by the pipeline are frequently
  far too large, exceeding an agent's session budget and stalling mid-way.

### 6.2 What helped most

- **Cost-isolation architecture.** Separating flat-rate code-production auth from
  the metered `verify:compare` budget cut spend dramatically and kept cost from
  ever gating iteration. Code production has no per-token bill; the metered keys
  are reserved for verification only.
- **Neutral-judge methodology.** Weighting the cross-family judge over
  self-verdicts produced a *trustworthy* quality signal instead of a
  bias-inflated one — the single most important reason the verdicts above are
  meaningful.
- **Observability.** Work Logs, capability reports, and verify:compare comments
  are what made each stall diagnosable in minutes.
- **Human escape hatches.** `agent:retry`, `capability:override`, and
  `force_retry` — automation without manual overrides created inescapable loops.

### 6.3 Largest impediments

1. **Auth expiry / rate limits** — the recurring killer, and hardest to diagnose
   because it presents as agent failure.
2. **Default-to-Codex routing** — follow-ups lost agent affinity and were
   silently rerouted to Codex, corrupting the comparison.
3. **No auto-resume after transient waits** — the loop parks and waits for a
   trigger that never comes.
4. **Follow-up generator producing oversized issues** — one follow-up expanded to
   54 checkbox items, unworkable within any session budget.

## 7. Problems creating follow-up issues & dispatching agents — and the fixes

The follow-up → dispatch → build loop broke in many small, *silent* ways. Each
row is a real failure hit during this build, its root cause, and the fix applied.

### 7.1 Follow-up issue creation

| Problem (symptom) | Root cause | Fix |
|---|---|---|
| `verify:create-issue` ran but **created no issue** | The generator crashed with `ModuleNotFoundError: No module named 'scripts'` (missing `PYTHONPATH`), and the fallback step had no status-check function (`!cancelled()`), so it was **skipped after the failure** — dead code | Added `PYTHONPATH: ${{ github.workspace }}`; added `!cancelled()` to the fallback and create steps so the fallback actually fires on failure/empty output |
| Follow-up issues **routed to the wrong agent** (a Claude follow-up ran as Codex) | The resolver read only `agent:*` labels; when the label was dropped (by the block flow) it fell back to the registry default (Codex), ignoring `from:claude` | Resolver now honours `from:<agent>` / `runner:<agent>` affinity before the default |
| Follow-ups **blocked in an inescapable loop** | The capability check adds `needs-human` **and strips the `agent:*` label** on a `BLOCKED` verdict, and re-runs on every re-add — so re-adding the agent label just re-blocked it | Added a `capability:override` escape hatch: when a human applies it, the block is skipped, `needs-human` is cleared, and the agent label is preserved |
| Eval-branch follow-ups **escaped to `main`** | Follow-up PRs always targeted the default branch | Follow-up issue now carries a `<!-- base-branch: X -->` marker that the dispatcher/auto-pilot honour, keeping the fix on the originating branch |
| Follow-up issues **far too large** (54 tasks) | The generator explodes each real task into `Define / Implement / Validate` triplets plus per-model rows | Split oversized issues by hand for now; recommended cap: emit one checkbox per real task and hard-split issues above ~10 tasks |

### 7.2 Agent dispatch

| Problem (symptom) | Root cause | Fix |
|---|---|---|
| Bridge failed with **`401 Bad credentials`** at PR creation | The bot PAT (`OWNER_PR_PAT`) had expired but was still present, so the `||` token chain selected it instead of falling through — the fallback never fired | Added `resolve_working_token.js`: probes each candidate and picks the first that **authenticates**, falling through an expired PAT; plus `health-47-pat-check` to warn before a PAT dies |
| Bridge failed: **"Exactly one `agent:*` label is required"** even though `bridge_agent: claude` was set in the dispatch form | The resolve-agent-label step derived the agent solely from the issue's labels and **ignored the `bridge_agent` input** | Bridge now honours `inputs.agent` as a fallback when the issue has no `agent:*` label |
| Issue stuck `status:in-progress` with **no PR created** | Dispatched via the **belt dispatcher**, whose belt *worker* never runs in this consumer — it transitioned the issue but couldn't open the PR; `in-progress` then blocked the working path | Use the **issue-bridge** path (`Agents 63 Issue Intake → agent_bridge`), which is what actually creates bootstrap PRs here |
| Keepalive **parked and never resumed** (`wait (gate-pending)` / `missing-agent-label`) | The loop treats these as transient waits but has **no mechanism to wake itself** once they clear; `missing-agent-label` also fired on stale labels from the `workflow_run` payload | Manual unstick via keepalive dispatch (`pr_number`, `force_retry`); recommended durable fix: a scheduled re-poke of parked PRs + fresh label fetch |
| Confusion: **no "Claude belt dispatcher"** | The dispatcher is agent-agnostic but its file is named `*-codex-belt-*` (legacy) | Documented: use the shared dispatcher with `agent_key: claude`; recommended rename to an agent-neutral name |

## 8. Recommendations

1. **Fix reliability before re-scoring.** Auth-freshness monitoring, routing
   affinity, capability override, PAT health, and dispatch hardening are now in
   place — but must be **merged to `main` and synced** to take effect. Until then
   the comparison keeps getting confounded.
2. **Cap generated issue size** (≤10 tasks; kill the triplet explosion) so
   agents stop stalling mid-issue.
3. **Re-run the comparison on the fixed, synced infrastructure** with balanced
   task coverage (run Claude on the same tasks as Codex) before drawing a final
   verdict. Weight the neutral judge; exclude infra-confounded runs.
4. **Provisional read:** Codex's *convergence* (concerns → pass) is the more
   reliable pattern for autonomous building; Claude excels when it first-passes
   but stalls on the neutral judge or on infra. This needs confirmation on clean,
   balanced runs.

---

*This report reflects data gathered during active development; several outcomes
were affected by the infrastructure issues catalogued in Section 7, which is why
Section 8 prioritises reliability fixes before a conclusive agent verdict.*
