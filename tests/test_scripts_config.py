from __future__ import annotations
import re
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/review/scripts"

def test_mailto_default_is_empty_and_overridable():
    text = (SCRIPTS / "verify_citations.py").read_text()
    m = re.search(r'^MAILTO\s*=\s*"([^"]*)"', text, re.M)
    assert m and m.group(1) == ""

def test_mailto_reaches_openalex_and_crossref(monkeypatch):
    """The configured contact email must reach both OpenAlex and CrossRef requests,
    and must be omitted from both when unset (regression: search_openalex's
    mailto default was bound at definition time, so a runtime MAILTO reassignment
    never reached it)."""
    import sys, importlib
    sys.path.insert(0, str(SCRIPTS))
    vc = importlib.import_module("verify_citations")

    captured = {}

    class FakeResponse:
        status_code = 200
        def json(self):
            return {"results": [], "message": {"items": []}}

    def fake_get(url, params=None, timeout=None):
        captured[url] = params
        return FakeResponse()

    monkeypatch.setattr(vc.requests, "get", fake_get)

    monkeypatch.setattr(vc, "MAILTO", "a@example.org")
    vc.search_openalex("some query")
    vc.search_crossref("some query")
    assert captured["https://api.openalex.org/works"].get("mailto") == "a@example.org"
    assert captured["https://api.crossref.org/works"].get("mailto") == "a@example.org"

    captured.clear()
    monkeypatch.setattr(vc, "MAILTO", "")
    vc.search_openalex("some query")
    vc.search_crossref("some query")
    assert "mailto" not in captured["https://api.openalex.org/works"]
    assert "mailto" not in captured["https://api.crossref.org/works"]

def test_image_only_pdf_scores_as_unusable(tmp_path):
    # garble_score.py's real CLI is: garble_score.py <pdf_path> <output_dir>,
    # writing <output_dir>/garble_report.md and exiting 2 for DEGRADED_EMPTY_TEXT
    # (see garble_score.py's Usage docstring and its main()).
    import subprocess, sys
    import pymupdf
    pdf = tmp_path / "blank.pdf"
    doc = pymupdf.open(); doc.new_page(); doc.new_page(); doc.save(pdf)
    out = tmp_path / "out"
    r = subprocess.run([sys.executable, str(SCRIPTS / "garble_score.py"), str(pdf), str(out)], capture_output=True, text=True)
    assert r.returncode != 0 or "empty" in (r.stdout + r.stderr).lower()
    report = out / "garble_report.md"
    assert report.exists()
    assert "empty" in report.read_text().lower()
