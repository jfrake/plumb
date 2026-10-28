"""
Tests for strict numeric-quote matching and citation gate strictness.

verify_quotes.py must require ALL material numbers in a numeric quote to be
present in the CSV corpus, not just one.

verify_citations.py must return nonzero when:
  - Body has in-text citations but no REFERENCES section.
  - Dangling body citations exist (in body but absent from REFERENCES).
  - COULD_NOT_SEARCH outcomes are present (network/lookup failures).
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

import pytest

# Insert scripts directory on path so we can import directly.
SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "skills/review/scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import importlib

vq = importlib.import_module("verify_quotes")
vc = importlib.import_module("verify_citations")


# ---------------------------------------------------------------------------
# Numeric quote matching must require ALL numbers
# ---------------------------------------------------------------------------

class TestNumericQuoteStrictness:
    """check_against_csvs must return False when only a subset of numbers are present."""

    QUOTE = "the coefficient is 0.30 (SE 0.10), p=0.04"

    def _csv_dir_with(self, tmp_path: Path, rows: list[str]) -> Path:
        csv_file = tmp_path / "table1.csv"
        csv_file.write_text("\n".join(rows) + "\n", encoding="utf-8")
        return tmp_path

    def test_partial_numbers_not_verified(self, tmp_path):
        """CSV contains 0.30 but NOT 0.10 or 0.04 -> NOT verified."""
        csv_dir = self._csv_dir_with(
            tmp_path, ["coef,se,pval", "0.30,0.05,0.01"]
        )
        found, details = vq.check_against_csvs(self.QUOTE, str(csv_dir))
        assert not found, (
            f"Expected check_against_csvs to return False when only 1/3 numbers "
            f"are present, but got found={found}, details={details}"
        )

    def test_all_numbers_verified(self, tmp_path):
        """CSV contains 0.30, 0.10, and 0.04 -> verified."""
        csv_dir = self._csv_dir_with(
            tmp_path, ["coef,se,pval", "0.30,0.10,0.04"]
        )
        found, details = vq.check_against_csvs(self.QUOTE, str(csv_dir))
        assert found, (
            f"Expected check_against_csvs to return True when all numbers present, "
            f"but got found={found}, details={details}"
        )

    def test_numbers_across_multiple_csvs_verified(self, tmp_path):
        """Numbers may span multiple CSV files and still count as fully verified."""
        (tmp_path / "table1.csv").write_text("coef\n0.30\n", encoding="utf-8")
        (tmp_path / "table2.csv").write_text("se,pval\n0.10,0.04\n", encoding="utf-8")
        found, details = vq.check_against_csvs(self.QUOTE, str(tmp_path))
        assert found, (
            f"All numbers present across two CSVs but got found={found}, details={details}"
        )

    def test_verify_all_quotes_marks_partial_as_unverifiable(self, tmp_path):
        """
        End-to-end: a numeric quote against a CSV with only one matching number
        must NOT get status CSV_VERIFIED.
        """
        # CSV has only 0.30
        csv_dir = tmp_path / "csvs"
        csv_dir.mkdir()
        (csv_dir / "table1.csv").write_text("coef\n0.30\n", encoding="utf-8")

        quote_dict = {
            "quote": self.QUOTE,
            "line_num": 1,
            "pattern": '"...',
            "is_numeric": True,
        }
        # Use empty paper text so Tier 1 and Tier 2 both fail, driving us to CSV check.
        results = vq.verify_all_quotes([quote_dict], paper_text="", csv_dir=str(csv_dir))
        assert len(results) == 1
        status = results[0]["status"]
        assert status != "CSV_VERIFIED", (
            f"Quote with only 1/3 numbers in CSV should not be CSV_VERIFIED; got {status}"
        )

    def test_verify_all_quotes_csv_verified_when_all_present(self, tmp_path):
        """When all numbers are present, CSV_VERIFIED should be returned."""
        csv_dir = tmp_path / "csvs"
        csv_dir.mkdir()
        (csv_dir / "table1.csv").write_text("coef,se,pval\n0.30,0.10,0.04\n", encoding="utf-8")

        quote_dict = {
            "quote": self.QUOTE,
            "line_num": 1,
            "pattern": '"...',
            "is_numeric": True,
        }
        results = vq.verify_all_quotes([quote_dict], paper_text="", csv_dir=str(csv_dir))
        assert len(results) == 1
        status = results[0]["status"]
        assert status == "CSV_VERIFIED", (
            f"All 3 numbers in CSV; expected CSV_VERIFIED but got {status}"
        )


# ---------------------------------------------------------------------------
# Citation gate exit codes
# ---------------------------------------------------------------------------

class TestCitationGateExitCodes:
    """verify_citations.verify_references must return nonzero for structural defects."""

    # The function under test: verify_references(review_path, output_path) -> int

    def _write_review(self, path: Path, text: str) -> Path:
        path.write_text(textwrap.dedent(text), encoding="utf-8")
        return path

    def test_body_citations_no_references_section_nonzero(self, tmp_path):
        """Body has Smith (2020) but NO REFERENCES section -> nonzero.

        Citation format used is the one that extract_body_citations detects:
        'Author (Year)' with the year in parentheses following the author name.
        """
        review = self._write_review(
            tmp_path / "review.txt",
            """\
