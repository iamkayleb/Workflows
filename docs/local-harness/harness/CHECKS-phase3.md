# Phase 3 — wiring Cursor into the work phase

`work.py` replaces `round.py work`. The sequence becomes:

    python round.py prerun --ignore-window
    python work.py
    python round.py postrun <the outcome work.py prints>

Put `work.py` beside `round.py` and `guard.py` in `bukay-ops`.

## Setup: tell it where your clone is

`work.py` cuts worktrees from a local clone of bukay. Your clone is not where
it guesses, so set this once per shell (or permanently in System Properties →
Environment Variables):

    $env:BUKAY_REPO_DIR = "C:\Users\user\Documents\bukay\bukay"   # PowerShell

Optional, and all have sensible defaults:

    $env:BUKAY_WORKTREE_ROOT = "C:\bw"     # keep it short; Windows path limits
    $env:BUKAY_AGENT_TIMEOUT = "2100"      # 35 min, under the 45-min lease
    $env:BUKAY_DRAFT = "1"                 # opener PRs open as drafts

Before the first run, once, in your clone:

    git config core.longpaths true

## 1. Doctor — costs nothing, run it first

    python work.py doctor

It finds git, gh, your clone, guard.py and each agent CLI, then checks the
flags it intends to use against that CLI's own `--help`.

**The Cursor invocation in `work.py` is a guess.** I could not verify it —
Cursor is not installed where I am, and these CLIs change flags often. If
doctor prints `** these flags do not appear in --help`, open `work.py`, find
`ADAPTERS["cursor"]["argv"]`, and correct it from the help output it just
printed. You are looking for the non-interactive / print mode and whatever flag
auto-approves file edits.

Do not skip to step 3 until doctor says **All checks passed**.

## 2. Dry run — still costs nothing

    python round.py reset
    python round.py prerun --ignore-window
    python work.py --dry-run

Expect: the guard's decision, the issue it picked, the branch name, a worktree
created and removed, and the full prompt the agent would receive. Read that
prompt. It is the thing that determines what you get back.

Then close the round out:

    python round.py postrun no_op

## 3. Approve one issue

    gh issue edit 534 --repo iamkayleb/bukay --add-label ready:agent

Wait ten seconds — GitHub's issue list lags writes — then:

    python guard.py triage

Expect #534 under `actionable` and the decision to read `opener`.

## 4. The first real round

    python round.py prerun --ignore-window
    python work.py

This one spends tokens. Watch for:

- `commits: N` near the end. **This is the check that matters.** The old
  pipeline marked tasks done in thirteen seconds with nothing on disk, three
  times. If N is 0, `work.py` opens nothing and tells you to record `no_op` —
  that is correct behaviour, not a failure of the harness.
- `files changed:` — sanity-check the list against the issue's task list.
- A warning about uncommitted changes, meaning the agent edited files but did
  not commit them. They will not reach the pull request.

Then record what it printed:

    python round.py postrun new_issue      # or no_op

## 5. Read the pull request before anything else touches it

Check the diff against the issue's acceptance criteria yourself, this once.
You are calibrating how much you trust the lane, and the only way to do that is
to read the first one carefully.

## What is deliberately absent

The closer lane, the supervisor loop, scheduling and rotation. `work.py`
implements the opener only; if the guard picks `closer` it says so and stops.
