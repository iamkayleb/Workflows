# Repo Review Process

This process exists to standardize periodic design-vs-implementation reviews across active repos. Issue generation is an output of the review, not the review itself.

The weekly packet must answer one core question for each active repo:

> What does the repo intend to be, how much of that design is actually implemented, and what gaps block testing or live use?

## Review Order

1. Read the registry decision anchor and the repo design sources.
2. Inspect the implementation areas named by the packet.
3. Compare design commitments to real behavior, tests, integrations, persistence, and workflow handoffs.
4. Use archived review conversations as precedent for the review standard and known project intent.
5. Identify gaps that block testing, live implementation, or product completeness.
6. Draft issues only for verified gaps, with evidence and acceptance gates.
7. Queue one human decision packet before creating remote issues.

## Registry

The repo roster lives in `config/repo_review_registry.json`.

Statuses:

- `active`: included in the scheduled design-vs-implementation review.
- `paused`: tracked, but not normally reviewed until reactivated.
- `ignored`: deliberately out of the current review lane.
- `needs-human`: blocked until a human resolves the recorded ambiguity.

The registry excludes repos named `stranske` and `collab-deliverables`.

Repo-specific review interpretation lives in `config/repo_review_profiles.json`. The evaluator uses these profiles for human-usable progress summaries, readiness summaries, review focus, and known concerns. Generic code-existence statements are not acceptable as the final human packet summary when a profile exists.

Human feedback from the weekly packet lives in `config/repo_review_feedback.json`. This file records per-repo decisions, priority, selected candidate indexes, dropped candidate indexes, and routing rules. It is the source for the approved issue queue consumed by coding-agent opener lanes.

## Standard Dimensions

Every active repo review uses the same dimensions:

- `design_contract`: identify the intended product or workflow from README/docs and the registry decision anchor.
- `implementation_coverage`: distinguish real working behavior from scaffolds, seams, fixtures, or advisory-only outputs.
- `test_and_live_readiness`: determine whether tests or smoke paths prove the user journey required by the design.
- `integration_and_state`: check cross-repo contracts, external providers, persistence, reload behavior, source authority, generated artifacts, and workflow handoffs.
- `issue_generation`: convert verified gaps into issue drafts with evidence, non-goals, tasks, acceptance criteria, and tests that would fail before the fix.

## Weekly Run

Run from the Workflows repo:

```bash
python scripts/repo_review_evaluator.py
```

Outputs are written to `docs/reports/repo-review/`:

- `human-decision-packet.md`: one review queue across active repos.
- `repo-review-summary.json`: machine-readable summary.
- `approved-issue-queue.json`: machine-readable queue of approved, prioritized, agent-formatted issue bodies.
- `approved-issue-queue.md`: human-readable rendering of the approved issue queue, deeper-review items, and dropped candidates.
- `repos/<owner>__<repo>/decision-brief.md`: human-facing progress, readiness, issue-set, and feedback brief.
- `repos/<owner>__<repo>/review-execution.md`: automated evidence gathering and preliminary gap classification.
- `repos/<owner>__<repo>/design-review.md`: standardized review worksheet for that repo.
- `repos/<owner>__<repo>/state.md`: repo state, sources, implementation areas, and local signals.
- `repos/<owner>__<repo>/issue-drafts.md`: existing draft inputs and archive-derived candidate inputs.

The `docs/reports/repo-review/` directory is ephemeral output and is ignored by git.

## Local Signals

Local changes are split by how they affect the review:

- `Issues.txt` is a helper/queue file. Changes there are review inputs, not blockers.
- Generated output such as `docs/reports/` is ephemeral and does not block review.
- Other non-generated local changes are surfaced as review-blocking until they are understood, because they may change the implementation being evaluated.

Local `.gitnexus/` maps are review inputs, not blockers. The evaluator reads only `.gitnexus/meta.json` to report map freshness, indexed commit, and index size. It does not parse the binary local map. For deeper semantic review, especially repos marked `deeper-review`, use the GitNexus MCP query/context tools against the repo design target, review focus, and implementation paths surfaced in the packet. If a natural-language GitNexus query returns no processes, fall back to Cypher community/process listings before concluding the map has no useful signal.

`pending standardized review` means the worksheet has been queued and evidence still needs to be gathered. It does not mean the design-vs-implementation review has already been completed.

`standard review executed; human decision queued` means the automated evidence pass has run and the repo is ready for the single human decision point.

`decision-brief.md` is the human review surface. It summarizes current progress against the design anchor, readiness for testing/live implementation, candidate issue set, and a compact feedback slot for approve/revise/defer/drop/deeper-review decisions.

`review-execution.md` is the automated execution phase. It gathers evidence for each standard dimension and classifies obvious automated gaps such as missing design sources, missing implementation surfaces, missing tests/workflows, or absent smoke/live-readiness markers. Dimensions marked `needs human decision` still require semantic review before issue approval.

## Archive Use

Archived conversations are not just a source of issue text. They are review precedent:

- what design goal was previously stated;
- what implementation shortcuts were rejected;
- what testing/live-readiness gates were expected;
- what follow-up issues were considered valuable.

Archive-derived candidates still require the standardized review before approval. They should not be copied into remote issues without checking current code and docs.

## Human Decision Point

The human reviews `human-decision-packet.md` and each relevant `design-review.md`, then chooses per repo:

- approve selected issue drafts after the review;
- edit drafts before issue creation;
- request another implementation inspection;
- pause the repo;
- mark the repo `needs-human` with a blocking question;
- ignore the repo for now.

Only approved drafts should flow into the remote issue-intake workflow.

Approved drafts flow through `approved-issue-queue.json`. Opener-lane automations should select from that queue by priority, using `high` before `normal` before `low`, while respecting the repo recorded on each item. Closer-lane automations should continue to sweep PRs, review comments, merge readiness, and verifier status across all active repos rather than focusing on a fixed two-repo list.

## Issue Gate

No issue should be approved unless it states:

- the design commitment or readiness goal;
- the current evidence from code, docs, tests, or archives;
- what behavior is missing;
- non-goals that prevent scaffold-only completion claims;
- tasks a coding agent can complete;
- acceptance criteria with a failing test, smoke test, or documented live-verification gate.

Approved issue bodies must follow the required agent issue sections from `templates/consumer-repo/docs/AGENT_ISSUE_FORMAT.md`:

- `## Tasks`
- `## Acceptance Criteria`

The weekly queue also includes the recommended sections:

- `## Why`
- `## Scope`
- `## Non-Goals`
- `## Implementation Notes`

Consumer repo reviews must not generate issues for Workflows maintenance, template sync, or cross-repo lane-management work unless that work directly implements repo-local behavior required by the consumer repo design. Those maintenance tasks belong in `stranske/Workflows`.

Completion audits should still use the issue-completion audit workflow before declaring issue work fully done: review feedback, merge state, verifier outcomes, and non-PASS follow-up disposition all matter.
