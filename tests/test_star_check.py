from __future__ import annotations
import csv
import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/review/scripts"
sys.path.insert(0, str(SCRIPTS))
import pvalues  # noqa: E402
import verify_arithmetic as va  # noqa: E402


def _write(p, rows):
    with open(p, "w", newline="") as f:
        csv.writer(f).writerows(rows)


# --- Task 11: the shared p-value module and t_vs_p with rounding bounds ---

def test_p_values_under_the_normal_and_student_t():
    assert pvalues.p_student(2.228, 10) == pytest.approx(0.0500, abs=5e-4)
    assert pvalues.p_student(2.086, 20) == pytest.approx(0.0500, abs=5e-4)
    assert pvalues.p_student(2.5, 5) == pytest.approx(0.05449, abs=5e-5)
    assert pvalues.p_student(1.0, 1) == pytest.approx(0.5, abs=1e-9)
    assert pvalues.p_student(0.0, 5) == 1.0 and pvalues.p_student(math.inf, 5) == 0.0
    assert pvalues.p_normal(1.959964) == pytest.approx(0.05, abs=1e-6) and pvalues.p_normal(math.inf) == 0.0


def test_rounding_bounds_come_from_the_printed_digits():
    lo, hi = pvalues.abs_t_bounds("0.084", "0.047")
    assert (lo, hi) == (pytest.approx(0.0835 / 0.0475), pytest.approx(0.0845 / 0.0465))
    assert pvalues.abs_t_bounds("-0.084", "0.047") == (lo, hi)
    assert pvalues.abs_t_bounds("0.01", "0.02") == (pytest.approx(0.2), pytest.approx(1.0))
    assert pvalues.abs_t_bounds("0.01", "0.0") is None and pvalues.abs_t_bounds("x", "0.1") is None
    assert pvalues.abs_t_bounds_from_t("2.10") == (pytest.approx(2.095), pytest.approx(2.105))
    assert pvalues.parse_printed("−0.5") == (-0.5, pytest.approx(0.05))


def test_printed_p_range_and_one_tailed_halving():
    assert pvalues.printed_p_range("< .001") == (0.0, 0.001)
    assert pvalues.printed_p_range("0.12") == (pytest.approx(0.115), pytest.approx(0.125))
    assert pvalues.printed_p_range(".000") == (0.0, pytest.approx(0.0005))
    assert pvalues.printed_p_range("n.s.") is None
    two = pvalues.p_range(1.7579, 1.8172)
    one = pvalues.p_range(1.7579, 1.8172, one_tailed=True)
    assert one == (pytest.approx(two[0] / 2), pytest.approx(two[1] / 2))
    assert two == (pytest.approx(0.0692, abs=1e-4), pytest.approx(0.0788, abs=1e-4))


def test_pack_scripts_can_import_the_module(tmp_path):
    # Run the documented import line as a pack script would, from packs/nonlinear/scripts/.
    script = ROOT / "packs" / "nonlinear" / "scripts" / "_import_probe.py"
    code = ("import sys\nfrom pathlib import Path\n"
            "sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'skills' / 'review' / 'scripts'))\n"
            "import pvalues\nprint(round(pvalues.p_student(2.5, 5), 4))\n")
    assert 'parents[3] / "skills" / "review" / "scripts"' in pvalues.__doc__
    script.write_text(code)
    try:
        r = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, cwd=tmp_path)
    finally:
        script.unlink()
    assert r.returncode == 0 and r.stdout.strip() == "0.0545", r.stderr


def _t_vs_p_errors(tmp_path, coef, se, p, one_tailed=()):
    d = tmp_path / "t"
    d.mkdir(exist_ok=True)
    _write(d / "table_01.csv", [["Variables", "Coef", "SE", "p"], ["x", coef, se, p]])
    t = va.parse_table_csv(d / "table_01.csv")
    return [f for f in va.run_checks({"table_01.csv": t}, one_tailed) if f["check"] == "t_vs_p" and f["status"] == "error"]


def test_t_vs_p_allows_a_small_df_and_rounding(tmp_path):
    # 0.05 (0.03) with p 0.12 is right under t(20); the normal alone would give 0.096.
    assert _t_vs_p_errors(tmp_path, "0.05", "0.03", "0.12") == []
    assert _t_vs_p_errors(tmp_path, "0.30", "0.05", ".000") == []
    assert _t_vs_p_errors(tmp_path, "0.20**", "(0.10)", "0.05") == []


@pytest.mark.parametrize("coef,se,p", [("1.500", "1.000", "0.12"), ("0.150", "0.100", "0.12"),
                                       ("2.000", "1.000", "0.035"), ("0.500", "0.200", "0.005"),
                                       ("3.00", "1.00", "0.001")])
def test_t_vs_p_adds_no_flag_the_old_rule_did_not_raise(tmp_path, coef, se, p):
    assert _t_vs_p_errors(tmp_path, coef, se, p) == []


