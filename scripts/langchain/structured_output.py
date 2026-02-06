from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


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


def parse_structured_output(
    content: str,
    model: type[T],
    *,
    repair: Callable[[str, str, str], str | None] | None,
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
        if repair is None:
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
