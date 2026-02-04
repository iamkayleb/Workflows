"""Tests for tools/codex_session_analyzer.py."""

from __future__ import annotations

from unittest.mock import patch

from tools.codex_session_analyzer import analyze_session
from tools.llm_provider import (
    CompletionAnalysis,
    FallbackChainProvider,
    LLMProvider,
    SessionQualityContext,
)


class RecordingProvider(LLMProvider):
    """Provider that records the quality context received."""

    def __init__(self) -> None:
        self.received_quality_context: SessionQualityContext | None = None

    @property
    def name(self) -> str:
        return "recording"

    def is_available(self) -> bool:
        return True

    def analyze_completion(
        self,
        session_output: str,
        tasks: list[str],
        context: str | None = None,
        quality_context: SessionQualityContext | None = None,
    ) -> CompletionAnalysis:
        self.received_quality_context = quality_context
        return CompletionAnalysis(
            completed_tasks=[],
            in_progress_tasks=[],
            blocked_tasks=[],
            confidence=0.4,
            reasoning="recording",
            provider_used=self.name,
        )


def test_analyze_session_passes_quality_context_through_fallback_chain():
    """Quality context is passed to the active provider in fallback chain."""
    provider = RecordingProvider()
    chain = FallbackChainProvider([provider])
    summary_text = "Summary of work completed."

    with patch("tools.codex_session_analyzer.get_llm_provider", return_value=chain):
        analyze_session(summary_text, ["task1"], data_source="summary")

    assert provider.received_quality_context is not None
    assert provider.received_quality_context.analysis_text_length == len(summary_text)


def test_analyze_session_skips_quality_context_for_legacy_provider():
    """Analyze session skips quality_context when provider doesn't support it."""

    class LegacyProvider(LLMProvider):
        def __init__(self) -> None:
            self.called = False

        @property
        def name(self) -> str:
            return "legacy"

        def is_available(self) -> bool:
            return True

        def analyze_completion(
            self,
            session_output: str,
            tasks: list[str],
            context: str | None = None,
        ) -> CompletionAnalysis:
            self.called = True
            _ = session_output
            _ = tasks
            _ = context
            return CompletionAnalysis(
                completed_tasks=[],
                in_progress_tasks=[],
                blocked_tasks=[],
                confidence=0.2,
                reasoning="legacy",
                provider_used=self.name,
            )

    provider = LegacyProvider()
    summary_text = "Summary of work completed."

    with patch("tools.codex_session_analyzer.get_llm_provider", return_value=provider):
        result = analyze_session(summary_text, ["task1"], data_source="summary")

    assert provider.called is True
    assert result.completion.provider_used == "legacy"
