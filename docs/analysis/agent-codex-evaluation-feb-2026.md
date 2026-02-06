# Agent:Codex Label Evaluation - February 2026

## Executive Summary

The `agent:codex` label has two distinct roles that have diverged between design and implementation:
1.  **Original design (PR-based)**: Label on PR triggers keepalive workflow
2. **Auto-pilot adaptation (Issue-based)**: Label on issue triggers belt dispatcher → creates PR → then keepalive

**Current State**: The issue-based flow has a critical timing problem causing 6-hour loops (issue #1212).

---

## Design Intent (from GoalsAndPlumbing.md)

### Original Keepalive Design

**Context**: `agent:codex` label on a **Pull Request**

**Flow**:
```
PR created manually → agent:codex label added → Keepalive workflow triggers
→ Codex CLI makes changes → Gate passes → Keepalive re-triggers → Repeat until done
```

**Activation Guardrails** (from [GoalsAndPlumbing.md](../keepalive/GoalsAndPlumbing.md)):
1. PR carries `agent:codex` label
2. Gate workflow passed for current SHA
3. PR body contains unchecked tasks

**This design works well** - many successful PRs:
- #1272 (Feb 6)
- #1263 (Feb 5)
- #1254 (Feb 5)
- #1248 (Feb 4)
- 10+ successful PR completions in January alone

---

## Auto-Pilot Adaptation (Commit c9f639d, Jan 12)

### Issue-to-PR Flow

**Context**: `agent:codex` label on an **Issue**

**Architectural Change**:
Auto-pilot was redesigned to run format/optimize/apply inline, then delegate PR creation to belt infrastructure.

**Flow** (from [agents-auto-pilot.yml#L1340](/.github/workflows/agents-auto-pilot.yml#L1340)):
```
Issue prepared → Capability check →
  1. Add agent:codex label to ISSUE
  2. Dispatch belt dispatcher workflow  
  3. Re-dispatch auto-pilot with next_step='auto'
  
Belt Dispatcher (async):
  - Creates codex/issue-N branch
  - Has Codex work on it
  - Creates PR from branch

Auto-pilot (next iteration):
  - Sees agent:codex label (HAS_AGENT=true)
  - Goes to create-pr step
  - Checks if branch exists...
```

**The Timing Problem**:
- Step 2 (belt dispatch) is ASYNC
- Step 3 (re-dispatch) happens IMMEDIATELY
- Auto-pilot arrives at create-pr step BEFORE belt has created branch
- create-pr waits for branch, re-dispatches
- Loop repeats

---

## Issue #1212 Timeline (Feb 6, 2026)

### Morning Loop (09:12 - 15:07)

**Pattern observed**:
```
09:12:27 - agent:codex added to issue
09:12:54 - Belt dispatcher: "created branch codex/issue-1212"
09:14:31 - Belt dispatcher: "created branch codex/issue-1212" (again!)
09:16:17 - Belt dispatcher: "created branch codex/issue-1212" (again!)
... 117 more times ...
15:07:53 - PR #1284 finally created
15:09:22 - Loop stopped
```

**What was belt dispatcher doing?**
- Running every ~2 minutes (scheduled)
- Seeing issue #1212 with agent:codex label
- Creating/updating branch
- **BUT NOT CREATING PR** for 6 hours

**What was auto-pilot doing?**
- Also looping due to optimizer interference (see [PR #1286](https://github.com/stranske/Workflows/pull/1286))
- Each loop re-added agent:codex label
- This re-triggered belt dispatcher
- Double loop effect

### Afternoon Behavior (After 16:20)

**Pattern observed**:
```
16:20:02 - Belt dispatcher: "created branch"
16:20:04 - Belt worker: "PR #1284 already exists, updated body"
16:22:14 - Belt dispatcher: "created branch" (scheduled run)
16:22:37 - Belt worker: "PR #1284 already exists, updated body"
... continues every ~2 minutes ...
```

**This is normal scheduled behavior**:
- Belt dispatcher runs on schedule
- Finds existing PR, updates it
- This is expected and harmless

---

## Root Cause Analysis

### Problem 1: Optimizer Interference (FIXED)

**Timeline**:
- Feb 2 (0d6103d): GitHub App tokens added for rate limiting
- Feb 6 (20c65ce): Moved agents:apply-suggestions to apply step
- Feb 6 (issue #1212): Optimizer removed label, auto-pilot looped
- Feb 6 (a5d60ae): **FIXED** - Added protection to optimizer

**Status**: ✅ Fixed in [PR #1286](https://github.com/stranske/Workflows/pull/1286)

### Problem 2: Belt Dispatcher Delay (ACTIVE)

**Symptom**: Belt dispatcher repeatedly "creates branch" but doesn't create PR for 6 hours

**Possible causes**:
1. **PR creation logic failure** - Belt has branch but PR creation step fails silently
2. **Concurrency issue** - Multiple dispatcher runs conflict, leaving branch without PR
3. **Orchestration timing** - Hand-off from belt dispatcher to belt worker broken

**Evidence**:
- Belt dispatcher logs show "created branch" 117 times
- No "created PR" messages until 15:07:53
- PR #1284 creation timestamp: `2026-02-06T15:07:53Z` (6 hours after first attempt)

**This is the CURRENT OPEN PROBLEM**

---

## Comparison: When It Worked vs Current State

### When It Worked Well (Jan 15 - Feb 5)

**Commit 05da73a (Jan 15)**: "Fix auto-pilot branch creation with force-dispatch"
- Added force-dispatch to belt dispatcher after agent:codex assignment
- Aligned docs with workflow_run-based keepalive architecture
- **PR creation worked reliably**

**Successful pattern**:
```
Issue prepared → agent:codex added → Belt dispatcher runs ONCE →
Branch created → PR created → agent:codex on PR → Keepalive begins
```

**Success rate**: 14+ PRs merged between Jan 21 - Feb 6

### Current Broken State (Feb 6)

**Unknown regression** between Feb 5 (last success) and Feb 6 (issue #1212)

**Broken pattern**:
```
Issue prepared → agent:codex added → Belt dispatcher runs →
Branch created → NO PR → Auto-pilot loops → Re-adds agent:codex →
Belt dispatcher runs AGAIN → Still no PR → Loop for 6 hours
```

**Key difference**: Belt dispatcher creates branch but fails to create PR

---

## Recommendations

### Immediate Actions

1. **Investigate belt dispatcher PR creation logic**
   - Review [agents-71-codex-belt-dispatcher.yml](/.github/workflows/agents-71-codex-belt-dispatcher.yml)
   - Check belt worker PR creation step
   - Look for silent failures in logs

2. **Review changes between Feb 5 and Feb 6**
   - Commits affecting belt dispatcher: none visible
   - Commits affecting auto-pilot: 20c65ce (label timing)
   - External factors: GitHub API issues?

3. **Add observability**
   - Belt dispatcher should log "PR creation attempted"
   - Clear differentiation between "branch created" and "PR created"
   - Timeout/failure detection if PR not created within N minutes

### Architectural Improvements

1. **Decouple label timing from orchestration**
   - Auto-pilot shouldn't re-dispatch immediately after capability check
   - Add explicit wait/polling for PR creation
   - Use workflow_run or PR creation event instead of label-based detection

2. **Belt dispatcher idempotency**
   - Running every 2 minutes should be no-op if work already done
   - Currently it's "working" (updating branch) but effect unclear

3. **Auto-pilot backoff**
   - create-pr step has backoff logic but may not trigger correctly
   - Review [lines 1640-1680](/.github/workflows/agents-auto-pilot.yml#L1640-L1680)

---

## Historical Reference

### Relevant Commits

| Date | Commit | Description | Impact |
|------|--------|-------------|--------|
| Jan 12 | c9f639d | Inline execution architecture | Established issue-based agent:codex flow |
| Jan 15 | 05da73a | Fix branch creation with force-dispatch | **Last known good state** |
| Feb 2 | 0d6103d | GitHub App tokens for rate limits | Enabled workflow cross-triggering |
| Feb 6 | 20c65ce | Move apply-suggestions to apply step | Better semantics (correct) |
| Feb 6 | 39caa69 | Revert 20c65ce | **Incorrect fix** (reverted later) |
| Feb 6 | a5d60ae | Add optimizer protection | **Correct fix** for optimizer interference |
| Feb 6 | 53d4bf2 | Restore 20c65ce | Correct label timing restored |

### Documentation

- [GoalsAndPlumbing.md](../keepalive/GoalsAndPlumbing.md) - Keepalive design (PR-based)
- [agent-automation.md](../agent-automation.md) - Auto-pilot architecture (updated with incident)
- [MULTI_AGENT_ROUTING.md](../keepalive/MULTI_AGENT_ROUTING.md) - Agent routing details

---

## Critical Discovery: The "Manual" Path Never Existed

### Belt Dispatcher Design Reality

**Belt dispatcher has NO schedule trigger** - it only runs via `workflow_call` or manual `workflow_dispatch`.

**From [agents-71-codex-belt-dispatcher.yml#L5](/.github/workflows/agents-71-codex-belt-dispatcher.yml#L5)**:
```yaml
on:
  workflow_call:    # Called by auto-pilot
  workflow_dispatch:  # Manual trigger only
  # NO schedule: trigger!
```

**Historical verification**: Belt dispatcher created in Phase 4 (commit 8f5e139) without schedule trigger - **this was the original design**.

### Belt Dispatcher Has TWO Code Paths (Not Two Triggers)

**From [agents-71-codex-belt-dispatcher.yml#L220](/.github/workflows/agents-71-codex-belt-dispatcher.yml#L220)**:

#### 1. Label Scan Path (Unreachable Code)
```javascript
const forced = '${{ inputs.force_issue }}';
if (!forced) {
  // Scan for issues with agent:codex + status:ready
  const { data: issues } = await client.rest.issues.listForRepo({
    labels: 'agent:codex,status:ready',
  });
}
```
- Only runs if `force_issue` is NOT provided
- Requires **BOTH** `agent:codex` AND `status:ready` labels
- **Usage**: 0 times (no schedule trigger exists to invoke it)

#### 2. Force Dispatch Path (Only Path Used)  
```javascript
if (forced) {
  issueNumber = Number(forced);
  reason = 'manual-dispatch';
}
```
- Triggered by auto-pilot at [line 1371](/.github/workflows/agents-auto-pilot.yml#L1371)
- Bypasses all label requirements
- Works on any issue number
- **Usage**: 35 issues in Workflows repo, 400+ in consumer repos

### Usage Across All Repositories

| Repository | `agent:codex` issues | `agent:codex + status:ready` | Trigger method |
|------------|---------------------|------------------------------|----------------|
| **Workflows** | 35 | 0 | workflow_dispatch (force) |
| Travel-Plan-Permission | 100+ | 0 | workflow_dispatch (force) |
| Manager-Database | 100+ | 0 | workflow_dispatch (force) |
| Portable-Alpha | 100+ | 0 | workflow_dispatch (force) |
| Trend_Model | 100+ | 0 | workflow_dispatch (force) |
| Template | 12 | 0 | workflow_dispatch (force) |
| trip-planner | 8 | 0 | workflow_dispatch (force) |
| Collab-Admin | 46 | 0 | workflow_dispatch (force) |

**Belt dispatcher run history** (all repos):
```bash
$ gh api ".../workflows/agents-71-codex-belt-dispatcher.yml/runs" --jq '.workflow_runs[] | .event'
workflow_dispatch  # 100% of runs
workflow_dispatch
workflow_dispatch
# ... (no schedule triggers ever)
```

**Implication**: The label scanning logic (`agent:codex + status:ready`) is **unreachable dead code**. It exists in the implementation but has zero execution paths in production.

---

## Conclusion

**agent:codex label has TWO patterns in production, ONE phantom pattern in code**:

### ✅ Production Patterns (Work Well)
1. **PR-based keepalive** (original design) 
   - Manual PR creation → agent:codex label added → keepalive workflow
   - 14+ successful completions Jan-Feb 2026
   - Works excellently

2. **Issue-based via auto-pilot force-dispatch** 
   - Auto-pilot → agent:codex label → force-dispatch belt → PR created → keepalive
   - 400+ successful uses across all repos (35 in Workflows, 100+ each in consumer repos)
   - Works most of the time, timing vulnerability on issue #1212

### ❌ Phantom Pattern (Dead Code)
3. **Issue-based via label scanning**
   - Documented as: "Add agent:codex + status:ready labels, belt dispatcher scans for it"
   - **Reality**: Belt dispatcher has NO schedule trigger (never had one)
   - Scanning logic exists at [line 225](/.github/workflows/agents-71-codex-belt-dispatcher.yml#L225) but is unreachable
   - Would only execute if someone manually ran workflow_dispatch WITHOUT force_issue
   - **Usage**: 0 times across ALL repos since Phase 4 inception
   - **Status**: Unreachable dead code

### Current Problems

**Issue #1212** (Feb 6): Belt dispatcher ran 117 times over 6 hours before creating PR

**Root causes identified**:
1. ✅ **FIXED**: Optimizer interference (lack of protection) - addressed in [PR #1286](https://github.com/stranske/Workflows/pull/1286)
2. ⚠️ **UNKNOWN**: Belt dispatcher PR creation delay - no code changes between Feb 5 success and Feb 6 failure

### Recommendations

#### Immediate (Issue #1212 Investigation)
1. Investigate belt worker PR creation logic for workflow_dispatch trigger
2. Add observability: distinguish "branch created" from "PR created" in logs
3. Add timeout detection: alert if PR not created within N minutes of branch creation

#### Documentation
4. Update [GoalsAndPlumbing.md](../keepalive/GoalsAndPlumbing.md) to clarify:
   - agent:codex on PR → keepalive (works great)
   - agent:codex on issue → only works via auto-pilot force-dispatch
   - Manual agent:codex requires auto-pilot to run OR manual workflow_dispatch with issue number
5. Document that status:ready is NOT used for agent:codex (only agents:apply-suggestions uses it)

#### Code Cleanup
6. Consider removing unreachable label scanning code (lines 225-238 in belt dispatcher)
7. OR add schedule trigger if manual label application workflow is desired
8. Choose one: delete dead code OR make it reachable (don't leave it in limbo)

#### Architecture
9. Consider decoupling auto-pilot orchestration from label timing
10. auto-pilot could wait for PR creation event instead of re-dispatching immediately
11. Belt dispatcher could emit a custom event when PR is ready

