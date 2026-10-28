"""Tests for citation-gate infra-failure handling (Problem 1 fix).

Three new tests:
  test_all_apis_unreachable_is_exit2
      When every search helper raises LookupUnavailable, a review with one body
      citation and one matching REFERENCES entry must produce exit 2 (infra),
      NOT exit 1 (content defect), and the reference status must be
      SEARCH_UNAVAILABLE, not NOT_FOUND.

  test_api_answered_zero_is_not_found
      When search_paper returns ([], None, False) -- reachable but empty (HTTP 200
      with zero results) -- the reference is NOT_FOUND, a content defect: exit 1.

  test_verify_citations_matches_parenthetical (Problem 2 regression)
      extract_body_citations on a review containing "(Smith 2020)" and
      "(von Hippel 2005)" must yield both citations.
"""

from __future__ import annotations

import importlib
import sys
import tempfile
import textwrap
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "skills/review/scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

vc = importlib.import_module("verify_citations")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_review(path: Path, text: str) -> Path:
    path.write_text(textwrap.dedent(text), encoding="utf-8")
    return path


def _body_cites(text: str):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(text)
        fname = f.name
    return vc.extract_body_citations(fname)


# ---------------------------------------------------------------------------
# test_all_apis_unreachable_is_exit2
# ---------------------------------------------------------------------------


class TestAllApisUnreachable:
    """When every API raises LookupUnavailable, the exit code must be 2, not 1."""

    def test_exit_code_is_2_not_1(self, tmp_path, monkeypatch):
        """Monkeypatch search_paper to signal all_unavailable=True.

        The review has one body citation matching one REFERENCES entry; the
        reference is parseable (has author, year, title) so search_paper IS
        called.  Because all APIs are unreachable, the status must be
        SEARCH_UNAVAILABLE and the exit code must be 2 (infra), not 1 (content).
        """
        monkeypatch.setattr(
            vc,
            "search_paper",
            lambda *a, **kw: ([], None, True),  # all_unavailable=True
        )

        review = _write_review(
            tmp_path / "review.txt",
            """\
            The findings follow Smith (2020).

            REFERENCES

            Smith, J. (2020). A study of methods. Journal of Methods, 1(1), 1-10.
            """,
        )
        out = tmp_path / "out.md"
        code = vc.verify_references(str(review), str(out))
        assert code == 2, (
            f"Expected exit 2 (infra) when all APIs are unreachable; got {code}"
        )

    def test_status_is_search_unavailable_not_not_found(self, tmp_path, monkeypatch):
        """The written report must contain SEARCH_UNAVAILABLE, not NOT_FOUND."""
        monkeypatch.setattr(
            vc,
            "search_paper",
            lambda *a, **kw: ([], None, True),
        )

        review = _write_review(
            tmp_path / "review.txt",
            """\
            Evidence from Smith (2020).

            REFERENCES

            Smith, J. (2020). Evidence paper. Journal, 1(1), 1-10.
            """,
        )
        out = tmp_path / "out.md"
        vc.verify_references(str(review), str(out))
        report = out.read_text(encoding="utf-8")
        assert "SEARCH_UNAVAILABLE" in report, (
            f"Expected SEARCH_UNAVAILABLE in report when all APIs unreachable; "
            f"report excerpt: {report[:500]}"
        )
        assert "NOT_FOUND" not in report, (
            f"Report must NOT contain NOT_FOUND when all APIs unreachable; "
            f"report excerpt: {report[:500]}"
        )

    def test_exit1_still_takes_priority_over_exit2(self, tmp_path, monkeypatch):
        """When one reference is SEARCH_UNAVAILABLE and another is dangling
        (a content defect), exit 1 must take priority over exit 2."""
        monkeypatch.setattr(
            vc,
            "search_paper",
            lambda *a, **kw: ([], None, True),
        )

        review = _write_review(
            tmp_path / "review.txt",
            """\
            Evidence from Smith (2020). Also see Jones (2019).

            REFERENCES

            Smith, J. (2020). Evidence paper. Journal, 1(1), 1-10.
            """,
            # Jones (2019) is in the body but not in REFERENCES -> dangling -> exit 1
        )
        out = tmp_path / "out.md"
        code = vc.verify_references(str(review), str(out))
        assert code == 1, (
            f"Expected exit 1 (content defect takes priority); got {code}"
        )


# ---------------------------------------------------------------------------
# test_api_answered_zero_is_not_found
# ---------------------------------------------------------------------------


