# Agent Evaluation — Claude vs Codex — Round <N> (<YYYY-MM-DD>)

> **How to use this template.** Replace every `<…>` and the illustrative numbers
> below with your own. The data here is a *worked example*, not real results —
> it exists to show the shape. Pull the per-run numbers with
> `scripts/agent_eval_pull.py`; fill the manual columns (AC %, test quality,
> scope) by eye. Keep the six sections in this order — it's the order a
> cost-focused boss reads in.

---

## 1. Decision & confidence (read this first)

**On 4 valid, like-for-like runs (2 matched pairs):**

- **Quality:** effectively tied on the neutral judge — **Claude 81.5 avg vs Codex 81.0 avg**. But the split matters: Codex was more *consistent* (both runs PASS), while Claude took one **CONCERNS** on a security-relevant run.
- **Efficiency:** **Codex wins** — leaner (avg 6 rounds vs 7.5; 8.5 commits vs 16.5) and tidier (no scope creep vs one unrelated change from Claude).
- **Recommendation:** **Lean Codex for now**, on efficiency + scope discipline at parity quality — but **confidence is LOW–MEDIUM**: only 2 matched pairs survived, because **3 of 7 attempts (43%) were lost to infrastructure, not agent quality** (see §4).

> Bottom line for the decision: the agents are close on quality; the real story is
> that our infrastructure ate almost half the runs. Fixing that is higher-leverage
> than choosing between the two.

## 2. Methodology — how runs qualified (the validity gate)

Same task text, same acceptance criteria, same base commit, **same fixed infra
snapshot**, right-sized issues (≤10 tasks). A run is scored as an *agent* data
point only if it passed **all** of:

1. Preflight auth healthy (token not expired, session budget available)
2. Ran on the same fixed infra snapshot as its pair
3. Correct agent actually executed (routing verified in the log)
4. Produced real work (commits; not a silent no-op)
5. Issue within the size envelope

Runs failing any of 1–5 are **excluded and logged in §4**, never scored. Quality
is graded by the neutral judge (OpenAI `gpt-5.5`); same-family self-verdicts are
discounted.

## 3. Scorecard (valid runs only)

### Quality (neutral judge = OpenAI `gpt-5.5`)

| Issue | Agent | Verdict | Score | Corr | Comp | Qual | Test | Risk | AC % *(manual)* |
|---|---|---|---|---|---|---|---|---|---|
| A — Services CRUD | Claude | ✅ PASS | **85** | 9 | 9 | 8 | 8 | 8 | 100% |
| A — Services CRUD | Codex | ✅ PASS | **80** | 8 | 8 | 8 | 7 | 8 | 100% |
| C — Booking engine | Claude | ⚠️ CONCERNS | **78** | 6 | 8 | 8 | 6 | 6 | 90% |
| C — Booking engine | Codex | ✅ PASS | **82** | 8 | 8 | 8 | 7 | 7 | 100% |
| **Neutral avg** | **Claude** | | **81.5** | | | | | | |
| **Neutral avg** | **Codex** | | **81.0** | | | | | | |

*Cross-judge (Anthropic, context only — discounted for self-bias): Claude A 90 / C 82; Codex A 84 / C 79.*

### Efficiency (cost proxies — code is flat-rate, so these ARE the cost)

| Issue | Agent | Rounds-to-green | Failed rounds | Rate-limited rounds | Wall-clock | Commits | Files | Scope |
|---|---|---|---|---|---|---|---|---|
| A | Claude | 6 | 0 | 0 | 38m | 9 | 11 | clean |
| A | Codex | 5 | 1 | 0 | 41m | 8 | 12 | clean |
| C | Claude | 9 | 1 | 1 | 62m | **24** | 14 | ⚠️ 1 unrelated (SQLite swap) |
| C | Codex | 7 | 0 | 0 | 45m | 9 | 10 | clean |
| **Avg** | **Claude** | 7.5 | 0.5 | 0.5 | 50m | 16.5 | | 1 lapse |
| **Avg** | **Codex** | 6.0 | 0.5 | 0.0 | 43m | 8.5 | | clean |

### Reliability & scope

| Signal | Claude | Codex |
|---|---|---|
| Repeat-run variance (same issue twice) | verdict stable, commit count swingy (9 vs 24) | stable on both axes |
| Failure mode | asked / flagged (no silent-wrong) | asked / flagged |
| Human overrides needed | 1 (`capability:override`) | 0 |
| Out-of-scope changes | 1 (datasource swap) | 0 |

## 4. Confound ledger (excluded runs — infra, NOT agent quality)

**3 of 7 attempts (43%) were lost to infrastructure.** These are not agent
failures and are excluded from §3.

| Issue | Agent | What happened | Category | Fix status |
|---|---|---|---|---|
| B — Auth middleware | Codex | `CODEX_AUTH_JSON` expired mid-run → 0 commits | auth-expiry | token refreshed; health check watched |
| B — Auth middleware | Claude | stale-label stall, never auto-resumed | trigger / no-resume | fix on branch, **not yet synced** |
| D — smoke | Codex | `agent:claude` issue executed as **codex** | routing / no affinity | affinity fix on branch, **not yet synced** |

> **Interpretation for the decision:** the single largest source of lost work this
> round was **not** either model — it was auth expiry, a routing mis-attribution,
> and a no-resume stall. This is where the next investment should go; it also means
> §1's verdict rests on a thin 2-pair sample and should be re-run once the fixes are
> live.

## 5. Cost economics

| Category | Mechanism | This round |
|---|---|---|
| Code production (both agents) | Flat-rate subscription auth | **$0 marginal** — no per-token bill; throttled by rate limits |
| Verification (verify:compare) | Metered API, gated to verify only | ~$<X> *(fill in actual)* — the only metered spend |
| CI / Actions | Runner minutes | within plan |

**The real cost is human time, not dollars.** Under flat-rate auth, "cost per
task" reduces to rounds + interventions: **Codex ~6 rounds / 0 overrides** vs
**Claude ~7.5 rounds / 1 override** per issue. Codex is the cheaper agent *in the
only currency that varies* here.

## 6. Readiness caveats (what must be true before we rely on this)

- Merge + sync the infra fixes (auth-freshness monitoring, routing affinity,
  stale-label resume, capability override). Until then, expect ~40% confound loss
  and treat §1 as provisional.
- Re-run this round on the fixed snapshot to lift confidence from LOW–MEDIUM to
  HIGH (target: ≥4 matched pairs, <10% confound loss).
- Keep issues ≤10 tasks; the one 24-commit run correlated with a large, churny
  issue, not genuine inefficiency.

---

### Appendix — data provenance
Per-run rows pulled with `scripts/agent_eval_pull.py <PR> --repo <consumer> --out round-<N>.csv`.
Manual columns (AC %, test quality, scope) scored by reviewer. Procedure:
`AGENT_EVAL_RUNBOOK.md`. Cost-proxy rationale: `AGENT_EFFICIENCY_TEMPLATE.md`.
