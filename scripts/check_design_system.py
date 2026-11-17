#!/usr/bin/env python3
"""Report styling that bypasses the project's design system.

    python scripts/check_design_system.py                 # report, exit 0
    python scripts/check_design_system.py --strict        # fail on violations
    python scripts/check_design_system.py --changed-only  # only the PR's files

Why this exists
===============
A design system that nothing enforces is a directory, not a system. One was
synced into a consumer repo, sat there through four months of automated
rounds, and ended up with **zero references** in the application while every
component invented its own palette. Nobody noticed, because nothing asked.

Prompting agents to "use the design system" does not fix that. An instruction
an agent can quietly skip is indistinguishable from one it followed, which is
the same shape as a test that passes because it checked nothing. So this
checks the result instead of trusting the intent.

What counts as a violation
==========================
Only things that are unambiguous when a token system exists:

  * a literal colour in source -- ``#1e293b``, ``rgb(...)``, ``hsl(...)``
  * an inline ``style=`` attribute that sets a colour

Layout utilities, spacing and typography are left alone. This is not a
style-police pass; it catches the one thing that visibly fragments a product,
which is twelve components each picking their own greys.

If the project has no ``design-system/tokens.css`` the check reports that and
exits 0. A repo without a design system has nothing to bypass.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# Source files worth scanning. Stylesheets are included: the design system's
# own files are excluded by path below, so a hex here is an app-level override.
SUFFIXES = {".tsx", ".jsx", ".ts", ".js", ".vue", ".svelte", ".css", ".scss", ".html"}

SKIP_DIRS = {
    "node_modules", ".next", "dist", "build", "out", "coverage", ".git",
    "__pycache__", ".venv", "venv", ".workflows-lib", "design-system",
    "public", "generated", ".turbo",
}

HEX = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b")
FUNC = re.compile(r"\b(?:rgba?|hsla?)\s*\(", re.I)
INLINE_STYLE_COLOR = re.compile(
    r"""style\s*=\s*[{"'][^}"']*(?:color|background|border|fill|stroke)""", re.I
)

# `#` appears constantly in things that are not colours. Anchor out the common
# false positives rather than reporting them and training people to ignore this.
NOT_A_COLOUR = re.compile(
    r"""(?x)
    (?: ^\s*(?://|\#|\*|<!--)        # comment lines
      | \b(?:https?|mailto):         # URLs
      | \#\{                         # template interpolation
      | \#[0-9]+\b                   # issue references: #552
      | id\s*=                       # anchors
    )"""
)


def tokens_file(root: Path) -> Path | None:
    for candidate in (root / "design-system" / "tokens.css",
                      root / "src" / "design-system" / "tokens.css"):
        if candidate.is_file():
            return candidate
    return None


def changed_files(root: Path, base: str) -> list[Path] | None:
    """Files this branch changed, or None when git cannot say."""
    try:
        merge_base = subprocess.run(
            ["git", "merge-base", "HEAD", base], cwd=root,
            capture_output=True, text=True, check=True).stdout.strip()
        out = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=ACMR", merge_base, "HEAD"],
            cwd=root, capture_output=True, text=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return [root / line for line in out.splitlines() if line.strip()]


def scan(path: Path, root: Path) -> list[tuple[int, str, str]]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    found: list[tuple[int, str, str]] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if NOT_A_COLOUR.search(line):
            continue
        if HEX.search(line):
            found.append((lineno, "literal colour", line.strip()[:110]))
        elif FUNC.search(line):
            found.append((lineno, "colour function", line.strip()[:110]))
        elif INLINE_STYLE_COLOR.search(line):
            found.append((lineno, "inline style colour", line.strip()[:110]))
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", type=Path)
    ap.add_argument("--strict", action="store_true",
                    help="exit non-zero when violations are found")
    ap.add_argument("--changed-only", action="store_true",
                    help="scan only files changed against --base")
    ap.add_argument("--base", default="origin/main",
                    help="base ref for --changed-only (default origin/main)")
    ap.add_argument("--max-report", type=int, default=40)
    args = ap.parse_args()

    root = args.root.resolve()
    tokens = tokens_file(root)
    if tokens is None:
        print("No design-system/tokens.css in this project; nothing to bypass.")
        return 0

    token_names = sorted(set(re.findall(r"^\s*(--[a-z0-9-]+)\s*:",
                                        tokens.read_text(encoding="utf-8"), re.M)))
    print(f"Design system: {tokens.relative_to(root)} ({len(token_names)} tokens)")

    if args.changed_only:
        candidates = changed_files(root, args.base)
        if candidates is None:
            print("Could not determine changed files from git; scanning the tree instead.")
            candidates = None
    else:
        candidates = None

    if candidates is None:
        candidates = [p for p in root.rglob("*") if p.is_file()]

    files = [
        p for p in candidates
        if p.is_file()
        and p.suffix in SUFFIXES
        and not any(part in SKIP_DIRS for part in p.relative_to(root).parts)
    ]

    violations: list[tuple[Path, int, str, str]] = []
    for path in sorted(files):
        for lineno, kind, snippet in scan(path, root):
            violations.append((path, lineno, kind, snippet))

    print(f"Scanned {len(files)} source file(s).")
    if not violations:
        print("No literal colours outside the design system.")
        return 0

    by_file: dict[Path, int] = {}
    for path, _, _, _ in violations:
        by_file[path] = by_file.get(path, 0) + 1

    print(f"\n{len(violations)} literal colour(s) in {len(by_file)} file(s):\n")
    for path, lineno, kind, snippet in violations[: args.max_report]:
        print(f"  {path.relative_to(root)}:{lineno}  {kind}")
        print(f"      {snippet}")
    if len(violations) > args.max_report:
        print(f"  ... and {len(violations) - args.max_report} more")

    print(
        "\nUse a design-system token instead, or override one in an app stylesheet\n"
        "loaded after tokens.css. Never fork components.css.\n"
        f"Available tokens: {', '.join(token_names[:8])}, ..."
    )

    if args.strict:
        print("\n::error::Styling bypasses the design system.")
        return 1
    print("\n(advisory: pass --strict to fail on this)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
