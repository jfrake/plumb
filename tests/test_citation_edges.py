"""Tests for citation extractor edge cases.

FIX A: extract_body_citations must handle:
  - Semicolon-separated multi-cite: "(Smith 2020; Jones 2021)" yields both citations.
  - Three-or-more-author narrative: "Smith, Jones, and Lee (2020)" yields at least
    (first_author, 2020) where first_author starts with "Smith".

Existing forms must not regress:
  - Narrative "Author (Year)": "Smith (2020)" -> ("Smith", 2020)
  - Narrative "Author et al. (Year)": "Jones et al. (2019)" -> recognized
  - Parenthetical "(Author Year)": not tested here (out of scope for this file)
  - Hyphenated-name narrative: "Van der Berg (2020)" -> ("Berg", 2020) or similar
"""

from __future__ import annotations

import importlib
import sys
import tempfile
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "skills/review/scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

vc = importlib.import_module("verify_citations")


def _body_cites(text: str) -> set[tuple[str, int]]:
    """Write text to a temp file and extract body citations from it."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(text)
        fname = f.name
    return vc.extract_body_citations(fname)


# ---------------------------------------------------------------------------
# Semicolon-separated multi-cite
# ---------------------------------------------------------------------------


def test_semicolon_multicite_both_extracted():
    """'(Smith 2020; Jones 2021)' must yield both (Smith, 2020) and (Jones, 2021)."""
    cites = _body_cites("The findings (Smith 2020; Jones 2021) confirm the hypothesis.\n")
    years = {c[1] for c in cites}
    first_authors = {c[0].split(",")[0].strip().split()[0] for c in cites}
    assert 2020 in years, f"Expected year 2020 in citations; got {cites}"
    assert 2021 in years, f"Expected year 2021 in citations; got {cites}"
    # Each entry must be keyed to the right author
    smith_cites = [c for c in cites if "Smith" in c[0] and c[1] == 2020]
    jones_cites = [c for c in cites if "Jones" in c[0] and c[1] == 2021]
    assert smith_cites, f"Expected a (Smith, 2020) citation; got {cites}"
    assert jones_cites, f"Expected a (Jones, 2021) citation; got {cites}"


def test_semicolon_multicite_three_entries():
    """Three-entry semicolon multi-cite should yield all three author+year pairs."""
    cites = _body_cites(
        "Prior work (Adams 2018; Baker 2019; Chen 2022) supports this.\n"
    )
    assert any("Adams" in c[0] and c[1] == 2018 for c in cites), (
        f"Expected (Adams, 2018); got {cites}"
    )
    assert any("Baker" in c[0] and c[1] == 2019 for c in cites), (
        f"Expected (Baker, 2019); got {cites}"
    )
    assert any("Chen" in c[0] and c[1] == 2022 for c in cites), (
        f"Expected (Chen, 2022); got {cites}"
    )


def test_semicolon_years_are_ints():
    """Years extracted from semicolon multi-cite must be plain 4-digit ints."""
    cites = _body_cites("(Smith 2020; Jones 2021) is the standard reference.\n")
    for author, year in cites:
        assert isinstance(year, int), f"Expected int year; got {type(year)} for {author}"
        assert 1900 <= year <= 2100, f"Year out of plausible range: {year}"


# ---------------------------------------------------------------------------
# Three-or-more-author narrative cite
# ---------------------------------------------------------------------------


def test_three_author_narrative_recognized():
    """'Smith, Jones, and Lee (2020)' must yield at least one citation with first
    author 'Smith' and year 2020."""
    cites = _body_cites("Smith, Jones, and Lee (2020) demonstrate the effect.\n")
    smith_2020 = [c for c in cites if c[0].startswith("Smith") and c[1] == 2020]
    assert smith_2020, (
        f"Expected a citation with first author 'Smith' and year 2020; got {cites}"
    )


def test_three_author_narrative_year_is_int():
    """Year in a 3+ author narrative must be a plain int."""
    cites = _body_cites("Smith, Jones, and Lee (2020) show this.\n")
    for author, year in cites:
        if year == 2020 and "Smith" in author:
            assert isinstance(year, int), f"Expected int year; got {type(year)}"


def test_four_author_narrative_first_author_captured():
    """'Brown, White, Green, and Black (2019)' should capture at least (Brown, 2019)."""
    cites = _body_cites("Brown, White, Green, and Black (2019) established this.\n")
    brown_2019 = [c for c in cites if c[0].startswith("Brown") and c[1] == 2019]
    assert brown_2019, (
        f"Expected citation with first author 'Brown' and year 2019; got {cites}"
    )


# ---------------------------------------------------------------------------
# Regression: existing forms must not break
# ---------------------------------------------------------------------------


def test_narrative_author_year_unchanged():
    """'Smith (2020)' still yields a citation with Smith and 2020."""
    cites = _body_cites("Smith (2020) argues this is important.\n")
    assert any("Smith" in c[0] and c[1] == 2020 for c in cites), (
        f"Regression: 'Smith (2020)' not captured; got {cites}"
    )


def test_et_al_narrative_unchanged():
    """'Jones et al. (2019)' still yields a citation."""
    cites = _body_cites("Jones et al. (2019) provide evidence.\n")
    assert any("Jones" in c[0] and c[1] == 2019 for c in cites), (
        f"Regression: 'Jones et al. (2019)' not captured; got {cites}"
    )


def test_two_author_and_narrative_unchanged():
    """'Smith and Jones (2021)' still yields a citation."""
    cites = _body_cites("Smith and Jones (2021) confirm the result.\n")
    assert any(c[1] == 2021 for c in cites), (
        f"Regression: 'Smith and Jones (2021)' not captured; got {cites}"
    )


# ---------------------------------------------------------------------------
# Parenthetical "(Author Year)" forms -- now handled via citation_parser
# ---------------------------------------------------------------------------


def test_parenthetical_plain():
    """'(Smith 2020)' must yield a citation with Smith and year 2020."""
    cites = _body_cites("The evidence (Smith 2020) is conclusive.\n")
    assert any("Smith" in c[0] and c[1] == 2020 for c in cites), (
        f"Expected (Smith, 2020) from '(Smith 2020)'; got {cites}"
    )


def test_parenthetical_von_particle():
    """'(von Hippel 2005)' must yield a citation containing 'Hippel' and year 2005."""
    cites = _body_cites("This is well established (von Hippel 2005).\n")
    assert any("Hippel" in c[0] and c[1] == 2005 for c in cites), (
        f"Expected citation containing 'Hippel' and year 2005; got {cites}"
    )


def test_parenthetical_hyphenated_two_author():
    """'(Montiel-Olea and Pflueger 2013)' must be captured."""
    cites = _body_cites("The IV is valid (Montiel-Olea and Pflueger 2013).\n")
    assert any("Montiel" in c[0] and c[1] == 2013 for c in cites), (
        f"Expected citation with 'Montiel' and year 2013; got {cites}"
    )
