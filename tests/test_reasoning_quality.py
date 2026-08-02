"""Regression tests for issues found during the creator's human review."""

from __future__ import annotations

from typing import Any

from app.ai import prompts
from app.schemas import (
    ActionsResult,
    HypothesesResult,
    ReasoningRisksResult,
    TimelineResult,
)
from app.services import actions, hypotheses, reasoning_risks, timeline


class ResultClient:
    """Return one pre-built structured result from a service call."""

    def __init__(self, result: Any) -> None:
        self.result = result

    def complete_structured(self, **_: Any):
        return self.result


def test_invented_calendar_date_is_not_accepted_as_timeline_timestamp():
    result = TimelineResult(
        events=[
            {
                "timestamp": "2024-10-28",
                "description": "The incident happened on Monday.",
                "evidence": [
                    {
                        "source": "description",
                        "quote": "The incident happened on Monday, 2024-11-04.",
                    }
                ],
                "inferred": False,
            }
        ]
    )

    checked = timeline.run(ResultClient(result), "evidence", None)

    assert checked.events[0].timestamp == "unknown"
    assert checked.events[0].inferred is True


def test_exact_quoted_timestamp_is_preserved():
    result = TimelineResult(
        events=[
            {
                "timestamp": "2024-11-04 10:20:11",
                "description": "A request failed.",
                "evidence": [
                    {
                        "source": "logs",
                        "quote": "2024-11-04 10:20:11 ERROR request failed",
                    }
                ],
                "inferred": False,
            }
        ]
    )

    checked = timeline.run(ResultClient(result), "evidence", None)

    assert checked.events[0].timestamp == "2024-11-04 10:20:11"
    assert checked.events[0].inferred is False


def test_high_confidence_with_counter_evidence_is_capped_at_medium():
    result = HypothesesResult(
        hypotheses=[
            {
                "title": "Node configuration mismatch",
                "explanation": "One node may differ.",
                "confidence": "high",
                "confidence_reason": "Several observations point to the node.",
                "supporting_evidence": [
                    {"source": "logs", "quote": "api-2 returned 500"},
                    {"source": "alerts", "quote": "error rate reached 10%"},
                ],
                "contradicting_evidence": [
                    {"source": "extra", "quote": "api-2 receives 25% of traffic"}
                ],
                "recommended_test": "Compare the node configuration.",
            }
        ]
    )

    checked = hypotheses.run(ResultClient(result), "evidence", None, None)

    assert checked.hypotheses[0].confidence.value == "medium"
    assert "Human-review safeguard" in checked.hypotheses[0].confidence_reason


def test_reasoning_risk_confidence_ceiling_updates_the_hypothesis():
    hypothesis_result = HypothesesResult(
        hypotheses=[
            {
                "title": "Node configuration mismatch",
                "explanation": "One node may differ.",
                "confidence": "high",
                "confidence_reason": "Two independent observations support it.",
                "supporting_evidence": [
                    {"source": "logs", "quote": "api-2 returned 500"},
                    {"source": "alerts", "quote": "api-2 alert fired"},
                ],
                "contradicting_evidence": [],
                "recommended_test": "Compare the node configuration.",
            }
        ]
    )
    risk_result = ReasoningRisksResult(
        risks=[
            {
                "bias_id": "overconfidence_bias",
                "bias_name": "Overconfidence bias",
                "where_it_appears": "Node configuration mismatch is not tested.",
                "why_it_matters": "The wrong node could be removed.",
                "mitigation": "Run the comparison first.",
                "linked_hypothesis": "Node configuration mismatch",
                "confidence_ceiling": "medium",
            }
        ]
    )

    warnings = reasoning_risks.reconcile_hypothesis_confidence(
        hypothesis_result, risk_result
    )

    assert hypothesis_result.hypotheses[0].confidence.value == "medium"
    assert "lowered confidence from high to medium" in (
        hypothesis_result.hypotheses[0].confidence_reason
    )
    assert len(warnings) == 1


def test_reasoning_risk_removes_a_date_not_present_in_the_evidence():
    result = ReasoningRisksResult(
        risks=[
            {
                "bias_id": "post_hoc_fallacy",
                "bias_name": "Post hoc fallacy",
                "where_it_appears": "The analysis claimed Monday was October 28.",
                "why_it_matters": "It changes the sequence.",
                "mitigation": "Use the quoted November 4 date.",
                "linked_hypothesis": None,
                "confidence_ceiling": None,
            }
        ]
    )

    checked, warnings = reasoning_risks.run(
        ResultClient(result),
        "The evidence states November 4 and does not map Monday to another date.",
        None,
        None,
        None,
    )

    assert "October 28" not in checked.risks[0].where_it_appears
    assert "[unverified date removed]" in checked.risks[0].where_it_appears
    assert "November 4" in checked.risks[0].mitigation
    assert any("unsupported date" in warning for warning in warnings)


def test_action_outcome_certainty_is_tempered_and_made_testable():
    result = ActionsResult(
        actions=[
            {
                "step": "Remove api-2 from the load balancer.",
                "rationale": "Removing it will immediately resolve the 10% failure rate.",
                "priority": "immediate",
                "linked_hypothesis": "Node configuration mismatch",
            }
        ],
        open_questions=[],
    )

    checked = actions.run(ResultClient(result), "evidence", None, None, None)

    rationale = checked.actions[0].rationale
    assert "will immediately resolve" not in rationale
    assert "may help resolve" in rationale
    assert "Verify the effect" in rationale
    assert rationale in prompts.actions_context(checked)


def test_guarantee_softening_does_not_invert_a_positive_outcome():
    result = ActionsResult(
        actions=[
            {
                "step": "Apply the reviewed configuration.",
                "rationale": "The change guarantees availability.",
                "priority": "soon",
                "linked_hypothesis": None,
            }
        ],
        open_questions=[],
    )

    checked = actions.run(ResultClient(result), "evidence", None, None, None)

    assert "may help ensure availability" in checked.actions[0].rationale
    assert "reduce availability" not in checked.actions[0].rationale


def test_prompts_explicitly_encode_human_review_guardrails():
    assert "DO NOT INVENT CALENDAR RELATIONSHIPS" in prompts.SYSTEM_PROMPT
    assert "caps confidence at medium" in prompts.HYPOTHESES_INSTRUCTION
    assert "confidence_ceiling" in prompts.risks_instruction()
    assert 'Never say an action "will resolve"' in prompts.ACTIONS_INSTRUCTION
    assert "Never restate a hypothesis" in prompts.POSTMORTEM_INSTRUCTION


def test_risk_context_carries_the_enforced_correction_forward():
    risks = ReasoningRisksResult(
        risks=[
            {
                "bias_id": "overconfidence_bias",
                "bias_name": "Overconfidence bias",
                "where_it_appears": "Node hypothesis",
                "why_it_matters": "May trigger the wrong mitigation.",
                "mitigation": "Compare node configuration first.",
                "linked_hypothesis": "Node configuration mismatch",
                "confidence_ceiling": "medium",
            }
        ]
    )

    context = prompts.risks_context(risks)

    assert "why it matters: May trigger the wrong mitigation." in context
    assert "mitigation: Compare node configuration first." in context
    assert "linked hypothesis: Node configuration mismatch" in context
    assert "confidence ceiling: medium" in context
