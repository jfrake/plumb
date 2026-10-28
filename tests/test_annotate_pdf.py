"""annotate_pdf.py on a small PDF generated here. Every PDF, issue, and sentence is fake."""
from __future__ import annotations
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pymupdf
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/review/scripts"

PAGES = [["Fake cover page."], ["The fake widgets rose sharply in the", "second quarter of the fake year."],
         ["A fake second claim sits here."]]
ISSUES = [
    {"id": "1", "title": "Fake widgets", "severity": "Undermines the main claim", "summary": "Fake summary one. It matters."},
    {"id": "2", "title": "Fake claim", "severity": "Weakens a claim", "summary": "Fake summary two."},
    {"id": "3", "title": "Fake spot", "severity": "Minor", "summary": "Fake summary three."},
    {"id": "4", "title": "Fake nowhere", "severity": None, "summary": "Fake summary four."},
]


def _pdf(path: Path) -> Path:
    doc = pymupdf.open()
    for lines in PAGES:
        page = doc.new_page()
        y = 72
        for line in lines:
            page.insert_text((72, y), line)
            y += 14
    doc.save(str(path))
    return path


def _run(tmp_path, issues=ISSUES):
    pdf = _pdf(tmp_path / "fakepaper.pdf")
    before = hashlib.sha256(pdf.read_bytes()).hexdigest()
    src, locs, out = tmp_path / "v.json", tmp_path / "l.json", tmp_path / "fakepaper_annotated.pdf"
    src.write_text(json.dumps(issues))
    excerpts = {"1": "The fake widgets rose sharply in the second quarter", "2": "A fake second claim sits here"}
    loc_in = [{"id": i["id"], "excerpt": excerpts.get(i["id"]), "ms_page": {"3": 3}.get(i["id"])} for i in issues]
    (tmp_path / "li.json").write_text(json.dumps(loc_in))
    r = subprocess.run([sys.executable, str(SCRIPTS / "locate_issues.py"), str(pdf), str(tmp_path / "li.json"), str(locs)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout
    r = subprocess.run([sys.executable, str(SCRIPTS / "annotate_pdf.py"), str(pdf), str(src), str(locs), str(out)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return pdf, before, out, json.loads(locs.read_text()), json.loads(r.stdout)


def _annots(doc):
    """{issue id: {page, type, rect, color, content}}, read while each page is loaded."""
    out = {}
    for i in range(doc.page_count):
        page = doc[i]
        for a in page.annots():
            content = a.info["content"]
            out[content.split(".")[0]] = {"page": i, "type": a.type[1], "rect": pymupdf.Rect(a.rect),
                                          "color": tuple(round(c, 2) for c in a.colors["stroke"]),
                                          "content": content}
    return out


def test_index_page_links_each_issue_to_its_page(tmp_path):
    _, _, out, _, placed = _run(tmp_path)
    doc = pymupdf.open(str(out))
    assert doc.page_count == len(PAGES) + 1
    index = doc[0].get_text()
    assert "Notes produced with Plumb, an AI review tool." in index
    for i in ISSUES:
        assert f"{i['id']}. " in index and i["title"] in index
    assert "location not found" in index
    assert "(ms p. 3, PDF p. 3, approximate)" in index and "((" not in index
    targets = [l["page"] for l in doc[0].get_links() if l["kind"] == pymupdf.LINK_GOTO]
    assert targets == [2, 3, 3]
    assert placed == {"highlight": 2, "page_note": 1, "index_only": 1}


def test_highlights_sit_on_the_located_rect_with_severity_colors(tmp_path):
    _, _, out, locs, _ = _run(tmp_path)
    doc = pymupdf.open(str(out))
    annots = _annots(doc)
    a = annots["1"]
    assert a["page"] == 2 and a["type"] == "Highlight"
    want = pymupdf.Rect(locs["1"]["rect"])
    assert abs(a["rect"].y0 - want.y0) < 5 and abs(a["rect"].x1 - want.x1) < 8
    assert a["color"] == (1.0, 0.6, 0.6)
    assert annots["2"]["color"] == (1.0, 0.8, 0.5)
    assert a["content"] == "1. Undermines the main claim. Fake summary one. It matters."


def test_spot_not_found_puts_a_note_at_the_top_of_the_page(tmp_path):
    _, _, out, _, _ = _run(tmp_path)
    a = _annots(pymupdf.open(str(out)))["3"]
    assert a["page"] == 3 and a["type"] == "Text" and a["rect"].y0 < 60
    assert "exact spot not found" in a["content"]
    assert a["color"] == (1.0, 0.95, 0.5)


def test_two_page_notes_on_one_page_do_not_overlap(tmp_path):
    pdf = _pdf(tmp_path / "fakepaper.pdf")
    issues = [
        {"id": "a", "title": "Fake a", "severity": "Minor", "summary": "Fake a summary."},
        {"id": "b", "title": "Fake b", "severity": "Minor", "summary": "Fake b summary."},
    ]
    locations = {
        "a": {"pdf_page": 2, "rect": None, "rects": [], "method": "page_only", "label": "PDF p. 2"},
        "b": {"pdf_page": 2, "rect": None, "rects": [], "method": "page_only", "label": "PDF p. 2"},
    }
    src, locs, out = tmp_path / "v.json", tmp_path / "l.json", tmp_path / "fakepaper_annotated.pdf"
    src.write_text(json.dumps(issues))
    locs.write_text(json.dumps(locations))
    r = subprocess.run([sys.executable, str(SCRIPTS / "annotate_pdf.py"), str(pdf), str(src), str(locs), str(out)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    annots = _annots(pymupdf.open(str(out)))
    ra, rb = annots["a"]["rect"], annots["b"]["rect"]
    assert annots["a"]["page"] == 2 and annots["b"]["page"] == 2
    assert not ra.intersects(rb)


def test_page_not_found_appears_only_in_the_index(tmp_path):
    _, _, out, _, _ = _run(tmp_path)
    assert "4" not in _annots(pymupdf.open(str(out)))


def test_original_pdf_is_unchanged(tmp_path):
    pdf, before, _, _, _ = _run(tmp_path)
    assert hashlib.sha256(pdf.read_bytes()).hexdigest() == before


def test_refuses_to_write_over_the_original(tmp_path):
    pdf = _pdf(tmp_path / "fakepaper.pdf")
    (tmp_path / "v.json").write_text("[]")
    (tmp_path / "l.json").write_text("{}")
    r = subprocess.run([sys.executable, str(SCRIPTS / "annotate_pdf.py"), str(pdf), str(tmp_path / "v.json"),
                        str(tmp_path / "l.json"), str(pdf)], capture_output=True, text=True)
    assert r.returncode == 2 and "never changes the original" in r.stdout


def test_long_issue_lists_run_onto_more_index_pages(tmp_path):
    many = [{"id": str(n), "title": f"Fake issue {n}", "severity": "Minor", "summary": "Fake."} for n in range(1, 61)]
    _, _, out, _, _ = _run(tmp_path, many)
    doc = pymupdf.open(str(out))
    assert doc.page_count == len(PAGES) + 2
    assert "Fake issue 60" in doc[1].get_text()
    assert "(continued)" in doc[1].get_text()
    targets = [l["page"] for l in doc[0].get_links() if l["kind"] == pymupdf.LINK_GOTO]
    assert targets == [3, 4, 4]


def test_links_on_a_second_index_page_land_on_the_shifted_pages(tmp_path):
    # Listed from 60 down, so the three located issues sit on the second index page.
    many = [{"id": str(n), "title": f"Fake issue {n}", "severity": "Minor", "summary": "Fake."} for n in range(60, 0, -1)]
    _, _, out, _, _ = _run(tmp_path, many)
    doc = pymupdf.open(str(out))
    assert doc.page_count == len(PAGES) + 2
    links = lambda p: [l["page"] for l in doc[p].get_links() if l["kind"] == pymupdf.LINK_GOTO]
    assert links(0) == [] and links(1) == [4, 4, 3]
    assert "The fake widgets rose sharply" in doc[3].get_text()
    assert "A fake second claim" in doc[4].get_text()


def test_index_lines_wrap_within_the_page(tmp_path):
    long = [dict(ISSUES[0], title="A fake and very long title about fake widgets " * 4)] + ISSUES[1:]
    _, _, out, _, _ = _run(tmp_path, long)
    page = pymupdf.open(str(out))[0]
    spans = [s for b in page.get_text("dict")["blocks"] for l in b.get("lines", []) for s in l["spans"]]
    assert spans and max(s["bbox"][2] for s in spans) <= page.rect.width - 54 + 1
    assert " ".join(page.get_text().split()).count("A fake and very long title about fake widgets") == 4
    targets = [l["page"] for l in page.get_links() if l["kind"] == pymupdf.LINK_GOTO]
    assert targets == [2, 3, 3]


def test_index_page_renders_unicode_and_typographic_characters(tmp_path):
    title = "β ≥ 0.5 “quoted” en–2005 …"
    issues = [dict(ISSUES[0], title=title)] + ISSUES[1:]
    _, _, out, _, _ = _run(tmp_path, issues)
    index = " ".join(pymupdf.open(str(out))[0].get_text().split())
    assert title in index


def test_the_unicode_font_is_subset_not_embedded_whole(tmp_path):
    pdf, _, out, _, _ = _run(tmp_path, ISSUES[:2])
    grown = out.stat().st_size - pdf.stat().st_size
    assert grown < 300 * 1024, f"annotated PDF grew by {grown} bytes; the font is not subset"


def test_wrap_breaks_at_spaces_and_cuts_an_overlong_word():
    import importlib
    sys.path.insert(0, str(SCRIPTS))
    ann = importlib.import_module("annotate_pdf")
    lines = ann.wrap("fake " * 40 + "x" * 200, 200)
    assert len(lines) > 2 and all(pymupdf.get_text_length(l, fontsize=ann.FONT_SIZE) <= 200 for l in lines)
    assert "".join(lines).replace(" ", "") == "fake" * 40 + "x" * 200


def _check(path):
    return subprocess.run([sys.executable, str(SCRIPTS / "annotate_pdf.py"), "--check", str(path)],
                          capture_output=True, text=True)


def test_check_passes_a_built_annotated_pdf(tmp_path):
    _, _, out, _, _ = _run(tmp_path)
    r = _check(out)
    assert r.returncode == 0, r.stdout


def test_check_fails_a_missing_unreadable_or_index_less_file(tmp_path):
    r = _check(tmp_path / "fakepaper_annotated.pdf")
    assert r.returncode == 1 and "does not exist" in r.stdout
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a pdf at all")
    r = _check(bad)
    assert r.returncode == 1 and "cannot be opened" in r.stdout
    plain = _pdf(tmp_path / "plain.pdf")
    r = _check(plain)
    assert r.returncode == 1 and "index page" in r.stdout
