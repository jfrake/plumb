"""Wide multi-model table, broader header vocab, parse error, and no-tables tests.

These tests cover three gaps:
  Gap 1: wide multi-model explicit-column tables
  Gap 2: broader SE/p/t-stat header vocabulary
  Gap 3: visible parse errors and NO_TABLES verdict
"""
from __future__ import annotations

import sys, pathlib, csv, runpy, subprocess, tempfile, os

SCRIPT_DIR = pathlib.Path(__file__).resolve().parents[1] / "skills/review/scripts"
sys.path.insert(0, str(SCRIPT_DIR))
import importlib; va = importlib.import_module("verify_arithmetic")

SCRIPT_PATH = SCRIPT_DIR / "verify_arithmetic.py"


def _write(p, rows):
    with open(p, "w", newline="") as f:
        csv.writer(f).writerows(rows)


# ---------------------------------------------------------------------------
# Gap 1: wide multi-model layout
# ---------------------------------------------------------------------------

def test_wide_table_two_models_checked(tmp_path):
    """Wide two-model layout: model 1 consistent, model 2 inconsistent."""
    d = tmp_path / "extracted_tables"
    d.mkdir()
    # coef_1/se_1 -> t=2.0 -> p~0.046, printed 0.05: consistent
    # coef_2/se_2 -> t=2.0 -> p~0.046, printed 0.99: inconsistent
    _write(d / "table_01.csv", [
        ["Variables", "coef_1", "se_1", "p_1", "coef_2", "se_2", "p_2"],
        ["x",         "0.20",   "0.10", "0.05", "0.50",   "0.25", "0.99"],
    ])
    t = va.parse_table_csv(d / "table_01.csv")

    # Both models must appear in the parsed rows
    all_keys = set()
    for row in t["rows"]:
        all_keys.update(row["coeffs"].keys())
    assert "1" in all_keys, f"model '1' not found in row keys: {all_keys}"
    assert "2" in all_keys, f"model '2' not found in row keys: {all_keys}"

    findings = va.run_checks({"table_01.csv": t})
    errors = [f for f in findings if f["check"] == "t_vs_p" and f["status"] == "error"]

    # Model 2 must be flagged
    assert any("/ 2" in f["cell"] or f["cell"].endswith("2") for f in errors), (
        f"expected t_vs_p error for model 2; findings: {findings}"
    )
    # Model 1 must NOT be flagged
    assert not any("/ 1" in f["cell"] or f["cell"].endswith("1") for f in errors), (
        f"unexpected t_vs_p error for model 1; findings: {findings}"
    )


# ---------------------------------------------------------------------------
# Gap 2: broader header vocabulary
# ---------------------------------------------------------------------------

def test_header_vocab_variants(tmp_path):
    """Headers using 'S.E.' and 'Pr(>|t|)' must be recognized."""
    d = tmp_path / "extracted_tables"
    d.mkdir()
    # coef=0.20, se=0.10 -> t=2.0 -> p~0.046, printed 0.99: inconsistent
    _write(d / "table_01.csv", [
        ["Variables", "Coef", "S.E.", "Pr(>|t|)"],
        ["x",         "0.20", "0.10", "0.99"],
    ])
    t = va.parse_table_csv(d / "table_01.csv")

    row = t["rows"][0]
    assert row["ses"], f"SE column not recognized; row: {row}"
    assert row["pvals"], f"p-value column not recognized; row: {row}"

    findings = va.run_checks({"table_01.csv": t})
    assert any(f["check"] == "t_vs_p" and f["status"] == "error" for f in findings), (
        f"expected t_vs_p error; findings: {findings}"
    )


# ---------------------------------------------------------------------------
# Gap 3a: parse error emits a finding
# ---------------------------------------------------------------------------

def test_parse_error_emits_finding(tmp_path):
    """A table with a parse error must produce a parse_error finding."""
    d = tmp_path / "extracted_tables"
    d.mkdir()
    bad = d / "table_01.csv"
    # Write raw bytes that are not valid UTF-8
    bad.write_bytes(b"\x80\x81\x82")

    # Attempt to parse; store the error the same way main() does
    try:
        va.parse_table_csv(bad)
        stored = {"columns": [], "rows": [], "error": "no exception raised"}
    except Exception as exc:
        stored = {"columns": [], "rows": [], "error": str(exc)}

    findings = va.run_checks({"table_01.csv": stored})
    assert any(f["check"] == "parse_error" and f["status"] == "error" for f in findings), (
        f"expected parse_error finding; findings: {findings}"
    )

    # Also run main() via subprocess and check the report
    out_md = tmp_path / "report.md"
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), str(d), str(out_md)],
        capture_output=True, text=True
    )
    assert result.returncode == 0, f"script exited non-zero: {result.stderr}"
    report = out_md.read_text()
    assert "PARSE_ERROR" in report or "VERDICT: PARSE_ERRORS_PRESENT" in report, (
        f"report does not contain parse error signal:\n{report}"
    )


# ---------------------------------------------------------------------------
# Gap 3b: empty directory produces NO_TABLES verdict
# ---------------------------------------------------------------------------

def test_no_tables_verdict(tmp_path):
    """An empty extracted-tables directory must produce VERDICT: NO_TABLES."""
    d = tmp_path / "extracted_tables"
    d.mkdir()
    out_md = tmp_path / "report.md"
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), str(d), str(out_md)],
        capture_output=True, text=True
    )
    assert result.returncode == 0, f"script exited non-zero: {result.stderr}"
    report = out_md.read_text()
    assert "VERDICT: NO_TABLES" in report, (
        f"expected VERDICT: NO_TABLES in report:\n{report}"
    )
