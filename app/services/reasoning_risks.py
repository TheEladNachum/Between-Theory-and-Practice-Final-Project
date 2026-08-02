"""Stage 4: the bias and fallacy detector.

Safeguards run after the model answers:

* Risks naming a bias that is not in the catalogue are dropped. The prompt
  lists the permitted ids, but a closed vocabulary is only closed if something
  actually enforces it.
* The canonical bias name from the catalogue replaces whatever the model wrote,
  so the interface always shows consistent terminology.
* Calendar values absent from the evidence are marked and reported rather than
  allowed to become part of the investigation narrative.
* Structured confidence ceilings can be applied back to linked hypotheses, so
  the audit and the hypothesis list cannot display contradictory confidence.
"""

from __future__ import annotations

import re

from app.ai import prompts
from app.ai.client import AIClient
from app.core.biases import BIAS_BY_ID
from app.schemas import (
    Confidence,
    HypothesesResult,
    ReasoningRisksResult,
    SummaryResult,
    TimelineResult,
)

STAGE = "reasoning_risks"


def run(
    client: AIClient,
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

    removed_dates: set[str] = set()
    for risk in result.risks:
        for field in ("where_it_appears", "why_it_matters", "mitigation"):
            cleaned, removed = _remove_unsupported_dates(
                getattr(risk, field), evidence_block
            )
            setattr(risk, field, cleaned)
            removed_dates.update(removed)

    for value in sorted(removed_dates):
        warnings.append(
            f'The reasoning-risk audit introduced an unsupported date "{value}"; '
            "it was replaced with an explicit unverified-date marker."
        )

    return result, warnings


_MONTH = (
    r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?"
)
_CALENDAR_VALUE = re.compile(
    rf"\b(?:19|20)\d{{2}}-\d{{2}}-\d{{2}}(?:[ T]\d{{2}}:\d{{2}}(?::\d{{2}})?)?\b"
    rf"|\b(?:{_MONTH})\s+\d{{1,2}}(?:,\s*\d{{4}})?\b"
    rf"|\b\d{{1,2}}\s+(?:{_MONTH})(?:\s+\d{{4}})?\b",
    re.I,
)


def _remove_unsupported_dates(text: str, evidence_block: str) -> tuple[str, set[str]]:
    """Mark explicit calendar values that were not copied from the evidence."""
    removed: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        value = match.group(0)
        if value in evidence_block:
            return value
        removed.add(value)
        return "[unverified date removed]"

    return _CALENDAR_VALUE.sub(replace, text), removed


_CONFIDENCE_LEVEL = {
    Confidence.LOW: 0,
    Confidence.MEDIUM: 1,
    Confidence.HIGH: 2,
}


def reconcile_hypothesis_confidence(
    hypotheses: HypothesesResult | None,
    risks: ReasoningRisksResult,
) -> list[str]:
    """Apply audit confidence ceilings so adjacent stages cannot disagree.

    A correction is deliberately one-way: the audit may lower confidence but
    can never raise it.
    """
    if hypotheses is None:
        return []

    by_title = {hypothesis.title: hypothesis for hypothesis in hypotheses.hypotheses}
    warnings: list[str] = []

    for risk in risks.risks:
        if risk.linked_hypothesis is None or risk.confidence_ceiling is None:
            continue

        hypothesis = by_title.get(risk.linked_hypothesis)
        if hypothesis is None:
            warnings.append(
                "The reasoning-risk audit named an unknown hypothesis "
                f'"{risk.linked_hypothesis}"; its confidence correction was ignored.'
            )
            continue

        if (
            _CONFIDENCE_LEVEL[risk.confidence_ceiling]
            >= _CONFIDENCE_LEVEL[hypothesis.confidence]
        ):
            continue

        previous = hypothesis.confidence
        hypothesis.confidence = risk.confidence_ceiling
        hypothesis.confidence_reason = (
            hypothesis.confidence_reason.rstrip()
            + f" Reasoning-risk review lowered confidence from {previous.value} "
            + f"to {risk.confidence_ceiling.value}; resolve the audit finding before "
            + "raising it again."
        )
        warnings.append(
            f'Confidence for hypothesis "{hypothesis.title}" was lowered from '
            f"{previous.value} to {risk.confidence_ceiling.value} after the "
            "reasoning-risk audit."
        )

    hypotheses.hypotheses.sort(
        key=lambda hypothesis: -_CONFIDENCE_LEVEL[hypothesis.confidence]
    )
    return warnings
