# Agent Evaluation — Multi-Tenancy Middleware (2026-06-13)

**Task (same spec, separate issues per the eval flow):** request-scoped tenant
resolution + a Prisma client guard extension (`$extends`) that enforces
tenant isolation, with tests, seed data, and docs.

| Agent | Issue | PR | Eval branch |
|---|---|---|---|
| Codex | #72 | [#73](https://github.com/iamkayleb/bukay/pull/73) | `eval/codex` |
| Claude | #74 | [#75](https://github.com/iamkayleb/bukay/pull/75) | `eval/claude` |

Both PRs merged; both 9/9 tasks. **This is the first fully fair round — both ran
on the now-fixed infrastructure**, so efficiency is finally comparable.

## 1. Quality — verify:compare verdicts

| | Codex (#73) | Claude (#75) |
|---|---|---|
| **OpenAI `gpt-5.5`** (neutral judge) | ✅ **PASS — 82%** | ⚠️ **CONCERNS — 78%** |
| **Anthropic `claude-opus-4-7`** | ⚠️ CONCERNS — 75% *(cross)* | ✅ PASS — 80% *(self\*)* |

\* Anthropic judging Claude's own PR is a **self-verdict** (same model family) —
biased toward PASS; weight it lightly.

**Don't misread this as "both got one PASS + one CONCERNS, tie."** Weight the
**neutral judge (OpenAI `gpt-5.5`)**, same judge on the same task:

> **Codex PASS 82% vs Claude CONCERNS 78%.**

Claude's only PASS came from its **own family**; its **neutral** judge raised
concerns. Codex's PASS came from the **neutral** judge; its CONCERNS came from a
cross judge on a narrower issue. **On the unbiased signal, Codex is ahead this
round.**

### Concern severity (this matters more than the labels)

| | Codex (#73) — flagged by Anthropic | Claude (#75) — flagged by OpenAI (neutral) |
|---|---|---|
| What | `prisma/seed.ts` upsert mixes a top-level `tenantId` with a compound unique key → invalid `WhereUniqueInput` | the `$extends` guard may be registered under **capitalized model names instead of delegates → tenant guard ineffective in production** |
| Where | **seed/demo data** (dev-time, fails loudly at seed) | **the core tenant-isolation feature** (the whole point of the task) |
| Tests | tests use assertion helpers, not full DB queries | **tests cover a proxy wrapper, not the real `$extends` integration → green tests, false confidence** |
| Blast radius | low / contained | **high — silent tenant-isolation failure + misleading tests** |

Codex's concern is a contained seed-script bug. Claude's neutral-judge concern
is more serious: the security-critical guard may not actually work in
production, and its tests would stay green anyway because they exercise a
wrapper rather than the real code path.

### Score split

| Dimension | Codex (OpenAI/Anthropic) | Claude (OpenAI/Anthropic) |
|---|---|---|
| Correctness | 8.0 / 6.0 | **5.0** / 8.0 |
| Testing | (assertion-helper note) | **6.0** / 9.0 |
| Completeness/quality | ~7.5 avg | mixed |

The judges *disagree most on Claude's correctness and testing* (neutral judge
low: 5.0 / 6.0).

## 2. Efficiency / hygiene (now apples-to-apples)

| Metric | Codex (#73) | Claude (#75) | Winner |
|---|---|---|---|
| Tasks complete | 9/9 | 9/9 | tie |
| Commits | **9** | **28** | **Codex** |
| Keepalive rounds | ~7 | ~9 | Codex (slight) |
| Rate-limited rounds | 0 | 1 | Codex |
| Files changed | comparable | ~12 | ~tie |
| Extra/unrelated changes | — | datasource swap (SQLite vs PostgreSQL) noted | Codex |

Because both ran on fixed infra, this is a **valid** efficiency comparison
(unlike the Prisma round). Codex was **markedly leaner — 9 commits vs 28**.

## 3. Verdict

**Winner this round: Codex**, on both axes:

- **Quality** — the neutral judge passed Codex (82%) and flagged Claude (78%),
  and Claude's concern is the more serious one (core guard possibly ineffective
  + tests that don't exercise the real path).
- **Efficiency** — Codex did it in 9 commits vs Claude's 28, with no rate-limit
  rounds.

Claude's PR *looks* thorough (its self-judge praised "comprehensive testing and
documentation"), but the neutral judge caught that the thoroughness is partly
illusory — the tests validate a wrapper, not the production `$extends`.

## 4. Running scoreboard

| Round | Task | Infra | Result |
|---|---|---|---|
| 1 | Next.js scaffold (#51/#47) | **broken** (Codex confounded) | Claude (Codex FAILed on broken infra) |
| 2 | Prisma data model (#60/#62) | mixed (Codex efficiency confounded) | Claude (neutral judge 90 vs 78) |
| 3 | Multi-tenancy middleware (#72/#74) | **fixed (fair)** | **Codex** (neutral judge 82 vs 78; 9 vs 28 commits) |

**Key framing for the report-out:** Rounds 1–2 were confounded by the
infrastructure issues (documented in
`../troubleshooting/CODEX_COST_AND_RUNTIME_FIXES.md`). **Round 3 is the first
un-confounded, like-for-like comparison — and Codex won it.** That strongly
supports the earlier hypothesis that Codex's poor showings were the broken infra,
not the model.

## 5. Patterns to keep watching

- **Codex:** scope discipline (prior round's dual lockfiles) and small
  correctness slips in non-core files (this round's seed bug). Generally lean
  and fast when the infra is healthy.
- **Claude:** writes thorough-*looking* tests that can mock/wrap the real
  integration — green tests giving **false confidence** on the actual production
  path (this round's `$extends` guard). Watch for tests that don't exercise the
  real code path, and unrelated changes (the SQLite/PostgreSQL swap).

## 6. Recommendation

One fair round isn't conclusive — run 2–3 more on the fixed infra (varied task
types: API endpoint, bug fix, refactor) to see whether Round 3's Codex win
holds or whether it's task-dependent. Procedure: `AGENT_EVAL_RUNBOOK.md`.
