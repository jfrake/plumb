from __future__ import annotations
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "packs" / "meta-analysis" / "scripts" / "ma_arith.py"
_spec = importlib.util.spec_from_file_location("ma_arith", SCRIPT)
ma = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ma)


def _one(**rec):
    rec.setdefault("id", "r1")
    rec.setdefault("page", "7")
    rec.setdefault("locator", "Results, Table 2")
    return ma.run_record(rec, set())


def test_t_quantiles():
    assert ma.t_quantile(0.975, 23) == pytest.approx(2.068658, abs=1e-6)
    assert ma.t_quantile(0.975, 1) == pytest.approx(12.706205, abs=1e-6)
    assert ma.t_quantile(0.975, 178) == pytest.approx(1.973381, abs=1e-6)
    assert ma.t_quantile(0.90, 9) == pytest.approx(1.383029, abs=1e-6)


def test_i2_from_q_and_df():
    r = _one(kind="i2", q="40.0", df=9, q_based=True)
    assert r["status"] == "info" and r["values"]["i2"] == pytest.approx(77.5)


def test_i2_mismatch():
    assert _one(kind="i2", q="40.0", df=9, q_based=True, printed_i2="85")["status"] == "mismatch"


def test_i2_within_rounding_is_ok():
    r = _one(kind="i2", q="40", df=9, q_based=True, printed_i2="77")
    assert r["status"] == "ok"
    assert r["values"]["i2_min"] == pytest.approx(77.2152, abs=1e-4)
    assert r["values"]["i2_max"] == pytest.approx(77.7778, abs=1e-4)


def test_i2_not_q_based_is_never_a_mismatch():
    r = _one(kind="i2", q="40.0", df=9, q_based=False, printed_i2="85")
    assert r["status"] == "info" and "not compared" in r["message"]


def test_i2_floor_and_df_note():
    assert _one(kind="i2", q="8.0", df=9, q_based=True)["values"]["i2"] == 0.0
    r = _one(kind="i2", q="40.0", df=9, q_based=True, k=180)
    assert "is not k - 1" in r["message"] and r["status"] == "info"


def test_prediction_interval_raw():
    r = _one(kind="prediction_interval", mean="0.10", ci=["0.07", "0.13"], tau="0.12", k=25, scale="raw")
    lo, hi = r["values"]["pi"]
    assert lo == pytest.approx(-0.150250, abs=1e-6) and hi == pytest.approx(0.350250, abs=1e-6)
    assert r["values"]["includes_zero"] == "every corner"
    assert r["values"]["lower_range"][1] == pytest.approx(-0.134354, abs=1e-6)


def test_prediction_interval_hartung_knapp():
    r = _one(kind="prediction_interval", mean="0.10", ci=["0.07", "0.13"], tau="0.12", k=25, scale="raw",
             ci_method="t_k1")
    lo, hi = r["values"]["pi"]
    assert lo == pytest.approx(-0.150053, abs=1e-6) and hi == pytest.approx(0.350053, abs=1e-6)


def test_prediction_interval_fisher_z():
    r = _one(kind="prediction_interval", mean=".10", ci=[".07", ".13"], tau=".12", k=180, k_unit="effect sizes",
             scale="fisher_z")
    lo, hi = r["values"]["pi"]
    assert lo == pytest.approx(-0.137552, abs=1e-6) and hi == pytest.approx(0.326673, abs=1e-6)
    assert r["values"]["includes_zero"] == "every corner" and r["values"]["k_unit"] == "effect sizes"


def test_prediction_interval_uses_independent_samples_as_k():
    r = _one(kind="prediction_interval", mean=".10", ci=[".07", ".13"], tau=".12", k=61, k_unit="samples",
             scale="fisher_z")
    lo, hi = r["values"]["pi"]
    assert lo == pytest.approx(-0.140828, abs=1e-6) and hi == pytest.approx(0.329655, abs=1e-6)
    assert r["values"]["k_used"] == 61


