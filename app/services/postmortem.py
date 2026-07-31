"""Stage 6: the draft postmortem document.

This is the only stage that sees every earlier result at once, because a
postmortem that contradicts the analysis it is summarising is worse than no
postmortem at all.
"""

from __future__ import annotations

from app.ai import prompts
from app.ai.client import ClaudeClient
from app.schemas import (
    ActionsResult,
    HypothesesResult,
    PostmortemResult,
    ReasoningRisksResult,
    SummaryResult,
    TimelineResult,
)

STAGE = "postmortem"


def run(
    client: ClaudeClient,
    evidence_block: str,
    summary: SummaryResult | None,
    timeline: TimelineResult | None,
    hypotheses: HypothesesResult | None,
    risks: ReasoningRisksResult | None,
    actions: ActionsResult | None,
) -> PostmortemResult:
    context_parts = []
    if summary:
        context_parts.append(prompts.summary_context(summary))
    if timeline:
        context_parts.append(prompts.timeline_context(timeline))
    if hypotheses:
        context_parts.append(prompts.hypotheses_context(hypotheses))
    if risks:
        context_parts.append(prompts.risks_context(risks))
    if actions:
        context_parts.append(prompts.actions_context(actions))

    return client.complete_structured(
        stage=STAGE,
        system_prompt=prompts.SYSTEM_PROMPT,
        evidence_block=evidence_block,
        prior_context="\n".join(context_parts),
        instruction=prompts.POSTMORTEM_INSTRUCTION,
        schema_model=PostmortemResult,
    )
