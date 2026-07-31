"""Stage 4: the bias and fallacy detector.

Two safeguards run after the model answers:

* Risks naming a bias that is not in the catalogue are dropped. The prompt
  lists the permitted ids, but a closed vocabulary is only closed if something
  actually enforces it.
* The canonical bias name from the catalogue replaces whatever the model wrote,
  so the interface always shows consistent terminology.
"""

from __future__ import annotations

from app.ai import prompts
from app.ai.client import ClaudeClient
from app.core.biases import BIAS_BY_ID
from app.schemas import (
    HypothesesResult,
    ReasoningRisksResult,
    SummaryResult,
    TimelineResult,
)

STAGE = "reasoning_risks"


def run(
    client: ClaudeClient,
    evidence_block: str,
    summary: SummaryResult | None,
    timeline: TimelineResult | None,
    hypotheses: HypothesesResult | None,
) -> tuple[ReasoningRisksResult, list[str]]:
    """Return the risks plus any warnings raised while validating them."""
    context_parts = []
    if summary:
        context_parts.append(prompts.summary_context(summary))
    if timeline:
        context_parts.append(prompts.timeline_context(timeline))
    if hypotheses:
        context_parts.append(prompts.hypotheses_context(hypotheses))

    result = client.complete_structured(
        stage=STAGE,
        system_prompt=prompts.SYSTEM_PROMPT,
        evidence_block=evidence_block,
        prior_context="\n".join(context_parts),
        instruction=prompts.risks_instruction(),
        schema_model=ReasoningRisksResult,
    )

    warnings: list[str] = []
    kept = []
    for risk in result.risks:
        definition = BIAS_BY_ID.get(risk.bias_id)
        if definition is None:
            warnings.append(
                f'The bias detector reported "{risk.bias_name}", which is not in '
                f"the catalogue. It was discarded."
            )
            continue
        risk.bias_name = definition.name
        kept.append(risk)

    result.risks = kept
    return result, warnings
