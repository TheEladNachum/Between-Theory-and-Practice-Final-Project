"""Turning Pydantic models into JSON schemas, and model text back into Pydantic
models.

Different OpenAI-compatible providers accept different subsets of JSON Schema.
Providers that support structured output ("json_schema" response format)
require every object to be closed (`additionalProperties: false`) with all
properties listed in `required`; Pydantic does not generate schemas in that
shape, so `strict_schema` adapts them. Providers that only support a plain
"json_object" mode get the schema described in the prompt instead, via
`schema_hint`.

Doing all of this here means the schema, the prompt hint, and the parsing code
can never drift apart - they are all derived from the same Pydantic model.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Type, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

# Keywords the structured-output validator rejects. Pydantic emits several of
# them from Field(...) metadata, so they are stripped rather than avoided.
UNSUPPORTED_KEYWORDS = (
    "default",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "minLength",
    "maxLength",
    "minItems",
    "maxItems",
    "pattern",
    "multipleOf",
    "examples",
)


class ParseError(RuntimeError):
    """Raised when model output cannot be coerced into the expected schema."""


def _tighten(node: Any) -> Any:
    """Recursively close every object and drop unsupported keywords."""
    if isinstance(node, list):
        return [_tighten(item) for item in node]
    if not isinstance(node, dict):
        return node

    cleaned = {k: _tighten(v) for k, v in node.items() if k not in UNSUPPORTED_KEYWORDS}

    if cleaned.get("type") == "object" and "properties" in cleaned:
        cleaned["additionalProperties"] = False
        # Structured outputs require every declared property to be required.
        # Optionality is expressed with an explicit null in an anyOf instead.
        cleaned["required"] = list(cleaned["properties"].keys())

    return cleaned


def strict_schema(model: Type[BaseModel]) -> Dict[str, Any]:
    """A JSON schema for `model` that the structured-output API will accept."""
    return _tighten(model.model_json_schema())


def schema_hint(model: Type[BaseModel]) -> str:
    """A compact rendering of `model`'s schema, for embedding in a prompt.

    Used as the fallback when a provider does not accept a formal
    `json_schema` response format but can still be steered with a plain
    `json_object` mode. The model is shown the shape it must produce rather
    than having it enforced by the API.
    """
    schema = strict_schema(model)
    return (
        "Return a single JSON object and nothing else. It must match this "
        "JSON schema exactly (same field names, same nesting, no extra "
        "fields):\n"
        + json.dumps(schema, ensure_ascii=False, indent=2)
    )


def extract_json(text: str) -> str:
    """Pull the JSON object out of a model response.

    With structured outputs the response is already bare JSON, so this is a
    safety net for the case where a stage falls back to free-form output - or
    where a model wraps its answer in a ```json fence out of habit.
    """
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.DOTALL)
    if fenced:
        return fenced.group(1)

    first, last = stripped.find("{"), stripped.rfind("}")
    if first != -1 and last > first:
        return stripped[first : last + 1]

    raise ParseError("No JSON object found in the model response.")


def parse_into(model: Type[T], text: str) -> T:
    """Validate model output against `model`, with a readable error on failure."""
    try:
        payload = json.loads(extract_json(text))
    except json.JSONDecodeError as exc:
        raise ParseError(f"Model returned malformed JSON: {exc}") from exc

    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        # Report only the first few problems - the full Pydantic dump is far too
        # long to be useful in a UI warning strip.
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}"
            for err in exc.errors()[:3]
        )
        raise ParseError(f"Model output did not match the expected shape ({problems}).") from exc
