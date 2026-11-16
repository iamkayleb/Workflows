#!/usr/bin/env python3
"""Apply to work.py: close stdin for agents, matching the probe.

    python stdin-devnull.py

`work.py probe` passes stdin=DEVNULL and Cursor answers in 9 to 18 seconds,
ten times out of ten. A real round inherits the terminal's stdin instead, and
Cursor printed its interactive startup tip and then sat there. A CLI that can
see a TTY may wait for input that is never coming.

Make the round behave like the probe: no stdin unless the adapter asks for it
(Codex reads its prompt from stdin, so that one keeps its pipe).

This also matters for scheduled runs, where there is no terminal at all — the
round and the probe should not differ in a way that only shows up at 9pm.

Safe to run more than once.
"""
from __future__ import annotations

import pathlib
import sys

p = pathlib.Path("work.py")
if not p.exists():
    sys.exit("work.py not found — run this from bukay-ops")
s = p.read_text(encoding="utf-8").replace("\r\n", "\n")

if "stdin=subprocess.DEVNULL" in s and "use_stdin" in s and "input=prompt if use_stdin" not in s:
    print("already applied")
    raise SystemExit(0)

OLD = '''        use_stdin = ADAPTERS[agent].get("stdin_prompt")
        cp = subprocess.run(argv, cwd=str(wt), text=True,
                            timeout=tmo,
                            encoding="utf-8", errors="replace",
                            input=prompt if use_stdin else None)'''
NEW = '''        use_stdin = ADAPTERS[agent].get("stdin_prompt")
        # An agent that is not reading its prompt from stdin gets no stdin at
        # all. The probe does this and Cursor answers in seconds; a round that
        # inherited the terminal's stdin printed its interactive startup tip
        # and stopped. A scheduled run has no terminal either, so the two paths
        # must not differ here.
        cp = subprocess.run(argv, cwd=str(wt), text=True,
                            timeout=tmo,
                            encoding="utf-8", errors="replace",
                            **({"input": prompt} if use_stdin
                               else {"stdin": subprocess.DEVNULL}))'''

if OLD not in s:
    # Tolerate the timeout constant not yet being per-agent.
    OLD2 = OLD.replace("timeout=tmo,", "timeout=AGENT_TIMEOUT_SECONDS,")
    NEW2 = NEW.replace("timeout=tmo,", "timeout=AGENT_TIMEOUT_SECONDS,")
    if OLD2 in s:
        OLD, NEW = OLD2, NEW2
    else:
        sys.exit("could not find the agent invocation — send me work.py")

p.write_text(s.replace(OLD, NEW, 1), encoding="utf-8", newline="\n")
print("applied: stdin closed for agents that do not read a prompt from it")
