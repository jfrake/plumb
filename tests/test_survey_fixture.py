from __future__ import annotations
import importlib.util
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "packs" / "survey"
SCRIPT = PACK / "scripts" / "check_correlation_matrix.py"
LABEL = "SYNTHETIC TEST PAPER, NOT REAL RESEARCH"


def _script():
    spec = importlib.util.spec_from_file_location("check_correlation_matrix", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fixture(name):
    d = PACK / "fixtures" / name
    exp = yaml.safe_load((d / "expected.yaml").read_text(encoding="utf-8"))
    assert exp["matrix_checked"] is True
    assert LABEL in (d / "planted.tex").read_text(encoding="utf-8")
    assert (d / "planted.pdf").exists()
    checked = [m for m in _script().run(d / "tables")["matrices"] if m["status"] == "checked"]
    assert len(checked) == 1, checked
    return exp, checked[0]


def _pair(m, a, b):
    idx = {n: i + 1 for i, v in enumerate(m["variables"]) for n in (a, b) if n in v}
    want = {idx[a], idx[b]}
    return next(p for p in m["pairs"] if {p["i"], p["j"]} == want)


def _severities(exp):
    return {i["check"]: i["severity"] for i in exp["must_catch"]}


def test_planted_1_is_complete_and_its_matrix_is_coherent():
    exp, m = _fixture("planted-1")
    assert sorted(i["check"] for i in exp["must_catch"]) == sorted(
        ["S2", "S4", "S7", "S8", "S9", "S10", "S13", "S16", "S17"])
    assert sorted(i["check"] for i in exp["must_not_flag"]) == ["S1", "S16", "S9"]
    sev = _severities(exp)
    assert sev["S2"] == "Minor" and sev["S9"] == "Undermines the main claim"
    assert all(sev[c] == "Weakens a claim" for c in ("S4", "S7", "S8", "S10", "S13", "S16", "S17"))
    assert m["psd"]["impossible"] is False
    assert m["psd"]["min_eigenvalue"] >= -m["psd"]["bound"] + 0.05
    plant = _pair(m, "Psychological safety", "Team trust")
    assert plant["at_or_above_one"] is True and plant["lower_bound"] >= 1.0
    decoy = _pair(m, "Voice climate", "Leader openness")
    assert decoy["at_or_above_one"] is False and round(decoy["disattenuated"], 3) == 0.601


def test_planted_2_is_complete_and_its_matrix_is_impossible():
    exp, m = _fixture("planted-2")
    assert sorted(i["check"] for i in exp["must_catch"]) == ["S1", "S11", "S14", "S18"]
    assert sorted(i["check"] for i in exp["must_not_flag"]) == ["S13", "S8", "S9"]
    sev = _severities(exp)
    assert sev["S14"] == "Undermines the main claim"
    assert all(sev[c] == "Weakens a claim" for c in ("S1", "S11", "S18"))
    assert m["psd"]["impossible"] is True
    assert m["psd"]["min_eigenvalue"] <= -m["psd"]["bound"] - 0.05
    assert len(m["psd"]["driving_variables"]) == 3
