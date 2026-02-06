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

## Conclusion

**agent:codex label has TWO distinct successful patterns**:
1. ✅ **PR-based** (original design) - Works excellently for manual PR creation + keepalive
2. ⚠️ **Issue-based** (auto-pilot) - Works most of the time, but has timing vulnerability

**Current problem**: Belt dispatcher PR creation is unreliable (issue #1212 took 6 hours).

**Root cause**: Unknown - no obvious code changes between Feb 5 success and Feb 6 failure.

**Next steps**:
1. Investigate belt dispatcher/worker PR creation logic
2. Add observability for PR creation success/failure
3. Consider architectural decoupling of orchestration from label timing

