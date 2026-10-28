#!/usr/bin/env python3
"""Arithmetic for the nonlinear pack.

Turning points and end slopes of a quadratic, moderated curves, conditional slopes of a
linear interaction, moderator values outside the data, tests of a difference between two
independent estimates, and odds ratios converted to probabilities. Every number comes from
the paper through the verify agent's inputs file; nothing is estimated.

Usage: nonlinear_arith.py <inputs.json> <out.json>
Exit 0 when out.json is written. Exit 2 when the inputs cannot be read.
"""
from __future__ import annotations

import itertools
import json
import math
import re
import sys
from pathlib import Path

KINDS = ("quadratic", "moderated_quadratic", "linear_interaction", "plotted_points",
         "difference", "odds_ratio")

# Reasons that make a result a number flag. Every other reason is a fact for the claims agent.
FLAG_REASONS = {
    "tp_outside_range",
    "end_slope_insignificant",
    "end_slope_insignificant_any_cov",
    "tp_interval_leaves_range",
    "curvature_flips_in_moderator_range",
    "tp_outside_range_at_m",
    "lower_order_read_outside_range",
    "point_outside_range",
    "difference_not_distinguishable",
    "or_claim_mismatch",
}


class RecordError(Exception):
    pass


def _fmt(v: float) -> str:
    if isinstance(v, float) and math.isnan(v):
        return "undefined"
    if isinstance(v, float) and math.isinf(v):
        return "unbounded"
    return f"{v:.4g}"


# A printed number such as "0.84" or "-0.140" carries its own rounding: half a unit in the last
# printed digit. A plain JSON number is treated as exact.
_PRINTED = re.compile(r"^\s*([+-]?)(\d*)(?:\.(\d*))?(?:[eE]([+-]?\d+))?\s*$")


def _parse_printed(v: str, key: str):
    m = _PRINTED.match(v)
    if not m or not (m.group(2) or m.group(3)):
        raise RecordError(f"field '{key}' must be a number")
    value = float(v.strip())
    if not math.isfinite(value):
        raise RecordError(f"field '{key}' must be a number")
    half = 0.5 * 10.0 ** (int(m.group(4) or 0) - len(m.group(3) or ""))
    return value, half


def _num(rec: dict, key: str, required: bool = True):
    v = rec.get(key)
    if v is None:
        if required:
            raise RecordError(f"missing field '{key}'")
        return None
    if isinstance(v, str):
        return _parse_printed(v, key)[0]
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise RecordError(f"field '{key}' must be a number")
    return float(v)


def _half(rec: dict, key: str) -> float:
    v = rec.get(key)
    return _parse_printed(v, key)[1] if isinstance(v, str) else 0.0


def _positive(rec: dict, key: str, required: bool = True):
    v = _num(rec, key, required)
    if v is not None and v <= 0:
        raise RecordError(f"field '{key}' must be greater than zero")
    return v


def _range(rec: dict, lo_key: str, hi_key: str, required: bool = True):
    lo, hi = _num(rec, lo_key, required), _num(rec, hi_key, required)
    if (lo is None) != (hi is None):
        raise RecordError(f"give both '{lo_key}' and '{hi_key}', or neither")
    if lo is not None and lo > hi:
        raise RecordError(f"'{lo_key}' is larger than '{hi_key}'")
    if lo is not None and lo == hi:
        raise RecordError(f"'{lo_key}' and '{hi_key}' are equal, so there is no range")
    return lo, hi


# Rounding box. A printed input v with half-unit h is the interval [v - h, v + h]; a plain
# JSON number is the point [v, v]. Each flag is decided over the box by interval reasoning:
# a flag is raised only when every point of the box is on the flag side ("all"). When the box
# straddles the boundary the record gets "<reason>_rounding_sensitive" instead, a fact, not a
# flag. The method per flag is stated at its check. Interval bounds treat the inputs as
# independent, which can only widen a range, so a widened range never creates a false flag.
def _iv(rec: dict, key: str):
    v = _num(rec, key, False)
    if v is None:
        return None
    h = _half(rec, key)
    return (v - h, v + h)


