"""The Claude client wrapper.

Design notes that matter for the report:

* **One shared prefix, six stages.** Every analysis stage sends the same system
  prompt and the same evidence block, then appends a stage-specific
  instruction. Because the API caches on an exact prefix match, and because the
  render order is system -> messages, keeping the constant parts first lets all
  six stages reuse one cached copy of the evidence instead of re-reading it six
  times. (The cache only engages above a minimum prefix size, so short
  incidents simply will not hit it - that is expected, not a bug.)

* **Structured outputs, not "please reply in JSON".** Each stage passes a JSON
  schema derived from the Pydantic model it expects back. The model is
  constrained to that shape, which removes a whole class of parsing failures
  and, more importantly, removes the temptation to accept a prose answer that
  merely looks well-organised.

* **Adaptive thinking.** The model decides how much to reason per stage rather
  than being given a fixed budget; `effort` sets the ceiling on that trade-off.
"""

from __future__ import annotations

import logging
from typing import Type, TypeVar

import anthropic
from pydantic import BaseModel

from app.ai.parsing import ParseError, parse_into, strict_schema
from app.config import Settings

log = logging.getLogger("incidentiq.ai")

T = TypeVar("T", bound=BaseModel)


class ModelError(RuntimeError):
    """Any failure that came from the model or the transport."""


class ClaudeClient:
    """A thin, stage-oriented wrapper over the Messages API."""

    def __init__(self, settings: Settings) -> None:
        if not settings.is_configured:
            raise ModelError(
                "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key."
            )
        self._settings = settings
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

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

        The content blocks are ordered constant-first so the cache breakpoint
        sits at the end of the evidence, which is the last thing shared by
        every stage.
        """
        content: list[dict] = [
            {
                "type": "text",
                "text": evidence_block,
                # Everything up to and including this block is identical across
                # stages, so this is where the reusable prefix ends.
                "cache_control": {"type": "ephemeral"},
            }
        ]
        if prior_context:
            content.append({"type": "text", "text": prior_context})
        content.append({"type": "text", "text": instruction})

        if self._settings.log_prompts:
            log.info("--- stage %s ---\n%s\n%s", stage, instruction, prior_context[:2000])

        try:
            with self._client.messages.stream(
                model=self._settings.anthropic_model,
                max_tokens=self._settings.max_output_tokens,
                system=[{"type": "text", "text": system_prompt}],
                messages=[{"role": "user", "content": content}],
                thinking={"type": "adaptive"},
                output_config={
                    "effort": self._settings.effort,
                    "format": {
                        "type": "json_schema",
                        "schema": strict_schema(schema_model),
                    },
                },
            ) as stream:
                message = stream.get_final_message()
        except anthropic.AuthenticationError as exc:
            raise ModelError("The API key was rejected. Check ANTHROPIC_API_KEY in .env.") from exc
        except anthropic.RateLimitError as exc:
            raise ModelError("Rate limited by the API. Wait a moment and try again.") from exc
        except anthropic.APIConnectionError as exc:
            raise ModelError("Could not reach the API. Check your network connection.") from exc
        except anthropic.APIStatusError as exc:
            raise ModelError(f"API error {exc.status_code}: {exc.message}") from exc

        return self._to_model(message, schema_model, stage)

    # ------------------------------------------------------------------ #

    def _to_model(self, message, schema_model: Type[T], stage: str) -> T:
        """Validate the response, converting every failure mode into ModelError."""
        # A refusal returns HTTP 200 with an empty or partial body, so this has
        # to be checked before touching `content`.
        if message.stop_reason == "refusal":
            detail = getattr(message.stop_details, "explanation", None) or "no explanation given"
            raise ModelError(f"The model declined to answer stage '{stage}' ({detail}).")

        if message.stop_reason == "max_tokens":
            raise ModelError(
                f"Stage '{stage}' hit the output limit and was cut off. "
                f"Raise MAX_OUTPUT_TOKENS in .env, or trim the evidence."
            )

        text = "".join(block.text for block in message.content if block.type == "text")
        if not text.strip():
            raise ModelError(f"Stage '{stage}' returned an empty response.")

        try:
            return parse_into(schema_model, text)
        except ParseError as exc:
            raise ModelError(f"Stage '{stage}': {exc}") from exc
