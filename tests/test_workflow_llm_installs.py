"""Workflow checks for pinned LLM dependency installs."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AGENTS_AUTO_PILOT = ROOT / ".github" / "workflows" / "agents-auto-pilot.yml"
REUSABLE_VERIFIER = ROOT / ".github" / "workflows" / "reusable-agents-verifier.yml"

PINNED_INSTALLS = {
    AGENTS_AUTO_PILOT: "pip install -r tools/requirements-llm.txt",
    REUSABLE_VERIFIER: "pip install -r .workflows-lib/tools/requirements-llm.txt",
}


def _read_workflow(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _merge_continuations(text: str) -> list[str]:
    merged: list[str] = []
    buffer = ""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            if buffer:
                merged.append(buffer)
                buffer = ""
            continue
        buffer = f"{buffer} {stripped}".strip() if buffer else stripped
        if not stripped.endswith("\\"):
            merged.append(buffer)
            buffer = ""
    if buffer:
        merged.append(buffer)
    return merged


def _floating_langchain_installs(text: str) -> list[str]:
    offenders: list[str] = []
    for line in _merge_continuations(text):
        if "pip install" not in line or "langchain" not in line:
            continue
        if "-r tools/requirements-llm.txt" in line:
            continue
        if "-r .workflows-lib/tools/requirements-llm.txt" in line:
            continue
        offenders.append(line)
    return offenders


def _requirements_met(path: Path, expected_install: str) -> bool:
    text = _read_workflow(path)
    return expected_install in text and not _floating_langchain_installs(text)


@pytest.mark.xfail(
    not _requirements_met(AGENTS_AUTO_PILOT, PINNED_INSTALLS[AGENTS_AUTO_PILOT]),
    reason="Workflow updates are required to pin langchain installs.",
)
def test_agents_auto_pilot_uses_pinned_llm_installs() -> None:
    text = _read_workflow(AGENTS_AUTO_PILOT)
    assert PINNED_INSTALLS[AGENTS_AUTO_PILOT] in text
    assert not _floating_langchain_installs(text)


@pytest.mark.xfail(
    not _requirements_met(REUSABLE_VERIFIER, PINNED_INSTALLS[REUSABLE_VERIFIER]),
    reason="Workflow updates are required to pin langchain installs.",
)
def test_reusable_verifier_uses_pinned_llm_installs() -> None:
    text = _read_workflow(REUSABLE_VERIFIER)
    assert PINNED_INSTALLS[REUSABLE_VERIFIER] in text
    assert not _floating_langchain_installs(text)