def test_rounding_box_keeps_a_printed_pi_that_the_digits_allow():
    r = _one(kind="prediction_interval", mean=".20", ci=[".16", ".24"], tau=".04", k=12, scale="fisher_z",
             printed_pi=[".10", ".29"])
    lo, hi = r["values"]["pi"]
    assert lo == pytest.approx(0.101437, abs=1e-6) and hi == pytest.approx(0.294675, abs=1e-6)
    assert r["status"] == "ok" and r["values"]["includes_zero"] == "none"


def test_prediction_interval_small_k():
    r = _one(kind="prediction_interval", mean="0.10", ci=["0.07", "0.13"], tau="0.12", k=2, scale="raw")
    assert r["status"] == "not_computable"


def test_credibility_interval_z():
    r = _one(kind="credibility_interval", rho=".20", sd_rho=".10")
    lo, hi = r["values"]["z_interval"]
    assert lo == pytest.approx(0.071845, abs=1e-6) and hi == pytest.approx(0.328155, abs=1e-6)
    assert "t_interval" not in r["values"]


def test_credibility_matches_either_method():
    r = _one(kind="credibility_interval", rho=".20", sd_rho=".10", k=10)
    lo, hi = r["values"]["t_interval"]
    assert lo == pytest.approx(0.061697, abs=1e-6) and hi == pytest.approx(0.338303, abs=1e-6)
    assert _one(kind="credibility_interval", rho=".20", sd_rho=".10", k=10, printed=[".06", ".34"])["status"] == "ok"
    assert _one(kind="credibility_interval", rho=".20", sd_rho=".10", k=10, printed=[".07", ".33"])["status"] == "ok"
    assert _one(kind="credibility_interval", rho=".20", sd_rho=".10", k=10, printed=[".09", ".31"])["status"] == "mismatch"


def test_dependence_bound_excludes_zero():
    r = _one(kind="dependence_bound", mean=".10", ci=[".07", ".13"], n_es=180, n_samples=61, scale="fisher_z")
    lo, hi = r["values"]["bound"]
    assert lo == pytest.approx(0.048227, abs=1e-6) and hi == pytest.approx(0.151237, abs=1e-6)
    assert r["values"]["includes_zero"] == "none" and r["status"] == "info"


def test_dependence_bound_includes_zero():
    r = _one(kind="dependence_bound", mean=".05", ci=[".01", ".09"], n_es=40, n_samples=12, scale="fisher_z")
    lo, hi = r["values"]["bound"]
    assert lo == pytest.approx(-0.023206, abs=1e-6) and hi == pytest.approx(0.122673, abs=1e-6)
    assert r["values"]["includes_zero"] == "every corner"


def test_conversions():
    r = _one(kind="convert", **{"from": "d", "to": "r", "value": "0.50"})
    assert r["values"]["result"] == pytest.approx(0.242536, abs=1e-6) and "assumes equal groups" in r["message"]
    r = _one(kind="convert", n1=30, n2=70, **{"from": "d", "to": "r", "value": "0.50"})
    assert r["values"]["result"] == pytest.approx(0.223341, abs=1e-6)
    assert _one(kind="convert", **{"from": "r", "to": "d", "value": "0.30"})["values"]["result"] == pytest.approx(0.628971, abs=1e-6)
    assert _one(kind="convert", **{"from": "or", "to": "d", "value": "2.0"})["values"]["result"] == pytest.approx(0.382152, abs=1e-6)


def test_t_to_r_with_wrong_df_is_a_mismatch():
    r = _one(kind="convert", df=98, printed=".243", **{"from": "t", "to": "r", "value": "2.50"})
    assert r["values"]["result"] == pytest.approx(0.244851, abs=1e-6) and r["status"] == "mismatch"
    r = _one(kind="convert", df=98, printed=".245", from_model_with_controls=True, **{"from": "t", "to": "r", "value": "2.50"})
    assert r["status"] == "ok" and "partial correlation" in r["message"]


