#!/usr/bin/env python3
"""Apply to work.py: say so when a previous round is still holding the branch.

    python worktree-guard.py

Keeping a worktree that still has uncommitted changes stopped the harness
throwing work away. It also meant the next round on that issue died like this:

    claimed — agent=claude
    claude: no outcome printed (exit 2)

...because `git worktree add -B <branch>` refuses when the branch is already
checked out somewhere. Forty-two seconds, no explanation, three nights running.

The condition is not an error — it means a human has unfinished work in that
directory. So detect it first, name the directory, and return no_op instead of
dying at a git command whose message never reaches the log.

Safe to run more than once.
"""
from __future__ import annotations

import pathlib
import sys

p = pathlib.Path("work.py")
if not p.exists():
    sys.exit("work.py not found — run this from bukay-ops")
s = p.read_text(encoding="utf-8").replace("\r\n", "\n")

if "already checked out in" in s:
    print("already applied")
    raise SystemExit(0)

anchor = '''    # --- worktree -----------------------------------------------------------
    WORKTREE_ROOT.mkdir(parents=True, exist_ok=True)
    git(["fetch", "origin", BASE_BRANCH], REPO_DIR)
'''
if anchor not in s:
    # Fall back to a looser anchor if the comment has drifted.
    anchor = '    git(["fetch", "origin", BASE_BRANCH], REPO_DIR)\n'
    if anchor not in s:
        sys.exit("could not find the worktree setup — send me work.py")

addition = '''
    # A worktree kept from an earlier round still holds this branch, which makes
    # `git worktree add -B` refuse. That is not a fault: it means unfinished
    # work is sitting in that directory. Say where, and stop cleanly.
    existing = git(["worktree", "list", "--porcelain"], REPO_DIR, check=False)
    held_at = None
    current = None
    for line in existing.splitlines():
        if line.startswith("worktree "):
            current = line[len("worktree "):].strip()
        elif line.strip() == f"branch refs/heads/{branch}":
            held_at = current
            break
    if held_at:
        print(f"\\n{branch} is already checked out in {held_at}")
        print("A previous round left work there. Finish and push it, or remove")
        print(f"the worktree:  git worktree remove --force {held_at}")
        print("outcome to record: no_op")
        return 1

'''
s = s.replace(anchor, anchor.rstrip("\n") + "\n" + addition, 1)
p.write_text(s, encoding="utf-8", newline="\n")
print("applied: worktree-held check")
