from __future__ import annotations
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
STEM = "rdd"
FIXTURE = ROOT / "packs" / "archival" / "fixtures" / f"{STEM}-1"
MODULES = ['rdd']
CATCH = ['RD3', 'RD8', 'RD1', 'RD5', 'RD17', 'RD4', 'RD10']
DECOYS = ['RD6', 'RD7', 'RD16']
HEADLINE = "RD3"


def test_rdd_fixture_is_complete_and_coherent():
    exp = yaml.safe_load((FIXTURE / "expected.yaml").read_text(encoding="utf-8"))
    ids = set()
    for m in MODULES:
        ids |= {i["id"] for i in yaml.safe_load(
            (ROOT / "packs" / "archival" / "modules" / f"{m}.yaml").read_text(encoding="utf-8"))["checklist"]}
    assert exp["module"] == STEM and exp["synthetic"] is True and exp["owner"] == "blind-agent"
    assert exp["status"] == "pending_planting"
    assert "SYNTHETIC TEST PAPER, NOT REAL RESEARCH" in (FIXTURE / "planted.tex").read_text(encoding="utf-8")
    assert (FIXTURE / "planted.pdf").exists()
    assert sorted(i["check"] for i in exp["must_catch"]) == sorted(CATCH)
    assert sorted(i["check"] for i in exp["must_not_flag"]) == sorted(DECOYS)
    for item in exp["must_catch"] + exp["must_not_flag"] + exp.get("also_fair", []):
        assert {"check", "page", "locator", "note"} <= set(item), item
        assert item["check"] in ids and item["locator"].strip(), item
    for item in exp["must_catch"]:
        assert item["severity"] in ("Undermines the main claim", "Weakens a claim", "Minor"), item
    heads = [i for i in exp["must_catch"] if i["severity"] == "Undermines the main claim"]
    assert [i["check"] for i in heads] == [HEADLINE]
    plants = {(i["check"], str(i["page"]), i["locator"]) for i in exp["must_catch"]}
    for d in exp["must_not_flag"]:
        same = [p for p in plants if p[0] == d["check"] and p[1] == str(d["page"])]
        assert all(p[2] != d["locator"] for p in same), d
