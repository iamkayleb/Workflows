from __future__ import annotations

import io
import sys
from unittest.mock import patch

from scripts.langchain import task_decomposer


def test_decompose_task_fallback_adds_verification() -> None:
    result = task_decomposer.decompose_task("Update docs and add tests", use_llm=False)
    sub_tasks = result["sub_tasks"]
    assert len(sub_tasks) >= 2
    assert all("verify" in task.lower() for task in sub_tasks)


def test_normalize_subtasks_splits_multi_action() -> None:
    sub_tasks = task_decomposer._normalize_subtasks(["Update docs and add tests"])
    assert len(sub_tasks) == 2
    assert any("update docs" in task.lower() for task in sub_tasks)
    assert any("add tests" in task.lower() for task in sub_tasks)
    assert all("verify" in task.lower() for task in sub_tasks)
    assert any("docs updated" in task.lower() for task in sub_tasks)
    assert any("tests pass" in task.lower() for task in sub_tasks)


def test_normalize_subtasks_strips_dependency_clause() -> None:
    sub_tasks = task_decomposer._normalize_subtasks(["After merging PR #123, update docs"])
    assert len(sub_tasks) == 1
    assert "after merging" not in sub_tasks[0].lower()
    assert "update docs" in sub_tasks[0].lower()


def test_normalize_subtasks_rephrases_dependency_phrases() -> None:
    sub_tasks = task_decomposer._normalize_subtasks(["Depends on backend merge"])
    assert len(sub_tasks) == 1
    assert sub_tasks[0].lower().startswith("document dependency for:")
    assert "depends on" not in sub_tasks[0].lower()
    assert "verify" in sub_tasks[0].lower()


def test_normalize_subtasks_scopes_large_tasks() -> None:
    sub_tasks = task_decomposer._normalize_subtasks(
        ["Implement end-to-end workflow for keepalive metrics collection"]
    )
    assert len(sub_tasks) == 3
    assert any(task.lower().startswith("define scope for:") for task in sub_tasks)
    assert any(task.lower().startswith("implement focused slice for:") for task in sub_tasks)
    assert any(task.lower().startswith("validate focused slice for:") for task in sub_tasks)
    assert all("verify" in task.lower() for task in sub_tasks)


def test_decompose_task_empty_input() -> None:
    """decompose_task returns empty sub_tasks for empty input."""
    result = task_decomposer.decompose_task("")
    assert result["sub_tasks"] == []
    assert result["provider_used"] is None
    assert result["used_llm"] is False


def test_decompose_task_whitespace_only() -> None:
    """decompose_task returns empty sub_tasks for whitespace-only input."""
    result = task_decomposer.decompose_task("   \n\t  ")
    assert result["sub_tasks"] == []


def test_split_task_parts_with_then() -> None:
    """_split_task_parts splits on ' then '."""
    parts = task_decomposer._split_task_parts("update config then run tests")
    assert len(parts) == 2
    assert "update config" in parts
    assert "run tests" in parts


def test_split_task_parts_with_semicolon() -> None:
    """_split_task_parts splits on semicolons."""
    parts = task_decomposer._split_task_parts("fix bug; write tests; deploy")
    assert len(parts) == 3


def test_split_task_parts_with_comma() -> None:
    """_split_task_parts splits on commas."""
    parts = task_decomposer._split_task_parts("lint, format, typecheck")
    assert len(parts) == 3


def test_split_task_parts_with_slash() -> None:
    """_split_task_parts splits on slashes."""
    parts = task_decomposer._split_task_parts("config/settings")
    assert len(parts) == 2


def test_split_task_parts_single_task() -> None:
    """_split_task_parts returns single element for simple task."""
    parts = task_decomposer._split_task_parts("simple task")
    assert parts == ["simple task"]


def test_word_count() -> None:
    """_word_count counts alphanumeric words."""
    assert task_decomposer._word_count("hello world") == 2
    assert task_decomposer._word_count("it's a test") == 3
    assert task_decomposer._word_count("") == 0


def test_is_large_task_by_keywords() -> None:
    """_is_large_task detects large task keywords."""
    assert task_decomposer._is_large_task("full migration of database")
    assert task_decomposer._is_large_task("overall system redesign")
    assert task_decomposer._is_large_task("refactor entire codebase")
    assert task_decomposer._is_large_task("migrate to new api")
    assert task_decomposer._is_large_task("consolidate modules")
    assert task_decomposer._is_large_task("rollout new features")


def test_is_large_task_by_word_count() -> None:
    """_is_large_task detects tasks exceeding MAX_SUBTASK_WORDS."""
    long_task = "this is a very long task description that exceeds the maximum word limit"
    assert task_decomposer._is_large_task(long_task)


def test_is_large_task_small_task() -> None:
    """_is_large_task returns False for small tasks."""
    assert not task_decomposer._is_large_task("fix bug")
    assert not task_decomposer._is_large_task("add test")


def test_is_large_task_prefix_with_keyword() -> None:
    """_is_large_task handles prefixes with large keywords."""
    assert task_decomposer._is_large_task("implement full system")
    assert task_decomposer._is_large_task("define migration plan")


def test_infer_verification_patterns() -> None:
    """_infer_verification returns appropriate verification for various patterns."""
    assert task_decomposer._infer_verification("add tests for module") == "tests pass"
    assert task_decomposer._infer_verification("update documentation") == "docs updated"
    assert task_decomposer._infer_verification("run black formatter") == "formatter passes"
    assert task_decomposer._infer_verification("fix lint errors") == "lint passes"
    assert task_decomposer._infer_verification("run mypy typecheck") == "typecheck passes"
    assert task_decomposer._infer_verification("bump dependencies") == "dependencies updated"
    assert task_decomposer._infer_verification("update config file") == "config validated"
    assert task_decomposer._infer_verification("random task") is None


