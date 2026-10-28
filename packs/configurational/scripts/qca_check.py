#!/usr/bin/env python3
"""Coherence checks for the figures a qualitative comparative analysis (QCA) prints.

Checks the fit table (consistency, PRI, raw and unique coverage, solution figures), the truth
table, the design counts (logical rows, remainders, cases), the necessity table, and, when the
paper prints membership scores, recomputes fit from them within their rounding. Every input comes
from the paper through the verify agent's inputs file; nothing is estimated, minimized, or chosen.

Usage: qca_check.py <inputs.json> <out.json>
Exit 0 when out.json is written. Exit 2 when the inputs cannot be read.

A printed figure is a JSON string exactly as printed ("0.86", ".810") and is parsed with
decimal.Decimal, never float. A figure printed with no decimal point ("1", "0") is exact, except a
percent, which stands for half a percentage point, and a fit figure (consistency, PRI, coverage),
which stands for half a unit in the first decimal (0.05), since a paper that strips trailing zeros
prints "1" for "1.00" or "1.0"; any other figure stands for half a unit in its last digit either
side. An exact count is a JSON integer of at most MAX_COUNT.
"""
from __future__ import annotations

import json
import re
import sys
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

TOL = Decimal("0.005")
HALF = Decimal("0.50")
CONVENTION = Decimal("0.90")
FLOORS = {"pri": Decimal("0.50"), "raw_consistency": Decimal("0.75")}
MAX_CONDITIONS = 30
MAX_COUNT = 10 ** 12  # input cap: no paper counts more cases or rows; keeps every output integer printable
BARE_FIT_HALF = Decimal("0.05")  # a stripped "1.00" or "1.0": half a unit in the first decimal
RS = "_rounding_sensitive"
KINDS = {
    "fit_table": ("B6", "B7"),
    "truth_table": ("B3", "B6", "B7"),
    "design": ("B3", "B5", "B7"),
    "necessity": ("B7", "B8"),
    "memberships": ("B3", "B4", "B7"),
}
REASON_CHECK = {
    "cases_exceed_n": "B3",
    "observed_rows_impossible": "B5",
    "remainder_share_mismatch": "B5",
    "pri_below_half": "B6",
    "row_coded_against_cutoff": "B6",
    "unique_exceeds_raw": "B7",
    "solution_coverage_below_max_raw": "B7",
    "solution_coverage_above_sum_raw": "B7",
    "unique_sum_exceeds_solution": "B7",
    "pri_exceeds_consistency": "B7",
    "value_out_of_range": "B7",
    "frequency_rows_exceed_n": "B7",
    "recomputed_mismatch": "B7",
    "necessary_below_threshold": "B8",
}
NUMBER = re.compile(r"^-?\d+(\.\d+)?$")
NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")


class RecordError(Exception):
    pass


# --- parsing -------------------------------------------------------------------------------

def _dec(value, field: str, percent: bool = False, fit: bool = False):
    """A printed figure: (value, half unit). None when the field is null. `fit` marks a consistency,
    PRI, or coverage figure, whose bare whole number stands for a stripped one- or two-decimal print."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise RecordError(f"field '{field}' must be a string exactly as printed, not {value!r}")
    s = value.strip().replace("−", "-")
    if s.startswith("."):
        s = "0" + s
    elif s.startswith("-."):
        s = "-0" + s[1:]
    if len(s) > 40 or not NUMBER.match(s):
        raise RecordError(f"field '{field}' is not a printed number: {value!r}")
    places = len(s.split(".", 1)[1]) if "." in s else 0
    v = Decimal(s)
    if places:
        half = Decimal(5).scaleb(-(places + 1))
    else:
        half = Decimal("0.5") if percent else (BARE_FIT_HALF if fit else Decimal(0))
    if percent:
        v, half = v / 100, half / 100
    return v, half


def _count(value, field: str, required: bool = False):
    if value is None:
        if required:
            raise RecordError(f"field '{field}' is required")
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RecordError(f"field '{field}' must be a whole number of zero or more, not {value!r}")
    if value > MAX_COUNT:
        raise RecordError(f"field '{field}' is above the input cap of {MAX_COUNT} (10**12)")
    return value


def _flag(value, field: str) -> bool:
    if value is None:
        return False
    if not isinstance(value, bool):
        raise RecordError(f"field '{field}' must be true or false, not {value!r}")
    return value


def _literals(label: str):
    """'A*B*~C' as a frozenset of (negated, name); None when the label is not a formula."""
    if not isinstance(label, str):
        return None
    out = []
    for part in label.split("*"):
        part = part.strip()
        neg = part.startswith("~")
        name = part[1:].strip() if neg else part
        if not NAME.match(name):
            return None
        out.append((neg, name))
    names = [n for _, n in out]
    if len(set(names)) != len(names):
        return None
    return frozenset(out)


def _s(v) -> str:
    """A computed value for the output: exact Decimals as they are, fractions to four places."""
    if isinstance(v, Fraction):
        q = round(v * 10000)
        return f"{'-' if q < 0 else ''}{abs(q) // 10000}.{abs(q) % 10000:04d}"
    return str(v)


class Out:
    """Violations, facts, and skipped checks, each filed under its check id."""

    def __init__(self, kind: str):
        self.checks = KINDS[kind]
        self.hits = {c: [] for c in self.checks}
        self.facts = {c: {} for c in self.checks}
        self.skipped = {c: [] for c in self.checks}

    def hit(self, reason: str, **info) -> None:
        base = reason[: -len(RS)] if reason.endswith(RS) else reason
        self.hits[REASON_CHECK[base]].append(dict(reason=reason, **info))

    def fact(self, check: str, key: str, value) -> None:
        self.facts[check][key] = value

    def skip(self, check: str, why: str) -> None:
        self.skipped[check].append(why)


def _tol(a, b) -> Decimal:
    """The settled 0.005 when two figures are printed to the same number of decimals; when they are not,
    the two figures' printed rounding summed, if that is wider."""
    return TOL if a[1] == b[1] else max(TOL, a[1] + b[1])


