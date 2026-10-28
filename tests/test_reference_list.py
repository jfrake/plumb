from __future__ import annotations
import importlib
import sys
from pathlib import Path

import pymupdf
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/review/scripts"
sys.path.insert(0, str(SCRIPTS))
crl = importlib.import_module("check_reference_list")
vc = importlib.import_module("verify_citations")

# Invented references for testing only (not real works).
REF_PAGE = (
    "References\n"
    "Smith, J. (2020). A study of methods. Journal of Methods, 1(1), 1-10.\n"
    "Jones, K., & Lee, M. (2019). Another study of\n"
    "organizations. Management Science, 3(2), 4-5.\n"
    "van der Berg, A. (2018). Teams at work. Organization Science, 9, 1-2.\n"
    "Appendix\n"
    "Table A1. Means and standard deviations\n"
)


def _pdf(tmp_path, pages):
    doc = pymupdf.open()
    for text in pages:
        doc.new_page().insert_text((72, 72), text, fontsize=9)
    p = tmp_path / "paper.pdf"
    doc.save(p)
    return p


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(vc.time, "sleep", lambda s: None)


def test_entries_are_split_joined_and_stop_at_the_appendix(tmp_path):
    pdf = _pdf(tmp_path, ["Body text cites Smith (2020) and Jones and Lee (2019).", REF_PAGE])
    entries = crl.reference_entries(pdf)
    assert len(entries) == 3
    assert entries[0].startswith("Smith, J. (2020)")
    assert entries[1].startswith("Jones, K., & Lee, M. (2019)") and "organizations. Management Science" in entries[1]
    assert entries[2].startswith("van der Berg, A. (2018)")
    assert not any("Table A1" in e for e in entries)


def test_second_author_line_does_not_start_a_new_entry():
    lines = ["Smith, J., &", "Jones, K. (2020). A title. Journal, 1, 1-2."]
    assert crl.split_entries(lines) == ["Smith, J., & Jones, K. (2020). A title. Journal, 1, 1-2."]


def test_no_reference_section_exits_2(tmp_path):
    pdf = _pdf(tmp_path, ["A paper with no reference list at all."])
    out = tmp_path / "stage-1" / "reference_list.md"
    assert crl.main([str(pdf), str(out)]) == 2
    assert "No reference section" in out.read_text()


def test_network_trouble_exits_2(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "search_paper", lambda *a, **k: ([], None, True))
    out = tmp_path / "reference_list.md"
    assert crl.main([str(_pdf(tmp_path, [REF_PAGE])), str(out)]) == 2
    assert "SEARCH_UNAVAILABLE" in out.read_text()


def test_missing_work_exits_1(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "search_paper", lambda *a, **k: ([], None, False))
    out = tmp_path / "reference_list.md"
    assert crl.main([str(_pdf(tmp_path, [REF_PAGE])), str(out)]) == 1
    assert "NOT_FOUND" in out.read_text()
    assert (tmp_path / "reference_list_input.txt").read_text().startswith("REFERENCES\n\n")


def test_mailto_is_passed_to_the_lookups(tmp_path, monkeypatch):
    monkeypatch.setattr(vc, "search_paper", lambda *a, **k: ([], None, True))
    monkeypatch.setattr(vc, "MAILTO", "")
    crl.main([str(_pdf(tmp_path, [REF_PAGE])), str(tmp_path / "r.md"), "someone@example.org"])
    assert vc.MAILTO == "someone@example.org"


def test_first_reference_list_wins_over_a_later_appendix_list(tmp_path):
    later = "Online appendix\nReferences\nZed, Q. (2001). Only in the appendix. Journal, 2, 3-4.\n"
    entries = crl.reference_entries(_pdf(tmp_path, [REF_PAGE, later]))
    assert len(entries) == 3
    assert entries[0].startswith("Smith, J. (2020)")
    assert not any("Zed" in e for e in entries)
