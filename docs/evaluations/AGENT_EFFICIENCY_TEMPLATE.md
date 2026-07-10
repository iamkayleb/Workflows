# Agent Efficiency Evaluation — Claude vs Codex

> Purpose: decide which agent to build the full project with, judged on **efficiency
> (quality achieved per unit of cost)** — not on subjective "who did better."
>
> Primary unit of analysis: **per issue**. Secondary rollup: **per phase / whole project**.
>
> This is the adapted version for **this** system. The original template's headline
> **Cost per Passed AC (₦)** has been replaced with the cost *proxies* the workflows
> actually record — see the box below for why.

---

## 0. How to use this doc

1. Freeze the issue before running (same text, same acceptance criteria, same base commit).
2. Run **both** agents on the **same issue**, each on its own branch (`agent:claude`, `agent:codex`).
3. Let each agent build **cumulatively on its own branch** — Claude's issue #7 builds on
   Claude's issue #3, not on Codex's. This is what exposes compounding cost.
4. Pull one row per (issue × agent) with the collector, then paste it into
   `agent-eval-data.csv`:
   ```bash
   python scripts/agent_eval_pull.py <PR> --repo iamkayleb/bukay --out agent-eval-data.csv
   ```
   The columns it emits map 1:1 to the scorecard below.
5. After each phase, complete a **Phase Rollup** section.
6. The headline number is **Rounds-to-Green** and **Wall-clock per Passed AC** — the cost
   proxies — plus the **neutral-judge** verifier score. Everything else explains outliers.

### Fair-fight checklist (do this or the numbers are meaningless)

- [ ] Identical issue text + acceptance criteria for both agents
- [ ] Same base commit / starting state
- [ ] Same model tier where comparable, same tool permissions
- [ ] Issue frozen — no edits between the two runs
- [ ] **Both ran on the same, fixed infrastructure** (an infra outage measures the infra,
      not the agent — see `AGENT_EVAL_RUNBOOK.md` preflight)
- [ ] Run date recorded (model versions drift over time)

---

> ## ⚠️ Why there is no ₦ / USD cost column
>
> In this system, **code production has no per-token bill**:
> - Codex authenticates with `CODEX_AUTH_JSON` (ChatGPT subscription, **flat-rate**).
> - Claude authenticates with `CLAUDE_CODE_OAUTH_TOKEN` (subscription, **flat-rate**).
> - Metered keys (`OPENAI_API_KEY` / `CLAUDE_API_KEY`) are gated behind `LLM_ALLOW_METERED`
>   and spend **only** on `verify:compare`.
>
> So dollars are not the denominator. The metrics pipeline records **rounds, failures,
> wall-clock, and step durations** — never tokens or dollars. Those are your cost proxies.
> Raw token *counts* still exist in per-run agent session-log artifacts if you want a
> secondary proxy, but they don't map to a bill and are not pulled by the collector.

---

## 1. What gets measured

### Cost proxies (the denominator) — no dollars; these are what the system records

| Metric | CSV column | How it's captured | Why it matters |
|---|---|---|---|
| Agent rounds | `rounds` | Keepalive Work Log row count | Primary cost proxy under flat-rate auth |
| Failed rounds | `failures` | Work Log rows with `❌`/failure result | Wasted cycles — the efficiency leak |
| Wall-clock (min) | `wall_clock_min` | Σ Actions run durations on the branch | Time is money when a human waits |
| Run count | `run_count` | # Actions runs on the branch | Compute churn |
| Human interventions (proxy) | `nonbot_comments` | non-bot PR comments | Real cost in a hands-off workflow; confirm by eye |

### Quality (the numerator) — measured, not felt

| Metric | CSV column | How it's captured | Scale |
|---|---|---|---|
| First-pass gate | `first_pass_gate` | passed `pr-00-gate.yml` on first run? | Y/N |
| Verifier verdict (neutral) | `neutral_verdict` / `neutral_confidence` | `verify:compare` OpenAI `gpt-5.5` judge | verdict + 0–100 |
| Verifier dimension scores | `neutral_scores` | neutral judge's Correctness/Completeness/Quality/Testing/Risks | 0–10 each |
| Cross-judge (context) | `other_verdict` / `other_confidence` | Anthropic judge — **discount self-verdicts** | verdict + 0–100 |
| AC coverage | *(manual)* | of AC checkboxes, how many pass when YOU test | % |
| Rework rate | *(manual)* | follow-up issues (`follow-up` label) / bug commits later | count |
| Diff discipline | `files_changed`, `additions`, `deletions` | PR diff stat | ratio / count |
| Test quality | *(manual)* | real tests vs. assertion-free stubs | 1–5 |
| Instruction adherence | *(manual)* | respected `CLAUDE.md` & repo conventions? | 1–5 |

> **Weight the neutral judge.** A model judging its own family's work is biased toward
> PASS. OpenAI `gpt-5.5` is neutral for both agents; weight `neutral_*` highest and treat
> `other_*` as context only.

### Reliability (the tiebreaker)

| Metric | How to capture | Note |
|---|---|---|
| Variance | run the same frozen issue twice — consistent `rounds`/verdict? | predictable beats swingy |
| Failure mode | session-log artifact + Work Log `reason` — asks vs. ships broken silently | silent-wrong is most expensive |

