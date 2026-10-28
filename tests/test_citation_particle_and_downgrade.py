"""TDD tests for two citation-gate correctness fixes.

FIX 1: SEARCH_UNAVAILABLE downgrade -- if the precise search returned a
reachable-empty response (HTTP 200, zero results) but the broad retry returned
all_unavailable=True, the reference must be NOT_FOUND (exit 1), not
SEARCH_UNAVAILABLE (exit 2).

FIX 2: Particle surname mismatch -- a body citation "von Hippel (2005)" and a
REFERENCES entry "von Hippel, E. (2005)." must not produce a dangling-citation
false positive.  Surname normalisation must be shared between reference parsing
and dangling detection.
"""

from __future__ import annotations

import importlib
import sys
import textwrap
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "skills/review/scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

vc = importlib.import_module("verify_citations")
cp = importlib.import_module("citation_parser")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_review(path: Path, text: str) -> Path:
    path.write_text(textwrap.dedent(text), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# FIX 1: reachable-empty precise + all-unavailable broad => NOT_FOUND
# ---------------------------------------------------------------------------


class TestSearchUnavailableDowngrade:
    """The precise search returned HTTP 200 with zero results (reachable-empty).
    The broad retry returned all_unavailable=True (transient network failure).
    The reference must be classified NOT_FOUND, not SEARCH_UNAVAILABLE.
    """

    def _make_precise_reachable_empty_broad_unavailable(self):
        """Return a search_paper replacement that simulates the bug scenario.

        First call (precise): ([], None, False)  -- at least one API 200, zero results.
        Second call (broad): ([], None, True)    -- all APIs failed.
        """
        call_count = [0]

        def _mock(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # Precise search: reachable, zero results
                return [], None, False
            else:
                # Broad retry: all APIs unavailable
                return [], None, True

        return _mock

    def test_reachable_empty_precise_then_broad_unavailable_is_not_found(
        self, tmp_path, monkeypatch
    ):
        """When the precise search is reachable-empty and the broad retry is
        all-unavailable, the reference must be NOT_FOUND (exit 1), not
        SEARCH_UNAVAILABLE (exit 2).
        """
        monkeypatch.setattr(
            vc,
            "search_paper",
            self._make_precise_reachable_empty_broad_unavailable(),
        )

        review = _write_review(
            tmp_path / "review.txt",
            """\
            The analysis uses Smith (2020).

            REFERENCES

            Smith, J. (2020). A fabricated study. Journal of Testing, 1(1), 1-10.
            """,
        )
        out = tmp_path / "out.md"
        code = vc.verify_references(str(review), str(out))

        assert code == 1, (
            f"Expected exit 1 (NOT_FOUND content defect) when precise search is "
            f"reachable-empty and broad retry is all-unavailable; got exit {code}"
        )
        report = out.read_text(encoding="utf-8")
        assert "NOT_FOUND" in report, (
            f"Report must contain NOT_FOUND; got: {report[:600]}"
        )
        assert "SEARCH_UNAVAILABLE" not in report, (
            f"Report must NOT contain SEARCH_UNAVAILABLE when a reachable response "
            f"was received in the precise pass; got: {report[:600]}"
        )

    def test_all_attempts_unavailable_is_search_unavailable(
        self, tmp_path, monkeypatch
    ):
        """When every attempt (precise AND broad) is all-unavailable, the
        reference must remain SEARCH_UNAVAILABLE (exit 2), not NOT_FOUND.
        """
        monkeypatch.setattr(
            vc,
            "search_paper",
            lambda *a, **kw: ([], None, True),  # always all-unavailable
        )

        review = _write_review(
            tmp_path / "review.txt",
            """\
            The approach follows Jones (2019).

            REFERENCES

            Jones, A. (2019). A real-ish study. Journal of Science, 2(2), 5-15.
            """,
        )
        out = tmp_path / "out.md"
        code = vc.verify_references(str(review), str(out))

        assert code == 2, (
            f"Expected exit 2 (infra failure) when ALL attempts are all-unavailable; "
            f"got exit {code}"
        )
        report = out.read_text(encoding="utf-8")
        assert "SEARCH_UNAVAILABLE" in report, (
            f"Report must contain SEARCH_UNAVAILABLE; got: {report[:600]}"
        )
        assert "NOT_FOUND" not in report, (
            f"Report must NOT contain NOT_FOUND when all APIs were unreachable "
            f"for every attempt; got: {report[:600]}"
        )


# ---------------------------------------------------------------------------
# FIX 2: particle surname -- "von Hippel (2005)" body citation must match
#         "von Hippel, E. (2005)" reference entry without a dangling false positive
# ---------------------------------------------------------------------------


class TestParticleSurnameMatching:
    """Body citation 'von Hippel (2005)' and reference 'von Hippel, E. (2005).'
    must be matched without a dangling-citation false positive.
    """

    def test_particle_surname_reference_not_dangling(self, tmp_path, monkeypatch):
        """A review citing 'von Hippel (2005)' in the body with a REFERENCES
        entry 'von Hippel, E. (2005). Title.' must NOT be flagged as dangling.
        The reference must be looked up (we intercept search_paper to return a
        plausible match) and must not appear in the dangling-citations list.
        """
        # Return a plausible match so the reference passes VERIFIED and we can
        # focus on the dangling-check logic.
        monkeypatch.setattr(
            vc,
            "search_paper",
            lambda *a, **kw: (
                [
                    {
                        "title": "The Sources of Innovation",
                        "authorships": [
                            {"author": {"display_name": "Eric von Hippel"}}
                        ],
                        "publication_year": 2005,
                        "primary_location": {
                            "source": {"display_name": "MIT Press"}
                        },
                        "cited_by_count": 4500,
                        "doi": "10.1093/acprof:oso/9780195093117.001.0001",
                    }
                ],
                "Semantic Scholar",
                False,
            ),
        )

        review = _write_review(
            tmp_path / "review.txt",
            """\
            User innovation is central to this debate (von Hippel 2005).

            REFERENCES

            von Hippel, E. (2005). Democratizing Innovation. MIT Press.
            """,
        )
        out = tmp_path / "out.md"
        code = vc.verify_references(str(review), str(out))
        report = out.read_text(encoding="utf-8")

        # Must not produce a dangling-citation block for von Hippel.
        assert "Dangling Body Citations" not in report or "von Hippel" not in report, (
            f"'von Hippel (2005)' must not be flagged as dangling when a "
            f"matching REFERENCES entry exists; report excerpt:\n{report[:800]}"
        )
        # Must not be a content defect due to dangling alone.
        assert code in (0, 1, 2), f"Unexpected exit code {code}"
        # Specifically the dangling check should not produce exit 1 for this
        # case.  If code==1 it must be for a different reason (AUTHOR_MISMATCH
        # or NOT_FOUND on the matched result), not for dangling.
        # We verify by checking that the dangling section is absent or does not
        # mention von Hippel.
        if "Dangling Body Citations" in report:
            assert "von Hippel" not in report.split("Dangling Body Citations")[1].split(
                "## Verification"
            )[0], (
                "'von Hippel' must not appear in the Dangling Body Citations section"
            )

    def test_particle_surname_stored_correctly_in_last_names(self):
        """extract_references_from_text must store 'Hippel' (or 'von Hippel')
        in last_names for 'von Hippel, E. (2005). Title.'  It must NOT store
        just 'von'.
        """
        import tempfile, os

        text = textwrap.dedent(
            """\
            The paper argues this point.

            REFERENCES

            von Hippel, E. (2005). Democratizing Innovation. MIT Press.
            """
        )
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as fh:
            fh.write(text)
            fpath = fh.name

        try:
            refs = vc.extract_references_from_text(fpath)
        finally:
            os.unlink(fpath)

        assert refs, "Expected at least one parsed reference"
        ref = refs[0]
        last_names = [n.lower() for n in ref.get("last_names", [])]
        assert "von" not in last_names or any(
            n in last_names for n in ("hippel", "von hippel")
        ), (
            f"Reference parser stored 'von' as the sole last name token, which "
            f"is the particle, not the surname. last_names={ref.get('last_names')}"
        )
        # At minimum 'Hippel' must be present or the full 'von Hippel' compound.
        has_hippel = any(
            "hippel" in n for n in last_names
        )
        assert has_hippel, (
            f"'Hippel' (or 'von Hippel') must appear in last_names for "
            f"'von Hippel, E. (2005)'; got last_names={ref.get('last_names')}"
        )

    def test_non_particle_surnames_unaffected(self, tmp_path, monkeypatch):
        """Existing non-particle surnames must still match correctly.
        'Smith (2020)' body citation and 'Smith, J. (2020).' reference must
        not produce a dangling false positive.
        """
        monkeypatch.setattr(
            vc,
            "search_paper",
            lambda *a, **kw: ([], None, True),  # avoid real network calls
        )

        review = _write_review(
            tmp_path / "review.txt",
            """\
            Smith (2020) demonstrates the effect clearly.

            REFERENCES

            Smith, J. (2020). A study of effects. Journal, 1(1), 1-10.
            """,
        )
        out = tmp_path / "out.md"
        vc.verify_references(str(review), str(out))
        report = out.read_text(encoding="utf-8")

        # Smith must not appear in dangling citations.
        if "Dangling Body Citations" in report:
            dangling_section = report.split("Dangling Body Citations")[1].split(
                "## Verification"
            )[0]
            assert "Smith" not in dangling_section, (
                f"'Smith (2020)' must not be flagged as dangling; dangling section:\n"
                f"{dangling_section}"
            )