def _imul(a, b):
    ps = [x * y for x in a for y in b]
    return (min(ps), max(ps))


def _iadd(a, b):
    return (a[0] + b[0], a[1] + b[1])


def _isub(a, b):
    return (a[0] - b[1], a[1] - b[0])


def _iscale(a, k):
    return (min(a[0] * k, a[1] * k), max(a[0] * k, a[1] * k))


def _amax(a):
    return max(abs(a[0]), abs(a[1]))


def _amin(a):
    return 0.0 if a[0] <= 0 <= a[1] else min(abs(a[0]), abs(a[1]))


def _ratio(n, d):
    return n / d if d > 0 else math.inf


def _width0(*ivs) -> bool:
    return all(iv[0] == iv[1] for iv in ivs)


def _cls(all_cond: bool, none_cond: bool) -> str:
    return "all" if all_cond else ("none" if none_cond else "some")


def _tp_outside(b1, b2, xmin, xmax) -> str:
    """Method: exact range. -b1/(2 b2) is monotone in b1 and in b2 while the b2 box excludes
    zero, so the extremes sit at the four (b1, b2) corners. A b2 box holding zero is "some"."""
    if b2[0] <= 0 <= b2[1]:
        return "some"
    tps = [-x / (2 * y) for x in b1 for y in b2]
    lo, hi = min(tps), max(tps)
    return _cls(lo > xmax[1] or hi < xmin[0], lo >= xmin[1] and hi <= xmax[0])


def _se_range(sa, sb, c, cov):
    """Range of sqrt(se_a^2 + c^2 se_b^2 + 2 c cov) over the box, with cov clamped to
    +-se_a se_b. Upper end: the variance is increasing in se_a and se_b and convex in c, so the
    maximum sits at corners. Lower end: exact when se_a, se_b, c, cov are points; otherwise a
    lower bound that subtracts the largest possible covariance term."""
    k_lo, k_hi = sa[0] * sb[0], sa[1] * sb[1]
    e_lo = max(-k_hi, min(cov[0], k_lo))
    e_hi = min(k_hi, max(cov[1], -k_lo))
    var_max = max(sa[1] ** 2 + cc ** 2 * sb[1] ** 2 + 2 * cc * e for cc in c for e in (e_lo, e_hi))
    if _width0(sa, sb, c) and e_lo == e_hi:
        var_min = var_max
    else:
        var_min = sa[0] ** 2 + _amin(c) ** 2 * sb[0] ** 2 - 2 * _amax(c) * max(abs(e_lo), abs(e_hi))
    return math.sqrt(max(var_min, 0.0)), math.sqrt(max(var_max, 0.0))


def _slope_insignificant(s, sa, sb, c, cov, crit) -> str:
    """Method: interval bounds on the z statistic. With the covariance, z = |s| / se with se
    from _se_range. Without it, the largest z any covariance allows is |s| / |se_a - |c| se_b|,
    and the difference d = se_a - |c| se_b is multilinear, so its extremes sit at corners. If d
    can be zero the bound is unbounded and the result is never "all"."""
    if cov is not None:
        se_min, se_max = _se_range(sa, sb, c, cov)
        return _cls(_ratio(_amax(s), se_min) < crit, _ratio(_amin(s), se_max) >= crit)
    absc = (_amin(c), _amax(c))
    d = _isub(sa, _imul(absc, sb))
    return _cls(_ratio(_amax(s), _amin(d)) < crit, _ratio(_amin(s), _amax(d)) >= crit)


def _points(rec: dict, keys):
    names, axes = [], []
    for k in keys:
        v = _num(rec, k, False)
        if v is None:
            continue
        h = _half(rec, k)
        names.append(k)
        axes.append([v - h, v, v + h] if h > 0 else [v])
    return [dict(zip(names, combo)) for combo in itertools.product(*axes)]