def test_attenuation():
    r = _one(kind="attenuation", r_obs=".10", rxx=".70", ryy="1.00", printed_rho=".12")
    assert r["values"]["rho"] == pytest.approx(0.119523, abs=1e-6) and r["status"] == "ok"


FLOW = dict(kind="flow", identified="1,480", duplicates_removed="276", screened="1,204", excluded_screening="1,050",
            assessed_full_text="164", excluded_full_text={"no correlation reported": "60", "not an employee sample": "43"},
            included="61", included_unit="samples", k_analyzed="61", k_unit="samples")


def test_flow_finds_the_one_broken_step():
    r = _one(**FLOW)
    assert r["status"] == "mismatch"
    bad = [s for s in r["values"]["steps"] if s["status"] == "mismatch"]
    assert len(bad) == 1 and bad[0]["expected"] == 154 and bad[0]["printed"] == 164


def test_flow_units_differ_is_info():
    r = _one(**dict(FLOW, assessed_full_text="154", included="51", included_unit="articles"))
    last = r["values"]["steps"][-1]
    assert last["status"] == "info" and "not compared" in last["message"]
    assert r["status"] == "ok"


def test_flow_counts_other_sources_and_removals():
    r = _one(**dict(FLOW, removed_other={"automation tools": "20"}, screened="1,184", excluded_screening="1,030",
                    assessed_full_text="154", other_sources_included="10", included="61"))
    assert r["status"] == "ok"


def test_cell_n():
    r = _one(kind="cell_n", cell_ns=[900, 1500, 2400, 3000, 4200, 6000, 9000, 12000, 36000, 45000],
             cell_ks=[3, 60], used_n="12000")
    v = r["values"]
    assert v["arithmetic_mean"] == 12000 and v["harmonic_mean"] == pytest.approx(3147.64, abs=0.01)
    assert v["median"] == 5100 and v["used_n_matches"] == ["arithmetic mean"] and r["status"] == "info"


def test_study_table():
    rec = dict(kind="study_table", n=["2,412", "2,412", "2,412", "400"], r=[".10", ".12", ".08", ".30"],
               labels=["S1", "S2", "S3", "S4"], years=["2009-2014"] * 3 + ["2016"],
               sources=["National Workplace Panel"] * 3 + ["own survey"], printed_k="4", printed_total_n="7,636")
    r = _one(**rec)
    assert r["status"] == "ok" and r["values"]["shared_rows"] == [["S1", "S2", "S3"]]
    assert r["values"]["largest_share"] == pytest.approx(0.3159, abs=1e-4)
    assert _one(**dict(rec, printed_k="5"))["status"] == "mismatch"


def test_bad_record_and_verdict():
    seen = set()
    results = [ma.run_record({"id": "a", "kind": "i2", "page": "3", "locator": "x", "df": 9, "q_based": True}, seen),
               ma.run_record({"id": "b", "kind": "i2", "page": "3", "locator": "x", "q": "40.0", "df": 9,
                              "q_based": True, "printed_i2": "85"}, seen),
               ma.run_record({"id": "b", "kind": "i2", "page": "3", "locator": "x", "q": "4", "df": 2,
                              "q_based": True}, seen)]
    assert [r["status"] for r in results] == ["input_error", "mismatch", "input_error"]
    assert "duplicate id" in results[2]["message"]
    assert ma.verdict(results) == "INPUT_ERRORS_PRESENT"
    assert ma.verdict(results[1:2]) == "MISMATCHES_FOUND" and ma.verdict([]) == "NO_CHECKS"


