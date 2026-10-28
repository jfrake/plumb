from __future__ import annotations
import importlib.util
import json
import random
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "packs" / "nonlinear" / "scripts" / "nonlinear_arith.py"
_spec = importlib.util.spec_from_file_location("nonlinear_arith", SCRIPT)
na = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(na)


def _one(**rec):
    rec.setdefault("id", "r1")
    rec.setdefault("check", "N1")
    return na.run_record(rec, set())


def test_quadratic_turning_point_outside_the_range_is_one_flag():
    r = _one(kind="quadratic", b1=0.84, b2=-0.078, x_min=0.0, x_max=3.10)
    assert r["status"] == "ok" and r["flag"] is True
    assert r["values"]["tp"] == pytest.approx(5.384615, abs=1e-5)
    assert r["reasons"] == ["tp_outside_range"]
    assert r["values"]["slope_at_max"] == pytest.approx(0.3564)
    assert r["values"]["slope_at_min"] == pytest.approx(0.84)


def test_end_slope_bounds_without_covariance():
    r = _one(kind="quadratic", b1=0.12, b2=-0.0060, se1=0.020, se2=0.0024, x_min=3.0, x_max=15.0)
    assert r["values"]["tp"] == pytest.approx(10.0)
    hi = r["values"]["slope_test_at_max"]
    assert r["values"]["slope_at_max"] == pytest.approx(-0.06)
    assert hi["se_lo"] == pytest.approx(0.052) and hi["se_hi"] == pytest.approx(0.092)
    assert hi["verdict"] == "insignificant_any_cov"
    lo = r["values"]["slope_test_at_min"]
    assert lo["se_lo"] == pytest.approx(0.0056) and lo["se_hi"] == pytest.approx(0.0344)
    assert lo["z_lo"] == pytest.approx(2.44186, abs=1e-4) and lo["verdict"] == "significant"
    assert r["reasons"] == ["end_slope_insignificant_any_cov"] and r["flag"] is True


def test_quadratic_centered_decoy_does_not_flag():
    r = _one(kind="quadratic", b1=-0.24, b2=-1.20, se1=0.10, se2=0.30, cov12=0.006,
             x_min=-0.38, x_max=0.58)
    assert r["values"]["tp"] == pytest.approx(-0.10)
    assert r["values"]["tp_se_delta"] == pytest.approx(0.044096, abs=1e-5)
    lo, hi = r["values"]["tp_fieller"]
    assert lo == pytest.approx(-0.222423, abs=1e-5) and hi == pytest.approx(-0.019705, abs=1e-5)
    assert r["flag"] is False and r["reasons"] == []


def test_depends_on_covariance_is_a_fact_not_a_flag():
    r = _one(kind="quadratic", b1=0.30, b2=-0.50, se1=0.10, se2=0.20, x_min=-0.37, x_max=0.53)
    hi = r["values"]["slope_test_at_max"]
    assert r["values"]["slope_at_max"] == pytest.approx(-0.23)
    assert hi["z_lo"] == pytest.approx(0.737179, abs=1e-5) and hi["z_hi"] == pytest.approx(2.053571, abs=1e-5)
    assert r["values"]["slope_test_at_min"]["verdict"] == "significant"
    assert r["reasons"] == ["end_slope_depends_on_cov"] and r["flag"] is False


def test_quadratic_with_mean_and_sd_only_never_flags():
    r = _one(kind="quadratic", b1=0.84, b2=-0.078, x_mean=1.2, x_sd=0.6)
    assert r["status"] == "ok" and r["flag"] is False
    assert r["values"]["tp_sd_from_mean"] == pytest.approx((5.384615 - 1.2) / 0.6, abs=1e-4)
    assert "inside" not in r["values"]


