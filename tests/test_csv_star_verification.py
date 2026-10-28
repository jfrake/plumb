"""
Tests for CSV-route significance-star verification.

BUG: check_against_csvs() verified only digit tokens from the quote, ignoring
significance stars. A quote like "b = 0.30***" whose number (0.30) is in the CSV
corpus but whose stars (***) are NOT present was returned as verified, letting a
fabricated significance level reach CSV_VERIFIED status.

FIX: check_against_csvs() must also require every distinct star sequence present
in the quote to appear in the CSV corpus. Stars absent from the corpus cause the
function to return False, so the quote falls through to UNVERIFIABLE.

Three test cases:
  1. test_csv_route_rejects_fabricated_stars  - stars in quote, absent from CSV -> UNVERIFIABLE
  2. test_csv_route_accepts_matching_stars    - stars in quote, present in CSV  -> CSV_VERIFIED
  3. test_csv_route_plain_number_unchanged    - no stars, number in CSV          -> CSV_VERIFIED
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


def _make_quote_dict(quote: str, line_num: int = 1) -> dict:
    return {
        "quote": quote,
        "line_num": line_num,
        "pattern": '"...',
        "is_numeric": bool(vq.NUMERIC_PATTERN.search(quote)),
    }


# ---------------------------------------------------------------------------
# Helpers: a fuzzy paper passage that contains the words but NOT the stars
# (forces the CSV route when stars are the only mismatch).
# ---------------------------------------------------------------------------

# Prose passage that matches the quote text well enough to attempt passage-route
# verification, but lacks significance stars. The passage-route star check fails,
# so the CSV route is tried.  The CSV route is the unit under test here.
_PROSE_WITHOUT_STARS = (
    "the coefficient is 0 30 and the result is highly significant confirming "
    "the hypothesis of the model estimated with fixed effects and clustered errors "
    "across all firms in the sample period of the study consistent with prior work"
)

# A quote whose words substantially match the passage above (high Jaccard overlap)
# but which includes stars that are absent from the passage.
_QUOTE_WITH_STARS = "the coefficient is 0.30***"


# ---------------------------------------------------------------------------
# Test 1: fabricated stars -> CSV_VERIFIED should NOT be granted
# ---------------------------------------------------------------------------

class TestCsvRouteRejectsFabricatedStars:
    """
    Quote contains 0.30***.  CSV corpus has 0.30 but NOT ***.
    The passage route fails (stars absent from passage).
    The CSV route must also fail (stars absent from corpus) -> UNVERIFIABLE.
    """

    def test_csv_route_rejects_fabricated_stars(self, tmp_path):
        """Number in CSV but stars absent from CSV -> status must be UNVERIFIABLE."""
        csv_dir = tmp_path / "csvs"
        csv_dir.mkdir()
        # CSV contains the number but no stars.
        (csv_dir / "table1.csv").write_text("coef\n0.30\n", encoding="utf-8")

        quote_dict = _make_quote_dict(_QUOTE_WITH_STARS)
        assert quote_dict["is_numeric"], "Quote with 0.30*** must be detected as numeric"

        results = vq.verify_all_quotes(
            [quote_dict],
            paper_text=_PROSE_WITHOUT_STARS,
            csv_dir=str(csv_dir),
        )
        assert len(results) == 1
        status = results[0]["status"]

        assert status not in ACCEPTED_STATUSES, (
            f"Quote '0.30***' with CSV containing only '0.30' (no stars) "
            f"must not be accepted; got status={status}. "
            "Fabricated significance stars must cause UNVERIFIABLE."
        )
        assert status == "UNVERIFIABLE", (
            f"Expected UNVERIFIABLE, got {status}"
        )


# ---------------------------------------------------------------------------
# Test 2: matching stars in CSV -> CSV_VERIFIED
# ---------------------------------------------------------------------------

class TestCsvRouteAcceptsMatchingStars:
    """
    Quote contains 0.30***.  CSV corpus contains '0.30***' (both number and stars).
    The passage route fails (stars absent from the fuzzy prose passage).
    The CSV route must succeed -> CSV_VERIFIED.
    """

    def test_csv_route_accepts_matching_stars(self, tmp_path):
        """Number AND stars both present in CSV -> CSV_VERIFIED."""
        csv_dir = tmp_path / "csvs"
        csv_dir.mkdir()
        # CSV contains the full token including stars.
        (csv_dir / "table1.csv").write_text("coef\n0.30***\n", encoding="utf-8")

        quote_dict = _make_quote_dict(_QUOTE_WITH_STARS)
        assert quote_dict["is_numeric"], "Quote with 0.30*** must be detected as numeric"

        results = vq.verify_all_quotes(
            [quote_dict],
            paper_text=_PROSE_WITHOUT_STARS,
            csv_dir=str(csv_dir),
        )
        assert len(results) == 1
        status = results[0]["status"]

        assert status == "CSV_VERIFIED", (
            f"Quote '0.30***' with CSV containing '0.30***' should be CSV_VERIFIED; "
            f"got status={status}"
        )


# ---------------------------------------------------------------------------
# Test 3: plain number, no stars -- no regression to existing behavior
# ---------------------------------------------------------------------------

class TestCsvRoutePlainNumberUnchanged:
    """
    Quote contains only '0.30' (no stars).  CSV corpus contains '0.30'.
    Stars check is vacuous (no stars in quote).
    Existing CSV-verification behavior must be preserved -> CSV_VERIFIED.
    """

    _PLAIN_QUOTE = "0.30"
    # Short paper text: text ratio will not reach threshold, so CSV route is taken.
    _PAPER_TEXT = "The model produces results consistent with theoretical predictions."

    def test_csv_route_plain_number_unchanged(self, tmp_path):
        """Number without stars, number in CSV -> CSV_VERIFIED (no regression)."""
        csv_dir = tmp_path / "csvs"
        csv_dir.mkdir()
        (csv_dir / "table1.csv").write_text("coef\n0.30\n", encoding="utf-8")

        quote_dict = _make_quote_dict(self._PLAIN_QUOTE)

        results = vq.verify_all_quotes(
            [quote_dict],
            paper_text=self._PAPER_TEXT,
            csv_dir=str(csv_dir),
        )
        assert len(results) == 1
        status = results[0]["status"]

        assert status == "CSV_VERIFIED", (
            f"Plain-number quote '0.30' with '0.30' in CSV should be CSV_VERIFIED; "
            f"got status={status}"
        )