def test_cli_writes_report_and_json(tmp_path):
    src = tmp_path / "in.json"
    src.write_text(json.dumps([dict(FLOW, id="flow", page="5", locator="Figure 1")]))
    out = tmp_path / "ma_arith.md"
    p = subprocess.run([sys.executable, str(SCRIPT), str(src), str(out)], capture_output=True, text=True)
    assert p.returncode == 0 and "VERDICT: MISMATCHES_FOUND" in p.stdout
    assert out.read_text().startswith("VERDICT: MISMATCHES_FOUND")
    assert json.loads((tmp_path / "ma_arith.json").read_text())[0]["status"] == "mismatch"


def test_cli_bad_file_exits_2(tmp_path):
    src = tmp_path / "in.json"
    src.write_text("not json")
    out = tmp_path / "ma_arith.md"
    p = subprocess.run([sys.executable, str(SCRIPT), str(src), str(out)], capture_output=True, text=True)
    assert p.returncode == 2 and not out.exists()
    src.write_text("{}")
    assert subprocess.run([sys.executable, str(SCRIPT), str(src), str(out)]).returncode == 2


# --- Preflight C7 to C11: records the script cannot use, decimal commas, PI conventions, flow layouts ---

GOOD = {"id": "good", "kind": "i2", "page": "3", "locator": "x", "q": "40.0", "df": 9, "q_based": True}
BAD = {
    "or_zero": {"kind": "convert", "from": "or", "to": "d", "value": "0"},
    "r_one_to_d": {"kind": "convert", "from": "r", "to": "d", "value": "1.00"},
    "fisher_z_mean_one": {"kind": "prediction_interval", "mean": "1.00", "ci": [".90", "1.00"], "tau": ".1",
                          "k": 10, "scale": "fisher_z"},
    "k_too_large": {"kind": "prediction_interval", "mean": ".1", "ci": [".07", ".13"], "tau": ".12",
                    "k": 10 ** 400, "scale": "raw"},
    "n_es_too_large": {"kind": "dependence_bound", "mean": ".1", "ci": [".07", ".13"], "n_es": 10 ** 400,
                       "n_samples": 61, "scale": "raw"},
    "tau_overflows": {"kind": "prediction_interval", "mean": ".1", "ci": [".07", ".13"], "tau": "1e300", "k": 10,
                      "scale": "raw"},
    "nan_string": {"kind": "attenuation", "r_obs": "nan", "rxx": ".7", "ryy": "1"},
    "inf_string": {"kind": "i2", "q": "inf", "df": 9, "q_based": True, "printed_i2": "80"},
    "kind_not_text": {"kind": ["i2"]},
    "years_not_text": {"kind": "study_table", "n": ["10", "10"], "years": [[1], [1]]},
    "total_n_zero": {"kind": "study_table", "n": ["0", "0"]},
}


def _strict(text):
    def no_constant(name):
        raise ValueError(name)
    return json.loads(text, parse_constant=no_constant)


@pytest.mark.parametrize("name", sorted(BAD))
def test_cli_reports_bad_records_and_keeps_the_batch(tmp_path, name):
    src = tmp_path / "in.json"
    src.write_text(json.dumps([GOOD, dict(BAD[name], id=name, page="3", locator="x")]))
    out = tmp_path / "ma_arith.md"
    p = subprocess.run([sys.executable, str(SCRIPT), str(src), str(out)], capture_output=True, text=True)
    assert p.returncode == 0 and "Traceback" not in p.stderr, p.stderr
    results = _strict((tmp_path / "ma_arith.json").read_text())
    assert results[0]["status"] == "info" and results[0]["values"]["i2"] == pytest.approx(77.5)
    assert results[1]["status"] == "input_error" and results[1]["id"] == name and results[1]["message"]


def test_non_finite_json_exits_2(tmp_path):
    src = tmp_path / "in.json"
    src.write_text('[{"id": "a", "page": "1", "locator": "x", "kind": "attenuation", "r_obs": NaN, "rxx": 0.7, '
                   '"ryy": 1}]')
    out = tmp_path / "ma_arith.md"
    p = subprocess.run([sys.executable, str(SCRIPT), str(src), str(out)], capture_output=True, text=True)
    assert p.returncode == 2 and not out.exists()


