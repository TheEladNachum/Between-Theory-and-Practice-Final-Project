"""The AI client.

`AIClient` talks to any OpenAI-compatible chat endpoint. The provider is chosen
entirely by `AI_BASE_URL`, `AI_API_KEY` and `AI_MODEL` in `.env` - this class
does not know or care whether it is speaking to Gemini, Groq, OpenRouter, a
local Ollama model, or OpenAI. The OpenAI SDK is used only as a convenient
generic transport for that wire format; the project does not depend on OpenAI.

Design notes that matter for the report:

* **One shared prefix, six stages.** Every analysis stage sends the same system
  prompt, then a user message that begins with the same evidence block. Keeping
  the constant parts first lets a provider that caches identical prefixes reuse
  them - but nothing here depends on that, because prefix caching is a
  provider-specific optimisation and this client is provider-agnostic.

* **Structured output, with graceful degradation.** Each stage asks for a JSON
  object matching a schema derived from the Pydantic model it expects back. The
  request first uses the provider's formal `json_schema` response format. If the
  provider rejects that schema, the client retries once in plain `json_object`
  mode with the schema described in the prompt instead. Either way the response
  is validated by `parse_into`, so a valid Pydantic model is what comes back.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar

import openai
from pydantic import BaseModel

from app.ai.parsing import ParseError, parse_into, schema_hint, strict_schema
from app.config import Settings

log = logging.getLogger("incidentiq.ai")

T = TypeVar("T", bound=BaseModel)


class ModelError(RuntimeError):
    """Any failure that came from the model or the transport."""


class _SchemaUnsupported(Exception):
    """Internal: the provider rejected the formal json_schema response format.

    Not a user-facing error - it triggers the one-step downgrade to plain JSON
    mode rather than being surfaced.
    """


# Logged once per process so the user can see which output mode a provider
# actually accepted, without spamming a line per stage.
_downgrade_logged = False


class AIClient:
    """A thin, stage-oriented wrapper over an OpenAI-compatible chat endpoint."""

    def __init__(self, settings: Settings, client: Optional[Any] = None) -> None:
        if not settings.is_configured:
            raise ModelError(
                "AI_API_KEY and AI_BASE_URL must both be set. Copy .env.example "
                "to .env and fill them in."
            )
        self._settings = settings
        # `client` is injectable so the fallback logic can be tested without a
        # network. In normal use it is created here from .env.
        self._client = client or openai.OpenAI(
            base_url=settings.ai_base_url,
            api_key=settings.ai_api_key,
        )

    # ------------------------------------------------------------------ #

    def complete_structured(
        self,
        *,
        stage: str,
        system_prompt: str,
        evidence_block: str,
        instruction: str,
        schema_model: Type[T],
        prior_context: str = "",
    ) -> T:
        """Run one analysis stage and return a validated `schema_model`.

        The user turn is assembled constant-first: the evidence block (shared by
        every stage), then any prior-stage context, then this stage's
        instruction.
        """
        user_parts = [evidence_block]
        if prior_context:
            user_parts.append(prior_context)
        user_parts.append(instruction)
        user_message = "\n\n".join(user_parts)

        if self._settings.log_prompts:
            log.info("--- stage %s ---\n%s\n%s", stage, instruction, prior_context[:2000])

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        # Attempt 1: formal structured output.
        try:
            text, truncated = self._call(
                stage,
                messages,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": schema_model.__name__,
                        "schema": strict_schema(schema_model),
                        "strict": True,
                    },
                },
            )
        except _SchemaUnsupported:
            # Attempt 2: the provider cannot enforce the schema - describe it in
            # the prompt and ask for a plain JSON object instead.
            self._note_downgrade(stage)
            hinted = [
                messages[0],
                {"role": "user", "content": user_message + "\n\n" + schema_hint(schema_model)},
            ]
            text, truncated = self._call(
                stage, hinted, response_format={"type": "json_object"}
            )

        if truncated:
            raise ModelError(
                f"Stage '{stage}' hit the output limit and was cut off. "
                f"Raise MAX_OUTPUT_TOKENS in .env, or trim the evidence."
            )
        if not text.strip():
            raise ModelError(f"Stage '{stage}' returned an empty response.")

        try:
            return parse_into(schema_model, text)
        except ParseError as exc:
            raise ModelError(f"Stage '{stage}': {exc}") from exc

    # ------------------------------------------------------------------ #

    def _call(
        self, stage: str, messages: List[Dict[str, str]], response_format: Dict[str, Any]
    ) -> Tuple[str, bool]:
        """Make one streaming request. Returns (text, was_truncated).

        Raises `_SchemaUnsupported` if the provider rejected the response
        format, and `ModelError` for every other failure - mapped to wording
        the user can act on.
        """
        try:
            stream = self._client.chat.completions.create(
                model=self._settings.ai_model,
                messages=messages,
                response_format=response_format,
                max_tokens=self._settings.max_output_tokens,
                stream=True,
            )
            chunks: List[str] = []
            finish_reason: Optional[str] = None
            for event in stream:
                if not event.choices:
                    continue
                choice = event.choices[0]
                piece = getattr(choice.delta, "content", None)
                if piece:
                    chunks.append(piece)
                if choice.finish_reason:
                    finish_reason = choice.finish_reason
            return "".join(chunks), finish_reason == "length"

        except openai.BadRequestError as exc:
            # A 400 that mentions the response format almost always means the
            # provider does not support formal json_schema for this schema.
            if response_format.get("type") == "json_schema" and _is_schema_error(exc):
                raise _SchemaUnsupported() from exc
            raise ModelError(f"Stage '{stage}': the request was rejected - {exc}") from exc
        except openai.AuthenticationError as exc:
            raise ModelError(
                f"The API key was rejected (401). Check AI_API_KEY in .env. "
                f"Provider said: {_provider_message(exc)}"
            ) from exc
        except openai.PermissionDeniedError as exc:
            # 403 has several causes, so surface what the provider actually said
            # rather than guessing - the message usually names the fix (enable
            # the API for this key, a key restriction, an unsupported region, or
            # a model this key cannot use).
            raise ModelError(
                f"The provider refused the request (403). Common causes: the "
                f"provider's API is not enabled for this key, the key is "
                f"restricted, your region is not supported, or AI_MODEL is not "
                f"available to this key. Provider said: {_provider_message(exc)}"
            ) from exc
        except openai.NotFoundError as exc:
            raise ModelError(
                f"Model or endpoint not found (404). Check AI_MODEL and "
                f"AI_BASE_URL in .env. Provider said: {_provider_message(exc)}"
            ) from exc
        except openai.RateLimitError as exc:
            raise ModelError(
                f"Rate limited by the provider (429). Wait and try again. "
                f"Provider said: {_provider_message(exc)}"
            ) from exc
        except openai.APIConnectionError as exc:
            raise ModelError(
                "Could not reach the AI endpoint. Check AI_BASE_URL and your network."
            ) from exc
        except openai.APIStatusError as exc:
            raise ModelError(
                f"AI endpoint error {exc.status_code}: {_provider_message(exc)}"
            ) from exc

    def _note_downgrade(self, stage: str) -> None:
        global _downgrade_logged
        if not _downgrade_logged:
            log.info(
                "provider %s does not accept json_schema; using json_object mode "
                "with an in-prompt schema (first seen at stage '%s')",
                self._settings.provider_name,
                stage,
            )
            _downgrade_logged = True


def _provider_message(exc: Exception) -> str:
    """The provider's own error text, so the user sees the real reason.

    The OpenAI SDK exposes a parsed `.message`; fall back to the string form if
    a provider returned something the SDK could not parse.
    """
    message = getattr(exc, "message", None)
    return message or str(exc) or "(no detail returned)"


def _is_schema_error(exc: Exception) -> bool:
    """Heuristic: does this 400 look like a rejection of the response format?"""
    text = str(exc).lower()
    needles = ("response_format", "json_schema", "schema", "response format")
    return any(needle in text for needle in needles)
