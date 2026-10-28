from __future__ import annotations
import importlib.util
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "packs" / "simulation" / "fixtures" / "planted-1"
SCRIPT = ROOT / "packs" / "simulation" / "scripts" / "run_noise.py"


def _script():
    spec = importlib.util.spec_from_file_location("run_noise", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_fixture_plants_and_decoys_check_out_with_the_script():
    exp = yaml.safe_load((FIXTURE / "expected.yaml").read_text(encoding="utf-8"))
    assert exp["script_checked"] is True
    tex = (FIXTURE / "planted.tex").read_text(encoding="utf-8")
    assert "SYNTHETIC TEST PAPER, NOT REAL RESEARCH" in tex and "independently drawn landscapes" in tex
    assert (FIXTURE / "planted.pdf").exists()
    assert len(exp["must_catch"]) == 13 and len(exp["must_not_flag"]) == 4
    assert {i["check"] for i in exp["must_not_flag"]} == {"K10", "K4", "K13", "K6"}
    records = {r["id"]: r for r in json.loads((FIXTURE / "script_inputs.json").read_text(encoding="utf-8"))}
    rn = _script()
    by_record = {i["record"]: i for key in ("must_catch", "must_not_flag") for i in exp[key] if i.get("record")}
    assert set(by_record) == {"k4-plant", "k5-plant", "d2-decoy"}
    k4 = rn.run_record(records["k4-plant"])
    assert by_record["k4-plant"]["check"] == "K4" and k4["flag"] == "inside_noise"
    d2 = rn.run_record(records["d2-decoy"])
    assert by_record["d2-decoy"]["check"] == "K4" and d2["flag"] is None and d2["excludes_zero"] is True
    k5 = rn.run_record(records["k5-plant"])
    assert by_record["k5-plant"]["check"] == "K5" and k5["flag"] is None
    assert k5["runs_for_p05"] < records["k5-plant"]["a"]["runs"]