def _outcome(pts, pred) -> str:
    res = []
    for p in pts:
        try:
            res.append(bool(pred(p)))
        except (ArithmeticError, ValueError):
            res.append(None)
    if all(r is True for r in res):
        return "all"
    return "some" if any(r is True for r in res) else "none"


def _mark(reason: str, outcome: str, reasons: list, facts: list, text: str = "") -> None:
    """Add the reason when the whole box is on the flag side; the sensitive fact otherwise."""
    if outcome == "all":
        if reason not in reasons:
            reasons.append(reason)
    elif outcome == "some":
        name = reason + "_rounding_sensitive"
        if name not in reasons:
            reasons.append(name)
            facts.append(f"Whether this holds ({reason}) depends on the rounding of the reported values.")


def _cov_ok(cov, se_a, se_b, name):
    if cov is not None and abs(cov) > se_a * se_b * (1 + 1e-9):
        raise RecordError(f"'{name}' is larger in size than the two standard errors allow")


def _combo_test(s, se_a, se_b, c, cov, crit):
    """Test s = a + c*b, where a and b have standard errors se_a and se_b.

    Var(s) = se_a^2 + c^2 se_b^2 + 2 c cov. Without the covariance, |cov| <= se_a se_b bounds
    the standard error between |se_a - |c| se_b| and se_a + |c| se_b.
    """
    if se_a <= 0 or se_b <= 0:
        raise ValueError("standard error is not positive")
    if cov is not None:
        var = se_a ** 2 + c ** 2 * se_b ** 2 + 2 * c * cov
        se = math.sqrt(max(var, 0.0))
        z = abs(s) / se if se > 0 else math.inf
        return {"se": se, "z": z, "verdict": "significant" if z >= crit else "insignificant"}
    se_lo = abs(se_a - abs(c) * se_b)
    se_hi = se_a + abs(c) * se_b
    z_lo = abs(s) / se_hi
    z_hi = abs(s) / se_lo if se_lo > 0 else math.inf
    if z_hi < crit:
        verdict = "insignificant_any_cov"
    elif z_lo < crit:
        verdict = "depends_on_cov"
    else:
        verdict = "significant"
    return {"se_lo": se_lo, "se_hi": se_hi, "z_lo": z_lo, "z_hi": z_hi, "verdict": verdict}


def _fieller(b1, b2, se1, se2, cov, t):
    """Fieller set for theta = -b1/(2 b2): {theta : 4A theta^2 + 4B theta + C <= 0}."""
    a = b2 ** 2 - t ** 2 * se2 ** 2
    b = b1 * b2 - t ** 2 * cov
    c = b1 ** 2 - t ** 2 * se1 ** 2
    if a <= 0:
        return None
    root = math.sqrt(max(b ** 2 - a * c, 0.0))
    return [(-b - root) / (2 * a), (-b + root) / (2 * a)]


