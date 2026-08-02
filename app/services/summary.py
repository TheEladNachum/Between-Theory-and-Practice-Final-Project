"""Stage 1: incident summary, plus the facts/assumptions split."""

from __future__ import annotations

from app.ai import prompts
from app.ai.client import AIClient
from app.schemas import SummaryResult

STAGE = "summary"


def run(client: AIClient, evidence_block: str) -> SummaryResult:
    return client.complete_structured(
        stage=STAGE,
        system_prompt=prompts.SYSTEM_PROMPT,
        evidence_block=evidence_block,
        instruction=prompts.SUMMARY_INSTRUCTION,
        schema_model=SummaryResult,
    )
