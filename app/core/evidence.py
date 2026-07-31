"""Citation checking.

The model is asked to quote the input whenever it states a fact. This module
checks that those quotes are real. It is the mechanical half of the project's
central claim - that AI output should be verified rather than trusted - and it
runs on every analysis without the user having to ask for it.

The check is deliberately forgiving about formatting (whitespace, case,
punctuation) and strict about content. A quote that survives normalisation but
still does not appear in the cited source is reported to the user.
"""

from __future__ import annotations

import re
from typing import Iterable, List, Sequence, Tuple

from app.schemas import EvidenceRef

# A quote shorter than this is not worth checking - single words like "timeout"
# match almost anything and would produce false confidence.
MIN_QUOTE_LENGTH = 8

# Fraction of the quote's words that must appear in the source, in order, for a
# near-match to count. Log lines get re-wrapped and truncated constantly, so an
# exact substring test alone produces too many false alarms.
NEAR_MATCH_THRESHOLD = 0.8


def normalise(text: str) -> str:
    """Collapse whitespace and case so formatting differences do not matter."""
    return re.sub(r"\s+", " ", text).strip().lower()


def _tokens(text: str) -> List[str]:
    return re.findall(r"[a-z0-9_./:-]+", normalise(text))


def _ordered_overlap(quote: str, source: str) -> float:
    """Fraction of the quote's tokens found in the source, preserving order.

    Walking the source with a single cursor means "a b c" matches "a x b x c"
    but not "c b a" - order carries meaning in a log file.
    """
    quote_tokens = _tokens(quote)
    if not quote_tokens:
        return 0.0

    source_tokens = _tokens(source)
    cursor = 0
    matched = 0
    for token in quote_tokens:
        try:
            cursor = source_tokens.index(token, cursor) + 1
            matched += 1
        except ValueError:
            continue
    return matched / len(quote_tokens)


def verify_one(ref: EvidenceRef, sources: dict[str, str]) -> bool:
    """True when `ref.quote` can be found in the source it claims to come from."""
    if len(ref.quote.strip()) < MIN_QUOTE_LENGTH:
        # Too short to verify meaningfully; don't cry wolf.
        return True

    source_text = sources.get(ref.source)
    if source_text is None:
        # Cited a field that was never provided. That is always a real problem.
        return False

    if normalise(ref.quote) in normalise(source_text):
        return True

    return _ordered_overlap(ref.quote, source_text) >= NEAR_MATCH_THRESHOLD


def verify_all(
    refs: Iterable[EvidenceRef], sources: dict[str, str]
) -> Tuple[List[EvidenceRef], List[EvidenceRef]]:
    """Split citations into (verified, unverified)."""
    verified: List[EvidenceRef] = []
    unverified: List[EvidenceRef] = []
    for ref in refs:
        (verified if verify_one(ref, sources) else unverified).append(ref)
    return verified, unverified


def collect_refs(*groups: Sequence[object]) -> List[EvidenceRef]:
    """Gather every EvidenceRef hanging off a set of result objects.

    Walks one level into each item and picks up any attribute holding a list of
    EvidenceRef, so new schema fields are covered without touching this code.
    """
    found: List[EvidenceRef] = []
    for group in groups:
        for item in group:
            if isinstance(item, EvidenceRef):
                found.append(item)
                continue
            for value in vars(item).values() if hasattr(item, "__dict__") else []:
                if isinstance(value, list):
                    found.extend(v for v in value if isinstance(v, EvidenceRef))
    return found


def dedupe(refs: Iterable[EvidenceRef]) -> List[EvidenceRef]:
    """Drop duplicate citations, keeping first-seen order."""
    seen: set[tuple[str, str]] = set()
    unique: List[EvidenceRef] = []
    for ref in refs:
        key = (ref.source, normalise(ref.quote))
        if key not in seen:
            seen.add(key)
            unique.append(ref)
    return unique
