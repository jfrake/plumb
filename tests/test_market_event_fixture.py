from __future__ import annotations
import importlib.util
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "packs" / "market-event" / "fixtures" / "planted-1"
SCRIPT = ROOT / "packs" / "market-event" / "scripts" / "event_arith.py"


def _script():
    spec = importlib.util.spec_from_file_location("event_arith", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_fixture_plants_and_decoys_check_out_with_the_script():
    exp = yaml.safe_load((FIXTURE / "expected.yaml").read_text(encoding="utf-8"))
    assert exp["script_checked"] is True
    assert "SYNTHETIC TEST PAPER, NOT REAL RESEARCH" in (FIXTURE / "planted.tex").read_text(encoding="utf-8")
    assert (FIXTURE / "planted.pdf").exists()
    assert len(exp["must_catch"]) == 13 and len(exp["must_not_flag"]) == 3
    [headline] = [i for i in exp["must_catch"] if i["check"] == "R5"]
    assert headline["severity"] == "Undermines the main claim"
    records = {r["id"]: r for r in json.loads((FIXTURE / "script_inputs.json").read_text(encoding="utf-8"))}
    ea = _script()
    linked = {"must_catch": 0, "must_not_flag": 0}
    for key in ("must_catch", "must_not_flag"):
        for item in exp[key]:
            if item.get("record"):
                result = ea.run_record(records[item["record"]], set())
                assert result["status"] == "ok", item
                if key == "must_catch":
                    assert item["reason"] in result["reasons"], item
                else:
                    assert result["flag"] is False, item
                linked[key] += 1
    assert linked["must_catch"] == 4 and linked["must_not_flag"] == 1
    for rec in records.values():
        if rec["id"].startswith("d"):
            assert ea.run_record(rec, set())["flag"] is False, rec["id"]


def test_final_fix_severities_and_extra_fair_findings():
    exp = yaml.safe_load((FIXTURE / "expected.yaml").read_text(encoding="utf-8"))
    by_record = {i.get("record"): i for i in exp["must_catch"] if i.get("record")}
    assert by_record["p3-daily-sum"]["severity"] == "Weakens a claim"
    assert by_record["p3-daily-sum"]["locator"] == "Table 5: Daily mean abnormal returns, full sample"
    assert by_record["p13-flow"]["severity"] == "Weakens a claim"
    fair = {(i["check"], i["page"], i["locator"]) for i in exp["also_fair"]}
    assert {("R1", 4, "Event dating: The event date is the date of the CivicWire release"),
            ("R6", 11, "Appendix Table A3: Table A3: Cumulative abnormal returns over additional windows"),
            ("R5", 6, "Results, H3: The reaction over [-1, +1] is also positive")} <= fair
    tex = (FIXTURE / "planted.tex").read_text(encoding="utf-8")
    assert r"\citep{petersen2009}" in tex and "petersen2009,harringtonshrider2007" not in tex
