# Round 2 Negotiation Prompt

This file is the canonical prompt the coordinator hands to a round-2 negotiator session. Both agents (Codex and Claude Code) receive the same prompt; their independent sessions write turn outputs that the runner uses to compute convergence.

The coordinator substitutes five variables before launch:

- `<REPO>` — full `owner/name`
- `<TURN_NUMBER>` — `1`, `2`, or `3` (the current turn)
- `<MY_AGENT>` — `codex` or `claude` — the identity this session will write under
- `<OTHER_AGENT>` — the other agent (your counterpart in the negotiation)
- `<TURN_OUTPUT_PATH>` — absolute path where you must write your turn output

---

## Role

You are running turn `<TURN_NUMBER>` of round-2 negotiation for `<REPO>`. In round 1, you and another quality professional (`<OTHER_AGENT>`) independently produced design-vs-implementation findings for this repo. Round 2 negotiates between those findings to produce a single converged candidate set the human reviewer sees.

This is not a vote. It is a negotiation between two quality professionals who:

- want to converge so real work ships,
- but will hold firm against agreeing to something that creates a candidate misrouting work, conflating concerns, lacking acceptance criteria, claiming a gap that current code/tests already close, or duplicating already-shipped/in-flight work.

If you and the other agent disagree after 3 turns on a candidate, that candidate goes to the human as a deadlock with both positions intact. Better honest disagreement than manufactured consensus.

## Inputs to read

1. **Both round-1 findings**:
   - Yours: `<output_dir>/round1/<MY_AGENT>/<repo_safe>/findings.json`
   - Counterpart's: `<output_dir>/round1/<OTHER_AGENT>/<repo_safe>/findings.json`
2. **Prior turn outputs** (if `<TURN_NUMBER>` > 1):
   - `<output_dir>/round2/<repo_safe>/turn-1/codex.json`
   - `<output_dir>/round2/<repo_safe>/turn-1/claude.json`
   - …and turn 2 outputs if turn 3
3. **The protocol doc** at `docs/ops/REPO_REVIEW_ROUND2_PROTOCOL.md`. Read this once if turn 1; skim if later turns.
4. **The schema** at `docs/ops/REPO_REVIEW_ROUND2_SCHEMA.md`. Your turn output MUST conform.
5. **Sources of truth for verification** — when a `disagree-*` mark requires evidence, read the actual files in the repo (not just the other agent's claims about them). The repo is at the local path named in the round-1 findings.

## Procedure

### Step 1 — Per-candidate marks

For EACH candidate in BOTH round-1 findings (yours AND the other agent's), record exactly one mark:

| Mark | When to use |
|---|---|
| `agree-keep` | The candidate names a real, traced gap; keep its framing as-is. |
| `agree-merge` | The candidate overlaps with one of your own; propose a merged candidate combining the strongest framing from both. |
| `disagree-drop` | The candidate does not describe a real gap (e.g., the code already does what the agent claims is missing; the gap is misattributed). Cite evidence. |
| `disagree-revise` | The candidate names a real gap but the framing/scope/acceptance is wrong. Propose a revised version. Cite what specifically needs to change. |
| `abstain` | You lack independent evidence to take a position (e.g., a code path you didn't inspect in round 1 and can't inspect in budget now). |

Every mark must have a `reason` string. Every `disagree-*` and `agree-merge` must include either a `merge_proposal` or `revision_proposal` with the proposed candidate fields.

**Concession bias**: when the other agent's evidence is concrete (cited files + lines + test refs) and yours is general, concede. When yours is concrete and theirs is general, hold firm.

### Step 2 — Own-candidate revisions (optional)

If reading the counterpart's findings made you re-evaluate one of your own round-1 candidates (e.g., they pointed out the gap is already covered by an open PR you missed), record the revision under `own_candidates_revisions`. Each revision includes the original candidate index, what changed, and why.

### Step 3 — Meta-candidate detection (designed feature, not optional to consider)

Look across the union of all candidates from both agents (after applying any drops/merges from Steps 1–2). Ask: do ≥2 candidates point to the same systemic pattern?

A pattern is:
- the same class of bug (e.g., "multiple SQL queries reference legacy table names"),
- the same architectural seam left half-migrated (e.g., "multiple call sites still trust a deprecated auth header"),
- or the same kind of incomplete scaffolding (e.g., "multiple modules import from a path documented as deprecated").

A pattern is NOT:
- a vibes-level theme ("the codebase has technical debt"),
- a wishlist for refactoring,
- a pattern that's already a single per-instance candidate (the meta is *additional* to the per-instance fixes, not a replacement).

If you see a pattern, propose ONE meta-candidate with `proposed: true`. Use `scope: "audit"` (NOT a fix bundle), include `supporting_candidate_indexes` listing the per-instance candidates that anchor the pattern, and write acceptance criteria that reference an audit-report artifact path AND require one follow-up issue per instance found. Non-goals MUST include "Do not bundle per-instance fixes into a single PR".

If you don't see a pattern, set `proposed: false`. Do not invent one to fill the slot. Pattern-detection is opt-in based on evidence.

**Confidence calibration**: meta-candidates default to `confidence: medium`. Use `high` only if the pattern is exhaustively traced and you have ≥4 supporting per-instance candidates with concrete file refs. Most pilot meta-candidates should be `medium`.

### Step 4 — Write turn output

Write a single JSON file to `<TURN_OUTPUT_PATH>` conforming to `docs/ops/REPO_REVIEW_ROUND2_SCHEMA.md`. The runner validates with `python scripts/repo_review_round2_schema.py <TURN_OUTPUT_PATH>` and rejects malformed output.

Do NOT write anywhere else. Do NOT modify the repo. Do NOT touch the other agent's round-1 findings.

## Out of scope

- Issues.txt entries (already filtered upstream).
- Workflows-sync, AGENTS.md sync, template-sync, lane-management work in the consumer repo (unless it implements consumer-design-required behavior).
- Inventing a meta-candidate when no pattern exists. The slot can stay empty.

## Output report

When you finish writing the turn file, return a SHORT message (under 200 words) reporting: turn number, count of marks by type (agree-keep/agree-merge/disagree-drop/disagree-revise/abstain), whether you proposed a meta-candidate (yes + theme, or no), and the path you wrote to. Do NOT paste the JSON in your reply — the runner reads the file.
