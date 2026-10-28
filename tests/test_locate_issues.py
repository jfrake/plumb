"""locate_issues.py on small PDFs generated here. Every PDF and sentence is fake."""
from __future__ import annotations
import importlib
import json
import subprocess
import sys
from pathlib import Path

import pymupdf

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/review/scripts"
sys.path.insert(0, str(SCRIPTS))
loc = importlib.import_module("locate_issues")


def make_pdf(path: Path, pages: list, labels=None) -> Path:
    doc = pymupdf.open()
    for lines in pages:
        page = doc.new_page()
        y = 72
        for line in lines:
            page.insert_text((72, y), line)
            y += 14
    if labels:
        doc.set_page_labels(labels)
    doc.save(str(path))
    return path


def run(tmp_path, pdf, issues):
    src, out = tmp_path / "issues.json", tmp_path / "locations.json"
    src.write_text(json.dumps(issues))
    r = subprocess.run([sys.executable, str(SCRIPTS / "locate_issues.py"), str(pdf), str(src), str(out)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads(out.read_text()), json.loads(r.stdout)


def test_exact_match_gives_page_and_rect(tmp_path):
    pdf = make_pdf(tmp_path / "p.pdf", [["Fake cover."], ["The fake widgets rose sharply in the", "second quarter of the fake year."]])
    got, counts = run(tmp_path, pdf, [{"id": "1", "excerpt": "The fake widgets rose sharply in the second quarter", "ms_page": None}])
    assert got["1"]["pdf_page"] == 2 and got["1"]["method"] == "exact"
    x0, y0, x1, y1 = got["1"]["rect"]
    assert 60 < y0 < 100 and x0 >= 70
    assert len(got["1"]["rects"]) == 2 and got["1"]["label"] == "PDF p. 2"
    assert counts == {"exact": 1, "page_only": 0, "approximate": 0, "not_found": 0}


def test_hyphenated_word_across_lines_matches(tmp_path):
    pdf = make_pdf(tmp_path / "p.pdf", [["A fake manu-", "script sentence that wraps here."]])
    got, _ = run(tmp_path, pdf, [{"id": "1", "excerpt": "A fake manuscript sentence that wraps", "ms_page": 1}])
    assert got["1"]["method"] == "exact" and got["1"]["pdf_page"] == 1


def test_curly_quotes_and_ligatures_normalize():
    assert loc.key("“ﬁrm”") == loc.key('"firm"') == "firm"


def test_match_on_two_pages_resolved_by_ms_page(tmp_path):
    same = "the fake result holds in every fake sample"
    pdf = make_pdf(tmp_path / "p.pdf", [["1", same], ["2", "Other fake text."], ["3", same]])
    got, _ = run(tmp_path, pdf, [{"id": "a", "excerpt": same, "ms_page": 3}, {"id": "b", "excerpt": same, "ms_page": 1}])
    assert got["a"]["pdf_page"] == 3 and got["b"]["pdf_page"] == 1


def test_first_twelve_words_when_the_full_excerpt_is_paraphrased(tmp_path):
    pdf = make_pdf(tmp_path / "p.pdf", [["one two three four five six seven eight nine ten eleven twelve thirteen"]])
    got, _ = run(tmp_path, pdf, [{"id": "1", "excerpt": "one two three four five six seven eight nine ten eleven twelve CHANGED", "ms_page": None}])
    assert got["1"]["method"] == "exact"


def test_page_labels_map_ms_page(tmp_path):
    labels = [{"startpage": 0, "prefix": "", "style": "r", "firstpagenum": 1},
              {"startpage": 2, "prefix": "", "style": "D", "firstpagenum": 1}]
    pdf = make_pdf(tmp_path / "p.pdf", [["Fake i."], ["Fake ii."], ["Fake body one."], ["Fake body two."]], labels)
    got, _ = run(tmp_path, pdf, [{"id": "1", "excerpt": "no such fake text anywhere", "ms_page": 2}])
    assert got["1"] == {"pdf_page": 4, "rect": None, "rects": [], "method": "page_only",
                        "label": "ms p. 2 (PDF p. 4)"}


def test_fitted_offset_from_printed_numbers(tmp_path):
    pdf = make_pdf(tmp_path / "p.pdf", [["Fake title page."], ["Fake abstract."], ["1", "Fake body."], ["2", "More fake."], ["3", "End."]])
    got, _ = run(tmp_path, pdf, [{"id": "1", "excerpt": "missing fake words here", "ms_page": 3}])
    assert got["1"]["pdf_page"] == 5 and got["1"]["method"] == "page_only"


def test_no_labels_no_numbers_is_approximate(tmp_path):
    pdf = make_pdf(tmp_path / "p.pdf", [["Fake a."], ["Fake b."], ["Fake c."]])
    got, _ = run(tmp_path, pdf, [{"id": "1", "excerpt": "missing fake words here", "ms_page": 2}])
    assert got["1"]["method"] == "approximate" and got["1"]["pdf_page"] == 2
    assert got["1"]["label"] == "ms p. 2 (PDF p. 2, approximate)"


def test_not_found(tmp_path):
    pdf = make_pdf(tmp_path / "p.pdf", [["Fake a."]])
    got, counts = run(tmp_path, pdf, [{"id": "1", "excerpt": "missing fake words", "ms_page": None},
                                      {"id": "2", "excerpt": None, "ms_page": 40}])
    assert got["1"]["method"] == got["2"]["method"] == "not_found"
    assert got["1"]["pdf_page"] is None and got["1"]["label"] == "location not found"
    assert counts["not_found"] == 2


def test_excerpt_spanning_a_page_break_matches_exact(tmp_path):
    filler = [f"Fake filler line {i}." for i in range(1, 50)]
    page1_lines = filler + ["the fake sentence continues onto"]
    page2_lines = ["the next page here."]
    pdf = make_pdf(tmp_path / "p.pdf", [page1_lines, page2_lines])
    excerpt = "the fake sentence continues onto the next page here"
    got, _ = run(tmp_path, pdf, [{"id": "1", "excerpt": excerpt, "ms_page": None}])
    assert got["1"]["pdf_page"] == 1 and got["1"]["method"] == "exact"
    x0, y0, x1, y1 = got["1"]["rect"]
    assert y0 > 400


def test_known_pdf_page_is_kept_when_the_excerpt_is_missing(tmp_path):
    pdf = make_pdf(tmp_path / "p.pdf", [["Fake a."], ["Fake table page."]])
    got, _ = run(tmp_path, pdf, [{"id": "1", "excerpt": None, "ms_page": None, "pdf_page": 2}])
    assert got["1"]["pdf_page"] == 2 and got["1"]["method"] == "page_only"


def test_unreadable_pdf_exit_2(tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_text("not a pdf")
    (tmp_path / "i.json").write_text("[]")
    r = subprocess.run([sys.executable, str(SCRIPTS / "locate_issues.py"), str(bad), str(tmp_path / "i.json"),
                        str(tmp_path / "o.json")], capture_output=True, text=True)
    assert r.returncode == 2