The findings support the theory Smith (2020). This is significant.
""",
        )
        out = tmp_path / "out.md"
        code = vc.verify_references(str(review), str(out))
        assert code != 0, (
            "Expected nonzero exit when body has citations but no REFERENCES section, "
            f"but got code={code}"
        )

    def test_no_citations_no_references_clean(self, tmp_path):
        """No citations and no REFERENCES -> clean exit (existing behavior preserved)."""
        review = self._write_review(
            tmp_path / "review.txt",
            """\
            The paper is well-written. The contribution is clear.
            """,
        )
        out = tmp_path / "out.md"
        code = vc.verify_references(str(review), str(out))
        # No body citations, no references -> no defect to report.
        assert code == 0, (
            f"Expected 0 for review with no citations and no REFERENCES, got {code}"
        )

    def test_dangling_body_citation_nonzero(self, tmp_path):
        """
        Body cites (Jones 2018) and REFERENCES exists but does not include Jones 2018
        -> nonzero (dangling citation).
        """
        review = self._write_review(
            tmp_path / "review.txt",
            """\
            The results are consistent with Jones (2018).

            REFERENCES

            Smith, J. (2020). A paper on things. Journal of Things, 1(1), 1-20.
            """,
        )
        out = tmp_path / "out.md"
        code = vc.verify_references(str(review), str(out))
        assert code != 0, (
            f"Expected nonzero for dangling body citation, got code={code}"
        )

    def test_matching_references_section_passes(self, tmp_path):
        """
        Minimal well-formed review: body citation matches a REFERENCES entry.
        The gate should not fire for structural defects (network results irrelevant here).
        We check only that the function returns an int (structural check passes).
        Note: this test calls the network and may return nonzero if the paper is not
        found, but it must NOT fail due to missing REFERENCES or dangling citations.
        """
        review = self._write_review(
            tmp_path / "review.txt",
            """\
            The methodology follows Smith (2020).

            REFERENCES

            Smith, J. (2020). A study of methods. Journal of Methods, 1(1), 1-10.
            """,
        )
        out = tmp_path / "out.md"
        code = vc.verify_references(str(review), str(out))
        # Code may be nonzero if the paper is NOT_FOUND on network, but the report
        # must exist and structural checks must not inject extra errors.
        assert isinstance(code, int), f"Expected int return, got {type(code)}"
        # Confirm no dangling citations reported in the output
        report_text = out.read_text(encoding="utf-8")
        assert "Dangling Body Citations" not in report_text or "Smith" not in report_text.split("Dangling")[1].split("##")[0], \
            "Smith 2020 should not appear as a dangling citation when present in REFERENCES"

    def test_content_defect_exits_1_not_found(self, tmp_path, monkeypatch):
        """
        NOT_FOUND (a parseable reference that returns no database match) is a content
        defect: verify_references must return exit 1 (not 2).

        search_paper returns ([], None, False): reachable but empty (API answered HTTP 200
        with zero results), so the reference is NOT_FOUND, not SEARCH_UNAVAILABLE.
        """
        monkeypatch.setattr(vc, "search_paper", lambda *a, **kw: ([], None, False))

        review = self._write_review(
            tmp_path / "review.txt",
            """\
The findings are clear.

REFERENCES

