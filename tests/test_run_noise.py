from __future__ import annotations
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "packs" / "simulation" / "scripts" / "run_noise.py"


def _mod():
    spec = importlib.util.spec_from_file_location("run_noise", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _rec(mean_a, mean_b, spread=0.06, runs=100, crn="no", claim="meaningful", kind="sd", spread_of="runs"):
    arm = {"spread": spread, "spread_kind": kind, "runs": runs}
    return {"id": "r1", "label": "delegated vs centralized", "page": 7, "location": "Table 3 row 1",
            "outcome": "long-run performance", "a": dict(arm, mean=mean_a), "b": dict(arm, mean=mean_b),
            "spread_of": spread_of, "claim": claim, "common_random_numbers": crn}


def test_k4_plant_is_inside_noise_when_independence_is_stated():
    r = _mod().run_record(_rec(0.712, 0.705))
    assert r["status"] == "computed" and r["flag"] == "inside_noise"
    assert r["diff"] == pytest.approx(0.007) and r["se_diff"] == pytest.approx(0.0084853, abs=1e-6)
    assert r["ci95"][0] == pytest.approx(-0.0096312, abs=1e-6) and r["ci95"][1] == pytest.approx(0.0236312, abs=1e-6)
    assert r["excludes_zero"] is False and r["runs_for_p05"] == 565


def test_unclear_independence_never_yields_inside_noise():
    r = _mod().run_record(_rec(0.712, 0.705, crn="unclear"))
    assert r["status"] == "independence_unstated" and r["flag"] is None
    assert r["ci95"][0] == pytest.approx(-0.0096312, abs=1e-6)


def test_shared_draws_are_not_computable():
    r = _mod().run_record(_rec(0.712, 0.705, crn="yes"))
    assert r["status"] == "not_computable" and r["flag"] is None and "paired" in r["reason"]


def test_d2_decoy_excludes_zero_and_is_not_flagged():
    r = _mod().run_record(_rec(0.742, 0.705))
    assert r["status"] == "computed" and r["flag"] is None and r["excludes_zero"] is True
    assert r["ci95"][0] == pytest.approx(0.0203688, abs=1e-6) and r["ci95"][1] == pytest.approx(0.0536312, abs=1e-6)


def test_k5_plant_standardized_effect_and_runs_for_p05():
    r = _mod().run_record(_rec(0.709, 0.705, spread=0.05, runs=10000, claim="significant"))
    assert r["standardized"] == pytest.approx(0.08) and r["runs_for_p05"] == 1201
    assert r["excludes_zero"] is True and r["flag"] is None


@pytest.mark.parametrize("kind,spread", [("se", 0.006), ("ci95_halfwidth", 1.96 * 0.006)])
def test_spread_kinds_convert_to_the_sd_across_runs(kind, spread):
    r = _mod().run_record(_rec(0.712, 0.705, spread=spread, kind=kind))
    assert r["sd_a"] == pytest.approx(0.06) and r["sd_b"] == pytest.approx(0.06)
    assert r["flag"] == "inside_noise"


@pytest.mark.parametrize("spread_of", ["agents", "unclear"])
def test_spread_not_across_runs_is_not_computable(spread_of):
    r = _mod().run_record(_rec(0.712, 0.705, spread_of=spread_of))
    assert r["status"] == "not_computable" and r["flag"] is None


def test_few_runs_are_noted():
    r = _mod().run_record(_rec(0.712, 0.705, runs=20))
    assert r["small_runs"] is True and "understates" in r["note"]


def test_no_difference_has_no_runs_for_p05():
    r = _mod().run_record(_rec(0.705, 0.705, claim="none"))
    assert r["runs_for_p05"] is None and r["flag"] is None


@pytest.mark.parametrize("mean_a,spread", [("0.715", "0.06"), ("0.71600", "0.06000")])
def test_rounding_or_one_tail_can_clear_the_flag(mean_a, spread):
    r = _mod().run_record(_rec(mean_a, "0.700", spread=spread))
    assert r["status"] == "computed" and r["excludes_zero"] is False and r["flag"] is None
    assert r["z_max"] >= 1.645


def test_printed_strings_are_read_like_numbers():
    m = _mod()
    a, b = m.run_record(_rec("0.712", "0.705", spread="0.060")), m.run_record(_rec(0.712, 0.705))
    assert a["diff"] == pytest.approx(b["diff"]) and a["se_diff"] == pytest.approx(b["se_diff"])
    assert a["flag"] == b["flag"] == "inside_noise" and a["z_max"] < b["z_max"] < 1.645


def _cli(path):
    return subprocess.run([sys.executable, str(SCRIPT), str(path)], capture_output=True, text=True)


def test_cli_prints_json_and_writes_no_files(tmp_path):
    f = tmp_path / "in.json"
    f.write_text(json.dumps([_rec(0.712, 0.705), _rec(0.742, 0.705)]))
    r = _cli(f)
    out = json.loads(r.stdout)
    assert r.returncode == 0 and "independent" in out["assumptions"]
    assert [x["flag"] for x in out["results"]] == ["inside_noise", None]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["in.json"]
    src = SCRIPT.read_text(encoding="utf-8")
    assert "write_text" not in src and "open(" not in src


@pytest.mark.parametrize("breaker,word", [
    (lambda r: r.pop("claim"), "claim"),
    (lambda r: r["a"].pop("runs"), "a.runs"),
    (lambda r: r.update(common_random_numbers="maybe"), "common_random_numbers"),
    (lambda r: r["b"].update(spread_kind="iqr"), "b.spread_kind"),
    (lambda r: r["a"].update(mean="0,712"), "a.mean"),
    (lambda r: r["a"].update(mean="0_712"), "a.mean"),
    (lambda r: r.update(label=float("nan")), "label"),
    (lambda r: r.update(page=float("inf")), "page"),
    (lambda r: r["a"].update(spread=1e200), "too large"),
    (lambda r: r["a"].update(runs=10 ** 400), "too large"),
    (lambda r: (r["a"].update(mean=1e308), r["b"].update(mean=-1e308)), "too large"),
])
def test_cli_bad_record_exits_2(tmp_path, breaker, word):
    rec = _rec(0.712, 0.705)
    breaker(rec)
    f = tmp_path / "in.json"
    f.write_text(json.dumps([rec]))
    r = _cli(f)
    assert r.returncode == 2 and word in r.stderr and r.stdout == ""


def test_cli_unreadable_input_exits_2(tmp_path):
    f = tmp_path / "in.json"
    f.write_text("not json")
    assert _cli(f).returncode == 2


def test_ci_halfwidth_uses_t_for_z_max_so_the_flag_is_not_set():
    m = _mod()
    a = {"mean": "-0.0479", "spread": "1.0224", "spread_kind": "ci95_halfwidth", "runs": 12}
    b = {"mean": "-0.8791", "spread": "0.0163", "spread_kind": "ci95_halfwidth", "runs": 12}
    rec = _rec(0, 0)
    rec.update(a=a, b=b)
    r = m.run_record(rec)
    assert r["status"] == "computed" and r["flag"] is None
    assert r["z_max"] >= 1.645
    assert m.t_crit(12) == pytest.approx(2.2009852, abs=1e-5)


def test_unstatable_runs_for_p05_does_not_fail_the_batch(tmp_path):
    tiny = _rec("1e-160", "0")
    ok = dict(_rec(0.712, 0.705), id="r2")
    f = tmp_path / "in.json"
    f.write_text(json.dumps([tiny, ok]))
    r = _cli(f)
    out = json.loads(r.stdout)
    assert r.returncode == 0 and len(out["results"]) == 2
    assert out["results"][0]["runs_for_p05"] is None and "more runs than can be stated" in out["results"][0]["note"]
    assert out["results"][1]["runs_for_p05"] == 565


def test_float_noise_difference_has_no_stated_runs():
    r = _mod().run_record(_rec("0.30000000000000004", "0.3"))
    assert r["status"] == "computed" and r["runs_for_p05"] is None and "more runs" in r["note"]


# --- Final fix wave A: inside_noise_if_independent (I1) and sNaN (m8) ---

def test_unstated_independence_inside_noise_if_independent_is_true_when_small():
    r = _mod().run_record(_rec(0.712, 0.705, crn="unclear"))
    assert r["status"] == "independence_unstated" and r["flag"] is None
    assert r["inside_noise_if_independent"] is True


def test_unstated_independence_far_outside_noise_is_false():
    r = _mod().run_record(_rec(0.742, 0.605, crn="unclear"))
    assert r["status"] == "independence_unstated" and r["flag"] is None
    assert r["inside_noise_if_independent"] is False


def test_inside_noise_if_independent_matches_the_flag_on_computed_rows():
    m = _mod()
    inside, outside = m.run_record(_rec(0.712, 0.705)), m.run_record(_rec(0.742, 0.705))
    assert inside["flag"] == "inside_noise" and inside["inside_noise_if_independent"] is True
    assert outside["flag"] is None and outside["inside_noise_if_independent"] is False


def test_inside_noise_if_independent_is_false_without_a_claim():
    r = _mod().run_record(_rec(0.712, 0.705, crn="unclear", claim="none"))
    assert r["inside_noise_if_independent"] is False


def test_inside_noise_if_independent_is_null_when_z_max_is_null():
    r = _mod().run_record(_rec("0.5", "0.4", spread="2e-162", runs=1, crn="unclear"))
    assert r["status"] == "independence_unstated" and r["z_max"] is None
    assert r["inside_noise_if_independent"] is None


def test_not_computable_rows_carry_no_inside_noise_if_independent():
    r = _mod().run_record(_rec(0.712, 0.705, crn="yes"))
    assert "inside_noise_if_independent" not in r


def test_assumptions_describe_inside_noise_if_independent():
    assert "inside_noise_if_independent" in _mod().ASSUMPTIONS
    assert "inside_noise_if_independent" in SCRIPT.read_text(encoding="utf-8").split('"""', 2)[1]


@pytest.mark.parametrize("field", ["mean", "spread"])
def test_cli_signaling_nan_exits_2(tmp_path, field):
    rec = _rec(0.712, 0.705)
    rec["a"][field] = "sNaN"
    f = tmp_path / "in.json"
    f.write_text(json.dumps([rec]))
    r = _cli(f)
    assert r.returncode == 2 and f"a.{field}" in r.stderr and r.stdout == "" and "Traceback" not in r.stderr
