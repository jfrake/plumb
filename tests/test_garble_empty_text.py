# tests/test_garble_empty_text.py
"""
TDD tests for garble_score: near-empty extracted text must be treated as
DEGRADED_EMPTY_TEXT rather than CLEAN.

Fail-first: written before the implementation is in place.
"""
from __future__ import annotations

import sys
import pathlib

SD = pathlib.Path(__file__).resolve().parents[1] / "skills/review/scripts"
sys.path.insert(0, str(SD))
import importlib
gs = importlib.import_module("garble_score")


# --- helpers ---

def _make_scores(char_count: int) -> dict:
    """Return a scores dict that looks like the output of score_pdf() but with
    a controlled total_chars value and no garble artifacts."""
    return {
        "global_quality_score": 100,
        "global_garble_ratio": 0.0,
        "total_artifacts": 0,
        "total_chars": char_count,
        "total_pages": 3,
        "flagged_pages": [],
        "page_scores": [],
        "fixes_available": [],
        "details": [],
    }


# --- Empty-text verdict tests ---

class TestEmptyTextVerdict:
    """Near-empty text (below threshold) must not report CLEAN."""

    def test_near_empty_pdf_reports_degraded_empty_text(self):
        """5 total chars across a 3-page PDF is below any reasonable threshold;
        report should show DEGRADED_EMPTY_TEXT, not CLEAN."""
        scores = _make_scores(5)
        report = gs.generate_report(scores)
        assert "DEGRADED_EMPTY_TEXT" in report, (
            "Expected DEGRADED_EMPTY_TEXT verdict for near-empty extracted text; "
            f"got report:\n{report}"
        )
        assert "CLEAN" not in report, (
            "Report must not contain CLEAN when text is near-empty"
        )

    def test_zero_chars_reports_degraded_empty_text(self):
        """Completely empty extraction should also be DEGRADED_EMPTY_TEXT."""
        scores = _make_scores(0)
        report = gs.generate_report(scores)
        assert "DEGRADED_EMPTY_TEXT" in report

    def test_below_threshold_has_warning_block(self):
        """DEGRADED_EMPTY_TEXT report should include a downstream warning."""
        scores = _make_scores(10)
        report = gs.generate_report(scores)
        # The warning block should guide downstream agents
        assert "WARNING" in report or "scanned" in report.lower() or "no text" in report.lower(), (
            "Expected a warning block in the report for empty-text PDFs"
        )

    def test_normal_text_unaffected(self):
        """A PDF with 5000 chars and high quality score remains CLEAN."""
        scores = _make_scores(5000)
        report = gs.generate_report(scores)
        assert "CLEAN" in report, (
            "Expected CLEAN verdict for normal text PDF"
        )
        assert "DEGRADED_EMPTY_TEXT" not in report

    def test_normal_text_degraded_by_garble_unaffected(self):
        """A garble-degraded PDF with plenty of text stays DEGRADED (not DEGRADED_EMPTY_TEXT)."""
        scores = _make_scores(5000)
        scores["global_quality_score"] = 50  # garble-degraded
        scores["global_garble_ratio"] = 0.1
        scores["total_artifacts"] = 500
        report = gs.generate_report(scores)
        assert "DEGRADED" in report
        # DEGRADED_EMPTY_TEXT should not appear when chars are plentiful
        assert "DEGRADED_EMPTY_TEXT" not in report

    def test_threshold_boundary_just_above(self):
        """A PDF right above the empty-text threshold should not trigger DEGRADED_EMPTY_TEXT."""
        # The threshold is expected to be around 50 chars; test with 200 (well above).
        scores = _make_scores(200)
        report = gs.generate_report(scores)
        assert "CLEAN" in report
        assert "DEGRADED_EMPTY_TEXT" not in report

    def test_compute_garble_score_empty_string_unchanged(self):
        """compute_garble_score itself (per-text scorer) still returns 100 for empty string."""
        result = gs.compute_garble_score("")
        assert result["quality_score"] == 100
        assert result["garble_ratio"] == 0.0

    def test_scores_dict_has_empty_text_flag(self):
        """score_pdf() result has an 'empty_text' boolean key set correctly.

        We test via generate_report() since score_pdf() requires a real PDF,
        but we also verify the flag propagates when present in the scores dict.
        """
        scores = _make_scores(5)
        scores["empty_text"] = True
        report = gs.generate_report(scores)
        assert "DEGRADED_EMPTY_TEXT" in report


# Ruling 40 (8): Stage 0 reads PAGE_COUNT from the report's "Pages Scanned" line.
def test_report_states_page_count(tmp_path):
    import pymupdf
    pdf = tmp_path / "p.pdf"
    doc = pymupdf.open()
    for i in range(3):
        doc.new_page().insert_text((72, 72), f"Page {i + 1} has enough ordinary words to score cleanly.")
    doc.save(pdf); doc.close()
    report = gs.generate_report(gs.score_pdf(str(pdf)))
    assert "**Pages Scanned:** 3" in report