def test_ensure_verification_adds_verify() -> None:
    """_ensure_verification adds verification when missing."""
    result = task_decomposer._ensure_verification("add tests")
    assert "verify" in result.lower()
    assert "tests pass" in result.lower()


def test_ensure_verification_keeps_existing() -> None:
    """_ensure_verification keeps existing verify clause."""
    task = "update docs (verify: reviewed)"
    result = task_decomposer._ensure_verification(task)
    assert result == task


def test_contains_dependency_phrase() -> None:
    """_contains_dependency_phrase detects dependency patterns."""
    assert task_decomposer._contains_dependency_phrase("depends on PR merge")
    assert task_decomposer._contains_dependency_phrase("blocked by backend")
    assert task_decomposer._contains_dependency_phrase("waiting for review")
    assert task_decomposer._contains_dependency_phrase("post-merge cleanup")
    assert task_decomposer._contains_dependency_phrase("after merge, deploy")
    assert not task_decomposer._contains_dependency_phrase("simple task")


def test_rewrite_dependency_task() -> None:
    """_rewrite_dependency_task reformats dependency tasks."""
    result = task_decomposer._rewrite_dependency_task("depends on backend merge")
    assert result.startswith("Document dependency for:")
    assert "depends on" not in result.lower()
    assert "verify" in result.lower()


def test_rewrite_dependency_task_empty_cleaned() -> None:
    """_rewrite_dependency_task handles edge case where cleaned text is empty."""
    result = task_decomposer._rewrite_dependency_task("depends on")
    assert "dependency details" in result.lower()


def test_parse_subtasks_various_formats() -> None:
    """_parse_subtasks handles various list formats."""
    text = """
    - First task
    * Second task
    + Third task
    1. Fourth task
    2) Fifth task
    Plain line
    """
    tasks = task_decomposer._parse_subtasks(text)
    assert len(tasks) == 6
    assert "First task" in tasks
    assert "Plain line" in tasks


def test_parse_subtasks_empty_lines() -> None:
    """_parse_subtasks skips empty lines."""
    text = "\n\n- task\n\n"
    tasks = task_decomposer._parse_subtasks(text)
    assert tasks == ["task"]


def test_fallback_decompose_empty() -> None:
    """_fallback_decompose returns empty list for empty input."""
    result = task_decomposer._fallback_decompose("")
    assert result == []


def test_fallback_decompose_multi_part() -> None:
    """_fallback_decompose splits multi-part tasks."""
    result = task_decomposer._fallback_decompose("task A and task B")
    assert len(result) == 2


def test_fallback_decompose_single_task() -> None:
    """_fallback_decompose creates standard decomposition for single tasks."""
    result = task_decomposer._fallback_decompose("single task")
    assert len(result) == 3
    assert any("define approach" in t.lower() for t in result)
    assert any("implement" in t.lower() for t in result)
    assert any("validate" in t.lower() for t in result)


def test_expand_large_task() -> None:
    """_expand_large_task creates scoped sub-tasks."""
    result = task_decomposer._expand_large_task("big project")
    assert len(result) == 3
    assert any("define scope" in t.lower() for t in result)
    assert any("implement focused slice" in t.lower() for t in result)
    assert any("validate focused slice" in t.lower() for t in result)


def test_strip_dependency_clause() -> None:
    """_strip_dependency_clause removes leading dependency clauses."""
    assert task_decomposer._strip_dependency_clause("after merge, deploy") == "deploy"
    assert task_decomposer._strip_dependency_clause("once done, test") == "test"
    assert task_decomposer._strip_dependency_clause("simple task") == "simple task"


def test_normalize_subtasks_public_api() -> None:
    """normalize_subtasks is accessible as public API."""
    result = task_decomposer.normalize_subtasks(["update docs"])
    assert len(result) == 1
    assert "verify" in result[0].lower()


def test_load_prompt_fallback() -> None:
    """_load_prompt returns default template when file doesn't exist."""
    prompt = task_decomposer._load_prompt()
    assert "Decompose into smaller" in prompt


def test_main_json_output(monkeypatch) -> None:
    """main outputs JSON when --json flag is provided."""
    monkeypatch.setattr(
        sys, "argv", ["task_decomposer.py", "--task", "simple task", "--json", "--no-llm"]
    )
    captured = io.StringIO()
    with patch("sys.stdout", captured):
        task_decomposer.main()
    output = captured.getvalue()
    assert '"sub_tasks"' in output
    assert '"used_llm": false' in output


def test_main_plain_output(monkeypatch) -> None:
    """main outputs plain text without --json flag."""
    monkeypatch.setattr(sys, "argv", ["task_decomposer.py", "--task", "simple task", "--no-llm"])
    captured = io.StringIO()
    with patch("sys.stdout", captured):
        task_decomposer.main()
    output = captured.getvalue()
    assert output.startswith("-")
    assert "verify" in output.lower()


def test_main_empty_task(monkeypatch) -> None:
    """main handles empty task gracefully."""
    monkeypatch.setattr(sys, "argv", ["task_decomposer.py", "--json", "--no-llm"])
    captured = io.StringIO()
    with patch("sys.stdout", captured):
        task_decomposer.main()
    output = captured.getvalue()
    assert '"sub_tasks": []' in output
