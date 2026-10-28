#!/usr/bin/env python3
"""Check printed correlation matrices for values no data could produce.

Reads every CSV in an extracted-tables folder, finds correlation matrices, and
for each one reports: values out of range; whether the matrix is impossible
within rounding (no complete-data correlation matrix could print these values);
and disattenuated correlations with a rounding lower bound. It also lists, as a
fact and not a flag, off-diagonal values that exceed a diagonal value beyond
rounding (not an error when the diagonal holds reliabilities). The rounding bound
B is attained by a uniform E, but not necessarily along the minimum eigenvector of
the printed matrix, so the bound test is conservative; a second, sharper sound test
uses the eigenvector directly. Report-only.

Usage: check_correlation_matrix.py <extracted_tables_dir> <out_json> [--out-md <path>]
Exit 0 when it ran (with or without flags); 2 when the folder is missing,
unreadable, or holds no CSV.
"""
from __future__ import annotations

import csv
import itertools
import json
import math
import re
import sys
from pathlib import Path

MARKS = "*" + chr(0x2020) + chr(0x2021) + chr(0xA7)  # star, daggers, section sign
BLANKS = {"", "-", chr(0x2013), chr(0x2014), "."}  # empty, hyphen, en and em dash, dot
NUMBER = re.compile(r"^-?(\d*)\.?(\d*)$")
ROW_INDEX = re.compile(r"^\s*\(?(\d{1,2})(?!\d)\)?\s*[.)]?\s*(.*)$")
PAREN_INDEX = re.compile(r"^\s*\(\d{1,2}\)\s*$")
COL_INDEX = re.compile(r"^\s*\(?(\d{1,2})(?!\d)\)?\s*\.?\s*$")
RELIABILITY_HEADERS = {"alpha", chr(0x3B1), "cronbach's alpha", "cronbach" + chr(0x2019) + "s alpha", "reliability",
                       "cr", "composite reliability", "omega", chr(0x3C9)}
MARGIN = 1e-9
TIE = 1e-12
JACOBI_MAX_K = 40
SCREEN = 0.85


class CellError(ValueError):
    pass


def parse_cell(text):
    """Return None for a blank cell, else (value, decimals). Raise CellError if unreadable."""
    s = (text or "").strip()
    for m in MARKS:
        s = s.replace(m, "")
    s = s.strip()
    if s[:1] in "([" and s[-1:] in ")]":
        s = s[1:-1].strip()
    s = s.replace(chr(0x2212), "-").replace(" ", "")  # U+2212 is the minus sign
    if len(s) > 1 and s[0] == chr(0x2013) and (s[1].isdigit() or s[1] == "."):
        s = "-" + s[1:]  # an en dash before a number is a minus sign
    if s in BLANKS:
        return None
    m = NUMBER.match(s)
    if not m or not (m.group(1) or m.group(2)):
        raise CellError(text)
    return float(s), len(m.group(2))


def half_unit(decimals):
    return 0.5 * 10.0 ** (-decimals)


# --- finding matrices -------------------------------------------------------

def _norm(name):
    return re.sub(r"\s+", " ", (name or "").strip().lower())


def _row_blocks(rows):
    """Runs of rows whose labels are numbered 1, 2, 3, ... (each run is one matrix)."""
    blocks, cur = [], []
    for r_i, row in enumerate(rows[1:], start=1):
        m = ROW_INDEX.match(row[0] if row else "")
        idx = int(m.group(1)) if m and m.group(2) is not None else None
        if idx is not None and idx == len(cur) + 1:
            cur.append((r_i, (row[0] or "").strip()))
            continue
        if len(cur) >= 3:
            blocks.append(cur)
        cur = [(r_i, (row[0] or "").strip())] if idx == 1 else []
    if len(cur) >= 3:
        blocks.append(cur)
    return blocks


def _numeric_columns(header):
    cols = []
    for c, h in enumerate(header[1:], start=1):
        m = COL_INDEX.match(h or "")
        if m and int(m.group(1)) == len(cols) + 1:
            cols.append(c)
        elif cols:
            break
    return cols


def _named_columns(header, labels):
    names = [_norm(ROW_INDEX.match(l).group(2)) if ROW_INDEX.match(l) else _norm(l) for l in labels]
    cols = []
    for c, h in enumerate(header[1:], start=1):
        if len(cols) < len(names) and _norm(h) and _norm(h) in (names[len(cols)], _norm(labels[len(cols)])):
            cols.append(c)
        elif cols:
            break
    return cols


def _reliability_column(header, first_matrix_col):
    for c in range(1, first_matrix_col):
        if _norm(header[c]) in RELIABILITY_HEADERS:
            return c
    return None


