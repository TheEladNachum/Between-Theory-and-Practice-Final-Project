"""Stage 5: recommended next actions and remaining open questions."""

from __future__ import annotations

from app.ai import prompts
from app.ai.client import AIClient
from app.schemas import (
    ActionsResult,
    HypothesesResult,
    ReasoningRisksResult,
    SummaryResult,
)

STAGE = "actions"


def run(
    client: AIClient,
    evidence_block: str,
    summary: SummaryResult | None,
    hypotheses: HypothesesResult | None,
    risks: ReasoningRisksResult | None,
) -> ActionsResult:
    context_parts = []
    if summary:
        context_parts.append(prompts.summary_context(summary))
    if hypotheses:
        context_parts.append(prompts.hypotheses_context(hypotheses))
    if risks:
        context_parts.append(prompts.risks_context(risks))

    return client.complete_structured(
        stage=STAGE,
        system_prompt=prompts.SYSTEM_PROMPT,
        evidence_block=evidence_block,
        prior_context="\n".join(context_parts),
        instruction=prompts.ACTIONS_INSTRUCTION,
        schema_model=ActionsResult,
    )
