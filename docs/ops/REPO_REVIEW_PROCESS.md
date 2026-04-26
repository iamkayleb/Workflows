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
- `repos/<owner>__<repo>/design-review.md`: standardized review worksheet for that repo.
- `repos/<owner>__<repo>/state.md`: repo state, sources, implementation areas, and local signals.
- `repos/<owner>__<repo>/issue-drafts.md`: existing draft inputs and archive-derived candidate inputs.

The `docs/reports/repo-review/` directory is ephemeral output and is ignored by git.

## Local Signals

Local changes are split by how they affect the review:

- `Issues.txt` is a helper/queue file. Changes there are review inputs, not blockers.
- Generated output such as `docs/reports/` is ephemeral and does not block review.
- Other non-generated local changes are surfaced as review-blocking until they are understood, because they may change the implementation being evaluated.

`pending standardized review` means the worksheet has been queued and evidence still needs to be gathered. It does not mean the design-vs-implementation review has already been completed.

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

## Issue Gate

No issue should be approved unless it states:

- the design commitment or readiness goal;
- the current evidence from code, docs, tests, or archives;
- what behavior is missing;
- non-goals that prevent scaffold-only completion claims;
- tasks a coding agent can complete;
- acceptance criteria with a failing test, smoke test, or documented live-verification gate.

Completion audits should still use the issue-completion audit workflow before declaring issue work fully done: review feedback, merge state, verifier outcomes, and non-PASS follow-up disposition all matter.
