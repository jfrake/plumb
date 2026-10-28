from __future__ import annotations
import importlib.util
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "packs" / "nonlinear" / "fixtures" / "planted-1"
SCRIPT = ROOT / "packs" / "nonlinear" / "scripts" / "nonlinear_arith.py"


def _script():
    spec = importlib.util.spec_from_file_location("nonlinear_arith", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_fixture_plants_and_decoys_check_out_with_the_script():
    exp = yaml.safe_load((FIXTURE / "expected.yaml").read_text(encoding="utf-8"))
    assert exp["script_checked"] is True
    assert "SYNTHETIC TEST PAPER, NOT REAL RESEARCH" in (FIXTURE / "planted.tex").read_text(encoding="utf-8")
    assert (FIXTURE / "planted.pdf").exists()
    assert len(exp["must_catch"]) == 12 and len(exp["must_not_flag"]) == 5
    records = {r["id"]: r for r in json.loads((FIXTURE / "script_inputs.json").read_text(encoding="utf-8"))}
    na = _script()
    linked = {"must_catch": 0, "must_not_flag": 0}
    for key, want in (("must_catch", True), ("must_not_flag", False)):
        for item in exp[key]:
            if item.get("record"):
                result = na.run_record(records[item["record"]], set())
                assert result["status"] == "ok" and result["flag"] is want, item
                linked[key] += 1
    assert linked["must_catch"] == 7 and linked["must_not_flag"] == 1