def test_quadratic_invalid_and_unbounded_fieller():
    assert _one(kind="quadratic", b1=1.0, b2=0.0, x_min=0.0, x_max=1.0)["status"] == "invalid"
    r = _one(kind="quadratic", b1=0.5, b2=-0.1, se1=0.2, se2=0.1, cov12=0.0, x_min=0.0, x_max=5.0)
    assert r["values"]["tp_fieller"] is None and "fieller_unbounded" in r["reasons"]


def test_near_edge_needs_percentiles():
    r = _one(kind="quadratic", b1=1.0, b2=-0.1, x_min=0.0, x_max=5.2, x_p05=0.5, x_p95=4.5)
    assert r["values"]["tp"] == pytest.approx(5.0) and r["reasons"] == ["tp_near_edge"]
    assert r["flag"] is False
    r = _one(kind="quadratic", b1=1.0, b2=-0.1, x_min=0.0, x_max=5.2)
    assert "tp_near_edge" not in r["reasons"]


def test_moderated_curve_flips_inside_the_moderator_range():
    r = _one(kind="moderated_quadratic", b1=0.84, b2=-0.10, b3=0.01, b4=0.008,
             x_min=0.0, x_max=3.10, m_min=1.0, m_max=22.0)
    assert r["values"]["m_star"] == pytest.approx(12.5)
    assert "curvature_flips_in_moderator_range" in r["reasons"] and r["flag"] is True


def test_linear_interaction_lower_order_term_read_outside_the_range():
    r = _one(kind="linear_interaction", m_min=2.0, m_max=9.0, lower_order_read=True)
    assert r["reasons"] == ["zero_outside_range", "lower_order_read_outside_range"] and r["flag"] is True
    r = _one(kind="linear_interaction", m_min=2.0, m_max=9.0)
    assert r["reasons"] == ["zero_outside_range"] and r["flag"] is False
    r = _one(kind="linear_interaction", m_min=-1.0, m_max=9.0, lower_order_read=True)
    assert r["reasons"] == [] and r["flag"] is False


def test_linear_interaction_conditional_slopes():
    r = _one(kind="linear_interaction", b1=0.31, b3=-0.05, se1=0.10, se3=0.02, m_min=2.0, m_max=9.0)
    assert r["values"]["slope_at_min"] == pytest.approx(0.21)
    assert r["values"]["slope_at_max"] == pytest.approx(-0.14)
    assert r["values"]["m_zero"] == pytest.approx(6.2)
    assert "slope_changes_sign_in_range" in r["reasons"] and r["flag"] is False
    t = r["values"]["slope_test_at_min"]
    assert t["se_lo"] == pytest.approx(0.06) and t["se_hi"] == pytest.approx(0.14)


def test_plotted_points_outside_the_range():
    r = _one(kind="plotted_points", m_min=0.0, m_max=14.0, m_mean=1.5, m_sd=2.4)
    assert r["values"]["outside"] == [pytest.approx(-0.9)]
    assert r["reasons"] == ["point_outside_range"] and r["flag"] is True


def test_difference_between_independent_estimates():
    r = _one(kind="difference", b_a=0.20, se_a=0.09, b_b=0.11, se_b=0.09, independent=True)
    assert r["values"]["z"] == pytest.approx(0.707107, abs=1e-5)
    assert r["reasons"] == ["difference_not_distinguishable"] and r["flag"] is True
    r = _one(kind="difference", b_a=0.20, se_a=0.09, b_b=0.11, se_b=0.09, independent=False)
    assert r["status"] == "not_computable" and r["flag"] is False


def test_odds_ratio_misread_as_a_ratio_of_probabilities():
    r = _one(kind="odds_ratio", odds_ratio=1.8, base_rate=0.40, claimed_relative_change=0.80)
    assert r["values"]["p1"] == pytest.approx(0.545455, abs=1e-5)
    assert r["values"]["relative_change"] == pytest.approx(0.363636, abs=1e-5)
    assert r["reasons"] == ["or_claim_mismatch"] and r["flag"] is True


