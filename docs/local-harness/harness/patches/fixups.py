#!/usr/bin/env python3
"""Apply the outstanding harness fixes. Safe to run more than once.

    python fixups.py

Run it from bukay-ops, with supervisor.py and work.py beside it.

Replaces three separate patch scripts that matched exact multi-line strings
and failed on all three counts. This matches on structure rather than exact
text, is safe to re-run, and prints the surrounding lines when it cannot find
something — so a mismatch produces evidence instead of a shrug.
"""
from __future__ import annotations

import pathlib
import re
import sys

CHANGED: list[str] = []
SKIPPED: list[str] = []


def load(name: str) -> tuple[pathlib.Path, str] | None:
    p = pathlib.Path(name)
    if not p.exists():
        print(f"  {name}: not found in {p.resolve().parent} — skipping")
        return None
    # newline="" would preserve CRLF; we normalise instead, and write back LF.
    return p, p.read_text(encoding="utf-8").replace("\r\n", "\n")


def save(p: pathlib.Path, s: str) -> None:
    p.write_text(s, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------------------
# supervisor.py — log why a round failed, and show prerun's recovery lines
# ---------------------------------------------------------------------------

def fix_supervisor() -> None:
    got = load("supervisor.py")
    if not got:
        return
    p, s = got

    if "recovery explains itself" in s:
        SKIPPED.append("supervisor: prerun logging")
    else:
        pat = re.compile(
            r"[ \t]*first = \(pre\.stdout or pre\.stderr or \"\"\)\.strip\(\)\.splitlines\(\)\n"
            r"[ \t]*if pre\.returncode != 0:\n"
            r"[ \t]*log\(f\"idle — \{first\[-1\] if first else 'prerun refused'\}\"\)\n"
            r"[ \t]*return\n"
            r"[ \t]*log\(f\"claimed — \{first\[-1\] if first else ''\}\"\)\n")
        new = (
            '    lines = [l.rstrip() for l in\n'
            '             ((pre.stdout or "") + (pre.stderr or "")).splitlines() if l.strip()]\n'
            '    # Every line, because recovery explains itself on the lines BEFORE the\n'
            '    # verdict, and a recovered round must not look like an idle one.\n'
            '    for extra in lines[:-1]:\n'
            '        log(f"  {extra}")\n'
            '    verdict = lines[-1] if lines else "(no output)"\n'
            '    if pre.returncode != 0:\n'
            '        log(f"idle — {verdict}")\n'
            '        return\n'
            '    log(f"claimed — {verdict}")\n')
        s, n = pat.subn(new, s, count=1)
        (CHANGED if n else SKIPPED).append(
            "supervisor: prerun logging" if n else "supervisor: prerun logging (PATTERN NOT FOUND)")

    if "stderr from the failed round" in s:
        SKIPPED.append("supervisor: failure stderr")
    else:
        anchor = '        log(f"{agent}: no outcome printed (exit {w.returncode}) — leaving the "\n'
        if anchor in s:
            add = (
                '        # Record the error itself. A round that fails at 9pm with nobody\n'
                '        # watching is only useful if the morning can tell you why, and most\n'
                '        # failures arrive on stderr rather than stdout.\n'
                '        err = [l.rstrip() for l in (w.stderr or "").splitlines() if l.strip()]\n'
                '        if err:\n'
                '            log(f"{agent}: stderr from the failed round —")\n'
                '            for line in err[-25:]:\n'
                '                log(f"  ! {line}")\n'
                '        else:\n'
                '            log(f"{agent}: the failed round wrote nothing to stderr either")\n')
            s = s.replace(anchor, add + anchor, 1)
            CHANGED.append("supervisor: failure stderr")
        else:
            SKIPPED.append("supervisor: failure stderr (ANCHOR NOT FOUND)")

    save(p, s)


# ---------------------------------------------------------------------------
# work.py — stop staging build caches into the pull request
# ---------------------------------------------------------------------------

def fix_work() -> None:
    got = load("work.py")
    if not got:
        return
    p, s = got

    if "exclude).pnpm-store" in s:
        SKIPPED.append("work: staging exclusions")
        save(p, s)
        return

    pat = re.compile(r"[ \t]*git\(\[\"add\", \"-A\"\], wt\)\n")
    new = (
        '            # `-A` captures everything the agent touched without it having to\n'
        '            # tell us — but it also captures what `pnpm install` leaves behind.\n'
        '            # These are artefacts of how this harness prepares a worktree, so\n'
        '            # excluding them is the harness\'s job, not the repository\'s.\n'
        '            git(["add", "-A", "--",\n'
        '                 ".",\n'
        '                 ":(exclude).pnpm-store",\n'
        '                 ":(exclude)node_modules",\n'
        '                 ":(exclude).next",\n'
        '                 ":(exclude)coverage",\n'
        '                 ":(exclude)prisma/dev.db",\n'
        '                 ":(exclude)prisma/dev.db-journal",\n'
        '                 ":(exclude).turbo",\n'
        '                 ":(exclude)*.log"], wt)\n')
    s, n = pat.subn(new, s, count=1)
    if not n:
        SKIPPED.append("work: staging exclusions (PATTERN NOT FOUND)")
        save(p, s)
        return
    CHANGED.append("work: staging exclusions")

    # Report anything the exclusions held back, so a real change cannot vanish.
    anchor = '        commits = git(["rev-list", "--count", f"{base_sha}..HEAD"], wt)\n'
    if anchor in s and "excluded as " not in s:
        add = (
            '        left = git(["status", "--porcelain"], wt, check=False)\n'
            '        if left:\n'
            '            print(f"not staged ({len(left.splitlines())} path(s), excluded as "\n'
            '                  f"build artefacts):")\n'
            '            for line in left.splitlines()[:10]:\n'
            '                print(f"  {line}")\n\n')
        s = s.replace(anchor, add + anchor, 1)
        CHANGED.append("work: unstaged report")

    save(p, s)


def show(name: str, pattern: str, context: int = 3) -> None:
    """Print the lines around whatever we failed to match, with numbers."""
    p = pathlib.Path(name)
    if not p.exists():
        return
    lines = p.read_text(encoding="utf-8").splitlines()
    rx = re.compile(pattern)
    hits = [i for i, l in enumerate(lines) if rx.search(l)]
    if not hits:
        print(f"--- {name}: no lines matched {pattern!r} at all")
        return
    print(f"--- {name}")
    shown: set[int] = set()
    for i in hits:
        for j in range(max(0, i - context), min(len(lines), i + context + 1)):
            if j not in shown:
                shown.add(j)
                print(f"{j + 1:5}| {lines[j]}")
        print("      ...")


def main() -> int:
    print("Applying harness fixes.\n")
    fix_supervisor()
    fix_work()
    print()
    for c in CHANGED:
        print(f"  applied   {c}")
    for k in SKIPPED:
        print(f"  {'FAILED ' if 'NOT FOUND' in k else 'already '}  {k}")
    if any("NOT FOUND" in k for k in SKIPPED):
        print("\nSomething did not match. Here is what is actually there —")
        print("paste this and I will adjust:\n")
        show("supervisor.py", r"pre\s*=\s*run\(|first\s*=|no outcome printed")
        show("work.py", r'git\(\["add"|staging \{len')
        return 1
    print("\nDone." if CHANGED else "\nNothing to do — all fixes already present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