@pytest.mark.parametrize("value", ["40,0", "0,712"])
def test_decimal_comma_is_an_input_error(value):
    r = _one(kind="i2", q=value, df=9, q_based=True)
    assert r["status"] == "input_error" and "comma" in r["message"]
    assert _one(kind="flow", identified="1,480", duplicates_removed="276", screened="1,204")["status"] == "ok"


def test_printed_pi_from_z_or_t_k1_is_ok():
    rec = dict(kind="prediction_interval", mean=".200", ci=[".160", ".240"], tau=".040", k=12, scale="fisher_z")
    r = _one(**rec, printed_pi=[".113", ".284"])
    assert r["status"] == "ok" and r["values"]["printed_matches"] == ["z"]
    lo, hi = r["values"]["pi"]
    assert lo == pytest.approx(0.101437, abs=1e-6) and hi == pytest.approx(0.294675, abs=1e-6)
    assert r["values"]["pi_z"][0] == pytest.approx(0.113446, abs=1e-6)
    r = _one(**rec, printed_pi=[".103", ".294"])
    assert r["status"] == "ok" and "t_k1" in r["values"]["printed_matches"]
    assert _one(**rec, printed_pi=[".13", ".27"])["status"] == "mismatch"


def test_flow_accepts_the_prisma_2009_layout():
    r = _one(kind="flow", identified="1,480", other_sources_identified="50", duplicates_removed="276",
             screened="1,254", excluded_screening="1,090", assessed_full_text="164",
             excluded_full_text={"no correlation reported": "103"}, included="61", included_unit="articles",
             k_analyzed="70", k_unit="samples")
    assert r["status"] == "ok" and "PRISMA 2009" in r["message"]
    assert r["values"]["steps"][0]["expected"] == 1254


def test_flow_does_not_compare_samples_with_full_text_reports():
    r = _one(kind="flow", identified="1,480", duplicates_removed="276", screened="1,204", excluded_screening="1,040",
             assessed_full_text="164", excluded_full_text={"no correlation reported": "103"}, included="70",
             included_unit="samples", k_analyzed="70", k_unit="samples")
    assert r["status"] == "ok"
    assert r["values"]["steps"][2]["status"] == "info" and "not compared" in r["values"]["steps"][2]["message"]


def test_skipped_corners_are_reported():
    r = _one(kind="prediction_interval", mean=".10", ci=[".10", ".10"], tau=".12", k=10, scale="raw")
    assert r["values"]["corners_skipped"] > 0 and "left out" in r["message"]
    assert r["values"]["includes_zero"] == "every computable corner"


# --- Fix round 1: zero-clipped boxes, exponent half-widths, safe echoes, reports unit, file errors ---

def test_printed_zero_tau2_box_is_clipped_at_zero():
    r = _one(kind="prediction_interval", mean=".20", ci=[".16", ".24"], tau2="0.00", k=12, scale="fisher_z",
             printed_pi=[".16", ".24"])
    assert r["status"] == "ok" and "z" in r["values"]["printed_matches"]
    assert r["values"]["corners_skipped"] == 0


def test_printed_zero_tau2_reads_zero_correctly():
    r = _one(kind="prediction_interval", mean="0.03", ci=["0.00", "0.06"], tau2="0.00", k=12, scale="raw")
    assert r["values"]["corners_skipped"] == 0
    assert r["values"]["includes_zero"] == "some corners"
    t = _one(kind="prediction_interval", mean="0.03", ci=["0.00", "0.06"], tau="0.00", k=12, scale="raw")
    assert t["values"]["includes_zero"] == "some corners" and t["values"]["corners_skipped"] == 0


def test_printed_zero_sd_rho_box_is_clipped_at_zero():
    r = _one(kind="credibility_interval", rho=".20", sd_rho=".00", printed=[".20", ".20"])
    assert r["status"] == "ok" and r["values"]["corners_skipped"] == 0
    assert r["values"]["z_lower_range"][1] == pytest.approx(0.205, abs=1e-6)


