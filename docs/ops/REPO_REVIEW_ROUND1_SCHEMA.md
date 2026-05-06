# Round 1 Findings Schema

This file is the contract for the round-1 reviewer's output. The reviewer (Codex or Claude Code) must write a JSON document conforming to this schema to:

```
<output_dir>/round1/<agent>/<repo_safe>/findings.json
```

where:

- `<output_dir>` is the evaluator's output directory (default `docs/reports/repo-review/`).
- `<agent>` is the reviewing agent's identifier — `codex` or `claude` for production runs; pilot runs may use a different identifier.
- `<repo_safe>` is the repo with `/` replaced by `__`, e.g. `stranske__Manager-Database`.

`scripts/repo_review_round1_schema.py` provides `validate_findings(data)` which returns a list of error strings; an empty list means valid. The evaluator (and the coordinator) reject malformed findings before round 2 starts.

## Top-level object

```json
{
  "agent": "claude|codex|<other-pilot-id>",
  "repo": "owner/repo",
  "design_summary": "Concrete, repo-specific product/workflow description.",
  "implementation_classification": [ ...IMPLEMENTATION_PIECE... ],
  "readiness_summary": "Repo-specific readiness statement naming the exact missing proof.",
  "remote_progress_check": "Reviewed N open issues + M recent merged PRs; <gap> is/isn't already covered.",
  "archive_dedup_check": "Reviewed K archive entries; no overlap with shipped work.",
  "candidates": [ ...CANDIDATE... ],
  "no_new_work_justification": "Required iff candidates is empty AND deeper_review_needed is false.",
  "deeper_review_needed": false,
  "deeper_review_reason": "Required iff deeper_review_needed is true."
}
```

### Field requirements

- **`agent`** (string, required): The reviewing agent's identifier.
- **`repo`** (string, required): Must match the `owner/name` form exactly as listed in `config/repo_review_registry.json`.
- **`design_summary`** (string, required, ≥120 characters): Concrete description of what the repo is intended to be — product, workflow, integration. **Failure rule:** if your design_summary could fit any other repo with the name swapped, you have not finished step 1; this fails the quality gate.
- **`implementation_classification`** (array, required, ≥1 item): Pieces of the design with status + evidence. Schema below.
- **`readiness_summary`** (string, required, ≥120 characters): Names the exact tests/smoke/verifier commands that prove the user journey, OR the specific missing proof. Generic phrases ("ready for normal coding-agent implementation", "review run-time before approving") fail the gate.
- **`remote_progress_check`** (string, required): Cite numbers and at least one specific check. Example: "Reviewed 4 open issues (#908, #909, #910, #927) and 44 recent merged PRs; the proposed RAG chain implementation gap is not covered by any open issue or recent PR." A bare "no overlap" without numbers fails.
- **`archive_dedup_check`** (string, required): Same shape — name how many archive entries were reviewed and which ones are/aren't overlapping with proposed candidates.
- **`candidates`** (array, required): Verified design-vs-implementation gaps. May be empty.
- **`no_new_work_justification`** (string): Required only when `candidates` is empty AND `deeper_review_needed` is false. Must name files and tests that prove no design gap remains. Generic "no gaps detected" fails.
- **`deeper_review_needed`** (boolean, required): True when the reviewer cannot complete the review with available inputs (e.g., dirty branch, missing design sources, GitNexus map stale and code is opaque).
- **`deeper_review_reason`** (string): Required when `deeper_review_needed` is true.

## IMPLEMENTATION_PIECE

```json
{
  "piece": "alert dispatch path",
  "status": "implemented-and-verified | partial | missing | stale-or-conflicting",
  "evidence": ["alerts/dispatch.py:42", "tests/test_alert_dispatch.py"]
}
```

- **`piece`** (string, required): What aspect of the design is being classified.
- **`status`** (enum, required): One of the four values above.
- **`evidence`** (array of strings, required, ≥1 item): Concrete file paths (with line numbers when load-bearing). For `missing`, this should explain *where the absence was verified* — e.g., "api/chat.py:350 references chains.rag_search but `chains/rag_search.py` does not exist in the repo". Generic counts (e.g., "103 test files") are not valid evidence.

## CANDIDATE

```json
{
  "title": "Specific, scoped issue title (≤120 chars)",
  "gap": "What design commitment is unmet.",
  "current_state": "What current code/tests prove today.",
  "required_change": "What must change to close the gap.",
  "design_refs": ["README.md#section", "docs/foo.md"],
  "implementation_refs": ["src/foo/bar.py:42"],
  "test_refs": ["tests/test_foo.py"],
  "acceptance_criteria": [
    "Test that fails before fix and passes after.",
    "PR notes the design source used to define completion."
  ],
  "non_goals": [
    "Do not bundle unrelated cleanup."
  ],
  "tasks": [
    "First concrete task a coding agent can complete.",
    "Second concrete task.",
    "..."
  ],
  "priority": "high|normal|low",
  "confidence": "high|medium|low",
  "body": "OPTIONAL — leave empty/omitted in round 1; the body-writer pass after round-2 convergence composes the issue body from the structured fields above."
}
```

### Candidate requirements

- **`title`** (string, required, ≤120 chars): Specific gap title. Not a slogan.
- **`gap`**, **`current_state`**, **`required_change`** (strings, required, each ≥40 chars): Substantive sentences. "Implementation is incomplete" / "code does not match design" fail the gate.
- **`design_refs`** (array, required, ≥1 item): File paths the gap is anchored in.
- **`implementation_refs`** (array, required, ≥1 item): Specific files (with line numbers when load-bearing) that prove the current state.
- **`test_refs`** (array, required, ≥1 item): Specific tests, smoke checks, or verifier paths — either the failing test that would prove the fix, or the test path that should be added.
- **`acceptance_criteria`** (array, required, ≥2 items): Verifiable conditions. At least one must reference a test, smoke check, verifier run, or live-readiness gate.
- **`non_goals`** (array, required, ≥1 item): Bounds the scope.
- **`tasks`** (array, required, ≥2 items): Concrete steps a coding agent can complete.
- **`priority`** (enum, required): `high`, `normal`, or `low`.
- **`confidence`** (enum, required): `high`, `medium`, or `low`.
- **`body`** (string, optional, but **leave empty in round 1**): The body-writer pass that runs after round-2 convergence composes AGENT_ISSUE_FORMAT.md-compliant bodies from the structured fields above. Round-1 reviewers should invest their effort in `design_refs`, `implementation_refs`, `test_refs`, `tasks`, `non_goals`, and `acceptance_criteria` instead — those are the inputs the body-writer reads. If a reviewer does include a body it is treated as advisory only; the body-writer pass overwrites it.

## Out-of-scope (do not include in `candidates`)

- **Issues.txt** entries from the repo root: ignore.
- **Workflow-sync, AGENTS.md / CLAUDE.md sync, template-sync, lane-management** maintenance: route to `stranske/Workflows`. Only raise these as candidates in the consumer repo if the work directly implements behavior required by THIS repo's design.
- **Archive-only candidates** (only basis is an old session transcript): drop them.
- **Already-covered work**: if an open GitHub issue or recently-merged PR addresses the gap, do not re-raise it. Note the dedup in `remote_progress_check`.

## Versioning

This schema is `v1`. Future evolutions will add `schema_version` to the top-level object. The validator currently rejects unknown top-level keys with a warning, not an error, so additional fields can be experimentally added before formal versioning.
