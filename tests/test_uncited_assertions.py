# tests/test_uncited_assertions.py
from __future__ import annotations

import sys, pathlib
SD = pathlib.Path(__file__).resolve().parents[1] / "skills/review/scripts"
sys.path.insert(0, str(SD))
import importlib; vca = importlib.import_module("verify_claim_attribution")

def test_flags_uncited_methodology_claim():
    txt = "S&P changed its ESG methodology in 2020 to fold in racial-justice responses."
    out = vca.extract_uncited_assertions(txt)
    assert any("methodology" in s.lower() for s in out)

def test_ignores_cited_claim():
    txt = "Prior work shows this pattern (Smith and Jones 2020)."
    out = vca.extract_uncited_assertions(txt)
    assert out == []

def test_numeric_citation_not_flagged():
    txt = "S&P changed its ESG methodology [1]."
    out = vca.extract_uncited_assertions(txt)
    assert out == []

def test_plain_sentence_no_named_party_not_flagged():
    txt = "The methodology used here is standard."
    out = vca.extract_uncited_assertions(txt)
    assert out == []
