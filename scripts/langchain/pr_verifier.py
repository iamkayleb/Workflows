#!/usr/bin/env python3
"""
Evaluate pull requests with an LLM-backed rubric.

Run with:
    python scripts/langchain/pr_verifier.py --context-file verifier-context.md --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PR_EVALUATION_PROMPT = """
You are reviewing a pull request to ensure it meets the documented acceptance criteria.

PR Context:
{context}

PR Diff (summary or full):
{diff}

Provide an evaluation that covers:
- correctness
- completeness
- quality
- testing
- risks

Respond with a concise report and a clear verdict (PASS, CONCERNS, FAIL).
""".strip()

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "pr_evaluation.md"


@dataclass
class PrEvaluationOutput:
    content: str
    provider_used: str | None
    used_llm: bool
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "provider_used": self.provider_used,
            "used_llm": self.used_llm,
            "error": self.error,
        }


def _load_prompt() -> str:
    if PROMPT_PATH.is_file():
        return PROMPT_PATH.read_text(encoding="utf-8").strip()
    return PR_EVALUATION_PROMPT


def _get_llm_client() -> tuple[object, str] | None:
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        return None

    github_token = os.environ.get("GITHUB_TOKEN")
    openai_token = os.environ.get("OPENAI_API_KEY")
    if not github_token and not openai_token:
        return None

    from tools.llm_provider import DEFAULT_MODEL, GITHUB_MODELS_BASE_URL

    if github_token:
        return (
            ChatOpenAI(
                model=DEFAULT_MODEL,
                base_url=GITHUB_MODELS_BASE_URL,
                api_key=github_token,
                temperature=0.1,
            ),
            "github-models",
        )
    return (
        ChatOpenAI(
            model=DEFAULT_MODEL,
            api_key=openai_token,
            temperature=0.1,
        ),
        "openai",
    )


def _prepare_prompt(context: str, diff: str | None) -> str:
    prompt = _load_prompt()
    diff_block = diff.strip() if diff and diff.strip() else "(diff unavailable)"
    context_block = context.strip() if context and context.strip() else "(context unavailable)"
    return prompt.format(context=context_block, diff=diff_block)


def _fallback_evaluation(message: str) -> PrEvaluationOutput:
    content = (
        "Verdict: CONCERNS\n\n"
        "LLM evaluation could not run. "
        "Review the PR manually or re-run once LLM credentials are available.\n\n"
        f"Details: {message}"
    )
    return PrEvaluationOutput(content=content, provider_used=None, used_llm=False, error=message)


def evaluate_pr(context: str, diff: str | None = None) -> PrEvaluationOutput:
    resolved = _get_llm_client()
    if resolved is None:
        return _fallback_evaluation("LLM client unavailable (missing credentials or dependency).")

    client, provider = resolved
    prompt = _prepare_prompt(context, diff)
    try:
        response = client.invoke(prompt)
    except Exception as exc:  # pragma: no cover - exercised in integration
        return _fallback_evaluation(f"LLM invocation failed: {exc}")

    content = getattr(response, "content", None) or str(response)
    return PrEvaluationOutput(content=content, provider_used=provider, used_llm=True)


def _load_text(path: str | None) -> str:
    if path:
        return Path(path).read_text(encoding="utf-8")
    return sys.stdin.read()


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate PRs against acceptance criteria.")
    parser.add_argument("--context-file", help="Path to verifier context markdown.")
    parser.add_argument("--diff-file", help="Path to PR diff or summary.")
    parser.add_argument("--output-file", help="Path to write evaluation output.")
    parser.add_argument("--json", action="store_true", help="Emit JSON payload to stdout.")
    args = parser.parse_args()

    context = _load_text(args.context_file)
    diff = _load_text(args.diff_file) if args.diff_file else None
    result = evaluate_pr(context, diff=diff)

    if args.output_file:
        Path(args.output_file).write_text(result.content, encoding="utf-8")

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=True))
    else:
        print(result.content)


if __name__ == "__main__":
    main()
