from __future__ import annotations
import importlib.util
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "packs" / "meta-analysis" / "fixtures" / "planted-1"
SCRIPT = ROOT / "packs" / "meta-analysis" / "scripts" / "ma_arith.py"


def _script():
    spec = importlib.util.spec_from_file_location("ma_arith", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _actual(result, key):
    if key == "status":
        return result["status"]
    if key == "shared_groups":
        return len(result["values"]["shared_rows"])
    return result["values"][key]


def test_fixture_plants_and_decoys_check_out_with_the_script():
    exp = yaml.safe_load((FIXTURE / "expected.yaml").read_text(encoding="utf-8"))
    assert exp["script_checked"] is True
    assert "SYNTHETIC TEST PAPER, NOT REAL RESEARCH" in (FIXTURE / "planted.tex").read_text(encoding="utf-8")
    assert (FIXTURE / "planted.pdf").exists()
    assert len(exp["must_catch"]) == 13 and len(exp["must_not_flag"]) == 4
    severity = {i["note"].split(":", 1)[0]: i["severity"] for i in exp["must_catch"]}
    assert severity["P2"] == "Weakens a claim" and severity["P2b"] == "Undermines the main claim"
    assert severity["P3"] == "Undermines the main claim"
    records = {r["id"]: r for r in json.loads((FIXTURE / "script_inputs.json").read_text(encoding="utf-8"))}
    ma = _script()
    linked = {"must_catch": 0, "must_not_flag": 0}
    for key in ("must_catch", "must_not_flag"):
        for item in exp[key]:
            if not item.get("record"):
                continue
            result = ma.run_record(records[item["record"]], set())
            assert result["status"] != "input_error", item
            for k, v in item["expect"].items():
                assert _actual(result, k) == v, (item["record"], k)
            linked[key] += 1
    assert linked == {"must_catch": 9, "must_not_flag": 2}
