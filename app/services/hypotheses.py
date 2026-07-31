"""Stage 3: competing root-cause hypotheses.

This stage also applies the one piece of post-processing the tool performs on
model output: hypotheses that cite no contradicting evidence are pushed below
those that do, at equal confidence. A hypothesis nobody argued against is not
better supported - it is less examined, and the ranking should not reward it.
"""

from __future__ import annotations

from app.ai import prompts
from app.ai.client import ClaudeClient
from app.schemas import (
    Confidence,
    HypothesesResult,
    SummaryResult,
    TimelineResult,
)

STAGE = "hypotheses"

_CONFIDENCE_RANK = {Confidence.HIGH: 0, Confidence.MEDIUM: 1, Confidence.LOW: 2}


def run(
    client: ClaudeClient,
    evidence_block: str,
    summary: SummaryResult | None,
    timeline: TimelineResult | None,
) -> HypothesesResult:
    context_parts = []
    if summary:
        context_parts.append(prompts.summary_context(summary))
    if timeline:
        context_parts.append(prompts.timeline_context(timeline))

    result = client.complete_structured(
        stage=STAGE,
        system_prompt=prompts.SYSTEM_PROMPT,
        evidence_block=evidence_block,
        prior_context="\n".join(context_parts),
        instruction=prompts.HYPOTHESES_INSTRUCTION,
        schema_model=HypothesesResult,
    )

    result.hypotheses.sort(key=_ranking_key)
    return result


def _ranking_key(hypothesis) -> tuple[int, int]:
    """Sort by confidence, then demote anything that was never argued against."""
    examined = 0 if hypothesis.contradicting_evidence else 1
    return (_CONFIDENCE_RANK.get(hypothesis.confidence, 3), examined)
