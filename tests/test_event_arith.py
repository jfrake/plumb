from __future__ import annotations
import importlib.util
import itertools
import json
import random
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "packs" / "market-event" / "scripts" / "event_arith.py"
_spec = importlib.util.spec_from_file_location("event_arith", SCRIPT)
ea = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ea)

NAMED = "cross-sectional t"


def _one(**rec):
    rec.setdefault("id", "r1")
    return ea.run_record(rec, set())


def _item(label, start, end, value, n=212):
    return {"label": label, "start": start, "end": end, "value": value, "n": n}


def test_named_t_that_fits_its_numbers_is_not_flagged():
    r = _one(kind="car_test", test=NAMED, mean="0.41", sd="5.90", n=212, t="1.01", stars="")
    assert r["status"] == "ok" and r["flag"] is False and r["reasons"] == []
    assert r["values"]["t_recomputed"] == pytest.approx(1.0118, abs=1e-4)
    lo, hi = r["values"]["t_range"]
    assert lo == pytest.approx(0.9986, abs=1e-4) and hi == pytest.approx(1.0250, abs=1e-4)
    plo, phi = r["values"]["p_range"]
    assert plo == pytest.approx(0.3101, abs=1e-4) and phi == pytest.approx(0.3160, abs=1e-4)


def test_named_t_that_cannot_come_from_its_numbers_is_flagged():
    r = _one(kind="car_test", test=NAMED, mean="0.47", sd="6.40", n=88, t="2.14", stars="**")
    lo, hi = r["values"]["t_range"]
    assert lo == pytest.approx(0.6810, abs=1e-4) and hi == pytest.approx(0.6968, abs=1e-4)
    assert r["reasons"] == ["t_mismatch"] and r["flag"] is True
    plo, phi = r["values"]["p_range"]
    assert plo == pytest.approx(0.0320, abs=1e-4) and phi == pytest.approx(0.0356, abs=1e-4)
    # Final fix A3: the p the recomputed t allows, beside what the mark needs.
    rlo, rhi = r["values"]["p_range_recomputed"]
    assert rlo == pytest.approx(0.4859, abs=1e-4) and rhi == pytest.approx(0.4977, abs=1e-4)
    assert any("The recomputed t allows p from 0.4859 to 0.4977; the mark '**' needs at most 0.05" in f
               for f in r["facts"])


@pytest.mark.parametrize("test", ["unspecified", "Patell Z"])
def test_an_unnamed_statistic_that_differs_is_a_fact(test):
    r = _one(kind="car_test", test=test, mean="0.47", sd="6.40", n=88, t="2.14", stars="**")
    assert r["reasons"] == ["reported_stat_differs_from_cross_sectional_t"] and r["flag"] is False
    assert r["values"]["ratio_printed_to_recomputed"] == pytest.approx(3.106, abs=1e-3)


def test_a_stated_formula_names_the_statistic():
    r = _one(kind="car_test", formula_stated=True, mean="0.47", sd="6.40", n=88, t="2.14")
    assert r["reasons"] == ["t_mismatch"] and r["flag"] is True


def test_stars_that_exceed_every_reference_are_flagged_only_when_named():
    r = _one(kind="car_test", test=NAMED, mean="2.10", sd="4.60", n=12, stars="*", tails="two")
    plo, phi = r["values"]["p_range"]
    assert plo == pytest.approx(0.1125, abs=1e-4) and phi == pytest.approx(0.1433, abs=1e-4)
    assert r["reasons"] == ["stars_exceed"] and r["flag"] is True
    # Ruled behavior change (fix round 1): unstated tails also allow the halved band 0.0563-0.0717,
    # which fits "*", so the same record is not flagged.
    r = _one(kind="car_test", test=NAMED, mean="2.10", sd="4.60", n=12, stars="*")
    assert "stars_exceed" not in r["reasons"] and r["flag"] is False
    r = _one(kind="car_test", mean="2.10", sd="4.60", n=12, stars="*", tails="two")
    assert r["reasons"] == ["stars_differ_from_cross_sectional_t"] and r["flag"] is False


