#!/usr/bin/env python3
"""Apply to work.py: restore the formatting step, and make it speak up.

    python format-step.py

`prettier --check` is a CI gate here. A round that skips it fails the build for
a reason unrelated to whether its change is correct, which is what happened to
PRs #548 and #549 and left `main` red.

The step existed. A later patch rewrote the block it lived in and removed it,
and nothing noticed because its output was the only evidence it ran — there was
no `formatting...` line in any round output after that.

It also ran with check=False, so a failing formatter would have been silent
even when present. That is the same defect this project keeps cataloguing: a
step whose failure looks exactly like success.

Now it runs, reports, and warns loudly when it cannot.

Safe to run more than once.
"""
from __future__ import annotations

import pathlib
import sys

p = pathlib.Path("work.py")
if not p.exists():
    sys.exit("work.py not found — run this from bukay-ops")
s = p.read_text(encoding="utf-8").replace("\r\n", "\n")

if "formatter did not run" in s:
    print("already applied")
    raise SystemExit(0)

anchor = '        dirty = git(["status", "--porcelain"], wt, check=False)\n'
if anchor not in s:
    sys.exit("could not find the staging block — send me work.py")

block = '''        if dirty:
            # `prettier --check` is a CI gate. An agent that forgets it fails
            # the build for a reason unrelated to its change, so the harness
            # does it — and says so, because a silent formatter is
            # indistinguishable from one that never ran.
            pnpm = shutil.which("pnpm") or shutil.which("pnpm.cmd")
            if not pnpm:
                print("WARNING: pnpm not found — the formatter did not run. "
                      "Expect CI to fail on `prettier --check`.")
            else:
                print("formatting...")
                fmt = run([pnpm, "format"], cwd=wt, timeout=900, check=False)
                if fmt.returncode != 0:
                    print(f"WARNING: the formatter did not run cleanly "
                          f"(exit {fmt.returncode}). Expect CI to fail on "
                          f"`prettier --check`. Output:")
                    for line in ((fmt.stderr or fmt.stdout or "")
                                 .strip().splitlines()[-8:]):
                        print(f"  ! {line}")
                else:
                    print("formatted.")
                dirty = git(["status", "--porcelain"], wt, check=False)

'''
s = s.replace(anchor, anchor + block, 1)
p.write_text(s, encoding="utf-8", newline="\n")
print("applied: formatting step restored, with a warning when it cannot run")
