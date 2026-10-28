"""The hypothesis ledger's synthetic test paper: expected.yaml and the writer's script run."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "skills" / "review" / "fixtures" / "hypothesis-ledger" / "planted-1"
SCRIPT = ROOT / "skills" / "review" / "scripts" / "check_hypotheses.py"
ACTIVE = {"HL1", "HL2", "HL3", "HL4", "HL5", "HL7", "HL8", "HL9", "HL10", "HL11", "HL12", "HL13", "HL14", "HL15"}
SCRIPT_PLANTS = {"P3": ("H2", "HL3"), "P5": ("H5", "HL5"), "P6": ("H6", "HL7"), "P7": ("H7", "HL9"),
                 "P11": ("H10", "HL15")}


def _expected():
    return yaml.safe_load((FIXTURE / "expected.yaml").read_text(encoding="utf-8"))


def test_fixture_expected_yaml_is_complete():
    exp = _expected()
    assert exp["synthetic"] is True and exp["status"] == "pending_planting" and exp["owner"] == "blind-agent"
    assert exp["label"] == "SYNTHETIC TEST PAPER, NOT REAL RESEARCH" and exp["paper"] == "planted.pdf"
    assert "SYNTHETIC TEST PAPER, NOT REAL RESEARCH" in (FIXTURE / "planted.tex").read_text(encoding="utf-8")
    assert (FIXTURE / "planted.pdf").exists()
    plants, decoys = exp["must_catch"], exp["must_not_flag"]
    assert [p["note"].split(":", 1)[0] for p in plants] == [f"P{i}" for i in range(1, 15)]
    assert [d["note"].split(":", 1)[0] for d in decoys] == [f"D{i}" for i in range(1, 7)]
    for entry in plants + decoys + exp.get("also_fair", []):
        assert {"check", "page", "locator", "note"} <= set(entry), entry
        assert entry["check"] in ACTIVE, entry
        assert "<" not in str(entry["page"]) and "<" not in entry["locator"], entry
    assert all(p.get("severity") in ("Undermines the main claim", "Weakens a claim", "Minor") for p in plants)
    severity = {p["note"].split(":", 1)[0]: p["severity"] for p in plants}
    assert severity["P7"] == "Undermines the main claim" and severity["P10"] == "Minor"
    for a in exp.get("also_fair", []):
        if a["note"].startswith("run B only"):
            assert a.get("run") == "B" and a.get("pack_check"), a
    seen = {(p["check"], str(p["page"]), p["locator"]) for p in plants}
    for d in decoys:
        assert (d["check"], str(d["page"]), d["locator"]) not in seen, d
    owner = {o["plant"]: o for o in exp["owner_run"]}
    assert set(owner) == {"P12", "P13"}
    assert owner["P12"]["checks"] == ["N6"] and owner["P13"]["checks"] == ["N1"]
    assert all(o["hypothesis_audit_raises"] is False for o in owner.values())


def test_fixture_script_run_matches_the_plants():
    exp = _expected()
    assert exp["script_checked"] is True
    spec = importlib.util.spec_from_file_location("check_hypotheses", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mods, _ = mod._imports()
    ledger = json.loads((FIXTURE / "ledger.json").read_text(encoding="utf-8"))
    out = mod.run(ledger, FIXTURE / "tables", mods)
    got = {(f["id"], f["check"]) for f in out.flags}
    fair = {(a["hypothesis"], a["check"]) for a in exp.get("also_fair", []) if a.get("script")}
    assert got == set(SCRIPT_PLANTS.values()) | fair, got
    assert fair <= {("H8", "HL9")}
    assert [f["id"] for f in out.facts] == ["H9"] and out.facts[0]["p_two_sided"][0] > 0.05
    decoys = {(d["hypothesis"], d["check"]) for d in exp["must_not_flag"] if d.get("hypothesis")}
    assert decoys and not decoys & got
