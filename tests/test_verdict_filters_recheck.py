"""Verdict filters after the 2026-10-03 recheck: fix advice passes, plain verdicts fail."""
from __future__ import annotations
import pytest
from plumb import outputs


def _flagged(text: str) -> bool:
    return outputs.has_recommendation(text) or bool(outputs.desk_reject_phrases(text))


@pytest.mark.parametrize("text", [
    "The paper should be revised to report first-stage F statistics.",
    "The manuscript should be revised to address attrition.",
    "We recommend publication bias diagnostics.",
    "I recommend publication of the replication code.",
    "We recommend publication-quality figures.",
    "We recommend revisions to the theory section so the mechanism is explicit.",
    "We recommend revisions\nto the theory section.",
    "Revise the paper to report first-stage F statistics.",
    "We would recommend rejecting the null of parallel trends.",
])
def test_fix_advice_is_not_a_verdict(text):
    assert not _flagged(text)


@pytest.mark.parametrize("text", [
    "minor revisions",
    "Minor revisions.",
    "I recommend this manuscript be rejected.",
    "We recommend the manuscript be rejected.",
    "I recommend this article be accepted.",
    "I recommend that it be rejected.",
    "We recommend revisions before this can be published.",
    "I recommend publication after minor changes.",
    "The paper should be rejected.",
    "I recommend adding a placebo test. I recommend rejection.",
    "We recommend clustering at the firm level. We recommend rejection.",
])
def test_plain_verdicts_are_caught(text):
    assert _flagged(text)