---

## 2. Derived scores (the numbers your report leads with)

```
Rounds to Green        = rounds until gate + verifier pass          # lower is better  (PRIMARY)
Rounds per Passed AC   = rounds / AC_passed                         # lower is better
Wall-clock per Passed AC = wall_clock_min / AC_passed               # lower is better
Failed-round rate      = failures / rounds                          # lower is better
Intervention Load      = nonbot_comments per issue                  # lower is better
Quality Index          = mean(neutral_confidence/10, AC%/10, test_quality, adherence, diff_discipline)
Efficiency Ratio       = Quality Index / normalized_cost_proxy      # higher is better
                         where normalized_cost_proxy blends rounds + wall-clock (z-scored)
```

> Report **Rounds-to-Green** and **Wall-clock per Passed AC** side by side with the
> **neutral verifier score**. If the two agents disagree on cost-proxy vs. quality, that
> disagreement is your most valuable finding.

---

## 3. Per-Issue Scorecard (copy one block per issue)

### Issue #___ — <title>

| Factor | CSV column | Claude | Codex | Notes |
|---|---|---|---|---|
| **COST PROXIES** | | | | |
| Agent rounds | `rounds` | | | |
| Failed rounds | `failures` | | | |
| Wall-clock (min) | `wall_clock_min` | | | |
| Run count | `run_count` | | | |
| Human interventions | `nonbot_comments` | | | confirm by eye |
| **QUALITY** | | | | |
| First-pass gate (Y/N) | `first_pass_gate` | | | |
| Neutral verdict | `neutral_verdict` | | | OpenAI `gpt-5.5` |
| Neutral score (0–100) | `neutral_confidence` | | | weight highest |
| Neutral dimension scores | `neutral_scores` | | | corr/comp/qual/test/risk |
| Cross-judge (context) | `other_verdict`/`other_confidence` | | | discount self-verdict |
| AC coverage (%) | *manual* | | | you test |
| Rework caused (count) | *manual* | | | `follow-up` issues |
| Files touched | `files_changed` | | | |
| Diff lines (+/−) | `additions`/`deletions` | | | |
| Test quality (1–5) | *manual* | | | |
| Instruction adherence (1–5) | *manual* | | | |
| **RELIABILITY** | | | | |
| Consistent on re-run (Y/N) | *manual* | | | |
| Failure mode (asks / silent) | *manual* | | | |
| **DERIVED** | | | | |
| Rounds to Green | | | | |
| Wall-clock per Passed AC | | | | |
| Failed-round rate | | | | |
| Quality Index | | | | |
| **Issue winner** | | | | + one-line why |

**Qualitative note (why the outliers happened):**
> _e.g. "Codex needed 3 gate rounds because it left ESLint errors each pass; Claude
> passed clean but over-engineered the health check with unused config."_

---

## 4. Phase Rollup (complete at end of each phase)

### Phase ___ — <name> (Issues #__–#__)

| Metric | Claude | Codex | Winner |
|---|---|---|---|
| Cumulative rounds | | | |
| Cumulative failed rounds | | | |
| Cumulative wall-clock (min) | | | |
| Total human interventions | | | |
| Issues merged first-pass | | | |
| Integration bugs at issue seams | | | |
| Does phase run end-to-end? (Y/N) | | | |
| **Rounds per Merged Issue** | | | |
| **Efficiency Ratio** | | | |

**Compounding note (the thing per-issue scores can't show):**
> _Did clean early work make later issues cheaper (fewer rounds) for that agent? Did messy
> early work force expensive rework? This is where the real winner usually emerges._

---

## 5. Final Recommendation (end of project or decision point)

- **Per-issue leader:** ______  (best at isolated, well-scoped tasks)
- **Full-project leader:** ______  (best once compounding cost is counted)
- **If they differ, why:** ______
- **Cost-proxy delta over full project:** ______ rounds / ______ min (____%)
- **Recommendation:** ______
- **Caveats / conditions:** (model versions as of ____; infra fixed? ____; issue mix
  skewed toward ____)

---

## Appendix — collector column reference

`scripts/agent_eval_pull.py` emits one CSV row per PR with these columns:

```
pr, agent, issue, merged, first_pass_gate,
rounds, failures, nonbot_comments, run_count, wall_clock_min,
commits, files_changed, additions, deletions,
neutral_provider, neutral_verdict, neutral_confidence, neutral_scores,
other_provider, other_verdict, other_confidence, url
```

Usage:
```bash
# one row to the terminal (with header)
python scripts/agent_eval_pull.py 73 --repo iamkayleb/bukay --header

# accumulate a scorecard (writes header on first append)
python scripts/agent_eval_pull.py 73 --repo iamkayleb/bukay --out agent-eval-data.csv
python scripts/agent_eval_pull.py 75 --repo iamkayleb/bukay --out agent-eval-data.csv

# raw JSON for one PR
python scripts/agent_eval_pull.py 87 --repo iamkayleb/bukay --json
```

Manual-only fields (the collector deliberately leaves these to your judgment): AC coverage,
rework count, test quality, instruction adherence, re-run consistency, failure mode.

See `AGENT_EVAL_RUNBOOK.md` for the fair-fight procedure and the preflight that confirms the
infrastructure is healthy before you spend an evaluation on it.