def test_stars_that_fit_only_the_normal_are_a_fact():
    r = _one(kind="car_test", test=NAMED, mean="1.00", n=12, t="1.70", stars="*", tails="two")
    plo, phi = r["values"]["p_range"]
    assert plo == pytest.approx(0.0882, abs=1e-4) and phi == pytest.approx(0.1182, abs=1e-4)
    tlo, thi = r["values"]["p_range_t"]
    assert tlo == pytest.approx(0.1162, abs=1e-4)
    assert r["reasons"] == ["stars_exceed_under_t"] and r["flag"] is False
    # Ruled behavior change (final fix A1): unstated tails also allow the halved t interval 0.0581-0.0591,
    # which fits "*", so no stars_exceed_under_t.
    r = _one(kind="car_test", test=NAMED, mean="1.00", n=12, t="1.70", stars="*")
    assert r["reasons"] == [] and r["flag"] is False


def test_a_mark_the_single_p_interval_allows_is_never_flagged():
    # t 2.65 with N 5 printed "**": the normal alone asks for "***" and t(4) alone for "*",
    # but every df between gives a p inside the "**" band.
    r = _one(kind="car_test", test=NAMED, mean="1.00", n=5, t="2.65", stars="**", tails="two")
    plo, phi = r["values"]["p_range"]
    assert plo == pytest.approx(0.0079, abs=1e-4) and phi == pytest.approx(0.0573, abs=1e-4)
    assert r["values"]["p_range_t"][0] == pytest.approx(0.0567, abs=1e-4)
    assert r["reasons"] == ["stars_exceed_under_t"] and r["flag"] is False
    # Final fix A1: with tails unstated the halved t interval fits "**".
    r = _one(kind="car_test", test=NAMED, mean="1.00", n=5, t="2.65", stars="**")
    assert r["reasons"] == [] and r["flag"] is False


def test_a_one_tailed_mark_is_checked_against_the_halved_t():
    r = _one(kind="car_test", test=NAMED, mean="2.00", sd="3.16", n=10, t="2.00", stars="**", tails="one")
    assert "stars_exceed_under_t" not in r["reasons"] and r["flag"] is False


def test_an_even_split_is_not_a_majority_against_the_mean():
    r = _one(kind="sign", n=10, pct_positive="50.0", mean="0.5")
    assert "majority_against_mean" not in r["reasons"]


def test_an_unnamed_statistic_fact_names_the_printed_statistic():
    r = _one(kind="car_test", test="Patell Z", mean="2.10", sd="4.60", n=12, t="1.30", stars="**", tails="two")
    assert r["reasons"][-1] == "stars_differ_from_cross_sectional_t"
    assert any("the printed statistic under any reference from the normal to Student t with 11 df" in f
               for f in r["facts"])
    r = _one(kind="car_test", test="Patell Z", mean="2.10", sd="4.60", n=12, t="1.30", p="0.01", tails="two")
    assert "p_differs_from_cross_sectional_t" in r["reasons"]
    assert any("the printed statistic under any reference from the normal to Student t with 11 df" in f
               for f in r["facts"])


def test_printed_p_and_implied_sd():
    r = _one(kind="car_test", test=NAMED, mean="1.52", sd="8.30", n=212, p="0.30")
    assert r["reasons"] == ["p_mismatch"] and r["flag"] is True
    r = _one(kind="car_test", test=NAMED, mean="1.52", sd="8.30", n=212, p="<0.01")
    assert r["reasons"] == [] and r["flag"] is False
    r = _one(kind="car_test", test=NAMED, mean="1.52", n=212, t="2.67")
    assert r["values"]["implied_sd"] == pytest.approx(8.288, abs=1e-3) and r["flag"] is False
    assert _one(kind="car_test", mean="1.52", n=212)["status"] == "not_computable"


def test_daily_returns_that_do_not_add_to_the_window_are_flagged():
    items = [_item("AR -1", -1, -1, "0.09"), _item("AR 0", 0, 0, "0.27"), _item("AR +1", 1, 1, "0.18"),
             _item("CAR[-1,+1]", -1, 1, "0.41")]
    r = _one(kind="window_sum", measure="CAR", winsorized_level="daily", items=items)
    [t] = r["values"]["tilings"]
    assert t["sum"] == pytest.approx(0.54) and t["gap"] == pytest.approx(0.13) and t["tolerance"] == pytest.approx(0.02)
    assert r["reasons"] == ["sum_mismatch"] and r["flag"] is True
    items[3]["value"] = "0.54"
    assert _one(kind="window_sum", measure="CAR", winsorized_level="daily", items=items)["flag"] is False