@pytest.mark.parametrize("key", ["tau", "tau2", "sd_rho"])
def test_negative_spread_is_an_input_error(key):
    if key == "sd_rho":
        r = _one(kind="credibility_interval", rho=".20", sd_rho="-.10")
    else:
        r = _one(kind="prediction_interval", mean=".10", ci=[".07", ".13"], k=10, scale="raw", **{key: "-.01"})
    assert r["status"] == "input_error" and key in r["message"]


@pytest.mark.parametrize("text,half", [("1.2e-3", 5e-5), ("2.5e3", 50.0), ("4.37E-03", 5e-6), ("12", 0.5)])
def test_half_width_honours_the_exponent(text, half):
    assert ma._num({"x": text}, "x")[1] == pytest.approx(half)


def test_scientific_tau2_is_not_a_false_mismatch():
    r = _one(kind="prediction_interval", mean="0.10", ci=["0.07", "0.13"], tau2="1.2e-3", k=20, scale="raw",
             printed_pi=["0.02", "0.18"])
    assert r["status"] == "ok" and r["values"]["includes_zero"] == "none"


@pytest.mark.parametrize("bad", ['"page": 1e400', '"page": [".07", 1e400]', '"kind": {"a": 1e400}',
                                 '"id": 1e400', '"locator": -1e400'])
def test_non_finite_echo_fields_never_break_the_batch(tmp_path, bad):
    good = json.dumps(GOOD)
    fields = {"id": '"b"', "kind": '"i2"', "page": '"3"', "locator": '"x"'}
    key = bad.split('"')[1]
    fields[key] = bad.split(": ", 1)[1]
    rec = "{" + ", ".join(f'"{k}": {v}' for k, v in fields.items()) + "}"
    src = tmp_path / "in.json"
    src.write_text(f"[{good}, {rec}]")
    out = tmp_path / "ma_arith.md"
    p = subprocess.run([sys.executable, str(SCRIPT), str(src), str(out)], capture_output=True, text=True)
    assert p.returncode == 0 and "Traceback" not in p.stderr, p.stderr
    results = _strict((tmp_path / "ma_arith.json").read_text())
    assert results[0]["status"] == "info" and results[1]["status"] == "input_error"
    assert results[1][key] is None


PRISMA_2020 = dict(kind="flow", identified="2,517", duplicates_removed="676", screened="1841",
                   excluded_screening="45", not_retrieved="1", assessed_full_text="1,795",
                   excluded_full_text={"a": "249", "b": "266"})


def test_flow_included_in_studies_is_not_compared():
    r = _one(**PRISMA_2020, included="1,270", included_unit="studies")
    assert r["status"] == "ok"
    assert r["values"]["steps"][2]["status"] == "info" and "not compared" in r["values"]["steps"][2]["message"]


def test_flow_accepts_reports_as_a_unit():
    assert "reports" in ma.UNITS
    r = _one(**PRISMA_2020, included="1,280", included_unit="reports")
    assert r["status"] == "ok" and r["values"]["steps"][2]["status"] == "ok"
    assert _one(**PRISMA_2020, included="1,270", included_unit="reports")["status"] == "mismatch"
    assert _one(**PRISMA_2020, included="1,270", included_unit="articles")["status"] == "mismatch"


def test_deeply_nested_json_exits_2(tmp_path):
    src = tmp_path / "in.json"
    src.write_text("[" * 200000 + "]" * 200000)
    out = tmp_path / "ma_arith.md"
    p = subprocess.run([sys.executable, str(SCRIPT), str(src), str(out)], capture_output=True, text=True)
    assert p.returncode == 2 and "Traceback" not in p.stderr and not out.exists()


