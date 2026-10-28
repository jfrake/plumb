"""check_hypotheses.py: the deterministic hypothesis checks. Every expected value was computed with the repo's
pvalues and verify_arithmetic.check_claim (spec section 6.2); the plan's reviewer re-derives them (L10)."""
from __future__ import annotations
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "review" / "scripts"
SCRIPT = SCRIPTS / "check_hypotheses.py"


def _mod():
    spec = importlib.util.spec_from_file_location("check_hypotheses", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CH = _mod()
MODS, _ = CH._imports()


def _est(b="", se="", **over):
    e = {"b": b, "se": se, "t": "", "p": "", "ci": [], "ci_level": "", "marks": "", "scale": "coefficient",
         "se_of": "printed estimate"}
    e.update(over)
    return e


def _test(test_id, b="", se="", term_kind="main effect", expected_sign="positive", **over):
    est = over.pop("estimate", None) or _est(b, se)
    t = {"test_id": test_id, "study": "", "table": "Table 3", "column": "Model 2", "term": "X",
         "term_kind": term_kind, "expected_sign": expected_sign, "variables": {}, "sample": "full",
         "designated": "unspecified", "model_includes_product": False, "model_family": "linear", "estimate": est,
         "note_levels": ["0.10", "0.05", "0.01"], "tails": "unstated", "cells": [f"table_03.csv:{len(test_id)}:2"],
         "evidence_kind": "n/a", "verdict": ""}
    t.update(over)
    return t


def _row(rid, tests, cites=None, **over):
    r = {"id": rid, "type": "directional", "verdict": "supported", "verdict_page": "15", "page": "7",
         "tests": tests, "verdict_cites": [t["test_id"] for t in tests] if cites is None else cites,
         "verdict_scope": "cited tests", "claimed_level": "", "shape": "n/a", "base_sign": "n/a",
         "moderator_note": "", "independent": "n/a"}
    r.update(over)
    return r


def _ledger(*rows, level="0.05", tails="two"):
    return {"criterion": {"level": level, "tails": tails, "page": "11", "text": ""}, "hypotheses": list(rows)}


def _check(ledger, tables=None):
    return CH.run(ledger, tables, MODS)


def _flags(out, check=None):
    return [f for f in out.flags if check is None or f["check"] == check]


# --- spec 6.2 test 1: HL3 flags a verdict the estimate cannot support ---

def test_hl3_flags_supported_estimate_above_the_level():
    out = _check(_ledger(_row("H2", [_test("H2-t1", "0.061", "0.052")]), tails="unstated"))
    (flag,) = _flags(out, "HL3")
    assert flag["item"] == "numbers:hyp:H2:HL3" and flag["table"] == "Table 3"
    text = flag["reasons"][0]
    assert "two-sided: p 0.232 to 0.249" in text and "one-tailed, which the paper does not state: p 0.116 to 0.125" in text


def test_hl3_readings_match_the_spec_digits():
    pv, va, _ = MODS
    res = va.check_claim({"b": "0.061", "se": "0.052", "directional": True, "tails": "unstated",
                          "claim": {"op": "<", "level": "0.05"}})
    two, one = res["values"]["two-sided"], res["values"]["one-tailed, which the paper does not state"]
    assert [round(x, 4) for x in two] == [0.2324, 0.2492] and [round(x, 4) for x in one] == [0.1162, 0.1246]


# --- test 2: the decoy within rounding ---

def test_hl3_decoy_within_rounding_is_not_flagged():
    out = _check(_ledger(_row("H8", [_test("H8-t1", "-0.049", "0.025", expected_sign="negative")])))
    assert _flags(out) == []
    pv, va, _ = MODS
    res = va.check_claim({"b": "-0.049", "se": "0.025", "tails": "two", "claim": {"op": "<", "level": "0.05"}})
    assert [round(x, 4) for x in res["values"]["two-sided"]] == [0.0433, 0.0572]


# --- test 3: a level the verdict sentence states ---

def test_hl3_claimed_level_replaces_the_criterion():
    row = _row("H3", [_test("H3-t1", "0.21", "0.11")], claimed_level="0.01")
    out = _check(_ledger(row, tails="unstated"))
    (flag,) = _flags(out, "HL3")
    assert "at p < 0.01 (the level the verdict sentence states)" in flag["reasons"][0]
    assert "two-sided: p 0.041 to 0.075" in flag["reasons"][0]
    assert "one-tailed, which the paper does not state: p 0.020 to 0.037" in flag["reasons"][0]
    assert _flags(_check(_ledger(dict(row, claimed_level=""), tails="unstated"))) == []


# --- test 4: partial support is HL3 only when every focal cited test fails (fix-round ruling I4) ---

def test_hl3_partial_support_is_not_flagged():
    row = _row("H4", [_test("H4-t1", "0.071", "0.030"), _test("H4-t2", "0.034", "0.029")],
               verdict="partially supported")
    assert _flags(_check(_ledger(row)), "HL3") == []


def test_hl3_mixed_passing_and_failing_supported_tests_are_not_flagged():
    row = _row("H4", [_test("H4-t1", "0.071", "0.030"), _test("H4-t2", "0.034", "0.029")])
    assert _flags(_check(_ledger(row)), "HL3") == []


# --- test 5: intervals, with the lenient tails rule ---

@pytest.mark.parametrize("ci,scale,tails,expect", [
    (["-0.02", "0.11"], "coefficient", "two", "flag"),
    (["0.01", "0.11"], "coefficient", "two", "none"),
    (["0.92", "1.40"], "ratio", "two", "flag"),
    (["-0.01", "0.30"], "coefficient", "unstated", "not computable"),
    (["0.11", "-0.02"], "coefficient", "two", "reversed"),
])
def test_hl3_intervals(ci, scale, tails, expect):
    est = _est(ci=ci, ci_level="95", scale=scale)
    out = _check(_ledger(_row("H5", [_test("H5-t1", estimate=est)]), tails=tails))
    assert bool(_flags(out, "HL3")) == (expect == "flag")
    assert bool([u for u in out.unknown if u["check"] == "HL3"]) == (expect in ("not computable", "reversed"))
    if expect == "not computable":
        assert "the verdict needs a 90 percent interval" in out.unknown[0]["detail"]
    if expect == "reversed":
        assert "lower end above its upper end" in out.unknown[0]["detail"]


# --- test 6: a ratio printed with another number's error ---

def test_ratio_with_another_numbers_error_is_not_computable():
    est = _est("1.02", "0.05", scale="ratio", se_of="another number")
    out = _check(_ledger(_row("H5", [_test("H5-t1", estimate=est)])))
    assert _flags(out) == [] and [u["check"] for u in out.unknown] == ["HL3"]
    null = _row("H6", [_test("H6-t1", estimate=est, expected_sign="none")], type="null")
    out = _check(_ledger(null))
    assert _flags(out) == [] and [u["check"] for u in out.unknown] == ["HL7"]


# --- test 7: marks only ---

@pytest.mark.parametrize("marks,flagged", [("*", True), ("**", False)])
def test_hl3_marks_only(tmp_path, marks, flagged):
    (tmp_path / "table_07_note.txt").write_text("Standardized paths. * p<.05, ** p<.01", encoding="utf-8")
    est = _est("0.21", "", marks=marks, scale="standardized", se_of="unstated")
    row = _row("H3", [_test("H3-t1", estimate=est, cells=["table_07.csv:4:2"])], claimed_level="0.01")
    out = _check(_ledger(row), tables=tmp_path)
    assert bool(_flags(out, "HL3")) == flagged
    if flagged:
        assert "the mark '*' claims p < 0.05 only" in _flags(out, "HL3")[0]["reasons"][0]


def test_hl3_marks_only_without_a_note_is_not_computable(tmp_path):
    est = _est("0.21", "", marks="*", scale="standardized", se_of="unstated")
    out = _check(_ledger(_row("H3", [_test("H3-t1", estimate=est)], claimed_level="0.01")), tables=tmp_path)
    assert _flags(out) == [] and out.unknown[0]["check"] == "HL3"


# --- test 8: HL5, sign against the hypothesis ---

@pytest.mark.parametrize("b,flagged,unknown", [("0.18", True, False), ("-0.18", False, False),
                                               ("0.000", False, True)])
def test_hl5_sign(b, flagged, unknown):
    row = _row("H5", [_test("H5-t1", b, "0.06", expected_sign="negative", model_family="hazard")])
    out = _check(_ledger(row))
    assert bool(_flags(out, "HL5")) == flagged
    assert bool([u for u in out.unknown if u["check"] == "HL5"]) == unknown


def test_hl5_does_not_reduce_is_not_a_null():
    row = _row("H5", [_test("H5-t1", "0.08", "0.02", expected_sign="not negative")])
    out = _check(_ledger(row))
    assert _flags(out) == []


def test_hl5_does_not_reduce_flags_a_significant_negative_estimate(tmp_path):
    # Fix-round rulings: a bare statistic rejects only under its printed df (I2), and only when the note says the
    # parentheses hold standard errors (I3).
    (tmp_path / "table_03_note.txt").write_text("Standard errors in parentheses.", encoding="utf-8")
    est = _est("-0.08", "0.02", df="200")
    row = _row("H5", [_test("H5-t1", estimate=est, expected_sign="not negative")])
    (flag,) = _flags(_check(_ledger(row), tables=tmp_path), "HL5")
    assert "is negative and significant" in flag["reasons"][0]
    assert _flags(_check(_ledger(row))) == []


def test_hl5_names_a_one_tailed_test_in_the_wrong_direction():
    row = _row("H5", [_test("H5-t1", "0.18", "0.06", expected_sign="negative", tails="one")])
    (flag,) = _flags(_check(_ledger(row)), "HL5")
    assert "a one-tailed p for an estimate in the wrong direction" in flag["reasons"][0]


# --- test 9: HL5 skips interaction rows and non-focal cited coefficients ---

def _p7(b="-0.090", **over):
    product = _test("H7-t1", b, "0.030", term_kind="product term", expected_sign="positive",
                    model_includes_product=True, table="Table 4", column="Model 3", term="Slack x Competition")
    main = _test("H7-t2", "-0.25", "0.06", term_kind="main effect", expected_sign="none",
                 model_includes_product=True, table="Table 4", column="Model 3", term="Competition")
    fields = dict(type="interaction", shape="weakens", base_sign="negative")
    fields.update(over)
    return _row("H7", [product, main], **fields)


def test_hl5_skips_the_interaction_row_and_its_main_effect():
    out = _check(_ledger(_p7()))
    assert _flags(out, "HL5") == [] and [f["check"] for f in _flags(out)] == ["HL9"]


# --- test 10: HL7, null framing, two-sided always ---

def test_hl7_null_called_not_supported():
    row = _row("H6", [_test("H6-t1", "0.012", "0.020", expected_sign="none")], type="null", verdict="not supported")
    (flag,) = _flags(_check(_ledger(row, tails="one")), "HL7")
    assert "two-sided: p 0.522 to 0.575" in flag["reasons"][0]
    pv, va, _ = MODS
    res = va.check_claim({"b": "0.012", "se": "0.020", "tails": "two", "claim": {"op": "<", "level": "0.05"}})
    assert [round(x, 4) for x in res["values"]["two-sided"]] == [0.5215, 0.5748]
    assert _flags(_check(_ledger(dict(row, verdict="supported")))) == []


def test_hl7_null_called_supported_although_rejected(tmp_path):
    # Fix-round rulings: a bare statistic rejects only under its printed df (I2), and only when the note says the
    # parentheses hold standard errors (I3).
    (tmp_path / "table_03_note.txt").write_text("Standard errors in parentheses.", encoding="utf-8")
    est = _est("0.12", "0.020", df="120")
    row = _row("H6", [_test("H6-t1", estimate=est, expected_sign="none")], type="null")
    (flag,) = _flags(_check(_ledger(row), tables=tmp_path), "HL7")
    assert "called supported, but its test rejects it" in flag["reasons"][0]
    assert _flags(_check(_ledger(row))) == []


# --- test 11: HL9, shape against sign ---

def test_hl9_shape_against_sign():
    (flag,) = _flags(_check(_ledger(_p7())), "HL9")
    assert "needs a positive product term" in flag["reasons"][0]
    assert _flags(_check(_ledger(_p7("0.090"))), "HL9") == []
    coded = "the variable measures scarcity; the hypothesis names munificence"
    assert _flags(_check(_ledger(_p7(moderator_note=coded))), "HL9") == []
    assert _flags(_check(_ledger(_p7("0.090", moderator_note=coded))), "HL9")


def test_hl9_not_computable_cases():
    out = _check(_ledger(_p7(shape="substitutes")))
    assert _flags(out, "HL9") == [] and out.unknown[0]["check"] == "HL9"
    out = _check(_ledger(_p7(base_sign="from estimate")))
    assert _flags(out, "HL9") == [] and "no model without the product term" in out.unknown[0]["detail"]


def test_hl9_base_sign_from_a_model_without_the_product_term():
    row = _p7(base_sign="from estimate")
    row["tests"].append(_test("H7-t3", "-0.21", "0.05", term_kind="main effect", expected_sign="none",
                              model_includes_product=False, column="Model 2", term="Competition"))
    (flag,) = _flags(_check(_ledger(row)), "HL9")
    assert "needs a positive product term" in flag["reasons"][0]


def test_hl9_no_model_includes_the_product_term():
    row = _p7("0.090")
    for t in row["tests"]:
        t["model_includes_product"] = False
    (flag,) = _flags(_check(_ledger(row)), "HL9")
    assert flag["reasons"] == ["no model the row's tests come from includes the product term"]


def test_hl9_verdict_cites_only_the_moderated_effect():
    row = _p7("0.090")
    row["verdict_cites"] = ["H7-t2"]
    (flag,) = _flags(_check(_ledger(row)), "HL9")
    assert flag["reasons"] == ["the verdict cites no product term although one is in the row's tests"]


# --- test 12: HL15, the designated test ---

def test_hl15_designated_test_not_cited():
    designated = _test("H10-t1", "0.041", "0.036", designated="yes", column="Model 4")
    cited = _test("H10-t2", "0.083", "0.031", designated="no", column="Model 2")
    out = _check(_ledger(_row("H10", [designated, cited], cites=["H10-t2"])))
    (flag,) = _flags(out, "HL15")
    assert "two-sided: p 0.242 to 0.267" in flag["reasons"][0] and _flags(out, "HL3") == []


def test_hl15_scope_list_whose_tests_pass():
    tests = [_test("H1-t1", "0.142", "0.041"), _test("H1-t2", "0.120", "0.040"), _test("H1-t3", "0.150", "0.050")]
    row = _row("H1", tests, cites=["H1-t1"], verdict_scope=["H1-t2", "H1-t3"])
    assert _flags(_check(_ledger(row))) == []


# --- test 13: split-sample estimates are not focal for a difference row ---

def _p12(**over):
    fam = _test("H9-t1", "0.18", "0.07", term_kind="subsample estimate", expected_sign="none", table="Table 9",
                column="Family", sample="family firms")
    non = _test("H9-t2", "0.09", "0.08", term_kind="subsample estimate", expected_sign="none", table="Table 9",
                column="Non-family", sample="non-family firms")
    fields = dict(type="difference", shape="larger in: family firms", independent="yes")
    fields.update(over)
    return _row("H9", [fam, non], **fields)


def test_hl3_does_not_read_subsample_estimates():
    out = _check(_ledger(_p12()))
    assert _flags(out) == []


# --- test 14: HL8 facts ---

def test_hl8_facts():
    out = _check(_ledger(_p12()))
    (fact,) = out.facts
    assert (fact["b_a"], fact["se_a"], fact["b_b"], fact["se_b"], fact["independent"]) == ("0.18", "0.07", "0.09",
                                                                                        "0.08", True)
    assert [round(x, 3) for x in fact["difference"]] == [0.080, 0.100]
    assert [round(x, 4) for x in fact["se"]] == [0.0992, 0.1134]
    assert [round(x, 3) for x in fact["abs_z"]] == [0.706, 1.008]
    assert [round(x, 3) for x in fact["p_two_sided"]] == [0.314, 0.480]
    assert _flags(out) == []


def test_hl8_no_facts_with_a_difference_test_or_shared_units():
    row = _p12()
    row["tests"].append(_test("H9-t3", "0.09", "0.05", term_kind="difference test", expected_sign="positive"))
    row["verdict_cites"].append("H9-t3")
    assert _check(_ledger(row)).facts == []
    out = _check(_ledger(_p12(independent="unknown")))
    assert out.facts == [] and out.unknown[0]["check"] == "HL8"


# --- test 15: one flag per row per check ---

def test_one_flag_per_row_per_check_lists_both_reasons():
    designated = _test("H10-t1", "0.041", "0.036", designated="yes")
    cited = _test("H10-t2", "0.083", "0.031")
    robust = _test("H10-t3", "0.030", "0.040")
    row = _row("H10", [designated, cited, robust], cites=["H10-t2"], verdict_scope=["H10-t2", "H10-t3"])
    flags = _flags(_check(_ledger(row)), "HL15")
    assert len(flags) == 1 and len(flags[0]["reasons"]) == 2
    assert flags[0]["item"] == "numbers:hyp:H10:HL15"


# --- test 16: exit codes and the report ---

def _cli(tmp_path, content, script=SCRIPT):
    path = tmp_path / "ws" / "stage-1" / "hypothesis_ledger.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if content is not None:
        path.write_text(content, encoding="utf-8")
    md, js = path.with_name("hypothesis_checks.md"), path.with_name("hypothesis_checks.json")
    r = subprocess.run([sys.executable, str(script), str(path), str(md), "--json", str(js)],
                       capture_output=True, text=True)
    return r, md, js


@pytest.mark.parametrize("content", [None, "{not json", "[]"], ids=["missing", "invalid", "list"])
def test_exit_2_on_a_bad_ledger(tmp_path, content):
    r, md, _ = _cli(tmp_path, content)
    assert r.returncode == 2 and not md.exists() and "Traceback" not in r.stderr


def test_exit_2_when_the_import_fails(tmp_path):
    lone = tmp_path / "lone"
    lone.mkdir()
    shutil.copy(SCRIPT, lone / "check_hypotheses.py")
    r, _, _ = _cli(tmp_path, json.dumps(_ledger()), script=lone / "check_hypotheses.py")
    assert r.returncode == 2 and "cannot import" in r.stderr


def test_report_lines_carry_the_item_table_and_cells(tmp_path):
    r, md, js = _cli(tmp_path, json.dumps(_ledger(_row("H2", [_test("H2-t1", "0.061", "0.052")]))))
    assert r.returncode == 0, r.stderr
    text = md.read_text(encoding="utf-8")
    flag = text.split("## Flags\n\n", 1)[1].split("\n", 1)[0]
    assert flag.startswith("1. H2: ")
    assert flag.endswith("Check: HL3. [paper] Hypothesis: H2. Item: numbers:hyp:H2:HL3. Table: Table 3. "
                         "Cells: table_03.csv:5:2.")
    assert "## Facts\n\nNone." in text and "## Not computed\n\nNone." in text
    assert json.loads(js.read_text(encoding="utf-8"))["flags"][0]["item"] == "numbers:hyp:H2:HL3"


def test_empty_ledger_writes_empty_sections(tmp_path):
    r, md, _ = _cli(tmp_path, json.dumps({"mode": "none", "hypotheses": []}))
    assert r.returncode == 0
    assert "## Flags\n\nNone." in md.read_text(encoding="utf-8")


@pytest.mark.parametrize("row", [
    None, "H1", {"id": ["H1"], "type": {"x": 1}, "verdict": "supported", "tests": 1e308},
    {"id": "H1", "type": "directional", "verdict": "supported", "verdict_cites": [["t"]],
     "tests": [{"test_id": float("inf"), "term_kind": "main effect", "estimate": "0.1"}]},
    {"id": "H1", "type": "difference", "verdict": "supported", "independent": "yes", "verdict_cites": [],
     "tests": [{"test_id": "a", "term_kind": "subsample estimate", "estimate": {"b": "0.1", "se": "0"}},
               {"test_id": "b", "term_kind": "subsample estimate", "estimate": {"b": "x", "se": "-1"}}]},
    {"id": "H1", "type": "difference", "verdict": "supported", "independent": "yes", "verdict_cites": [],
     "tests": [{"test_id": "a", "term_kind": "subsample estimate", "estimate": {"b": "9" * 400, "se": "0.07"}},
               {"test_id": "b", "term_kind": "subsample estimate", "estimate": {"b": "0.09", "se": "0.08"}}]},
], ids=["none", "string", "wrong-types", "inf-id", "bad-subsamples", "infinite-subsample"])
def test_malformed_rows_never_crash(row):
    out = _check({"criterion": [], "hypotheses": [row]})
    json.dumps({"flags": out.flags, "facts": out.facts, "not_computed": out.unknown}, allow_nan=False)
    assert out.flags == []


# --- Review Focus 1: correct tables at printed rounding raise no flag ---

def _printed(x, d):
    s = f"{x:.{d}f}"
    return s[1:] if s.startswith("-") and float(s) == 0 else s


def _generated_row(rng, i):
    """One hypothesis whose verdict is right for the true estimate, printed at 2 to 4 decimals in one style."""
    import math
    d, se = rng.choice([2, 3, 3, 4]), rng.uniform(0.005, 0.2)
    b = rng.choice([rng.uniform(-4, 4), rng.uniform(1.5, 2.2), rng.uniform(-2.2, -1.5)]) * se
    p = math.erfc(abs(b / se) / math.sqrt(2))
    style, tails = rng.choice(["se", "se", "t", "p", "ci", "marks"]), rng.choice(["two", "one"])
    level = rng.choice([0.01, 0.05, 0.10])
    est = _est(_printed(b, d))
    if style == "se":
        est["se"] = _printed(se, d) if float(_printed(se, d)) > 0 else _printed(se, d + 2)
    elif style == "t":
        est["t"] = _printed(b / se, 2)
    elif style == "p":
        est["p"] = "<0.001" if p < 0.001 else _printed(p, 3)
    elif style == "ci":
        conf, z = rng.choice([(90, 1.6448536), (95, 1.9599640), (99, 2.5758293)])
        est.update(ci=[_printed(b - z * se, d), _printed(b + z * se, d)], ci_level=str(conf))
    else:
        tails = "two"
        est.update(marks=next((m for m, t in (("***", .01), ("**", .05), ("*", .10)) if p < t), ""),
                   scale="standardized", se_of="unstated")
    p_used = p / 2 if tails == "one" else p
    kind = rng.choice(["directional", "null", "interaction", "curvilinear"])
    cells = ["table_01.csv:2:2"]
    if kind == "null":
        test = _test("t1", estimate=est, expected_sign="none", designated="yes", tails=tails, cells=cells)
        return _row(f"H{i}", [test], type="null", verdict="supported" if p >= level else "not supported"), level, tails
    if kind == "interaction":
        base, shape = rng.choice(["positive", "negative"]), rng.choice(["strengthens", "weakens", "reverses"])
        need = base if shape == "strengthens" else ("negative" if base == "positive" else "positive")
        test = _test("t1", estimate=est, term_kind="product term", expected_sign=need, model_includes_product=True,
                     tails=tails, cells=cells)
        ok = (b > 0) == (need == "positive") and p_used < level
        return _row(f"H{i}", [test], type="interaction", shape=shape, base_sign=base,
                    verdict="supported" if ok else "not supported"), level, tails
    if kind == "curvilinear":
        shape = rng.choice(["inverted U", "U", "diminishing returns", "increasing returns"])
        need = "negative" if shape in ("inverted U", "diminishing returns") else "positive"
        test = _test("t1", estimate=est, term_kind="squared term", expected_sign=need, tails=tails, cells=cells)
        ok = (b > 0) == (need == "positive") and p_used < level
        return _row(f"H{i}", [test], type="curvilinear", shape=shape,
                    verdict="supported" if ok else "not supported"), level, tails
    want = rng.choice(["positive", "negative"])
    test = _test("t1", estimate=est, expected_sign=want, tails=tails, cells=cells)
    ok = (b > 0) == (want == "positive") and p_used < level
    return _row(f"H{i}", [test], verdict="supported" if ok else "not supported"), level, tails


def test_generated_correct_tables_raise_no_flag(tmp_path):
    import random
    rng = random.Random(20260930)
    (tmp_path / "table_01_note.txt").write_text("Standard errors in parentheses. * p<0.10, ** p<0.05, *** p<0.01",
                                                encoding="utf-8")
    flagged = []
    for i in range(3000):
        row, level, tails = _generated_row(rng, i)
        out = _check(_ledger(row, level=f"{level:.2f}", tails=tails), tables=tmp_path)
        flagged += out.flags
    assert flagged == []


# --- Independent preflight rulings (2026-09-30): C1 to C5, C10, and the long-number exit ---

@pytest.mark.parametrize("case", ["non-focal-designated", "null-designated", "not-negative-scope"])
def test_hl15_reads_only_focal_directional_tests(case):
    if case == "non-focal-designated":
        prod = _test("H7-t1", "0.090", "0.030", term_kind="product term", expected_sign="positive", designated="yes",
                     model_includes_product=True)
        main = _test("H7-t2", "-0.04", "0.06", expected_sign="none", designated="yes", model_includes_product=True)
        row = _row("H7", [prod, main], cites=["H7-t1"], type="interaction", shape="weakens", base_sign="negative")
    elif case == "null-designated":
        full = _test("H6-t1", "0.010", "0.020", expected_sign="none", designated="yes", column="Model 4")
        reduced = _test("H6-t2", "0.012", "0.021", expected_sign="none", designated="no")
        row = _row("H6", [full, reduced], cites=["H6-t2"], type="null")
    else:
        tests = [_test("H5-t1", "0.03", "0.02", expected_sign="not negative"),
                 _test("H5-t2", "0.02", "0.03", expected_sign="not negative")]
        row = _row("H5", tests, cites=["H5-t1"], verdict_scope=["H5-t1", "H5-t2"])
    assert _flags(_check(_ledger(row))) == []


def test_ratio_with_its_own_error_is_not_computable():
    est = _est("1.50", "0.30", scale="ratio", se_of="printed estimate")
    out = _check(_ledger(_row("H1", [_test("H1-t1", estimate=est)])))
    assert _flags(out) == [] and "log scale" in out.unknown[0]["detail"]


@pytest.mark.parametrize("est", [_est(t="2.05"), _est("0.41", "0.20")], ids=["t", "b-se"])
def test_small_sample_statistic_is_not_read_as_rejecting_a_null(est):
    row = _row("H6", [_test("H6-t1", estimate=est, expected_sign="none")], type="null")
    out = _check(_ledger(row))
    assert _flags(out) == [] and [u["check"] for u in out.unknown] == ["HL7"]


def test_t_statistics_in_parentheses_are_read_as_t(tmp_path):
    (tmp_path / "table_03_note.txt").write_text("t-statistics in parentheses. * p<0.10, ** p<0.05, *** p<0.01",
                                                encoding="utf-8")
    row = _row("H1", [_test("H1-t1", "0.130", "2.40", cells=["table_03.csv:4:2"])])
    assert _flags(_check(_ledger(row), tables=tmp_path)) == []
    assert _flags(_check(_ledger(row))) == []  # I3 ruling: no note, and only the error reading would flag


def test_hl9_verdict_citing_the_designated_figure():
    product = _test("H7-t1", "0.090", "0.030", term_kind="product term", expected_sign="positive",
                    model_includes_product=True)
    figure = _test("H7-t2", estimate=_est(), term_kind="figure", expected_sign="none", designated="yes",
                   model_includes_product=True)
    row = _row("H7", [product, figure], cites=["H7-t2"], type="interaction", shape="weakens", base_sign="negative")
    assert _flags(_check(_ledger(row))) == []


def test_exit_2_on_a_number_too_long_to_read(tmp_path):
    row = _row("H1", [_test("H1-t1", "9" * 400, "0.05")])
    r, md, _ = _cli(tmp_path, json.dumps(_ledger(row)))
    assert r.returncode == 2 and "too long to read" in r.stderr and "Traceback" not in r.stderr and not md.exists()


# --- Fix round (2026-09-30 rulings): I1 to I4, M1 to M3, M7 ---

STARS = "Standard errors in parentheses. * p<0.10, ** p<0.05, *** p<0.01"


def _note_dir(tmp_path, text, name="table_03"):
    (tmp_path / f"{name}_note.txt").write_text(text, encoding="utf-8")
    return tmp_path


def _marked(rid, marks, **over):
    est = _est("0.21", "", marks=marks, scale="standardized", se_of="unstated")
    return _test(f"{rid}-t1", estimate=est, cells=["table_03.csv:4:2"], **over)


@pytest.mark.parametrize("marks,tails,expect", [
    ("*", "one", "unknown"),         # two-sided stars, one-tailed paper: p < .10 two-sided is p < .05 one-tailed
    ("*", "unstated", "unknown"),    # the one-tailed reading is allowed, so no flag
    ("*", "two", "flag"),
    ("", "one", "flag"),             # no star: two-sided p >= .10, so one-tailed p >= .05 under every reading
    ("**", "one", "none"),
])
def test_marks_only_reads_the_lenient_tails(tmp_path, marks, tails, expect):
    out = _check(_ledger(_row("H4", [_marked("H4", marks)]), tails=tails), tables=_note_dir(tmp_path, STARS))
    assert bool(_flags(out, "HL3")) == (expect == "flag")
    unknown = [u for u in out.unknown if u["check"] == "HL3"]
    assert bool(unknown) == (expect == "unknown")
    if unknown:  # inference I13 reads this phrase only when the split is between the test's tail readings
        assert ("the readings straddle" in unknown[0]["detail"]) == (tails == "unstated")


def test_marks_only_no_mark_below_a_strict_key_is_not_a_flag(tmp_path):
    out = _check(_ledger(_row("H4", [_marked("H4", "")])), tables=_note_dir(tmp_path, "* p<.01"))
    assert _flags(out) == [] and [u["check"] for u in out.unknown] == ["HL3"]


def test_marks_only_hl15_reads_the_lenient_tails(tmp_path):
    cited = _test("H4-t2", "0.30", "0.10", cells=["table_03.csv:6:2"])
    row = _row("H4", [_marked("H4", "*", designated="yes"), cited], cites=["H4-t2"])
    assert _flags(_check(_ledger(row, tails="one"), tables=_note_dir(tmp_path, STARS))) == []
    assert _flags(_check(_ledger(row, tails="two"), tables=_note_dir(tmp_path, STARS)), "HL15")


@pytest.mark.parametrize("t,df,level,verdict", [("2.20", "10", "0.05", "supported"), ("2.17", "12", "0.05", "supported"),
                                                ("1.85", "8", "0.10", "supported"), ("2.80", "20", "0.01", "supported")])
def test_small_sample_null_with_printed_df_is_read_under_t(t, df, level, verdict):
    row = _row("H6", [_test("H6-t1", estimate=_est(t=t, df=df), expected_sign="none")], type="null", verdict=verdict)
    out = _check(_ledger(row, level=level))
    assert _flags(out) == [] and out.unknown == []


def test_printed_df_makes_a_small_sample_test_fail():
    row = _row("H6", [_test("H6-t1", estimate=_est(t="2.20", df="10"), expected_sign="none")], type="null",
               verdict="not supported")
    (flag,) = _flags(_check(_ledger(row)), "HL7")
    assert "p 0.0520 to 0.0529" in flag["reasons"][0] and "t(10)" in flag["reasons"][0]
    hl3 = _row("H1", [_test("H1-t1", estimate=_est("0.40", "0.18", df="5"))])
    (flag,) = _flags(_check(_ledger(hl3)), "HL3")
    assert "two-sided, t(5): p 0.069 to 0.086" in flag["reasons"][0]
    assert _flags(_check(_ledger(_row("H1", [_test("H1-t1", "0.40", "0.18")])))) == []


def test_bare_statistic_without_df_never_rejects_a_null():
    row = _row("H6", [_test("H6-t1", "0.12", "0.020", expected_sign="none")], type="null")
    out = _check(_ledger(row))
    assert _flags(out) == [] and [u["check"] for u in out.unknown] == ["HL7"]
    assert "degrees of freedom" in out.unknown[0]["detail"]
    neg = _row("H5", [_test("H5-t1", "-0.08", "0.02", expected_sign="not negative")])
    out = _check(_ledger(neg))
    assert _flags(out) == [] and [u["check"] for u in out.unknown] == ["HL5"]


@pytest.mark.parametrize("note", ["t-statistics in parentheses.",
                                  "Average marginal effects; z-statistics in parentheses. * p<0.10, ** p<0.05, "
                                  "*** p<0.01",
                                  "Odds ratios. Robust z statistics in parentheses.",
                                  "Bootstrap: t-values in brackets."])
def test_t_in_parentheses_is_read_in_any_note_wording(tmp_path, note):
    row = _row("H1", [_test("H1-t1", "0.130", "2.40", cells=["table_03.csv:4:2"])])
    out = _check(_ledger(row), tables=_note_dir(tmp_path, note))
    assert _flags(out) == [] and out.unknown == []


@pytest.mark.parametrize("note", ["Standard errors in parentheses.",
                                  "Bootstrapped standard errors in parentheses.",
                                  "Average marginal effects; standard errors in parentheses."])
def test_se_in_parentheses_is_read_in_any_note_wording(tmp_path, note):
    row = _row("H1", [_test("H1-t1", "0.130", "2.40", cells=["table_03.csv:4:2"])])
    assert _flags(_check(_ledger(row), tables=_note_dir(tmp_path, note)), "HL3")


@pytest.mark.parametrize("note", [None, "Model 3 adds controls.", "Values in parentheses."])
def test_unsaid_parentheses_that_would_flag_only_as_an_error_are_not_computable(tmp_path, note):
    row = _row("H1", [_test("H1-t1", "0.130", "2.40", cells=["table_03.csv:4:2"])])
    out = _check(_ledger(row), tables=None if note is None else _note_dir(tmp_path, note))
    assert _flags(out) == [] and [u["check"] for u in out.unknown] == ["HL3"]
    assert "parentheses" in out.unknown[0]["detail"]
    small = _row("H1", [_test("H1-t1", "0.061", "0.052", cells=["table_03.csv:4:2"])])
    assert _flags(_check(_ledger(small), tables=None if note is None else tmp_path), "HL3")


def test_partial_support_is_flagged_when_every_cited_focal_test_fails():
    row = _row("H4", [_test("H4-t1", "0.034", "0.029"), _test("H4-t2", "0.020", "0.030")],
               verdict="partially supported")
    (flag,) = _flags(_check(_ledger(row)), "HL3")
    assert "called partially supported" in flag["reasons"][0] and len(flag["reasons"]) == 2
    one_holds = _row("H4", [_test("H4-t1", "0.071", "0.030"), _test("H4-t2", "0.020", "0.030")],
                     verdict="partially supported")
    assert _flags(_check(_ledger(one_holds))) == []


def test_superscript_digits_are_not_numbers(tmp_path):
    row = _row("H1", [_test("H1-t1", "²", "0.05"), _test("H1-t2", "0.3", "①")])
    assert CH._too_long(_ledger(row)) == ""
    r, md, js = _cli(tmp_path, json.dumps(_ledger(row)))
    assert r.returncode == 0 and "Traceback" not in r.stderr, r.stderr


def _strict(text):
    def bad(name):
        raise ValueError(name)
    return json.loads(text, parse_constant=bad)


def test_deep_nesting_exits_2(tmp_path, monkeypatch):
    r, md, _ = _cli(tmp_path, "[" * 100000 + "]" * 100000)
    assert r.returncode == 2 and "Traceback" not in r.stderr and not md.exists()

    def deep(_text):
        raise RecursionError("maximum recursion depth exceeded")  # what Python 3.9's json raises
    monkeypatch.setattr(CH.json, "loads", deep)
    path = tmp_path / "ws" / "stage-1" / "hypothesis_ledger.json"
    assert CH.main([str(path), str(tmp_path / "out.md"), "--json", str(tmp_path / "out.json")]) == 2


def test_json_output_is_strict_with_a_nan_id(tmp_path):
    subs = [_test("D-t1", "0.30", "0.10", term_kind="subsample estimate", expected_sign="none"),
            _test("D-t2", "0.10", "0.10", term_kind="subsample estimate", expected_sign="none")]
    row = _row("D", subs, cites=[], type="difference", independent="yes", shape="larger in: A")
    text = json.dumps(_ledger(row)).replace('"id": "D"', '"id": NaN')
    r, _, js = _cli(tmp_path, text)
    assert r.returncode == 0, r.stderr
    facts = _strict(js.read_text(encoding="utf-8"))["facts"]
    assert facts and facts[0]["id"] == "?"


def test_hl8_facts_stay_finite_for_huge_estimates(tmp_path):
    subs = [_test("D-t1", "1" + "0" * 300, "1" + "0" * 300, term_kind="subsample estimate", expected_sign="none"),
            _test("D-t2", "-1" + "0" * 300, "1" + "0" * 300, term_kind="subsample estimate", expected_sign="none")]
    row = _row("D", subs, cites=[], type="difference", independent="yes", shape="larger in: A")
    r, _, js = _cli(tmp_path, json.dumps(_ledger(row)))
    assert r.returncode == 0 and "Traceback" not in r.stderr, r.stderr
    _strict(js.read_text(encoding="utf-8"))


def test_hl9_ratio_product_term_reads_against_1():
    po = _test("H15-t1", estimate=_est("0.85", p="0.01", scale="ratio"), term_kind="product term",
               expected_sign="positive", model_includes_product=True)
    row = _row("H15", [po], type="interaction", shape="weakens", base_sign="negative")
    (flag,) = _flags(_check(_ledger(row)), "HL9")
    assert "is negative against 1 (0.85)" in flag["reasons"][0]


# --- Fix round 2 (2026-09-30 rulings): df only for a linear model's t; lenient marks for HL5 and HL7 ---

@pytest.mark.parametrize("family", ["logit or probit", "count", "hazard", "other"])
def test_df_is_ignored_outside_a_linear_model(family):
    est = _est("0.40", "", t="2.00", df="5")  # a z statistic; the 5 is a model or LR chi-square df
    out = _check(_ledger(_row("H9", [_test("H9-t1", estimate=est, model_family=family)])))
    assert _flags(out) == []
    est = _est("0.40", "0.20", df="30")
    out = _check(_ledger(_row("H9", [_test("H9-t1", estimate=est, model_family=family)])))
    assert _flags(out) == []


def test_df_is_read_for_a_linear_model():
    est = _est("0.40", "", t="2.00", df="5")
    assert _flags(_check(_ledger(_row("H9", [_test("H9-t1", estimate=est, model_family="linear")]))), "HL3")


@pytest.mark.parametrize("note,marks,expect", [
    (STARS, "**", "unknown"),                       # silent note: one-sided stars put two-sided p below .10 only
    (STARS, "***", "flag"),                         # p < .02 two-sided under every reading
    (STARS + " Two-tailed tests.", "**", "flag"),
    (STARS + " One-tailed tests.", "**", "unknown"),
])
def test_hl7_reads_marks_at_every_tails_reading(tmp_path, note, marks, expect):
    est = _est("0.21", "", marks=marks)
    row = _row("H6", [_test("H6-t1", estimate=est, expected_sign="none", cells=["table_03.csv:4:2"])], type="null")
    out = _check(_ledger(row), tables=_note_dir(tmp_path, note))
    assert bool(_flags(out, "HL7")) == (expect == "flag")
    assert bool([u for u in out.unknown if u["check"] == "HL7"]) == (expect == "unknown")


@pytest.mark.parametrize("marks,flagged", [("**", False), ("***", True)])
def test_hl5_reads_marks_at_every_tails_reading(tmp_path, marks, flagged):
    est = _est("-0.21", "", marks=marks)
    row = _row("H5", [_test("H5-t1", estimate=est, expected_sign="not negative", cells=["table_03.csv:4:2"])])
    assert bool(_flags(_check(_ledger(row), tables=_note_dir(tmp_path, STARS)), "HL5")) == flagged


# --- Final fix wave A: blank estimates (I1), partial support (I2), straddle reasons (I3), M5 ---

TAILS = "the readings straddle"


@pytest.mark.parametrize("marks", ["", "**"])
def test_blank_estimate_is_not_computed_for_hl3(tmp_path, marks):
    est = _est("", "", marks=marks)
    row = _row("H1", [_test("H1-t1", estimate=est, cells=["table_03.csv:4:2"])])
    out = _check(_ledger(row), tables=_note_dir(tmp_path, STARS))
    assert _flags(out) == []
    hl3 = [u for u in out.unknown if u["check"] == "HL3"]
    assert hl3 and "the estimate is blank" in hl3[0]["detail"]
    assert "carries no significance mark" not in hl3[0]["detail"]


@pytest.mark.parametrize("verdict", ["not supported", "supported"])
def test_blank_estimate_is_not_computed_for_hl7(tmp_path, verdict):
    est = _est("", "")
    row = _row("H6", [_test("H6-t1", estimate=est, expected_sign="none", cells=["table_03.csv:4:2"])], type="null",
               verdict=verdict)
    out = _check(_ledger(row), tables=_note_dir(tmp_path, STARS))
    assert _flags(out) == []
    assert [u["check"] for u in out.unknown] == ["HL7"] and "the estimate is blank" in out.unknown[0]["detail"]


def test_blank_estimate_is_not_computed_for_hl15(tmp_path):
    designated = _test("H10-t1", estimate=_est("", ""), designated="yes", cells=["table_03.csv:4:2"])
    cited = _test("H10-t2", "0.30", "0.10", cells=["table_03.csv:4:3"])
    row = _row("H10", [designated, cited], cites=["H10-t2"])
    out = _check(_ledger(row), tables=_note_dir(tmp_path, STARS))
    assert _flags(out) == []
    hl15 = [u for u in out.unknown if u["check"] == "HL15"]
    assert hl15 and "the estimate is blank" in hl15[0]["detail"]


FIXTURE = ROOT / "skills" / "review" / "fixtures" / "hypothesis-ledger" / "planted-1"


def test_blanked_fixture_raises_no_flag():
    """The review's probe: every cell left unverified (b, se, t, p, marks, and interval blank), notes kept."""
    ledger = json.loads((FIXTURE / "ledger.json").read_text(encoding="utf-8"))
    for row in ledger["hypotheses"]:
        for t in row["tests"]:
            t["estimate"].update(b="", se="", t="", p="", marks="", ci=[])
    out = _check(ledger, tables=FIXTURE / "tables")
    assert _flags(out) == []
    assert all("carries no significance mark" not in u["detail"] for u in out.unknown)


def _partial_h4(sub_kind="subsample estimate", sub_sign="none", sub_marks="**"):
    full = _test("H4-T5C1", "0.034", "0.029", designated="yes", column="(1)")
    sub = _test("H4-T5C4", estimate=_est("0.071", "0.030", marks=sub_marks), term_kind=sub_kind,
                expected_sign=sub_sign, designated="no", column="(4)", sample="manufacturing only")
    return _row("H4", [full, sub], verdict="partially supported")


@pytest.mark.parametrize("kind,sign", [("subsample estimate", "none"), ("subsample estimate", "positive"),
                                       ("main effect", "positive")])
def test_partial_support_held_in_a_non_focal_cited_test_draws_no_hl3(kind, sign):
    out = _check(_ledger(_partial_h4(kind, sign)))
    assert _flags(out, "HL3") == [] and _flags(out, "HL5") == []


def test_partial_support_with_a_cited_test_not_computable_draws_no_hl3():
    full = _test("H4-T5C1", "0.034", "0.029")
    sub = _test("H4-T5C4", estimate=_est("", ""), term_kind="subsample estimate", expected_sign="none")
    out = _check(_ledger(_row("H4", [full, sub], verdict="partially supported")))
    assert _flags(out, "HL3") == []


def test_partial_support_is_flagged_when_every_cited_test_fails_focal_or_not():
    full = _test("H4-T5C1", "0.034", "0.029")
    sub = _test("H4-T5C4", "0.020", "0.030", term_kind="subsample estimate", expected_sign="none")
    (flag,) = _flags(_check(_ledger(_row("H4", [full, sub], verdict="partially supported"))), "HL3")
    assert len(flag["reasons"]) == 2


def test_partial_support_wrong_signed_focal_test_with_a_held_non_focal_test_draws_no_hl5():
    full = _test("H4-T5C1", "-0.034", "0.029")
    sub = _test("H4-T5C4", "0.071", "0.030", term_kind="subsample estimate", expected_sign="positive")
    out = _check(_ledger(_row("H4", [full, sub], verdict="partially supported")))
    assert _flags(out, "HL5") == []
    wrong = _test("H4-T5C4", "-0.071", "0.030", term_kind="subsample estimate", expected_sign="positive")
    assert _flags(_check(_ledger(_row("H4", [full, wrong], verdict="partially supported"))), "HL5")
    unsigned = _test("H4-T5C4", "0.071", "0.030", term_kind="subsample estimate", expected_sign="none")
    assert _flags(_check(_ledger(_row("H4", [full, unsigned], verdict="partially supported"))), "HL5") == []


def test_fixture_h4_with_a_subsample_column_draws_no_hl3():
    ledger = json.loads((FIXTURE / "ledger.json").read_text(encoding="utf-8"))
    (h4,) = [r for r in ledger["hypotheses"] if r["id"] == "H4"]
    for t in h4["tests"]:
        if t["column"] == "(4)":
            t["term_kind"], t["expected_sign"] = "subsample estimate", "none"
    out = _check(ledger, tables=FIXTURE / "tables")
    assert [f for f in out.flags if f["id"] == "H4"] == []


def _hl3_unknown(out):
    (u,) = [u for u in out.unknown if u["check"] == "HL3"]
    return u["detail"]


def test_tails_phrase_for_a_statistic_that_passes_only_one_tailed():
    out = _check(_ledger(_row("H1", [_test("H1-t1", "0.061", "0.035")]), tails="unstated"))
    assert TAILS in _hl3_unknown(out)


def test_printed_bound_at_the_level_has_its_own_reason():
    row = _row("H1", [_test("H1-t1", estimate=_est("0.30", "", p="<0.01"))], claimed_level="0.01")
    detail = _hl3_unknown(_check(_ledger(row, tails="unstated")))
    assert TAILS not in detail and "the printed bound '<0.01'" in detail


def test_rounding_straddle_has_its_own_reason():
    row = _row("H8", [_test("H8-t1", "-0.049", "0.025", expected_sign="negative")])
    detail = _hl3_unknown(_check(_ledger(row)))
    assert TAILS not in detail and "the printed digits straddle 0.05" in detail
    assert "two-sided: p 0.043 to 0.057" in detail


@pytest.mark.parametrize("tails", ["two", "unstated"])
def test_mark_at_the_level_under_a_silent_star_convention_has_its_own_reason(tmp_path, tails):
    out = _check(_ledger(_row("H1", [_marked("H1", "**")]), tails=tails), tables=_note_dir(tmp_path, STARS))
    detail = _hl3_unknown(out)
    assert TAILS not in detail and "does not say whether its marks are one- or two-sided" in detail


def test_mark_one_tailed_split_keeps_the_tails_phrase(tmp_path):
    note = STARS + " Two-tailed tests."
    out = _check(_ledger(_row("H1", [_marked("H1", "*")]), tails="unstated"), tables=_note_dir(tmp_path, note))
    assert TAILS in _hl3_unknown(out)
    stated = _check(_ledger(_row("H1", [_marked("H1", "*")]), tails="one"), tables=_note_dir(tmp_path, STARS))
    assert TAILS not in _hl3_unknown(stated)


def test_mark_range_straddle_has_its_own_reason(tmp_path):
    note = "* p<0.10, ** p<0.01. Two-tailed tests."
    out = _check(_ledger(_row("H1", [_marked("H1", "*")]), tails="two"), tables=_note_dir(tmp_path, note))
    detail = _hl3_unknown(out)
    assert TAILS not in detail and "the mark '*' puts p" in detail


def test_parentheses_ambiguity_does_not_carry_the_tails_phrase(tmp_path):
    row = _row("H1", [_test("H1-t1", "0.130", "1.95", cells=["table_03.csv:4:2"])])
    out = _check(_ledger(row, tails="unstated"), tables=_note_dir(tmp_path, "Values in parentheses."))
    detail = _hl3_unknown(out)
    assert "parentheses" in detail and TAILS not in detail


@pytest.mark.parametrize("x,level,shown", [(0.051, 0.05, "0.0510"), (0.0433, 0.05, "0.043"), (0.232, 0.05, "0.232"),
                                           (0.0549, 0.05, "0.0549"), (0.0551, 0.05, "0.055"), (0.104, 0.1, "0.1040"),
                                           (0.004, 0.05, "0.0040")])
def test_p_bounds_near_the_level_print_four_decimals(x, level, shown):
    assert CH._p(x, level) == shown
