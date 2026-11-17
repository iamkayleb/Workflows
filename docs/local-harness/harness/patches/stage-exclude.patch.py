#!/usr/bin/env python3
"""Apply to work.py: stop staging build caches into the pull request.

    python stage-exclude.patch.py work.py

The harness stages with `git add -A` so it captures everything the agent
changed without needing the agent to know what it touched. The cost is that it
also captures anything the *preparation* step created — `pnpm install` writes
a local `.pnpm-store/` in a fresh worktree, and PR #541 shipped
`.pnpm-store/v11/index.db` into the repository.

The fix is a pathspec exclusion rather than a change to the repo's .gitignore:
these directories are artefacts of how the harness prepares a worktree, so
knowing about them belongs to the harness. The repository should not have to
carry entries for a build process it never runs itself.
"""
import pathlib
import sys

p = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "work.py")
s = p.read_text(encoding="utf-8")

OLD = '''        if dirty:
            print(f"staging {len(dirty.splitlines())} change(s) left by {agent}")
            git(["add", "-A"], wt)'''

NEW = '''        if dirty:
            print(f"staging {len(dirty.splitlines())} change(s) left by {agent}")
            # `-A` captures everything the agent touched without it having to
            # tell us — but it also captures what `pnpm install` leaves behind.
            # These are artefacts of how this harness prepares a worktree, so
            # excluding them is the harness's job, not the repository's.
            git(["add", "-A", "--",
                 ".",
                 ":(exclude).pnpm-store",
                 ":(exclude)node_modules",
                 ":(exclude).next",
                 ":(exclude)coverage",
                 ":(exclude)prisma/dev.db",
                 ":(exclude)prisma/dev.db-journal",
                 ":(exclude).turbo",
                 ":(exclude)*.log"], wt)'''

if OLD not in s:
    sys.exit("could not find the staging step — is this the current work.py?")
s = s.replace(OLD, NEW)

# Report anything left unstaged, so a genuine change that matches one of the
# exclusions above cannot disappear silently.
OLD2 = '''        # --- ground truth ---------------------------------------------------
        # Not "did it say it was done" — did anything land on disk.
        commits = git(["rev-list", "--count", f"{base_sha}..HEAD"], wt)'''
NEW2 = '''        left = git(["status", "--porcelain"], wt, check=False)
        if left:
            # Excluded on purpose, but say so: an exclusion that silently eats
            # a real change would be the same class of bug as the mock that
            # accepted a column which did not exist.
            print(f"not staged ({len(left.splitlines())} path(s), excluded as "
                  f"build artefacts):")
            for line in left.splitlines()[:10]:
                print(f"  {line}")

        # --- ground truth ---------------------------------------------------
        # Not "did it say it was done" — did anything land on disk.
        commits = git(["rev-list", "--count", f"{base_sha}..HEAD"], wt)'''
if OLD2 in s:
    s = s.replace(OLD2, NEW2)
else:
    print("warning: could not add the unstaged report; staging fix applied anyway")

p.write_text(s, encoding="utf-8")
print(f"patched {p}")