def _quadratic(rec, crit, values, reasons, facts):
    b1, b2 = _num(rec, "b1"), _num(rec, "b2")
    x_min, x_max = _range(rec, "x_min", "x_max", required=False)
    x_mean, x_sd = _num(rec, "x_mean", False), _positive(rec, "x_sd", False)
    if x_min is None and (x_mean is None or x_sd is None):
        raise RecordError("needs x_min and x_max, or x_mean and x_sd")
    if b2 == 0:
        raise RecordError("b2 is zero, so there is no turning point")
    # A "reversal" claim (a U or an inverted U, the default) needs the turning point inside the
    # data and both end slopes. A "monotone" claim (diminishing or increasing returns, no
    # optimum) needs only the slope at the far end, the maximum; its turning point is a fact.
    claim = rec.get("claim", "reversal")
    if claim not in ("reversal", "monotone"):
        raise RecordError("field 'claim' must be \"reversal\" or \"monotone\"")
    monotone = claim == "monotone"
    se1, se2 = _positive(rec, "se1", False), _positive(rec, "se2", False)
    cov = _num(rec, "cov12", False)
    if cov is not None and (se1 is None or se2 is None):
        raise RecordError("cov12 needs se1 and se2")
    if se1 is not None and se2 is not None:
        _cov_ok(cov, se1, se2, "cov12")
    tp = -b1 / (2 * b2)
    values["tp"] = tp
    shape = "inverted U" if b2 < 0 else "U"
    facts.append(f"The implied turning point is {_fmt(tp)} (a {shape} if it lies inside the data).")
    if x_mean is not None and x_sd is not None:
        values["tp_sd_from_mean"] = (tp - x_mean) / x_sd
        facts.append(f"The turning point is {_fmt(values['tp_sd_from_mean'])} standard deviations from the mean.")
    inside = None
    if x_min is not None:
        inside = x_min <= tp <= x_max
        values["inside"] = inside
        values["position"] = (tp - x_min) / (x_max - x_min)
        s_lo, s_hi = b1 + 2 * b2 * x_min, b1 + 2 * b2 * x_max
        values["slope_at_min"], values["slope_at_max"] = s_lo, s_hi
        facts.append(f"The slope is {_fmt(s_lo)} at the minimum ({_fmt(x_min)}) and {_fmt(s_hi)} at the maximum ({_fmt(x_max)}).")
        # Method: exact range of the turning point (see _tp_outside).
        if monotone:
            out = "none"
            values["claim"] = claim
            facts.append("The claim is monotone, so only the slope at the maximum (the far end) is tested; a turning point outside the range is consistent with it.")
        else:
            out = _tp_outside(_iv(rec, "b1"), _iv(rec, "b2"), _iv(rec, "x_min"), _iv(rec, "x_max"))
        if out == "all":
            reasons.append("tp_outside_range")
            facts.append(f"The turning point lies outside the observed range {_fmt(x_min)} to {_fmt(x_max)}, so the fitted curve does not change direction inside the data.")
        else:
            _mark("tp_outside_range", out, reasons, facts)
            ends = (("min", "x_min", x_min, s_lo), ("max", "x_max", x_max, s_hi))
            if monotone:
                ends = ends[1:]
            if se1 is not None and se2 is not None:
                for end, xkey, x, sl in ends:
                    test = _combo_test(sl, se1, se2, 2 * x, cov, crit)
                    values[f"slope_test_at_{end}"] = test
                    c_iv = _iscale(_iv(rec, xkey), 2)
                    s_iv = _iadd(_iv(rec, "b1"), _imul(_iv(rec, "b2"), c_iv))
                    o = _slope_insignificant(s_iv, _iv(rec, "se1"), _iv(rec, "se2"), c_iv, _iv(rec, "cov12"), crit)
                    reason = "end_slope_insignificant" if cov is not None else "end_slope_insignificant_any_cov"
                    if o == "all" and reason not in reasons:
                        if cov is not None:
                            facts.append(f"The slope at the {end} has z {_fmt(test['z'])}, below {_fmt(crit)}.")
                        else:
                            facts.append(f"The slope at the {end} is not distinguishable from zero under any covariance the standard errors allow (z at most {_fmt(test['z_hi'])}).")
                    _mark(reason, o, reasons, facts)
                    if test["verdict"] == "depends_on_cov" and "end_slope_depends_on_cov" not in reasons:
                        reasons.append("end_slope_depends_on_cov")
                        facts.append(f"Whether the slope at the {end} is distinguishable from zero depends on the unreported covariance (z from {_fmt(test['z_lo'])} to {_fmt(test['z_hi'])}).")
            p05, p95 = _num(rec, "x_p05", False), _num(rec, "x_p95", False)
            if inside and p05 is not None and p95 is not None and (tp < p05 or tp > p95):
                reasons.append("tp_near_edge")
                facts.append(f"The turning point lies outside the 5th to 95th percentiles ({_fmt(p05)} to {_fmt(p95)}).")
    if cov is not None:
        var = se1 ** 2 / (4 * b2 ** 2) + b1 ** 2 * se2 ** 2 / (4 * b2 ** 4) - b1 * cov / (2 * b2 ** 3)
        values["tp_se_delta"] = math.sqrt(max(var, 0.0))
        interval = _fieller(b1, b2, se1, se2, cov, crit)
        values["tp_fieller"] = interval
        if interval is None:
            reasons.append("fieller_unbounded")
            facts.append("The Fieller interval for the turning point is unbounded because the squared term is not distinguishable from zero.")
        else:
            facts.append(f"The Fieller interval for the turning point is {_fmt(interval[0])} to {_fmt(interval[1])}.")
            if x_min is not None and not monotone:
                # Method: exact when b1, b2, se1, se2, cov12, x_min, x_max are points. The
                # Fieller endpoints are not monotone in the inputs, so a printed input can only
                # make this "some" (never a flag) when a point of the corner grid leaves the range.
                keys = ["b1", "b2", "se1", "se2", "cov12", "x_min", "x_max"]

                def leaves(p):
                    if not p["x_min"] <= -p["b1"] / (2 * p["b2"]) <= p["x_max"]:
                        return False
                    iv = _fieller(p["b1"], p["b2"], p["se1"], p["se2"], p["cov12"], crit)
                    return iv is not None and (iv[0] < p["x_min"] or iv[1] > p["x_max"])

                o = _outcome(_points(rec, keys), leaves)
                if o == "all" and any(_half(rec, k) > 0 for k in keys):
                    o = "some"
                _mark("tp_interval_leaves_range", o, reasons, facts)
    elif se1 is not None:
        facts.append("No interval for the turning point: the covariance of the two coefficients is not reported.")