def _named_blocks(rows):
    """Fallback: column headers that repeat the row labels in order."""
    header = rows[0]
    labels = [(r_i, (row[0] or "").strip()) for r_i, row in enumerate(rows[1:], start=1) if row and row[0].strip()]
    for start in range(len(labels)):
        cols = _named_columns(header, [l for _, l in labels[start:]])
        if len(cols) >= 2:
            k = len(cols) + 1 if len(labels) - start > len(cols) else len(cols)
            if k >= 3:
                return [labels[start:start + k]], cols
    return [], []


def find_matrices(rows):
    """Yield (row_block, matrix_columns, reliability_column) for each matrix in a table."""
    if not rows or len(rows) < 4:
        return []
    header = rows[0]
    cols = _numeric_columns(header)
    blocks = _row_blocks(rows) if cols else []
    if not blocks:
        blocks, cols = _named_blocks(rows)
    out = []
    for block in blocks:
        k = len(block)
        if len(cols) not in (k, k - 1):
            continue
        out.append((block, cols[:k], _reliability_column(header, cols[0])))
    return out


# --- linear algebra ----------------------------------------------------------

def jacobi_eigen(a):
    """Eigenvalues and eigenvectors (columns) of a symmetric matrix, by cyclic Jacobi rotation."""
    n = len(a)
    a = [row[:] for row in a]
    v = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for _ in range(100):
        off = sum(a[i][j] ** 2 for i in range(n) for j in range(i + 1, n))
        if off < 1e-24:
            break
        for p in range(n - 1):
            for q in range(p + 1, n):
                if abs(a[p][q]) < 1e-300:
                    continue
                theta = (a[q][q] - a[p][p]) / (2.0 * a[p][q])
                t = (1.0 if theta >= 0 else -1.0) / (abs(theta) + math.sqrt(theta * theta + 1.0))
                c = 1.0 / math.sqrt(t * t + 1.0)
                s = t * c
                for k in range(n):
                    akp, akq = a[k][p], a[k][q]
                    a[k][p] = c * akp - s * akq
                    a[k][q] = s * akp + c * akq
                for k in range(n):
                    apk, aqk = a[p][k], a[q][k]
                    a[p][k] = c * apk - s * aqk
                    a[q][k] = s * apk + c * aqk
                for k in range(n):
                    vkp, vkq = v[k][p], v[k][q]
                    v[k][p] = c * vkp - s * vkq
                    v[k][q] = s * vkp + c * vkq
    return [a[i][i] for i in range(n)], v


def cholesky_ok(a):
    n = len(a)
    low = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = a[i][j] - sum(low[i][k] * low[j][k] for k in range(j))
            if i == j:
                if s <= 0.0:
                    return False
                low[i][i] = math.sqrt(s)
            else:
                low[i][j] = s / low[j][j]
    return True


def impossible_check(p, h, labels):
    """P has a unit diagonal; h[i][j] is the rounding half-unit of cell (i, j)."""
    k = len(p)
    bound = max(sum(h[i][j] for j in range(k) if j != i) for i in range(k))
    if k > JACOBI_MAX_K:
        shifted = [[p[i][j] + (bound + MARGIN if i == j else 0.0) for j in range(k)] for i in range(k)]
        return {"min_eigenvalue": None, "bound": round(bound, 6), "impossible": not cholesky_ok(shifted),
                "driving_variables": [], "method": "cholesky", "fired": "cholesky" if not cholesky_ok(shifted) else None,
                "note": "more than 40 variables: decided by Cholesky only, no eigenvector"}
    vals, vecs = jacobi_eigen(p)
    m = min(range(k), key=lambda i: vals[i])
    vec = [vecs[r][m] for r in range(k)]
    driving = [labels[i] for i in sorted(range(k), key=lambda i: -abs(vec[i]))[:3]]
    s_vec = sum(h[i][j] * abs(vec[i]) * abs(vec[j]) for i in range(k) for j in range(k) if i != j)
    fired = None
    if vals[m] < -bound - MARGIN:
        fired = "bound"
    elif vals[m] + s_vec < -MARGIN:
        fired = "eigenvector"
    flag = fired is not None
    return {"min_eigenvalue": round(vals[m], 6), "bound": round(bound, 6), "impossible": flag,
            "driving_variables": driving if flag else [], "method": "jacobi", "fired": fired}


# --- one matrix --------------------------------------------------------------

def _drop_for_blanks(k, blank_pairs):
    if not blank_pairs:
        return [], "exact"
    for size in (1, 2, 3):
        for combo in itertools.combinations(range(k), size):
            s = set(combo)
            if all(i in s or j in s for i, j in blank_pairs):
                return list(combo), "exact"
    dropped, left = [], set(blank_pairs)
    while left:
        counts = {}
        for i, j in left:
            counts[i] = counts.get(i, 0) + 1
            counts[j] = counts.get(j, 0) + 1
        worst = min(counts, key=lambda x: (-counts[x], x))
        dropped.append(worst)
        left = {pr for pr in left if worst not in pr}
    return sorted(dropped), "greedy"