def _in_range(out: Out, where: str, value, field: str) -> None:
    if value is not None and not Decimal(0) <= value[0] <= Decimal(1):
        out.hit("value_out_of_range", where=where, field=field, value=str(value[0]))


# --- fit_table -----------------------------------------------------------------------------

def _parse_fit(rec: dict) -> dict:
    outcome = rec.get("outcome", "presence")
    if outcome not in ("presence", "absence"):
        raise RecordError("field 'outcome' must be 'presence' or 'absence'")
    terms = rec.get("terms")
    if not isinstance(terms, list) or not terms or not all(isinstance(t, dict) for t in terms):
        raise RecordError("field 'terms' must be a non-empty list of configurations")
    parsed = []
    for i, t in enumerate(terms, 1):
        label = t.get("label")
        if not isinstance(label, str) or not label.strip():
            raise RecordError(f"term {i} needs a 'label'")
        parsed.append({
            "label": label.strip(),
            "raw_consistency": _dec(t.get("raw_consistency"), f"terms[{i}].raw_consistency", fit=True),
            "pri": _dec(t.get("pri"), f"terms[{i}].pri", fit=True),
            "raw_coverage": _dec(t.get("raw_coverage"), f"terms[{i}].raw_coverage", fit=True),
            "unique_coverage": _dec(t.get("unique_coverage"), f"terms[{i}].unique_coverage", fit=True),
            "headline": _flag(t.get("headline"), f"terms[{i}].headline"),
        })
    return {
        "outcome": outcome,
        "terms": parsed,
        "solution_consistency": _dec(rec.get("solution_consistency"), "solution_consistency", fit=True),
        "solution_coverage": _dec(rec.get("solution_coverage"), "solution_coverage", fit=True),
        "consistency_cutoff": _dec(rec.get("consistency_cutoff"), "consistency_cutoff"),
        "crisp_outcome": _flag(rec.get("crisp_outcome"), "crisp_outcome"),
        "split_unclear": _flag(rec.get("split_unclear"), "split_unclear"),
    }