@pytest.mark.parametrize("level", ["window", "unstated"])
def test_a_gap_after_window_level_winsorizing_is_a_fact(level):
    items = [_item("AR -1", -1, -1, "0.09"), _item("AR 0", 0, 0, "0.27"), _item("AR +1", 1, 1, "0.18"),
             _item("CAR[-1,+1]", -1, 1, "0.41")]
    r = _one(kind="window_sum", measure="CAR", winsorized_level=level, items=items)
    assert r["reasons"] == ["sum_mismatch_unflagged"] and r["flag"] is False


def test_sub_windows_tile_a_window():
    items = [_item("[-5,-2]", -5, -2, "0.52"), _item("[-1,+1]", -1, 1, "0.41"),
             _item("[+2,+5]", 2, 5, "0.59"), _item("[-5,+5]", -5, 5, "1.52")]
    assert _one(kind="window_sum", measure="CAR", winsorized_level="none", items=items)["flag"] is False
    items[3]["value"] = "1.72"
    assert _one(kind="window_sum", measure="CAR", winsorized_level="none", items=items)["reasons"] == ["sum_mismatch"]
    items[2]["n"] = 210
    r = _one(kind="window_sum", measure="CAR", winsorized_level="none", items=items)
    assert r["reasons"] == ["n_differs"] and r["flag"] is False
    r = _one(kind="window_sum", measure="BHAR", winsorized_level="none", items=items)
    assert r["status"] == "not_computable" and r["flag"] is False


def test_share_positive_and_sign_test():
    r = _one(kind="sign", n=212, pct_positive="46.7", mean="1.52", median="-0.18", test="sign", z="-0.96")
    assert r["values"]["possible_k"] == [99]
    z, zcc = r["values"]["z_candidates"]
    assert z == pytest.approx(-0.9615, abs=1e-4) and zcc == pytest.approx(-0.8928, abs=1e-4)
    assert r["values"]["binomial_p"]["99"] == pytest.approx(0.3720, abs=1e-4)
    assert r["reasons"] == ["majority_against_mean", "median_against_mean"] and r["flag"] is False
    assert _one(kind="sign", n=212, pct_positive="46.7", test="sign", z="-1.50")["reasons"] == ["sign_z_mismatch"]
    r = _one(kind="sign", n=212, pct_positive="46.7", test="generalized sign", z="-1.50")
    assert r["flag"] is False and any("p0" in f for f in r["facts"])


def test_a_printed_p0_keeps_its_rounding():
    # p0 printed as 0.48 may be anything from 0.475 to 0.485; a z of -0.52 fits p0 0.4849.
    r = _one(kind="sign", n=212, n_positive=99, test="generalized sign", p0="0.48", z="-0.52")
    assert r["reasons"] == [] and r["flag"] is False
    lo, hi = r["values"]["z_ranges"][0]
    assert lo == pytest.approx(-0.5249, abs=1e-4) and hi == pytest.approx(-0.2338, abs=1e-4)
    r = _one(kind="sign", n=212, n_positive=99, test="generalized sign", p0="0.480", z="-0.52")
    assert r["reasons"] == ["sign_z_mismatch"] and r["flag"] is True


def test_a_share_no_count_can_produce_is_flagged():
    assert _one(kind="sign", n=212, pct_positive="47.0")["reasons"] == ["pct_not_achievable"]
    assert _one(kind="sign", n=25, pct_positive="47")["reasons"] == ["pct_not_achievable"]
    r = _one(kind="sign", n=25, pct_positive="48")
    assert r["values"]["possible_k"] == [12] and r["flag"] is False


def test_sample_flow():
    steps = [{"label": "no identifiers", "removed": 31}, {"label": "short history", "removed": 19},
             {"label": "zero returns", "removed": 4}]
    r = _one(kind="sample_flow", start=268, steps=steps, final=212)
    assert r["values"]["running"] == [237, 218, 214] and r["reasons"] == ["flow_mismatch"] and r["flag"] is True
    assert _one(kind="sample_flow", start=268, steps=steps, final=214)["flag"] is False
    steps[0]["remaining"] = 236
    assert "step_mismatch" in _one(kind="sample_flow", start=268, steps=steps, final=214)["reasons"]


def test_period_counts():
    counts = {"2007": 21, "2008": 64, "2009": 59, "2010": 31, "2011": 22, "2012": 15}
    r = _one(kind="period_counts", counts=counts, total=212)
    assert r["values"]["largest"] == "2008" and r["flag"] is False
    assert r["values"]["largest_share"] == pytest.approx(0.3019, abs=1e-4)
    assert r["values"]["two_largest_share"] == pytest.approx(0.5802, abs=1e-4)
    assert "herfindahl" not in json.dumps(r).lower()
    assert _one(kind="period_counts", counts=counts, total=220)["reasons"] == ["counts_sum_mismatch"]