def test_odds_ratio_rare_outcome_is_not_flagged():
    r = _one(kind="odds_ratio", odds_ratio=1.8, base_rate=0.05, claimed_relative_change=0.80)
    assert r["values"]["relative_change"] == pytest.approx(0.730769, abs=1e-5)
    assert r["flag"] is False
    r = _one(kind="odds_ratio", odds_ratio=1.8, base_rate=0.40, claimed_relative_change=0.40)
    assert r["flag"] is False


def test_bad_records_are_invalid_and_the_rest_run(tmp_path):
    src, dst = tmp_path / "in.json", tmp_path / "out.json"
    src.write_text(json.dumps([
        {"id": "a", "kind": "odds_ratio", "odds_ratio": 2.0, "base_rate": 0.5},
        {"id": "b", "kind": "quadratic", "b1": "big", "b2": -1, "x_min": 0, "x_max": 1},
        {"id": "a", "kind": "odds_ratio", "odds_ratio": 2.0, "base_rate": 0.5},
        {"id": "c", "kind": "cubic"},
        {"id": "d", "kind": "quadratic", "b1": 1, "b2": -1, "se1": 0.1, "se2": 0.1, "cov12": 0.5,
         "x_min": 0, "x_max": 1},
    ]))
    rc = subprocess.run([sys.executable, str(SCRIPT), str(src), str(dst)], capture_output=True, text=True)
    assert rc.returncode == 0, rc.stderr
    out = json.loads(dst.read_text())
    assert [r["status"] for r in out] == ["ok", "invalid", "invalid", "invalid", "invalid"]
    assert "duplicate" in out[2]["message"] and "cov12" in out[4]["message"]
    assert out[0]["flag"] is False and out[1]["flag"] is False


def test_unreadable_inputs_exit_2(tmp_path):
    dst = tmp_path / "out.json"
    bad_json, not_list = tmp_path / "bad.json", tmp_path / "obj.json"
    bad_json.write_text("{not json")
    not_list.write_text(json.dumps({"id": "a"}))
    for src in (tmp_path / "missing.json", bad_json, not_list):
        rc = subprocess.run([sys.executable, str(SCRIPT), str(src), str(dst)], capture_output=True, text=True)
        assert rc.returncode == 2, src
        assert not dst.exists()


def test_fieller_interval_matches_its_inequality():
    rng = random.Random(7)
    checked = 0
    while checked < 200:
        b1, b2 = rng.uniform(-2, 2), rng.uniform(-2, 2)
        se1, se2 = rng.uniform(0.01, 0.5), rng.uniform(0.01, 0.5)
        cov = rng.uniform(-1, 1) * se1 * se2
        t = 1.96
        interval = na._fieller(b1, b2, se1, se2, cov, t)
        if interval is None:
            continue
        lo, hi = interval

        def f(th):
            return (b1 + 2 * th * b2) ** 2 - t ** 2 * (se1 ** 2 + 4 * th * cov + 4 * th ** 2 * se2 ** 2)

        eps = 1e-6 * max(1.0, hi - lo)
        for th in (lo + eps, (lo + hi) / 2, hi - eps):
            assert f(th) <= 1e-9
        assert f(lo - 1e-3 * max(1.0, hi - lo)) > 0 and f(hi + 1e-3 * max(1.0, hi - lo)) > 0
        assert lo <= -b1 / (2 * b2) <= hi
        checked += 1


def test_printed_rounding_straddling_the_range_edge_is_not_a_flag():
    r = _one(kind="quadratic", b1="0.84", b2="-0.14", x_min=0.0, x_max=2.95)
    assert "tp_outside_range" not in r["reasons"]
    assert "tp_outside_range_rounding_sensitive" in r["reasons"] and r["flag"] is False


def test_exact_numbers_at_the_same_edge_still_flag():
    r = _one(kind="quadratic", b1=0.84, b2=-0.14, x_min=0.0, x_max=2.95)
    assert r["reasons"][0] == "tp_outside_range" and r["flag"] is True


