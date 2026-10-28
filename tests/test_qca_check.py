from __future__ import annotations
import importlib.util
import itertools
import json
import random
import subprocess
import sys
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal
from fractions import Fraction
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "packs" / "configurational" / "scripts" / "qca_check.py"


def _load():
    spec = importlib.util.spec_from_file_location("qca_check", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


Q = _load()


def _run(*records):
    return Q.run_records(list(records))


def _one(results, check):
    [r] = [r for r in results if r["check"] == check]
    return r


def _term(label, cons=None, pri=None, raw=None, uniq=None, headline=False):
    return {"label": label, "raw_consistency": cons, "pri": pri, "raw_coverage": raw, "unique_coverage": uniq,
            "headline": headline}


def _fit(terms, sol_cov=None, sol_cons=None, rid="fit", **extra):
    rec = {"id": rid, "kind": "fit_table", "source": "Table 3, p. 10", "cells": [], "terms": terms,
           "solution_coverage": sol_cov, "solution_consistency": sol_cons}
    rec.update(extra)
    return rec


# --- arithmetic: each reason fires, and its boundary case does not ---

CASES = [
    ("unique_exceeds_raw", _fit([_term("A", raw="0.400", uniq="0.406")]), True),
    ("unique_exceeds_raw", _fit([_term("A", raw="0.400", uniq="0.405")]), False),
    ("pri_exceeds_consistency", _fit([_term("A", cons="0.810", pri="0.816")]), True),
    ("pri_exceeds_consistency", _fit([_term("A", cons="0.810", pri="0.815")]), False),
    ("solution_coverage_below_max_raw", _fit([_term("A", raw="0.400"), _term("B", raw="0.300")], "0.394"), True),
    ("solution_coverage_below_max_raw", _fit([_term("A", raw="0.400"), _term("B", raw="0.300")], "0.395"), False),
    ("solution_coverage_above_sum_raw", _fit([_term("A", raw="0.300"), _term("B", raw="0.200")], "0.506"), True),
    ("solution_coverage_above_sum_raw", _fit([_term("A", raw="0.300"), _term("B", raw="0.200")], "0.505"), False),
    ("unique_sum_exceeds_solution",
     _fit([_term("A", raw="0.400", uniq="0.300"), _term("B", raw="0.400", uniq="0.311")], "0.600"), True),
    ("unique_sum_exceeds_solution",
     _fit([_term("A", raw="0.400", uniq="0.300"), _term("B", raw="0.400", uniq="0.310")], "0.600"), False),
    ("value_out_of_range", _fit([_term("A", cons="1.02")]), True),
    ("value_out_of_range", _fit([_term("A", cons="1.00")]), False),
    ("pri_below_half", _fit([_term("A", cons="0.80", pri="0.494")]), True),
    ("pri_below_half", _fit([_term("A", cons="0.80", pri="0.495")]), False),
    ("frequency_rows_exceed_n",
     {"id": "d", "kind": "design", "source": "p. 8", "conditions": 4, "n_cases": 20, "frequency_cutoff": 3,
      "rows_kept": 7}, True),
    ("frequency_rows_exceed_n",
     {"id": "d", "kind": "design", "source": "p. 8", "conditions": 4, "n_cases": 21, "frequency_cutoff": 3,
      "rows_kept": 7}, False),
    ("observed_rows_impossible",
     {"id": "d", "kind": "design", "source": "p. 8", "conditions": 3, "n_cases": 40, "observed_rows": 9}, True),
    ("observed_rows_impossible",
     {"id": "d", "kind": "design", "source": "p. 8", "conditions": 3, "n_cases": 40, "observed_rows": 8}, False),
    ("cases_exceed_n",
     {"id": "d", "kind": "design", "source": "p. 8", "conditions": 3, "n_cases": 40, "cases_in_truth_table": 41},
     True),
    ("cases_exceed_n",
     {"id": "d", "kind": "design", "source": "p. 8", "conditions": 3, "n_cases": 40, "cases_in_truth_table": 40},
     False),
    ("necessary_below_threshold",
     {"id": "n", "kind": "necessity", "source": "Table 2", "threshold": "0.90",
      "rows": [{"condition": "A", "consistency": "0.894", "coverage": "0.60", "declared_necessary": True}]}, True),
    ("necessary_below_threshold",
     {"id": "n", "kind": "necessity", "source": "Table 2", "threshold": "0.90",
      "rows": [{"condition": "A", "consistency": "0.895", "coverage": "0.60", "declared_necessary": True}]}, False),
    ("row_coded_against_cutoff",
     {"id": "t", "kind": "truth_table", "source": "Table 4", "consistency_cutoff": "0.80",
      "rows": [{"n": 5, "raw_consistency": "0.794", "pri": "0.70", "outcome": 1}]}, True),
    ("row_coded_against_cutoff",
     {"id": "t", "kind": "truth_table", "source": "Table 4", "consistency_cutoff": "0.80",
      "rows": [{"n": 5, "raw_consistency": "0.795", "pri": "0.70", "outcome": 1}]}, False),
]


@pytest.mark.parametrize("reason,record,fires", CASES)
def test_each_reason_fires_and_its_boundary_does_not(reason, record, fires):
    results = _run(record)
    hit = [r for r in results if reason in r["reasons"]]
    assert bool(hit) == fires, results
    if fires:
        assert hit[0]["flag"] is True and hit[0]["check"] == Q.REASON_CHECK[reason]


def test_pri_above_consistency_by_0006_flags_and_by_0004_does_not():
    assert _one(_run(_fit([_term("A", cons="0.810", pri="0.816")])), "B7")["flag"] is True
    assert _one(_run(_fit([_term("A", cons="0.810", pri="0.814")])), "B7")["flag"] is False


def test_crisp_disjoint_example_is_rounding_sensitive():
    rec = _fit([_term("A*B", cons="1.00", raw="0.12", uniq="0.12"), _term("~A*C", cons="1.00", raw="0.12",
                                                                           uniq="0.12")], "0.25", "1.00",
               crisp_outcome=True)
    r = _one(_run(rec), "B7")
    assert r["reasons"] == ["solution_coverage_above_sum_raw_rounding_sensitive"] and r["flag"] is False
    assert r["facts"]["violations"][0]["rounding_bound"] == "0.015"


def test_sum_rounding_bound_at_three_decimals():
    def excess_result(k, sol):
        terms = [_term(f"C{i}", raw="0.050") for i in range(k)]
        return _one(_run(_fit(terms, sol)), "B7")

    nine = excess_result(9, "0.456")  # excess 0.006; bound 10 x 0.0005 = 0.005
    assert nine["reasons"] == ["solution_coverage_above_sum_raw"] and nine["flag"] is True
    assert nine["facts"]["violations"][0]["rounding_bound"] == "0.0050"
    ten = excess_result(10, "0.506")  # excess 0.006; bound 11 x 0.0005 = 0.0055
    assert ten["facts"]["violations"][0]["rounding_bound"] == "0.0055" and ten["flag"] is True
    eleven = excess_result(11, "0.556")  # excess 0.006; bound 12 x 0.0005 = 0.006
    assert eleven["reasons"] == ["solution_coverage_above_sum_raw_rounding_sensitive"]
    assert eleven["flag"] is False


def test_pre_grill_unique_sum_decoy_passes():
    rec = _fit([_term("A", raw="0.20", uniq="0.12"), _term("B", raw="0.20", uniq="0.11"),
                _term("C", raw="0.20", uniq="0.11")], "0.33")
    assert _one(_run(rec), "B7")["reasons"] == []


def test_pairwise_tolerance_follows_printed_precision():
    assert _one(_run(_fit([_term("A", cons="0.87", pri="0.9")])), "B7")["reasons"] == []
    assert _one(_run(_fit([_term("A", cons="0.84", pri="0.9")])), "B7")["reasons"] == ["pri_exceeds_consistency"]
    assert _one(_run(_fit([_term("A", cons="0.81", pri="0.82")])), "B7")["reasons"] == ["pri_exceeds_consistency"]


def test_float_traps_are_exact():
    assert 0.26 - 0.25 > 0.01  # the trap is real in binary floating point
    uniq = _fit([_term("A", raw="0.20", uniq="0.13"), _term("B", raw="0.20", uniq="0.13")], "0.25")
    assert _one(_run(uniq), "B7")["reasons"] == []  # 0.26 against 0.25 at a tolerance of 0.01
    pri = _fit([_term("A", cons="0.81", pri="0.815")])
    assert _one(_run(pri), "B7")["reasons"] == []  # 0.815 against 0.81 at 0.005


def test_zero_denominators_and_split_unclear_are_not_computable():
    split = _one(_run(_fit([_term("A", raw="0.30", uniq="0.30")], "0.90", split_unclear=True)), "B7")
    assert split["status"] == "not_computable" and split["reasons"] == []
    missing = _one(_run(_fit([_term("A", raw="0.30"), _term("B", raw=None)], "0.50")), "B7")
    assert missing["status"] == "not_computable"
    mem = {"id": "m", "kind": "memberships", "source": "Appendix", "sets": ["A", "Y"], "outcome": "Y",
           "conditions": ["A"], "compare": ["fit"],
           "cases": [{"A": "0", "Y": "0.40"}, {"A": "0.00", "Y": "0.70"}]}
    r = _one([x for x in _run(_fit([_term("A", cons="0.50")]), mem) if x["id"] == "m"], "B7")
    assert r["status"] == "not_computable" and "can reach zero" in r["message"]


def test_logical_rows_and_least_remainder_share():
    mv = {"id": "d", "kind": "design", "source": "p. 4", "variant": "mvQCA", "conditions": [3, 2, 2], "n_cases": 9}
    assert _one(_run(mv), "B5")["facts"]["logical_rows"] == 12
    cs = {"id": "d", "kind": "design", "source": "p. 4", "conditions": 7, "n_cases": 16}
    facts = _one(_run(cs), "B5")["facts"]
    assert facts["logical_rows"] == 128 and facts["least_remainder_share"] == "0.8750"


def test_cli_exit_codes(tmp_path):
    def run(*args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True).returncode

    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert run(str(bad), str(tmp_path / "o.json")) == 2
    obj = tmp_path / "obj.json"
    obj.write_text('{"id": "x"}', encoding="utf-8")
    assert run(str(obj), str(tmp_path / "o.json")) == 2
    nan = tmp_path / "nan.json"
    nan.write_text('[{"id": "x", "kind": "design", "source": "p", "conditions": NaN, "n_cases": 3}]',
                   encoding="utf-8")
    assert run(str(nan), str(tmp_path / "o.json")) == 2
    assert run(str(obj)) == 2
    deep = tmp_path / "deep.json"
    deep.write_text("[" * 100000, encoding="utf-8")
    assert run(str(deep), str(tmp_path / "o.json")) == 2
    good = tmp_path / "good.json"
    good.write_text(json.dumps([CASES[0][1]]), encoding="utf-8")
    assert run(str(good), str(tmp_path / "sub" / "o.json")) == 0
    out = json.loads((tmp_path / "sub" / "o.json").read_text(encoding="utf-8"))
    assert {r["check"] for r in out["results"]} == {"B6", "B7"}


def test_invalid_records_keep_the_batch():
    records = ["text", {"kind": "design"}, {"id": "a", "kind": "nope", "source": "p"},
               {"id": "b", "kind": "fit_table", "source": "p", "terms": [{"label": "A", "raw_consistency": 0.8}]},
               {"id": "c", "kind": "design", "source": "p", "conditions": 99, "n_cases": 3},
               {"id": "d", "kind": "design", "source": "p", "conditions": 3, "n_cases": 8},
               {"id": "d", "kind": "design", "source": "p", "conditions": 3, "n_cases": 8}]
    results = Q.run_records(records)
    invalid = [r for r in results if r["status"] == "invalid"]
    assert len(invalid) == 6 and all(r["message"] for r in invalid)
    assert [r["check"] for r in results if r["id"] == "d" and r["status"] == "ok"] == ["B3", "B5", "B7"]


def test_malformed_records_never_raise():
    rng = random.Random(11)
    values = [None, True, 3, -1, 2.5, "x", "0.5", "", "1e5", "0.80", "-0.2", [], {}, ["0.1"], "∞", "0" * 60]
    kinds = list(Q.KINDS) + ["other", None]
    fields = ["terms", "rows", "conditions", "n_cases", "sets", "outcome", "cases", "compare", "threshold",
              "solution_coverage", "remainder_share", "percent", "frequency_cutoff", "split_unclear"]
    for i in range(400):
        rec = {"id": f"r{i}", "kind": rng.choice(kinds), "source": "p"}
        for f in rng.sample(fields, 5):
            rec[f] = rng.choice(values + [[{"label": rng.choice(values), "raw_coverage": rng.choice(values),
                                             "n": rng.choice(values), "outcome": rng.choice(values),
                                             "condition": "A", "A": rng.choice(values)}]])
        for r in Q.run_records([rec]):
            assert r["status"] in ("ok", "invalid", "not_computable")
            json.dumps(r, allow_nan=False)


# --- recomputation from printed memberships ---

HAND = [  # (A, B, Y) printed at two decimals
    ("0.80", "0.70", "0.90"), ("0.60", "0.90", "0.40"), ("0.20", "0.80", "0.30"), ("0.90", "0.30", "0.70"),
    ("0.70", "0.60", "0.80"),
]
# Worked by hand from the section 6 formulas, for the configuration A*B (X = min(A, B)):
# X = .70 .60 .20 .30 .60 (sum 2.40); min(X, Y) = .70 .40 .20 .30 .60 (sum 2.20); Y sums to 3.10;
# min(X, Y, 1 - Y) = .10 .40 .20 .30 .20 (sum 1.20).
# Consistency 2.20 / 2.40 = 11/12; raw coverage 2.20 / 3.10 = 22/31; PRI (2.20 - 1.20) / (2.40 - 1.20) = 5/6.
# Necessity of A: min(A, Y) = .80 .40 .20 .70 .70 (sum 2.80); consistency 2.80 / 3.10 = 28/31;
# coverage 2.80 / 3.20 = 7/8.
EXACT = {"consistency": Fraction(11, 12), "coverage": Fraction(22, 31), "pri": Fraction(5, 6)}
NEC = {"consistency": Fraction(28, 31), "coverage": Fraction(7, 8)}


def _hand_memberships(compare=("fit", "nec"), cases=HAND):
    return {"id": "m", "kind": "memberships", "source": "Appendix Table A1", "sets": ["A", "B", "Y"],
            "outcome": "Y", "conditions": ["A", "B"], "compare": list(compare),
            "cases": [{"A": a, "B": b, "Y": y} for a, b, y in cases]}


def _hand_fit(cons="0.92", pri="0.83", raw="0.71"):
    return _fit([_term("A*B", cons=cons, pri=pri, raw=raw, uniq=raw)], raw, cons)


def _hand_nec(cons="0.90", cov="0.88"):
    return {"id": "nec", "kind": "necessity", "source": "Table 2", "threshold": "0.90",
            "rows": [{"condition": "A", "consistency": cons, "coverage": cov, "declared_necessary": False}]}


def _boxes(pairs):
    h = Fraction(1, 200)
    return [((max(Fraction(0), Fraction(x) - h), min(Fraction(1), Fraction(x) + h)),
             (max(Fraction(0), Fraction(y) - h), min(Fraction(1), Fraction(y) + h))) for x, y in pairs]


def _xy():
    return [(min(Decimal(a), Decimal(b)), Decimal(y)) for a, b, y in HAND]


def test_hand_example_point_values():
    xs = [Fraction(x) for x, _ in _xy()]
    ys = [Fraction(y) for _, y in _xy()]
    for kind, value in EXACT.items():
        assert Q._point(xs, ys, kind) == value, kind
    a = [Fraction(Decimal(r[0])) for r in HAND]
    assert Q._point(a, ys, "coverage") == NEC["consistency"] and Q._point(a, ys, "consistency") == NEC["coverage"]


def _brute(boxes, kind):
    grids = []
    for (xl, xh), (yl, yh) in boxes:
        half = Fraction(1, 2)
        xs = {v for v in (xl, xh, yl, yh, 1 - yl, 1 - yh, half) if xl <= v <= xh}
        ys = {v for v in (yl, yh, xl, xh, 1 - xl, 1 - xh, half) if yl <= v <= yh}
        grids.append([Q._nd(kind, x, y) for x in xs for y in ys])
    ratios = []
    for combo in itertools.product(*grids):
        den = sum(d for _, d in combo)
        if den:
            ratios.append(Fraction(sum(n for n, _ in combo)) / den)
    return min(ratios), max(ratios)


@pytest.mark.parametrize("kind", ["consistency", "coverage", "pri"])
def test_interval_bounds_match_brute_force(kind):
    boxes = _boxes([(str(x), str(y)) for x, y in _xy()])
    lo, hi = Q.ratio_range(boxes, kind)
    assert (lo, hi) == _brute(boxes, kind)
    assert lo <= EXACT[kind] <= hi
    rng = random.Random(5)
    for _ in range(3000):
        pts = [(xl + (xh - xl) * Fraction(rng.randint(0, 20), 20), yl + (yh - yl) * Fraction(rng.randint(0, 20), 20))
               for (xl, xh), (yl, yh) in boxes]
        v = Q._point([p[0] for p in pts], [p[1] for p in pts], kind)
        assert lo <= v <= hi


def test_reported_figures_recompute_without_mismatch():
    results = _run(_hand_fit(), _hand_nec(), _hand_memberships())
    r = _one([x for x in results if x["id"] == "m"], "B7")
    assert r["reasons"] == [] and r["status"] == "ok"
    fields = {(x["record"], x["where"], x["field"]) for x in r["facts"]["recomputed_ranges"]}
    assert fields == {("fit", "A*B", "raw_consistency"), ("fit", "A*B", "raw_coverage"), ("fit", "A*B", "pri"),
                      ("nec", "A", "consistency"), ("nec", "A", "coverage")}


@pytest.mark.parametrize("field", ["cons", "pri", "raw"])
def test_misreport_of_005_fires(field):
    good = {"cons": "0.92", "pri": "0.83", "raw": "0.71"}
    good[field] = str(Decimal(good[field]) + Decimal("0.05"))
    results = _run(_hand_fit(**good), _hand_nec(), _hand_memberships())
    r = _one([x for x in results if x["id"] == "m"], "B7")
    assert r["reasons"] == ["recomputed_mismatch"] and r["flag"] is True
    assert len(r["facts"]["violations"]) == 1


def test_necessity_misreport_fires():
    results = _run(_hand_fit(), _hand_nec(cons="0.95"), _hand_memberships())
    r = _one([x for x in results if x["id"] == "m"], "B7")
    assert [v["field"] for v in r["facts"]["violations"]] == ["consistency"]


def test_unique_and_solution_figures_are_facts_only():
    fit = _fit([_term("A*B", cons="0.92", pri="0.83", raw="0.71", uniq="0.30"),
                _term("~A*B", cons="0.40", pri="0.10", raw="0.33", uniq="0.05")], "0.99", "0.20")
    results = _run(fit, _hand_memberships(compare=("fit",)))
    r = _one([x for x in results if x["id"] == "m"], "B7")
    assert all(v["where"] != "solution" for v in r["facts"].get("violations", []))
    facts = r["facts"]["at_printed_values:fit"]
    assert set(facts["unique_coverage"]) == {"A*B", "~A*B"} and facts["solution_coverage"]


def test_crisp_outcome_gets_no_separate_pri():
    cases = [("1", "1", "1"), ("1", "0", "0"), ("0", "1", "1"), ("1", "1", "1"), ("0", "0", "0")]
    fit = _fit([_term("A*B", cons="1.00", pri=None, raw="0.67", uniq="0.67")], "0.67", "1.00", crisp_outcome=True)
    r = _one([x for x in _run(fit, _hand_memberships(("fit",), cases)) if x["id"] == "m"], "B7")
    assert r["reasons"] == []
    assert {x["field"] for x in r["facts"]["recomputed_ranges"]} == {"raw_consistency", "raw_coverage"}


def test_headline_below_floor_is_reported():
    cases = [("0.80", "0.70", "0.20"), ("0.60", "0.90", "0.40"), ("0.20", "0.80", "0.30"),
             ("0.90", "0.30", "0.70"), ("0.70", "0.60", "0.80")]
    fit = _fit([_term("A*B", cons="0.76", pri="0.52", raw="0.70", headline=True)], None)
    r = _one([x for x in _run(fit, _hand_memberships(("fit",), cases)) if x["id"] == "m"], "B7")
    assert r["facts"]["recomputed_pri_below_floor"][0]["term"] == "A*B"
    assert r["facts"]["recomputed_consistency_below_floor"][0]["floor"] == "0.75"


# --- records ---

def _mem_rows(values, **extra):
    rec = {"id": "m", "kind": "memberships", "source": "Table A1", "sets": ["A", "B", "Y"], "outcome": "Y",
           "conditions": ["A", "B"], "cases": [{"A": a, "B": b, "Y": y} for a, b, y in values]}
    rec.update(extra)
    return rec


def test_printed_half_is_row_unknown():
    rows = [("0.50", "0.80", "0.70"), ("0.500", "0.80", "0.70"), ("0.90", "0.10", "0.60"), ("0.90", "0.20", "0.20")]
    r = _run(_mem_rows(rows))
    b3 = _one(r, "B3")["facts"]
    assert b3["printed_half_row_unknown"] == {"A": 1}
    assert b3["cases_left_out"] == {"row_unknown": 1, "at_exactly_half": 1}
    assert b3["observed_rows"] == {"A*~B": 2} and b3["cases_in_rows"] == 2
    stated = _one(_run(_mem_rows(rows, states_half=True)), "B3")["facts"]
    assert stated["cases_left_out"] == {"row_unknown": 0, "at_exactly_half": 2}
    assert _one(r, "B4")["facts"]["share_above_half"] == {"A": "0.5000", "B": "0.5000", "Y": "0.7500"}


def test_truth_table_coding_flags_and_facts():
    rows = [{"n": 5, "raw_consistency": "0.78", "pri": "0.70", "outcome": 1},
            {"n": 4, "raw_consistency": "0.91", "pri": "0.85", "outcome": 0},
            {"n": 1, "raw_consistency": "0.95", "pri": "0.90", "outcome": "remainder"},
            {"n": 3, "raw_consistency": None, "pri": None, "outcome": "remainder"},
            {"n": 2, "raw_consistency": "0.85", "pri": "0.40", "outcome": "C"}]
    rec = {"id": "t", "kind": "truth_table", "source": "Table 4", "consistency_cutoff": "0.80", "pri_cutoff": "0.70",
           "frequency_cutoff": 2, "n_cases": 20, "complete": True, "rows": rows}
    results = _run(rec)
    b6 = _one(results, "B6")
    assert b6["reasons"] == ["row_coded_against_cutoff"]
    assert b6["facts"]["rows_coded_0_meeting_every_cutoff"] == ["row 2"]
    b3 = _one(results, "B3")["facts"]
    assert b3["cases_in_table"] == 15 and b3["cases_short_of_n"] == 5
    gap = dict(rec, consistency_gap=True)
    b6gap = _one(_run(gap), "B6")
    assert b6gap["reasons"] == [] and "rows_coded_0_meeting_every_cutoff" not in b6gap["facts"]


def test_truth_table_pri_checks_and_case_count():
    rows = [{"n": 12, "raw_consistency": "0.84", "pri": "0.46", "outcome": 1},
            {"n": 10, "raw_consistency": "0.70", "pri": "0.76", "outcome": 0}]
    results = _run({"id": "t", "kind": "truth_table", "source": "Table 4", "n_cases": 20, "rows": rows})
    assert _one(results, "B6")["reasons"] == ["pri_below_half"]
    assert _one(results, "B7")["reasons"] == ["pri_exceeds_consistency"]
    assert _one(results, "B3")["reasons"] == ["cases_exceed_n"]


def test_remainder_share_definitions():
    base = {"id": "d", "kind": "design", "source": "p. 8", "conditions": 6, "n_cases": 180, "observed_rows": 40,
            "rows_kept": 16}
    assert _one(_run(dict(base, remainder_share="37.5", percent=True)), "B5")["reasons"] == []
    kept = _one(_run(dict(base, remainder_share="75", percent=True)), "B5")
    assert kept["reasons"] == [] and kept["facts"]["remainder_share_matches"] == ["rows_kept"]
    assert _one(_run(dict(base, remainder_share="0.90")), "B5")["reasons"] == ["remainder_share_mismatch"]
    one = dict(base, remainder_share="0.90")
    del one["rows_kept"]
    r = _one(_run(one), "B5")
    assert r["reasons"] == [] and r["facts"]["remainder_share_unmatched"]["compared_with"] == ["observed_rows"]
    whole = {"id": "d", "kind": "design", "source": "p. 8", "conditions": 6, "n_cases": 30, "observed_rows": 6,
             "rows_kept": 4, "remainder_share": "91", "percent": True}  # 1 - 6/64 = 90.625 percent
    assert _one(_run(whole), "B5")["reasons"] == []
    wide = dict(whole, conditions=8, n_cases=150, observed_rows=38, rows_kept=20, remainder_share="85")
    assert _one(_run(wide), "B5")["reasons"] == []  # 1 - 38/256 = 85.16 percent
    assert _one(_run(dict(whole, remainder_share="89")), "B5")["reasons"] == ["remainder_share_mismatch"]


def test_configuration_shared_with_the_negated_outcome_is_a_fact():
    pres = _fit([_term("A*B*~C", cons="0.85", raw="0.40"), _term("D", cons="0.90", raw="0.30")], "0.55",
                rid="pres", outcome="presence")
    absn = _fit([_term("A*B", cons="0.82", raw="0.35")], "0.35", rid="abs", outcome="absence")
    results = _run(pres, absn)
    b6 = _one([r for r in results if r["id"] == "pres"], "B6")
    assert b6["facts"]["in_negated_solution"] == [{"term": "A*B*~C", "negated_record": "abs", "negated_term": "A*B"}]
    assert b6["flag"] is False


def test_necessity_threshold_source():
    rec = {"id": "n", "kind": "necessity", "source": "Table 2", "threshold": None,
           "rows": [{"condition": "A", "consistency": "0.88", "coverage": "0.60", "declared_necessary": True},
                    {"condition": "B", "negated": True, "consistency": "0.60", "coverage": "0.50",
                     "declared_necessary": False}]}
    r = _one(_run(rec), "B8")
    assert r["reasons"] == ["necessary_below_threshold"]
    assert r["facts"]["violations"][0]["threshold_source"] == "convention 0.90"


# --- generated correct papers raise no flag ---

def _gen(rng, n, crisp, places, rounding):
    q = Decimal(1).scaleb(-places)

    def pr(v):
        return str((Decimal(v.numerator) / Decimal(v.denominator)).quantize(q, rounding=rounding))

    conds = ["A", "B", "C", "D"]
    cases = []
    for _ in range(n):
        if crisp:
            row = {c: Fraction(rng.randint(0, 1)) for c in conds}
            row["Y"] = Fraction(1) if (row["A"] and row["B"]) or rng.random() < 0.3 else Fraction(0)
        else:
            row = {c: Fraction(rng.randint(1, 999999), 1000000) for c in conds}
            row["Y"] = min(Fraction(999999, 1000000), max(Fraction(1, 1000000),
                                                            (row["A"] + row["B"]) / 2 + Fraction(rng.randint(-2, 2), 10)))
            for k in list(row):
                if row[k] == Fraction(1, 2):
                    row[k] += Fraction(1, 1000000)
        cases.append(row)
    ys = [c["Y"] for c in cases]

    def xs_of(lits):
        return [min(1 - c[nm] if neg else c[nm] for neg, nm in lits) for c in cases]

    terms = []
    for _ in range(12):
        lits = frozenset((rng.random() < 0.3, nm) for nm in rng.sample(conds, rng.randint(1, 3)))
        xs = xs_of(lits)
        if sum(xs) == 0 or lits in [t[0] for t in terms]:
            continue
        pri = Q._point(xs, ys, "pri")
        if pri is not None and pri >= Fraction(1, 2):
            terms.append((lits, xs))
        if len(terms) == 3:
            break
    if not terms:
        return None
    sol = [max(col) for col in zip(*[t[1] for t in terms])]
    sol_cov = Q._point(sol, ys, "coverage")
    fterms = []
    for lits, xs in terms:
        rest = [max(col) for col in zip(*[t[1] for t in terms if t[1] is not xs])] if len(terms) > 1 else [0] * n
        label = "*".join(("~" if neg else "") + nm for neg, nm in sorted(lits, key=lambda x: x[1]))
        fterms.append({"label": label, "raw_consistency": pr(Q._point(xs, ys, "consistency")),
                       "pri": None if crisp else pr(Q._point(xs, ys, "pri")),
                       "raw_coverage": pr(Q._point(xs, ys, "coverage")),
                       "unique_coverage": pr(sol_cov - Q._point(rest, ys, "coverage"))})
    fit = {"id": "fit", "kind": "fit_table", "source": "T3", "terms": fterms, "crisp_outcome": crisp,
           "solution_consistency": pr(Q._point(sol, ys, "consistency")), "solution_coverage": pr(sol_cov)}
    nec_rows = []
    for c in conds:
        xs = [row[c] for row in cases]
        if sum(xs) == 0 or sum(ys) == 0:
            continue
        cons = Q._point(xs, ys, "coverage")
        nec_rows.append({"condition": c, "consistency": pr(cons), "coverage": pr(Q._point(xs, ys, "consistency")),
                         "declared_necessary": cons >= Fraction(9, 10)})
    nec = {"id": "nec", "kind": "necessity", "source": "T2", "threshold": "0.90", "rows": nec_rows}
    counts = {}
    for row in cases:
        key = tuple(int(row[c] > Fraction(1, 2)) for c in conds)
        counts[key] = counts.get(key, 0) + 1
    tt_rows = []
    for key, k in counts.items():
        xs = [min(row[c] if bit else 1 - row[c] for c, bit in zip(conds, key)) for row in cases]
        cons = Q._point(xs, ys, "consistency")
        pri = None if crisp else Q._point(xs, ys, "pri")
        coded = 1 if cons >= Fraction(4, 5) and (pri is None or pri >= Fraction(1, 2)) else 0
        tt_rows.append({"n": k, "raw_consistency": pr(cons), "pri": None if pri is None else pr(pri),
                        "outcome": "remainder" if k < 2 else coded})
    tt = {"id": "tt", "kind": "truth_table", "source": "T4", "consistency_cutoff": "0.80",
          "pri_cutoff": None if crisp else "0.50", "frequency_cutoff": 2, "n_cases": n, "complete": True,
          "crisp_outcome": crisp, "rows": tt_rows}
    kept = sum(1 for k in counts.values() if k >= 2)
    share = (1 - Fraction(rng.choice([len(counts), kept]), 16)) * 100
    design = {"id": "d", "kind": "design", "source": "p. 8", "conditions": 4, "n_cases": n, "frequency_cutoff": 2,
              "rows_kept": kept, "observed_rows": len(counts), "cases_in_truth_table": n,
              "remainder_share": str((Decimal(share.numerator) / Decimal(share.denominator)).quantize(
                  Decimal("1") if rng.random() < 0.5 else Decimal("0.1"))),
              "percent": True}
    mem = {"id": "m", "kind": "memberships", "source": "A1", "sets": conds + ["Y"], "outcome": "Y",
           "conditions": conds, "compare": ["fit", "nec"],
           "cases": [{k: (str(int(v)) if crisp else pr_m(v)) for k, v in row.items()} for row in cases]}
    return [fit, nec, tt, design, mem]


def pr_m(v):
    return str((Decimal(v.numerator) / Decimal(v.denominator)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


@pytest.mark.parametrize("crisp", [False, True])
@pytest.mark.parametrize("places", [2, 3])
def test_generated_correct_papers_raise_no_flag(crisp, places):
    rng = random.Random(1000 * places + crisp)
    tables = 0
    for i in range(40):
        n = rng.choice([12, 16, 30, 60])
        records = _gen(rng, n, crisp, places, ROUND_HALF_EVEN if i % 2 else ROUND_HALF_UP)
        if records is None:
            continue
        tables += 1
        for r in Q.run_records(records):
            assert r["status"] != "invalid", r
            assert r["flag"] is False, r
    assert tables >= 30


# --- final fix wave A: bare whole-number fit figures, floor facts, count cap ---

def _crisp_nec(both, a_only, y_only, cons, cov):
    """A crisp necessity record for A over Y and its memberships: `both` cases in A and Y, `a_only` in A
    only, `y_only` in Y only. Necessity consistency is both/(both+y_only); coverage is both/(both+a_only)."""
    nec = {"id": "nec", "kind": "necessity", "source": "Table 2", "threshold": "0.90",
           "rows": [{"condition": "A", "consistency": cons, "coverage": cov, "declared_necessary": False}]}
    cases = [{"A": "1", "Y": "1"}] * both + [{"A": "1", "Y": "0"}] * a_only + [{"A": "0", "Y": "1"}] * y_only
    mem = {"id": "m", "kind": "memberships", "source": "Table A1", "sets": ["A", "Y"], "outcome": "Y",
           "conditions": ["A"], "cases": cases, "compare": ["nec"]}
    return nec, mem


def test_bare_whole_fit_figure_has_one_decimal_half_width():
    assert Q._dec("1", "f", fit=True) == (Decimal(1), Decimal("0.05"))
    assert Q._dec("0", "f", fit=True) == (Decimal(0), Decimal("0.05"))
    assert Q._dec("1.00", "f", fit=True) == (Decimal(1), Decimal("0.005"))
    assert Q._dec("1", "f") == (Decimal(1), Decimal(0))


@pytest.mark.parametrize("both,a_only,y_only,cons,cov,flags", [
    (249, 1, 51, "0.83", "1", False),   # coverage 249/250 = 0.996, "1.00" printed "1"
    (24, 1, 6, "0.8", "1", False),      # coverage 24/25 = 0.96 beside one-decimal figures, "1.0" printed "1"
    (27, 3, 3, "0.9", "1", True),       # coverage 27/30 = 0.90 printed "1" is a misreport
])
def test_bare_whole_fit_figure_recomputes_within_its_rounding(both, a_only, y_only, cons, cov, flags):
    r = _one([x for x in _run(*_crisp_nec(both, a_only, y_only, cons, cov)) if x["id"] == "m"], "B7")
    assert r["flag"] is flags
    assert r["reasons"] == (["recomputed_mismatch"] if flags else [])


def test_bare_whole_fit_figure_beside_three_decimals_is_not_an_inversion():
    r = _one(_run(_fit([_term("A", cons="0.970", pri="1")])), "B7")
    assert r["reasons"] == []


def test_bare_membership_stays_exact():
    lo, hi, _, exact = Q._box("1", "m")
    assert (lo, hi, exact) == (Fraction(1), Fraction(1), True)


def _crisp_fit(both, a_only, y_only, cons):
    fit = {"id": "fit", "kind": "fit_table", "source": "Table 3", "outcome": "presence", "crisp_outcome": True,
           "terms": [{"label": "A", "raw_consistency": cons, "pri": None, "raw_coverage": None,
                      "unique_coverage": None, "headline": True}],
           "solution_consistency": None, "solution_coverage": None}
    cases = [{"A": "1", "Y": "1"}] * both + [{"A": "1", "Y": "0"}] * a_only + [{"A": "0", "Y": "1"}] * y_only
    mem = {"id": "m", "kind": "memberships", "source": "Table A1", "sets": ["A", "Y"], "outcome": "Y",
           "conditions": ["A"], "cases": cases, "compare": ["fit"]}
    return _one([x for x in _run(fit, mem) if x["id"] == "m"], "B7")


def test_correct_print_at_the_floor_draws_no_floor_fact():
    r = _crisp_fit(187, 63, 50, "0.75")   # 187/250 = 0.748, correctly printed "0.75"
    assert r["reasons"] == [] and "recomputed_consistency_below_floor" not in r["facts"]


def test_floor_fact_when_the_print_does_not_cover_the_recomputed_value():
    r = _crisp_fit(185, 65, 50, "0.75")   # 185/250 = 0.740 printed "0.75"
    assert r["reasons"] == ["recomputed_mismatch"]
    assert r["facts"]["recomputed_consistency_below_floor"][0]["reported"] == "0.75"
    r = _crisp_fit(187, 63, 50, "0.80")   # 0.748 printed "0.80"
    assert r["facts"]["recomputed_consistency_below_floor"][0]["recomputed_high"] == "0.7480"


def test_floor_fact_when_the_printed_value_is_itself_below_the_floor():
    r = _crisp_fit(187, 63, 50, "0.748")
    assert r["reasons"] == [] and r["facts"]["recomputed_consistency_below_floor"][0]["reported"] == "0.748"


def test_count_above_the_cap_is_an_invalid_record():
    big = 10 ** 12 + 1
    rec = {"id": "tt", "kind": "truth_table", "source": "p",
           "rows": [{"n": big, "outcome": 0, "raw_consistency": "0.1"}]}
    [r] = _run(rec)
    assert r["status"] == "invalid" and str(10 ** 12) in r["message"]
    ok = dict(rec, rows=[{"n": 10 ** 12, "outcome": 0, "raw_consistency": "0.1"}])
    assert all(r["status"] == "ok" for r in _run(ok))


def test_huge_counts_exit_cleanly(tmp_path):
    src = tmp_path / "big.json"
    src.write_text(json.dumps([{"id": "tt", "kind": "truth_table", "source": "T",
                                "rows": [{"n": int("9" * 4300), "outcome": 0, "raw_consistency": "0.1"}] * 2}]),
                   encoding="utf-8")
    p = subprocess.run([sys.executable, str(SCRIPT), str(src), str(tmp_path / "o.json")], capture_output=True,
                       text=True)
    assert p.returncode == 0 and "Traceback" not in p.stderr
    [r] = json.loads((tmp_path / "o.json").read_text(encoding="utf-8"))["results"]
    assert r["status"] == "invalid"


def test_value_error_at_write_exits_2(tmp_path, monkeypatch, capsys):
    src = tmp_path / "in.json"
    src.write_text(json.dumps([CASES[0][1]]), encoding="utf-8")

    def boom(*a, **k):
        raise ValueError("too big")

    monkeypatch.setattr(Q.json, "dumps", boom)
    assert Q.main([str(src), str(tmp_path / "o.json")]) == 2
    assert "cannot write" in capsys.readouterr().err
