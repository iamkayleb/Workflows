from __future__ import annotations

import json
from unittest import mock

import pytest

from scripts.langchain import pr_verifier


def _response_with(content: str) -> mock.MagicMock:
    response = mock.MagicMock()
    response.content = content
    return response


def _valid_payload() -> dict[str, object]:
    return {
        "verdict": "PASS",
        "confidence": 0.9,
        "scores": {
            "correctness": 9,
            "completeness": 8,
            "quality": 9,
            "testing": 8,
            "risks": 7,
        },
        "concerns": [],
        "summary": "Looks good.",
    }


@pytest.mark.parametrize(
    "bad_content",
    [
        lambda payload: "Here you go:\n" + json.dumps(payload),
        lambda payload: "```json\n" + json.dumps(payload) + "\n```",
        lambda _payload: (
            '{"verdict": "PASS", "confidence": 0.9, "scores": '
            '{"correctness": 9, "completeness": 8, "quality": 9, "testing": 8, "risks": 7,}, '
            '"concerns": [], "summary": "Looks good.",}'
        ),
    ],
)
def test_evaluate_pr_repairs_malformed_output(monkeypatch: pytest.MonkeyPatch, bad_content) -> None:
    payload = _valid_payload()
    bad = bad_content(payload)
    good = json.dumps(payload)

    mock_client = mock.MagicMock()
    mock_client.invoke.side_effect = [_response_with(bad), _response_with(good)]

    monkeypatch.setattr(pr_verifier, "_prepare_prompt", lambda ctx, diff: "prompt")
    monkeypatch.setattr(
        pr_verifier,
        "_get_llm_client",
        lambda model=None, provider=None: (mock_client, "github-models"),
    )

    result = pr_verifier.evaluate_pr("context")
    assert result.verdict == "PASS"
    assert result.used_llm is True
    assert mock_client.invoke.call_count == 2


def test_comparison_runner_repairs_malformed_output() -> None:
    payload = _valid_payload()
    bad = "```json\n" + json.dumps(payload) + "\n```"
    good = json.dumps(payload)

    mock_client = mock.MagicMock()
    mock_client.invoke.side_effect = [_response_with(bad), _response_with(good)]

    runner = pr_verifier.ComparisonRunner(
        context="context",
        diff=None,
        prompt="prompt",
        clients=[(mock_client, "github-models", "model")],
    )
    result = runner.run_single(mock_client, "github-models", "model")
    assert result.verdict == "PASS"
    assert result.used_llm is True
    assert mock_client.invoke.call_count == 2


def test_evaluate_pr_repairs_once_then_returns_error(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _valid_payload()
    bad = "```json\n" + json.dumps(payload) + "\n```"

    mock_client = mock.MagicMock()
    mock_client.invoke.side_effect = [_response_with(bad), _response_with(bad)]

    monkeypatch.setattr(pr_verifier, "_prepare_prompt", lambda ctx, diff: "prompt")
    monkeypatch.setattr(
        pr_verifier,
        "_get_llm_client",
        lambda model=None, provider=None: (mock_client, "github-models"),
    )

    result = pr_verifier.evaluate_pr("context")
    assert result.verdict == "CONCERNS"
    assert result.used_llm is True
    assert result.error
    assert "Failed to parse JSON response after repair" in result.error
    assert mock_client.invoke.call_count == 2