class TestApiAnsweredZeroIsNotFound:
    """When search_paper returns ([], None, False), the ref is NOT_FOUND -> exit 1."""

    def test_reachable_empty_is_not_found(self, tmp_path, monkeypatch):
        """all_unavailable=False means at least one API answered HTTP 200 with
        zero results.  The reference genuinely could not be matched: NOT_FOUND."""
        monkeypatch.setattr(
            vc,
            "search_paper",
            lambda *a, **kw: ([], None, False),  # reachable, zero results
        )

        review = _write_review(
            tmp_path / "review.txt",
            """\
            The approach follows Smith (2020).

            REFERENCES

            Smith, J. (2020). A study of methods. Journal of Methods, 1(1), 1-10.
            """,
        )
        out = tmp_path / "out.md"
        code = vc.verify_references(str(review), str(out))
        assert code == 1, (
            f"Expected exit 1 (NOT_FOUND content defect) when API is reachable "
            f"but returns zero results; got {code}"
        )

    def test_report_contains_not_found_not_search_unavailable(self, tmp_path, monkeypatch):
        """The report must say NOT_FOUND, not SEARCH_UNAVAILABLE."""
        monkeypatch.setattr(
            vc,
            "search_paper",
            lambda *a, **kw: ([], None, False),
        )

        review = _write_review(
            tmp_path / "review.txt",
            """\
            The approach follows Smith (2020).

            REFERENCES

            Smith, J. (2020). A study of methods. Journal of Methods, 1(1), 1-10.
            """,
        )
        out = tmp_path / "out.md"
        vc.verify_references(str(review), str(out))
        report = out.read_text(encoding="utf-8")
        assert "NOT_FOUND" in report, (
            f"Expected NOT_FOUND in report when API reachable but empty; "
            f"report excerpt: {report[:500]}"
        )
        assert "SEARCH_UNAVAILABLE" not in report, (
            f"Report must NOT contain SEARCH_UNAVAILABLE when API was reachable; "
            f"report excerpt: {report[:500]}"
        )


# ---------------------------------------------------------------------------
# test_verify_citations_matches_parenthetical (Problem 2)
# ---------------------------------------------------------------------------


class TestParentheticalCitations:
    """extract_body_citations must recognise parenthetical "(Author Year)" forms."""

    def test_plain_parenthetical_smith(self):
        """'(Smith 2020)' must yield a citation with Smith and year 2020."""
        cites = _body_cites("The evidence (Smith 2020) supports this.\n")
        assert any("Smith" in c[0] and c[1] == 2020 for c in cites), (
            f"Expected (Smith, 2020) from '(Smith 2020)'; got {cites}"
        )

    def test_particle_parenthetical_von_hippel(self):
        """'(von Hippel 2005)' must yield a citation with von Hippel and year 2005."""
        cites = _body_cites("See (von Hippel 2005) for details.\n")
        assert any("Hippel" in c[0] and c[1] == 2005 for c in cites), (
            f"Expected a citation containing 'Hippel' and year 2005 from "
            f"'(von Hippel 2005)'; got {cites}"
        )

    def test_hyphenated_parenthetical(self):
        """'(Montiel-Olea and Pflueger 2013)' must be recognised."""
        cites = _body_cites(
            "The instrument is valid (Montiel-Olea and Pflueger 2013).\n"
        )
        assert any("Montiel" in c[0] and c[1] == 2013 for c in cites), (
            f"Expected citation containing 'Montiel' and year 2013; got {cites}"
        )

    def test_semicolon_parenthetical_mixed(self):
        """'(Smith 2020; von Hippel 2005)' must yield both entries."""
        cites = _body_cites("Prior work (Smith 2020; von Hippel 2005) establishes this.\n")
        assert any("Smith" in c[0] and c[1] == 2020 for c in cites), (
            f"Expected (Smith, 2020); got {cites}"
        )
        assert any("Hippel" in c[0] and c[1] == 2005 for c in cites), (
            f"Expected ('Hippel', 2005); got {cites}"
        )

    def test_narrative_forms_still_work(self):
        """Narrative 'Smith (2020)' must still be recognised (no regression)."""
        cites = _body_cites("Smith (2020) shows this clearly.\n")
        assert any("Smith" in c[0] and c[1] == 2020 for c in cites), (
            f"Regression: narrative 'Smith (2020)' not captured; got {cites}"
        )