def test_unwritable_output_exits_2(tmp_path):
    src = tmp_path / "in.json"
    src.write_text(json.dumps([GOOD]))
    out = src / "ma_arith.md"
    p = subprocess.run([sys.executable, str(SCRIPT), str(src), str(out)], capture_output=True, text=True)
    assert p.returncode == 2 and "Traceback" not in p.stderr and "MA_ARITH" in p.stdout


# --- Task 4 fix round 1 ---

def _run_many(recs):
    seen = set()
    return ma.resolve_groups(recs, [ma.run_record(r, seen) for r in recs])


def _base(rid, **rec):
    return dict(rec, id=rid, page="7", locator="Table 2")


def test_i2_percent_sign_and_proportion_forms():
    assert _one(kind="i2", q="40.0", df=19, q_based=True, printed_i2="52.5%")["status"] == "ok"
    assert _one(kind="i2", q="40.0", df=19, q_based=True, printed_i2="0.525",
                printed_i2_form="proportion")["status"] == "ok"
    assert _one(kind="i2", q="40.0", df=19, q_based=True, printed_i2="0.525",
                printed_i2_form="percent")["status"] == "mismatch"
    assert _one(kind="i2", q="40.0", df=19, q_based=True, printed_i2="0.525",
                printed_i2_form="ratio")["status"] == "input_error"


def test_i2_proportion_form_with_percent_value_is_input_error():
    for printed in ("52.5", "52.5%", "0.525%", "1.2"):
        r = _one(kind="i2", q="40.0", df=19, q_based=True, printed_i2=printed, printed_i2_form="proportion")
        assert r["status"] == "input_error", printed
        assert "proportion" in r["message"]
    assert _one(kind="i2", q="40.0", df=19, q_based=True, printed_i2="1.00",
                printed_i2_form="proportion")["status"] == "mismatch"


def test_i2_tau2_based_printed_is_not_compared():
    r = _one(kind="i2", q="40.00", df=19, q_based=False, printed_i2="70.3")
    assert r["status"] == "info"


def test_alt_group_reports_mismatch_only_when_all_mismatch():
    common = dict(kind="prediction_interval", mean=".300", ci=[".250", ".350"], tau=".150", k=20,
                  alt_group="tau-scale")
    raw = _base("raw", scale="raw", printed_pi=["-0.020", "0.620"], **common)
    fz = _base("fz", scale="fisher_z", printed_pi=["-0.020", "0.620"], **common)
    a, b = _run_many([raw, fz])
    assert a["status"] == "ok" and b["status"] == "info" and "raw" in b["message"]
    bad = _run_many([dict(raw, printed_pi=["0.1", "0.2"]), dict(fz, printed_pi=["0.1", "0.2"])])
    assert [x["status"] for x in bad] == ["mismatch", "mismatch"]
    assert _run_many([dict(raw, printed_pi=["0.1", "0.2"])])[0]["status"] == "mismatch"
    assert _run_many([dict(raw, alt_group=3)])[0]["status"] == "input_error"


def test_alt_group_on_k_alternatives():
    common = dict(kind="prediction_interval", mean=".300", se=".025", tau=".150", scale="raw", alt_group="k")
    t3 = _base("a", k=5, k_unit="samples", **common)
    t18 = _base("b", k=20, k_unit="effect sizes", **common)
    printed = _one(**dict(t18, printed_pi=["-0.0197", "0.6197"]))
    assert printed["status"] in ("ok", "mismatch")
    res = _run_many([dict(t3, printed_pi=["-0.30", "0.90"]), dict(t18, printed_pi=[str(printed["values"]["pi"][0]),
                                                                              str(printed["values"]["pi"][1])])])
    assert res[0]["status"] == "info" and res[1]["status"] == "ok"


def test_flow_removed_other_accepts_count_or_list_and_sums():
    base = dict(kind="flow", identified="1000", duplicates_removed="100", screened="880")
    assert _one(removed_other=[15, "5"], **base)["status"] == "ok"
    assert _one(removed_other="20", **base)["status"] == "ok"
    assert _one(removed_other={"automation": 15, "other": 5}, **base)["status"] == "ok"
    assert _one(removed_other=[15], **base)["status"] == "mismatch"
    assert _one(removed_other="x", **base)["status"] == "input_error"


