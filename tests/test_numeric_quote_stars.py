"""
Tests for FIX 3: significance-star verification in numeric quotes.

Choice: option (a) - verify star tokens explicitly alongside numbers.
A quote like "b=0.30***" must have both its number (0.30) AND its significance
stars (***) verified against the matched passage or CSV corpus.  A passage that
contains 0.30 but NOT *** is insufficient; the quote must be UNVERIFIABLE.

Rationale for option (a) over option (b):
  Fabricated significance stars are a real failure mode: a reviewer might quote
  "b=0.30***" when the paper reports "b=0.30" (p=0.08, n.s.) or "b=0.30*".
  Treating stars as verifiable content rather than decoration catches such
  misrepresentations.  Option (b) (remove stars from NUMERIC_PATTERN) would
  silently allow a stars-only quote to escape numeric handling, but would not
  fix the underlying problem that a mixed quote's stars go unchecked.

Star-verification spec:
  - A star sequence (* or ** or ***) present in the quote must appear somewhere
    in the matched passage for the quote to pass the passage route.
  - If the passage lacks the stars but the number is present elsewhere, the quote
    is UNVERIFIABLE (stars unverified).
  - A stars-only emphasis quote like "***important note***" contains no numbers,
    so _numbers_verified_in_passage returns True vacuously.  To avoid dragging
    it into false numeric handling, stars that appear only as emphasis (no digit
    content in the quote) must not force UNVERIFIABLE.  The fix should leave
    the is_numeric flag True for such quotes (NUMERIC_PATTERN still fires) but
    the vacuous number check means the stars do not independently block it.
    Actually: the cleaner contract is that the passage route checks numbers AND
    stars together.  For a stars-only quote, no numbers => number check vacuous
    => only star check matters.  If the passage contains "***" emphasis too, it
    passes; if not, it fails.  This is intentional: a reviewer quoting "***" out
    of context is unusual and the gate is correct to scrutinize it.

These tests drive the implementation of star verification via
_numbers_and_stars_verified_in_passage (or equivalent).
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "skills/review/scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

vq = importlib.import_module("verify_quotes")

ACCEPTED_STATUSES = {"EXACT", "FUZZY", "CSV_VERIFIED"}
REJECTED_STATUSES = {"UNVERIFIABLE", "NUMERIC_MISMATCH"}

# Long prose used so text-ratio threshold is met.
_LONG_TEMPLATE = (
    "the estimated coefficient on the main predictor is {coef} and the effect "
    "is {sig} at the one percent level confirming the theoretical prediction of "
    "the structural model estimated with entity fixed effects and clustered standard "
    "errors across all observed time periods in the panel data"
)


def _make_quote_dict(quote: str, line_num: int = 1) -> dict:
    return {
        "quote": quote,
        "line_num": line_num,
        "pattern": '"...',
        "is_numeric": bool(vq.NUMERIC_PATTERN.search(quote)),
    }


# ---------------------------------------------------------------------------
# Test 1: stars in quote but NOT in passage -> UNVERIFIABLE
# ---------------------------------------------------------------------------

class TestStarsInQuoteNotInPassage:
    """
    Review quotes 'b=0.30***' but paper passage has 'b=0.30' (no stars).
    The number is verified but the stars are not.  Status must be UNVERIFIABLE.
    """

    # Paper has the coefficient but no significance stars
    PAPER_TEXT = _LONG_TEMPLATE.format(coef="0.30", sig="significant")
    # Review quotes the coefficient with three stars attached
    REVIEW_QUOTE = _LONG_TEMPLATE.format(coef="0.30***", sig="significant")

    def test_stars_unverified_when_passage_lacks_stars(self):
        """Number (0.30) is in passage; stars (***) are not -> UNVERIFIABLE."""
        # Precondition: the quote is detected as numeric (has both number and stars).
        quote_dict = _make_quote_dict(self.REVIEW_QUOTE)
        assert quote_dict["is_numeric"], (
            "Quote with '0.30***' must be detected as numeric"
        )

        # Precondition: text ratio beats threshold (stars are a tiny difference).
        _, ratio = vq.find_best_match(self.REVIEW_QUOTE, self.PAPER_TEXT)
        assert ratio >= vq.MIN_MATCH_RATIO_NUMERIC, (
            f"Test precondition failed: text ratio {ratio:.4f} < {vq.MIN_MATCH_RATIO_NUMERIC}. "
            "The passage is too short to expose the bypass."
        )

        results = vq.verify_all_quotes(
            [quote_dict],
            paper_text=self.PAPER_TEXT,
            csv_dir=None,
        )
        assert len(results) == 1
        status = results[0]["status"]

        assert status not in ACCEPTED_STATUSES, (
            f"Quote 'b=0.30***' whose passage has '0.30' but no stars was accepted "
            f"with status={status}.  Stars must be verified: the gate should return "
            "UNVERIFIABLE when stars are in the quote but absent from the passage."
        )


# ---------------------------------------------------------------------------
# Test 2: stars in quote AND in passage -> FUZZY (accepted)
# ---------------------------------------------------------------------------

class TestStarsInQuoteAndInPassage:
    """
    Review quotes 'b=0.30***' and passage also has '***'.
    Both number and stars verified -> FUZZY.
    """

    PAPER_TEXT = _LONG_TEMPLATE.format(coef="0.30***", sig="highly significant")
    REVIEW_QUOTE = _LONG_TEMPLATE.format(coef="0.30***", sig="highly significant")

    def test_stars_and_number_both_in_passage_accepted(self):
        """Number and stars both present in passage -> FUZZY or EXACT."""
        quote_dict = _make_quote_dict(self.REVIEW_QUOTE)
        assert quote_dict["is_numeric"], "Quote with '0.30***' must be numeric"

        results = vq.verify_all_quotes(
            [quote_dict],
            paper_text=self.PAPER_TEXT,
            csv_dir=None,
        )
        assert len(results) == 1
        status = results[0]["status"]

        assert status in ACCEPTED_STATUSES, (
            f"Quote 'b=0.30***' with passage containing both '0.30' and '***' "
            f"should be accepted; got status={status}"
        )


# ---------------------------------------------------------------------------
# Test 3: number wrong AND stars wrong -> UNVERIFIABLE (regression)
# ---------------------------------------------------------------------------

class TestWrongNumberAndWrongStars:
    """
    Paper has 'b=0.31*'; review quotes 'b=0.30***'.
    Both number and stars mismatch -> UNVERIFIABLE.
    """

    PAPER_TEXT = _LONG_TEMPLATE.format(coef="0.31*", sig="marginally significant")
    REVIEW_QUOTE = _LONG_TEMPLATE.format(coef="0.30***", sig="marginally significant")

    def test_wrong_number_and_wrong_stars_rejected(self):
        """Neither the number nor the stars match the passage -> UNVERIFIABLE."""
        quote_dict = _make_quote_dict(self.REVIEW_QUOTE)
        assert quote_dict["is_numeric"], "Quote with '0.30***' must be numeric"

        results = vq.verify_all_quotes(
            [quote_dict],
            paper_text=self.PAPER_TEXT,
            csv_dir=None,
        )
        assert len(results) == 1
        status = results[0]["status"]

        assert status not in ACCEPTED_STATUSES, (
            f"Quote with wrong number (0.30 vs 0.31) and wrong stars (*** vs *) "
            f"should not be accepted; got status={status}"
        )


# ---------------------------------------------------------------------------
# Test 4: stars-only emphasis quote is treated as numeric (NUMERIC_PATTERN fires)
#         but number check is vacuous, so passage text similarity governs.
# ---------------------------------------------------------------------------

class TestStarsOnlyEmphasisQuote:
    """
    A quote that contains only stars but no numbers is detected as numeric
    (NUMERIC_PATTERN fires on [*]{1,3}).  With no digit tokens, the number
    portion of the check is vacuous.  Whether it passes depends on whether
    stars appear in the passage.
    """

    PAPER_TEXT = (
        "the authors highlight several key contributions marked with emphasis "
        "in the original manuscript including the main theoretical claim and "
        "the empirical validation both of which are central to the overall argument"
    )

    def test_stars_only_quote_is_numeric(self):
        """NUMERIC_PATTERN detects stars -> is_numeric True."""
        quote_dict = _make_quote_dict("***important note***")
        assert quote_dict["is_numeric"], (
            "Stars-only quote should be detected as numeric by NUMERIC_PATTERN"
        )

    def test_stars_only_quote_not_in_passage_unverifiable(self):
        """Stars-only quote whose passage has no stars -> UNVERIFIABLE (stars unverified)."""
        # The paper text contains no stars; the quote has only stars.
        quote_dict = {
            "quote": "***important note***",
            "line_num": 1,
            "pattern": '"...',
            "is_numeric": True,
        }
        results = vq.verify_all_quotes(
            [quote_dict],
            paper_text=self.PAPER_TEXT,
            csv_dir=None,
        )
        assert len(results) == 1
        status = results[0]["status"]
        # Stars in quote, none in passage -> stars unverified -> should not be
        # accepted as if it were a verified numeric quote.
        assert status not in ACCEPTED_STATUSES, (
            f"Stars-only quote with no stars in passage should not be accepted; "
            f"got status={status}"
        )
