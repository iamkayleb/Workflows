# Round 2 Schema

Two artifacts have schemas in round 2:

1. **Per-agent per-turn output** (one file per agent per turn).
2. **Converged set** (one file per repo, written by the runner after all turns complete).

Both are validated by `scripts/repo_review_round2_schema.py`.

---

## Per-turn output

Path: `<output_dir>/round2/<repo_safe>/turn-<N>/<agent>.json`

```json
{
  "agent": "codex|claude",
  "repo": "owner/repo",
  "turn": 1,
  "marks": [
    {
      "source_agent": "codex|claude",
      "candidate_index": 1,
      "mark": "agree-keep|agree-merge|disagree-drop|disagree-revise|abstain",
      "reason": "Concrete reason citing files / tests / open issues / PRs.",
      "merge_proposal": null,
      "revision_proposal": null
    }
  ],
  "own_candidates_revisions": [
    {
      "candidate_index": 1,
      "change": "What you're changing in your own round-1 candidate.",
      "reason": "Why."
    }
  ],
  "meta_candidate_proposal": {
    "proposed": true,
    "pattern": "Concise systemic-pattern description.",
    "title": "Audit and remediate <pattern> across the codebase",
    "rationale": "Why ≥2 instances justify a systemic audit.",
    "supporting_candidate_indexes": [
      {"agent": "codex", "candidate_index": 1},
      {"agent": "claude", "candidate_index": 1}
    ],
    "scope": "audit",
    "tasks": ["..."],
    "acceptance_criteria": ["..."],
    "non_goals": ["..."],
    "priority": "normal|low",
    "confidence": "medium|low|high"
  }
}
```

### Per-turn requirements

- **`agent`**: `codex` or `claude` (or `pilot-*` for pre-cron pilots).
- **`repo`**: must match the round-1 findings.
- **`turn`**: integer 1–3.
- **`marks`** (array, required): one mark per round-1 candidate from BOTH agents. Length must equal `total_round1_candidates_across_both_agents`.
- **Each mark** must have `source_agent`, `candidate_index`, `mark` (enum), and a non-empty `reason`. `agree-merge` requires `merge_proposal`; `disagree-revise` requires `revision_proposal`. `disagree-drop` reasons must cite a file ref, test ref, open issue, or PR.
- **`own_candidates_revisions`** (array, may be empty): revisions to your own round-1 candidates triggered by reading the other agent's findings.
- **`meta_candidate_proposal`** (object, required): set `proposed: false` if no pattern. If `proposed: true`, all fields below are required.

### Meta-candidate requirements (when `proposed: true`)

- **`scope`**: must be exactly `"audit"`. The validator rejects other values.
- **`supporting_candidate_indexes`**: array of ≥2 entries, each `{agent, candidate_index}` referencing a real round-1 candidate.
- **`tasks`** (array, ≥3 items): must include enumeration, classification, and per-instance follow-up filing.
- **`acceptance_criteria`** (array, ≥3 items): must reference an audit-report artifact path AND a per-instance follow-up requirement. The validator looks for tokens like `report`, `artifact`, `follow-up`, `issue`.
- **`non_goals`** (array, ≥1): must include language equivalent to "do not bundle per-instance fixes into a single PR". The validator looks for tokens like `bundle`, `single PR`, or `not … per-instance`.
- **`confidence`**: `medium` is the default; `high` requires ≥4 supporting candidates with concrete file refs (validator currently warns only — rule may tighten).
- **`priority`**: `normal` or `low`. The meta-candidate doesn't preempt urgent per-instance fixes.

---

## Converged set

Path: `<output_dir>/round2/<repo_safe>/converged.json`

Written by the runner after all turns complete. Schema:

```json
{
  "schema_version": "v1",
  "repo": "owner/repo",
  "turns_completed": 1,
  "round1_sources": [
    {"agent": "codex", "path": "<absolute>", "candidate_count": 3},
    {"agent": "claude", "path": "<absolute>", "candidate_count": 1}
  ],
  "converged_candidates": [
    {
      "title": "...",
      "gap": "...",
      "current_state": "...",
      "required_change": "...",
      "design_refs": [...], "implementation_refs": [...], "test_refs": [...],
      "acceptance_criteria": [...], "non_goals": [...], "tasks": [...],
      "priority": "high|normal|low",
      "confidence": "high|medium|low",
      "scope": "fix|audit",
      "origin": {
        "source_agent": "codex|claude|merged",
        "round1_index": 1,
        "merged_from": null
      },
      "body": "Optional agent-ready body."
    }
  ],
  "deadlocked_candidates": [
    {
      "title": "...",
      "source_agent": "codex|claude",
      "round1_index": 1,
      "marks_history": [
        {"agent": "codex", "turn": 1, "mark": "agree-keep", "reason": "..."},
        {"agent": "claude", "turn": 1, "mark": "disagree-drop", "reason": "..."}
      ]
    }
  ],
  "dropped_candidates": [
    {
      "title": "...",
      "source_agent": "codex|claude",
      "round1_index": 1,
      "drop_reason": "Both agents agreed: <reason>."
    }
  ],
  "meta_candidate": null,
  "negotiation_log": [
    "<output_dir>/round2/<repo_safe>/turn-1/codex.json",
    "<output_dir>/round2/<repo_safe>/turn-1/claude.json"
  ]
}
```

### Converged-set requirements

- **`converged_candidates`** uses the round-1 candidate schema (with one extra `origin` field) PLUS the new `scope` enum. `scope: fix` is the default; `scope: audit` is reserved for meta-candidates.
- **`deadlocked_candidates`** carry both agents' positions inline. Surfaced to the human packet under "Deadlocked candidates", never silently dropped.
- **`dropped_candidates`** preserves a record of explicit drops so the human packet can show what BOTH agents agreed shouldn't ship and why.
- **`meta_candidate`** is `null` if neither agent proposed a pattern OR if the proposal was deadlocked. When set, it carries the same shape as a converged candidate with `scope: "audit"` and `origin.source_agent: "merged"`.

The evaluator's `load_round2_converged(output_dir, repo)` returns this object; the packet rendering treats `converged_candidates + meta_candidate` as the candidate set, and surfaces `deadlocked_candidates` in a separate section.