def _fit_table(rec: dict, out: Out) -> None:
    p = _parse_fit(rec)
    terms, sol_cov = p["terms"], p["solution_coverage"]
    _in_range(out, "solution", p["solution_consistency"], "solution_consistency")
    _in_range(out, "solution", sol_cov, "solution_coverage")
    below, headline = [], []
    for t in terms:
        w = t["label"]
        for f in ("raw_consistency", "pri", "raw_coverage", "unique_coverage"):
            _in_range(out, w, t[f], f)
        raw, uniq, cons, pri = t["raw_coverage"], t["unique_coverage"], t["raw_consistency"], t["pri"]
        if raw and uniq and uniq[0] > raw[0] + _tol(uniq, raw):
            out.hit("unique_exceeds_raw", where=w, unique_coverage=str(uniq[0]), raw_coverage=str(raw[0]))
        if cons and pri and pri[0] > cons[0] + _tol(pri, cons):
            out.hit("pri_exceeds_consistency", where=w, pri=str(pri[0]), raw_consistency=str(cons[0]))
        if pri and pri[0] < HALF - TOL:
            out.hit("pri_below_half", where=w, pri=str(pri[0]))
        cut = p["consistency_cutoff"]
        if cut and cons and cons[0] < cut[0] - TOL:
            below.append({"term": w, "raw_consistency": str(cons[0]), "cutoff": str(cut[0])})
        if t["headline"]:
            headline.append(w)
    if below:
        out.fact("B6", "term_below_cutoff", below)
    if headline:
        out.fact("B6", "headline_terms", headline)
    if p["split_unclear"]:
        out.skip("B7", "the chart could not be split into one solution per record (split_unclear), "
                       "so the solution coverage inequalities were not computed")
        return
    raws = [t["raw_coverage"] for t in terms]
    uniqs = [t["unique_coverage"] for t in terms]
    if sol_cov is None:
        out.skip("B7", "no solution coverage, so the solution coverage inequalities were not computed")
        return
    known = [r for r in raws if r is not None]
    top = max(known, key=lambda r: r[0]) if known else None
    if top and sol_cov[0] < top[0] - _tol(sol_cov, top):
        out.hit("solution_coverage_below_max_raw", where="solution", solution_coverage=str(sol_cov[0]),
                largest_raw_coverage=str(max(r[0] for r in known)))
    k = len(terms)
    if None in raws:
        out.skip("B7", "a raw coverage is missing, so 'solution coverage at most the sum of raw coverages' "
                       "was not computed")
    else:
        excess = sol_cov[0] - sum(r[0] for r in raws)
        bound = sol_cov[1] + sum(r[1] for r in raws)
        if excess > TOL:
            reason = "solution_coverage_above_sum_raw" + (RS if excess <= bound else "")
            out.hit(reason, where="solution", solution_coverage=str(sol_cov[0]),
                    sum_raw_coverage=str(sum(r[0] for r in raws)), excess=str(excess), rounding_bound=str(bound))
    if None in uniqs:
        out.skip("B7", "a unique coverage is missing, so 'unique coverages sum to at most solution coverage' "
                       "was not computed")
    else:
        excess = sum(u[0] for u in uniqs) - sol_cov[0]
        bound = sol_cov[1] + sum(u[1] for u in uniqs)
        if excess > TOL * k:
            reason = "unique_sum_exceeds_solution" + (RS if excess <= bound else "")
            out.hit(reason, where="solution", sum_unique_coverage=str(sum(u[0] for u in uniqs)),
                    solution_coverage=str(sol_cov[0]), excess=str(excess), tolerance=str(TOL * k),
                    rounding_bound=str(bound))


# --- truth_table ---------------------------------------------------------------------------

def _truth_table(rec: dict, out: Out) -> None:
    rows = rec.get("rows")
    if not isinstance(rows, list) or not rows or not all(isinstance(r, dict) for r in rows):
        raise RecordError("field 'rows' must be a non-empty list of rows")
    ccut = _dec(rec.get("consistency_cutoff"), "consistency_cutoff")
    pcut = _dec(rec.get("pri_cutoff"), "pri_cutoff")
    fcut = _count(rec.get("frequency_cutoff"), "frequency_cutoff")
    gap = _flag(rec.get("consistency_gap"), "consistency_gap")
    complete = _flag(rec.get("complete"), "complete")
    _flag(rec.get("crisp_outcome"), "crisp_outcome")
    n_cases = _count(rec.get("n_cases"), "n_cases")
    total, zero_above = 0, []
    for i, r in enumerate(rows, 1):
        w = f"row {i}"
        n = _count(r.get("n"), f"rows[{i}].n", required=True)
        coded = r.get("outcome")
        coded = {"1": 1, "0": 0}.get(coded, coded) if isinstance(coded, str) else coded
        if isinstance(coded, bool) or coded not in (1, 0, "C", "remainder"):
            raise RecordError(f"rows[{i}].outcome must be 1, 0, 'C', or 'remainder'")
        total += n
        if coded == "remainder":
            continue
        cons = _dec(r.get("raw_consistency"), f"rows[{i}].raw_consistency", fit=True)
        pri = _dec(r.get("pri"), f"rows[{i}].pri", fit=True)
        _in_range(out, w, cons, "raw_consistency")
        _in_range(out, w, pri, "pri")
        if cons and pri and pri[0] > cons[0] + _tol(pri, cons):
            out.hit("pri_exceeds_consistency", where=w, pri=str(pri[0]), raw_consistency=str(cons[0]))
        if coded == 1 and pri and pri[0] < HALF - TOL:
            out.hit("pri_below_half", where=w, pri=str(pri[0]))
        if gap or coded == "C":
            continue
        if coded == 1:
            against = []
            if ccut and cons and cons[0] < ccut[0] - TOL:
                against.append(f"raw consistency {cons[0]} below the stated cutoff {ccut[0]}")
            if pcut and pri and pri[0] < pcut[0] - TOL:
                against.append(f"PRI {pri[0]} below the stated cutoff {pcut[0]}")
            if fcut is not None and n < fcut:
                against.append(f"{n} cases below the stated frequency cutoff {fcut}")
            if against:
                out.hit("row_coded_against_cutoff", where=w, detail="; ".join(against))
        elif coded == 0 and (ccut or pcut or fcut is not None):
            meets = ((not ccut or (cons is not None and cons[0] >= ccut[0]))
                     and (not pcut or (pri is not None and pri[0] >= pcut[0]))
                     and (fcut is None or n >= fcut))
            if meets:
                zero_above.append(w)
    out.fact("B3", "cases_in_table", total)
    if n_cases is not None and total > n_cases:
        out.hit("cases_exceed_n", where="truth table", cases_in_table=total, n_cases=n_cases)
    if complete and n_cases is not None and total < n_cases:
        out.fact("B3", "cases_short_of_n", n_cases - total)
    if zero_above:
        out.fact("B6", "rows_coded_0_meeting_every_cutoff", zero_above)
    if gap:
        out.fact("B6", "consistency_gap", True)


