from __future__ import annotations

import re
from pathlib import Path

WORKFLOWS_DIR = Path(".github/workflows")
AUTO_PILOT = WORKFLOWS_DIR / "agents-auto-pilot.yml"
VERIFIER = WORKFLOWS_DIR / "reusable-agents-verifier.yml"


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


def test_agents_auto_pilot_llm_install_is_pinned() -> None:
    text = _load_text(AUTO_PILOT)
    _assert_pinned_install(
        text,
        "pip install -r tools/requirements-llm.txt",
        AUTO_PILOT.name,
    )
    _assert_no_floating_langchain(text, AUTO_PILOT.name)


def test_reusable_agents_verifier_llm_install_is_pinned_for_modes() -> None:
    text = _load_text(VERIFIER)
    _assert_pinned_install(
        text,
        "pip install -r .workflows-lib/tools/requirements-llm.txt",
        VERIFIER.name,
        minimum=2,
    )
    _assert_no_floating_langchain(text, VERIFIER.name)
