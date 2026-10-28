from __future__ import annotations
import importlib.util
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "packs" / "inference" / "fixtures" / "planted-1"
sys.path.insert(0, str(ROOT / "skills" / "review" / "scripts"))
import verify_arithmetic as va  # noqa: E402


def _arith():
    spec = importlib.util.spec_from_file_location("inference_arith", ROOT / "packs" / "inference" / "scripts" / "inference_arith.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _flags(record_id, inputs, ia):
    if record_id in inputs["claims"]:
        return va.check_claim(inputs["claims"][record_id])["flag"]
    if record_id in inputs["arith"]:
        return ia.run_record(inputs["arith"][record_id])["flag"]
    s = inputs["stars"][record_id]
    rows = [["Variables", "(1)"], [s["label"], s["coef"] + s["mark"]], ["", "(" + s["se"] + ")"]]
    return any(f["status"] == "error" for f in va.check_stars("table_fixture.csv", rows, s["note"]))


def test_fixture_plants_and_decoys_check_out_with_the_scripts():
    exp = yaml.safe_load((FIXTURE / "expected.yaml").read_text(encoding="utf-8"))
    assert exp["script_checked"] is True and exp["journal"] == "smj"
    assert "SYNTHETIC TEST PAPER, NOT REAL RESEARCH" in (FIXTURE / "planted.tex").read_text(encoding="utf-8")
    assert (FIXTURE / "planted.pdf").exists()
    assert len(exp["must_catch"]) == 13 and len(exp["must_not_flag"]) == 5
    raw = json.loads((FIXTURE / "script_inputs.json").read_text(encoding="utf-8"))
    inputs = {k: {r["id"]: r for r in raw[k]} for k in ("claims", "arith", "stars")}
    ia = _arith()
    linked = {"must_catch": 0, "must_not_flag": 0}
    for key, want in (("must_catch", True), ("must_not_flag", False)):
        for item in exp[key]:
            if item.get("record"):
                assert _flags(item["record"], inputs, ia) is want, item
                linked[key] += 1
    assert linked["must_catch"] == 3 and linked["must_not_flag"] == 1


def test_final_fix_wave_c_labels_and_page_count():
    import pymupdf

    exp = yaml.safe_load((FIXTURE / "expected.yaml").read_text(encoding="utf-8"))
    h1 = "Results, H1: Clustering standard errors by province, the level at which nine of the 24 provinces adopted the reform, gives a similar estimate"
    p1 = [i for i in exp["must_catch"] if i["locator"] == h1]
    assert len(p1) == 1 and p1[0]["check"] == "I4" and p1[0]["page"] == 7
    assert p1[0]["severity"] == "Undermines the main claim" and "an I1 label also counts" in p1[0]["note"]
    fair = {(i["check"], i["page"], i["locator"]) for i in exp["also_fair"]}
    assert ("I1", 7, "Results, H1: nine of the 24 provinces adopted the reform") in fair
    assert ("I4", 7, "Results, H1: nine of the 24 provinces adopted the reform") not in fair
    assert ("I1", 12, "Table 7: Standard errors in parentheses. Standard errors are clustered by firm.") in fair
    assert ("I1", 9, "Results, H2: we cluster standard errors by industry in this table") in fair
    p5 = [i for i in exp["must_catch"] if i["check"] == "I7"]
    assert p5[0]["locator"] == "Table 2: Firm clusters 38,650" and p5[0]["page"] == 8
    tex = (FIXTURE / "planted.tex").read_text(encoding="utf-8")
    assert "First, the reform raised firms' R\\&D intensity. The effect is larger" in tex
    for cite in ("Abadie et al. 2023", "Bertrand, Duflo, and Mullainathan 2004", "Bettis et al. 2016", "Roth et al. 2023"):
        assert tex.count(cite) == 1, cite
    assert "\\textit{Stata Journal}, 20(4)" in tex and "SSRN" not in tex
    with pymupdf.open(str(FIXTURE / "planted.pdf")) as doc:
        assert 14 <= doc.page_count <= 18