def test_prediction_interval_level():
    common = dict(kind="prediction_interval", mean=".200", se=".050", tau=".100", k=20, scale="raw")
    at95 = _one(**common)["values"]["pi"]
    at80 = _one(pi_level="0.80", **common)
    assert at80["values"]["pi"][0] > at95[0]
    lo, hi = at80["values"]["pi"]
    assert _one(pi_level="0.80", printed_pi=[f"{lo:.3f}", f"{hi:.3f}"], **common)["status"] == "ok"
    assert _one(printed_pi=[f"{lo:.3f}", f"{hi:.3f}"], **common)["status"] == "mismatch"
    assert _one(pi_level="1.2", **common)["status"] == "input_error"


def test_three_level_tau2_components_sum():
    common = dict(kind="prediction_interval", mean=".300", se=".025", k=20, scale="raw")
    whole = _one(tau2=".0225", **common)
    parts = _one(tau2=[".0100", ".0125"], **common)
    assert parts["values"]["pi"] == pytest.approx(whole["values"]["pi"], abs=1e-6)
    lo, hi = parts["values"]["pi"]
    assert _one(tau2=[".0100", ".0125"], printed_pi=[f"{lo:.3f}", f"{hi:.3f}"], **common)["status"] == "ok"
    assert _one(tau2=[], **common)["status"] == "input_error"
    assert _one(tau2=[".01", "x"], **common)["status"] == "input_error"
    assert _one(tau2=[".01", "-.02"], **common)["status"] == "input_error"


# --- Task 4 fix round 2 ---

def _pi(rid, printed=("0.1", "0.2"), **kw):
    rec = dict(kind="prediction_interval", mean=".300", se=".025", tau=".150", scale="raw", k=20,
               alt_group="g", printed_pi=list(printed), id=rid, page="7", locator="Table 2")
    rec.update(kw)
    return rec


def test_group_sibling_without_printed_value_does_not_rescue_a_mismatch():
    a, b = _run_many([_pi("a"), _pi("b", printed_pi=None)])
    assert a["status"] == "mismatch" and b["status"] == "info"


def test_group_not_computable_sibling_does_not_rescue_a_mismatch():
    a, b = _run_many([_pi("a"), _pi("b", k=2)])
    assert b["status"] == "not_computable" and a["status"] == "mismatch"


def test_group_input_error_sibling_does_not_rescue_a_mismatch():
    a, b = _run_many([_pi("a"), _pi("b", scale="bad")])
    assert a["status"] == "mismatch" and b["status"] == "input_error"


def test_mixed_kind_group_is_not_resolved():
    i2 = dict(kind="i2", q="40.0", df=19, q_based=True, alt_group="g", id="b", page="7", locator="T")
    a, b = _run_many([_pi("a"), i2])
    assert a["status"] == "mismatch" and b["status"] == "info"
    assert "mixed kinds" in a["message"] and "mixed kinds" in b["message"]
    ok_flow = dict(kind="flow", identified="1000", duplicates_removed="100", screened="900", alt_group="g",
                   id="c", page="7", locator="T")
    a2, c = _run_many([_pi("a"), ok_flow])
    assert a2["status"] == "mismatch" and c["status"] == "ok"


def test_group_with_one_ok_member_resolves_and_says_so():
    good = _pi("g1", printed_pi=None)
    lo, hi = _one(**{k: v for k, v in good.items() if k != "alt_group"})["values"]["pi"]
    ok = _pi("ok", printed_pi=[f"{lo:.3f}", f"{hi:.3f}"])
    bad, ok_r = _run_many([_pi("bad"), ok])
    assert ok_r["status"] == "ok" and bad["status"] == "info"
    assert "another alternative in the group matched" in bad["message"]