def check_matrix(table, part, labels, cells, diag):
    """cells[(i, j)] = (value, h) for i != j, keyed with i > j; diag[i] = (value, h) or None."""
    k = len(labels)
    rec = {"table": table, "part": part, "status": "checked", "reason": None, "k": k,
           "variables": labels, "dropped_variables": [], "drop_method": "exact",
           "diagonal": "blank", "diagonal_source": "diagonal", "diagonal_unusable": [],
           "range_violations": [], "psd": None,
           "pairs": [], "screen": [], "diag_below_offdiag": []}
    values = [v for v, _ in cells.values()]
    if values and sum(1 for v in values if abs(v) > 1) * 2 > len(values):
        rec.update(status="not_computable", reason="not a correlation matrix (covariances or counts?)")
        return rec
    if any(d is not None and d[0] > 1 for d in diag):
        rec.update(status="not_computable", reason="not a correlation matrix (covariances or counts?)")
        return rec
    nums = [d for d in diag if d is not None]
    if nums:
        rec["diagonal"] = "ones" if all(abs(d[0] - 1.0) < TIE for d in nums) else "values"
    for (i, j), (v, _) in sorted(cells.items()):
        if abs(v) > 1:
            rec["range_violations"].append({"row": i + 1, "col": j + 1, "value": v})
    unusable = {i for i, d in enumerate(diag) if d is not None and d[0] <= max(0.0, d[1])}
    rec["diagonal_unusable"] = [labels[i] for i in sorted(unusable)]
    if rec["range_violations"]:
        return rec
    blank = [(i, j) for i in range(k) for j in range(i) if (i, j) not in cells]
    drop, method = _drop_for_blanks(k, blank)
    rec["dropped_variables"] = [labels[i] for i in drop]
    rec["drop_method"] = method
    keep = [i for i in range(k) if i not in drop]
    if len(keep) < 3:
        rec.update(status="not_computable", reason="fewer than three variables have complete cells")
        return rec
    n = len(keep)
    p = [[1.0] * n for _ in range(n)]
    h = [[0.0] * n for _ in range(n)]
    for a in range(n):
        for b in range(a):
            v, hv = cells[(keep[a], keep[b])]
            p[a][b] = p[b][a] = v
            h[a][b] = h[b][a] = hv
    rec["psd"] = impossible_check(p, h, [labels[i] for i in keep])
    if rec["diagonal"] != "values":
        return rec
    for a in range(n):
        for b in range(n):
            if a == b or diag[keep[a]] is None or keep[a] in unusable:
                continue
            r, hr = cells[(max(keep[a], keep[b]), min(keep[a], keep[b]))]
            d, hd = diag[keep[a]]
            if (abs(r) - hr) - (d + hd) > TIE:
                rec["diag_below_offdiag"].append({"row": keep[a] + 1, "col": keep[b] + 1, "diag": d, "r": r})
    pairs = []
    for a in range(n):
        for b in range(a + 1, n):
            i, j = keep[a], keep[b]
            if diag[i] is None or diag[j] is None or i in unusable or j in unusable:
                continue
            (di, hi), (dj, hj) = diag[i], diag[j]
            r, hr = cells[(j, i)]
            dis = r / math.sqrt(di * dj)
            low = max(abs(r) - hr, 0.0) / math.sqrt((di + hi) * (dj + hj))
            pairs.append({"i": i + 1, "j": j + 1, "r": r, "d_i": di, "d_j": dj,
                          "disattenuated": round(dis, 6), "lower_bound": round(low, 6),
                          "at_or_above_one": low >= 1.0})
    pairs.sort(key=lambda x: (-abs(x["disattenuated"]), x["i"], x["j"]))
    rec["pairs"] = pairs
    rec["screen"] = [[x["i"], x["j"]] for x in pairs if abs(x["disattenuated"]) >= SCREEN]
    return rec


def _cell(rows, r, c, where):
    row = rows[r]
    text = row[c] if c < len(row) else ""
    try:
        parsed = parse_cell(text)
    except CellError:
        raise CellError(f"cell {where} reads {text!r}")
    return None if parsed is None else (parsed[0], half_unit(parsed[1]))


