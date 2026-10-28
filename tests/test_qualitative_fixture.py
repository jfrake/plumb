from __future__ import annotations
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "packs" / "qualitative" / "fixtures" / "planted-1"
LABEL = "SYNTHETIC TEST PAPER, NOT REAL RESEARCH"
CHECKS = {f"Q{i}" for i in range(1, 16)}
SEVERITIES = ("Undermines the main claim", "Weakens a claim", "Minor")
MUST_NOT_RAISE = ("more interviews or a larger sample as a flaw by itself", "an inter-rater reliability statistic",
                  "statistical generalizability", "a missing ethics or IRB statement",
                  "a positionality statement as a flaw by itself")


def _expected():
    return yaml.safe_load((FIXTURE / "expected.yaml").read_text(encoding="utf-8"))


def test_fixture_is_complete_and_labeled():
    exp = _expected()
    assert exp["synthetic"] is True and exp["owner"] == "blind-agent" and exp["label"] == LABEL
    assert exp["status"] in ("pending_planting", "ready")
    tex = (FIXTURE / "planted.tex").read_text(encoding="utf-8")
    assert LABEL in tex and (FIXTURE / "planted.pdf").exists() and "disguised" in tex
    catch, decoys = exp["must_catch"], exp["must_not_flag"]
    assert sorted(i["note"].split(":", 1)[0] for i in catch) == [f"P{i}" for i in range(1, 9)]
    assert sorted(i["note"].split(":", 1)[0] for i in decoys) == [f"D{i}" for i in range(1, 6)]
    assert tuple(exp["must_not_raise"]) == MUST_NOT_RAISE
    for key in ("must_catch", "must_not_flag", "also_fair"):
        for item in exp.get(key) or []:
            assert {"check", "page", "locator", "note"} <= set(item), item
            assert item["check"] in CHECKS or str(item["check"]).startswith("core:"), item
            assert chr(0x2014) not in str(item), item
    for item in catch:
        assert item["severity"] in SEVERITIES, item
    plants = {(i["check"], str(i["page"]), i["locator"]) for i in catch}
    for d in decoys:
        assert (d["check"], str(d["page"]), d["locator"]) not in plants, d


def test_fixture_counts_disagree_only_where_planted():
    exp = _expected()
    counts = exp["interview_counts"]
    assert counts["methods_text"] == 41 and sum(counts["table_1_rows"]) == 38
    assert all(isinstance(n, int) and n > 0 for n in counts["table_1_rows"])
    [p1] = [i for i in exp["must_catch"] if i["note"].startswith("P1:")]
    assert p1["check"] == "Q6" and "41" in p1["note"] and "38" in p1["note"]
