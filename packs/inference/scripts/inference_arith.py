#!/usr/bin/env python3
"""Arithmetic for the inference pack: multiple-testing families, stated effect sizes, and intervals.

Every number is read as printed (a JSON string), so its rounding is known. The rounding and p-value
functions come from the core's pvalues.py; this script does not reimplement them. A result is
flagged only when it holds for every value the printed digits allow.

Usage: inference_arith.py <inputs.json> <out.json>

Units: pct_of_mean and pct_change values are fractions (0.02 means 2 percent), for both the
claimed value and the computed one.
Exit 0 when it ran (whether or not anything is flagged); 2 when the inputs file is missing, is not
JSON, or is not a list, or when pvalues.py cannot be imported.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "skills" / "review" / "scripts"))
try:
    import pvalues
except ImportError:
    pvalues = None  # main() reports this and exits 2

METHODS = ("bonferroni", "holm", "bh")
REL_TOL = 1e-9  # values that touch at a rounding boundary count as consistent (lenient reading)


class RecordError(ValueError):
    pass


class NotComputable(RecordError):
    """The record is well formed but the printed digits leave the quantity undetermined."""


def _num(rec, key, required=True):
    """(value, half_unit) for a printed number in rec[key]; None when absent and not required."""
    raw = rec.get(key)
    if raw is None or str(raw).strip() == "":
        if required:
            raise RecordError(f"missing field '{key}'")
        return None
    parsed = pvalues.parse_printed(str(raw))
    if parsed is None:
        raise RecordError(f"field '{key}' is not a number: {raw!r}")
    return parsed


def _test_p(test):
    """(low, point, high) two-sided p for one test in a family."""
    if test.get("p") not in (None, ""):
        rng = pvalues.printed_p_range(str(test["p"]))
        if rng is None:
            raise RecordError(f"test {test.get('id')!r}: p is not a p-value: {test['p']!r}")
        point = pvalues.parse_printed(str(test["p"]).strip().lstrip("<=").strip())
        return rng[0], (point[0] if point else rng[1]), rng[1]
    b, se = _num(test, "b"), _num(test, "se")
    bounds = pvalues.abs_t_bounds(str(test["b"]), str(test["se"]))
    if bounds is None:
        raise RecordError(f"test {test.get('id')!r}: the standard error must be positive")
    lo, hi = pvalues.p_range(*bounds)
    return lo, pvalues.p_normal(abs(b[0]) / se[0]), hi


def bonferroni(ps):
    m = len(ps)
    return [min(1.0, m * p) for p in ps]


def holm(ps):
    m = len(ps)
    order = sorted(range(m), key=lambda i: ps[i])
    out, running = [0.0] * m, 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * ps[i]))
        out[i] = running
    return out


def bh(ps):
    m = len(ps)
    order = sorted(range(m), key=lambda i: ps[i], reverse=True)
    out, running = [0.0] * m, 1.0
    for k, i in enumerate(order):
        running = min(running, ps[i] * m / (m - k))
        out[i] = running
    return out


ADJUST = {"bonferroni": bonferroni, "holm": holm, "bh": bh}


def _family(rec):
    tests = rec.get("tests")
    if not isinstance(tests, list) or len(tests) < 2:
        raise RecordError("a family needs a list 'tests' of at least two tests")
    if not all(isinstance(t, dict) for t in tests):
        raise RecordError("every entry in 'tests' must be an object")
    ids = [str(t.get("id")) for t in tests]
    if len(set(ids)) != len(ids):
        raise RecordError("test ids in a family must be unique")
    triples = [_test_p(t) for t in tests]
    alpha = _num(rec, "alpha", required=False)
    alpha = alpha[0] if alpha else 0.05
    if not 0 < alpha <= 1:
        raise RecordError("alpha must satisfy 0 < alpha <= 1")
    values, facts = {"alpha": alpha, "adjusted": {}, "sure_survivors": {}, "sure_failures": {}}, []
    for method in METHODS:
        f = ADJUST[method]
        low, point, high = (f([t[k] for t in triples]) for k in range(3))
        # Each adjustment is non-decreasing in every input p, so adjusting all lows and all highs
        # bounds each adjusted p over every value the printed digits allow.
        values["adjusted"][method] = {i: {"low": lo, "point": pt, "high": hi}
                                      for i, lo, pt, hi in zip(ids, low, point, high)}
        values["sure_survivors"][method] = [i for i, hi in zip(ids, high) if hi < alpha * (1 - REL_TOL)]
        values["sure_failures"][method] = [i for i, lo in zip(ids, low) if lo > alpha * (1 + REL_TOL)]
        facts.append(f"{method}: {len(values['sure_survivors'][method])} of {len(ids)} tests surely below "
                     f"{alpha:g} after adjustment; {len(values['sure_failures'][method])} surely at or above it")
    reasons, flag = [], False
    method = rec.get("claimed_method")
    if method is not None:
        if not isinstance(method, str) or method not in METHODS:
            raise RecordError(f"claimed_method must be one of {', '.join(METHODS)}")
        listed = rec.get("claimed_survivors")
        if "claimed_survivors" in rec and not isinstance(listed, list):
            raise RecordError("claimed_survivors must be a list of test ids")
        claimed = [str(x) for x in listed or []]
        unknown = [c for c in claimed if c not in ids]
        if unknown:
            raise RecordError(f"claimed_survivors names tests not in the family: {unknown}")
        wrong = [c for c in claimed if c in values["sure_failures"][method]]
        printed_p = {str(t.get("id")) for t in tests if t.get("p") not in (None, "")}
        # Without a claimed_survivors key the paper made no survivor claim, so nothing is missed.
        # Tests built from b and se are only reported: the normal reference is anti-lenient there.
        would = ([i for i in values["sure_survivors"][method] if i not in claimed]
                 if "claimed_survivors" in rec else [])
        missed = [i for i in would if i in printed_p]
        for i in would:
            if i not in printed_p:
                facts.append(f"{i} would survive {method} on the normal reference from its coefficient and standard error; "
                             "the paper does not say so (a fact, not a flag)")
        if wrong or missed:
            flag = True
            reasons.append("claimed_adjustment_mismatch")
            if wrong:
                facts.append(f"the paper says {', '.join(wrong)} survive {method}, but the printed p-values put them at or above {alpha:g} after adjustment")
            if missed:
                facts.append(f"{', '.join(missed)} survive {method} on the printed p-values, but the paper does not say so")
    return values, reasons, flag, facts


def _box(pair):
    return pair[0] - pair[1], pair[0] + pair[1]


def _corners(f, *boxes):
    vals = [f(*c) for c in _product(boxes)]
    return min(vals), max(vals)


def _product(boxes):
    out = [()]
    for lo, hi in boxes:
        out = [c + (v,) for c in out for v in ((lo,) if lo == hi else (lo, hi))]
    return out


def _magnitude(rec):
    b, dxp = _num(rec, "b"), _num(rec, "delta_x")
    dx = dxp[0]
    dx_box = _box(dxp) if "." in str(rec["delta_x"]) else (dx, dx)
    scale = rec.get("outcome_scale", "level")
    if scale not in ("level", "log"):
        raise RecordError("outcome_scale must be 'level' or 'log'")
    mean_y, sd_y, se = _num(rec, "mean_y", False), _num(rec, "sd_y", False), _num(rec, "se", False)
    if se and se[0] <= 0:
        raise RecordError("se must be positive")
    change = lambda coef: coef * dx if scale == "level" else math.exp(coef * dx) - 1.0
    values = {"effect": change(b[0])}
    if scale == "level" and mean_y and mean_y[0] != 0:
        values["pct_of_mean"] = values["effect"] / mean_y[0]
    if scale == "level" and sd_y and sd_y[0] > 0:
        values["sd_y"] = values["effect"] / sd_y[0]
    if se:
        ends = sorted((change(b[0] - 1.96 * se[0]), change(b[0] + 1.96 * se[0])))
        values["interval"] = ends
    facts = [f"effect of a change of {dx:g} in the regressor: {values['effect']:.6g}"
             + (" (proportional change)" if scale == "log" else " (outcome units)")]
    if "pct_of_mean" in values:
        facts.append(f"that is {values['pct_of_mean']:.4g} of the outcome's mean (a fraction)")
    if "sd_y" in values:
        facts.append(f"that is {values['sd_y']:.4g} standard deviations of the outcome")

    def implied_range(key):
        """[min, max] of the implied quantity over the rounding boxes; None when a divisor box straddles zero."""
        bb = _box(b)
        if scale == "level":
            eff = lambda bv, dv: bv * dv
        else:
            eff = lambda bv, dv: math.exp(bv * dv) - 1.0
        if key == "effect":
            return _corners(eff, bb, dx_box)
        div = mean_y if key == "pct_of_mean" else sd_y
        db = _box(div)
        if db[0] <= 0 <= db[1]:
            return None
        return _corners(lambda bv, dv, yv: eff(bv, dv) / yv, bb, dx_box, db)

    reasons, flag = [], False
    claimed = rec.get("claimed")
    if claimed is not None:
        if not isinstance(claimed, dict):
            raise RecordError("claimed must be an object with 'unit' and 'value'")
        unit = claimed.get("unit")
        if not isinstance(unit, str):
            raise RecordError("claimed unit must be a string")
        if scale == "log" and unit != "pct_change":
            raise RecordError("on a log outcome state the claim as pct_change")
        key = {"level": "effect", "pct_of_mean": "pct_of_mean", "sd_y": "sd_y",
               "pct_change": "effect" if scale == "log" else None}.get(unit)
        if key is None or (key != "effect" and (mean_y if key == "pct_of_mean" else sd_y) is None):
            raise RecordError(f"claimed unit {unit!r} cannot be computed from this record")
        said = _num(claimed, "value")
        tol = _num(rec, "tolerance", False)
        tol = tol[0] if tol else 0.10
        if tol < 0:
            raise RecordError("tolerance must be zero or more")
        rng = implied_range(key)
        if rng is None:
            raise NotComputable(f"the rounding of the divisor for {unit!r} allows zero, so the size is not determined")
        lo = rng[0] - (tol + REL_TOL) * abs(rng[0])
        hi = rng[1] + (tol + REL_TOL) * abs(rng[1])
        s_lo, s_hi = said[0] - said[1], said[0] + said[1]
        computed = values.get(key, sum(rng) / 2)
        values["claimed"] = said[0]
        values["implied_range"] = list(rng)
        if s_hi < lo or s_lo > hi:
            flag = True
            reasons.append("magnitude_claim_mismatch")
            facts.append(f"the paper states {said[0]:g} ({unit}); the reported numbers give {computed:.4g} "
                         f"(anywhere from {rng[0]:.4g} to {rng[1]:.4g} given the printed rounding)")
    return values, reasons, flag, facts


def _interval(rec):
    bp, sep = _num(rec, "b"), _num(rec, "se")
    b, se = bp[0], sep[0]
    if se <= 0:
        raise RecordError("se must be positive")
    crit = _num(rec, "crit", False)
    crit = crit[0] if crit else 1.96
    lo, hi = b - crit * se, b + crit * se
    values = {"low": lo, "high": hi, "covers_zero": lo <= 0 <= hi}
    abs_lo = 0.0 if abs(b) <= bp[1] else abs(b) - bp[1]
    abs_hi = abs(b) + bp[1]
    always = abs_hi <= crit * max(0.0, se - sep[1])
    never = abs_lo > crit * (se + sep[1])
    values["zero_depends_on_rounding"] = not (always or never)
    facts = [f"interval {lo:.4g} to {hi:.4g} ({'covers' if values['covers_zero'] else 'excludes'} zero"
             + ("; whether it covers zero depends on rounding" if values["zero_depends_on_rounding"] else "") + ")"]
    bench = _num(rec, "benchmark", False)
    if bench:
        values["benchmark"] = bench[0]
        values["covers_benchmark"] = lo <= bench[0] <= hi
        gap = abs(b - bench[0])
        half = bp[1] + bench[1]
        gap_lo = 0.0 if gap <= half else gap - half
        b_always = gap + half <= crit * max(0.0, se - sep[1])
        b_never = gap_lo > crit * (se + sep[1])
        values["benchmark_depends_on_rounding"] = not (b_always or b_never)
        facts.append(f"it {'covers' if values['covers_benchmark'] else 'excludes'} the benchmark {bench[0]:g}"
                     + (f" ({rec['source_of_benchmark']})" if rec.get("source_of_benchmark") else "")
                     + ("; whether it covers the benchmark depends on rounding"
                        if values["benchmark_depends_on_rounding"] else ""))
    return values, [], False, facts


KINDS = {"family": _family, "magnitude": _magnitude, "interval": _interval}


def run_record(rec):
    out = {k: rec.get(k) for k in ("id", "kind", "check", "source")}
    out.update(status="ok", values={}, reasons=[], flag=False, facts=[])
    kind = rec.get("kind")
    if not isinstance(kind, str) or kind not in KINDS:
        out.update(status="invalid", message=f"unknown kind {kind!r}; use one of {', '.join(KINDS)}")
        return out
    try:
        values, reasons, flag, facts = KINDS[kind](rec)
    except NotComputable as e:
        out.update(status="not_computable", message=str(e))
        return out
    except (RecordError, OverflowError) as e:
        out.update(status="invalid", message=str(e))
        return out
    out.update(values=values, reasons=reasons, flag=flag, facts=facts)
    return out


def main(argv):
    if len(argv) == 2 and argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    if len(argv) != 3:
        print("Usage: inference_arith.py <inputs.json> <out.json>", file=sys.stderr)
        return 2
    if pvalues is None:
        print("cannot import pvalues.py from skills/review/scripts; is this file inside packs/inference/scripts/?",
              file=sys.stderr)
        return 2
    try:
        records = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"inputs not readable: {e}", file=sys.stderr)
        return 2
    if not isinstance(records, list):
        print("inputs must be a JSON list of records", file=sys.stderr)
        return 2
    results = [run_record(r) if isinstance(r, dict) else
               {"id": None, "status": "invalid", "message": "record is not a JSON object", "flag": False}
               for r in records]
    Path(argv[2]).write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"INFERENCE ARITH: {sum(1 for r in results if r.get('flag'))} flagged, {len(results)} records")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
