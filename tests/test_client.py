"""Tests for the provider-agnostic client and its schema-degradation fallback.

No network and no key are needed: a fake OpenAI-compatible transport is injected
into AIClient, so the request-building, the fallback path, and the error mapping
can all be exercised in isolation.
"""

from __future__ import annotations

from types import SimpleNamespace

import openai
import pytest

from app.ai.client import AIClient, ModelError
from app.ai.parsing import schema_hint, strict_schema
from app.config import Settings
from app.schemas import SummaryResult

VALID_JSON = (
    '{"summary": "Checkout failed.",'
    ' "facts": [{"statement": "500s seen",'
    '   "evidence": [{"source": "logs", "quote": "POST /checkout 500"}]}],'
    ' "assumptions": []}'
)


def settings() -> Settings:
    # Explicit values so the test does not depend on the environment or a .env.
    return Settings(ai_base_url="https://example.test/v1", ai_api_key="k", ai_model="m")


# --------------------------------------------------------------------------- #
# A fake transport shaped like openai.OpenAI().chat.completions
# --------------------------------------------------------------------------- #


def _chunk(content: str | None, finish_reason: str | None = None):
    delta = SimpleNamespace(content=content)
    choice = SimpleNamespace(delta=delta, finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice])


def _stream(text: str, finish_reason: str = "stop"):
    # One content chunk, then a final chunk carrying the finish reason.
    yield _chunk(text)
    yield _chunk(None, finish_reason)


class FakeCompletions:
    def __init__(self, script):
        """`script` is a list of callables; each handles one create() call."""
        self._script = list(script)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        handler = self._script.pop(0)
        return handler(kwargs)


class FakeClient:
    def __init__(self, script):
        self.chat = SimpleNamespace(completions=FakeCompletions(script))


def make_client(script) -> AIClient:
    fake = FakeClient(script)
    client = AIClient(settings(), client=fake)
    return client, fake


def schema_rejection(_kwargs):
    # A 400 whose message names the response format triggers the downgrade.
    raise openai.BadRequestError(
        "Invalid 'response_format': json_schema is not supported",
        response=SimpleNamespace(status_code=400, request=None, headers={}),
        body=None,
    )


# --------------------------------------------------------------------------- #
# Construction
# --------------------------------------------------------------------------- #


def test_missing_config_raises_model_error():
    with pytest.raises(ModelError):
        AIClient(Settings(ai_base_url="", ai_api_key=""), client=object())


# --------------------------------------------------------------------------- #
# Happy path - schema mode
# --------------------------------------------------------------------------- #


def test_schema_mode_returns_parsed_model():
    client, fake = make_client([lambda k: _stream(VALID_JSON)])
    result = client.complete_structured(
        stage="summary",
        system_prompt="SYS",
        evidence_block="EVID",
        instruction="INSTR",
        schema_model=SummaryResult,
    )
    assert isinstance(result, SummaryResult)
    assert result.summary == "Checkout failed."

    # It asked for a formal json_schema, once.
    assert len(fake.chat.completions.calls) == 1
    assert fake.chat.completions.calls[0]["response_format"]["type"] == "json_schema"


def test_request_is_assembled_constant_first():
    client, fake = make_client([lambda k: _stream(VALID_JSON)])
    client.complete_structured(
        stage="summary", system_prompt="SYS", evidence_block="EVID",
        instruction="INSTR", schema_model=SummaryResult, prior_context="PRIOR",
    )
    messages = fake.chat.completions.calls[0]["messages"]
    assert messages[0]["role"] == "system" and messages[0]["content"] == "SYS"
    user = messages[1]["content"]
    # Order: evidence, then prior context, then the instruction.
    assert user.index("EVID") < user.index("PRIOR") < user.index("INSTR")


# --------------------------------------------------------------------------- #
# Fallback - schema rejected, retry in json_object mode
# --------------------------------------------------------------------------- #


def test_schema_rejection_downgrades_to_json_mode():
    client, fake = make_client([schema_rejection, lambda k: _stream(VALID_JSON)])
    result = client.complete_structured(
        stage="summary", system_prompt="SYS", evidence_block="EVID",
        instruction="INSTR", schema_model=SummaryResult,
    )
    assert isinstance(result, SummaryResult)

    calls = fake.chat.completions.calls
    assert len(calls) == 2
    assert calls[0]["response_format"]["type"] == "json_schema"   # first attempt
    assert calls[1]["response_format"]["type"] == "json_object"   # downgraded
    # The schema shape was moved into the prompt for the fallback.
    assert "JSON schema" in calls[1]["messages"][1]["content"]


def test_json_mode_still_validates_output():
    # If the downgraded call returns malformed JSON, it must still raise cleanly.
    client, _ = make_client([schema_rejection, lambda k: _stream("not json at all")])
    with pytest.raises(ModelError):
        client.complete_structured(
            stage="summary", system_prompt="SYS", evidence_block="EVID",
            instruction="INSTR", schema_model=SummaryResult,
        )


# --------------------------------------------------------------------------- #
# Truncation and empty output
# --------------------------------------------------------------------------- #


def test_truncated_output_raises_with_max_tokens_hint():
    client, _ = make_client([lambda k: _stream(VALID_JSON, finish_reason="length")])
    with pytest.raises(ModelError) as exc:
        client.complete_structured(
            stage="summary", system_prompt="SYS", evidence_block="EVID",
            instruction="INSTR", schema_model=SummaryResult,
        )
    assert "MAX_OUTPUT_TOKENS" in str(exc.value)


def test_empty_output_raises():
    client, _ = make_client([lambda k: _stream("   ")])
    with pytest.raises(ModelError):
        client.complete_structured(
            stage="summary", system_prompt="SYS", evidence_block="EVID",
            instruction="INSTR", schema_model=SummaryResult,
        )


# --------------------------------------------------------------------------- #
# Error mapping
# --------------------------------------------------------------------------- #


def test_auth_error_maps_to_readable_message():
    def raise_auth(_k):
        raise openai.AuthenticationError(
            "bad key",
            response=SimpleNamespace(status_code=401, request=None, headers={}),
            body=None,
        )

    client, _ = make_client([raise_auth])
    with pytest.raises(ModelError) as exc:
        client.complete_structured(
            stage="summary", system_prompt="SYS", evidence_block="EVID",
            instruction="INSTR", schema_model=SummaryResult,
        )
    assert "AI_API_KEY" in str(exc.value)


# --------------------------------------------------------------------------- #
# schema_hint helper
# --------------------------------------------------------------------------- #


def test_schema_hint_contains_field_names():
    hint = schema_hint(SummaryResult)
    assert "summary" in hint and "assumptions" in hint
    assert "JSON schema" in hint


def test_strict_schema_is_closed():
    schema = strict_schema(SummaryResult)
    assert schema["additionalProperties"] is False