def _item(v, key: str):
    """A list item that is a number or a printed string, as (value, half-unit)."""
    if isinstance(v, str):
        return _parse_printed(v, key)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise RecordError(f"'{key}' must hold numbers")
    return float(v), 0.0


def _moderated_quadratic(rec, crit, values, reasons, facts):
    b1, b2, b3, b4 = (_num(rec, k) for k in ("b1", "b2", "b3", "b4"))
    x_min, x_max = _range(rec, "x_min", "x_max")
    m_min, m_max = _range(rec, "m_min", "m_max")
    extra = rec.get("m_values") or []
    if not isinstance(extra, list):
        raise RecordError("'m_values' must be a list")
    ms = []
    for m, h in [(m_min, _half(rec, "m_min")), (m_max, _half(rec, "m_max"))] + [_item(v, "m_values") for v in extra]:
        if float(m) not in [x[0] for x in ms]:
            ms.append((float(m), h))
    at = []
    outcomes = []
    b1_iv, b2_iv, b3_iv, b4_iv = (_iv(rec, k) for k in ("b1", "b2", "b3", "b4"))
    xmin_iv, xmax_iv = _iv(rec, "x_min"), _iv(rec, "x_max")
    for m, h in ms:
        c = b2 + b4 * m
        tp = -(b1 + b3 * m) / (2 * c) if c != 0 else None
        at.append({"m": m, "curvature": c, "tp": tp})
        if tp is None:
            facts.append(f"At m = {_fmt(m)} the curvature is zero, so there is no turning point.")
            continue
        facts.append(f"At m = {_fmt(m)} the curvature is {_fmt(c)} and the turning point is {_fmt(tp)}.")
        # Method: exact-range style bound. The turning point is -N / (2 c) with N = b1 + b3 m
        # and c = b2 + b4 m; while the c box excludes zero, the extremes of the ratio over the
        # independent N and c boxes sit at their corners (a range that can only be too wide).
        m_iv = (m - h, m + h)
        c_iv = _iadd(b2_iv, _imul(b4_iv, m_iv))
        n_iv = _iadd(b1_iv, _imul(b3_iv, m_iv))
        outcomes.append(_tp_outside(n_iv, c_iv, xmin_iv, xmax_iv))
    values["at"] = at
    if "all" in outcomes:
        reasons.append("tp_outside_range_at_m")
    elif "some" in outcomes:
        _mark("tp_outside_range_at_m", "some", reasons, facts)
    # Method: the curvature at each end is an interval (b2 + b4 m); the sign flips for sure only
    # when the two end intervals lie strictly on opposite sides of zero.
    cl = _iadd(b2_iv, _imul(b4_iv, _iv(rec, "m_min")))
    ch = _iadd(b2_iv, _imul(b4_iv, _iv(rec, "m_max")))
    flip = _cls((cl[1] < 0 < ch[0]) or (cl[0] > 0 > ch[1]),
                (cl[0] >= 0 and ch[0] >= 0) or (cl[1] <= 0 and ch[1] <= 0))
    if flip != "none" and b4 != 0:
        values["m_star"] = -b2 / b4
    if flip == "all":
        facts.append(f"The curvature changes sign at m = {_fmt(values['m_star'])}, inside the moderator's range {_fmt(m_min)} to {_fmt(m_max)}.")
    _mark("curvature_flips_in_moderator_range", flip, reasons, facts)


