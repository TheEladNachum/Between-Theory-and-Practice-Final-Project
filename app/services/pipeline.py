"""Sequences the six analysis stages and assembles the final result.

Two decisions worth defending:

* **A failed stage does not abort the run.** If the hypothesis stage fails, the
  summary and timeline are still worth having, and the user is told exactly
  which part is missing. An investigation tool that throws away four good
  stages because the fifth failed is worse than useless during an incident.

* **Citation checking happens here, once, over everything.** Every quote the
  model produced across all stages is checked against the input it named. The
  failures are attached to the result and surfaced in the interface rather than
  written to a log nobody reads.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterator, List

from app.ai import prompts
from app.ai.client import AIClient, ModelError
from app.core import evidence as evidence_check
from app.schemas import AnalysisResult, EvidenceRef, IncidentInput
from app.services import (
    actions as actions_stage,
    hypotheses as hypotheses_stage,
    postmortem as postmortem_stage,
    reasoning_risks as risks_stage,
    summary as summary_stage,
    timeline as timeline_stage,
)

log = logging.getLogger("incidentiq.pipeline")

# Keys that carry EvidenceRef lists, used when annotating the serialised result.
_REF_FIELDS = ("evidence", "supporting_evidence", "contradicting_evidence")


def run(client: AIClient, incident: IncidentInput) -> Iterator[Dict[str, Any]]:
    """Run the full analysis, yielding progress events as each stage finishes.

    Yields dicts shaped for the SSE stream: `stage_start`, `stage_done`,
    `stage_error`, and finally `complete`.
    """
    evidence_block = prompts.build_evidence_block(incident)
    result = AnalysisResult(title=incident.title)

    summary = timeline = hypotheses = risks = actions = None

    # -- stage 1: summary -------------------------------------------------
    yield {"type": "stage_start", "stage": "summary"}
    try:
        summary = summary_stage.run(client, evidence_block)
        result.summary = summary.summary
        result.facts = summary.facts
        result.assumptions = summary.assumptions
        result.stages_completed.append("summary")
        yield {"type": "stage_done", "stage": "summary"}
    except ModelError as exc:
        yield from _stage_failed("summary", exc, result)

    # -- stage 2: timeline ------------------------------------------------
    yield {"type": "stage_start", "stage": "timeline"}
    try:
        timeline = timeline_stage.run(client, evidence_block, summary)
        result.timeline = timeline.events
        result.stages_completed.append("timeline")
        yield {"type": "stage_done", "stage": "timeline"}
    except ModelError as exc:
        yield from _stage_failed("timeline", exc, result)

    # -- stage 3: hypotheses ----------------------------------------------
    yield {"type": "stage_start", "stage": "hypotheses"}
    try:
        hypotheses = hypotheses_stage.run(client, evidence_block, summary, timeline)
        result.hypotheses = hypotheses.hypotheses
        result.stages_completed.append("hypotheses")
        yield {"type": "stage_done", "stage": "hypotheses"}
    except ModelError as exc:
        yield from _stage_failed("hypotheses", exc, result)

    # -- stage 4: reasoning risks -----------------------------------------
    yield {"type": "stage_start", "stage": "reasoning_risks"}
    try:
        risks, risk_warnings = risks_stage.run(
            client, evidence_block, summary, timeline, hypotheses
        )
        result.reasoning_risks = risks.risks
        result.warnings.extend(risk_warnings)
        result.stages_completed.append("reasoning_risks")
        yield {"type": "stage_done", "stage": "reasoning_risks"}
    except ModelError as exc:
        yield from _stage_failed("reasoning_risks", exc, result)

    # -- stage 5: actions --------------------------------------------------
    yield {"type": "stage_start", "stage": "actions"}
    try:
        actions = actions_stage.run(client, evidence_block, summary, hypotheses, risks)
        result.actions = actions.actions
        result.open_questions = actions.open_questions
        result.stages_completed.append("actions")
        yield {"type": "stage_done", "stage": "actions"}
    except ModelError as exc:
        yield from _stage_failed("actions", exc, result)

    # -- stage 6: postmortem -----------------------------------------------
    yield {"type": "stage_start", "stage": "postmortem"}
    try:
        postmortem = postmortem_stage.run(
            client, evidence_block, summary, timeline, hypotheses, risks, actions
        )
        result.postmortem_markdown = postmortem.markdown
        result.stages_completed.append("postmortem")
        yield {"type": "stage_done", "stage": "postmortem"}
    except ModelError as exc:
        yield from _stage_failed("postmortem", exc, result)

    # -- verification and assembly ------------------------------------------
    payload = _finalise(result, incident)
    yield {"type": "complete", "result": payload}


# --------------------------------------------------------------------------- #


def _stage_failed(stage: str, exc: ModelError, result: AnalysisResult):
    """Record a stage failure and keep going."""
    log.warning("stage %s failed: %s", stage, exc)
    result.warnings.append(f"The {stage.replace('_', ' ')} stage failed: {exc}")
    yield {"type": "stage_error", "stage": stage, "message": str(exc)}


def _finalise(result: AnalysisResult, incident: IncidentInput) -> Dict[str, Any]:
    """Verify every citation, annotate the failures, and serialise."""
    sources = incident.evidence_sources()

    all_refs: List[EvidenceRef] = []
    all_refs.extend(ref for fact in result.facts for ref in fact.evidence)
    all_refs.extend(ref for event in result.timeline for ref in event.evidence)
    for hypothesis in result.hypotheses:
        all_refs.extend(hypothesis.supporting_evidence)
        all_refs.extend(hypothesis.contradicting_evidence)

    _, unverified = evidence_check.verify_all(all_refs, sources)
    unverified = evidence_check.dedupe(unverified)
    result.unverified_citations = unverified

    if unverified:
        result.warnings.append(
            f"{len(unverified)} citation(s) could not be found in the evidence they "
            f"named. See the Reasoning risks tab - claims resting on them are unsupported."
        )
    if not result.stages_completed:
        result.warnings.append("Every stage failed. Check the API key and the server log.")

    payload = result.model_dump(mode="json")
    _annotate_unverified(payload, sources)
    return payload


def _annotate_unverified(payload: Dict[str, Any], sources: Dict[str, str]) -> None:
    """Add `unverified: true` to citations that failed the check.

    The flag lives only on the serialised payload, never on the Pydantic model.
    Adding it to `EvidenceRef` would put it in the JSON schema sent to the
    model, which would then be obliged to fill it in - and asking the model to
    self-declare which of its own quotes are fabricated defeats the point of
    checking them.
    """

    def walk(node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item)
            return
        if not isinstance(node, dict):
            return

        for key, value in node.items():
            if key in _REF_FIELDS and isinstance(value, list):
                for ref in value:
                    if isinstance(ref, dict) and "source" in ref and "quote" in ref:
                        parsed = EvidenceRef(source=ref["source"], quote=ref["quote"])
                        if not evidence_check.verify_one(parsed, sources):
                            ref["unverified"] = True
            else:
                walk(value)

    walk(payload)
