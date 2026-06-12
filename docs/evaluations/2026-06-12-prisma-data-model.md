# Agent Evaluation — Multi-Tenant Prisma Data Model (2026-06-12)

**Task (same spec, separate issues per the eval flow):** define the Prisma data
model — `Tenant, User, Service, Staff, BusinessHour, Client, Booking, Payment,
AuditLog`, `tenantId` + `@@index([tenantId])` on all tenant-scoped tables,
initial migration + seed (demo tenant + 3 services), and `docs/DATA_MODEL.md`.

| Agent | Issue | PR | Eval branch |
|---|---|---|---|
| Codex | #60 | [#61](https://github.com/iamkayleb/bukay/pull/61) | `eval/codex` |
| Claude | #62 | [#63](https://github.com/iamkayleb/bukay/pull/63) | `eval/claude` |

Both PRs were merged and evaluated with `verify:compare`.

## 1. Quality — verify:compare verdicts

| | Codex (#61) | Claude (#63) |
|---|---|---|
| **OpenAI `gpt-5.5`** (neutral judge) | ✅ PASS — **78%** | ✅ PASS — **90%** |
| **Anthropic `claude-opus-4-7`** | ✅ PASS — 85% *(cross)* | ✅ PASS — 92% *(self\*)* |
| **Consensus** | PASS (unanimous) | PASS (unanimous) |

\* Anthropic judging Claude's own PR is a **self-verdict** (same model family) —
discount it for bias. Claude's unbiased judge is OpenAI.

**Cleanest apples-to-apples signal:** the **same neutral judge (OpenAI
`gpt-5.5`)**, on the **same task**, rated **Claude 90%** vs **Codex 78%**. Both
pass; Claude scores higher.

### Detailed scores (where reported)

| Dimension | Codex | Claude |
|---|---|---|
| Correctness | PASS | 9.0/10 |
| Completeness | PASS | 9.5/10 |
| Quality | PASS | 8.5/10 |
| Risks | PASS | 8.0/10 |
| Testing | minimal direct Prisma validation (noted) | OpenAI 7.0 (static) / Anthropic 9.0 |

### Concerns raised by judges

- **Codex (#61):** dual lockfiles committed (`package-lock.json` **and**
  `pnpm-lock.yaml`), **scope expanded beyond the issue**, minimal direct Prisma
  validation testing.
- **Claude (#63):** none blocking; only a testing-depth split between judges
  (static checks vs enforced coverage).

## 2. Efficiency / hygiene

| Metric | Codex (#61) | Claude (#63) | Notes |
|---|---|---|---|
| Tasks complete | 8/8 | 8/8 | tie |
| Commits | **30** | **8** | see caveat |
| Keepalive rounds | many (retry-heavy) | ~9 | see caveat |
| Rate-limited rounds | 2 | 2 | tie |
| Scope tidiness | dual lockfiles + scope creep | clean | Claude |

## 3. ⚠️ Fairness caveat

**Codex's #61 ran straight through the infrastructure gauntlet that was being
fixed** (`.cjs`/`type:module`, the bubblewrap sandbox, the CLI-version and
model-rejection chain — see `../troubleshooting/CODEX_COST_AND_RUNTIME_FIXES.md`).
Its **30 commits and high round count are inflated by failed/retry rounds and
keepalive checkpoints**, not genuine inefficiency. Claude's #63 ran later on the
**already-fixed** infrastructure. **The efficiency columns are therefore not
apples-to-apples** — do not read "30 vs 8 commits" as Codex being ~4× less
efficient.

## 4. Verdict

Both agents delivered an acceptance-meeting Prisma data model — a clear
improvement over the prior round (where Codex failed on broken infra). On the
comparable dimensions:

- **Quality:** **Claude edges it.** The neutral judge scored it higher (90% vs
  78%), and it drew **no scope/hygiene concerns**; Codex committed dual lockfiles
  and expanded beyond the issue.
- **Efficiency:** **Inconclusive** this round due to the infra confound on Codex.

**Winner: Claude**, on quality and tidiness — narrowly, with both passing. First
round where both produced mergeable, criteria-meeting work.

## 5. Follow-up

A clean Codex re-run on the now-fixed infrastructure is needed to settle the
efficiency question (procedure: `AGENT_EVAL_RUNBOOK.md`). Expected: Codex's
commit/round count drops sharply. Real differentiator to keep watching: **scope
discipline** (Codex adds out-of-scope files; Claude stays within the issue).

## Prior round (for reference)

The first comparison (Next.js scaffold, issue-51) ran during the broken-infra
window: Codex (#52) **failed** both independent judges (missing app code,
vendored `node_modules`); Claude (#47) passed with concerns. That result
reflected "Codex on broken infra," which this round corrects.
