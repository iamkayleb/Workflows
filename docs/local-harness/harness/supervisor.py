#!/usr/bin/env python3
"""Phase 4: the supervisor. One process, started at logon, that runs rounds.

    python supervisor.py              run the loop
    python supervisor.py --once       one tick, then exit (for testing)
    python supervisor.py --status     what happened recently, then exit

Why one loop rather than a dozen scheduled tasks
------------------------------------------------
The machine this runs on sleeps overnight, so wall-clock scheduling is fiction:
a task set for 02:00 fires into a closed lid or not at all. A single process
started at logon simply works whenever the machine is awake, which is the only
thing that was ever true. Task Scheduler's entire job is to start this at logon
and restart it if it dies.

Each tick is the same three steps you have been running by hand:

    round.py prerun   -> recovers a stale round, checks window/ceiling/cap,
                         claims the lane. Exit 1 means "nothing to do", which
                         is not an error.
    work.py           -> picks the approved issue, runs the agent, commits what
                         it produced, opens a pull request. Prints the outcome.
    round.py postrun  -> records that outcome and hands the baton on.

Nothing clever happens when a round fails. It is recorded, the rotation moves
on, and the next tick decides afresh. Retry logic is where unattended systems
grow their worst behaviour, and the rotation already limits a broken agent to
one tick in three.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROUND = HERE / "round.py"
WORK = HERE / "work.py"
LOG = HERE / "supervisor.log"
HEALTH = HERE / "health.json"
LOCK = HERE / "supervisor.lock"

TICK_SECONDS = int(os.environ.get("BUKAY_TICK_SECONDS", "1200"))      # 20 min
LOG_MAX_BYTES = int(os.environ.get("BUKAY_LOG_MAX", str(2 * 1024 * 1024)))

# Outcomes work.py can print. `interrupted` is written by recovery, never here.
OUTCOME = re.compile(r"outcome to record:\s*(\w+)")

_stop = False


def _handle_signal(_sig, _frame):
    global _stop
    _stop = True
    log("stop requested — finishing this tick and exiting")


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log(message: str) -> None:
    line = f"{datetime.now().isoformat(timespec='seconds')}  {message}"
    print(line, flush=True)
    try:
        # Rotate before writing rather than after, so the file never exceeds
        # the cap even if the process dies mid-tick. One generation is enough:
        # this is an operational log, not an audit trail.
        if LOG.exists() and LOG.stat().st_size > LOG_MAX_BYTES:
            LOG.replace(LOG.with_suffix(".log.1"))
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError as exc:                                  # noqa: BLE001
        # A log that cannot be written must not stop the work.
        print(f"  (could not write log: {exc})", flush=True)


# ---------------------------------------------------------------------------
# Health — visibility, not control
# ---------------------------------------------------------------------------

def read_health() -> dict:
    try:
        return json.loads(HEALTH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"agents": {}, "ticks": 0, "rounds": 0}


def record(agent: str, outcome: str | None, ok: bool) -> dict:
    """Track consecutive failures per agent.

    Deliberately advisory. The rotation already advances after every round, so
    a dead agent costs one tick in three rather than the whole night — the
    problem is self-limiting and does not need a kill switch. What it does need
    is to be visible, because the failure mode that cost this project most was
    the one that produced no error at all.
    """
    h = read_health()
    a = h["agents"].setdefault(agent, {"consecutive_failures": 0, "last": None,
                                       "rounds": 0})
    a["rounds"] += 1
    a["last"] = {"at": datetime.now().isoformat(timespec="seconds"),
                 "outcome": outcome, "ok": ok}
    a["consecutive_failures"] = 0 if ok else a["consecutive_failures"] + 1
    h["rounds"] = h.get("rounds", 0) + 1
    try:
        HEALTH.write_text(json.dumps(h, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass
    if a["consecutive_failures"] >= 3:
        log(f"WARNING: {agent} has failed {a['consecutive_failures']} rounds in "
            f"a row. Run `python work.py probe --agent {agent}` — it is "
            f"probably a credential or a CLI update, not the work.")
    return h


# ---------------------------------------------------------------------------
# One tick
# ---------------------------------------------------------------------------

def run(argv: list[str], timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *argv], cwd=str(HERE),
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def agent_now() -> str:
    try:
        return json.loads((HERE / "sentinel.json").read_text(encoding="utf-8"))["agent"]
    except Exception:                                        # noqa: BLE001
        return "unknown"


def tick() -> None:
    # 1. prerun. Exit 1 is the ordinary "nothing to do" answer: outside the
    #    window, at the daily ceiling, or a round already running.
    pre = run([str(ROUND), "prerun"], timeout=300)
    first = (pre.stdout or pre.stderr or "").strip().splitlines()
    if pre.returncode != 0:
        log(f"idle — {first[-1] if first else 'prerun refused'}")
        return
    log(f"claimed — {first[-1] if first else ''}")

    agent = agent_now()

    # 2. the work itself. work.py bounds the agent with its own timeout, so the
    #    generous ceiling here is only a backstop against work.py itself hanging.
    try:
        w = run([str(WORK)], timeout=3 * 3600)
        out = (w.stdout or "") + (w.stderr or "")
    except subprocess.TimeoutExpired:
        log(f"{agent}: work.py exceeded 3h — leaving the claim for recovery")
        return

    for line in (w.stdout or "").splitlines():
        if line.strip():
            log(f"  {line.rstrip()}")

    m = OUTCOME.search(out)
    outcome = m.group(1) if m else None
    if not outcome:
        # No outcome printed means work.py died in a way it did not handle. The
        # claim is left alone on purpose: the lease will expire and the next
        # prerun will recover it properly, which is the path already tested.
        log(f"{agent}: no outcome printed (exit {w.returncode}) — leaving the "
            f"claim for lease recovery")
        record(agent, None, ok=False)
        return

    # 3. postrun. Only now does the rotation advance.
    post = run([str(ROUND), "postrun", outcome], timeout=300)
    tail = (post.stdout or post.stderr or "").strip().splitlines()
    log(f"{agent}: {outcome} — {tail[-1] if tail else ''}")
    record(agent, outcome, ok=(outcome == "new_issue" and post.returncode == 0))


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def cmd_status() -> int:
    h = read_health()
    print(f"rounds recorded: {h.get('rounds', 0)}\n")
    for name, a in sorted(h.get("agents", {}).items()):
        last = a.get("last") or {}
        flag = "  <-- failing" if a.get("consecutive_failures", 0) >= 3 else ""
        print(f"  {name:8} rounds={a.get('rounds', 0):3} "
              f"consecutive_failures={a.get('consecutive_failures', 0)} "
              f"last={last.get('outcome')} at {last.get('at')}{flag}")
    if LOG.exists():
        print(f"\nlast lines of {LOG.name}:")
        for line in LOG.read_text(encoding="utf-8").splitlines()[-15:]:
            print(f"  {line}")
    return 0


def pid_alive(pid: int) -> bool:
    """Is a process with this id running right now?

    Deliberately not a timestamp heuristic. A supervisor killed by a restart
    leaves a lock whose mtime says "seconds ago" and whose process is gone;
    anything that infers liveness from the file's age gets that backwards and
    blocks the next logon from starting.
    """
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            out = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True, text=True, timeout=30,
                encoding="utf-8", errors="replace").stdout
        except (OSError, subprocess.SubprocessError):
            return True        # cannot tell — assume alive and stay out of the way
        return str(pid) in out
    try:
        os.kill(pid, 0)        # signal 0 only checks; it does not terminate
    except ProcessLookupError:
        return False
    except PermissionError:
        return True            # exists, owned by someone else
    return True


def acquire_lock() -> bool:
    """One supervisor at a time.

    Task Scheduler can start a second copy while the first is still finishing a
    round, and two loops sharing one sentinel would each treat the other's
    claim as stale. The lock records a pid; whether that pid is running is the
    only question worth asking about it.
    """
    try:
        if LOCK.exists():
            raw = LOCK.read_text(encoding="utf-8").strip()
            try:
                pid = int(raw)
            except ValueError:
                pid = -1
            if pid == os.getpid():
                return True                      # our own lock, re-entered
            if pid_alive(pid):
                log(f"another supervisor is running (pid {pid}); "
                    f"delete {LOCK.name} if that is wrong")
                return False
            log(f"found a lock from pid {raw}, which is no longer running — "
                f"taking over")
        LOCK.write_text(str(os.getpid()), encoding="utf-8")
        return True
    except OSError as exc:                                   # noqa: BLE001
        log(f"could not take the lock: {exc}")
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--once", action="store_true", help="one tick, then exit")
    ap.add_argument("--status", action="store_true", help="recent history, then exit")
    ap.add_argument("--tick", type=int, default=TICK_SECONDS,
                    help=f"seconds between ticks (default {TICK_SECONDS})")
    args = ap.parse_args()

    if args.status:
        return cmd_status()

    for s in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(s, _handle_signal)
        except (ValueError, AttributeError, OSError):
            pass   # not every signal exists on Windows

    if args.once:
        tick()
        return 0

    if not acquire_lock():
        return 1
    log(f"supervisor started (pid {os.getpid()}, tick {args.tick}s)")
    try:
        while not _stop:
            try:
                tick()
            except Exception as exc:                         # noqa: BLE001
                # A tick that throws must not end the night. The claim, if one
                # was taken, is recovered by the next prerun's lease check.
                log(f"tick raised {type(exc).__name__}: {exc}")
            woke = datetime.now()
            while not _stop and datetime.now() - woke < timedelta(seconds=args.tick):
                time.sleep(2)
    finally:
        LOCK.unlink(missing_ok=True)
        log("supervisor stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
