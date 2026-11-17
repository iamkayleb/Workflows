# Phase 4 — the supervisor

One process, started at logon, that runs rounds while the machine is awake.
`supervisor.py` goes in `bukay-ops` beside `round.py`, `guard.py` and `work.py`.

## Before you start

In `round.py`, set the rotation — Cursor measured 10/10 clean, so it leads:

    ROTATION = ("cursor", "codex", "claude")

Then `python round.py reset` so the sentinel starts on Cursor.

## Test it by hand first

    python supervisor.py --once

One tick, then exit. Run it a few times and watch the agent rotate. If the
window is closed it will log `idle — refused: outside the evening window`,
which is correct, not a failure. To exercise a real tick during the day,
temporarily widen `WINDOW_START_HOUR` in `round.py`.

Then the loop, briefly:

    python supervisor.py --tick 60

Ctrl-C stops it cleanly after the current tick. Check `supervisor.log`.

## Install it in Task Scheduler

Task Scheduler has exactly one job: start this at logon and restart it if it
dies. It is not the orchestration layer — the supervisor is.

Open Task Scheduler, Create Task (not Basic Task):

- **General** — name `bukay supervisor`. Run only when user is logged on.
  Do NOT tick "Run with highest privileges"; it needs no elevation.
- **Triggers** — New, At log on, your account.
- **Actions** — New, Start a program:
  - Program: `C:\Windows\py.exe` (or the full path from `where python`)
  - Arguments: `supervisor.py`
  - Start in: `C:\Users\user\Documents\bukay-ops`
  The "Start in" field matters: without it the script cannot find its siblings.
- **Conditions** — untick "Start the task only if the computer is on AC power"
  if you want it on battery. Leave the wake timers alone; the evening window
  means the machine is awake anyway.
- **Settings** — tick "If the task fails, restart every 1 minute", up to 3
  times. Untick "Stop the task if it runs longer than", since this runs all
  evening by design.

Log off and back on to confirm it starts.

## Watching it

    python supervisor.py --status

Per-agent round counts, consecutive failures, and the tail of the log. The log
itself is `supervisor.log`, rotating once at 2 MB.

Three consecutive failures from one agent prints a WARNING naming the probe
command to run. It does not disable the agent: the rotation already limits a
broken one to a third of ticks, and a kill switch that nobody watches is worse
than a warning that someone reads.

## What it deliberately does not do

- **No retries.** A failed round is recorded and the rotation moves on. Retry
  logic is where unattended systems grow their worst behaviour.
- **No cleverness about a crashed work phase.** If `work.py` dies without
  printing an outcome, the claim is left alone so the lease expires and the
  next prerun recovers it — the path already proven in Phase 1.
- **No second instance.** A lock file stops Task Scheduler starting a second
  supervisor over a running one. A lock older than six hours is treated as
  stale and taken over.

## Settings

    BUKAY_TICK_SECONDS=1200     seconds between ticks (default 20 min)
    BUKAY_LOG_MAX=2097152       log rotation threshold

Set these in the Task Scheduler action's environment if you change them, not
just in your shell — the scheduled task does not inherit your Git Bash exports.
That also applies to BUKAY_REPO_DIR, which the supervisor needs.