# --- design --------------------------------------------------------------------------------

def _logical_rows(conditions) -> int:
    if isinstance(conditions, bool):
        raise RecordError("field 'conditions' must be a number or a list of category counts")
    if isinstance(conditions, int):
        if not 1 <= conditions <= MAX_CONDITIONS:
            raise RecordError(f"field 'conditions' must be between 1 and {MAX_CONDITIONS}")
        return 2 ** conditions
    if isinstance(conditions, list) and conditions and len(conditions) <= MAX_CONDITIONS:
        rows = 1
        for c in conditions:
            if isinstance(c, bool) or not isinstance(c, int) or not 2 <= c <= 10:
                raise RecordError("each category count in 'conditions' must be a whole number from 2 to 10")
            rows *= c
        return rows
    raise RecordError("field 'conditions' must be a number or a list of category counts")


def _design(rec: dict, out: Out) -> None:
    logical = _logical_rows(rec.get("conditions"))
    n = _count(rec.get("n_cases"), "n_cases", required=True)
    if n == 0:
        raise RecordError("field 'n_cases' must be at least 1")
    fcut = _count(rec.get("frequency_cutoff"), "frequency_cutoff")
    kept = _count(rec.get("rows_kept"), "rows_kept")
    observed = _count(rec.get("observed_rows"), "observed_rows")
    in_tt = _count(rec.get("cases_in_truth_table"), "cases_in_truth_table")
    share = _dec(rec.get("remainder_share"), "remainder_share", percent=_flag(rec.get("percent"), "percent"))
    out.fact("B5", "logical_rows", logical)
    out.fact("B5", "least_remainder_share", _s(1 - Fraction(min(n, logical), logical)))
    if fcut is not None and kept is not None and fcut * kept > n:
        out.hit("frequency_rows_exceed_n", where="design", frequency_cutoff=fcut, rows_kept=kept, n_cases=n)
    if observed is not None and (observed > logical or observed > n):
        out.hit("observed_rows_impossible", where="design", observed_rows=observed, logical_rows=logical,
                n_cases=n)
    if share is not None:
        lo, hi = share[0] - share[1], share[0] + share[1]
        matches = {}
        for name, rows in (("observed_rows", observed), ("rows_kept", kept)):
            if rows is not None:
                s = 1 - Fraction(rows, logical)
                matches[name] = Fraction(lo) <= s <= Fraction(hi)
        if len(matches) == 2 and not any(matches.values()):
            out.hit("remainder_share_mismatch", where="design", remainder_share=str(share[0]),
                    from_observed_rows=_s(1 - Fraction(observed, logical)),
                    from_rows_kept=_s(1 - Fraction(kept, logical)))
        elif matches and not any(matches.values()):
            out.fact("B5", "remainder_share_unmatched", {"stated": str(share[0]), "compared_with": list(matches)})
        elif matches:
            out.fact("B5", "remainder_share_matches", [k for k, v in matches.items() if v])
    if in_tt is not None:
        if in_tt > n:
            out.hit("cases_exceed_n", where="design", cases_in_truth_table=in_tt, n_cases=n)
        elif in_tt < n:
            out.fact("B3", "cases_short_of_n", n - in_tt)


