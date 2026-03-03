# Phase 5D: Agent Delegation Policy

**Status:** Design specification
**Phase:** 5D (final phase of provider-agnostic plan)
**Last Updated:** February 17, 2026

## Purpose

Define the **system-driven delegation policy** for `agent:auto` label routing. This policy determines which agent (Codex or Claude) should handle a given keepalive round based on objective metrics.

## Principles

1. **System-driven, not agent-driven:** The policy decides which agent runs; agents do not self-assign
2. **Deterministic and auditable:** Every decision is logged with reasoning
3. **Conservative by default:** Prefer stable agent (Codex) unless clear signal to switch
4. **Fail-safe:** If Claude unavailable or metrics unclear, fall back to Codex
5. **No thrashing:** Once switched, require evidence before switching back

---

## Policy Decision Tree

### When `agent:auto` Label is Present

```
┌─────────────────────────────────────────────────────────────┐
│  PR has agent:auto label                                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │  Load keepalive state         │
        │  - current_agent              │
        │  - iteration_count            │
        │  - recent_effectiveness       │
        └──────────────┬────────────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │  Check prerequisites          │
        │  - Secrets available?         │
        │  - Gate status?               │
        │  - Rate limit capacity?       │
        └──────────────┬────────────────┘
                       │
          ┌────────────┴────────────┐
          │                         │
          ▼                         ▼
    Prerequisites met?        Prerequisites failed
          │                         │
          │                         ▼
          │                   Use current_agent or Codex
          │                   (no switch)
          │
          ▼
    ┌─────────────────────────────┐
    │  Evaluate effectiveness      │
    │  - Commits per round         │
    │  - Tasks completed           │
    │  - Gate pass history         │
    │  - Stall detection           │
    └──────────────┬────────────────┘
                   │
                   ▼
    ┌─────────────────────────────────────────┐
    │  Decision:                               │
    │  1. If no current agent → Codex default  │
    │  2. If effective → continue current      │
    │  3. If stalled (3+ rounds, no progress)  │
    │     → switch to other agent              │
    │  4. If switched within last 5 rounds     │
    │     → continue current (anti-thrash)     │
    └──────────────┬──────────────────────────┘
                   │
                   ▼
    ┌─────────────────────────────┐
    │  Record decision in state    │
    │  - chosen_agent              │
    │  - reason                    │
    │  - timestamp                 │
    │  - switch_count              │
    └─────────────────────────────┘
```

---

## Metrics Definitions

### Effectiveness Signals

| Metric | Definition | Threshold | Weight |
|--------|------------|-----------|--------|
| **Commits per round** | Number of commits pushed in last N rounds | ≥1 commit in last 3 rounds | High |
| **Tasks completed** | LLM-detected task completions | ≥1 task checked in last 3 rounds | High |
| **Gate pass** | PR passes gate after agent run | Gate passed within 2 rounds | Medium |
| **Change velocity** | Files changed per round | ≥1 file changed per round | Medium |
| **Stall detection** | Consecutive rounds with no progress | ≥3 rounds with 0 commits/tasks | Critical |

### Capacity Signals

| Metric | Definition | Threshold |
|--------|------------|-----------|
| **Secret availability** | Required auth secrets present | CODEX_AUTH_JSON or CLAUDE_AUTH_JSON |
| **Rate limit headroom** | Remaining API calls per hour | ≥50 calls remaining |
| **Concurrent runs** | In-progress keepalive runs for this agent | ≤2 concurrent |

---

## Policy Rules

### Rule 1: Prerequisites

**MUST** have these to run ANY agent:
- Gate must have run at least once (status: success, failure, or pending)
- PR must have unchecked tasks in body
- No `agents:paused` label

**MUST** have these to run SPECIFIC agent:
- Codex: `CODEX_AUTH_JSON` secret available
- Claude: `CLAUDE_AUTH_JSON` secret available
- Sufficient rate limit headroom (≥50 calls/hour)

**If prerequisites fail:** Skip agent run with reason `missing-prerequisites`

### Rule 2: Initial Agent Selection

**On first round (no current_agent in state):**
1. If `agent:codex` label present → Codex
2. If `agent:claude` label present → Claude
3. If `agent:auto` label present → Codex (default)
4. If no agent label → no agent (keepalive disabled)

**Reasoning:** Codex is the stable, proven default. Only switch if explicitly requested or after evidence suggests Claude would be better.

### Rule 3: Continue Current Agent

**If current agent is effective:**
- Has made ≥1 commit in last 3 rounds, OR
- Has completed ≥1 task in last 3 rounds, OR
- Gate passed after agent run in last 2 rounds

**Action:** Continue with current agent
**Reasoning:** "If it's working, don't change it"

### Rule 4: Stall Detection & Switch

**If current agent is stalled:**
- ≥3 consecutive rounds with 0 commits, AND
- ≥3 consecutive rounds with 0 task completions, AND
- Gate has not passed in last 5 rounds, AND
- Agent has run at least once (not waiting for external factors)

