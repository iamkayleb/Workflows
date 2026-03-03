"""Tests for generate_llm_workflow_update_comment helpers."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from scripts.generate_llm_workflow_update_comment import build_comment


def test_build_comment_includes_label_and_requirements() -> None:
    comment = build_comment(include_label=True)

    assert "Label: needs-human" in comment
    assert ".github/workflows/agents-auto-pilot.yml" in comment
    assert ".github/workflows/reusable-agents-verifier.yml" in comment
    assert "pip install -r tools/requirements-llm.txt" in comment
    assert "pip install -r .workflows-lib/tools/requirements-llm.txt" in comment
    assert "actions/cache@v4" in comment
    assert "langchain" in comment
    assert "agent-high-privilege" in comment


def test_build_comment_lists_default_workflows() -> None:
    comment = build_comment()

    assert "Affected workflows:" in comment
    assert "- .github/workflows/agents-auto-pilot.yml" in comment
    assert "- .github/workflows/reusable-agents-verifier.yml" in comment