def test_t_vs_p_accepts_a_p_only_student_t_with_1_df_allows(tmp_path):
    # |t| 1.286 to 2.200: the normal allows p up to 0.199, t(1) up to 0.421; the old rule flags p 0.30.
    assert _t_vs_p_errors(tmp_path, "0.05", "0.03", "0.30") == []
    assert _t_vs_p_errors(tmp_path, "0.05", "0.03", "0.50")


def test_t_vs_p_honors_a_one_tailed_note(tmp_path):
    # 0.20 (0.10) with p 0.020: too small for a two-sided p (at least 0.031), right for one-tailed.
    assert _t_vs_p_errors(tmp_path, "0.20", "0.10", "0.020")
    assert _t_vs_p_errors(tmp_path, "0.20", "0.10", "0.020", one_tailed={"table_01.csv"}) == []


def test_t_vs_p_still_flags_a_printed_p_no_reference_allows(tmp_path):
    bad = _t_vs_p_errors(tmp_path, "0.50", "0.25", "0.99")
    assert len(bad) == 1 and "printed p=0.99" in bad[0]["detail"]
    assert _t_vs_p_errors(tmp_path, "0.02", "0.10", "0.001")  # printed p far below what t = 0.2 allows


# --- Task 11 fix round 1: inequality and scientific p-values never raise a number flag ---

@pytest.mark.parametrize("coef,se,p", [("3.00", "0.10", "≤ 0.05"), ("3.00", "0.10", "p < 0.05"),
                                       ("0.02", "0.10", "> 0.10"), ("0.02", "0.10", ">.10"),
                                       ("3.00", "0.10", "1e-5"), ("3.00", "0.10", "0.001***")])
def test_t_vs_p_skips_inequality_and_scientific_p(tmp_path, coef, se, p):
    assert _t_vs_p_errors(tmp_path, coef, se, p) == []


def test_t_vs_p_t_column_skips_inequality_p(tmp_path):
    d = tmp_path / "tc"
    d.mkdir()
    _write(d / "table_01.csv", [["Variables", "Coef", "t", "p"], ["x", "0.05", "0.20", "> 0.10"]])
    t = va.parse_table_csv(d / "table_01.csv")
    assert [f for f in va.run_checks({"table_01.csv": t}) if f["check"] == "t_vs_p" and f["status"] == "error"] == []


def test_t_vs_p_still_flags_a_genuine_error(tmp_path):
    assert _t_vs_p_errors(tmp_path, "0.02", "0.10", "0.02")


def test_printed_p_range_inequalities_and_non_p():
    assert pvalues.printed_p_range("≤ 0.05") == (0.0, 0.05)
    assert pvalues.printed_p_range("<= 0.05") == (0.0, 0.05)
    assert pvalues.printed_p_range("p < 0.05") == (0.0, 0.05)
    assert pvalues.printed_p_range("p ≤ 0.05") == (0.0, 0.05)
    assert pvalues.printed_p_range("> 0.10") == (0.10, 1.0)
    assert pvalues.printed_p_range(">= 0.10") == (0.10, 1.0)
    assert pvalues.printed_p_range("≥ 0.10") == (0.10, 1.0)
    for bad in ("1e-5", "-0.2", "1.5", "> 2", "n.s."):
        assert pvalues.printed_p_range(bad) is None


def test_p_student_rejects_bad_df_and_infinite_df_is_normal():
    for df in (0, -1, math.nan):
        with pytest.raises(ValueError):
            pvalues.p_student(2.0, df)
    assert pvalues.p_student(2.0, math.inf) == pytest.approx(pvalues.p_normal(2.0))


def test_one_tailed_note_wording():
    for txt in ("one-tail test", "one tail tests", "single-tailed", "One-sided", "one-tailed"):
        assert va._ONE_TAILED.search(txt), txt
    assert not va._ONE_TAILED.search("two-tailed tests")


def test_wide_layout_raw_uses_last_column_of_group(tmp_path):
    d = tmp_path / "w"
    d.mkdir()
    _write(d / "table_01.csv", [["Variables", "coef_m1", "se_m1", "p_m1", "coef_m2", "se_m2", "p_m2"],
                                ["x", "0.05", "0.03", "0.12", "0.06", "0.03", "0.10"]])
    t = va.parse_table_csv(d / "table_01.csv")
    assert t["rows"][0]["_raw"]["1"] == {"coef": "0.05", "se": "0.03", "p": "0.12", "t": None}


# --- Task 12: table notes are copied and compared ---

CT = SCRIPTS / "compare_transcriptions.py"