def test_event_dates():
    r = _one(kind="event_dates", dates=["2008-10-06", "2008-10-08", "2009-03-02", "2009-03-02", "2010-05-15"],
             window=[-1, 1])
    v = r["values"]
    assert (v["moved"], v["distinct_dates"], v["max_windows_one_day"]) == (1, 4, 2)
    assert v["share_shared_day0"] == pytest.approx(0.4) and v["share_overlapping"] == pytest.approx(0.8)
    assert r["flag"] is False and any("holiday" in f for f in r["facts"])


def test_bad_records_are_invalid_and_the_rest_run(tmp_path):
    src, dst = tmp_path / "in.json", tmp_path / "out.json"
    src.write_text(json.dumps([
        {"id": "a", "kind": "sample_flow", "start": 10, "steps": [{"label": "x", "removed": 2}], "final": 8},
        {"id": "b", "kind": "car_test", "mean": "big", "n": 10, "sd": "1.0"},
        {"id": "a", "kind": "sample_flow", "start": 10, "steps": [{"label": "x", "removed": 2}], "final": 8},
        {"id": "c", "kind": "bhar_test"},
        {"id": "d", "kind": "event_dates", "dates": ["2008-02-30", "2008-03-03"], "window": [-1, 1]},
        {"id": "e", "kind": ["car_test"]},
        {"id": "f", "kind": "car_test", "test": "cross-sectional t", "mean": "1.0", "sd": "2.0", "n": 20,
         "stars": "*", "star_levels": ["*"]},
        {"id": "g", "kind": "car_test", "test": "cross-sectional t", "mean": "1.0", "sd": "2.0", "n": 20,
         "stars": "*", "star_levels": {"*": "0.10"}},
        {"id": "h", "kind": "sign", "n": 50, "n_positive": 20, "z": "-1.00", "p0": "half"},
        {"id": "i", "kind": "event_dates", "dates": ["9999-12-30", "9999-12-31"], "window": [-1, 5]},
        {"id": "j", "kind": "sample_flow", "start": 10, "steps": [{"label": "x", "removed": 2}], "final": 8},
    ]))
    rc = subprocess.run([sys.executable, str(SCRIPT), str(src), str(dst)], capture_output=True, text=True)
    assert rc.returncode == 0, rc.stderr
    out = json.loads(dst.read_text())
    assert [r["status"] for r in out] == ["ok", "invalid", "invalid", "invalid", "invalid"] + ["invalid"] * 5 + ["ok"]
    assert "duplicate" in out[2]["message"] and "date" in out[4]["message"]
    assert "star_levels" in out[6]["message"] and "star_levels" in out[7]["message"] and "p0" in out[8]["message"]


def test_unreadable_inputs_exit_2(tmp_path):
    dst = tmp_path / "out.json"
    bad_json, not_list = tmp_path / "bad.json", tmp_path / "obj.json"
    bad_json.write_text("{not json")
    not_list.write_text(json.dumps({"id": "a"}))
    for src in (tmp_path / "missing.json", bad_json, not_list):
        rc = subprocess.run([sys.executable, str(SCRIPT), str(src), str(dst)], capture_output=True, text=True)
        assert rc.returncode == 2, src
        assert not dst.exists()


def test_tilings_are_exact_and_complete():
    rng = random.Random(11)
    for _ in range(200):
        items = []
        for _ in range(rng.randint(3, 8)):
            s = rng.randint(-6, 6)
            items.append({"label": "", "start": s, "end": s + rng.randint(0, 4), "value": 0.0, "half": 0.0, "n": 1})
        for i, w in enumerate(items):
            got = {tuple(sorted(t)) for t in ea.tilings(items, i, limit=10_000)}
            for t in got:
                days = sorted(d for j in t for d in range(items[j]["start"], items[j]["end"] + 1))
                assert days == list(range(w["start"], w["end"] + 1)) and len(t) >= 2
            others = [j for j in range(len(items)) if j != i]
            want = set()
            for k in range(2, min(6, len(others)) + 1):
                for combo in itertools.combinations(others, k):
                    days = sorted(d for j in combo for d in range(items[j]["start"], items[j]["end"] + 1))
                    if days == list(range(w["start"], w["end"] + 1)):
                        want.add(tuple(sorted(combo)))
            assert want <= got


