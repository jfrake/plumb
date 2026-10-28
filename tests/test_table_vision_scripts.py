from __future__ import annotations
import csv, json, subprocess, sys
from pathlib import Path
import pymupdf

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/review/scripts"
sys.path.insert(0, str(SCRIPTS))
import compare_transcriptions as ct

def _pdf(path, pages):
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page(); page.insert_text((72, 72), text)
    doc.save(path)

def test_render_finds_caption_pages(tmp_path):
    pdf = tmp_path / "p.pdf"
    _pdf(pdf, ["Introduction text.", "Table 2\nResults", "As Table 2 shows, effects are large."])
    out = tmp_path / "pages"
    r = subprocess.run([sys.executable, str(SCRIPTS / "render_table_pages.py"), str(pdf), str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    idx = json.loads((out / "index.json").read_text())
    assert [e["page"] for e in idx] == [2] and idx[0]["labels"] == ["2"]
    assert (out / idx[0]["image"]).exists()

def test_render_no_tables_flag(tmp_path):
    pdf = tmp_path / "p.pdf"; _pdf(pdf, ["Only prose here."])
    out = tmp_path / "pages"
    r = subprocess.run([sys.executable, str(SCRIPTS / "render_table_pages.py"), str(pdf), str(out)], capture_output=True, text=True)
    assert r.returncode == 2 and (out / "no_tables.flag").exists()

def test_render_explicit_pages_merge(tmp_path):
    pdf = tmp_path / "p.pdf"; _pdf(pdf, ["Table 1\nA", "continued rows"])
    out = tmp_path / "pages"
    subprocess.run([sys.executable, str(SCRIPTS / "render_table_pages.py"), str(pdf), str(out)], check=True)
    subprocess.run([sys.executable, str(SCRIPTS / "render_table_pages.py"), str(pdf), str(out), "--pages", "2"], check=True)
    assert sorted(e["page"] for e in json.loads((out / "index.json").read_text())) == [1, 2]

def test_normalize():
    assert ct.normalize(" −0.26** ") == "-0.26**"
    assert ct.normalize("(0.07)") == "(0.07)"

def test_compare_identical():
    rows = [["", "(1)"], ["x", "0.26**"], ["", "(0.07)"]]
    res = ct.compare(rows, [list(r) for r in rows])
    assert res["shape_match"] and res["disagreements"] == [] and res["agreed"] == rows

def test_compare_cell_difference_blanks_cell():
    a = [["", "(1)"], ["x", "0.26**"]]; b = [["", "(1)"], ["x", "0.62**"]]
    res = ct.compare(a, b)
    assert res["agreed"][1][1] == ""
    assert res["disagreements"] == [{"row": 1, "col": 1, "a": "0.26**", "b": "0.62**", "reason": "cell"}]

def test_compare_shape_mismatch():
    res = ct.compare([["a", "b"]], [["a", "b"], ["c", "d"]])
    assert not res["shape_match"] and res["agreed"] is None
    assert res["disagreements"][0]["reason"] == "shape"

def test_cli_writes_agreed_and_missing(tmp_path):
    a = tmp_path / "a"; b = tmp_path / "b"; out = tmp_path / "out"
    a.mkdir(); b.mkdir()
    for d, val in ((a, "0.26"), (b, "0.26")):
        with open(d / "table_01.csv", "w", newline="") as fh:
            csv.writer(fh).writerows([["", "(1)"], ["x", val]])
    with open(a / "table_02.csv", "w", newline="") as fh:
        csv.writer(fh).writerows([["only", "a"]])
    r = subprocess.run([sys.executable, str(SCRIPTS / "compare_transcriptions.py"), str(a), str(b), str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert (out / "table_01.csv").exists() and not (out / "table_02.csv").exists()
    dis = json.loads((out / "disagreements.json").read_text())
    assert dis == [{"table": "table_02.csv", "row": None, "col": None, "a": "present", "b": "absent",
                    "reason": "missing_in_b", "whole_table": True,
                    "a_file": str(a / "table_02.csv"), "b_file": None}]
    assert "WHOLE-TABLE DISAGREEMENT: table_02.csv (missing_in_b)" in r.stdout

def test_cli_reports_shape_mismatch_as_whole_table(tmp_path):
    a = tmp_path / "a"; b = tmp_path / "b"; out = tmp_path / "out"
    a.mkdir(); b.mkdir()
    with open(a / "table_03.csv", "w", newline="") as fh:
        csv.writer(fh).writerows([["", "(1)"], ["x", "0.26"]])
    with open(b / "table_03.csv", "w", newline="") as fh:
        csv.writer(fh).writerows([["", "(1)"], ["x", "0.26"], ["", "(0.07)"]])
    r = subprocess.run([sys.executable, str(SCRIPTS / "compare_transcriptions.py"), str(a), str(b), str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert not (out / "table_03.csv").exists()
    dis = json.loads((out / "disagreements.json").read_text())
    assert dis == [{"table": "table_03.csv", "row": None, "col": None,
                    "a": "2 rows x 2 cols", "b": "3 rows x 2 cols", "reason": "shape", "whole_table": True,
                    "a_file": str(a / "table_03.csv"), "b_file": str(b / "table_03.csv")}]
    assert "WHOLE-TABLE DISAGREEMENT: table_03.csv (shape)" in r.stdout

def test_render_finds_captions_case_insensitive(tmp_path):
    pdf = tmp_path / "p.pdf"
    _pdf(pdf, ["TABLE 2\nResults", "Table A1:\nAppendix table"])
    out = tmp_path / "pages"
    r = subprocess.run([sys.executable, str(SCRIPTS / "render_table_pages.py"), str(pdf), str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    idx = json.loads((out / "index.json").read_text())
    assert sorted(e["page"] for e in idx) == [1, 2]
    assert sorted(e["labels"][0] for e in idx) == ["2", "A1"]

def test_render_no_tables_flag_cleared_on_merge(tmp_path):
    pdf = tmp_path / "p.pdf"; _pdf(pdf, ["Only prose here.", "more prose"])
    out = tmp_path / "pages"
    r = subprocess.run([sys.executable, str(SCRIPTS / "render_table_pages.py"), str(pdf), str(out)], capture_output=True, text=True)
    assert r.returncode == 2 and (out / "no_tables.flag").exists()
    r = subprocess.run([sys.executable, str(SCRIPTS / "render_table_pages.py"), str(pdf), str(out), "--pages", "1"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert not (out / "no_tables.flag").exists()
    assert (out / "index.json").exists()

def test_render_page_out_of_range_error(tmp_path):
    pdf = tmp_path / "p.pdf"; _pdf(pdf, ["Only one page"])
    out = tmp_path / "pages"
    r = subprocess.run([sys.executable, str(SCRIPTS / "render_table_pages.py"), str(pdf), str(out), "--pages", "5"], capture_output=True, text=True)
    assert r.returncode == 1, f"Expected exit 1, got {r.returncode}"
    assert "page 5 is outside this PDF (it has 1 pages)" in r.stderr, f"stderr: {r.stderr}"


# Architecture review I-5: a table continued across pages is one index entry.
def _render(pdf, out, *extra):
    return subprocess.run([sys.executable, str(SCRIPTS / "render_table_pages.py"), str(pdf), str(out), *extra],
                          capture_output=True, text=True)

def test_render_groups_continued_table_into_one_entry(tmp_path):
    pdf = tmp_path / "p.pdf"
    _pdf(pdf, ["Table 3\nFirst rows", "Table 3 (continued)\nMore rows", "Table 4\nOther results"])
    out = tmp_path / "pages"
    r = _render(pdf, out)
    assert r.returncode == 0, r.stderr
    idx = json.loads((out / "index.json").read_text())
    assert [e["pages"] for e in idx] == [[1, 2], [3]]
    assert idx[0]["labels"] == ["3"] and idx[0]["page"] == 1
    assert idx[0]["images"] == ["page_001.png", "page_002.png"]
    assert all((out / img).exists() for img in idx[0]["images"])

def test_render_groups_continued_caption_across_a_gap(tmp_path):
    pdf = tmp_path / "p.pdf"
    _pdf(pdf, ["Table 2\nFirst rows", "Figure 1\nA plot", "TABLE 2 Continued\nMore rows"])
    out = tmp_path / "pages"
    assert _render(pdf, out).returncode == 0
    idx = json.loads((out / "index.json").read_text())
    assert [e["pages"] for e in idx] == [[1, 3]]

def test_render_keeps_different_tables_on_consecutive_pages_apart(tmp_path):
    pdf = tmp_path / "p.pdf"
    _pdf(pdf, ["Table 1\nA", "Table 2\nB"])
    out = tmp_path / "pages"
    assert _render(pdf, out).returncode == 0
    idx = json.loads((out / "index.json").read_text())
    assert [e["pages"] for e in idx] == [[1], [2]]

def test_render_pages_with_table_adds_to_that_entry(tmp_path):
    pdf = tmp_path / "p.pdf"
    _pdf(pdf, ["Table 5\nA", "rows with no caption"])
    out = tmp_path / "pages"
    assert _render(pdf, out).returncode == 0
    r = _render(pdf, out, "--pages", "2", "--table", "5")
    assert r.returncode == 0, r.stderr
    idx = json.loads((out / "index.json").read_text())
    assert len(idx) == 1 and idx[0]["pages"] == [1, 2]
    assert idx[0]["images"] == ["page_001.png", "page_002.png"]

def test_render_table_flag_unknown_label_fails(tmp_path):
    pdf = tmp_path / "p.pdf"
    _pdf(pdf, ["Table 5\nA", "rows"])
    out = tmp_path / "pages"
    assert _render(pdf, out).returncode == 0
    r = _render(pdf, out, "--pages", "2", "--table", "9")
    assert r.returncode == 1 and "no entry for table 9" in r.stderr