def test_printed_strings_clearly_outside_still_flag_and_bad_strings_are_invalid():
    r = _one(kind="quadratic", b1="0.84", b2="-0.078", x_min=0.0, x_max=3.10)
    assert r["reasons"] == ["tp_outside_range"] and r["flag"] is True
    r = _one(kind="quadratic", b1="0.8.4", b2=-1, x_min=0, x_max=1)
    assert r["status"] == "invalid" and "b1" in r["message"]
    assert _one(kind="quadratic", b1="nan", b2=-1, x_min=0, x_max=1)["status"] == "invalid"


def test_odds_ratio_claim_consistent_with_some_rounded_value_is_not_flagged():
    r = _one(kind="odds_ratio", odds_ratio="1.1", base_rate="0.4", claimed_relative_change=0.084)
    assert r["flag"] is False and "or_claim_mismatch_rounding_sensitive" in r["reasons"]
    r = _one(kind="odds_ratio", odds_ratio="1.0", base_rate="0.5", claimed_relative_change=0.01)
    assert r["flag"] is False
    r = _one(kind="odds_ratio", odds_ratio="1.8", base_rate="0.4", claimed_relative_change=0.80)
    assert r["reasons"] == ["or_claim_mismatch"] and r["flag"] is True


def test_output_is_strict_json_when_a_bound_is_unbounded(tmp_path):
    src, dst = tmp_path / "in.json", tmp_path / "out.json"
    src.write_text(json.dumps([{"id": "a", "kind": "linear_interaction", "b1": 0.3, "b3": -0.05,
                                "se1": 0.10, "se3": 0.05, "m_min": 2, "m_max": 9}]))
    rc = subprocess.run([sys.executable, str(SCRIPT), str(src), str(dst)], capture_output=True, text=True)
    assert rc.returncode == 0, rc.stderr

    def refuse(c):
        raise AssertionError(c)

    out = json.loads(dst.read_text(), parse_constant=refuse)
    assert out[0]["status"] == "ok" and out[0]["values"]["slope_test_at_min"]["z_hi"] is None
    assert not any("inf" in f for f in out[0]["facts"])


def test_overflow_record_is_invalid_and_the_rest_run(tmp_path):
    src, dst = tmp_path / "in.json", tmp_path / "out.json"
    src.write_text(json.dumps([
        {"id": "big", "kind": "quadratic", "b1": 1, "b2": -1, "se1": 1e200, "se2": 1e200,
         "cov12": 1e200, "x_min": 0, "x_max": 1},
        {"id": "ok", "kind": "odds_ratio", "odds_ratio": 2.0, "base_rate": 0.5},
    ]))
    rc = subprocess.run([sys.executable, str(SCRIPT), str(src), str(dst)], capture_output=True, text=True)
    assert rc.returncode == 0, rc.stderr
    out = json.loads(dst.read_text())
    assert [r["status"] for r in out] == ["invalid", "ok"] and out[0]["flag"] is False


def test_zero_width_ranges_are_invalid():
    assert _one(kind="quadratic", b1=1, b2=-1, x_min=1.0, x_max=1.0)["status"] == "invalid"
    assert _one(kind="linear_interaction", m_min=2.0, m_max=2.0)["status"] == "invalid"


def test_curvature_flip_flags_only_when_the_rounding_box_agrees():
    kw = dict(kind="moderated_quadratic", b1=0.5, b3=0.0, x_min=-10.0, x_max=10.0, m_min=0.0, m_max=10.0)
    r = _one(b2="0.10", b4="-0.0105", **kw)
    assert "curvature_flips_in_moderator_range" not in r["reasons"]
    assert "curvature_flips_in_moderator_range_rounding_sensitive" in r["reasons"]
    r = _one(b2=0.10, b4=-0.0105, **kw)
    assert "curvature_flips_in_moderator_range" in r["reasons"] and r["flag"] is True