def test_the_script_uses_the_shared_p_value_module():
    src = SCRIPT.read_text(encoding="utf-8")
    assert "import pvalues" in src and 'parents[3] / "skills" / "review" / "scripts"' in src
    assert "lgamma" not in src and "betacf" not in src and "erfc" not in src


# ---- fix round 1 ----
import time


def _timed(**rec):
    t0 = time.time()
    r = _one(**rec)
    return r, time.time() - t0


def test_huge_n_sign_record_is_analytic():
    r, dt = _timed(kind="sign", n=10**9, pct_positive="55.3")
    assert dt < 1 and r["status"] == "ok"
    assert r["values"]["possible_k"] == [552_500_000, 553_500_000]
    r, dt = _timed(kind="sign", n=10**9, pct_positive="55.3", p0="0.5", test="generalized sign", z="3.0")
    assert dt < 1 and r["status"] == "ok"


def test_binomial_p_is_fast_and_exact_for_n_5000():
    r, dt = _timed(kind="sign", n=5000, pct_positive="55")
    assert dt < 2 and r["status"] == "ok"
    assert len(r["values"]["binomial_p"]) == 2
    r = _one(kind="sign", n=10, n_positive=8)
    assert r["values"]["binomial_p"]["8"] == pytest.approx(0.109375, abs=1e-9)


def test_tails_reading():
    kw = dict(kind="car_test", test=NAMED, mean="0.0090", sd="0.0500", n=100, stars="**", p="0.037")
    assert _one(**kw, tails="one")["flag"] is False
    assert _one(**kw)["flag"] is False
    assert _one(**kw, tails="one-tailed")["flag"] is False
    r = _one(**kw, tails="two")
    assert r["flag"] is True and set(r["reasons"]) <= {"stars_exceed", "p_mismatch"}
    assert _one(**kw, tails="1")["flag"] is False
    assert _one(**kw, tails="2")["flag"] is True
    assert _one(**kw, tails="weird")["flag"] is False


def test_event_dates_window_cap():
    r = _one(kind="event_dates", dates=["2008-10-06", "2008-10-08"], window=[-1300, 1300])
    assert r["status"] == "not_computable" and "2,520 trading days" in r["message"]
    r = _one(kind="event_dates", dates=["2008-10-06", "2008-10-08"], window=[0, 2520])
    assert r["status"] == "ok"


def test_tiling_search_is_pruned():
    items = [{"label": "w", "start": 0, "end": 29, "value": 0.0, "half": 0.0, "n": 1}]
    for a in range(29):
        for b in range(a, 29):
            items.append({"label": "", "start": a, "end": b, "value": 0.0, "half": 0.0, "n": 1})
    t0 = time.time()
    assert ea.tilings(items, 0) == []
    assert time.time() - t0 < 2


def test_sign_of_z_alone_is_a_fact():
    r = _one(kind="sign", n=212, pct_positive="46.7", test="sign", z="0.96")
    assert r["reasons"] == [] and r["flag"] is False
    assert any("sign of z differs" in f for f in r["facts"])


def test_numeric_printed_fields_are_invalid_but_counts_stay_numbers():
    r = _one(kind="car_test", test=NAMED, mean=0.41, sd="5.90", n=212, t="1.01")
    assert r["status"] == "invalid" and "copy printed values as strings" in r["message"]
    r = _one(kind="sign", n=212, pct_positive=46.7)
    assert r["status"] == "invalid" and "copy printed values as strings" in r["message"]
    items = [_item("a", 0, 0, 0.1), _item("b", 1, 1, "0.2"), _item("c", 0, 1, "0.3")]
    r = _one(kind="window_sum", measure="CAR", winsorized_level="none", items=items)
    assert r["status"] == "invalid" and "copy printed values as strings" in r["message"]
    assert _one(kind="sign", n=212, n_positive=99)["status"] == "ok"


def test_wide_binomial_range_spans_the_middle():
    r = _one(kind="sign", n=5000, pct_positive="50")
    bp = r["values"]["binomial_p"]
    assert max(bp.values()) == pytest.approx(1.0) and "2500" in bp
    assert any("over counts" in f for f in r["facts"])


def test_numeric_p_is_invalid():
    r = _one(kind="car_test", test=NAMED, mean="1.52", sd="8.30", n=212, p=0.03)
    assert r["status"] == "invalid" and "copy printed values as strings" in r["message"]