Smith, J. (2020). A paper on methods. Journal of Methods, 1(1), 1-10.
""",
        )
        out = tmp_path / "out.md"
        code = vc.verify_references(str(review), str(out))
        # Parseable ref + no network result -> NOT_FOUND (content defect) -> exit 1.
        assert code == 1, (
            f"Expected exit 1 for NOT_FOUND content defect, got {code}"
        )

    def test_could_not_search_exits_2_not_1(self, tmp_path, monkeypatch):
        """
        COULD_NOT_SEARCH (reference with no extractable author/title/year) is an
        infrastructure/parse failure: verify_references must return exit 2 (not 1).
        The reference used here has no parseable year, author, or title fragment, so
        the extractor produces an empty query and the status is COULD_NOT_SEARCH
        WITHOUT ever calling search_paper.
        """
        # search_paper should not be called for a COULD_NOT_SEARCH reference, but
        # patch it anyway to guard against accidental calls returning NOT_FOUND.
        # Return ([], None, False): reachable-but-empty, so any accidental call would
        # produce NOT_FOUND rather than SEARCH_UNAVAILABLE.
        monkeypatch.setattr(vc, "search_paper", lambda *a, **kw: ([], None, False))

        # A reference that yields no searchable fields: no year in parens, no
        # recognisable author, no title fragment the extractor can parse.
        # "Xyxyxy" with no year ensures last_names=[], title_fragment=None, year=None
        # and query is empty -> COULD_NOT_SEARCH.
        review = self._write_review(
            tmp_path / "review.txt",
            """\
The paper is good.

REFERENCES

Xyxyxy zyzy wqwq mmmm.
""",
        )
        out = tmp_path / "out.md"
        code = vc.verify_references(str(review), str(out))
        assert code == 2, (
            f"Expected exit 2 for COULD_NOT_SEARCH (infra/parse failure), got {code}"
        )

    def test_missing_references_exits_1(self, tmp_path):
        """Body citations with no REFERENCES section is a content defect: exit 1."""
        review = self._write_review(
            tmp_path / "review.txt",
            """\
The findings support Smith (2020).
""",
        )
        out = tmp_path / "out.md"
        code = vc.verify_references(str(review), str(out))
        assert code == 1, (
            f"Expected exit 1 when body has citations but REFERENCES section is absent, got {code}"
        )

    def test_dangling_citation_exits_1(self, tmp_path):
        """Dangling body citation (in text but not in REFERENCES) is a content defect: exit 1."""
        review = self._write_review(
            tmp_path / "review.txt",
            """\
The results align with Jones (2018).

REFERENCES

Smith, J. (2020). A paper on things. Journal of Things, 1(1), 1-20.
""",
        )
        out = tmp_path / "out.md"
        code = vc.verify_references(str(review), str(out))
        assert code == 1, (
            f"Expected exit 1 for dangling body citation, got {code}"
        )


# ---------------------------------------------------------------------------
# FIX 2: token-boundary numeric matching in check_against_csvs
# ---------------------------------------------------------------------------

class TestNumericTokenBoundary:
    """check_against_csvs must match numbers at token boundaries, not as substrings."""

    def test_short_number_does_not_match_longer_number(self, tmp_path):
        """
        A quote citing '0.3' must NOT be verified against a CSV containing only '0.30'.
        '0.3' is a substring of '0.30' but they are different numbers; the match must
        require a token boundary so '0.3' does not hit inside '0.30'.
        """
        csv_file = tmp_path / "table1.csv"
        csv_file.write_text("coef\n0.30\n", encoding="utf-8")

        quote = "the effect is 0.3"
        found, details = vq.check_against_csvs(quote, str(tmp_path))
        assert not found, (
            f"'0.3' should NOT match against corpus containing only '0.30' "
            f"(different numbers); got found={found}, details={details}"
        )

    def test_exact_number_matches_itself(self, tmp_path):
        """A quote citing '0.30' IS verified against a CSV containing '0.30'."""
        csv_file = tmp_path / "table1.csv"
        csv_file.write_text("coef\n0.30\n", encoding="utf-8")

        quote = "the effect is 0.30"
        found, details = vq.check_against_csvs(quote, str(tmp_path))
        assert found, (
            f"'0.30' should match against corpus containing '0.30'; "
            f"got found={found}, details={details}"
        )
