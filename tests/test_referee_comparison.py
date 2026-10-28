"""Tests for eval/referee_comparison. Every fixture here is FAKE: made-up items, sheet rows, and ratings."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RC = ROOT / "eval" / "referee_comparison"
sys.path.insert(0, str(RC))
sys.path.insert(0, str(RC / "pool"))

import count  # noqa: E402
import table3  # noqa: E402
import table3_from_counts  # noqa: E402
import table3_sheet  # noqa: E402
from check_pool import validate  # noqa: E402
from score_guess import public, score  # noqa: E402
import build_matchdata  # noqa: E402
import export  # noqa: E402

FAKE_TEXT = "FAKE: the main estimate uses a sample that drops late entrants, which may bias the effect upward here."


# --- counts.json and Table 3 ---

def test_counts_reproduce_table_3():
    counts = json.loads((RC / "counts.json").read_text())
    assert table3_from_counts.check(counts) == []
    r = table3_from_counts.rows(counts)
    expected = {"factual": (31, 20, 46, [58, 85], [55, 24]),
                "substantive judgment": (73, 59, 50, [73, 78], [52, 54]),
                "preference": (20, 8, 3, [55, 100], [30, 0]),
                "all": (124, 87, 99, [66, 82], [49, 38])}
    for cls, (n, also, po, valid, serious) in expected.items():
        got = r[cls]
        assert (got["referee_points"], got["also_raised"], got["plumb_only"]) == (n, also, po), cls
        assert got["valid_pct"] == valid and got["serious_pct"] == serious, cls


def test_counts_json_holds_only_labels_and_integers():
    counts = json.loads((RC / "counts.json").read_text())
    assert set(counts) == {"classes", "papers"}
    assert set(counts["papers"]) == {"A", "B", "C", "D"}
    for group in ("classes", "papers"):
        for row in counts[group].values():
            assert all(isinstance(v, int) for v in row.values())


def test_counts_check_catches_a_bad_total():
    counts = json.loads((RC / "counts.json").read_text())
    counts["classes"]["factual"]["referee_points"] += 1
    assert any("referee_points" in e for e in table3_from_counts.check(counts))


def test_table3_from_counts_cli_prints_the_total_row():
    r = subprocess.run([sys.executable, str(RC / "table3_from_counts.py")], capture_output=True, text=True)
    assert r.returncode == 0 and "all | 124 | 87 (70%) | 99 | 66% / 82% | 49% / 38%" in r.stdout


# --- pool validator and source guess ---

def item(**kw):
    base = {"id": "i-a1b2c3", "paper": "C", "paper_label": "Paper A", "title": "FAKE title",
            "text": FAKE_TEXT, "source": "referee", "class": "substantive judgment", "er_only": False,
            "match": [], "sheet_row": "C-R01"}
    base.update(kw)
    return base


def test_valid_item_passes():
    assert validate([item()]) == []


def test_source_cue_rejected():
    for cue in ["FAKE: the authors should report the interval for this estimate in the main table now.",
                "FAKE: Plumb flags that the interval for this estimate is missing from the main table.",
                "FAKE: weakens a claim, since the interval for this estimate is missing from the table.",
                "FAKE: the numeric-fidelity check found that the interval for this estimate is missing here."]:
        errs = validate([item(text=cue)])
        assert errs and "cue" in errs[0]


def test_length_bounds():
    assert validate([item(text="Too short.")])
    assert validate([item(text=" ".join(["word"] * 46))])


def test_cross_paper_and_one_sided_matches_rejected():
    a = item(id="i-000001", source="referee", match=["i-000002"])
    b = item(id="i-000002", source="plumb", paper="D", paper_label="Paper B", match=["i-000001"])
    assert any("paper" in e for e in validate([a, b]))
    c = item(id="i-000002", source="referee", match=[])
    errs = validate([a, c])
    assert any("mutual" in e for e in errs) and any("source" in e for e in errs)


def test_old_paper_keys_are_rejected():
    assert any("paper" in e for e in validate([item(paper="XYZ")]))


def test_score_guess_and_public_projection():
    items = [{"id": "i-000001", "source": "referee", "paper_label": "Paper A", "title": "T", "text": "x", "class": "factual"},
             {"id": "i-000002", "source": "plumb", "paper_label": "Paper A", "title": "T", "text": "y", "class": "factual"}]
    s = score(items, [{"id": "i-000001", "guess": "referee", "confidence": "high"},
                      {"id": "i-000002", "guess": "referee", "confidence": "high"}])
    assert s["n"] == 2 and s["accuracy"] == 0.5 and s["confident_correct"] == ["i-000001"]
    with pytest.raises(ValueError):
        score(items, [{"id": "i-000001", "guess": "referee", "confidence": "low"}])
    assert all(set(x) == {"id", "paper_label", "title", "text"} for x in public(items))


def test_build_matchdata_reads_strength_from_the_sheet_row():
    rows = {"C-R01": "| C-R01 | x | both | ... | V2 PARTIAL (weak) |", "C-R02": "| C-R02 | x | both | Capped MATCH |"}
    items = [item(id="i-000001", sheet_row="C-R01", match=["i-000003"]),
             item(id="i-000002", sheet_row="C-R02", match=["i-000003"]),
             item(id="i-000004", sheet_row="C-R03", match=[]),
             item(id="i-000003", source="plumb", sheet_row="C-P01", match=["i-000001", "i-000002"])]
    out = build_matchdata.build(items, rows)
    assert out["i-000001"]["proposed_strength"] == "partial"
    assert out["i-000002"]["proposed_strength"] == "full"
    assert out["i-000004"]["proposed_strength"] == "none"
    assert [c["id"] for c in out["i-000001"]["candidates"]] == ["i-000003"]


# --- table3.py on fake ratings ---

def mk(i, src, cls, paper="C", match=()):
    return {"id": i, "source": src, "class": cls, "paper": paper, "er_only": False, "match": list(match)}


ITEMS = [mk("r1", "referee", "factual", match=["p1"]), mk("r2", "referee", "preference"),
         mk("p1", "plumb", "factual", match=["r1"]), mk("p2", "plumb", "substantive judgment")]


def ans(c, imp, kind=None):
    return {"correctness": c, "importance": imp, "kind": kind}


RATINGS = {"u1": {"rater": "primary", "answers": {
    "r1": ans("valid", "Weakens a claim", "factual"), "r2": ans("doubtful", "Minor", "preference"),
    "p1": ans("valid", "Undermines the main claim", "factual"), "p2": ans("wrong", "Minor", "substantive judgment")}}}
MATCHES = {"r1": {"strength": "partial", "match": ["p1"]}, "r2": {"strength": "none", "match": []}}


def test_table3_counts_and_shares():
    res = table3.build(ITEMS, RATINGS, MATCHES)
    f = res["rows"]["factual"]
    assert f["referee"] == 1 and f["also_raised"] == 1 and f["plumb_only"] == 0
    a = res["rows"]["all"]
    assert a["referee"] == 2 and a["referee_valid"] == 0.5 and a["plumb_serious"] == 0.5


def test_table3_missing_rating_or_match_names_the_ids():
    r = {"u1": {"rater": "primary", "answers": {k: v for k, v in RATINGS["u1"]["answers"].items() if k != "p2"}}}
    with pytest.raises(table3.MissingData, match="p2"):
        table3.build(ITEMS, r, MATCHES)
    with pytest.raises(table3.MissingData, match="r2"):
        table3.build(ITEMS, RATINGS, {"r1": MATCHES["r1"]})


def test_table3_agreement_on_the_heldout_paper():
    items = [mk("r1", "referee", "factual", paper="A"), mk("p1", "plumb", "factual", paper="A")]
    r = {"u1": {"rater": "primary", "answers": {"r1": ans("valid", "Minor", "factual"), "p1": ans("valid", "Minor", "factual")}},
         "u2": {"rater": "second", "answers": {"r1": ans("valid", "Minor"), "p1": ans("wrong", "Minor")}}}
    res = table3.build(items, r, {"r1": {"strength": "none", "match": []}})
    assert res["agreement"]["n"] == 2 and res["agreement"]["correctness"] == 0.5


def test_table3_cli_exit_2_and_latex(tmp_path, capsys):
    (tmp_path / "i.json").write_text(json.dumps(ITEMS))
    (tmp_path / "r.json").write_text(json.dumps({"u1": {"rater": "primary", "answers": {}}}))
    (tmp_path / "m.json").write_text(json.dumps(MATCHES))
    code = table3.main(["--items", str(tmp_path / "i.json"), "--ratings", str(tmp_path / "r.json"),
                        "--matches", str(tmp_path / "m.json"), "--out", str(tmp_path / "t.tex")])
    assert code == 2 and "r1" in capsys.readouterr().err and not (tmp_path / "t.tex").exists()
    tex = table3.latex(table3.build(ITEMS, RATINGS, MATCHES))
    assert "\\toprule" in tex and "\\bottomrule" in tex


# --- count.py and table3_sheet.py on a fake sheet ---

HEADER = "| id | point | source | type | class | class note | validity (Plumb-only) | severity | ER | notes |"
FAKE_SHEET = "\n".join([
    "# FAKE coding sheet for tests", "", "## C", "", HEADER, "|---|---|---|---|---|---|---|---|---|---|",
    "| C-R01 | fake point one | both | verifiable (paper) | factual |  |  | Minor (3) |  | V2 MATCH fake |",
    "| C-R02 | fake point two | referees only | judgment | preference |  |  | Minor |  | V2 MISSED fake |",
    "| C-P01 | fake point three | Plumb only | judgment | substantive judgment |  | valid: fake | Minor (4) |  | fake |",
    "", "## A", "", HEADER, "|---|---|---|---|---|---|---|---|---|---|",
    "| A-R01 | fake point four | both | judgment | substantive judgment |  |  | Minor (2) | only | Capped PARTIAL (weak) |",
])


def test_count_parses_and_counts_a_fake_sheet(tmp_path):
    sheet = tmp_path / "sheet.md"
    sheet.write_text(FAKE_SHEET)
    rows = count.parse_sheet(sheet)
    count.check(rows)
    c = count.counts(rows)
    assert (c["M"], c["m1"], c["m1_er"], c["m2"], c["m3"]) == (3, 1, 2, 1, 1)
    assert count.counts([r for r in rows if r["paper"] == "A"])["m1_weak"] == 0
    out = tmp_path / "counts.md"
    assert count.main(["--sheet", str(sheet), "--out", str(out)]) == 0
    assert "| Total | 3 | 1 |" in out.read_text()


def test_count_rejects_er_only_off_the_heldout_paper(tmp_path):
    bad = FAKE_SHEET.replace("| C-R01 | fake point one | both | verifiable (paper) | factual |  |  | Minor (3) |  |",
                             "| C-R01 | fake point one | both | verifiable (paper) | factual |  |  | Minor (3) | only |")
    sheet = tmp_path / "sheet.md"
    sheet.write_text(bad)
    with pytest.raises(SystemExit, match="held-out"):
        count.check(count.parse_sheet(sheet))


def test_table3_sheet_on_a_fake_sheet(tmp_path):
    sheet = tmp_path / "sheet.md"
    sheet.write_text(FAKE_SHEET)
    rows = count.parse_sheet(sheet)
    items = [mk("i1", "referee", "factual") | {"sheet_row": "C-R01"},
             mk("i2", "referee", "preference") | {"sheet_row": "C-R02"},
             mk("i3", "plumb", "substantive judgment") | {"sheet_row": "C-P01"},
             mk("i4", "referee", "substantive judgment", paper="A") | {"sheet_row": "A-R01"}]
    answers = {"i1": ans("valid", "Minor"), "i2": ans("wrong", "Weakens a claim"),
               "i3": ans("valid", "Weakens a claim"), "i4": ans("doubtful", "Minor")}
    res = table3_sheet.build(rows, items, answers)
    assert res["rows"]["all"]["referee"] == {"n": 3, "valid": 1, "wrong": 1, "serious": 1}
    assert res["rows"]["all"]["plumb_only"] == {"n": 1, "valid": 1, "wrong": 0, "serious": 1}
    assert res["rows"]["factual"]["also_raised"] == 1
    assert "All issues & 3 & 1 (33\\%) & 1" in table3_sheet.latex(res)


# --- export.py ---

def test_export_keeps_confirmed_matches_and_assigns_roles():
    items = {"r1": mk("r1", "referee", "factual", paper="A"), "p1": mk("p1", "plumb", "factual", paper="A"),
             "r2": mk("r2", "referee", "factual", paper="C")}
    matchdata = {"r1": {"proposed": ["p1"], "proposed_strength": "partial"},
                 "r2": {"proposed": [], "proposed_strength": "none"}}
    cards = {"r1": {"strength": "full", "match": ["p1"]}}
    full = {i: {"correctness": "valid", "importance": "Minor", "kind": "factual", "note": "fake"} for i in items}
    docs = {"d1": {"answers": full}, "d2": {"answers": {i: full[i] for i in ("r1", "p1")}}}
    out, ratings = export.build(items, matchdata, cards, docs, {"d1": "primary", "d2": "second"}, "A")
    assert out["r1"] == {"strength": "full", "match": ["p1"], "origin": "confirmed"}
    assert out["r2"]["origin"] == "proposed"
    assert ratings["d1"]["rater"] == "primary" and "note" not in ratings["d1"]["answers"]["r1"]


def test_referee_comparison_scripts_print_help():
    for script in ("count.py", "export.py", "table3.py", "table3_sheet.py", "table3_from_counts.py",
                   "pool/build_pool.py", "pool/make_seed.py"):
        r = subprocess.run([sys.executable, str(RC / script), "--help"], capture_output=True, text=True)
        assert r.returncode == 0 and "usage" in r.stdout.lower(), script
