from __future__ import annotations
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "packs" / "theory" / "fixtures" / "planted-1"
LABEL = "SYNTHETIC TEST PAPER, NOT REAL RESEARCH"
CHECKS = {f"T{i}" for i in range(1, 16)}
SEVERITIES = ("Undermines the main claim", "Weakens a claim", "Minor")


def _expected():
    return yaml.safe_load((FIXTURE / "expected.yaml").read_text(encoding="utf-8"))


def test_fixture_is_complete_and_labeled():
    exp = _expected()
    assert exp["synthetic"] is True and exp["owner"] == "blind-agent" and exp["label"] == LABEL
    assert exp["status"] in ("pending_planting", "ready")
    tex = (FIXTURE / "planted.tex").read_text(encoding="utf-8")
    assert LABEL in tex and (FIXTURE / "planted.pdf").exists()
    catch, decoys, fair = exp["must_catch"], exp["must_not_flag"], exp.get("also_fair") or []
    names = sorted(i["note"].split(":", 1)[0] for i in catch)
    moved = [i for i in fair if i["note"].startswith("P7:")]
    assert names == [f"P{i}" for i in range(1, 9) if not (i == 7 and moved)]
    assert sorted(i["note"].split(":", 1)[0] for i in decoys) == [f"D{i}" for i in range(1, 5)]
    for key in ("must_catch", "must_not_flag", "also_fair"):
        for item in exp.get(key) or []:
            assert {"check", "page", "locator", "note"} <= set(item), item
            assert item["check"] in CHECKS or str(item["check"]).startswith("core:"), item
            assert chr(0x2014) not in str(item), item
    for item in catch:
        assert item["severity"] in SEVERITIES, item
        if item["note"].startswith("P7:"):
            assert "http" in item["note"], item
    plants = {(i["check"], str(i["page"]), i["locator"]) for i in catch}
    for d in decoys:
        assert (d["check"], str(d["page"]), d["locator"]) not in plants, d


def test_fixture_contains_no_estimation_table():
    tex = (FIXTURE / "planted.tex").read_text(encoding="utf-8").lower()
    for s in ("standard error", "confidence interval"):
        assert s not in tex, s