def test_fieller_interval_leaving_the_range_flags_only_when_the_rounding_box_agrees():
    kw = dict(kind="quadratic", se1=0.05, se2=0.05, cov12=0.0, x_min=0.3775, x_max=1.0)
    r = _one(b1="0.50", b2="-0.50", **kw)
    assert "tp_interval_leaves_range" not in r["reasons"]
    assert "tp_interval_leaves_range_rounding_sensitive" in r["reasons"]
    r = _one(b1=0.5, b2=-0.5, **kw)
    assert "tp_interval_leaves_range" in r["reasons"] and r["flag"] is True


def test_turning_point_uses_its_exact_range_over_the_box():
    r = _one(kind="quadratic", b1="0.1", b2="-0.01", x_min=2.6, x_max=3.2)
    assert "tp_outside_range" not in r["reasons"] and r["flag"] is False
    assert "tp_outside_range_rounding_sensitive" in r["reasons"]
    r = _one(kind="quadratic", b1=0.1, b2=-0.01, x_min=2.6, x_max=3.2)
    assert r["reasons"][0] == "tp_outside_range" and r["flag"] is True


def test_turning_point_at_m_does_not_flag_when_the_curvature_box_holds_zero():
    kw = dict(kind="moderated_quadratic", b1="1.6", b2="-0.10", b3=0, b4="0.02",
              x_min=1.7, x_max=10.7, m_min="0", m_max="4.9")
    r = _one(**kw)
    assert "tp_outside_range_at_m" not in r["reasons"] and r["flag"] is False
    assert "tp_outside_range_at_m_rounding_sensitive" in r["reasons"]
    kw.update(b1=1.6, b2=-0.10, b4=0.02, m_min=0.0, m_max=4.9)
    assert "tp_outside_range_at_m" in _one(**kw)["reasons"]
    r = _one(kind="moderated_quadratic", b1="1", b2="-0.1", b3=0, b4=0.01, x_min=20, x_max=25,
             m_min=0, m_max=9.9)
    assert "tp_outside_range_at_m" in r["reasons"]


def test_end_slope_bound_is_not_a_flag_when_the_standard_error_bound_reaches_zero():
    r = _one(kind="quadratic", b1=0.4423, b2=-0.2, se1="0.03", se2="0.01", x_min=1.1, x_max=1.2)
    assert "end_slope_insignificant_any_cov" not in r["reasons"] and r["flag"] is False
    assert "end_slope_insignificant_any_cov_rounding_sensitive" in r["reasons"]
    r = _one(kind="linear_interaction", b1=0.05, b3=0.0, se1="0.03", se3="0.01", m_min=1.0, m_max=3.0)
    assert "slope_insignificant_at_max" not in r["reasons"]


def test_covariance_is_clamped_to_what_the_standard_errors_allow():
    lo, hi = na._se_range((0.1, 0.1), (0.1, 0.1), (1.0, 1.0), (0.5, 0.5))
    assert lo == pytest.approx(0.2) and hi == pytest.approx(0.2)
    lo, hi = na._se_range((0.1, 0.1), (0.1, 0.1), (1.0, 1.0), (-0.5, -0.5))
    assert lo == pytest.approx(0.0, abs=1e-9) and hi == pytest.approx(0.0, abs=1e-9)


def test_plotted_points_from_a_printed_mean_and_sd_are_boxed():
    r = _one(kind="plotted_points", m_mean="1.0", m_sd="1.04", m_min=0, m_max=14)
    assert r["flag"] is False and "point_outside_range_rounding_sensitive" in r["reasons"]
    r = _one(kind="plotted_points", m_mean=1.0, m_sd=1.04, m_min=0, m_max=14)
    assert r["flag"] is True
    r = _one(kind="plotted_points", points=["-0.5", 3], m_min=0, m_max=14)
    assert r["reasons"] == ["point_outside_range"] and r["flag"] is True
    assert _one(kind="plotted_points", points=["x"], m_min=0, m_max=1)["status"] == "invalid"