def _linear_interaction(rec, crit, values, reasons, facts):
    m_min, m_max = _range(rec, "m_min", "m_max")
    read = rec.get("lower_order_read", False)
    if not isinstance(read, bool):
        raise RecordError("'lower_order_read' must be true or false")
    # Method: exact interval. Zero is outside the range for sure when the min box is above zero
    # or the max box is below it, and inside for sure when the min box is at most zero and the
    # max box at least zero.
    lo_iv, hi_iv = _iv(rec, "m_min"), _iv(rec, "m_max")
    out = _cls(lo_iv[0] > 0 or hi_iv[1] < 0, lo_iv[1] <= 0 and hi_iv[0] >= 0)
    if out == "all":
        facts.append(f"Zero lies outside the moderator's range {_fmt(m_min)} to {_fmt(m_max)}, so the lower-order coefficient is the effect at a value no observation has.")
    if out != "none":
        _mark("zero_outside_range", out, reasons, facts)
        if out == "all" and read:
            reasons.append("lower_order_read_outside_range")
    b1, b3 = _num(rec, "b1", False), _num(rec, "b3", False)
    if b1 is None or b3 is None:
        return
    s_lo, s_hi = b1 + b3 * m_min, b1 + b3 * m_max
    values["slope_at_min"], values["slope_at_max"] = s_lo, s_hi
    facts.append(f"The conditional slope is {_fmt(s_lo)} at the moderator's minimum and {_fmt(s_hi)} at its maximum.")
    if s_lo * s_hi < 0:
        values["m_zero"] = -b1 / b3
        reasons.append("slope_changes_sign_in_range")
        facts.append(f"The conditional slope changes sign at m = {_fmt(values['m_zero'])}, inside the moderator's range.")
    se1, se3 = _positive(rec, "se1", False), _positive(rec, "se3", False)
    cov = _num(rec, "cov13", False)
    if se1 is None or se3 is None:
        return
    _cov_ok(cov, se1, se3, "cov13")
    for end, mkey, m, sl in (("min", "m_min", m_min, s_lo), ("max", "m_max", m_max, s_hi)):
        test = _combo_test(sl, se1, se3, m, cov, crit)
        values[f"slope_test_at_{end}"] = test
        c_iv = _iv(rec, mkey)
        s_iv = _iadd(_iv(rec, "b1"), _imul(_iv(rec, "b3"), c_iv))
        o = _slope_insignificant(s_iv, _iv(rec, "se1"), _iv(rec, "se3"), c_iv, _iv(rec, "cov13"), crit)
        if o == "all":
            facts.append(f"The conditional slope at the moderator's {end} is not distinguishable from zero.")
        _mark(f"slope_insignificant_at_{end}", o, reasons, facts)
        if test["verdict"] == "depends_on_cov" and "slope_depends_on_cov" not in reasons:
            reasons.append("slope_depends_on_cov")
            facts.append("Whether a conditional slope at an end is distinguishable from zero depends on the unreported covariance.")


