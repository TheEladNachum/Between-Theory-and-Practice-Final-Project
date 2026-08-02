"""Tests for schema generation and model-output parsing."""

from __future__ import annotations

import pytest

from app.ai.parsing import ParseError, extract_json, parse_into, strict_schema
from app.schemas import ActionsResult, HypothesesResult, SummaryResult


def walk_objects(node):
    """Yield every JSON-schema object node in a schema."""
    if isinstance(node, dict):
        if node.get("type") == "object" and "properties" in node:
            yield node
        for value in node.values():
            yield from walk_objects(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk_objects(item)


# --- schema shaping ---------------------------------------------------------


@pytest.mark.parametrize("model", [SummaryResult, HypothesesResult, ActionsResult])
def test_every_object_is_closed(model):
    for obj in walk_objects(strict_schema(model)):
        assert obj["additionalProperties"] is False


@pytest.mark.parametrize("model", [SummaryResult, HypothesesResult, ActionsResult])
def test_every_property_is_required(model):
    # Structured outputs reject a schema where a declared property is optional.
    for obj in walk_objects(strict_schema(model)):
        assert set(obj["required"]) == set(obj["properties"])


def test_unsupported_keywords_are_stripped():
    schema = repr(strict_schema(ActionsResult))
    for keyword in ("'default'", "'minLength'", "'maxItems'", "'pattern'"):
        assert keyword not in schema


def test_optional_field_becomes_nullable_union():
    action = strict_schema(ActionsResult)["$defs"]["Action"]
    linked = action["properties"]["linked_hypothesis"]
    types = {entry.get("type") for entry in linked["anyOf"]}
    assert types == {"string", "null"}


# --- JSON extraction --------------------------------------------------------


def test_extract_bare_json():
    assert extract_json('{"a": 1}') == '{"a": 1}'


def test_extract_from_code_fence():
    assert extract_json('```json\n{"a": 1}\n```') == '{"a": 1}'


def test_extract_ignores_surrounding_prose():
    text = 'Here is the result:\n{"a": 1}\nHope that helps.'
    assert extract_json(text) == '{"a": 1}'


def test_extract_raises_when_no_object_present():
    with pytest.raises(ParseError):
        extract_json("I could not complete this task.")


# --- validation -------------------------------------------------------------


def test_parse_into_builds_the_model():
    payload = """
    {"summary": "Checkout failed.",
     "facts": [{"statement": "500s observed",
                "evidence": [{"source": "logs", "quote": "POST /checkout 500"}]}],
     "assumptions": []}
    """
    result = parse_into(SummaryResult, payload)
    assert result.summary == "Checkout failed."
    assert result.facts[0].evidence[0].source == "logs"


def test_parse_into_reports_missing_fields_readably():
    with pytest.raises(ParseError) as exc:
        parse_into(SummaryResult, '{"summary": "x"}')
    assert "did not match the expected shape" in str(exc.value)


def test_parse_into_rejects_malformed_json():
    with pytest.raises(ParseError) as exc:
        parse_into(SummaryResult, "{not json at all")
    assert "malformed JSON" in str(exc.value) or "No JSON object" in str(exc.value)