def _two_readings(tmp_path, note_a, note_b):
    a, b, out = tmp_path / "a", tmp_path / "b", tmp_path / "out"
    a.mkdir(); b.mkdir()
    for d, note in ((a, note_a), (b, note_b)):
        _write(d / "table_01.csv", [["", "(1)"], ["x", "0.26**"], ["", "(0.07)"]])
        if note is not None:
            (d / "table_01_note.txt").write_text(note)
    r = subprocess.run([sys.executable, str(CT), str(a), str(b), str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return out, json.loads((out / "disagreements.json").read_text())


def test_agreed_note_is_written_beside_the_table(tmp_path):
    out, dis = _two_readings(tmp_path, "* p < .05. Standard errors\nin parentheses.\n",
                             "* p < .05.  Standard errors in parentheses.")
    assert dis == []
    assert (out / "table_01_note.txt").read_text() == "* p < .05. Standard errors\nin parentheses.\n"
    assert (out / "table_01.csv").exists()


def test_disagreeing_notes_are_recorded_and_not_written(tmp_path):
    out, dis = _two_readings(tmp_path, "* p < .05.", "* p < .10.")
    assert dis == [{"table": "table_01.csv", "row": None, "col": None, "a": "* p < .05.", "b": "* p < .10.",
                    "reason": "note", "whole_table": False}]
    assert not (out / "table_01_note.txt").exists() and (out / "table_01.csv").exists()


def test_no_note_files_change_nothing(tmp_path):
    out, dis = _two_readings(tmp_path, None, None)
    assert dis == [] and not (out / "table_01_note.txt").exists()


def test_transcribers_copy_the_note_and_stage_1_does_not_ask_about_it():
    tr = (ROOT / "skills/review/agents/table-transcriber.md").read_text()
    assert "table_NN_note.txt" in tr and "word for word" in tr and "write an empty file" in tr
    assert "the table's title line" in tr
    s1 = (ROOT / "skills/review/stages/stage-1-verify.md").read_text()
    step1 = s1.split("\n1. ", 1)[1].split("\n2. ", 1)[0]
    assert "`table_NN_note.txt`" in step1 and "reason `note`" in step1
    assert "Entries with reason `note` are not asked" in s1


# --- Task 13: reading the note ---

LEGENDS = [
    ("* p < 0.10, ** p < 0.05, *** p < 0.01. Standard errors in parentheses.", {"*": 0.1, "**": 0.05, "***": 0.01}),
    ("+ p < .10; * p < .05; ** p < .01; *** p < .001. Robust standard errors clustered by firm in parentheses.",
     {"+": 0.1, "*": 0.05, "**": 0.01, "***": 0.001}),
    ("***, **, and * denote significance at the 1%, 5%, and 10% levels, respectively. Standard errors are in "
     "parentheses.", {"***": 0.01, "**": 0.05, "*": 0.1}),
    ("* significant at 10%; ** significant at 5%; *** significant at 1%. Standard errors in parentheses.",
     {"*": 0.1, "**": 0.05, "***": 0.01}),
    ("† p < .10; * p < .05. Standard errors in parentheses.", {"†": 0.1, "*": 0.05}),
    ("*p<.05 **p<.01 ***p<.001. Numbers in parentheses are standard errors.", {"*": 0.05, "**": 0.01, "***": 0.001}),
]


@pytest.mark.parametrize("note,markers", LEGENDS, ids=["p-list", "plus-first", "respectively", "percent",
                                                       "dagger", "no-separators"])
def test_parse_note_reads_common_keys(note, markers):
    s = va.parse_note(note)
    assert s["skip_reason"] is None and s["markers"] == markers and s["value_rows"] == {"(": "se"}


VALUE_ROWS = [
    ("* p < .05. t statistics in parentheses.", {"(": "t"}),
    ("* p < .05. t-statistics based on robust standard errors in parentheses.", {"(": "t"}),
    ("* p < .05. Numbers in parentheses are t-values.", {"(": "t"}),
    ("* p < .05. Standard errors in parentheses; p-values in brackets.", {"(": "se", "[": "p"}),
]


@pytest.mark.parametrize("note,rows", VALUE_ROWS, ids=["t", "t-based-on-se", "t-values", "se-and-p"])
def test_parse_note_reads_what_the_parentheses_hold(note, rows):
    assert va.parse_note(note)["value_rows"] == rows


SKIPS = [
    ("", "no table note"),
    ("Standard errors in parentheses.", "no key to the marks"),
    ("* p < .05; * p < .01. Standard errors in parentheses.", "inconsistent"),
    ("* p < .05. Standard errors and t-statistics in parentheses.", "does not say clearly"),
    ("* p < .05. Standard deviations in parentheses.", "does not say the parentheses hold"),
    ("Odds ratios reported. * p < .05. Standard errors in parentheses.", "odds ratios"),
    ("Standardized coefficients; standard errors in parentheses. * p < .05.", "standardized coefficients"),
    ("* p < .05 from 1,000 bootstrap replications. Standard errors in parentheses.", "bootstrapped"),
    ("* p < .05 after Holm correction. Standard errors in parentheses.", "adjusted p-values"),
    ("Average marginal effects. * p < .05. Standard errors in parentheses.", "marginal effects"),
    ("* p < .05. Robust standard errors clustered by firm. p-values in parentheses.", "does not say the parentheses hold"),
    ("* p < .05. p-values in parentheses are based on robust standard errors.", "does not say the parentheses hold"),
    ("* p < .05. 95% confidence intervals in brackets.", "does not say the parentheses hold"),
]


@pytest.mark.parametrize("note,reason", SKIPS, ids=["empty", "no-key", "conflict", "ambiguous", "sd",
                                                    "odds", "standardized", "bootstrap", "holm", "margins",
                                                    "p-values-after-se", "p-values-based-on-se", "intervals"])
def test_parse_note_skips_what_it_cannot_read(note, reason):
    assert reason in va.parse_note(note)["skip_reason"]


def test_unstandardized_coefficients_are_not_skipped():
    s = va.parse_note("Unstandardized coefficients. * p < .05. Standard errors in parentheses.")
    assert s["skip_reason"] is None and s["value_rows"] == {"(": "se"}


def test_parse_note_reads_tails():
    assert va.parse_note("One-tailed tests for hypothesized effects. * p < .05. "
                         "Standard errors in parentheses.")["tails"] == "one"
    assert va.parse_note("* p < .05 (two-tailed). Standard errors in parentheses.")["tails"] == "two"
    assert va.parse_note("* p < .05. Standard errors in parentheses.")["tails"] == "unstated"


# --- Task 13 fix round 1: skip any key that cannot be fully paired ---

UNPAIRED_KEYS = [
    "** and * indicate significance at the 1% and 5% levels. SEs in parentheses.",
    "*, **, and *** indicate significance at the 10%, 5%, and 1% levels. Standard errors in parentheses.",
    "* and ** indicate significance at 5% and 1% levels. Standard errors in parentheses.",
    "p<.05 * p<.01 ** p<.001 ***. Standard errors in parentheses.",
]


@pytest.mark.parametrize("note", UNPAIRED_KEYS, ids=["reversed", "list-of-three", "list-of-two", "mark-after"])
def test_parse_note_skips_a_key_it_cannot_fully_pair(note):
    s = va.parse_note(note)
    assert "key not read" in s["skip_reason"]


def test_significance_levels_in_parentheses_are_not_standard_errors():
    s = va.parse_note("* p < .05. Standard errors clustered by firm, marginal significance levels in parentheses.")
    assert s["value_rows"].get("(") != "se" and s["skip_reason"] is not None


@pytest.mark.parametrize("note,reason", [
    ("* p < .05. Relative risk ratios. Standard errors in parentheses.", "relative risk"),
    ("* p < .05. Coefficients are exp(b). Standard errors in parentheses.", "exponentiated"),
    ("* p < .05. Coefficients are e^b. Standard errors in parentheses.", "exponentiated"),
    ("* p < .05. Standardized regression coefficients. Standard errors in parentheses.", "standardized"),
], ids=["rrr", "exp-b", "e-to-b", "standardized-regression"])
def test_parse_note_skips_more_transformed_estimates(note, reason):
    assert reason in va.parse_note(note)["skip_reason"]


def test_probability_in_a_model_name_is_not_a_p_value():
    s = va.parse_note("* p < .05. Linear probability models with robust standard errors in parentheses.")
    assert s["skip_reason"] is None and s["value_rows"] == {"(": "se"}


def test_comma_joined_value_rows_are_read():
    s = va.parse_note("* p < .05. Standard errors in parentheses, t-statistics in brackets.")
    assert s["skip_reason"] is None and s["value_rows"] == {"(": "se", "[": "t"}


def test_footnote_marks_that_are_not_significance_are_not_thresholds():
    s = va.parse_note("* p < .05. † Winsorized at the 1% level. Standard errors in parentheses.")
    assert s["markers"] == {"*": 0.05} and s["skip_reason"] is None


def test_letter_marks_are_ignored():
    s = va.parse_note("* p < .05. a Winsorized at the 1% level. b Firm-level. Standard errors in parentheses.")
    assert s["markers"] == {"*": 0.05} and s["skip_reason"] is None


# --- Task 13 fix round 2: two kinds named for the same parentheses ---

@pytest.mark.parametrize("note", [
    "* p < .05. Standard errors are clustered at the firm level, and values in parentheses are t-values.",
    "* p < .05. Robust standard errors clustered by firm, with figures in parentheses being z-statistics.",
    "* p < .05. Standard errors clustered by firm, and the numbers in parentheses are absolute t statistics.",
], ids=["t-values", "z-statistics", "absolute-t"])
def test_parse_note_skips_when_two_kinds_are_named_for_one_set(note):
    s = va.parse_note(note)
    assert s["skip_reason"] is not None and s["value_rows"] == {}


@pytest.mark.parametrize("note", [
    "Significance levels: * 10%, ** 5%, *** 1%. Standard errors in parentheses.",
    "Significant at: * 10%; ** 5%; *** 1%, respectively. Standard errors in parentheses.",
    "* p < 5%, ** p < 1%. Standard errors in parentheses.",
], ids=["levels-colon", "significant-at", "p-percent"])
def test_parse_note_skips_percent_forms_it_does_not_pair(note):
    s = va.parse_note(note)
    assert s["skip_reason"] is not None and s["markers"] == {}


@pytest.mark.parametrize("footnote,mark", [
    ("Models include + 1% winsorizing.", "+"),
    ("Top-coded at \u2020 1%.", "\u2020"),
    ("\u2020 25% of firms dropped.", "\u2020"),
    ("+ 50% sample split.", "+"),
    ("Coefficients significant at conventional levels. \u2020 5% subsample.", "\u2020"),
], ids=["winsorizing", "top-coded", "dropped", "split", "subsample"])
def test_footnote_marks_next_to_percents_are_never_thresholds(footnote, mark):
    for note in (footnote + " Standard errors in parentheses.",
                 "* p < .05. " + footnote + " Standard errors in parentheses."):
        assert mark not in va.parse_note(note)["markers"]

# --- Task 14: checking each mark ---

KEY = "* p < 0.10, ** p < 0.05, *** p < 0.01. Standard errors in parentheses."


def _stars(rows, note=KEY):
    return va.check_stars("table_03.csv", [["Variables", "(1)", "(2)"]] + rows, note)


def test_over_starred_coefficient_is_flagged_with_its_one_tailed_reading():
    [f] = _stars([["Firm size", "0.10", "0.084**"], ["", "(0.20)", "(0.047)"]])
    assert f["status"] == "error" and f["cell"] == "Firm size / (2)"
    assert f["detail"] == ("|t| 1.758 to 1.817, p 0.069 to 0.079 (two-sided, normal); printed ** needs p <= 0.05; "
                           "a one-tailed test, which the note does not state, would give p 0.035 to 0.039")


def test_a_stated_one_tailed_test_is_honored():
    note = "One-tailed tests. " + KEY
    assert _stars([["Firm size", "0.084**"], ["", "(0.047)"]], note) == []


def test_rounding_keeps_a_mark_the_printed_digits_allow():
    # 0.048 / 0.025 = 1.92 gives p 0.055, but the digits allow p down to 0.0477.
    assert _stars([["x", "0.048**"], ["", "(0.025)"]]) == []
    assert _stars([["x", "0.046**"], ["", "(0.020)"]]) == []
    assert _stars([["x", "-0.084*"], ["", "(0.047)"]]) == []


def test_t_statistics_in_parentheses_are_not_read_as_standard_errors():
    rows = [["x", "0.084**"], ["", "(2.10)"]]
    assert _stars(rows, "* p < 0.10, ** p < 0.05. t statistics in parentheses.") == []
    assert _stars(rows)[0]["status"] == "error"


def test_missing_or_weaker_marks_are_never_flagged():
    assert _stars([["x", "0.52"], ["", "(0.15)"]]) == []
    assert _stars([["x", "0.52*"], ["", "(0.15)"]]) == []


def test_a_mark_on_the_value_cell_is_read():
    [f] = _stars([["x", "0.084"], ["", "(0.047)**"]])
    assert f["status"] == "error"


def test_an_unknown_mark_is_not_computable():
    [f] = _stars([["x", "0.084\u2020"], ["", "(0.047)"]])
    assert f["status"] == "not_computable" and "'\u2020'" in f["detail"]


def test_a_trailing_letter_is_a_footnote_not_a_mark():
    assert _stars([["x", "0.12a"], ["", "(0.047)"]]) == []
    assert _stars([["x", "0.12b (0.047)"]]) == []
    assert _stars([["x", "0.046**a"], ["", "(0.020)"]]) == []
    [f] = _stars([["x", "0.084**a"], ["", "(0.047)"]])
    assert f["status"] == "error"


def test_a_mixed_tail_note_only_loosens_the_check():
    note = "Two-tailed tests for controls, one-tailed for hypotheses. " + KEY
    assert _stars([["x", "0.084**"], ["", "(0.047)"]], note) == []
    [f] = _stars([["x", "0.05**"], ["", "(0.047)"]], note)
    assert f["status"] == "error"


def test_tables_the_note_rules_out_are_skipped():
    [f] = _stars([["x", "0.98***"], ["", "(0.60)"]], "Odds ratios. " + KEY)
    assert f["status"] == "not_computable" and "odds ratios" in f["detail"]
    [f] = _stars([["x", "0.084**"], ["", "(0.047)"]], "")
    assert f["status"] == "not_computable" and "no table note" in f["detail"]


def test_ratios_named_only_in_the_header_or_title_are_skipped():
    rows = [["Variables", "Odds ratio"], ["x", "0.10***"], ["", "(0.05)"]]
    [f] = va.check_stars("t.csv", rows, "Logit models. " + KEY)
    assert f["status"] == "not_computable" and "odds ratios" in f["detail"]
    rows = [["Variables", "(1)"], ["x", "0.10***"], ["", "(0.05)"]]
    [f] = va.check_stars("t.csv", rows, "Table 3. Logit models of entry (odds ratios). " + KEY)
    assert "odds ratios" in f["detail"]


def test_abnormal_return_mean_tables_are_left_to_the_market_event_pack():
    rows = [["Window", "Mean CAR"], ["(-1, +1)", "0.41**"], ["", "(5.90)"]]
    [f] = va.check_stars("table_05.csv", rows, "t-statistics in parentheses. ** p < .05")
    assert f["status"] == "not_computable" and "market-event overlay" in f["detail"]


def test_event_study_bins_without_car_are_checked():
    rows = [["Event time", "(1)"], ["[-3, -1]", "0.084**"], ["", "(0.047)"]]
    [f] = va.check_stars("t.csv", rows, KEY)
    assert f["status"] == "error"


def test_a_coefficient_and_its_standard_error_in_one_cell_are_read():
    [f] = _stars([["Firm size", "0.10", "0.084** (0.047)"]])
    assert f["status"] == "error" and f["cell"] == "Firm size / (2)"
    assert _stars([["Firm size", "0.046** (0.020)"]]) == []


def test_marks_in_a_layout_not_read_are_counted_as_skipped():
    assert _stars([["x", "0.084"], ["", "(0.047)"]], "") == []
    [f] = va.check_stars("t.csv", [["", "A", "B"], ["A", "1", ""], ["B", "0.30*", "1"]], KEY)
    assert f["status"] == "not_computable" and "layout not read" in f["detail"]
    rows = [["Variables", "Coef", "SE"], ["x", "0.084**", "0.047"]]
    assert "layout not read" in va.check_stars("t.csv", rows, KEY)[0]["detail"]


def test_cli_reports_star_flags_and_skips(tmp_path):
    d = tmp_path / "extracted_tables"
    d.mkdir()
    _write(d / "table_03.csv", [["Variables", "(1)"], ["Firm size", "0.084**"], ["", "(0.047)"]])
    (d / "table_03_note.txt").write_text(KEY + "\n")
    _write(d / "table_04.csv", [["Variables", "(1)"], ["Age", "0.30*"], ["", "(0.10)"]])
    out = tmp_path / "arithmetic.md"
    r = subprocess.run([sys.executable, str(SCRIPTS / "verify_arithmetic.py"), str(d), str(out)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    text = out.read_text()
    assert text.startswith("VERDICT: ERRORS_FOUND")
    assert "- [ERROR] stars_vs_se table_03.csv (Firm size / (1)): |t| 1.758 to 1.817" in text
    assert "- [NOT_COMPUTABLE] stars_vs_se table_04.csv (-): star check skipped: no table note" in text


def test_stage_1_logs_skipped_star_checks_and_numeric_fidelity_reads_stars_flags():
    s1 = (ROOT / "skills/review/stages/stage-1-verify.md").read_text()
    step2 = s1.split("\n2. ", 1)[1].split("\n3. ", 1)[0]
    assert "significance mark" in step2 and "never guessed" in step2
    assert '\'{"check":"stars_vs_se","skipped":<n>,"report":"stage-1/arithmetic.md"}\'' in step2
    nf = (ROOT / "skills/review/agents/numeric-fidelity.md").read_text()
    assert "For a `stars_vs_se` flag" in nf and "one-tailed tests" in nf and "BENIGN MISMATCH" in nf


def test_round_2_recommends_dropping_a_star_flag_numeric_fidelity_rates_benign():
    s1 = (ROOT / "skills/review/stages/stage-1-verify.md").read_text()
    assert '"C. The paper states one-tailed tests or another source for the marks (Recommended)"' in s1
    assert "take the recommended option for every question in both rounds (A, or C for a star flag" in s1
    assert "each `stars_vs_se` flag answered C" in s1 and "items answered B or C" in s1


def test_a_star_flag_answered_c_is_dropped_from_the_outputs(tmp_path):
    from plumb import checkin, validated
    ws = tmp_path / "ws"
    (ws / "stage-1").mkdir(parents=True)
    (ws / "run.json").write_text(json.dumps({"depth": "quick", "issues_list_mode": "facts_only"}))
    item = "numbers:arith:table_03.csv:Firm size / (1):stars_vs_se"
    flag = {"item": item, "kind": "number", "title": "Stars", "summary": "A star claims too much.",
            "excerpt": None, "ms_page": 4}
    (ws / "stage-1" / "flags.json").write_text(json.dumps([flag]))
    (ws / "stage-1" / "unverified_numbers.md").write_text("")
    checkin.record(ws, "numbers", item, "C. The paper states one-tailed tests or another source for the marks (Recommended)",
                   "C. The paper states one-tailed tests or another source for the marks (Recommended)")
    kept, dropped = validated.build(ws)
    assert kept == [] and dropped[0]["reason"] == "the paper states one-tailed tests or another source for the marks"


# --- Task 14 fix round 1 ---

def test_car_window_columns_with_subsample_rows_are_skipped_but_car_regressions_are_checked():
    rows = [["", "CAR(-1,+1)", "CAR(0,+5)"], ["Full sample", "0.41**", "0.30*"], ["", "(0.20)", "(0.17)"]]
    [f] = va.check_stars("t.csv", rows, KEY)
    assert f["status"] == "not_computable" and "market-event overlay" in f["detail"]
    rows = [["Variables", "CAR"], ["Size", "0.084**"], ["", "(0.047)"], ["Constant", "0.1"], ["", "(0.05)"],
            ["Observations", "500"]]
    assert va.check_stars("t.csv", rows, KEY)[0]["status"] == "error"


def test_a_car_regression_without_a_constant_row_is_checked():
    # Final fix B1: Observations and Adj. R² rows mark a regression body even with no Constant row.
    rows = [["Variables", "CAR[-1,+1]"], ["Size", "0.084**"], ["", "(0.047)"], ["Leverage", "0.020"],
            ["", "(0.030)"], ["Observations", "500"], ["Adj. R²", "0.04"]]
    assert va._is_car_mean_table(rows, KEY) is False
    assert va.check_stars("t.csv", rows, KEY)[0]["status"] == "error"


def test_a_note_that_is_not_utf8_is_read_with_replacement(tmp_path):
    d = tmp_path / "extracted_tables"
    d.mkdir()
    _write(d / "table_03.csv", [["Variables", "(1)"], ["Firm size", "0.084**"], ["", "(0.047)"]])
    (d / "table_03_note.txt").write_bytes(KEY.encode() + b" caf\xe9\n")
    out = tmp_path / "arithmetic.md"
    subprocess.run([sys.executable, str(SCRIPTS / "verify_arithmetic.py"), str(d), str(out)], check=True)
    assert "stars_vs_se table_03.csv (Firm size / (1))" in out.read_text()


def test_stage_1_says_skipped_counts_tables_and_the_labels_match():
    s1 = (ROOT / "skills/review/stages/stage-1-verify.md").read_text()
    assert "counts tables" in s1
    nf = (ROOT / "skills/review/agents/numeric-fidelity.md").read_text()
    assert "BENIGN]" not in nf


def test_esttab_note_with_parentheses_and_brackets_parses():
    note = "* p < 0.10, ** p < 0.05, *** p < 0.01. Standard errors in parentheses and p-values in brackets."
    s = va.parse_note(note)
    assert s["skip_reason"] is None and s["value_rows"]["("] == "se"
    assert va.parse_note("t statistics in parentheses and standard errors in parentheses. " + KEY)["skip_reason"]


def test_thousands_commas_and_percent_cells():
    [f] = _stars([["x", "1,234.5*"], ["", "(1,000.0)"]]) or [{"status": "none"}]
    assert f["status"] in ("none", "error")
    r = _stars([["x", "8.4%**"], ["", "(0.047)"]])
    assert all("'%" not in x["detail"] for x in r)
    [f] = _stars([["x", "1,234.5***"], ["", "(1.0)"]]) or [{"status": "none"}]
    assert "mark '," not in str(f)


# --- Task 14 fix round 2 ---

@pytest.mark.parametrize("note", [
    "Parentheses and brackets report standard errors and t statistics.",
    "In parentheses and brackets are standard errors and t-statistics, respectively.",
    "Reported in parentheses and brackets: standard errors and t-statistics.",
])
def test_two_delimiters_with_two_kinds_are_skipped(note):
    full = "* p < 0.10, ** p < 0.05, *** p < 0.01. " + note
    rows = [["V", "(1)"], ["x", "0.084**"], ["", "[1.79]"]]
    assert va.parse_note(full)["value_rows"].get("[") != "se"
    assert all(f["status"] == "not_computable" for f in va.check_stars("t.csv", rows, full))


def test_and_still_splits_between_delimiters():
    k = "* p < 0.10, ** p < 0.05, *** p < 0.01. "
    s = va.parse_note(k + "Robust standard errors in parentheses and t statistics in brackets.")
    assert s["value_rows"] == {"(": "se", "[": "t"}
    s = va.parse_note(k + "Standard errors in parentheses and p-values in brackets.")
    assert s["skip_reason"] is None and s["value_rows"]["("] == "se"


def test_car_mean_table_with_n_row_is_skipped_and_regression_with_constant_is_checked():
    rows = [["", "CAR(-1,+1)", "CAR(0,+5)"], ["Full sample", "0.41**", "0.3"], ["", "(1.70)", "(1.2)"],
            ["N", "250", "250"]]
    assert "market-event overlay" in va.check_stars("t.csv", rows, KEY)[0]["detail"]
    rows = [["V", "CAR"], ["Size", "0.084**"], ["", "(0.047)"], ["Constant", "0.1"], ["", "(0.05)"], ["N", "5"]]
    assert va.check_stars("t.csv", rows, KEY)[0]["status"] == "error"


def test_comma_strip_leaves_window_labels_alone():
    assert va._clean("(-1,+1)") == "(-1,+1)" and va._clean("[0,5]") == "[0,5]"
    assert va._clean("1,234.5***") == "1234.5***" and va._clean("(1,000.0)") == "(1000.0)"


def test_dropped_percent_pairs_are_counted():
    rows = [["V", "(1)", "(2)"], ["x", "0.084**", "8.4%**"], ["", "(0.047)", "(0.5)"]]
    fs = va.check_stars("t.csv", rows, KEY)
    assert [f["status"] for f in fs] == ["error", "not_computable"]
    assert "1 percentage" in fs[1]["detail"]


# --- Final fix wave: stale notes, scientific notation, open-ended p ranges ---

def _reading(d, rows, note):
    d.mkdir(exist_ok=True)
    _write(d / "table_01.csv", rows)
    n = d / "table_01_note.txt"
    if note is None:
        if n.exists():
            n.unlink()
    else:
        n.write_text(note)


_STALE_ROWS = [["", "(1)"], ["x", "0.26**"], ["", "(0.20)"]]


@pytest.mark.parametrize("case", ["disagree", "no_note", "shape", "missing"])
def test_a_rerun_that_writes_no_note_removes_the_old_one(tmp_path, case):
    a, b, out = tmp_path / "a", tmp_path / "b", tmp_path / "out"
    for d in (a, b):
        _reading(d, _STALE_ROWS, "** p < .05. Standard errors in parentheses.")
    subprocess.run([sys.executable, str(CT), str(a), str(b), str(out)], check=True, capture_output=True)
    assert (out / "table_01_note.txt").exists()
    if case == "disagree":
        _reading(b, _STALE_ROWS, "** p < .01. Standard errors in parentheses.")
    elif case == "no_note":
        _reading(a, _STALE_ROWS, None)
        _reading(b, _STALE_ROWS, None)
    elif case == "shape":
        _reading(b, _STALE_ROWS + [["y", "0.1"]], "** p < .05. Standard errors in parentheses.")
    else:
        (b / "table_01.csv").unlink()
    subprocess.run([sys.executable, str(CT), str(a), str(b), str(out)], check=True, capture_output=True)
    assert not (out / "table_01_note.txt").exists()
    report = tmp_path / "va.md"
    subprocess.run([sys.executable, str(SCRIPTS / "verify_arithmetic.py"), str(out), str(report)],
                   check=True, capture_output=True)
    assert not [ln for ln in report.read_text().splitlines() if "[ERROR] stars_vs_se" in ln]


def test_printed_lookahead_rejects_a_decimal_or_exponent_tail():
    assert va._printed("1.96e-3") is None
    assert va._printed("9.8e-4") is None
    assert va._printed("0.26**") == "0.26"


@pytest.mark.parametrize("coef,se,p", [("1.96e-3", "9.8e-4", "0.045"), ("0.02", "0.10", "4.5E-2"),
                                       ("1.96E+0", "0.98", "0.02")])
def test_t_vs_p_skips_scientific_cells(tmp_path, coef, se, p):
    assert _t_vs_p_errors(tmp_path, coef, se, p) == []


def test_t_vs_p_t_column_skips_scientific_cells(tmp_path):
    d = tmp_path / "tc"
    d.mkdir()
    _write(d / "table_01.csv", [["Variables", "Coef", "t", "p"], ["x", "0.05", "2.0e-1", "0.001"]])
    t = va.parse_table_csv(d / "table_01.csv")
    found = [f for f in va.run_checks({"table_01.csv": t}) if f["check"] == "t_vs_p"]
    assert [f for f in found if f["status"] == "error"] == []
    assert [f["status"] for f in found] == ["not_computable"]


def test_printed_p_range_open_ended_bounds_that_cover_everything_are_none():
    for text in ("< 0", "<= 0", "< 0.0", "\u2264 0", "> 1", ">= 1", "> 1.0", "\u2265 1"):
        assert pvalues.printed_p_range(text) is None, text
    assert pvalues.printed_p_range("< 0.001") == (0.0, 0.001)
    assert pvalues.printed_p_range("> 0.99") == (0.99, 1.0)


@pytest.mark.parametrize("case", ["shape", "missing"])
def test_a_rerun_never_leaves_a_stale_agreed_table(tmp_path, case):
    a, b, out = tmp_path / "a", tmp_path / "b", tmp_path / "out"
    rows = [["Variables", "Coef", "SE", "p"], ["x", "0.02", "0.10", "0.02"]]
    for d in (a, b):
        _reading(d, rows, None)
    subprocess.run([sys.executable, str(CT), str(a), str(b), str(out)], check=True, capture_output=True)
    assert (out / "table_01.csv").exists()
    if case == "shape":
        _reading(b, rows + [["y", "0.1", "0.1", "0.3"]], None)
    else:
        (b / "table_01.csv").unlink()
    subprocess.run([sys.executable, str(CT), str(a), str(b), str(out)], check=True, capture_output=True)
    assert list(out.glob("table_*.csv")) == []
    report = tmp_path / "va.md"
    subprocess.run([sys.executable, str(SCRIPTS / "verify_arithmetic.py"), str(out), str(report)],
                   check=True, capture_output=True)
    assert "t_vs_p" not in report.read_text()