def _plotted_points(rec, crit, values, reasons, facts):
    m_min, m_max = _range(rec, "m_min", "m_max")
    points = rec.get("points") or []
    if not isinstance(points, list):
        raise RecordError("'points' must be a list of numbers")
    items = [_item(p, "points") for p in points]
    if items:
        boxes = [(v - h, v + h) for v, h in items]
    else:
        mean, sd = _num(rec, "m_mean", False), _positive(rec, "m_sd", False)
        if mean is None or sd is None:
            raise RecordError("needs 'points', or 'm_mean' and 'm_sd'")
        items = [(mean - sd, 0.0), (mean + sd, 0.0)]
        mean_iv, sd_iv = _iv(rec, "m_mean"), _iv(rec, "m_sd")
        boxes = [_isub(mean_iv, sd_iv), _iadd(mean_iv, sd_iv)]
    pts = [v for v, _ in items]
    outside = [float(p) for p in pts if p < m_min or p > m_max]
    values["points"] = [float(p) for p in pts]
    values["outside"] = outside
    # Method: exact intervals. A point is outside for sure when its box lies beyond the
    # (lowest) minimum or (highest) maximum; inside for sure when it clears both boxes.
    lo_iv, hi_iv = _iv(rec, "m_min"), _iv(rec, "m_max")
    o = _cls(any(b[1] < lo_iv[0] or b[0] > hi_iv[1] for b in boxes),
             all(b[0] >= lo_iv[1] and b[1] <= hi_iv[0] for b in boxes))
    if outside:
        facts.append(f"Plotted or tested moderator values {', '.join(_fmt(p) for p in outside)} lie outside the observed range {_fmt(m_min)} to {_fmt(m_max)}.")
    _mark("point_outside_range", o, reasons, facts)


def _difference(rec, crit, values, reasons, facts):
    b_a, b_b = _num(rec, "b_a"), _num(rec, "b_b")
    se_a, se_b = _positive(rec, "se_a"), _positive(rec, "se_b")
    independent = rec.get("independent")
    if not isinstance(independent, bool):
        raise RecordError("'independent' must be true or false")
    if not independent:
        return "not_computable", "the two estimates share units, and their covariance is not reported"
    z = (b_a - b_b) / math.sqrt(se_a ** 2 + se_b ** 2)
    values["z"], values["p"] = z, math.erfc(abs(z) / math.sqrt(2))
    facts.append(f"The difference {_fmt(b_a - b_b)} has z {_fmt(z)} and two-sided p {_fmt(values['p'])}.")
    # Method: exact bounds. |z| is largest at the largest difference and the smallest standard
    # errors, and smallest at the smallest difference and the largest standard errors.
    d = _isub(_iv(rec, "b_a"), _iv(rec, "b_b"))
    sa, sb = _iv(rec, "se_a"), _iv(rec, "se_b")
    se_lo = math.sqrt(max(sa[0], 0.0) ** 2 + max(sb[0], 0.0) ** 2)
    se_hi = math.sqrt(sa[1] ** 2 + sb[1] ** 2)
    o = _cls(_ratio(_amax(d), se_lo) < crit, _ratio(_amin(d), se_hi) >= crit)
    _mark("difference_not_distinguishable", o, reasons, facts)


def _or_rel(odds, p0):
    return odds * p0 / (1 - p0 + odds * p0) / p0 - 1


def _rel_consistent(claimed, r_lo, r_hi):
    """True when some relative change in [r_lo, r_hi] is within 20 percent of the claim."""
    if claimed > 0:
        a, b = claimed / 1.2, claimed / 0.8
    elif claimed < 0:
        a, b = claimed / 0.8, claimed / 1.2
    else:
        a = b = 0.0
    return max(r_lo, a) <= min(r_hi, b)


