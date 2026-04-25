# Repo Review Process

This process turns periodic local repo reviews into issue drafts and one human decision packet. It is intentionally approval-gated: the evaluator does not create remote issues.

## Registry

The repo roster lives in `config/repo_review_registry.json`.

Statuses:

- `active`: included in weekly review and issue-draft generation.
- `paused`: tracked, but not a normal weekly issue-generation candidate.
- `ignored`: deliberately out of the current review lane.
- `needs-human`: blocked until a human resolves the recorded ambiguity.

The registry excludes repos named `stranske` and `collab-deliverables`.

## Weekly Run

Run from the Workflows repo:

```bash
python scripts/repo_review_evaluator.py
```

Outputs are written to `docs/reports/repo-review/`:

- `human-decision-packet.md`: the single human review queue.
- `repo-review-summary.json`: machine-readable summary.
- `repos/<owner>__<repo>/state.md`: local state per repo.
- `repos/<owner>__<repo>/issue-drafts.md`: extracted local issue drafts for approval.

The `docs/reports/repo-review/` directory is ephemeral output and is ignored by git.

## Human Decision Point

The human reviews `human-decision-packet.md` and chooses, per repo:

- approve selected drafts for remote issue creation;
- edit drafts before issue creation;
- pause the repo;
- mark the repo `needs-human` with a blocking question;
- ignore the repo for now.

Only approved drafts should flow into the remote issue-intake workflow.

## Evaluation Rules

The evaluator is local-first and conservative:

- `Issues.txt` entries with unchecked checklist items become issue drafts.
- Draft checklist counts are local unchecked boxes from `Issues.txt`; they are not remote GitHub open-issue counts.
- Dirty local changes are surfaced, not reverted or modified.
- Missing local clones are marked `needs human`.
- The packet is a decision queue, not an implementation trigger.

Completion audits should continue to use the issue-completion audit workflow before declaring issue work fully done: review feedback, merge state, verifier outcomes, and non-PASS follow-up disposition all matter.
