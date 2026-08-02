"""Stage 2: timeline reconstruction."""

from __future__ import annotations

from app.ai import prompts
from app.ai.client import AIClient
from app.schemas import SummaryResult, TimelineResult

STAGE = "timeline"


def run(
    client: AIClient, evidence_block: str, summary: SummaryResult | None
) -> TimelineResult:
    context = prompts.summary_context(summary) if summary else ""
    return client.complete_structured(
        stage=STAGE,
        system_prompt=prompts.SYSTEM_PROMPT,
        evidence_block=evidence_block,
        prior_context=context,
        instruction=prompts.TIMELINE_INSTRUCTION,
        schema_model=TimelineResult,
    )
