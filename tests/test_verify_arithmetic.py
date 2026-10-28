from __future__ import annotations

import sys, pathlib, csv
SCRIPT_DIR = pathlib.Path(__file__).resolve().parents[1] / "skills/review/scripts"
sys.path.insert(0, str(SCRIPT_DIR))
import importlib; va = importlib.import_module("verify_arithmetic")

def _write(p, rows):
    with open(p, "w", newline="") as f:
        csv.writer(f).writerows(rows)

def test_note_says_p_value_classifies_p(tmp_path):
    d = tmp_path/"extracted_tables"; d.mkdir()
    _write(d/"table_01.csv", [["Variables","Model 1"],["x","0.30"],["","[1.7]"]])
    t = va.parse_table_csv(d/"table_01.csv", value_type="p_value")
    assert t["rows"][0]["pvals"]["Model 1"] == 1.7 and not t["rows"][0]["ses"]
    f = va.run_checks({"table_01.csv": t})
    assert any(x["check"]=="pval_range" and x["status"]=="error" for x in f)

def test_note_says_se_classifies_se_even_in_brackets(tmp_path):
    # square brackets but the NOTE says standard errors -> the note wins, not the delimiter
    d = tmp_path/"extracted_tables"; d.mkdir()
    _write(d/"table_01.csv", [["Variables","Model 1"],["x","0.30"],["","[1.40]"]])
    t = va.parse_table_csv(d/"table_01.csv", value_type="standard_error")
    assert t["rows"][0]["ses"]["Model 1"] == 1.40 and not t["rows"][0]["pvals"]
    f = va.run_checks({"table_01.csv": t})
    assert not any(x["check"]=="pval_range" and x["status"]=="error" for x in f)

def test_t_vs_p_explicit_columns(tmp_path):
    d = tmp_path/"extracted_tables"; d.mkdir()
    # coeff 0.20, SE 0.10 -> t=2.0 -> p ~ .0455; printed p=.99 is inconsistent
    _write(d/"table_01.csv", [["Variables","Coef","SE","p"],["x","0.20","0.10","0.99"]])
    t = va.parse_table_csv(d/"table_01.csv")  # explicit columns -> value_type irrelevant
    f = va.run_checks({"table_01.csv": t})
    assert any(x["check"]=="t_vs_p" and x["status"]=="error" for x in f)

def test_confidence_interval_contains_and_order(tmp_path):
    d = tmp_path/"extracted_tables"; d.mkdir()
    _write(d/"table_01.csv", [["Variables","Model 1"],
                              ["x","0.30"],["","[0.12, 0.45]"],
                              ["y","9.90"],["","[0.10, 0.20]"]])
    t = va.parse_table_csv(d/"table_01.csv", value_type="confidence_interval")
    assert t["rows"][0]["cis"]["Model 1"] == (0.12, 0.45)
    f = va.run_checks({"table_01.csv": t})
    assert any(x["check"]=="ci_contains_coeff" and x["status"]=="error" for x in f)  # y outside its CI

def test_ci_reversed_bounds_flags(tmp_path):
    d = tmp_path/"extracted_tables"; d.mkdir()
    _write(d/"table_01.csv", [["Variables","Model 1"],["x","0.30"],["","[0.45, 0.12]"]])
    t = va.parse_table_csv(d/"table_01.csv", value_type="confidence_interval")
    f = va.run_checks({"table_01.csv": t})
    assert any(x["check"]=="ci_order" and x["status"]=="error" for x in f)

def test_se_zero_flags(tmp_path):
    d = tmp_path/"extracted_tables"; d.mkdir()
    _write(d/"table_01.csv", [["Variables","Model 1"],["x","0.30"],["","(0.00)"]])
    t = va.parse_table_csv(d/"table_01.csv", value_type="standard_error")
    f = va.run_checks({"table_01.csv": t})
    assert any(x["check"]=="se_positive" and x["status"]=="error" for x in f)

def test_unknown_falls_back_to_delimiter(tmp_path):
    d = tmp_path/"extracted_tables"; d.mkdir()
    _write(d/"table_01.csv", [["Variables","Model 1"],["x","0.30"],["","(0.10)"]])
    t = va.parse_table_csv(d/"table_01.csv", value_type="unknown")
    assert t["rows"][0]["ses"]["Model 1"] == 0.10   # no note -> paren delimiter -> SE fallback


def test_cli_creates_missing_output_directory(tmp_path):
    import subprocess
    d = tmp_path/"extracted_tables"; d.mkdir()
    _write(d/"table_01.csv", [["Variables","Model 1"],["x","0.30"],["","(0.10)"]])
    out = tmp_path/"stage-1"/"arithmetic.md"
    r = subprocess.run([sys.executable, str(SCRIPT_DIR/"verify_arithmetic.py"), str(d), str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert out.exists() and out.read_text().startswith("VERDICT:")
