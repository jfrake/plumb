from __future__ import annotations
import csv
import importlib.util
import json
import subprocess
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "packs" / "configurational" / "fixtures" / "planted-1"
SCRIPT = ROOT / "packs" / "configurational" / "scripts" / "qca_check.py"
LABEL = "SYNTHETIC TEST PAPER, NOT REAL RESEARCH"
CHECKS = {f"B{i}" for i in range(1, 16)}
SETS = ["HighROA", "BoardIndep", "CEODuality", "RDIntensity", "FirmSize", "Alliances", "OwnerConc"]
PLANTS = {"P1": ("B1", "Weakens a claim"), "P2": ("B2", "Weakens a claim"), "P3": ("B3", "Weakens a claim"),
          "P4": ("B6", "Weakens a claim"), "P5": ("B7", "Weakens a claim"),
          "P6": ("B8", "Undermines the main claim"), "P7": ("B9", "Weakens a claim"),
          "P8": ("B12", "Weakens a claim"), "P9": ("B13", "Weakens a claim")}
DECOYS = {"D1": "B2", "D2": "B11"}
MUST_NOT_RAISE = ["asks for standard errors, p-values, or a significance test for consistency or coverage",
                  "flags the use of the intermediate solution as such",
                  "asks for a power analysis or sample-size justification for the QCA",
                  "benchmarks consistency or coverage as an effect size",
                  "rates a reverse-causality alternative to a configuration as undermining the main claim"]


def _script():
    spec = importlib.util.spec_from_file_location("qca_check", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _expected():
    return yaml.safe_load((FIXTURE / "expected.yaml").read_text(encoding="utf-8"))


def _records():
    return json.loads((FIXTURE / "script_inputs.json").read_text(encoding="utf-8"))


def _p5():
    [p5] = [i for i in _expected()["must_catch"] if i["note"].startswith("P5:")]
    return p5


def test_planted_1_expected_is_complete_and_labeled():
    exp = _expected()
    assert exp["synthetic"] is True and exp["owner"] == "blind-agent" and exp["label"] == LABEL
    assert exp["status"] in ("pending_planting", "ready") and exp["script_checked"] is True
    assert exp["must_not_raise"] == MUST_NOT_RAISE
    catch = {i["note"].split(":", 1)[0]: i for i in exp["must_catch"]}
    assert set(catch) == set(PLANTS)
    for pid, (check, severity) in PLANTS.items():
        assert catch[pid]["check"] == check and catch[pid]["severity"] == severity, pid
    decoys = {i["note"].split(":", 1)[0]: i for i in exp["must_not_flag"]}
    assert {k: v["check"] for k, v in decoys.items()} == DECOYS
    assert {"B4", "B5", "B10", "B14"} <= {i["check"] for i in exp["also_fair"]}
    for key in ("must_catch", "must_not_flag", "also_fair"):
        for item in exp[key]:
            assert {"check", "page", "locator", "note"} <= set(item), item
            assert item["check"] in CHECKS, item
            assert chr(0x2014) not in json.dumps(item), item
    plants = {(i["check"], str(i["page"]), i["locator"]) for i in exp["must_catch"]}
    locators = {i["locator"] for i in exp["must_catch"]}
    for d in exp["must_not_flag"]:
        assert (d["check"], str(d["page"]), d["locator"]) not in plants and d["locator"] not in locators, d
    tex = (FIXTURE / "planted.tex").read_text(encoding="utf-8")
    assert LABEL in tex and (FIXTURE / "planted.pdf").exists()
    assert "between 50 and 5,000" not in tex and "threshold of 50 employees" not in tex


def test_planted_1_script_flags_only_the_planted_pri():
    records = _records()
    kinds = sorted(r["kind"] for r in records)
    assert kinds == ["design", "fit_table", "fit_table"]
    fits = {r["outcome"]: r for r in records if r["kind"] == "fit_table"}
    assert set(fits) == {"presence", "absence"}
    assert len(fits["presence"]["terms"]) == 3 and all(t["headline"] for t in fits["presence"]["terms"])
    results = _script().run_records(records)
    assert all(r["status"] != "invalid" for r in results), results
    [flagged] = [r for r in results if r["flag"]]
    p5 = _p5()
    assert flagged["id"] == p5["record"] == fits["presence"]["id"] and flagged["check"] == "B7"
    assert flagged["reasons"] == ["pri_exceeds_consistency"]
    assert [v["where"] for v in flagged["facts"]["violations"]] == [p5["term"]]
    [design] = [r for r in results if r["kind"] == "design" and r["check"] == "B5"]
    assert design["facts"]["logical_rows"] == 64
    [b3] = [r for r in results if r["kind"] == "design" and r["check"] == "B3"]
    assert b3["facts"]["cases_short_of_n"] == 18


def _memberships():
    with (FIXTURE / "memberships.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    return rows[0], rows[1:]


def test_planted_1_memberships_file():
    header, rows = _memberships()
    assert header == ["firm"] + SETS and len(rows) == 180
    half = {s: 0 for s in SETS}
    for row in rows:
        for s, v in zip(SETS, row[1:]):
            if s == "CEODuality":
                assert v in ("0", "1")
                continue
            assert len(v.split(".")[1]) == 6 and Decimal("0") <= Decimal(v) <= Decimal("1"), (s, v)
            if Decimal("0.495") <= Decimal(v) < Decimal("0.505"):
                half[s] += 1
                assert v == "0.500000", (s, v)
    assert half == {s: 18 if s == "Alliances" else 0 for s in SETS}


def test_planted_1_memberships_recompute_every_unplanted_figure():
    header, rows = _memberships()
    records = _records()
    fit_ids = [r["id"] for r in records if r["kind"] == "fit_table"]

    def two(v):
        return v if v in ("0", "1") else str(Decimal(v).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    mem = {"id": "test-memberships", "kind": "memberships", "source": "memberships.csv", "variant": "fsQCA",
           "sets": SETS, "outcome": "HighROA", "conditions": SETS[1:], "compare": fit_ids,
           "cases": [{s: two(v) for s, v in zip(SETS, row[1:])} for row in rows]}
    results = _script().run_records(records + [mem])
    mine = {r["check"]: r for r in results if r["id"] == "test-memberships"}
    violations = mine["B7"]["facts"].get("violations", [])
    p5 = _p5()
    assert [(v["record"], v["where"], v["field"]) for v in violations] == [(p5["record"], p5["term"], "pri")]
    ranges = mine["B7"]["facts"]["recomputed_ranges"]
    assert len(ranges) >= 3 * 3 + 3
    b3 = mine["B3"]["facts"]
    assert b3["printed_half_row_unknown"] == {"Alliances": 18}
    assert b3["cases_left_out"] == {"row_unknown": 18, "at_exactly_half": 0} and b3["cases_in_rows"] == 162


def test_planted_1_rerun_reproduces_the_data(tmp_path):
    subprocess.run([sys.executable, str(FIXTURE / "make_fixture.py"), "--out", str(tmp_path)], check=True,
                   capture_output=True)
    for name in ("memberships.csv", "script_inputs.json"):
        assert (tmp_path / name).read_bytes() == (FIXTURE / name).read_bytes(), name
