from __future__ import annotations
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "packs" / "inference" / "scripts" / "inference_arith.py"


def _mod():
    spec = importlib.util.spec_from_file_location("inference_arith", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


IA = _mod()
EIGHT = [".03", ".21", ".44", ".08", ".62", ".35", ".12", ".51"]


def _family(ps, **kw):
    rec = {"id": "f", "kind": "family", "check": "I11", "source": "Table 7",
           "tests": [{"id": f"t{i}", "p": p} for i, p in enumerate(ps)]}
    rec.update(kw)
    return IA.run_record(rec)


def test_family_adjusts_the_papers_own_p_values():
    r = _family(EIGHT)
    assert r["status"] == "ok" and r["flag"] is False
    point = lambda m: [round(r["values"]["adjusted"][m][f"t{i}"]["point"], 4) for i in range(8)]
    assert point("bonferroni") == [0.24, 1, 1, 0.64, 1, 1, 0.96, 1]
    assert point("holm") == [0.24, 1, 1, 0.56, 1, 1, 0.72, 1]
    assert point("bh") == [0.24, 0.42, 0.5829, 0.32, 0.62, 0.56, 0.32, 0.5829]
    for m in ("bonferroni", "holm", "bh"):
        assert r["values"]["sure_survivors"][m] == []


def test_family_flags_only_sure_contradictions():
    four = ["0.004", "0.011", "0.019", "0.041"]
    all_four = ["t0", "t1", "t2", "t3"]
    ok = _family(four, claimed_method="holm", claimed_survivors=all_four)
    assert ok["flag"] is False
    holm = [round(ok["values"]["adjusted"]["holm"][t]["point"], 3) for t in all_four]
    assert holm == [0.016, 0.033, 0.038, 0.041]
    bad = _family(four[:3] + ["0.052"], claimed_method="holm", claimed_survivors=all_four)
    assert bad["flag"] is True and bad["reasons"] == ["claimed_adjustment_mismatch"]
    # A test whose adjusted interval straddles alpha is neither a sure survivor nor a sure failure.
    edge = _family(["0.025", "0.30"], claimed_method="bonferroni", claimed_survivors=["t0"])
    assert edge["flag"] is False and edge["values"]["sure_survivors"]["bonferroni"] == []


def test_family_reads_coefficients_and_standard_errors():
    r = IA.run_record({"id": "f", "kind": "family", "check": "I11", "source": "T",
                       "tests": [{"id": "a", "b": "0.084", "se": "0.047"}, {"id": "b", "p": "0.5"}]})
    a = r["values"]["adjusted"]["bonferroni"]["a"]
    assert a["low"] == pytest.approx(2 * 0.0692, abs=2e-4) and a["high"] == pytest.approx(2 * 0.0788, abs=2e-4)


def test_magnitude_checks_a_stated_size():
    r = IA.run_record({"id": "m", "kind": "magnitude", "check": "I15", "source": "Discussion", "b": "0.00012",
                       "delta_x": "1.0", "mean_y": "0.061", "claimed": {"unit": "pct_of_mean", "value": "0.02"}})
    assert r["values"]["pct_of_mean"] == pytest.approx(0.0019672, abs=1e-6)
    assert r["flag"] is True and r["reasons"] == ["magnitude_claim_mismatch"]
    ok = IA.run_record({"id": "m", "kind": "magnitude", "check": "I15", "source": "D", "b": "0.00012",
                        "delta_x": "1.0", "mean_y": "0.061", "claimed": {"unit": "pct_of_mean", "value": "0.002"}})
    assert ok["flag"] is False


def test_magnitude_on_the_log_scale():
    r = IA.run_record({"id": "m", "kind": "magnitude", "check": "I15", "source": "D", "b": "0.035",
                       "delta_x": "2", "outcome_scale": "log", "se": "0.010"})
    assert r["values"]["effect"] == pytest.approx(0.072508, abs=1e-6)
    lo, hi = r["values"]["interval"]
    assert lo == pytest.approx(0.03128, abs=1e-4) and hi == pytest.approx(0.11539, abs=1e-4)


def test_interval_facts_are_never_flags():
    r = IA.run_record({"id": "i", "kind": "interval", "check": "I16", "source": "Table 5", "b": "0.012",
                       "se": "0.018", "benchmark": "0.046"})
    assert r["flag"] is False
    assert r["values"]["low"] == pytest.approx(-0.02328) and r["values"]["high"] == pytest.approx(0.04728)
    assert r["values"]["covers_zero"] is True and r["values"]["covers_benchmark"] is True


def test_bad_records_are_invalid_and_the_rest_still_run(tmp_path):
    inputs = tmp_path / "in.json"
    inputs.write_text(json.dumps([{"id": "x", "kind": "nope"}, {"id": "y", "kind": "interval", "b": "0.1"},
                                  {"id": "z", "kind": "interval", "b": "0.1", "se": "0.05"}]))
    out = tmp_path / "out.json"
    r = subprocess.run([sys.executable, str(SCRIPT), str(inputs), str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    got = json.loads(out.read_text())
    assert [g["status"] for g in got] == ["invalid", "invalid", "ok"]
    assert "missing field 'se'" in got[1]["message"]


@pytest.mark.parametrize("payload", [None, "not json", '{"id": "x"}'])
def test_exit_2_on_bad_inputs(tmp_path, payload):
    inputs = tmp_path / "in.json"
    if payload is not None:
        inputs.write_text(payload)
    r = subprocess.run([sys.executable, str(SCRIPT), str(inputs), str(tmp_path / "o.json")],
                       capture_output=True, text=True)
    assert r.returncode == 2 and not (tmp_path / "o.json").exists()


def test_exit_2_when_the_core_module_cannot_be_imported(tmp_path):
    lonely = tmp_path / "a" / "b" / "c" / "inference_arith.py"
    lonely.parent.mkdir(parents=True)
    shutil.copy(SCRIPT, lonely)
    (tmp_path / "in.json").write_text("[]")
    r = subprocess.run([sys.executable, str(lonely), str(tmp_path / "in.json"), str(tmp_path / "o.json")],
                       capture_output=True, text=True)
    assert r.returncode == 2 and "pvalues" in r.stderr


def test_malformed_records_never_crash():
    bad = [
        {"id": "a", "kind": "family", "tests": ["x", "y"]},
        {"id": "b", "kind": "family", "tests": [{"id": "1", "p": ".1"}, {"id": "2", "p": ".2"}],
         "claimed_method": "holm", "claimed_survivors": 5},
        {"id": "c", "kind": "magnitude", "b": "1", "delta_x": "1", "claimed": "big"},
        {"id": "d", "kind": "magnitude", "b": "1", "delta_x": "10000", "outcome_scale": "log"},
        {"id": "e", "kind": "family", "tests": [{"id": "1", "p": ".1"}, {"id": "2", "p": ".2"}], "alpha": "abc"},
    ]
    for rec in bad:
        assert IA.run_record(rec)["status"] == "invalid", rec


def test_touching_rounding_boundary_is_not_flagged():
    # Printed .0500 with two tests: Bonferroni low bound is 2 * .04995 = .0999, high .1001; alpha .1 is inside.
    r = _family([".0500", ".9"], alpha=".1", claimed_method="bonferroni", claimed_survivors=["t0"])
    assert r["flag"] is False
    m = IA.run_record({"id": "m", "kind": "magnitude", "check": "I15", "source": "D", "b": "0.10",
                       "delta_x": "1", "claimed": {"unit": "level", "value": "0.2"}, "tolerance": "0"})
    assert m["flag"] is True
    m2 = IA.run_record({"id": "m", "kind": "magnitude", "check": "I15", "source": "D", "b": "0.10",
                        "delta_x": "1", "claimed": {"unit": "level", "value": "0.1"}, "tolerance": "0"})
    assert m2["flag"] is False


def _mag(**kw):
    rec = {"id": "m", "kind": "magnitude", "check": "I15", "source": "D"}
    rec.update(kw)
    return IA.run_record(rec)


def test_fix1_magnitude_uses_rounding_boxes_of_all_inputs():
    r = _mag(b="0.03", delta_x="1", mean_y="0.5", claimed={"unit": "pct_of_mean", "value": "0.07"})
    assert r["status"] == "ok" and r["flag"] is False
    far = _mag(b="0.03", delta_x="1", mean_y="0.5", claimed={"unit": "pct_of_mean", "value": "0.2"})
    assert far["flag"] is True
    straddle = _mag(b="0.03", delta_x="1", mean_y="0", claimed={"unit": "pct_of_mean", "value": "0.7"})
    assert straddle["status"] == "not_computable" and straddle["flag"] is False


def test_fix2_missed_survivor_only_for_printed_p():
    rec = {"id": "f", "kind": "family", "check": "I11", "source": "T", "claimed_method": "bonferroni",
           "claimed_survivors": ["b"],
           "tests": [{"id": "a", "b": "0.20", "se": "0.08"}, {"id": "b", "p": "0.001"}]}
    r = IA.run_record(rec)
    assert r["flag"] is False and any("a" in f for f in r["facts"])
    rec["tests"] = [{"id": "a", "p": "0.001"}, {"id": "b", "p": "0.001"}]
    assert IA.run_record(rec)["flag"] is True


def test_fix3_missing_claimed_survivors_skips_missed_check():
    ps = [{"id": "a", "p": "0.001"}, {"id": "b", "p": "0.5"}]
    base = {"id": "f", "kind": "family", "check": "I11", "source": "T", "claimed_method": "holm", "tests": ps}
    assert IA.run_record(base)["flag"] is False
    assert IA.run_record(dict(base, claimed_survivors=[]))["flag"] is True


@pytest.mark.parametrize("rec", [
    {"id": "x", "kind": ["family"]},
    {"id": "x", "kind": "family", "claimed_method": ["holm"],
     "tests": [{"id": "1", "p": ".1"}, {"id": "2", "p": ".2"}]},
    {"id": "x", "kind": "family", "claimed_method": "holm", "claimed_survivors": None,
     "tests": [{"id": "1", "p": ".1"}, {"id": "2", "p": ".2"}]},
    {"id": "x", "kind": "magnitude", "b": "1", "delta_x": "1", "claimed": {"unit": ["level"], "value": "1"}},
])
def test_fix4_type_checks(rec):
    assert IA.run_record(rec)["status"] == "invalid"


def test_fix5_only_record_errors_and_overflow_are_caught(monkeypatch):
    assert _mag(b="1", delta_x="10000", outcome_scale="log")["status"] == "invalid"
    monkeypatch.setitem(IA.KINDS, "boom", lambda rec: 1 / 0)
    with pytest.raises(ZeroDivisionError):
        IA.run_record({"id": "z", "kind": "boom"})


def test_fix6_interval_rejects_nonpositive_se_and_notes_rounding():
    for se in ("0", "-0.1"):
        assert IA.run_record({"id": "i", "kind": "interval", "b": "0.1", "se": se})["status"] == "invalid"
    r = IA.run_record({"id": "i", "kind": "interval", "b": "0.04", "se": "0.02"})
    assert any("depends on rounding" in f for f in r["facts"])
    r = IA.run_record({"id": "i", "kind": "interval", "b": "0.012", "se": "0.018"})
    assert not any("depends on rounding" in f for f in r["facts"])


@pytest.mark.parametrize("alpha", ["0", "-0.1", "1.5"])
def test_fix7_alpha_range(alpha):
    assert _family(EIGHT, alpha=alpha)["status"] == "invalid"


def test_fix8_docs_say_fractions():
    text = SCRIPT.read_text()
    assert "fractions" in text and "0.02 means 2 percent" in text


def test_negative_tolerance_is_invalid():
    r = IA.run_record({"id": "t", "kind": "magnitude", "check": "I15", "source": "T", "b": "0.03",
                       "delta_x": "1", "mean_y": "0.5", "scale": "level", "tolerance": "-0.5",
                       "claimed": {"unit": "pct_of_mean", "value": "0.07"}})
    assert r["status"] == "invalid" and not r.get("flag")


# --- Final fix wave, section B ---

def test_log_outcome_claim_must_be_pct_change():
    r = _mag(b="0.10", delta_x="1", outcome_scale="log", mean_y="50",
             claimed={"unit": "pct_of_mean", "value": "0.105"})
    assert r["status"] == "invalid" and not r.get("flag")
    assert "on a log outcome state the claim as pct_change" in r["message"]
    for unit in ("level", "sd_y"):
        bad = _mag(b="0.10", delta_x="1", outcome_scale="log", sd_y="2", claimed={"unit": unit, "value": "0.105"})
        assert bad["status"] == "invalid", unit
    ok = _mag(b="0.10", delta_x="1", outcome_scale="log", claimed={"unit": "pct_change", "value": "0.105"})
    assert ok["status"] == "ok" and ok["flag"] is False


def test_interval_notes_when_benchmark_coverage_depends_on_rounding():
    def iv(b, se, bench):
        return IA.run_record({"id": "i", "kind": "interval", "check": "I16", "source": "T", "b": b, "se": se,
                              "benchmark": bench})
    edge = iv("0.012", "0.018", "0.046")
    assert edge["values"]["benchmark_depends_on_rounding"] is True and edge["flag"] is False
    assert any("whether it covers the benchmark depends on rounding" in f for f in edge["facts"])
    inside = iv("0.012", "0.018", "0.030")
    assert inside["values"]["covers_benchmark"] is True
    assert inside["values"]["benchmark_depends_on_rounding"] is False
    outside = iv("0.012", "0.018", "0.090")
    assert outside["values"]["covers_benchmark"] is False
    assert outside["values"]["benchmark_depends_on_rounding"] is False
    assert not any("benchmark depends on rounding" in f for f in outside["facts"])
    assert "benchmark_depends_on_rounding" not in iv("0.012", "0.018", None)["values"]


def test_claims_agent_does_not_rest_1d_on_a_rounding_dependent_benchmark():
    text = (ROOT / "packs" / "inference" / "agents" / "inference-claims.md").read_text(encoding="utf-8")
    i16 = text.split("### I16. ", 1)[1].split("\n### ", 1)[0]
    assert "Do not rest rule 1(d) on a benchmark whose coverage depends on rounding." in i16