def _odds_ratio(rec, crit, values, reasons, facts):
    odds = _positive(rec, "odds_ratio")
    p0 = _num(rec, "base_rate")
    if not 0 < p0 < 1:
        raise RecordError("'base_rate' must lie strictly between 0 and 1")
    p1 = odds * p0 / (1 - p0 + odds * p0)
    rel = p1 / p0 - 1
    values.update({"p1": p1, "relative_change": rel, "absolute_change": p1 - p0})
    facts.append(f"At a base rate of {_fmt(p0)}, an odds ratio of {_fmt(odds)} moves the probability to {_fmt(p1)}: a relative change of {_fmt(rel)} and an absolute change of {_fmt(p1 - p0)}.")
    claimed = _num(rec, "claimed_relative_change", False)
    if claimed is None:
        return
    hp = _half(rec, "base_rate")
    # Method: exact interval on the base rate. Below 0.10 for sure is "rare"; a box that
    # straddles 0.10 can never flag, only mark the claim rounding-sensitive.
    if p0 + hp < 0.10 or (hp == 0 and p0 < 0.10):
        facts.append("The outcome is rare, so reading the odds ratio as a relative change in probability is approximately right.")
        return
    maybe_rare = p0 - hp < 0.10
    if abs(claimed - rel) <= 0.20 * abs(rel):
        return
    # The relative change is monotone in each input, so the corners of the rounding box give
    # its exact range, and every value between them is reachable.
    ho = _half(rec, "odds_ratio")
    o_box = (max(odds - ho, 1e-12), odds + ho)
    p_box = (max(p0 - hp, 1e-12), min(p0 + hp, 1 - 1e-12))
    corners = [_or_rel(o, p) for o in o_box for p in p_box]
    if _rel_consistent(claimed, min(corners), max(corners)):
        if ho > 0 or hp > 0:
            _mark("or_claim_mismatch", "some", reasons, facts)
    elif maybe_rare:
        _mark("or_claim_mismatch", "some", reasons, facts)
    else:
        reasons.append("or_claim_mismatch")
        facts.append(f"The paper's reading, a relative change of {_fmt(claimed)}, does not match {_fmt(rel)}.")


HANDLERS = {"quadratic": _quadratic, "moderated_quadratic": _moderated_quadratic,
            "linear_interaction": _linear_interaction, "plotted_points": _plotted_points,
            "difference": _difference, "odds_ratio": _odds_ratio}


def _clean(v):
    """Replace non-finite numbers with None so the output is strict JSON."""
    if isinstance(v, float) and not math.isfinite(v):
        return None
    if isinstance(v, dict):
        return {k: _clean(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_clean(x) for x in v]
    return v


def run_record(rec, seen: set) -> dict:
    out = {k: rec.get(k) if isinstance(rec, dict) else None for k in ("id", "kind", "check", "term", "source")}
    out["cells"] = rec.get("cells", []) if isinstance(rec, dict) else []
    out.update({"status": "ok", "values": {}, "reasons": [], "flag": False, "facts": [], "message": None})
    try:
        if not isinstance(rec, dict):
            raise RecordError("a record must be an object")
        rid = rec.get("id")
        if not isinstance(rid, str) or not rid:
            raise RecordError("missing field 'id'")
        if rid in seen:
            raise RecordError(f"duplicate id '{rid}'")
        seen.add(rid)
        if rec.get("kind") not in KINDS:
            raise RecordError(f"unknown kind {rec.get('kind')!r}")
        if not isinstance(out["cells"], list):
            raise RecordError("'cells' must be a list")
        crit = _positive(rec, "crit", False) or 1.96
        result = HANDLERS[rec["kind"]](rec, crit, out["values"], out["reasons"], out["facts"])
        if result:
            out["status"], out["message"] = result
    except (RecordError, ArithmeticError, ValueError) as e:
        msg = str(e) if isinstance(e, RecordError) else f"arithmetic failed: {e}"
        out["status"], out["message"] = "invalid", msg
        out["values"], out["reasons"], out["facts"] = {}, [], []
    out["flag"] = any(r in FLAG_REASONS for r in out["reasons"])
    return out


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("usage: nonlinear_arith.py <inputs.json> <out.json>", file=sys.stderr)
        return 2
    src, dst = Path(argv[0]), Path(argv[1])
    try:
        records = json.loads(src.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"cannot read {src}: {e}", file=sys.stderr)
        return 2
    if not isinstance(records, list):
        print(f"{src} must hold a JSON list of records", file=sys.stderr)
        return 2
    seen: set = set()
    results = [run_record(r, seen) for r in records]
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(_clean(results), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
