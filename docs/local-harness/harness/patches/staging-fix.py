#!/usr/bin/env python3
"""Apply to work.py: stage reliably, and say more when git refuses.

    python staging-fix.py

The previous approach combined `git add -A -- .` with `:(exclude)` pathspecs.
Git exits 1 when a pathspec resolves to ignored files, so once `.pnpm-store/`
was added to .gitignore the whole staging step failed and a finished round was
thrown away at the last step:

    error: git add -A failed (1): ... The following paths are ign[ored]

Two fixes. Stage everything the ordinary way, then unstage the build artefacts
— two simple commands that cannot interact badly, instead of one clever one.
And raise the error excerpt from 500 characters, which truncated the message
exactly where it became useful.

Also disables autocrlf inside the worktree. The warnings in that failure
("LF will be replaced by CRLF the next time Git touches it") mean every file
the agent writes risks a line-ending rewrite, which turns a seven-file change
into a diff nobody can review.

Safe to run more than once.
"""
from __future__ import annotations

import pathlib
import re
import sys

p = pathlib.Path("work.py")
if not p.exists():
    sys.exit("work.py not found — run this from bukay-ops")
s = p.read_text(encoding="utf-8").replace("\r\n", "\n")
changed: list[str] = []

# --- 1. stage, then unstage the caches -----------------------------------
start = s.find('            git(["add", "-A", "--",')
if start != -1:
    end = s.find("], wt)", start)
    if end == -1:
        sys.exit("could not find the end of the staging call")
    end += len("], wt)\n")
    new = (
        '            # Stage everything, then unstage the build artefacts. Combining\n'
        '            # `-- .` with `:(exclude)` pathspecs makes git exit 1 as soon as\n'
        '            # one of those paths is also in .gitignore, which threw away a\n'
        '            # finished round at the last step. Two plain commands cannot\n'
        '            # interact badly; one clever one did.\n'
        '            git(["add", "-A"], wt)\n'
        '            for junk in (".pnpm-store", "node_modules", ".next", "coverage",\n'
        '                         ".turbo", "prisma/dev.db", "prisma/dev.db-journal"):\n'
        '                git(["reset", "-q", "--", junk], wt, check=False)\n')
    s = s[:start] + new + s[end:]
    changed.append("staging")
elif 'for junk in (".pnpm-store"' in s:
    changed.append("staging (already present)")
else:
    sys.exit("could not find the staging call — send me work.py and I will look")

# --- 2. show more of git's complaint -------------------------------------
s2, n = re.subn(r"\.strip\(\)\[:500\]\}\"\)", '.strip()[:2000]}")', s)
if n:
    s = s2
    changed.append("longer error excerpt")

# --- 3. keep line endings as the agent wrote them -------------------------
anchor = '    base_sha = git(["rev-parse", "HEAD"], wt)\n'
if anchor in s and "autocrlf" not in s:
    add = (
        '    # Windows would otherwise rewrite line endings on every file the agent\n'
        '    # touches, turning a small change into an unreviewable diff.\n'
        '    git(["config", "core.autocrlf", "false"], wt, check=False)\n')
    s = s.replace(anchor, anchor + add, 1)
    changed.append("autocrlf off in the worktree")

p.write_text(s, encoding="utf-8", newline="\n")
print("applied:", ", ".join(changed) if changed else "nothing")