# --- necessity -----------------------------------------------------------------------------

def _parse_necessity(rec: dict) -> dict:
    rows = rec.get("rows")
    if not isinstance(rows, list) or not rows or not all(isinstance(r, dict) for r in rows):
        raise RecordError("field 'rows' must be a non-empty list of conditions")
    outcome = rec.get("outcome", "presence")
    if outcome not in ("presence", "absence"):
        raise RecordError("field 'outcome' must be 'presence' or 'absence'")
    parsed = []
    for i, r in enumerate(rows, 1):
        cond = r.get("condition")
        if not isinstance(cond, str) or not cond.strip():
            raise RecordError(f"rows[{i}] needs a 'condition'")
        parsed.append({"condition": cond.strip(), "negated": _flag(r.get("negated"), f"rows[{i}].negated"),
                       "consistency": _dec(r.get("consistency"), f"rows[{i}].consistency", fit=True),
                       "coverage": _dec(r.get("coverage"), f"rows[{i}].coverage", fit=True),
                       "declared_necessary": _flag(r.get("declared_necessary"), f"rows[{i}].declared_necessary")})
    return {"outcome": outcome, "rows": parsed, "threshold": _dec(rec.get("threshold"), "threshold")}


def _necessity(rec: dict, out: Out) -> None:
    p = _parse_necessity(rec)
    for r in p["rows"]:
        w = ("~" if r["negated"] else "") + r["condition"]
        _in_range(out, w, r["consistency"], "consistency")
        _in_range(out, w, r["coverage"], "coverage")
        if r["declared_necessary"] and r["consistency"] is not None:
            limit, source = (p["threshold"][0], "paper") if p["threshold"] else (CONVENTION, "convention 0.90")
            if r["consistency"][0] < limit - TOL:
                out.hit("necessary_below_threshold", where=w, consistency=str(r["consistency"][0]),
                        threshold=str(limit), threshold_source=source)


# --- memberships: recompute within the rounding of the printed scores ----------------------

def _fr(d: Decimal) -> Fraction:
    return Fraction(d)


def _box(value, field: str):
    """A printed membership as (low, high, printed, exact) Fractions within [0, 1]."""
    if isinstance(value, int) and not isinstance(value, bool) and value in (0, 1):
        v = Fraction(value)
        return v, v, Decimal(value), True
    p = _dec(value, field)
    if p is None or not Decimal(0) <= p[0] <= Decimal(1):
        raise RecordError(f"membership '{field}' must be printed between 0 and 1, not {value!r}")
    v, h = p
    return max(Fraction(0), _fr(v - h)), min(Fraction(1), _fr(v + h)), v, h == 0


def _neg(b):
    return 1 - b[1], 1 - b[0]


def _grid(xl, xh, yl, yh):
    half = Fraction(1, 2)
    xs = sorted({v for v in (xl, xh, yl, yh, 1 - yl, 1 - yh, half) if xl <= v <= xh})
    ys = sorted({v for v in (yl, yh, xl, xh, 1 - xl, 1 - xh, half) if yl <= v <= yh})
    return [(x, y) for x in xs for y in ys]


def _nd(kind: str, x, y):
    """Numerator and denominator of one case's share of a fit figure."""
    if kind == "consistency":
        return min(x, y), x
    if kind == "coverage":
        return min(x, y), y
    m = min(x, y, 1 - y)
    return min(x, y) - m, x - m


def _extreme(points, sense: int):
    """Dinkelbach's method: the exact max (sense 1) or min (sense -1) of sum N / sum D over one point
    per case. N <= D and N >= 0 at every point, so each step's denominator is positive."""
    choice = [max(p, key=lambda nd: nd[1]) for p in points]
    lam = Fraction(sum(c[0] for c in choice)) / sum(c[1] for c in choice)
    while True:
        pick = max if sense > 0 else min
        choice = [pick(p, key=lambda nd: nd[0] - lam * nd[1]) for p in points]
        num, den = sum(c[0] for c in choice), sum(c[1] for c in choice)
        gap = num - lam * den
        if gap == 0 or (gap < 0) == (sense > 0):
            return lam
        lam = Fraction(num) / den


def ratio_range(boxes, kind: str):
    """Exact range of a fit figure when each case's (X, Y) moves within its box; None when the
    denominator can reach zero."""
    points = [[_nd(kind, x, y) for x, y in _grid(xl, xh, yl, yh)] for (xl, xh), (yl, yh) in boxes]
    if sum(min(d for _, d in p) for p in points) == 0:
        return None
    return _extreme(points, -1), _extreme(points, 1)


