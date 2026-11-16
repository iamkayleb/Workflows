#!/usr/bin/env python3
"""Apply to work.py: let the Claude agent run commands, like the others.

    python claude-can-run.py

The Claude adapter used `--permission-mode acceptEdits`, which allows file
edits and refuses command execution. Codex gets `--sandbox workspace-write`,
which allows both. So the two agents had different capabilities and nobody
said so: a Claude round could never run `pnpm build`, `vitest`, `tsc` or
`prisma migrate`, and returned unverified work by construction.

It showed up plainly in consecutive rounds on 10 November:

    claude  "This sandbox rejected every command that would execute code...
             none of the acceptance criteria are verified."
    codex   "Production build passed. All 17 booking tests passed. Real
             migrated-and-seeded SQLite verification passed."

Same harness, same issue shape, opposite outcomes — decided by which agent the
rotation happened to pick.

`bypassPermissions` is the mode that lets it run things. That is a real
decision, not a detail: the agent can execute arbitrary commands. It runs in a
throwaway git worktree under C:\\bw, the sandbox has no network, and the
harness — not the agent — does the committing and pushing. Those are the
boundaries that make it acceptable here. They would not make it acceptable
against a working copy you care about.

Safe to run more than once. To undo, set CLAUDE_MODE back to acceptEdits.
"""
from __future__ import annotations

import pathlib
import sys

CLAUDE_MODE = "bypassPermissions"

p = pathlib.Path("work.py")
if not p.exists():
    sys.exit("work.py not found — run this from bukay-ops")
s = p.read_text(encoding="utf-8").replace("\r\n", "\n")

OLD = '"--permission-mode", "acceptEdits"'
NEW = f'"--permission-mode", "{CLAUDE_MODE}"'

if NEW in s:
    print(f"already applied (claude runs with --permission-mode {CLAUDE_MODE})")
    raise SystemExit(0)
if OLD not in s:
    sys.exit("could not find the claude permission mode — send me work.py")

s = s.replace(OLD, NEW, 1)

# Say why, where the next reader will look.
anchor = '    "claude": {\n'
if anchor in s and "runs in a throwaway worktree" not in s:
    note = ('        # bypassPermissions so Claude can run the verification its own\n'
            '        # acceptance criteria demand. It runs in a throwaway worktree with\n'
            '        # no network, and the harness does the committing and pushing.\n')
    s = s.replace(anchor, anchor + note, 1)

p.write_text(s, encoding="utf-8", newline="\n")
print(f"applied: claude now runs with --permission-mode {CLAUDE_MODE}")
print("verify with:  python work.py doctor")