**Action:** Switch to other agent (Codex ↔ Claude)
**Reasoning:** "Try a different approach when stuck"

**Switch cooldown:** After switching, require ≥5 rounds before considering another switch (anti-thrash)

### Rule 5: Fail-Safe Fallbacks

**If Claude selected but unavailable:**
- Missing `CLAUDE_AUTH_JSON` → Fall back to Codex with reason `claude-unavailable`

**If Codex selected but unavailable:**
- Missing `CODEX_AUTH_JSON` → Fail with reason `codex-unavailable` (critical)

**If both unavailable:**
- Set action: `missing-agent-label` and skip run

### Rule 6: Manual Override

Users can override automatic selection:
- Apply `agent:codex` label → Always use Codex (remove `agent:auto`)
- Apply `agent:claude` label → Always use Claude (remove `agent:auto`)
- Apply both → Invalid, keepalive will fail-fast

---

## State Tracking

Keepalive state must include these new fields for delegation:

```json
{
  "current_agent": "codex",
  "last_switch_iteration": 12,
  "switch_count": 2,
  "effectiveness_history": [
    {"iteration": 18, "commits": 1, "tasks": 2, "gate": "pass"},
    {"iteration": 17, "commits": 0, "tasks": 0, "gate": "pending"},
    {"iteration": 16, "commits": 1, "tasks": 1, "gate": "fail"}
  ],
  "delegation_log": [
    {
      "iteration": 18,
      "chosen_agent": "codex",
      "reason": "effective",
      "timestamp": "2026-02-17T10:30:00Z"
    },
    {
      "iteration": 12,
      "chosen_agent": "claude",
      "reason": "codex-stalled",
      "previous_agent": "codex",
      "timestamp": "2026-02-15T14:20:00Z"
    }
  ]
}
```

### State Fields

| Field | Type | Description |
|-------|------|-------------|
| `current_agent` | string | Active agent (codex \| claude \| "") |
| `last_switch_iteration` | number | Iteration when last switch occurred |
| `switch_count` | number | Total number of switches in this PR |
| `effectiveness_history` | array | Last 10 iterations with metrics |
| `delegation_log` | array | Full history of delegation decisions |

---

## Implementation Plan

### Phase 5D-A: Add Effectiveness Tracking (1 week)

**Files to modify:**
- `.github/scripts/keepalive_loop.js`
- `.github/scripts/keepalive_state.js` (if exists)

**Changes:**
1. Extend keepalive state schema with delegation fields
2. After each agent run, record:
   - Commits count (from `changes-made` + commit history)
   - Tasks completed (from `llm-completed-tasks`)
   - Gate status (from PR check runs)
3. Store last 10 iterations in `effectiveness_history`

**Test:**
- Unit tests for effectiveness calculation
- Integration test: run keepalive 10 times, verify history persists

### Phase 5D-B: Implement Decision Engine (1 week)

**New file:**
- `.github/scripts/agent_delegation_policy.js`

**Exports:**
```javascript
/**
 * Determine which agent should run next round
 * @param {Object} options
 * @param {Object} options.state - Current keepalive state
 * @param {Array} options.labels - PR labels
 * @param {Object} options.secrets - Available secrets
 * @param {Object} options.registry - Agent registry
 * @returns {Object} - { agent, reason, shouldSwitch }
 */
function decideNextAgent({ state, labels, secrets, registry }) {
  // Implement decision tree from above
}

/**
 * Check if agent prerequisites are met
 */
function checkPrerequisites({ agent, secrets, rateLimits }) {
  // Validate secrets, rate limits, etc.
}

/**
 * Calculate effectiveness score for current agent
 */
function calculateEffectiveness({ history, lookbackRounds = 3 }) {
  // Analyze commits, tasks, gate status
}

/**
 * Detect stall condition
 */
function detectStall({ history, threshold = 3 }) {
  // Check for N consecutive rounds with no progress
}
```

**Integration:**
- `keepalive_loop.js` calls `decideNextAgent()` in evaluate step
- Output `agent_type` set based on decision
- Record decision in delegation_log

**Test:**
- Unit tests for each decision path (21 test cases covering all rules)
- Mock scenarios:
  - First run → defaults to Codex
  - Effective run → continues current
  - Stalled run → switches
  - Missing secrets → falls back
  - Switch cooldown → prevents thrash

### Phase 5D-C: Wire into Keepalive Loop (3 days)

**File to modify:**
- `.github/workflows/agents-keepalive-loop.yml`

**Changes:**
1. Evaluate step loads delegation policy module
2. Call `decideNextAgent()` instead of simple label check
3. Set `agent_type` output from decision
4. Pass decision reason to summary step for transparency

**Test:**
- End-to-end test with `agent:auto` label
- Verify decision logged in PR comment summary
- Verify switching behavior with mocked stall conditions

### Phase 5D-D: Consumer Template Sync (2 days)

