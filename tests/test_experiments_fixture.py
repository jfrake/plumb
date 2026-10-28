from __future__ import annotations
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "packs" / "experiments" / "fixtures" / "planted-1"
LABEL = "SYNTHETIC TEST PAPER, NOT REAL RESEARCH"
CHECKS = {f"E{i}" for i in range(1, 16)} | {"IV1", "IV2", "IV3", "IV4", "IV5", "IV9", "IV11"}
SEVERITIES = ("Undermines the main claim", "Weakens a claim", "Minor")
sys.path.insert(0, str(ROOT / "skills" / "review" / "scripts"))
import pvalues  # noqa: E402


def _expected():
    return yaml.safe_load((FIXTURE / "expected.yaml").read_text(encoding="utf-8"))


def _p_range(stat):
    """Two-sided (or declared one-sided) p interval for a printed t or F, over the printed digits' rounding."""
    value, half = pvalues.parse_printed(stat["value"])
    lo_v, hi_v = max(0.0, value - half), value + half
    if stat["kind"] == "F":
        d1, d2 = stat["df1"], stat["df2"]
        f = lambda x: pvalues._betai(d2 / 2, d1 / 2, d2 / (d2 + d1 * x))  # noqa: E731
    else:
        f = lambda x: pvalues.p_student(x, stat["df"])  # noqa: E731
    lo, hi = f(hi_v), f(lo_v)
    return (lo / 2, hi / 2) if stat.get("tails") == "one" else (lo, hi)


def _verdict(stat):
    if stat["kind"] == "df":
        return "consistent" if stat["n"] - stat["cells"] - stat["covariates"] == stat["df2"] else "mismatch"
    lo, hi = _p_range(stat)
    plo, phi = pvalues.printed_p_range(stat["p"])
    return "consistent" if lo <= phi and plo <= hi else "mismatch"


def test_fixture_is_complete_and_labeled():
    exp = _expected()
    assert exp["synthetic"] is True and exp["owner"] == "blind-agent" and exp["label"] == LABEL
    assert exp["status"] in ("pending_planting", "ready")
    tex = (FIXTURE / "planted.tex").read_text(encoding="utf-8")
    assert LABEL in tex and (FIXTURE / "planted.pdf").exists()
    assert "registry.example.org" in tex and "osf.io" not in tex and "aspredicted" not in tex.lower()
    catch, decoys = exp["must_catch"], exp["must_not_flag"]
    assert sorted(i["note"].split(":", 1)[0] for i in catch) == [f"P{i}" for i in range(1, 9)]
    assert sorted(i["note"].split(":", 1)[0] for i in decoys) == [f"D{i}" for i in range(1, 7)]
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
    assert any("does not resolve" in i["note"] for i in exp.get("also_fair") or [])


def test_fixture_statistics_recompute():
    exp = _expected()
    checked = 0
    for item in exp["must_catch"] + exp["must_not_flag"]:
        if "stat" in item:
            assert _verdict(item["stat"]) == item["stat"]["expect"], item
            checked += 1
    assert checked == 6
