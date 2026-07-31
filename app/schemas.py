"""The data model for an investigation.

These types are the contract between three things: the model's JSON output,
the HTTP API, and the frontend. They also encode the reasoning structure the
project brief asks for - Facts, Assumptions, Hypotheses, Actions are separate
types on purpose, so the code physically cannot blur them together.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- #
# Input
# --------------------------------------------------------------------------- #


class IncidentInput(BaseModel):
    """Everything the investigator pastes or uploads about one incident."""

    title: str = Field(default="Untitled incident")
    description: str = Field(
        default="", description="What was reported, in the reporter's own words."
    )
    logs: str = Field(default="", description="Raw application logs.")
    error_traces: str = Field(default="", description="Stack traces / exceptions.")
    alerts: str = Field(default="", description="Monitoring and alerting output.")
    deployment_notes: str = Field(
        default="", description="Recent deploys, config changes, migrations."
    )
    user_reports: str = Field(
        default="", description="Support tickets, user complaints, chat messages."
    )
    extra: str = Field(default="", description="Anything else - CSV, JSON, notes.")

    def evidence_sources(self) -> dict[str, str]:
        """Return only the non-empty inputs, keyed by the name the model must cite.

        The keys here become the vocabulary the model is allowed to use in the
        `source` field of an EvidenceRef. Keeping that list short and fixed is
        what makes citations checkable rather than decorative.
        """
        candidates = {
            "description": self.description,
            "logs": self.logs,
            "error_traces": self.error_traces,
            "alerts": self.alerts,
            "deployment_notes": self.deployment_notes,
            "user_reports": self.user_reports,
            "extra": self.extra,
        }
        return {k: v for k, v in candidates.items() if v.strip()}

    def is_empty(self) -> bool:
        return not self.evidence_sources()


# --------------------------------------------------------------------------- #
# Evidence
# --------------------------------------------------------------------------- #


class EvidenceRef(BaseModel):
    """A pointer back into the input data.

    `quote` must be text that actually appears in the named source. That is
    what `app/core/evidence.py` checks - an unverifiable citation is the single
    most common way an AI answer looks rigorous while being made up.
    """

    source: str = Field(description="Which input field this came from.")
    quote: str = Field(description="The exact text from that input.")


# --------------------------------------------------------------------------- #
# The four reasoning layers
# --------------------------------------------------------------------------- #


class Fact(BaseModel):
    """Something the input data directly states. No interpretation allowed."""

    statement: str
    evidence: List[EvidenceRef]


class Assumption(BaseModel):
    """Something believed but not shown by the data."""

    statement: str
    why_unproven: str = Field(description="What is missing that would prove it.")
    how_to_verify: str = Field(description="A concrete check that would settle it.")


class Confidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Hypothesis(BaseModel):
    """One possible explanation. Never presented as the answer."""

    title: str
    explanation: str
    confidence: Confidence
    confidence_reason: str = Field(
        description="Why this confidence level and not a higher or lower one."
    )
    supporting_evidence: List[EvidenceRef]
    contradicting_evidence: List[EvidenceRef] = Field(
        description="Evidence that argues against this hypothesis. "
        "An empty list here is itself a warning sign."
    )
    recommended_test: str = Field(
        description="A single check that would confirm or kill this hypothesis."
    )


class Priority(str, Enum):
    IMMEDIATE = "immediate"
    SOON = "soon"
    LATER = "later"


class Action(BaseModel):
    """A concrete next step, tied to the evidence that motivates it."""

    step: str
    rationale: str
    priority: Priority
    linked_hypothesis: Optional[str] = Field(
        default=None, description="Title of the hypothesis this step tests, if any."
    )


class OpenQuestion(BaseModel):
    """Something the available data simply cannot answer."""

    question: str
    why_it_matters: str


# --------------------------------------------------------------------------- #
# Timeline
# --------------------------------------------------------------------------- #


class TimelineEvent(BaseModel):
    """One point on the reconstructed timeline."""

    timestamp: str = Field(
        description="As written in the source, or 'unknown' if not stated."
    )
    description: str
    evidence: List[EvidenceRef]
    inferred: bool = Field(
        description="True when the ordering or timing was deduced rather than read "
        "directly from the data."
    )


# --------------------------------------------------------------------------- #
# Reasoning risks
# --------------------------------------------------------------------------- #


class ReasoningRisk(BaseModel):
    """A cognitive bias or logical fallacy that this investigation is exposed to."""

    bias_id: str = Field(description="Identifier from the bias catalogue.")
    bias_name: str
    where_it_appears: str = Field(
        description="The specific place in this investigation where it shows up."
    )
    why_it_matters: str
    mitigation: str = Field(description="What to do to reduce its effect.")


# --------------------------------------------------------------------------- #
# Claim verification
# --------------------------------------------------------------------------- #


class Verdict(str, Enum):
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"


class ClaimCheck(BaseModel):
    """The result of auditing one AI-generated claim against the input data."""

    claim: str
    verdict: Verdict
    reasoning: str


# --------------------------------------------------------------------------- #
# Aggregate results
# --------------------------------------------------------------------------- #


class SummaryResult(BaseModel):
    summary: str = Field(description="Professional prose summary of the incident.")
    facts: List[Fact]
    assumptions: List[Assumption]


class TimelineResult(BaseModel):
    events: List[TimelineEvent]


class HypothesesResult(BaseModel):
    hypotheses: List[Hypothesis]


class ReasoningRisksResult(BaseModel):
    risks: List[ReasoningRisk]


class ActionsResult(BaseModel):
    actions: List[Action]
    open_questions: List[OpenQuestion]


class PostmortemResult(BaseModel):
    markdown: str = Field(description="A complete postmortem document in Markdown.")


class VerificationResult(BaseModel):
    checks: List[ClaimCheck]


class AnalysisResult(BaseModel):
    """The full investigation, as returned to the frontend."""

    title: str
    summary: str = ""
    facts: List[Fact] = Field(default_factory=list)
    assumptions: List[Assumption] = Field(default_factory=list)
    timeline: List[TimelineEvent] = Field(default_factory=list)
    hypotheses: List[Hypothesis] = Field(default_factory=list)
    reasoning_risks: List[ReasoningRisk] = Field(default_factory=list)
    actions: List[Action] = Field(default_factory=list)
    open_questions: List[OpenQuestion] = Field(default_factory=list)
    postmortem_markdown: str = ""
    unverified_citations: List[EvidenceRef] = Field(
        default_factory=list,
        description="Citations whose quoted text was not found in the named "
        "source. These are shown to the user as a hallucination warning.",
    )
    stages_completed: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
