"""Tests for the citation checker.

This is the component the project's central claim rests on, so it is tested
hardest. The two failure modes that matter are opposite: passing a fabricated
quote (the tool would be endorsing a hallucination) and flagging a real one
(users learn to ignore the warnings, which is worse than not having them).
"""

from __future__ import annotations

from app.core.evidence import dedupe, normalise, verify_all, verify_one
from app.schemas import EvidenceRef

SOURCES = {
    "logs": (
        "2024-03-14 08:58:02 ERROR checkout-api  POST /api/checkout/session 500 "
        "30012ms - TimeoutError: acquiring connection from pool\n"
        "2024-03-14 09:12:38 INFO  checkout-api  starting v2.4.1 (build 8831)"
    ),
    "alerts": "[08:59] PAGE checkout-api: error_rate 12% over 5m - threshold 2%",
}


def ref(source: str, quote: str) -> EvidenceRef:
    return EvidenceRef(source=source, quote=quote)


# --- quotes that must pass --------------------------------------------------


def test_exact_quote_passes():
    assert verify_one(ref("logs", "TimeoutError: acquiring connection from pool"), SOURCES)


def test_whitespace_and_case_differences_pass():
    assert verify_one(ref("logs", "timeouterror:  ACQUIRING connection from pool"), SOURCES)


def test_quote_spanning_a_line_break_passes():
    quote = "starting v2.4.1 (build 8831)"
    assert verify_one(ref("logs", quote), SOURCES)


def test_near_match_with_dropped_words_passes():
    # Models routinely elide a token or two when quoting a long log line.
    quote = "2024-03-14 08:58:02 ERROR checkout-api POST /api/checkout/session 500"
    assert verify_one(ref("logs", quote), SOURCES)


def test_short_quote_is_not_judged():
    # "ERROR" would match almost anything; flagging it would be noise.
    assert verify_one(ref("logs", "ERROR"), SOURCES)


# --- quotes that must be flagged -------------------------------------------


def test_fabricated_quote_is_flagged():
    assert not verify_one(ref("logs", "FATAL: disk full on /var/lib/postgresql"), SOURCES)


def test_real_quote_attributed_to_wrong_source_is_flagged():
    # The text exists, but not in `alerts`. Mis-attribution is still a defect.
    assert not verify_one(ref("alerts", "TimeoutError: acquiring connection from pool"), SOURCES)


def test_citation_of_absent_source_is_flagged():
    assert not verify_one(ref("user_reports", "customers cannot check out"), SOURCES)


def test_reordered_words_are_flagged():
    # Order carries meaning in a log line, so a shuffled quote is not a match.
    assert not verify_one(ref("logs", "pool from connection acquiring TimeoutError"), SOURCES)


# --- batch behaviour --------------------------------------------------------


def test_verify_all_splits_correctly():
    refs = [
        ref("logs", "TimeoutError: acquiring connection from pool"),
        ref("logs", "FATAL: disk full on /var/lib/postgresql"),
    ]
    verified, unverified = verify_all(refs, SOURCES)
    assert len(verified) == 1
    assert len(unverified) == 1
    assert "disk full" in unverified[0].quote


def test_dedupe_ignores_formatting_differences():
    refs = [
        ref("logs", "TimeoutError: acquiring connection from pool"),
        ref("logs", "timeouterror:   acquiring connection from POOL"),
        ref("alerts", "error_rate 12% over 5m"),
    ]
    assert len(dedupe(refs)) == 2


def test_normalise_collapses_whitespace():
    assert normalise("  A   B \n C  ") == "a b c"
