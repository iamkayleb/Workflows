#!/usr/bin/env python3
"""Generate a needs-human comment for LLM workflow update requirements."""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from pathlib import Path

DEFAULT_WORKFLOWS = (
    Path(".github/workflows/agents-auto-pilot.yml"),
    Path(".github/workflows/reusable-agents-verifier.yml"),
)


def build_comment(
    workflows: Iterable[Path] = DEFAULT_WORKFLOWS, include_label: bool = False
) -> str:
    lines: list[str] = []
    if include_label:
        lines.append("Label: needs-human")
    lines.append(
        "Workflow updates required in .github/workflows/agents-auto-pilot.yml and "
        ".github/workflows/reusable-agents-verifier.yml. Add pinned installs "
        "(`pip install -r tools/requirements-llm.txt` and "
        "`pip install -r .workflows-lib/tools/requirements-llm.txt` for evaluate/compare), "
        "add actions/cache@v4 pip cache keyed by requirements hash + Python version, "
        "and remove any floating `pip install langchain*` lines. Workflow edits require "
        "agent-high-privilege."
    )
    lines.append("")
    lines.append("Affected workflows:")
    for workflow in workflows:
        lines.append(f"- {workflow}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--workflow",
        action="append",
        type=Path,
        dest="workflows",
        help="Path to a workflow YAML file (repeatable). Defaults to the LLM workflows.",
    )
    parser.add_argument(
        "--include-label",
        action="store_true",
        help="Include needs-human label line in the output.",
    )
    args = parser.parse_args()
    workflows = tuple(args.workflows) if args.workflows else DEFAULT_WORKFLOWS
    print(build_comment(workflows=workflows, include_label=args.include_label))


if __name__ == "__main__":
    main()
