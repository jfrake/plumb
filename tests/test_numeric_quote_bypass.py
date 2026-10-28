"""
Tests for the numeric quote verification bypass fix.

PROBLEM: A numeric quote with high text similarity to a passage but wrong numbers
was being accepted as FUZZY. The text ratio >= MIN_MATCH_RATIO_NUMERIC (0.92)
was sufficient for FUZZY status without any check that the numbers themselves
matched the source passage.

FIX: For numeric quotes, the numbers must verify before the quote can be FUZZY or
CSV_VERIFIED. Verification = either (a) all distinct numbers in the quote appear
in the best matched passage at token boundaries, OR (b) check_against_csvs confirms
all numbers are in the CSV corpus. If neither route verifies, status must be
UNVERIFIABLE (or NUMERIC_MISMATCH treated as unverifiable by the gate).

NOTE on passage length: the text-ratio threshold of 0.92 means a one-digit
difference only beats the threshold when the surrounding text is long enough that
the edit distance is small relative to total length. All "bypass" test cases use
a long passage to ensure the text ratio actually exceeds 0.92, which is the
condition that exposes the bug.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "skills/review/scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

vq = importlib.import_module("verify_quotes")

# Statuses that the gate treats as verified (not blocking).
ACCEPTED_STATUSES = {"EXACT", "FUZZY", "CSV_VERIFIED"}
# Statuses that the gate treats as failures (must trigger nonzero exit).
REJECTED_STATUSES = {"UNVERIFIABLE", "NUMERIC_MISMATCH"}

# Long prose template that ensures text ratio > 0.92 when only one digit differs.
# With ~220 chars and a single-char digit swap, ratio ≈ 0.995 (well above 0.92).
_LONG_TEMPLATE = (
    "the estimated coefficient for the primary independent variable is {n} "
    "standard deviations above zero and the effect is highly significant at "
    "the one percent level confirming the theoretical prediction of the "
    "structural model estimated with fixed effects and clustered standard errors"
)


def _make_quote_dict(quote: str, line_num: int = 1) -> dict:
    return {
        "quote": quote,
        "line_num": line_num,
        "pattern": '"...',
        "is_numeric": bool(vq.NUMERIC_PATTERN.search(quote)),
    }


# ---------------------------------------------------------------------------
# Test 1: numeric quote with wrong number and high text ratio must NOT be FUZZY
# ---------------------------------------------------------------------------

class TestNumericWrongNumberNotFuzzy:
    """
    Paper says 0.31; review quotes 0.30.  The surrounding text is long enough
    that the text ratio beats 0.92, which is the bypass condition.  With the
    fix in place the quote must NOT be accepted as FUZZY.
    """

    PAPER_TEXT = _LONG_TEMPLATE.format(n="0.31")
    REVIEW_QUOTE = _LONG_TEMPLATE.format(n="0.30")

    def _verify_ratio_beats_threshold(self):
        """Sanity-check: confirm the bypass condition actually holds."""
        _, ratio = vq.find_best_match(self.REVIEW_QUOTE, self.PAPER_TEXT)
        assert ratio >= vq.MIN_MATCH_RATIO_NUMERIC, (
            f"Test precondition failed: expected ratio >= {vq.MIN_MATCH_RATIO_NUMERIC}, "
            f"got {ratio:.4f}. The test passage is not long enough to expose the bypass."
        )

    def test_numeric_quote_wrong_number_not_fuzzy(self):
        """Wrong number (0.30 vs 0.31) with text ratio > 0.92 -> UNVERIFIABLE or NUMERIC_MISMATCH."""
        self._verify_ratio_beats_threshold()

        quote_dict = _make_quote_dict(self.REVIEW_QUOTE)
        assert quote_dict["is_numeric"], "Quote must be detected as numeric"

        results = vq.verify_all_quotes(
            [quote_dict],
            paper_text=self.PAPER_TEXT,
            csv_dir=None,
        )
        assert len(results) == 1
        status = results[0]["status"]

        assert status not in ACCEPTED_STATUSES, (
            f"Numeric quote with wrong number (0.30) should not be accepted; "
            f"paper has 0.31, quote has 0.30, text ratio > 0.92, but status={status}. "
            "This is the bypass bug: high text ratio accepted a wrong number as FUZZY."
        )

    def test_numeric_quote_wrong_number_csv_also_absent_not_fuzzy(self, tmp_path):
        """Wrong number (0.30) absent from CSV corpus -> must not be accepted even with CSV."""
        self._verify_ratio_beats_threshold()

        csv_dir = tmp_path / "csvs"
        csv_dir.mkdir()
        # CSV contains 0.31 (the correct number), NOT 0.30 (the wrong number).
        (csv_dir / "table1.csv").write_text("coef\n0.31\n", encoding="utf-8")

        quote_dict = _make_quote_dict(self.REVIEW_QUOTE)
        results = vq.verify_all_quotes(
            [quote_dict],
            paper_text=self.PAPER_TEXT,
            csv_dir=str(csv_dir),
        )
        assert len(results) == 1
        status = results[0]["status"]

        assert status not in ACCEPTED_STATUSES, (
            f"Wrong number 0.30: not in passage (paper has 0.31) and not in CSV "
            f"(CSV has 0.31 only), but got status={status}. Should be rejected."
        )


# ---------------------------------------------------------------------------
# Test 2: numeric quote with correct number in passage -> accepted
# ---------------------------------------------------------------------------

class TestNumericRightNumberInPassageOk:
    """
    Review quotes the correct number (0.31) matching the paper passage exactly.
    High text similarity PLUS matching number -> accepted (FUZZY or CSV_VERIFIED).
    """

    PAPER_TEXT = _LONG_TEMPLATE.format(n="0.31")
    REVIEW_QUOTE = _LONG_TEMPLATE.format(n="0.31")

    def test_numeric_quote_right_number_in_passage_ok(self):
        """Correct number (0.31) present in passage -> status is FUZZY or better."""
        quote_dict = _make_quote_dict(self.REVIEW_QUOTE)
        assert quote_dict["is_numeric"], "Quote must be detected as numeric"

        results = vq.verify_all_quotes(
            [quote_dict],
            paper_text=self.PAPER_TEXT,
            csv_dir=None,
        )
        assert len(results) == 1
        status = results[0]["status"]

        assert status in ACCEPTED_STATUSES, (
            f"Correct number (0.31) matches passage; expected FUZZY or EXACT but got {status}"
        )


# ---------------------------------------------------------------------------
# Test 3: number absent from passage but present in CSV -> CSV_VERIFIED
# ---------------------------------------------------------------------------

class TestNumericQuoteVerifiedViaCsv:
    """
    The number in the review quote does not appear in the matched prose passage
    (the text ratio is below threshold, so the passage-number route is not
    applicable) but the number IS present in the CSV corpus.
    The CSV route must verify and return CSV_VERIFIED.
    """

    # Short paper text: the quote will not reach text-ratio threshold, so we
    # depend entirely on the CSV route. The number 0.47 exists only in the CSV.
    PAPER_TEXT = (
        "We find a statistically significant result. The model fits well. "
        "Further analysis supports the conclusion of the empirical study."
    )
    REVIEW_QUOTE = "we find a statistically significant result with coefficient 0.47"

    def test_numeric_quote_verified_via_csv(self, tmp_path):
        """Number absent from prose passage but in CSV -> CSV_VERIFIED."""
        csv_dir = tmp_path / "csvs"
        csv_dir.mkdir()
        (csv_dir / "table1.csv").write_text("coef\n0.47\n", encoding="utf-8")

        quote_dict = _make_quote_dict(self.REVIEW_QUOTE)
        assert quote_dict["is_numeric"], "Quote must be detected as numeric"

        results = vq.verify_all_quotes(
            [quote_dict],
            paper_text=self.PAPER_TEXT,
            csv_dir=str(csv_dir),
        )
        assert len(results) == 1
        status = results[0]["status"]

        assert status == "CSV_VERIFIED", (
            f"Number 0.47 is in CSV corpus; expected CSV_VERIFIED but got {status}"
        )


# ---------------------------------------------------------------------------
# Test 4: pure-prose (non-numeric) quote with high similarity -> still FUZZY
# ---------------------------------------------------------------------------

class TestProseQuoteUnchanged:
    """
    Non-numeric quotes with high text similarity must still be accepted as FUZZY.
    The fix must not affect pure-prose matching behavior.
    """

    # Long prose without any numbers to ensure is_numeric is False and ratio beats 0.80.
    PAPER_TEXT = (
        "The theoretical framework draws on institutional theory and resource "
        "dependence theory and provides a coherent account of organizational "
        "behavior in competitive markets where firms must balance efficiency "
        "and legitimacy considerations across multiple stakeholder audiences."
    )
    REVIEW_QUOTE = (
        "the theoretical framework draws on institutional theory and resource "
        "dependence theory and provides a coherent account of organizational "
        "behavior in competitive markets where firms must balance efficiency"
    )

    def test_prose_quote_unchanged(self):
        """Non-numeric quote with high text similarity -> FUZZY (unchanged behavior)."""
        quote_dict = _make_quote_dict(self.REVIEW_QUOTE)
        assert not quote_dict["is_numeric"], (
            f"Quote should be non-numeric but is_numeric={quote_dict['is_numeric']}"
        )

        results = vq.verify_all_quotes(
            [quote_dict],
            paper_text=self.PAPER_TEXT,
            csv_dir=None,
        )
        assert len(results) == 1
        status = results[0]["status"]

        assert status in ACCEPTED_STATUSES, (
            f"Prose quote with high text similarity should be FUZZY or EXACT; got {status}"
        )
