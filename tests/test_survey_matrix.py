from __future__ import annotations
import csv
import importlib.util
import json
import math
import random
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "packs" / "survey" / "scripts" / "check_correlation_matrix.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_correlation_matrix", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cm = _load()


def _table(labels, lower, diag=None, upper=None, lead=None):
    """Rows for a CSV: header 1..k, lower[i][j] for j < i, optional diagonal, upper, and leading columns."""
    k = len(labels)
    lead = lead or {}
    header = ["Variable"] + list(lead) + [str(c + 1) for c in range(k)]
    rows = [header]
    for i in range(k):
        row = [f"{i + 1}. {labels[i]}"] + [lead[h][i] for h in lead]
        for j in range(k):
            if j < i:
                row.append(lower[i][j])
            elif j == i:
                row.append(diag[i] if diag else "")
            else:
                row.append(upper[i][j] if upper else "")
        rows.append(row)
    return rows


def _write(tmp_path, name, rows):
    tmp_path.mkdir(parents=True, exist_ok=True)
    with (tmp_path / f"{name}.csv").open("w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerows(rows)


def _one(rows, table="table_02"):
    recs = cm.matrices_from_table(table, rows)
    assert len(recs) == 1, recs
    return recs[0]


VALID4 = [["", "", "", ""], [".32", "", "", ""], [".18", ".41**", "", ""], ["-.05", ".22*", ".27**", ""]]
NAMES4 = ["Firm size", "Tenure", "Voice", "Trust"]


def test_parse_cell_strips_marks_and_reads_decimals():
    assert cm.parse_cell("(.83)**") == (0.83, 2)
    assert cm.parse_cell("-.27*") == (-0.27, 2)
    assert cm.parse_cell(chr(0x2212) + "0.3" + chr(0x2020)) == (-0.3, 1)
    assert cm.parse_cell("[.125]") == (0.125, 3)
    assert cm.parse_cell("") is None and cm.parse_cell("-") is None and cm.parse_cell(" " + chr(0x2014) + " ") is None
    with pytest.raises(cm.CellError):
        cm.parse_cell("n.s.")


def test_a_valid_lower_triangle_is_checked_with_no_flags():
    rec = _one(_table(NAMES4, VALID4))
    assert rec["status"] == "checked" and rec["part"] == "whole" and rec["k"] == 4
    assert rec["diagonal"] == "blank" and rec["range_violations"] == []
    assert rec["psd"]["impossible"] is False and rec["psd"]["method"] == "jacobi"


def test_an_upper_triangle_is_read():
    upper = [["", VALID4[1][0], VALID4[2][0], VALID4[3][0]], ["", "", VALID4[2][1], VALID4[3][1]],
             ["", "", "", VALID4[3][2]], ["", "", "", ""]]
    empty = [["", "", "", ""] for _ in range(4)]
    rec = _one(_table(NAMES4, empty, upper=upper))
    assert rec["status"] == "checked" and rec["psd"]["impossible"] is False
    assert rec["psd"]["min_eigenvalue"] == _one(_table(NAMES4, VALID4))["psd"]["min_eigenvalue"]


def test_k_rows_with_k_minus_one_columns_are_accepted():
    rows = _table(NAMES4, VALID4)
    rows = [r[:-1] for r in rows]
    rec = _one(rows)
    assert rec["status"] == "checked" and rec["k"] == 4


def test_a_leading_alpha_column_is_used_as_the_diagonal():
    lead = {"Mean": ["3.1", "4.0", "3.6", "3.9"], "SD": ["0.8", "1.1", "0.9", "0.7"],
            "Alpha": ["", ".81", ".88", ".85"]}
    rec = _one(_table(NAMES4, VALID4, lead=lead))
    assert rec["diagonal"] == "values" and rec["diagonal_source"] == "Alpha"
    assert {(p["i"], p["j"]) for p in rec["pairs"]} == {(2, 3), (2, 4), (3, 4)}


def test_an_unparseable_cell_makes_the_table_not_computable_and_names_the_cell():
    lower = [row[:] for row in VALID4]
    lower[2][1] = "n.s."
    rec = _one(_table(NAMES4, lower))
    assert rec["status"] == "not_computable" and "table_02:3:2" in rec["reason"] and "n.s." in rec["reason"]


def test_triangles_that_agree_become_one_matrix():
    upper = [["", ".32", ".18", "-.05"], ["", "", ".41", ".22"], ["", "", "", ".27"], ["", "", "", ""]]
    rec = _one(_table(NAMES4, VALID4, upper=upper))
    assert rec["part"] == "whole" and rec["status"] == "checked"


def test_triangles_that_differ_are_checked_as_two_matrices():
    upper = [["", ".45", ".10", ".02"], ["", "", ".38", ".30"], ["", "", "", ".19"], ["", "", "", ""]]
    recs = cm.matrices_from_table("table_02", _table(NAMES4, VALID4, upper=upper))
    assert [r["part"] for r in recs] == ["lower", "upper"]
    assert all(r["status"] == "checked" for r in recs)


def test_counts_in_the_upper_triangle_are_not_a_correlation_matrix():
    upper = [["", "312", "298", "305"], ["", "", "301", "290"], ["", "", "", "296"], ["", "", "", ""]]
    recs = cm.matrices_from_table("table_02", _table(NAMES4, VALID4, upper=upper))
    lower, upp = recs
    assert lower["status"] == "checked" and lower["range_violations"] == []
    assert upp["status"] == "not_computable" and "covariances or counts" in upp["reason"]


def test_a_covariance_matrix_is_not_computable():
    lower = [["", "", "", ""], ["0.42", "", "", ""], ["0.18", "0.61", "", ""], ["-0.05", "0.22", "0.27", ""]]
    rec = _one(_table(NAMES4, lower, diag=["2.31", "1.20", "0.95", "1.44"]))
    assert rec["status"] == "not_computable" and "covariances or counts" in rec["reason"]


def test_one_value_out_of_range_is_a_range_violation():
    lower = [row[:] for row in VALID4]
    lower[3][2] = "1.04"
    rec = _one(_table(NAMES4, lower))
    assert rec["range_violations"] == [{"row": 4, "col": 3, "value": 1.04}] and rec["psd"] is None


def test_a_blank_cell_drops_the_fewest_variables():
    labels = NAMES4 + ["Safety"]
    lower = [row[:] + [""] for row in VALID4] + [[".12", ".08", ".30", "", ""]]
    rec = _one(_table(labels, lower))
    assert rec["dropped_variables"] == ["4. Trust"] and rec["drop_method"] == "exact"
    assert rec["status"] == "checked" and rec["psd"] is not None


IMPOSSIBLE = [["", "", "", ""], [".90", "", "", ""], [".90", "-.50", "", ""], [".10", ".10", ".10", ""]]


def test_a_known_impossible_matrix_is_flagged_with_its_driving_variables():
    rec = _one(_table(["A", "B", "C", "D"], IMPOSSIBLE))
    psd = rec["psd"]
    assert psd["impossible"] is True and psd["min_eigenvalue"] < -psd["bound"]
    assert set(psd["driving_variables"]) == {"1. A", "2. B", "3. C"}
    assert psd["bound"] == pytest.approx(0.015)


def test_the_rounding_bound_is_a_per_cell_row_sum():
    lower = [["", "", ""], [".3", "", ""], [".27", ".125", ""]]
    rec = _one(_table(["A", "B", "C"], lower))
    # row 3 carries 0.005 + 0.0005; row 1 carries 0.05 + 0.005; row 2 carries 0.05 + 0.0005
    assert rec["psd"]["bound"] == pytest.approx(0.055)


def test_more_than_forty_variables_use_cholesky_only():
    k = 41
    names = [f"V{i}" for i in range(k)]
    lower = [["" if j >= i else ".10" for j in range(k)] for i in range(k)]
    rec = _one(_table(names, lower))
    assert rec["psd"]["method"] == "cholesky" and rec["psd"]["impossible"] is False
    assert rec["psd"]["min_eigenvalue"] is None and "more than 40" in rec["psd"]["note"]
    lower[1][0] = ".95"
    lower[2][0] = ".95"
    lower[2][1] = "-.95"
    assert _one(_table(names, lower))["psd"]["impossible"] is True


def test_check_4_ignores_a_tie_within_rounding():
    lower = [["", "", ""], [".83", "", ""], [".20", ".25", ""]]
    rec = _one(_table(["A", "B", "C"], lower, diag=[".83", ".90", ".88"]))
    assert rec["diag_below_offdiag"] == []


S9 = [["", "", ""], [".83", "", ""], [".31", ".35", ""]]


def test_the_s9_plant_numbers():
    rec = _one(_table(["Psychological safety", "Team trust", "Voice"], S9, diag=[".82", ".80", ".91"]))
    top = rec["pairs"][0]
    assert (top["i"], top["j"]) == (1, 2)
    assert top["disattenuated"] == pytest.approx(0.83 / math.sqrt(0.82 * 0.80), abs=1e-6)
    assert top["lower_bound"] == pytest.approx(0.825 / math.sqrt(0.825 * 0.805), abs=1e-6)
    assert round(top["lower_bound"], 4) == 1.0123 and top["at_or_above_one"] is True
    assert rec["screen"] == [[1, 2]]
    assert rec["diag_below_offdiag"] == [{"row": 2, "col": 1, "diag": 0.80, "r": 0.83}]
    assert rec["psd"]["impossible"] is False


def test_the_d2_decoy_numbers():
    lower = [["", "", ""], [".52", "", ""], [".20", ".24", ""]]
    rec = _one(_table(["Voice climate", "Leader openness", "Voice"], lower, diag=[".88", ".85", ".90"]))
    pair = next(p for p in rec["pairs"] if (p["i"], p["j"]) == (1, 2))
    assert round(pair["disattenuated"], 3) == 0.601 and pair["at_or_above_one"] is False
    assert rec["screen"] == []


def test_two_numbered_blocks_in_one_table_are_separate_matrices():
    rows = _table(NAMES4, VALID4)
    rows = rows + [["Panel B"] + [""] * 4] + rows[1:]
    recs = cm.matrices_from_table("table_03", rows)
    assert [r["table"] for r in recs] == ["table_03#1", "table_03#2"]


def _random_corr(rng, k, rank, composite):
    """A valid correlation matrix: R = F F' (rank below k when rank < k) plus, optionally, a composite
    that is the mean of the first three variables."""
    f = [[rng.gauss(0, 1) for _ in range(rank)] for _ in range(k)]
    c = [[sum(f[i][t] * f[j][t] for t in range(rank)) for j in range(k)] for i in range(k)]
    if composite:
        m = 3
        c = [row + [sum(row[:m]) / m] for row in c]
        c.append([sum(c[i][j] for i in range(m)) / m for j in range(k)] + [sum(c[i][j] for i in range(m) for j in range(m)) / (m * m)])
    n = len(c)
    return [[c[i][j] / math.sqrt(c[i][i] * c[j][j]) for j in range(n)] for i in range(n)]


def _printed(r, rng, mixed):
    k = len(r)
    names = [f"V{i}" for i in range(k)]
    lower = [["" for _ in range(k)] for _ in range(k)]
    for i in range(k):
        for j in range(i):
            d = rng.choice([1, 2, 2, 2, 3, 1]) if mixed else 2
            lower[i][j] = f"{r[i][j]:.{d}f}"
    return _table(names, lower)


def test_rounded_full_rank_matrices_are_never_flagged():
    rng = random.Random(20260929)
    for _ in range(1000):
        k = rng.randint(3, 12)
        r = _random_corr(rng, k, k + 2, False)
        rec = _one(_printed(r, rng, False))
        assert rec["psd"]["impossible"] is False, rec


def test_rank_deficient_and_mixed_decimal_matrices_are_never_flagged():
    rng = random.Random(29092026)
    for n in range(5000):
        k = rng.randint(3, 11)
        composite = n % 2 == 0
        rank = rng.randint(1, max(1, k - 1)) if not composite else rng.randint(3, k)
        r = _random_corr(rng, k, rank, composite)
        rec = _one(_printed(r, rng, True))
        assert rec["status"] == "checked" and rec["psd"]["impossible"] is False, rec


def test_cli_writes_json_and_markdown(tmp_path):
    tables = tmp_path / "extracted_tables"
    _write(tables, "table_01", _table(["A", "B", "C", "D"], IMPOSSIBLE))
    _write(tables, "table_02", [["", "Model 1"], ["Slack", "0.31**"], ["", "(0.10)"]])
    (tables / "table_01_note.txt").write_text("Note. N = 318.")
    out, md = tmp_path / "stage-1" / "survey_matrix.json", tmp_path / "m.md"
    r = subprocess.run([sys.executable, str(SCRIPT), str(tables), str(out), "--out-md", str(md)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    data = json.loads(out.read_text())
    assert data["matrices"][0]["psd"]["impossible"] is True
    assert data["skipped"] == [{"table": "table_02", "reason": "no correlation matrix layout"}]
    assert "impossible within rounding" in md.read_text()


def test_an_unreadable_table_is_skipped_and_the_others_are_checked(tmp_path):
    tables = tmp_path / "extracted_tables"
    _write(tables, "table_02", _table(NAMES4, VALID4))
    (tables / "table_01.csv").write_bytes(b"Variable,1\n1. A," + bytes([0xFF, 0xFE]) + b"\n")
    data = cm.run(tables)
    assert [m["table"] for m in data["matrices"]] == ["table_02"] and data["matrices"][0]["status"] == "checked"
    assert data["skipped"][0]["table"] == "table_01"
    assert data["skipped"][0]["reason"].startswith("unreadable table")


def test_cli_exits_2_without_tables(tmp_path):
    out = tmp_path / "o.json"
    assert subprocess.run([sys.executable, str(SCRIPT), str(tmp_path / "none"), str(out)]).returncode == 2
    (tmp_path / "empty").mkdir()
    assert subprocess.run([sys.executable, str(SCRIPT), str(tmp_path / "empty"), str(out)]).returncode == 2
    assert not out.exists()


def test_the_script_uses_only_the_standard_library():
    text = SCRIPT.read_text(encoding="utf-8")
    imports = {l.split()[1].split(".")[0] for l in text.splitlines() if l.startswith(("import ", "from "))}
    assert imports <= {"__future__", "csv", "itertools", "json", "math", "re", "sys", "pathlib"}, imports
    assert chr(0x2014) not in text


# --- fix round 1 -------------------------------------------------------------

def test_an_ave_column_is_not_used_as_reliabilities():
    rows = [["Construct", "AVE", "1", "2", "3"], ["1. A", ".50", "", "", ""], ["2. B", ".50", ".60", "", ""],
            ["3. C", ".55", ".30", ".35", ""]]
    rec = _one(rows)
    assert rec["diagonal"] == "blank" and rec["pairs"] == []
    assert not any(p["at_or_above_one"] for p in rec["pairs"])


def test_a_negative_alpha_does_not_stop_the_psd_check():
    lower = [["", "", ""], [".99", "", ""], [".99", "-.99", ""]]
    lead = {"Alpha": ["-.12", ".80", ".85"]}
    rec = _one(_table(["A", "B", "C"], lower, lead=lead))
    assert rec["status"] == "checked" and rec["range_violations"] == []
    assert rec["psd"]["impossible"] is True
    assert rec["diagonal_unusable"] == ["1. A"]
    assert all(1 not in (p["i"], p["j"]) for p in rec["pairs"])


def test_a_diagonal_printed_zero_is_unusable_but_the_psd_check_runs():
    lower = [["", "", ""], [".30", "", ""], [".20", ".25", ""]]
    rec = _one(_table(["A", "B", "C"], lower, diag=[".00", ".80", ".85"]))
    assert rec["psd"] is not None and rec["psd"]["impossible"] is False
    assert rec["diagonal_unusable"] == ["1. A"] and rec["range_violations"] == []


def test_paren_indices_with_regression_like_values_are_not_a_matrix():
    rows = [["", "(1)", "(2)", "(3)"], ["1. Size", "0.31", "0.12", "0.40"], ["2. Age", "0.22", "0.05", "0.18"],
            ["3. Slack", "0.09", "0.27", "0.33"]]
    recs = cm.matrices_from_table("table_04", rows)
    assert all(r["status"] != "checked" for r in recs)
    assert recs and "not a correlation matrix layout" in recs[0]["reason"]


def test_paren_indices_with_a_clean_triangle_are_still_read():
    rows = _table(NAMES4, VALID4)
    rows[0] = [rows[0][0]] + [f"({c})" for c in range(1, 5)]
    assert _one(rows)["status"] == "checked"


def test_an_en_dash_before_a_digit_is_a_minus_sign():
    assert cm.parse_cell(chr(0x2013) + ".27") == (-0.27, 2)
    assert cm.parse_cell(chr(0x2013) + "0.3*") == (-0.3, 1)
    assert cm.parse_cell(chr(0x2013)) is None


def test_an_unreadable_file_is_skipped_not_fatal(tmp_path, monkeypatch):
    tables = tmp_path / "extracted_tables"
    _write(tables, "table_02", _table(NAMES4, VALID4))
    _write(tables, "table_01", _table(NAMES4, VALID4))
    real = Path.open

    def fake(self, *a, **k):
        if self.name == "table_01.csv":
            raise PermissionError("denied")
        return real(self, *a, **k)

    monkeypatch.setattr(Path, "open", fake)
    data = cm.run(tables)
    assert [m["table"] for m in data["matrices"]] == ["table_02"]
    assert data["skipped"][0]["reason"].startswith("unreadable table")


def test_diag_below_offdiag_is_printed_as_a_fact_not_a_flag(tmp_path):
    rec = _one(_table(["Psychological safety", "Team trust", "Voice"], S9, diag=[".82", ".80", ".91"]))
    text = cm.to_markdown({"matrices": [rec], "skipped": []})
    assert "fact: a correlation exceeds a diagonal value" in text
    assert "not an error when the diagonal holds reliabilities" in text
    assert "fact" in cm.__doc__ and "flag" not in text.split("fact:")[1].split("\n")[0].lower()


def test_the_eigenvector_test_catches_what_the_uniform_bound_misses():
    # Pick a matrix where one coarse cell inflates B but the minimum eigenvector barely uses it.
    lower = [["", "", "", ""], [".9", "", "", ""], [".9", "-.5", "", ""], [".1", ".1", ".1", ""]]
    lower = [r[:] for r in lower]
    p = _one(_table(["A", "B", "C", "D"], lower))["psd"]
    assert p["fired"] == "bound"
    coarse = [["", "", "", ""], [".9", "", "", ""], [".9", "-.5", "", ""], ["0", "0", "0", ""]]
    q = _one(_table(["A", "B", "C", "D"], coarse))["psd"]
    assert q["fired"] in ("bound", "eigenvector") and q["impossible"] is True
    ok = _one(_table(NAMES4, VALID4))["psd"]
    assert ok["fired"] is None and ok["impossible"] is False


def test_the_eigenvector_test_fires_where_the_uniform_bound_does_not():
    lower = [["", "", "", ""], ["-.9", "", "", ""], ["-.5", ".95", "", ""], ["-.5", ".1", ".1", ""]]
    p = _one(_table(["A", "B", "C", "D"], lower))["psd"]
    assert p["impossible"] is True and p["fired"] == "eigenvector"
    assert p["min_eigenvalue"] >= -p["bound"]