def test_difference_flags_only_when_every_rounded_value_is_indistinguishable():
    r = _one(kind="difference", b_a="0.20", se_a="0.10", b_b="0.004", se_b="0.001", independent=True)
    assert r["flag"] is False and "difference_not_distinguishable_rounding_sensitive" in r["reasons"]
    r = _one(kind="difference", b_a=0.20, se_a=0.10, b_b=0.004, se_b=0.001, independent=True)
    assert r["flag"] is True
    r = _one(kind="difference", b_a="0.20", se_a="0.09", b_b="0.11", se_b="0.09", independent=True)
    assert r["reasons"] == ["difference_not_distinguishable"] and r["flag"] is True


def test_base_rate_box_straddling_the_rare_cutoff_never_flags():
    r = _one(kind="odds_ratio", odds_ratio=2.0, base_rate="0.10", claimed_relative_change=0.1)
    assert r["flag"] is False and "or_claim_mismatch_rounding_sensitive" in r["reasons"]
    r = _one(kind="odds_ratio", odds_ratio=2.0, base_rate=0.10, claimed_relative_change=0.1)
    assert r["flag"] is True


def test_m_values_accept_printed_strings():
    r = _one(kind="moderated_quadratic", b1=0.84, b2=-0.10, b3=0.01, b4=0.008,
             x_min=0.0, x_max=3.10, m_min=1.0, m_max=22.0, m_values=["5.0"])
    assert r["status"] == "ok" and any(a["m"] == 5.0 for a in r["values"]["at"])
    r = _one(kind="moderated_quadratic", b1=0.84, b2=-0.10, b3=0.01, b4=0.008,
             x_min=0.0, x_max=3.10, m_min=1.0, m_max=22.0, m_values=["oops"])
    assert r["status"] == "invalid"


def test_moderated_turning_point_range_uses_the_undoubled_curvature():
    kw = dict(kind="moderated_quadratic", b1=1, b2=-0.1, b3=0, b4=0.001, m_min=0, m_max=1)
    r = _one(x_min=4.5, x_max=5.6, **kw)
    assert "tp_outside_range_at_m" not in r["reasons"] and r["flag"] is False
    r = _one(x_min=2, x_max=3, **kw)
    assert "tp_outside_range_at_m" in r["reasons"] and r["flag"] is True


def test_tp_outside_range_at_m_agrees_with_reported_turning_points():
    rng = random.Random(11)
    for _ in range(400):
        x_min = rng.uniform(-3, 3)
        rec = dict(kind="moderated_quadratic", b1=rng.uniform(-2, 2), b2=rng.uniform(-1, 1),
                   b3=rng.uniform(-1, 1), b4=rng.uniform(-1, 1), x_min=x_min,
                   x_max=x_min + rng.uniform(0.1, 6), m_min=rng.uniform(-2, 0),
                   m_max=rng.uniform(0.5, 3))
        r = _one(**rec)
        expected = any(a["tp"] is not None and not rec["x_min"] <= a["tp"] <= rec["x_max"]
                       for a in r["values"]["at"])
        assert ("tp_outside_range_at_m" in r["reasons"]) == expected, rec


def test_only_certain_outcomes_get_certain_sounding_facts():
    r = _one(kind="linear_interaction", m_min="0", m_max=9.0)
    assert "zero_outside_range_rounding_sensitive" in r["reasons"]
    assert not any("Zero lies outside" in f for f in r["facts"])
    r = _one(kind="moderated_quadratic", b1=0.5, b3=0.0, x_min=-10.0, x_max=10.0, m_min=0.0,
             m_max=10.0, b2="0.10", b4="-0.0105")
    assert "curvature_flips_in_moderator_range_rounding_sensitive" in r["reasons"]
    assert not any("curvature changes sign" in f for f in r["facts"])
    r = _one(kind="linear_interaction", m_min=2.0, m_max=9.0)
    assert any("Zero lies outside" in f for f in r["facts"])


