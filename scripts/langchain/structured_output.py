from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


DEFAULT_REPAIR_PROMPT = """
The previous response did not match the required JSON schema.

Schema:
{schema_json}

Validation errors:
{validation_errors}

Original response:
{raw_response}

Return ONLY valid JSON that matches the schema with no surrounding text.
""".strip()


@dataclass(frozen=True)
class StructuredOutputResult(Generic[T]):
    payload: T | None
    raw_content: str | None
    error_stage: str | None
    error_detail: str | None


def schema_json(model: type[BaseModel]) -> str:
    return json.dumps(model.model_json_schema(), ensure_ascii=True, indent=2)


def format_validation_errors(exc: ValidationError) -> str:
    return json.dumps(exc.errors(), ensure_ascii=True, indent=2)


def build_repair_prompt(
    schema_json: str,
    validation_errors: str,
    raw_response: str,
    *,
    template: str = DEFAULT_REPAIR_PROMPT,
) -> str:
    return template.format(
        schema_json=schema_json,
        validation_errors=validation_errors,
        raw_response=raw_response,
    )


def build_repair_callback(
    client: Any, *, template: str = DEFAULT_REPAIR_PROMPT
) -> Callable[[str, str, str], str | None]:
    def _repair(schema_json: str, validation_errors: str, raw_response: str) -> str | None:
        try:
            repair_prompt = build_repair_prompt(
                schema_json=schema_json,
                validation_errors=validation_errors,
                raw_response=raw_response,
                template=template,
            )
            response = client.invoke(repair_prompt)
        except Exception:
            return None
        return getattr(response, "content", None) or str(response)

    return _repair


def parse_structured_output(
    content: str,
    model: type[T],
    *,
    repair: Callable[[str, str, str], str | None] | None,
    max_repair_attempts: int = 1,
) -> StructuredOutputResult[T]:
    try:
        payload = model.model_validate_json(content)
        return StructuredOutputResult(
            payload=payload,
            raw_content=content,
            error_stage=None,
            error_detail=None,
        )
    except ValidationError as exc:
        error_detail = format_validation_errors(exc)
        attempts = max(0, min(int(max_repair_attempts), 1))
        if repair is None or attempts == 0:
            return StructuredOutputResult(
                payload=None,
                raw_content=None,
                error_stage="validation",
                error_detail=error_detail,
            )
        repaired = repair(schema_json(model), error_detail, content)
        if not repaired:
            return StructuredOutputResult(
                payload=None,
                raw_content=None,
                error_stage="repair_unavailable",
                error_detail=error_detail,
            )
        try:
            payload = model.model_validate_json(repaired)
            return StructuredOutputResult(
                payload=payload,
                raw_content=repaired,
                error_stage=None,
                error_detail=None,
            )
        except ValidationError as repair_exc:
            repair_detail = format_validation_errors(repair_exc)
            return StructuredOutputResult(
                payload=None,
                raw_content=None,
                error_stage="repair_validation",
                error_detail=repair_detail,
            )
