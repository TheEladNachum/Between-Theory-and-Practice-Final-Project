"""Stage 5: recommended next actions and remaining open questions."""

from __future__ import annotations

import re

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

    result = client.complete_structured(
        stage=STAGE,
        system_prompt=prompts.SYSTEM_PROMPT,
        evidence_block=evidence_block,
        prior_context="\n".join(context_parts),
        instruction=prompts.ACTIONS_INSTRUCTION,
        schema_model=ActionsResult,
    )
    _temper_unearned_certainty(result)
    return result


_WILL_CERTAINTY = re.compile(
    r"\bwill\s+(?:immediately\s+)?(resolve|eliminate|fix|stop)\b", re.I
)
_GUARANTEE_CERTAINTY = re.compile(r"\bguarantees?\b", re.I)
_CERTAIN_TO = re.compile(r"\bis certain to\b", re.I)


def _temper_unearned_certainty(result: ActionsResult) -> None:
    """Turn deterministic outcome promises into testable expectations."""
    for action in result.actions:
        rationale = _WILL_CERTAINTY.sub(
            lambda match: f"may help {match.group(1).lower()}", action.rationale
        )
        rationale = _GUARANTEE_CERTAINTY.sub("may help ensure", rationale)
        rationale = _CERTAIN_TO.sub("may", rationale)

        if rationale != action.rationale:
            rationale = rationale.rstrip()
            if rationale and rationale[-1] not in ".!?":
                rationale += "."
            rationale += (
                " Verify the effect against the incident's failure metric because "
                "the current evidence is not conclusive."
            )
            action.rationale = rationale