def matrices_from_table(table, rows):
    """All matrix records for one table (list), or [] when it has no correlation matrix."""
    out = []
    found = find_matrices(rows)
    for n_block, (block, cols, rel_col) in enumerate(found, start=1):
        name = table if len(found) == 1 else f"{table}#{n_block}"
        k = len(block)
        labels = [lab for _, lab in block]
        lower, upper, diag = {}, {}, [None] * k
        from_column = False
        try:
            for i, (r, _) in enumerate(block):
                for j, c in enumerate(cols):
                    got = _cell(rows, r, c, f"{table}:{r}:{c}")
                    if got is None:
                        continue
                    if i > j:
                        lower[(i, j)] = got
                    elif i < j:
                        upper[(j, i)] = got
                    else:
                        diag[i] = got
                if rel_col is not None:
                    got = _cell(rows, r, rel_col, f"{table}:{r}:{rel_col}")
                    if got is not None and (diag[i] is None or abs(diag[i][0] - 1.0) < TIE):
                        diag[i] = got
                        from_column = True
        except CellError as exc:
            out.append({"table": name, "part": "whole", "status": "not_computable", "reason": str(exc),
                        "k": k, "variables": labels})
            continue
        source = rows[0][rel_col].strip() if from_column else "diagonal"
        parts = []
        common = set(lower) & set(upper)
        agree = all(abs(lower[x][0] - upper[x][0]) <= lower[x][1] + upper[x][1] + TIE for x in common)
        paren = any(PAREN_INDEX.match(rows[0][c] or "") for c in cols)
        if paren and lower and upper:
            tri = k * (k - 1) / 2.0
            blank_share = 1.0 - min(len(lower), len(upper)) / tri
            if blank_share < 0.8 and not agree:
                out.append({"table": name, "part": "whole", "status": "not_computable",
                            "reason": "not a correlation matrix layout", "k": k, "variables": labels})
                continue
        if lower and upper:
            if agree:
                merged = dict(upper)
                merged.update(lower)
                parts = [("whole", merged)]
            else:
                parts = [("lower", lower), ("upper", upper)]
        else:
            parts = [("whole", lower or upper)]
        for part, cells in parts:
            rec = check_matrix(name, part, labels, cells, diag)
            if rec["status"] == "checked" and rec["diagonal"] == "values":
                rec["diagonal_source"] = source
            out.append(rec)
    return out


def run(folder):
    folder = Path(folder)
    result = {"matrices": [], "skipped": []}
    for f in sorted(folder.glob("*.csv")):
        try:
            with f.open(encoding="utf-8", newline="") as fh:
                rows = [row for row in csv.reader(fh)]
        except (UnicodeDecodeError, csv.Error, OSError) as exc:
            result["skipped"].append({"table": f.stem, "reason": f"unreadable table: {exc}"})
            continue
        recs = matrices_from_table(f.stem, rows)
        if recs:
            result["matrices"].extend(recs)
        else:
            result["skipped"].append({"table": f.stem, "reason": "no correlation matrix layout"})
    return result


def to_markdown(result):
    lines = ["# Correlation matrix check", ""]
    for m in result["matrices"]:
        head = f"- {m['table']} ({m['part']}, k={m['k']}): {m['status']}"
        if m["status"] != "checked":
            lines.append(f"{head}; {m['reason']}")
            continue
        bits = []
        if m["range_violations"]:
            bits.append(f"{len(m['range_violations'])} value(s) out of range")
        if m["psd"] and m["psd"]["impossible"]:
            bits.append(f"impossible within rounding (smallest eigenvalue {m['psd']['min_eigenvalue']}, "
                        f"bound {m['psd']['bound']}; driving: {', '.join(m['psd']['driving_variables'])})")
        above = [x for x in m["pairs"] if x["at_or_above_one"]]
        if above:
            bits.append(f"{len(above)} pair(s) with a disattenuated lower bound at or above 1")
        if m["diag_below_offdiag"]:
            bits.append("fact: a correlation exceeds a diagonal value; "
                        "not an error when the diagonal holds reliabilities")
        if m["dropped_variables"]:
            bits.append(f"dropped for blank cells: {', '.join(m['dropped_variables'])}")
        lines.append(f"{head}; " + ("; ".join(bits) if bits else "no flags"))
    if not result["matrices"]:
        lines.append("No correlation matrix found.")
    return "\n".join(lines) + "\n"


def main(argv):
    args = list(argv[1:])
    out_md = None
    if "--out-md" in args:
        i = args.index("--out-md")
        if i + 1 >= len(args):
            print("--out-md needs a path", file=sys.stderr)
            return 2
        out_md = args[i + 1]
        del args[i:i + 2]
    if len(args) != 2:
        print(__doc__.strip().splitlines()[-3], file=sys.stderr)
        return 2
    folder, out_json = Path(args[0]), Path(args[1])
    if not folder.is_dir():
        print(f"not a folder: {folder}", file=sys.stderr)
        return 2
    try:
        has_csv = any(folder.glob("*.csv"))
    except OSError as exc:
        print(f"could not read the folder: {exc}", file=sys.stderr)
        return 2
    if not has_csv:
        print(f"no CSV tables in {folder}", file=sys.stderr)
        return 2
    result = run(folder)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, indent=2), encoding="utf-8")
    if out_md:
        Path(out_md).write_text(to_markdown(result), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
