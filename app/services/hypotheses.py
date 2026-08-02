"""Stage 3: competing root-cause hypotheses.

This stage also applies the one piece of post-processing the tool performs on
model output: hypotheses that cite no contradicting evidence are pushed below
those that do, at equal confidence. A hypothesis nobody argued against is not
better supported - it is less examined, and the ranking should not reward it.
"""

from __future__ import annotations

from app.ai import prompts
from app.ai.client import AIClient
from app.schemas import (
    Confidence,
    HypothesesResult,
    SummaryResult,
    TimelineResult,
)

STAGE = "hypotheses"

_CONFIDENCE_RANK = {Confidence.HIGH: 0, Confidence.MEDIUM: 1, Confidence.LOW: 2}


def run(
    client: AIClient,
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

    _enforce_confidence_evidence_threshold(result)
    result.hypotheses.sort(key=_ranking_key)
    return result


def _enforce_confidence_evidence_threshold(result: HypothesesResult) -> None:
    """Conservatively cap `high` confidence when its evidence fails the rule.

    Code may lower confidence for safety, but it never raises it.  This keeps
    the displayed confidence consistent with the evidence standard even when
    a model ignores the prompt.
    """
    for hypothesis in result.hypotheses:
        support = {(ref.source, ref.quote) for ref in hypothesis.supporting_evidence}
        reasons = []
        if len(support) < 2:
            reasons.append("fewer than two distinct supporting citations")
        if hypothesis.contradicting_evidence:
            reasons.append("contradicting evidence remains")

        if hypothesis.confidence == Confidence.HIGH and reasons:
            hypothesis.confidence = Confidence.MEDIUM
            hypothesis.confidence_reason = (
                hypothesis.confidence_reason.rstrip()
                + " Human-review safeguard: confidence is capped at medium because "
                + " and ".join(reasons)
                + "."
            )


def _ranking_key(hypothesis) -> tuple[int, int]:
    """Sort by confidence, then demote anything that was never argued against."""
    examined = 0 if hypothesis.contradicting_evidence else 1
    return (_CONFIDENCE_RANK.get(hypothesis.confidence, 3), examined)