def _point(xs, ys, kind: str):
    num = sum(_nd(kind, x, y)[0] for x, y in zip(xs, ys))
    den = sum(_nd(kind, x, y)[1] for x, y in zip(xs, ys))
    return None if den == 0 else Fraction(num) / den


def _memberships(rec: dict, out: Out, by_id: dict) -> None:
    if rec.get("variant") == "mvQCA":
        for c in out.checks:
            out.skip(c, "mvQCA memberships are not recomputed in version one")
        return
    sets = rec.get("sets")
    if not isinstance(sets, list) or not sets or not all(isinstance(s, str) and NAME.match(s) for s in sets):
        raise RecordError("field 'sets' must list the set names (letters, digits, '_', '.', '-')")
    if len(set(sets)) != len(sets):
        raise RecordError("field 'sets' names a set twice")
    outcome = rec.get("outcome")
    if outcome not in sets:
        raise RecordError("field 'outcome' must be one of 'sets'")
    conditions = rec.get("conditions")
    if not isinstance(conditions, list) or not conditions or not all(c in sets and c != outcome for c in conditions):
        raise RecordError("field 'conditions' must list sets other than the outcome")
    cases = rec.get("cases")
    if not isinstance(cases, list) or not cases or not all(isinstance(c, dict) for c in cases):
        raise RecordError("field 'cases' must be a non-empty list of mappings")
    states_half = _flag(rec.get("states_half"), "states_half")
    boxes, printed = {s: [] for s in sets}, {s: [] for s in sets}
    unknown_half = {s: 0 for s in sets}
    for i, c in enumerate(cases, 1):
        for s in sets:
            if s not in c:
                raise RecordError(f"case {i} has no value for set '{s}'")
            lo, hi, v, exact = _box(c[s], f"cases[{i}].{s}")
            boxes[s].append((lo, hi))
            printed[s].append(v)
            if v == Decimal("0.5") and not exact and not states_half and len(str(c[s]).split(".")[-1]) < 3:
                unknown_half[s] += 1
    n = len(cases)
    out.fact("B4", "share_above_half", {s: _s(Fraction(sum(1 for v in printed[s] if v > HALF), n)) for s in sets})
    out.fact("B3", "printed_half_row_unknown", {s: k for s, k in unknown_half.items() if k})
    rows, row_unknown, no_row = {}, 0, 0
    for i in range(n):
        vals = [(s, printed[s][i]) for s in conditions]
        if any(v == Decimal("0.5") for _, v in vals):
            ambiguous = any(v == Decimal("0.5") and boxes[s][i][0] != boxes[s][i][1] and not states_half
                            and len(str(cases[i][s]).split(".")[-1]) < 3 for s, v in vals)
            if ambiguous:
                row_unknown += 1
            else:
                no_row += 1
            continue
        key = "*".join(("" if v > HALF else "~") + s for s, v in vals)
        rows[key] = rows.get(key, 0) + 1
    out.fact("B3", "observed_rows", rows)
    out.fact("B3", "cases_in_rows", n - row_unknown - no_row)
    out.fact("B3", "cases_left_out", {"row_unknown": row_unknown, "at_exactly_half": no_row})
    ybox = boxes[outcome]
    crisp_y = all(lo == hi for lo, hi in ybox)
    compare = rec.get("compare") or []
    if not isinstance(compare, list):
        raise RecordError("field 'compare' must list record ids")
    ranges = []
    for rid in compare:
        target = by_id.get(rid) if isinstance(rid, str) else None
        if target is None or target.get("kind") not in ("fit_table", "necessity"):
            out.skip("B7", f"compare names '{rid}', which is not a fit_table or necessity record")
            continue
        try:
            parsed = (_parse_fit if target["kind"] == "fit_table" else _parse_necessity)(target)
        except RecordError as e:
            out.skip("B7", f"record '{rid}' is invalid ({e}), so it was not recomputed")
            continue
        y = ybox if parsed["outcome"] == "presence" else [_neg(b) for b in ybox]
        yp = [_fr(v) if parsed["outcome"] == "presence" else 1 - _fr(v) for v in printed[outcome]]
        if target["kind"] == "fit_table":
            _recompute_fit(rid, parsed, boxes, y, yp, crisp_y, printed, out, ranges)
        else:
            _recompute_necessity(rid, parsed, boxes, y, out, ranges)
    if ranges:
        out.fact("B7", "recomputed_ranges", ranges)


def _term_boxes(lits, boxes, y):
    out = []
    for i, yb in enumerate(y):
        los, his = [], []
        for neg, name in lits:
            b = _neg(boxes[name][i]) if neg else boxes[name][i]
            los.append(b[0])
            his.append(b[1])
        out.append(((min(los), min(his)), yb))
    return out


