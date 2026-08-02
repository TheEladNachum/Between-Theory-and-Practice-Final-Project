"""Tests for the pipeline, using a stub client instead of the real model.

Two behaviours are asserted here because both are design decisions rather than
accidents: a failing stage must not abort the run, and fabricated citations
must be caught and marked on the way out.
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.ai.client import ModelError
from app.schemas import (
    ActionsResult,
    HypothesesResult,
    IncidentInput,
    PostmortemResult,
    ReasoningRisksResult,
    SummaryResult,
    TimelineResult,
)
from app.services import pipeline

INCIDENT = IncidentInput(
    title="Checkout failing",
    logs="2024-03-14 08:58:02 ERROR checkout-api TimeoutError: acquiring connection from pool",
    deployment_notes="v2.4.1 deployed at 09:12, frontend only",
)

REAL_QUOTE = "TimeoutError: acquiring connection from pool"
FAKE_QUOTE = "FATAL: disk full on /var/lib/postgresql"


def canned(stage: str):
    """A minimal valid result for each stage."""
    if stage == "summary":
        return SummaryResult(
            summary="Checkout returned 500s.",
            facts=[
                {"statement": "Pool timeouts occurred",
                 "evidence": [{"source": "logs", "quote": REAL_QUOTE}]},
                {"statement": "Disk was full",
                 "evidence": [{"source": "logs", "quote": FAKE_QUOTE}]},
            ],
            assumptions=[],
        )
    if stage == "timeline":
        return TimelineResult(events=[])
    if stage == "hypotheses":
        return HypothesesResult(hypotheses=[
            {"title": "Pool exhaustion", "explanation": "Too few connections.",
             "confidence": "medium", "confidence_reason": "one log line",
             "supporting_evidence": [{"source": "logs", "quote": REAL_QUOTE}],
             "contradicting_evidence": [], "recommended_test": "Check pool metrics."},
            {"title": "Deploy broke it", "explanation": "Shipped at 09:12.",
             "confidence": "high", "confidence_reason": "timing",
             "supporting_evidence": [{"source": "logs", "quote": FAKE_QUOTE}],
             "contradicting_evidence": [{"source": "logs", "quote": REAL_QUOTE}],
             "recommended_test": "Roll back."},
        ])
    if stage == "reasoning_risks":
        return ReasoningRisksResult(risks=[
            {"bias_id": "post_hoc_fallacy", "bias_name": "wrong name on purpose",
             "where_it_appears": "Hypothesis 2", "why_it_matters": "Wrong fix.",
             "mitigation": "Require a mechanism."},
            {"bias_id": "recency_bias", "bias_name": "Recency bias",
             "where_it_appears": "nowhere", "why_it_matters": "n/a", "mitigation": "n/a"},
        ])
    if stage == "actions":
        return ActionsResult(actions=[], open_questions=[])
    return PostmortemResult(markdown="# Incident report")


class StubClient:
    """Stands in for AIClient. `failing` names stages that should raise."""

    def __init__(self, failing: tuple[str, ...] = ()) -> None:
        self.failing = failing
        self.calls: List[str] = []

    def complete_structured(self, *, stage: str, **_: Any):
        self.calls.append(stage)
        if stage in self.failing:
            raise ModelError(f"simulated failure in {stage}")
        return canned(stage)


def run(client) -> Dict[str, Any]:
    events = list(pipeline.run(client, INCIDENT))
    complete = [e for e in events if e["type"] == "complete"]
    assert len(complete) == 1, "the pipeline must always emit exactly one complete event"
    return complete[0]["result"]


# --- happy path -------------------------------------------------------------


def test_all_six_stages_run_in_order():
    client = StubClient()
    run(client)
    assert client.calls == [
        "summary", "timeline", "hypotheses", "reasoning_risks", "actions", "postmortem",
    ]


def test_result_is_assembled_from_every_stage():
    result = run(StubClient())
    assert result["summary"] == "Checkout returned 500s."
    assert len(result["hypotheses"]) == 2
    assert result["postmortem_markdown"].startswith("# Incident report")
    assert len(result["stages_completed"]) == 6


# --- degraded mode ----------------------------------------------------------


def test_a_failed_stage_does_not_abort_the_run():
    client = StubClient(failing=("hypotheses",))
    result = run(client)

    # Later stages still ran.
    assert "postmortem" in client.calls
    assert result["postmortem_markdown"]
    # And the user is told what is missing.
    assert result["hypotheses"] == []
    assert any("hypotheses stage failed" in w for w in result["warnings"])


def test_stage_error_event_is_emitted():
    events = list(pipeline.run(StubClient(failing=("actions",)), INCIDENT))
    errors = [e for e in events if e["type"] == "stage_error"]
    assert [e["stage"] for e in errors] == ["actions"]


def test_total_failure_still_produces_a_result():
    all_stages = ("summary", "timeline", "hypotheses", "reasoning_risks", "actions", "postmortem")
    result = run(StubClient(failing=all_stages))
    assert result["stages_completed"] == []
    assert any("Every stage failed" in w for w in result["warnings"])


# --- citation checking ------------------------------------------------------


def test_fabricated_citations_are_collected():
    result = run(StubClient())
    quotes = [ref["quote"] for ref in result["unverified_citations"]]
    assert FAKE_QUOTE in quotes
    assert REAL_QUOTE not in quotes


def test_fabricated_citations_are_marked_in_place():
    result = run(StubClient())
    fake_fact = next(f for f in result["facts"] if f["statement"] == "Disk was full")
    assert fake_fact["evidence"][0]["unverified"] is True

    real_fact = next(f for f in result["facts"] if f["statement"] == "Pool timeouts occurred")
    assert "unverified" not in real_fact["evidence"][0]


def test_unverified_citations_raise_a_warning():
    result = run(StubClient())
    assert any("could not be found" in w for w in result["warnings"])


# --- bias validation --------------------------------------------------------


def test_invented_biases_are_discarded_and_reported():
    result = run(StubClient())
    ids = [risk["bias_id"] for risk in result["reasoning_risks"]]
    assert ids == ["post_hoc_fallacy"]
    assert any("not in the catalogue" in w for w in result["warnings"])


def test_bias_name_is_normalised_to_the_catalogue():
    result = run(StubClient())
    assert result["reasoning_risks"][0]["bias_name"] == "Post hoc fallacy"


# --- hypothesis ranking -----------------------------------------------------


def test_unexamined_hypothesis_is_demoted_below_an_examined_one():
    """A high-confidence claim nobody argued against should not outrank a
    medium-confidence one that was actually challenged... but confidence still
    dominates, so here the high-confidence one leads. This pins the rule."""
    result = run(StubClient())
    assert result["hypotheses"][0]["title"] == "Deploy broke it"
    assert result["hypotheses"][0]["confidence"] == "high"
