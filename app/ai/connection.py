"""A minimal, provider-agnostic connection check for saved AI settings."""

from __future__ import annotations

from typing import Any

import openai

from app.ai.client import ModelError
from app.config import Settings


def check_connection(settings: Settings, client: Any | None = None) -> None:
    """Make one one-token chat request, raising a readable ``ModelError``.

    A chat completion is used instead of a provider-specific models endpoint so
    this works across the OpenAI-compatible providers supported by IncidentIQ.
    A successful return means the configured endpoint, key and model accepted
    a real request.  The response text is deliberately ignored.
    """
    if not settings.is_configured:
        raise ModelError("No API key is configured yet.")

    try:
        transport = client or openai.OpenAI(
            base_url=settings.ai_base_url,
            api_key=settings.ai_api_key,
        )
        transport.chat.completions.create(
            model=settings.ai_model,
            messages=[{"role": "user", "content": "Reply OK."}],
            max_tokens=1,
            stream=False,
        )
    except openai.AuthenticationError as exc:
        raise ModelError(
            "The API key was rejected (401). Check the saved key. Provider said: "
            + _provider_message(exc, settings.ai_api_key)
        ) from exc
    except openai.PermissionDeniedError as exc:
        raise ModelError(
            "The provider refused the request (403). The API may be disabled for "
            "this key, restricted, unavailable in this region, or the model may "
            "not be allowed. Provider said: "
            + _provider_message(exc, settings.ai_api_key)
        ) from exc
    except openai.NotFoundError as exc:
        raise ModelError(
            "Model or endpoint not found (404). Check the model and base URL. "
            "Provider said: " + _provider_message(exc, settings.ai_api_key)
        ) from exc
    except openai.RateLimitError as exc:
        raise ModelError(
            "The provider rate-limited the check (429). Wait and try again. "
            "Provider said: " + _provider_message(exc, settings.ai_api_key)
        ) from exc
    except openai.APIConnectionError as exc:
        raise ModelError(
            "Could not reach the AI endpoint. Check the base URL and network."
        ) from exc
    except openai.BadRequestError as exc:
        raise ModelError(
            "The provider rejected the check (400). Check the model and base URL. "
            "Provider said: " + _provider_message(exc, settings.ai_api_key)
        ) from exc
    except openai.APIStatusError as exc:
        raise ModelError(
            f"AI endpoint error {exc.status_code}: "
            + _provider_message(exc, settings.ai_api_key)
        ) from exc
    except Exception as exc:  # noqa: BLE001 - surface a useful UI error
        raise ModelError(
            "Connection check failed: " + _provider_message(exc, settings.ai_api_key)
        ) from exc


def _provider_message(exc: Exception, api_key: str) -> str:
    """Return provider detail with the write-only API key defensively redacted."""
    message = getattr(exc, "message", None) or str(exc) or "(no detail returned)"
    if api_key:
        message = message.replace(api_key, "[redacted]")
    return message