def _compare(rid, where, field, reported, rng, out, ranges):
    if reported is None:
        return
    if rng is None:
        out.skip("B7", f"{rid}, {where}: {field} has a denominator that can reach zero, so it was not recomputed")
        return
    lo, hi = rng
    r_lo, r_hi = _fr(reported[0] - reported[1]), _fr(reported[0] + reported[1])
    ranges.append({"record": rid, "where": where, "field": field, "reported": str(reported[0]),
                   "recomputed_low": _s(lo), "recomputed_high": _s(hi)})
    if r_hi < lo or r_lo > hi:
        out.hit("recomputed_mismatch", record=rid, where=where, field=field, reported=str(reported[0]),
                recomputed_low=_s(lo), recomputed_high=_s(hi))


def _recompute_fit(rid, parsed, boxes, y, yp, crisp_y, printed, out, ranges):
    names = set(boxes)
    sol_x = None
    for t in parsed["terms"]:
        lits = _literals(t["label"])
        if lits is None or not all(name in names for _, name in lits):
            out.skip("B7", f"{rid}, {t['label']}: the label is not a formula of the printed sets, "
                           "so it was not recomputed")
            sol_x = False
            continue
        tb = _term_boxes(lits, boxes, y)
        _compare(rid, t["label"], "raw_consistency", t["raw_consistency"], ratio_range(tb, "consistency"), out,
                 ranges)
        _compare(rid, t["label"], "raw_coverage", t["raw_coverage"], ratio_range(tb, "coverage"), out, ranges)
        if not crisp_y:
            rng = ratio_range(tb, "pri")
            _compare(rid, t["label"], "pri", t["pri"], rng, out, ranges)
            if t["headline"]:
                _below_floor(rid, t["label"], "pri", t["pri"], rng, out)
        if t["headline"]:
            _below_floor(rid, t["label"], "raw_consistency", t["raw_consistency"],
                         ratio_range(tb, "consistency"), out)
        if sol_x is not False:
            xs = [min(1 - _fr(printed[n][i]) if neg else _fr(printed[n][i]) for neg, n in lits)
                  for i in range(len(yp))]
            sol_x = xs if sol_x is None else [max(a, b) for a, b in zip(sol_x, xs)]
            t["_xs"] = xs
    if not sol_x:
        return
    sol_cov = _point(sol_x, yp, "coverage")
    facts = {"record": rid, "solution_consistency": _s(_point(sol_x, yp, "consistency") or 0),
             "solution_coverage": _s(sol_cov or 0), "unique_coverage": {}}
    for t in parsed["terms"]:
        others = [u["_xs"] for u in parsed["terms"] if u is not t]
        rest = [max(col) for col in zip(*others)] if others else [Fraction(0)] * len(yp)
        rest_cov = _point(rest, yp, "coverage")
        if sol_cov is not None and rest_cov is not None:
            facts["unique_coverage"][t["label"]] = _s(sol_cov - rest_cov)
    out.fact("B7", f"at_printed_values:{rid}", facts)


def _below_floor(rid, where, field, reported, rng, out):
    """A headline figure whose recomputed range lies below its floor, reported only when the paper's
    printed value is itself below the floor or its rounding interval misses the recomputed range; a
    correct print a hair above the true value ("0.75" for 0.748) is not a misreport."""
    floor = FLOORS[field]
    if reported is None or rng is None or rng[1] >= _fr(floor):
        return
    if reported[0] < floor or rng[1] < _fr(reported[0] - reported[1]):
        key = "recomputed_pri_below_floor" if field == "pri" else "recomputed_consistency_below_floor"
        out.facts["B7"].setdefault(key, []).append({"record": rid, "term": where, "reported": str(reported[0]),
                                                    "recomputed_high": _s(rng[1]), "floor": str(floor)})


def _recompute_necessity(rid, parsed, boxes, y, out, ranges):
    for r in parsed["rows"]:
        where = ("~" if r["negated"] else "") + r["condition"]
        if r["condition"] not in boxes:
            out.skip("B7", f"{rid}, {where}: the condition is not one of the printed sets, so it was not recomputed")
            continue
        cb = [_neg(b) if r["negated"] else b for b in boxes[r["condition"]]]
        tb = list(zip(cb, y))
        _compare(rid, where, "consistency", r["consistency"], ratio_range(tb, "coverage"), out, ranges)
        _compare(rid, where, "coverage", r["coverage"], ratio_range(tb, "consistency"), out, ranges)


