from __future__ import annotations

import json
import sys
from pathlib import Path

from scripts import check_issue_consistency


def test_extract_issue_numbers_handles_word_and_slug() -> None:
    text = "Issue #1075 and issue-1075 are referenced."
    numbers = check_issue_consistency.extract_issue_numbers(text)
    assert numbers == {1075}


def test_extract_title_issue_number_prefers_hash() -> None:
    title = "Codex belt for #1075"
    assert check_issue_consistency.extract_title_issue_number(title) == 1075


def test_collect_header_issue_numbers_reads_issue_lines(tmp_path: Path) -> None:
    path = tmp_path / "sample.txt"
    path.write_text("# Issue: 1075\n# not an issue reference\n", encoding="utf-8")
    numbers = check_issue_consistency.collect_header_issue_numbers(path, max_lines=5)
    assert numbers == {1075}


def test_extract_issue_numbers_ignores_pr_hashes() -> None:
    text = "PR #1076 relates to Issue #1075"
    numbers = check_issue_consistency.extract_issue_numbers(text)
    assert numbers == {1075}


def test_extract_head_ref_issue_numbers_from_branch() -> None:
    head_ref = "codex/issue-144-keepalive"
    numbers = check_issue_consistency.extract_head_ref_issue_numbers(head_ref)
    assert numbers == {144}


def test_is_autofix_context_reads_event_labels(tmp_path: Path, monkeypatch) -> None:
    payload = {
        "pull_request": {
            "labels": [{"name": "auto-fix"}],
        }
    }
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))

    assert check_issue_consistency.is_autofix_context("", "") is True


def test_is_autofix_context_detects_hyphenated_title() -> None:
    assert check_issue_consistency.is_autofix_context("Auto-fix from CI failure", "") is True


def test_resolve_pr_context_reads_event_payload(tmp_path: Path) -> None:
    payload = {
        "pull_request": {
            "title": "Fix issue #4242",
            "head": {"ref": "codex/issue-4242"},
        }
    }
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(payload), encoding="utf-8")

    title, head_ref = check_issue_consistency.resolve_pr_context("", "", str(event_path))

    assert title == "Fix issue #4242"
    assert head_ref == "codex/issue-4242"


def test_resolve_pr_context_falls_back_to_workflow_run(tmp_path: Path) -> None:
    payload = {"workflow_run": {"head_branch": "autofix/ci-branch"}}
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(payload), encoding="utf-8")

    title, head_ref = check_issue_consistency.resolve_pr_context("", "", str(event_path))

    assert title == ""
    assert head_ref == "autofix/ci-branch"


def test_run_git_with_fallback_handles_ambiguous_argument(monkeypatch) -> None:
    calls = []

    def fake_run_git(args: list[str]) -> str:
        calls.append(args)
        if args == ["log"]:
            raise RuntimeError(
                "fatal: ambiguous argument 'deadbeef..HEAD': unknown revision or path not in the working tree."
            )
        return "ok"

    monkeypatch.setattr(check_issue_consistency, "_run_git", fake_run_git)

    output, used_fallback = check_issue_consistency._run_git_with_fallback_and_flag(
        ["log"],
        ["log", "-n", "1"],
    )

    assert output == "ok"
    assert used_fallback is True
    assert calls == [["log"], ["log", "-n", "1"]]


def test_main_skips_on_multiple_head_ref_issue_numbers(monkeypatch, capsys) -> None:
    def fake_collect_commit_messages(base_ref, base_sha, base_remote):
        return [], False

    def fake_collect_changed_files(base_ref, base_sha, base_remote):
        return [], False

    monkeypatch.setattr(
        check_issue_consistency,
        "collect_commit_messages",
        fake_collect_commit_messages,
    )
    monkeypatch.setattr(
        check_issue_consistency,
        "collect_changed_files",
        fake_collect_changed_files,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["check_issue_consistency.py", "--pr-title", "", "--head-ref", "codex/issue-12-issue-34"],
    )

    exit_code = check_issue_consistency.main()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "multiple issue numbers detected in head ref" in captured.out