def test_claim_reversal_is_the_default_and_bad_claims_are_invalid():
    base = dict(kind="quadratic", b1="0.12", b2="-0.0060", se1="0.020", se2="0.0024", x_min=3.0, x_max=15.0)
    assert _one(**base) == _one(claim="reversal", **base)
    assert _one(claim="u-shape", **base)["status"] == "invalid"


def test_monotone_claim_never_flags_a_turning_point_outside_the_range():
    rec = dict(kind="quadratic", b1="0.84", b2="-0.078", se1="0.10", se2="0.030", cov12="-0.0025",
               x_min="0.0", x_max="3.10")
    rev = _one(**rec)
    assert "tp_outside_range" in rev["reasons"] and rev["flag"] is True
    mono = _one(claim="monotone", **rec)
    assert mono["status"] == "ok" and mono["flag"] is False
    assert not any(r.startswith("tp_outside_range") or r.startswith("tp_interval_leaves_range") for r in mono["reasons"])
    assert "slope_test_at_min" not in mono["values"]
    assert mono["values"]["slope_test_at_max"]["verdict"] == "significant"
    assert mono["values"]["tp"] == pytest.approx(rev["values"]["tp"])


def test_monotone_claim_tests_only_the_far_end():
    rec = dict(kind="quadratic", b1=0.12, b2=-0.0060, se1=0.020, se2=0.0024, x_min=3.0, x_max=15.0)
    mono = _one(claim="monotone", **rec)
    assert mono["reasons"] == ["end_slope_insignificant_any_cov"] and mono["flag"] is True
    assert "slope_test_at_min" not in mono["values"] and mono["values"]["slope_test_at_max"]["verdict"] == "insignificant_any_cov"
    # The near end would be insignificant here, but a monotone claim does not test it.
    near = _one(claim="monotone", kind="quadratic", b1=0.02, b2=0.004, se1=0.020, se2=0.0010, x_min=0.0, x_max=10.0)
    assert near["flag"] is False and "slope_test_at_min" not in near["values"]
    assert _one(kind="quadratic", b1=0.02, b2=0.004, se1=0.020, se2=0.0010, x_min=0.0, x_max=10.0)["flag"] is True


def test_monotone_far_end_slope_keeps_the_rounding_box():
    printed = dict(kind="quadratic", b1="0.30", b2="-0.05", se1="0.10", se2="0.020", cov12="-0.0015",
                   x_min="0", x_max="1.8")
    assert _one(**printed)["reasons"] == ["tp_outside_range"]
    mono = _one(claim="monotone", **printed)
    assert mono["reasons"] == ["end_slope_insignificant_rounding_sensitive"] and mono["flag"] is False
    assert mono["values"]["slope_test_at_max"]["z"] == pytest.approx(1.812366, abs=1e-5)
    exact = _one(claim="monotone", kind="quadratic", b1=0.30, b2=-0.05, se1=0.10, se2=0.020, cov12=-0.0015,
                 x_min=0.0, x_max=1.8)
    assert exact["reasons"] == ["end_slope_insignificant"] and exact["flag"] is True


def test_monotone_claim_keeps_near_edge_as_a_fact_and_skips_the_interval_flag():
    rec = dict(kind="quadratic", b1=1.0, b2=-0.1, x_min=0.0, x_max=5.2, x_p05=0.5, x_p95=4.5)
    assert _one(claim="monotone", **rec)["reasons"] == ["tp_near_edge"]
    leaving = dict(kind="quadratic", b1=0.60, b2=-0.10, se1=0.10, se2=0.030, cov12=-0.0025, x_min=0.0, x_max=3.5)
    rev, mono = _one(**leaving), _one(claim="monotone", **leaving)
    assert "tp_interval_leaves_range" in rev["reasons"]
    assert "tp_interval_leaves_range" not in mono["reasons"] and mono["values"]["tp_fieller"] == rev["values"]["tp_fieller"]