**Files to sync:**
- `templates/consumer-repo/.github/scripts/agent_delegation_policy.js`
- `templates/consumer-repo/.github/scripts/keepalive_loop.js` (updates)
- Update `.github/sync-manifest.yml`

**Validation:**
- Run `scripts/validate_workflow_yaml.py`
- Trigger `maint-68-sync-consumer-repos.yml`
- Merge sync PRs in reference consumer repo (Travel-Plan-Permission)

---

## Observability & Debugging

### Delegation Decision Transparency

Every keepalive summary comment must include:

```markdown
## Agent Selection (auto mode)

**Chosen:** Codex
**Reason:** Effective (2 commits, 3 tasks in last 3 rounds)
**Alternatives considered:** Claude (not selected: current agent effective)

**Effectiveness Metrics:**
- Commits (last 3 rounds): 2
- Tasks completed (last 3 rounds): 3
- Gate status: pass (round 18)
- Stall detection: No (progress detected)

**Switch History:**
- Total switches: 1
- Last switch: Round 12 (Codex → Claude, reason: codex-stalled)
- Cooldown remaining: 0 rounds
```

### Metrics Dashboard

Add to existing metrics dashboards:
- Agent usage breakdown (Codex vs Claude rounds)
- Switch rate (switches per PR)
- Effectiveness before/after switch
- Stall detection accuracy (manual review)

### Debugging

Query delegation log from keepalive state:
```bash
gh run view <RUN_ID> --log | grep "delegation_log" | jq
```

---

## Rollout Strategy

### Phase 1: Workflows Repo Only (1 week)

- Deploy Phase 5D to Workflows repo
- Test with internal PRs labeled `agent:auto`
- Monitor delegation decisions daily
- Tune thresholds based on observations

### Phase 2: Reference Consumer Repo (1 week)

- Sync to Travel-Plan-Permission
- Test with `agent:auto` on sample PRs
- Validate no regressions for `agent:codex` (default behavior)
- Collect feedback from maintainers

### Phase 3: Broad Rollout (1 week)

- Sync to all consumer repos (Template, trip-planner, Manager-Database)
- Announce `agent:auto` availability
- Monitor metrics across all repos
- Document usage patterns

---

## Success Criteria

Phase 5D is complete when:

- ✅ Delegation policy implemented and tested
- ✅ `agent:auto` label triggers intelligent routing
- ✅ Stall detection switches agents appropriately
- ✅ No thrashing observed (max 3 switches per PR)
- ✅ Delegation decisions logged transparently in PR comments
- ✅ Consumer templates synced with delegation policy
- ✅ Metrics dashboard tracks agent effectiveness

**Acceptance Test:**
1. Create PR with `agent:auto` label
2. Initial round → Codex selected (default)
3. Manually cause Codex to stall (make tasks uncompletable)
4. After 3 rounds → Claude selected (stall detected)
5. Claude makes progress → continues with Claude (effective)
6. Verify switch logged in summary with reasoning

---

## Risk Mitigation

### Risk: Policy Selects Wrong Agent

**Mitigation:**
- Manual override always available (remove `agent:auto`, add `agent:codex`)
- Delegation decisions logged transparently
- Cooldown prevents rapid thrashing

### Risk: Both Agents Unavailable

**Mitigation:**
- Fail-safe checks secrets before running
- Clear error message in PR comment
- Does not block PR (manual intervention required)

### Risk: Metrics Misleading (False Stall)

**Mitigation:**
- Require 3+ consecutive rounds for stall detection (not single round)
- Consider multiple signals (commits AND tasks AND gate)
- Manual review of first month's delegation logs to tune thresholds

### Risk: Claude More Expensive Than Expected

**Mitigation:**
- Track API costs in metrics dashboard
- Policy can be configured to prefer Codex (adjust stall threshold)
- `agent:codex` label disables delegation (cost control)

---

## Open Questions

1. **Stall threshold:** Is 3 rounds the right number, or should it be 5?
   - **Resolution:** Start with 3, tune based on data

2. **Switch cooldown:** Is 5 rounds enough to avoid thrashing?
   - **Resolution:** Monitor switch_count metric, increase if thrashing occurs

3. **Effectiveness lookback:** Last 3 rounds or last 5 rounds?
   - **Resolution:** Last 3 (more responsive to recent performance)

4. **Gate weight:** Should gate status be weighted higher than commits/tasks?
   - **Resolution:** No, all signals equal for v1. Revisit after data collection.

---

## References

- [Provider-Agnostic Plan](./provider-agnostic-coding-agents.md)
- [Agent Runner Output Contract](../contracts/agent-runner-output.md)
- [Keepalive Goals and Plumbing](../keepalive/GoalsAndPlumbing.md)
- [Multi-Agent Routing](../keepalive/MULTI_AGENT_ROUTING.md)

---

**Next Steps:** Implement Phase 5D-A (effectiveness tracking) as first PR.
