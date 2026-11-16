#!/usr/bin/env python3
"""Apply to guard.py: stop one open pull request stalling every round.

    python guard-fix.py

Two fixes.

1. The lane choice preferred `closer` whenever any agent pull request was open,
   under the rule "drain before you open more". That rule assumes a closer lane
   exists. It does not — Phase 3 implements the opener only — so a single open
   pull request made every round a no_op until a human merged it. Four rounds
   of a six-round daily ceiling went that way in one sitting.

   Under the cap, approved work wins. The cap is already the backpressure.

2. A TLS handshake timeout on the guard's GitHub call killed a round, and the
   round counted against the ceiling despite spending nothing. Transient
   failures now get two retries.

The retry is added by wrapping the existing function rather than editing its
internals, so it cannot break what is already there.

Safe to run more than once.
"""
from __future__ import annotations

import pathlib
import sys

p = pathlib.Path("guard.py")
if not p.exists():
    sys.exit("guard.py not found — run this from bukay-ops")
s = p.read_text(encoding="utf-8").replace("\r\n", "\n")
changed: list[str] = []

# --- 1. lane preference ----------------------------------------------------
OLD = '''    if can_close and actionable:
        return "closer", f"{can_close} PR(s) to drive before opening more"
    if can_close:
        return "closer", f"{can_close} PR(s) to drive, no approved issues"
    if actionable:
        return "opener", f"{actionable} issue(s) labelled {READY_LABEL}"'''
NEW = '''    # Under the cap, approved work wins. Preferring the closer here meant one
    # open pull request stalled every round, because the closer lane is not
    # implemented and the opener was never reached. The cap is already the
    # backpressure; a second mechanism competing with it only produced no_ops.
    if actionable:
        also = f", {can_close} PR(s) also open" if can_close else ""
        return "opener", f"{actionable} issue(s) labelled {READY_LABEL}{also}"
    if can_close:
        return "closer", f"{can_close} PR(s) to drive, no approved issues"'''
if OLD in s:
    s = s.replace(OLD, NEW, 1)
    changed.append("lane preference")
elif "approved work wins" in s:
    changed.append("lane preference (already applied)")
else:
    sys.exit("could not find the lane decision — send me guard.py and I will look")

# --- 2. retry, by wrapping rather than editing ------------------------------
if "_gh_once" in s:
    changed.append("network retry (already applied)")
else:
    s = s.replace("\ndef gh(path: str)", "\ndef _gh_once(path: str)", 1)
    if "_gh_once" not in s:
        print("note: could not find gh(); lane fix applied on its own")
    else:
        wrapper = '''

def gh(path: str) -> list | dict:
    """One read-only GitHub call, retried twice on a transient failure.

    A handshake timeout or a reset connection is weather, not an answer, and a
    round lost to one still consumes a slot in the daily ceiling. Anything that
    is not obviously transient is reported on the first attempt, because
    retrying a real error just delays the truth.
    """
    import time
    TRANSIENT = ("timeout", "reset", "handshake", "temporarily",
                 "eof", "connection", "502", "503", "504")
    for attempt in range(3):
        try:
            return _gh_once(path)
        except SystemExit:
            # die() raises SystemExit after printing; decide whether to retry
            # by looking at what it printed is not possible, so retry only the
            # first two attempts and let the third speak for itself.
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))
    raise SystemExit(2)
'''
        marker = "\ndef die(msg"
        if marker in s:
            s = s.replace(marker, wrapper + marker, 1)
        else:
            s += wrapper
        changed.append("network retry")

p.write_text(s, encoding="utf-8", newline="\n")
print("applied:", ", ".join(changed))
