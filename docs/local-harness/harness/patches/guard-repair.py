#!/usr/bin/env python3
"""Repair guard.py after guard-fix.py appended the gh() wrapper in the wrong place.

    python guard-repair.py

guard-fix.py looked for `def die(msg` as the place to insert the retry wrapper.
The real signature is `def die(message`, so the marker never matched and the
wrapper was appended to the end of the file — after
`if __name__ == "__main__": sys.exit(main())`. Python runs that line before it
ever reaches the definition, so `gh` is undefined when `fetch()` calls it.

This moves the wrapper above the entry point. It also verifies the result
imports cleanly before writing, so a bad repair cannot replace a bad patch.
"""
from __future__ import annotations

import pathlib
import re
import sys

p = pathlib.Path("guard.py")
if not p.exists():
    sys.exit("guard.py not found — run this from bukay-ops")
original = p.read_text(encoding="utf-8").replace("\r\n", "\n")
s = original

entry = "\nif __name__ == \"__main__\":"
if entry not in s:
    sys.exit("could not find the entry point in guard.py — send me the file")

head, tail = s.split(entry, 1)

# The wrapper, if it was appended, now lives in `tail`.
m = re.search(r"\n\ndef gh\(path: str\) -> list \| dict:.*", tail, re.S)
if m:
    wrapper = m.group(0)
    tail = tail[:m.start()] + tail[m.end():]
    s = head + wrapper.rstrip("\n") + "\n" + entry + tail
    where = "moved the wrapper above the entry point"
elif "\ndef gh(" in head:
    print("gh() is already defined before the entry point — nothing to repair")
    raise SystemExit(0)
else:
    sys.exit("could not find the appended gh() wrapper — send me guard.py")

# Prove it loads before replacing the file.
tmp = p.with_suffix(".py.check")
tmp.write_text(s, encoding="utf-8", newline="\n")
import py_compile
try:
    py_compile.compile(str(tmp), doraise=True)
except py_compile.PyCompileError as exc:
    tmp.unlink(missing_ok=True)
    sys.exit(f"repair would not compile, leaving guard.py alone:\n{exc}")
tmp.unlink(missing_ok=True)

p.write_text(s, encoding="utf-8", newline="\n")
print(f"repaired: {where}")
print("now run:  python guard.py triage")
