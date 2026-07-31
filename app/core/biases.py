"""The catalogue of cognitive biases and logical fallacies this tool looks for.

The eight entries below are exactly the ones listed in the project brief. They
are kept in code rather than buried in a prompt string for three reasons:

1. The bias detector prompt is generated from this list, so the model can only
   report biases we actually defined - it cannot invent a plausible-sounding
   one.
2. `bias_id` is a closed vocabulary, so the frontend can render each risk with
   the correct reference text.
3. Adding a bias is a one-line change here rather than a prompt rewrite.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class BiasDefinition:
    id: str
    name: str
    how_it_appears: str
    """How this bias typically shows up in an incident investigation."""
    detection_hint: str
    """What the detector should look for in the investigation so far."""
    mitigation: str
    """The standard countermeasure."""


BIAS_CATALOGUE: List[BiasDefinition] = [
    BiasDefinition(
        id="confirmation_bias",
        name="Confirmation bias",
        how_it_appears=(
            "The investigation collects only the evidence that supports the first "
            "suspected root cause, and quietly skips over log lines or metrics "
            "that point somewhere else."
        ),
        detection_hint=(
            "A hypothesis with a long supporting-evidence list and an empty or "
            "token contradicting-evidence list. Evidence in the input that no "
            "hypothesis accounts for."
        ),
        mitigation=(
            "For each hypothesis, actively search the input for evidence that "
            "would falsify it, and record what you find even when it is "
            "inconvenient."
        ),
    ),
    BiasDefinition(
        id="anchoring_bias",
        name="Anchoring bias",
        how_it_appears=(
            "The first error message, the loudest alert, or the AI's first "
            "suggestion dominates the rest of the investigation, and later "
            "evidence is interpreted to fit it."
        ),
        detection_hint=(
            "Every hypothesis is a variation on the first one. The most "
            "prominent error string in the input appears in most hypotheses "
            "regardless of whether it is a cause or a symptom."
        ),
        mitigation=(
            "Generate at least one hypothesis that does not involve the first "
            "error observed, and ask explicitly whether that error is a cause "
            "or a downstream effect."
        ),
    ),
    BiasDefinition(
        id="automation_bias",
        name="Automation bias",
        how_it_appears=(
            "AI-generated conclusions are trusted because they are fluent, "
            "well-formatted and confident-sounding, rather than because they are "
            "supported by the evidence."
        ),
        detection_hint=(
            "Confident claims with no citation, or citations whose quoted text "
            "does not appear in the input at all. Professional phrasing carrying "
            "an unproven assertion."
        ),
        mitigation=(
            "Check every claim against the cited source. Treat a claim with no "
            "verifiable citation as an assumption, not a fact."
        ),
    ),
    BiasDefinition(
        id="post_hoc_fallacy",
        name="Post hoc fallacy",
        how_it_appears=(
            "Because a deployment, config change or migration happened shortly "
            "before the incident, it is treated as the cause of the incident."
        ),
        detection_hint=(
            "A hypothesis whose only support is that a change happened first. "
            "No mechanism is given linking the change to the observed failure."
        ),
        mitigation=(
            "Require a mechanism, not just an ordering. Ask what in the change "
            "could produce this specific failure, and check whether the failure "
            "also occurred before the change."
        ),
    ),
    BiasDefinition(
        id="availability_bias",
        name="Availability bias",
        how_it_appears=(
            "Explanations that resemble bugs the investigator has personally "
            "seen before are preferred, simply because they come to mind first."
        ),
        detection_hint=(
            "Hypotheses that reach for familiar stock causes - connection pool "
            "exhaustion, a bad cache, a null pointer - with thin evidence "
            "specific to this incident."
        ),
        mitigation=(
            "Ask what evidence in this incident distinguishes the familiar "
            "explanation from the alternatives, rather than what makes it "
            "plausible in general."
        ),
    ),
    BiasDefinition(
        id="overconfidence_bias",
        name="Overconfidence bias",
        how_it_appears=(
            "A hypothesis is presented as settled even though the evidence is "
            "incomplete or partly contradictory."
        ),
        detection_hint=(
            "High confidence assigned despite missing data, unresolved open "
            "questions, or a hypothesis that has not yet been tested."
        ),
        mitigation=(
            "Tie the confidence level to a named piece of evidence, and lower it "
            "whenever a required check has not actually been run."
        ),
    ),
    BiasDefinition(
        id="hindsight_bias",
        name="Hindsight bias",
        how_it_appears=(
            "Once a likely cause is found, the investigation reports that it was "
            "obvious from the start, which hides how the evidence was really "
            "read at the time."
        ),
        detection_hint=(
            "A narrative that presents the conclusion as inevitable, or a "
            "timeline written from the answer backwards rather than from the "
            "evidence forwards."
        ),
        mitigation=(
            "Record what was known at each point in the timeline, and keep the "
            "hypotheses that were considered and dropped."
        ),
    ),
    BiasDefinition(
        id="base_rate_neglect",
        name="Base-rate neglect",
        how_it_appears=(
            "A rare and interesting error is treated as the cause while common, "
            "boring causes of production failure are never considered."
        ),
        detection_hint=(
            "An exotic explanation ranked above ordinary ones - bad config, "
            "expired credentials, resource limits, a dependency being down - "
            "without ruling the ordinary ones out."
        ),
        mitigation=(
            "Explicitly list the common causes for this class of failure and "
            "state why each was ruled in or out."
        ),
    ),
]

BIAS_BY_ID: Dict[str, BiasDefinition] = {b.id: b for b in BIAS_CATALOGUE}

VALID_BIAS_IDS: List[str] = [b.id for b in BIAS_CATALOGUE]


def catalogue_for_prompt() -> str:
    """Render the catalogue as the reference block used by the detector prompt."""
    blocks = []
    for bias in BIAS_CATALOGUE:
        blocks.append(
            f"- id: {bias.id}\n"
            f"  name: {bias.name}\n"
            f"  how it appears: {bias.how_it_appears}\n"
            f"  look for: {bias.detection_hint}"
        )
    return "\n".join(blocks)


def is_known(bias_id: str) -> bool:
    return bias_id in BIAS_BY_ID
