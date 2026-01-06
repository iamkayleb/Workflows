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
import re
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

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

Respond in JSON with:
{
  "verdict": "PASS | CONCERNS | FAIL",
  "scores": {
    "correctness": 0-10,
    "completeness": 0-10,
    "quality": 0-10,
    "testing": 0-10,
    "risks": 0-10
  },
  "concerns": ["..."],
  "summary": "concise report"
}
""".strip()

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "pr_evaluation.md"


class EvaluationScores(BaseModel):
    correctness: float = Field(ge=0, le=10)
    completeness: float = Field(ge=0, le=10)
    quality: float = Field(ge=0, le=10)
    testing: float = Field(ge=0, le=10)
    risks: float = Field(ge=0, le=10)


class EvaluationResult(BaseModel):
    verdict: Literal["PASS", "CONCERNS", "FAIL"]
    scores: EvaluationScores | None = None
    concerns: list[str] = Field(default_factory=list)
    summary: str | None = None
    provider_used: str | None = None
    used_llm: bool = False
    raw_content: str | None = None
    error: str | None = None


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


def _fallback_evaluation(message: str) -> EvaluationResult:
    return EvaluationResult(
        verdict="CONCERNS",
        scores=None,
        concerns=["LLM evaluation could not run."],
        summary="Review the PR manually or re-run once LLM credentials are available.",
        provider_used=None,
        used_llm=False,
        error=message,
    )


def _extract_json_block(text: str) -> str | None:
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def _parse_verdict(text: str) -> Literal["PASS", "CONCERNS", "FAIL"]:
    match = re.search(r"\b(PASS|CONCERNS|FAIL)\b", text, re.IGNORECASE)
    if match:
        return match.group(1).upper()  # type: ignore[return-value]
    return "CONCERNS"


def _parse_llm_response(content: str, provider: str) -> EvaluationResult:
    json_block = _extract_json_block(content)
    if json_block:
        try:
            payload = json.loads(json_block)
            return EvaluationResult.model_validate(
                {
                    **payload,
                    "provider_used": provider,
                    "used_llm": True,
                    "raw_content": content,
                }
            )
        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
            return EvaluationResult(
                verdict=_parse_verdict(content),
                scores=None,
                concerns=[],
                summary=content,
                provider_used=provider,
                used_llm=True,
                raw_content=content,
                error=f"Failed to parse JSON response: {exc}",
            )

    return EvaluationResult(
        verdict=_parse_verdict(content),
        scores=None,
        concerns=[],
        summary=content,
        provider_used=provider,
        used_llm=True,
        raw_content=content,
    )


def evaluate_pr(context: str, diff: str | None = None) -> EvaluationResult:
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
    return _parse_llm_response(content, provider)


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

    output_text = result.raw_content or result.summary or ""

    if args.output_file:
        Path(args.output_file).write_text(output_text, encoding="utf-8")

    if args.json:
        print(json.dumps(result.model_dump(), ensure_ascii=True))
    else:
        print(output_text)


if __name__ == "__main__":
    main()
