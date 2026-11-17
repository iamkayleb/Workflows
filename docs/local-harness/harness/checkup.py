#!/usr/bin/env python3
"""One command that answers "why did nothing run last night".

    python checkup.py

Run it from bukay-ops. It reads only — nothing is started, stopped or changed.

Four nights have now been lost to a question this prints in one screen: is a
supervisor running, is it running the code on disk, what does the sentinel say,
what did the log last say, and what would the guard decide right now.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
OK, BAD, MEH = "  ok   ", "  **   ", "  --   "


def say(text: str = "") -> None:
    """Print without ever dying on an encoding the console cannot take.

    The log carries replacement characters from an earlier mojibake, and a
    Windows console is cp1252. A diagnostic tool that crashes while reporting
    is worse than no tool.
    """
    enc = (sys.stdout.encoding or "utf-8")
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode(enc, "replace").decode(enc, "replace"))


def head(t: str) -> None:
    say(f"\n{t}\n" + "-" * len(t))


def run(argv, timeout=60) -> str:
    try:
        cp = subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                            encoding="utf-8", errors="replace")
        return (cp.stdout or "") + (cp.stderr or "")
    except Exception as exc:                                   # noqa: BLE001
        return f"(could not run {argv[0]}: {exc})"


# --- 1. is a supervisor running, and since when -----------------------------
head("supervisor process")
procs = []
if os.name == "nt":
    out = run(["powershell", "-NoProfile", "-Command",
               "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
               "Where-Object { $_.CommandLine -like '*supervisor.py*' } | "
               "ForEach-Object { \"$($_.ProcessId)|$($_.CreationDate)\" }"])
    procs = [l.strip() for l in out.splitlines() if l.strip() and "|" in l]
else:
    out = run(["bash", "-lc",
               "ps -eo pid,lstart,args | grep -E 'python[0-9.]* .*supervisor\\.py' "
               "| grep -v grep || true"])
    procs = [l.strip() for l in out.splitlines() if l.strip()]

if not procs:
    say(f"{BAD} no supervisor process is running — nothing will tick")
elif len(procs) > 1:
    say(f"{BAD} {len(procs)} supervisors running; only one should be:")
    for x in procs:
        say(f"         {x}")
else:
    say(f"{OK} one supervisor running: {procs[0]}")

lock = HERE / "supervisor.lock"
say(f"{OK if lock.exists() else MEH} lock file: "
      f"{lock.read_text().strip() if lock.exists() else 'absent'}")

# --- 2. is it running the code on disk --------------------------------------
head("patches present in the files on disk")
EXPECT = {
    "supervisor.py": [(("PRERUN_TIMEOUT",), "sleep tolerance"),
                      (("stderr from the failed round",), "failure logging"),
                      (("pid_alive",), "lock liveness")],
    "work.py": [(("already checked out in",), "worktree guard"),
                (("exclude).pnpm-store", "for junk in"), "staging exclusions"),
                (("formatter did not run",), "formatting step"),
                (("already opened a pull request",), "adopt existing PR"),
                (("subprocess.DEVNULL",), "stdin closed")],
    "guard.py": [(("approved work wins",), "lane preference"),
                 (("_gh_once",), "network retry")],
}
import re
for fname, checks in EXPECT.items():
    f = HERE / fname
    if not f.exists():
        say(f"{BAD} {fname} missing")
        continue
    body = f.read_text(encoding="utf-8", errors="replace")
    for needles, label in checks:
        found = any(n in body for n in needles)
        say(f"{OK if found else BAD} {fname:14} {label}")

# --- 3. does the RUNNING process have them ----------------------------------
head("is the running supervisor using that code")
log = HERE / "supervisor.log"
rotated = HERE / "supervisor.log.1"
if log.exists():
    lines = []
    # The log rotates at 2 MB, taking the start lines with it. Reading only the
    # current file reported "no supervisor started line at all" when it was
    # simply in the other one.
    if rotated.exists():
        lines += rotated.read_text(encoding="utf-8", errors="replace").splitlines()
    lines += log.read_text(encoding="utf-8", errors="replace").splitlines()
    starts = [l for l in lines if "supervisor started" in l]
    if starts:
        last = starts[-1]
        say(f"{OK} last start: {last.strip()}")
        try:
            when = dt.datetime.fromisoformat(last.split()[0])
            newest = max((HERE / f).stat().st_mtime for f in EXPECT if (HERE / f).exists())
            if when.timestamp() < newest:
                say(f"{BAD} a file was edited AFTER that start — restart the "
                      f"supervisor or it keeps running the old code")
            else:
                say(f"{OK} started after the most recent edit")
        except Exception:                                      # noqa: BLE001
            pass
    else:
        say(f"{BAD} no 'supervisor started' line in the log at all")
    if any("timed out after 300 seconds" in l for l in lines[-200:]):
        say(f"{BAD} log still shows a 300s prerun timeout — the running "
              f"process predates the sleep-tolerance patch")
else:
    say(f"{BAD} no supervisor.log")

# --- 4. sentinel and configuration ------------------------------------------
head("sentinel")
sent = HERE / "sentinel.json"
if sent.exists():
    s = json.loads(sent.read_text(encoding="utf-8"))
    for k in ("phase", "agent", "last_outcome", "rounds_today", "day"):
        say(f"         {k:14} {s.get(k)}")
    today = dt.date.today().isoformat()
    if s.get("day") != today:
        say(f"{OK} day is stale ({s.get('day')}) — the counter rolls on the next prerun")
    elif s.get("rounds_today", 0) >= 6:
        say(f"{BAD} {s['rounds_today']} rounds already today; check DAILY_CEILING")
    if s.get("phase") != "idle":
        say(f"{BAD} a claim is held (phase={s['phase']}) — nothing else can start "
              f"until its lease expires or it is recovered")
else:
    say(f"{BAD} no sentinel.json")

head("configuration")
rp = HERE / "round.py"
if rp.exists():
    body = rp.read_text(encoding="utf-8", errors="replace")
    for name in ("WINDOW_START_HOUR", "WINDOW_END_HOUR", "DAILY_CEILING",
                 "LEASE_MINUTES", "ROTATION"):
        m = re.search(rf"^{name}\s*=\s*(.+)$", body, re.M)
        say(f"         {name:20} {m.group(1).strip() if m else '?'}")
now = dt.datetime.now()
say(f"         now                  {now:%H:%M} ({now:%A})")
for v in ("BUKAY_REPO_DIR", "BUKAY_PR_CAP", "BUKAY_TICK_SECONDS", "BUKAY_CODEX_MODEL"):
    val = os.environ.get(v)
    say(f"{OK if val else MEH} {v:20} {val or 'not set in THIS shell'}")
say("         (a scheduled task sees only Windows user variables, not shell exports)")

# --- 5. what would the guard decide right now -------------------------------
head("guard, right now")
g = run([sys.executable, str(HERE / "guard.py"), "status"], timeout=180)
try:
    d = json.loads(g)
    say(f"         decision   {d['lane']} — {d['reason']}")
    say(f"         actionable {d['actionable_issues']}")
    say(f"         agent PRs  {d['agent_prs_open']}/{d['pr_cap']}")
except Exception:                                              # noqa: BLE001
    say(f"{BAD} guard did not return JSON:\n{g.strip()[:400]}")

# --- 6. the tail --------------------------------------------------------------
head("last 12 log lines")
if log.exists():
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines()[-12:]:
        say("         " + line.rstrip())

say("\nLines marked ** are the ones to act on.")
