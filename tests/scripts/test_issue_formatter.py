from __future__ import annotations

import json
import sys

from scripts.langchain import issue_formatter


def _extract_section(body: str, heading: str) -> str:
    marker = f"## {heading}"
    if marker not in body:
        return ""
    parts = body.split(marker, 1)[1].split("\n")
    # Skip the blank line after the heading
    content_lines = []
    for line in parts[1:]:
        if line.startswith("## "):
            break
        content_lines.append(line)
    return "\n".join(content_lines).strip()


def test_format_issue_fallback_adds_sections_and_checkboxes() -> None:
    raw = """Why:
We need to improve the issue intake.

Tasks:
- add formatter
- add tests

Acceptance Criteria:
- formatted issue body
- label transition works
"""
    result = issue_formatter.format_issue_body(raw, use_llm=False)
    formatted = result["formatted_body"]

    assert "## Why" in formatted
    assert "## Tasks" in formatted
    assert "## Acceptance Criteria" in formatted
    assert "- [ ] add formatter" in formatted
    assert "- [ ] add tests" in formatted
    assert "- [ ] formatted issue body" in formatted
    assert "- [ ] label transition works" in formatted


def test_format_issue_fallback_strips_bullets_from_scope() -> None:
    raw = """## Scope
- keep API stable
- avoid workflow changes

## Tasks
- add formatter
"""
    result = issue_formatter.format_issue_body(raw, use_llm=False)
    formatted = result["formatted_body"]

    scope = _extract_section(formatted, "Scope")
    assert scope
    assert "- " not in scope
    assert "* " not in scope
    assert "keep API stable" in scope
    assert "avoid workflow changes" in scope


def test_format_issue_fallback_uses_placeholders() -> None:
    raw = "Just a note without sections."
    result = issue_formatter.format_issue_body(raw, use_llm=False)
    formatted = result["formatted_body"]

    tasks = _extract_section(formatted, "Tasks")
    acceptance = _extract_section(formatted, "Acceptance Criteria")

    assert tasks == "- [ ] _Not provided._"
    assert acceptance == "- [ ] _Not provided._"


def test_load_prompt_appends_feedback(tmp_path, monkeypatch) -> None:
    prompt_path = tmp_path / "format_issue.md"
    feedback_path = tmp_path / "format_issue_feedback.md"
    prompt_path.write_text("Base prompt.", encoding="utf-8")
    feedback_path.write_text("Feedback notes.", encoding="utf-8")

    monkeypatch.setattr(issue_formatter, "PROMPT_PATH", prompt_path)
    monkeypatch.setattr(issue_formatter, "FEEDBACK_PROMPT_PATH", feedback_path)

    prompt = issue_formatter._load_prompt()

    assert "Base prompt." in prompt
    assert "Feedback notes." in prompt


def test_format_issue_body_falls_back_without_llm_tokens() -> None:
    raw = "Just a note without tokens."
    result = issue_formatter.format_issue_body(raw, use_llm=True)

    assert result["used_llm"] is False
    assert result["provider_used"] is None
    assert "## Tasks" in result["formatted_body"]


def test_build_label_transition_matches_expected_labels() -> None:
    assert issue_formatter.build_label_transition() == {
        "add": ["agents:formatted"],
        "remove": ["agents:format"],
    }


def test_main_emits_json_with_labels(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["issue_formatter.py", "--input-text", "Raw issue", "--json", "--no-llm"],
    )

    issue_formatter.main()
    captured = capsys.readouterr().out.strip()

    payload = json.loads(captured)
    assert payload["labels"] == {
        "add": ["agents:formatted"],
        "remove": ["agents:format"],
    }
    assert payload["used_llm"] is False
    assert "## Acceptance Criteria" in payload["formatted_body"]
