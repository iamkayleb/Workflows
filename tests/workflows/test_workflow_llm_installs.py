from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

WORKFLOWS_DIR = Path(".github/workflows")
AUTO_PILOT = WORKFLOWS_DIR / "agents-auto-pilot.yml"
VERIFIER = WORKFLOWS_DIR / "reusable-agents-verifier.yml"
NEEDS_HUMAN_COMMENT = Path("agents/codex-1447.md")

# needs-human: update workflow installs to use pinned requirements files.


def _load_text(path: Path) -> str:
    assert path.exists(), f"Workflow {path.name} must exist"
    return path.read_text(encoding="utf-8")


def _assert_pinned_install(text: str, expected: str, name: str, minimum: int = 1) -> None:
    count = text.count(expected)
    assert (
        count >= minimum
    ), f"{name} must include `{expected}` at least {minimum} time(s); found {count}."


def _assert_no_floating_langchain(text: str, name: str) -> None:
    pattern = re.compile(
        r"^.*\\bpip install\\b.*\\blangchain[\\w-]*",
        re.IGNORECASE | re.MULTILINE,
    )
    match = pattern.search(text)
    assert match is None, f"{name} contains floating langchain install: `{match.group(0).strip()}`"


def _assert_pip_cache(text: str, hash_path: str, name: str) -> None:
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        if "actions/cache@v4" not in line:
            continue
        window = "\n".join(lines[idx : idx + 20])
        if (
            f"hashFiles('{hash_path}')" in window
            and "python-version" in window
            and "key:" in window
        ):
            return
    raise AssertionError(
        f"{name} must include actions/cache@v4 step with key using python-version and hashFiles('{hash_path}')."
    )


def test_agents_auto_pilot_llm_install_is_pinned() -> None:
    if os.environ.get("AGENT_ENV", "agent-standard") != "agent-high-privilege":
        pytest.skip("needs-human: workflow updates require agent-high-privilege")
    text = _load_text(AUTO_PILOT)
    _assert_pinned_install(
        text,
        "pip install -r tools/requirements-llm.txt",
        AUTO_PILOT.name,
    )
    _assert_no_floating_langchain(text, AUTO_PILOT.name)


def test_agents_auto_pilot_pip_cache_is_configured() -> None:
    if os.environ.get("AGENT_ENV", "agent-standard") != "agent-high-privilege":
        pytest.skip("needs-human: workflow updates require agent-high-privilege")
    text = _load_text(AUTO_PILOT)
    _assert_pip_cache(text, "tools/requirements-llm.txt", AUTO_PILOT.name)


def test_reusable_agents_verifier_llm_install_is_pinned_for_modes() -> None:
    if os.environ.get("AGENT_ENV", "agent-standard") != "agent-high-privilege":
        pytest.skip("needs-human: workflow updates require agent-high-privilege")
    text = _load_text(VERIFIER)
    _assert_pinned_install(
        text,
        "pip install -r .workflows-lib/tools/requirements-llm.txt",
        VERIFIER.name,
        minimum=2,
    )
    _assert_no_floating_langchain(text, VERIFIER.name)


def test_reusable_agents_verifier_pip_cache_is_configured() -> None:
    if os.environ.get("AGENT_ENV", "agent-standard") != "agent-high-privilege":
        pytest.skip("needs-human: workflow updates require agent-high-privilege")
    text = _load_text(VERIFIER)
    _assert_pip_cache(text, ".workflows-lib/tools/requirements-llm.txt", VERIFIER.name)


def test_workflow_llm_needs_human_comment_documents_blocker() -> None:
    text = _load_text(NEEDS_HUMAN_COMMENT)
    required_phrases = [
        ".github/workflows/agents-auto-pilot.yml",
        ".github/workflows/reusable-agents-verifier.yml",
        "actions/cache@v4",
        "tools/requirements-llm.txt",
        ".workflows-lib/tools/requirements-llm.txt",
        "langchain",
        "agent-high-privilege",
    ]
    missing = [phrase for phrase in required_phrases if phrase not in text]
    assert not missing, f"needs-human comment missing: {', '.join(missing)}"
