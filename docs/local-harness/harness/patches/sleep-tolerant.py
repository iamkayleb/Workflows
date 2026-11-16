#!/usr/bin/env python3
"""Apply to supervisor.py: stop reporting a suspended laptop as a fault.

    python sleep-tolerant.py

`round.py prerun` reads and writes one JSON file; it cannot take five minutes.
But `subprocess.run`'s timeout is wall-clock, and this machine sleeps. A tick
that starts at 15:32 and resumes after a suspend has blown a 300-second budget
without anything going wrong, and the log said:

    tick raised TimeoutExpired: ... round.py prerun ... timed out after 300 seconds

which reads like a failure and is not one. Two changes: a budget generous
enough that only a genuine hang trips it, and a message that names the likely
cause instead of raising to the catch-all handler.

Safe to run more than once.
"""
from __future__ import annotations

import pathlib
import re
import sys

p = pathlib.Path("supervisor.py")
if not p.exists():
    sys.exit("supervisor.py not found — run this from bukay-ops")
s = p.read_text(encoding="utf-8").replace("\r\n", "\n")
changed: list[str] = []

# 1. A local file operation does not need a five-minute ceiling to be safe; it
#    needs one large enough that only a real hang trips it.
s2, n = re.subn(r'run\(\[str\(ROUND\), "prerun"\], timeout=300\)',
                'run([str(ROUND), "prerun"], timeout=PRERUN_TIMEOUT)', s)
if n:
    changed.append("prerun timeout")
    s = s2
s2, n = re.subn(r'run\(\[str\(ROUND\), "postrun", outcome\], timeout=300\)',
                'run([str(ROUND), "postrun", outcome], timeout=PRERUN_TIMEOUT)', s)
if n:
    changed.append("postrun timeout")
    s = s2

if "PRERUN_TIMEOUT" in s and "PRERUN_TIMEOUT =" not in s:
    s = s.replace(
        "TICK_SECONDS = int(os.environ.get",
        "# Generous on purpose. These calls touch one JSON file, so the only way\n"
        "# they exceed this is a genuine hang — a suspended machine is handled\n"
        "# separately below, because wall-clock timeouts cannot tell the two apart.\n"
        "PRERUN_TIMEOUT = 900\n\n"
        "TICK_SECONDS = int(os.environ.get", 1)
    changed.append("PRERUN_TIMEOUT constant")

# 2. Name the cause rather than raising to the catch-all.
if "the machine probably slept" not in s:
    old = "    pre = run([str(ROUND), \"prerun\"], timeout=PRERUN_TIMEOUT)\n"
    new = (
        "    try:\n"
        "        pre = run([str(ROUND), \"prerun\"], timeout=PRERUN_TIMEOUT)\n"
        "    except subprocess.TimeoutExpired:\n"
        "        # A wall-clock timeout cannot distinguish a hung process from a\n"
        "        # laptop that suspended mid-call. prerun touches one file, so the\n"
        "        # second is overwhelmingly more likely. Skip the tick and say so.\n"
        "        log(\"prerun did not return — the machine probably slept mid-tick; \"\n"
        "            \"skipping this one\")\n"
        "        return\n")
    if old in s:
        s = s.replace(old, new, 1)
        changed.append("sleep-tolerant prerun")

p.write_text(s, encoding="utf-8", newline="\n")
print("applied:", ", ".join(changed) if changed else "nothing (already present)")
