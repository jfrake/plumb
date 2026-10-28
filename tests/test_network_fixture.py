from __future__ import annotations
import importlib.util
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "packs" / "network" / "fixtures" / "planted-1"
SCRIPT = ROOT / "packs" / "network" / "scripts" / "check_network_numbers.py"
IDS = {"G1", "G2", "G3", "G4", "G6", "G7", "G8", "G9", "G10", "G11", "G12", "G13", "G15", "G16"}
SEVERITIES = ("Undermines the main claim", "Weakens a claim", "Minor", "number flag")
PLANTED = {"G1": "number flag", "G2": "Weakens a claim", "G3": "Weakens a claim", "G6": "Weakens a claim",
           "G7": "Minor", "G9": "Weakens a claim", "G16": "Weakens a claim", "G10": "Weakens a claim",
           "G11": "Weakens a claim", "G13": "Undermines the main claim", "G12": "Minor"}


def _script():
    spec = importlib.util.spec_from_file_location("check_network_numbers", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _expected():
    return yaml.safe_load((FIXTURE / "expected.yaml").read_text(encoding="utf-8"))


def test_fixture_is_complete_and_coherent():
    exp = _expected()
    assert exp["synthetic"] is True and exp["script_checked"] is True and exp["status"] == "pending_planting"
    assert "SYNTHETIC TEST PAPER, NOT REAL RESEARCH" in (FIXTURE / "planted.tex").read_text(encoding="utf-8")
    assert (FIXTURE / "planted.pdf").exists()
    catch, decoys, fair = exp["must_catch"], exp["must_not_flag"], exp["also_fair"]
    assert {i["check"]: i["severity"] for i in catch} == PLANTED and len(catch) == 11
    assert sorted(i["check"] for i in decoys) == ["G1", "G10", "G9"]
    assert [i["check"] for i in fair] == ["G4", "G15", "G11"]
    assert [i["page"] for i in fair] == [6, 9, 14]
    for item in catch + decoys + fair:
        assert {"check", "page", "locator", "note"} <= set(item), item
        assert item["check"] in IDS and str(item["page"]).strip() and ": " in item["locator"], item
    plants = {(i["check"], str(i["page"]), i["locator"]) for i in catch}
    for d in decoys:
        assert (d["check"], str(d["page"]), d["locator"]) not in plants, d


def test_fixture_script_inputs_flag_only_the_density():
    records = json.loads((FIXTURE / "script_inputs.json").read_text(encoding="utf-8"))
    assert {r["id"] for r in records} == {"t1-density", "t1-degree", "t5-dyads"}
    out = _script().run(records)
    assert [(r["id"], r["flag"]) for r in out["results"] if r["flag"]] == [("t1-density", "density_mismatch")]
    exp = _expected()
    assert [(i["check"], i["record"]) for i in exp["must_catch"] if i.get("record")] == [("G1", "t1-density")]
    assert [(i["check"], i["record"]) for i in exp["must_not_flag"] if i.get("record")] == [("G1", "t1-degree")]