# --- presence against absence --------------------------------------------------------------

def _negated_overlap(recs: list) -> dict:
    """For each fit_table id: configurations whose conditions all appear in a configuration of a
    fit_table for the other outcome, or that contain one."""
    fits = []
    for rec in recs:
        try:
            fits.append((rec["id"], _parse_fit(rec)))
        except RecordError:
            continue
    found = {}
    for rid, p in fits:
        for sid, q in fits:
            if sid == rid or q["outcome"] == p["outcome"]:
                continue
            for t in p["terms"]:
                a = _literals(t["label"])
                for u in q["terms"]:
                    b = _literals(u["label"])
                    if a and b and (a <= b or b <= a):
                        found.setdefault(rid, []).append({"term": t["label"], "negated_record": sid,
                                                          "negated_term": u["label"]})
    return found


# --- driver --------------------------------------------------------------------------------

def _message(check: str, hits: list, skipped: list) -> str:
    parts = []
    for h in hits:
        detail = ", ".join(f"{k} {v}" for k, v in h.items() if k not in ("reason", "where"))
        parts.append(f"{h['reason']} at {h.get('where', '')}: {detail}".strip())
    parts.extend(f"not computed: {s}" for s in skipped)
    return "; ".join(parts) if parts else f"{check}: no problem found."


def run_records(records: list) -> list:
    by_id, seen, results = {}, set(), []
    for rec in records:
        if isinstance(rec, dict) and isinstance(rec.get("id"), str) and rec["id"] not in by_id:
            by_id[rec["id"]] = rec
    fit_recs = [r for r in records if isinstance(r, dict) and r.get("kind") == "fit_table"
                and isinstance(r.get("id"), str)]
    overlap = _negated_overlap(fit_recs)
    for rec in records:
        rid = rec.get("id") if isinstance(rec, dict) else None
        kind = rec.get("kind") if isinstance(rec, dict) else None
        base = {"id": rid if isinstance(rid, str) else None, "kind": kind if isinstance(kind, str) else None}
        try:
            if not isinstance(rec, dict):
                raise RecordError("a record must be a JSON object")
            if not isinstance(rid, str) or not rid.strip():
                raise RecordError("field 'id' must be a non-empty string")
            if rid in seen:
                raise RecordError(f"id '{rid}' is used twice")
            seen.add(rid)
            if not isinstance(kind, str) or kind not in KINDS:
                raise RecordError(f"field 'kind' must be one of {', '.join(KINDS)}")
            if not isinstance(rec.get("source"), str):
                raise RecordError("field 'source' (table and page) is required")
            if "cells" in rec and not isinstance(rec["cells"], list):
                raise RecordError("field 'cells' must be a list")
            out = Out(kind)
            if kind == "fit_table":
                _fit_table(rec, out)
                if rid in overlap:
                    out.fact("B6", "in_negated_solution", overlap[rid])
            elif kind == "truth_table":
                _truth_table(rec, out)
            elif kind == "design":
                _design(rec, out)
            elif kind == "necessity":
                _necessity(rec, out)
            else:
                _memberships(rec, out, by_id)
        except RecordError as e:
            checks = ", ".join(KINDS[kind]) if isinstance(kind, str) and kind in KINDS else None
            results.append(dict(base, check=checks, status="invalid", flag=False, reasons=[], facts={},
                                message=str(e)))
            continue
        for check in out.checks:
            hits = out.hits[check]
            reasons = sorted({h["reason"] for h in hits})
            facts = dict(out.facts[check])
            if hits:
                facts["violations"] = hits
            results.append(dict(base, check=check, status="not_computable" if out.skipped[check] else "ok",
                                flag=any(not r.endswith(RS) for r in reasons), reasons=reasons, facts=facts,
                                message=_message(check, hits, out.skipped[check])))
    return results


def _no_constants(name):
    raise ValueError(f"{name} is not allowed")


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("usage: qca_check.py <inputs.json> <out.json>", file=sys.stderr)
        return 2
    src, dst = Path(argv[0]), Path(argv[1])
    try:
        records = json.loads(src.read_text(encoding="utf-8"), parse_constant=_no_constants)
    except (OSError, ValueError, RecursionError) as e:
        print(f"cannot read {src}: {e}", file=sys.stderr)
        return 2
    if not isinstance(records, list):
        print(f"{src} must hold a JSON list of records", file=sys.stderr)
        return 2
    results = run_records(records)
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(json.dumps({"results": results}, indent=1, allow_nan=False) + "\n", encoding="utf-8")
    except (OSError, ValueError) as e:
        print(f"cannot write {dst}: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
