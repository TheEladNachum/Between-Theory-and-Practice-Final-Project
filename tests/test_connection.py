"""The browser connection check uses a fake OpenAI-compatible transport."""

from __future__ import annotations

from types import SimpleNamespace

import openai
import pytest

from app.ai.client import ModelError
from app.ai.connection import check_connection
from app.config import Settings


class FakeCompletions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(choices=[])


def configured_settings(key: str = "test-secret") -> Settings:
    return Settings(
        ai_base_url="https://provider.example/v1",
        ai_api_key=key,
        ai_model="small-model",
    )


def test_connection_check_makes_only_a_one_token_request():
    completions = FakeCompletions()
    transport = SimpleNamespace(chat=SimpleNamespace(completions=completions))

    result = check_connection(configured_settings(), client=transport)

    assert result is None
    assert len(completions.calls) == 1
    request = completions.calls[0]
    assert request["model"] == "small-model"
    assert request["max_tokens"] == 1
    assert request["stream"] is False


def test_connection_error_is_readable_and_redacts_the_key():
    secret = "must-not-leak"

    class RejectedCompletions:
        def create(self, **_kwargs):
            raise openai.AuthenticationError(
                f"rejected credential {secret}",
                response=SimpleNamespace(status_code=401, request=None, headers={}),
                body=None,
            )

    transport = SimpleNamespace(
        chat=SimpleNamespace(completions=RejectedCompletions())
    )

    with pytest.raises(ModelError) as exc_info:
        check_connection(configured_settings(secret), client=transport)

    message = str(exc_info.value)
    assert "401" in message
    assert "rejected" in message
    assert secret not in message
    assert "[redacted]" in message
