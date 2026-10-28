#!/usr/bin/env python3
"""Deterministic meta-analysis arithmetic from the numbers a paper prints. Report-only.

Usage: ma_arith.py <input.json> <out.md>

Reads a JSON list of check records and writes <out.md> and, beside it, <out stem>.json
with one result per record. Every printed input is a string, so its rounding can be read;
each formula is evaluated at every corner of the rounding box. A record the script cannot use
(a missing or malformed field, a value outside a formula's domain, a result that is not a finite
number) gets status input_error and never stops the batch. Exit 0 when the report is written,
whatever it found; exit 2 when the input is missing, not JSON (NaN and Infinity are not JSON),
or not a list.
"""
from __future__ import annotations

import itertools
import json
import math
import re
import sys
from pathlib import Path
from statistics import NormalDist, harmonic_mean, median

KINDS = ("i2", "prediction_interval", "credibility_interval", "dependence_bound", "convert",
         "attenuation", "flow", "cell_n", "study_table")
UNITS = ("articles", "reports", "studies", "samples", "effect sizes")
EPS = 1e-12


class RecordError(Exception):
    """A field is missing or malformed; the record gets status input_error."""


# ---------------------------------------------------------------------------
# Numbers as printed
# ---------------------------------------------------------------------------

_THOUSANDS = re.compile(r"^[-+]?[1-9]\d{0,2}(,\d{3})+(\.\d*)?$")


def _clean(s: str) -> str:
    """Strip spaces and the minus sign; a comma is read only as a thousands separator."""
    s = s.strip().replace("\u2212", "-")
    if "," in s:
        if not _THOUSANDS.match(s):
            raise RecordError(f"{s!r} has a comma that is not a thousands separator; write the decimal point as '.'")
        s = s.replace(",", "")
    return s


def _num(rec: dict, key: str, required: bool = True):
    """(value, half_width) for a printed number; half-width is half a unit in the last printed digit."""
    if key not in rec or rec[key] is None:
        if required:
            raise RecordError(f"missing field '{key}'")
        return None
    raw = rec[key]
    if isinstance(raw, bool):
        raise RecordError(f"field '{key}' must be a number as printed, not {raw!r}")
    if isinstance(raw, (int, float)):
        try:
            v = float(raw)
        except OverflowError:
            raise RecordError(f"field '{key}' is too large: {raw!r}")
        if not math.isfinite(v):
            raise RecordError(f"field '{key}' is not a finite number: {raw!r}")
        return v, 0.0
    if not isinstance(raw, str):
        raise RecordError(f"field '{key}' must be a number as printed, not {raw!r}")
    s = _clean(raw)
    try:
        v = float(s)
    except ValueError:
        raise RecordError(f"field '{key}' is not a number: {raw!r}")
    if not math.isfinite(v):
        raise RecordError(f"field '{key}' is not a finite number: {raw!r}")
    mant, _, exp = s.lower().partition("e")
    places = len(mant.split(".", 1)[1]) if "." in mant else 0
    try:
        half = 0.5 * 10.0 ** (int(exp or "0") - places)
    except OverflowError:
        raise RecordError(f"field '{key}' has an exponent that is too large: {raw!r}")
    return v, half


def _spread(rec: dict, key: str, required: bool = True):
    """A printed standard deviation or variance: never negative, and its rounding box is clipped
    at zero, so a printed 0.00 covers 0 to 0.005 rather than losing its lower corners."""
    x = _num(rec, key, required)
    if x is None:
        return None
    v, h = x
    if v < 0:
        raise RecordError(f"field '{key}' must not be negative")
    return v, h, 0.0


def _pair(rec: dict, key: str, required: bool = True):
    if key not in rec or rec[key] is None:
        if required:
            raise RecordError(f"missing field '{key}'")
        return None
    raw = rec[key]
    if not isinstance(raw, list) or len(raw) != 2:
        raise RecordError(f"field '{key}' must be a list of two numbers")
    return [_num({"v": x}, "v") for x in raw]


def _int(rec: dict, key: str, required: bool = True):
    if key not in rec or rec[key] is None:
        if required:
            raise RecordError(f"missing field '{key}'")
        return None
    raw = rec[key]
    if isinstance(raw, bool):
        raise RecordError(f"field '{key}' must be a whole number")
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str):
        s = _clean(raw)
        if s.lstrip("-").isdigit():
            return int(s)
    raise RecordError(f"field '{key}' must be a whole number, not {raw!r}")


def _level(rec: dict, key: str, default: str) -> float:
    v, _ = _num({"v": rec.get(key, default)}, "v")
    if not 0 < v < 1:
        raise RecordError(f"field '{key}' must lie between 0 and 1")
    return v


def _box(inputs):
    """Every corner of the rounding box, central values first. An input given as (value, half-width,
    floor) has its lower corner clipped at the floor."""
    central = tuple(x[0] for x in inputs)
    sides = []
    for x in inputs:
        v, h = x[0], x[1]
        lower = max(x[2], v - h) if len(x) > 2 else v - h
        sides.append((lower, v + h) if h else (v,))
    return central, list(itertools.product(*sides))


def _range(f, inputs):
    """f at the central values, the min and max of each output over the corners, the outputs,
    and how many corners lie outside the formula's domain. Skipped corners are counted and
    reported, never hidden."""
    central, corners = _box(inputs)
    try:
        mid = f(*central)
    except (ValueError, ZeroDivisionError, OverflowError) as e:
        raise RecordError(f"the printed values lie outside the formula's domain ({e})")
    outs = []
    skipped = 0
    for c in corners:
        try:
            outs.append(f(*c))
        except (ValueError, ZeroDivisionError, OverflowError):
            skipped += 1
    if not outs:
        raise RecordError("no corner of the rounding box can be computed")
    if isinstance(mid, tuple):
        lo = tuple(min(o[i] for o in outs) for i in range(len(mid)))
        hi = tuple(max(o[i] for o in outs) for i in range(len(mid)))
    else:
        lo, hi = min(outs), max(outs)
    return mid, lo, hi, outs, skipped


def _skip_note(skipped: int, outs) -> str:
    if not skipped:
        return ""
    return (f" {skipped} of {skipped + len(outs)} corners of the rounding box lie outside the formula's domain "
            f"and were left out.")


def _matches(printed, lo: float, hi: float) -> bool:
    v, h = printed
    return v + h >= lo - EPS and v - h <= hi + EPS


def _zero(outs, skipped: int = 0, lo_i: int = 0, hi_i: int = 1) -> str:
    """'every corner' only when no corner was skipped; S1 and S2 read only that value."""
    hits = sum(1 for o in outs if o[lo_i] <= 0 <= o[hi_i])
    if hits == len(outs):
        return "every computable corner" if skipped else "every corner"
    return "some corners" if hits else "none"


def _r(x: float, n: int = 6) -> float:
    return round(x, n)


# ---------------------------------------------------------------------------
# Quantiles (standard library only)
# ---------------------------------------------------------------------------

def _betacf(a: float, b: float, x: float) -> float:
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 400):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    return h


def _betai(a: float, b: float, x: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def t_cdf(t: float, df: float) -> float:
    tail = 0.5 * _betai(df / 2.0, 0.5, df / (df + t * t))
    return 1.0 - tail if t >= 0 else tail


def t_quantile(p: float, df: float) -> float:
    """The t quantile for p above 0.5, by bisection on the t CDF."""
    if not 0.5 < p < 1.0 or df <= 0:
        raise ValueError("t_quantile needs 0.5 < p < 1 and df > 0")
    lo, hi = 0.0, 1.0
    while t_cdf(hi, df) < p:
        lo, hi = hi, hi * 2.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if t_cdf(mid, df) < p:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-12:
            break
    return (lo + hi) / 2.0


def z_quantile(p: float) -> float:
    return NormalDist().inv_cdf(p)


# ---------------------------------------------------------------------------
# Kinds
# ---------------------------------------------------------------------------

def _i2(rec: dict) -> dict:
    q = _num(rec, "q")
    df = _int(rec, "df")
    q_based = rec.get("q_based")
    if not isinstance(q_based, bool):
        raise RecordError("field 'q_based' must be true or false")
    if df <= 0:
        return {"status": "not_computable", "values": {}, "message": "df must be at least 1"}

    def f(qv):
        if qv <= 0:
            return 0.0
        return max(0.0, (qv - df) / qv) * 100.0

    mid, lo, hi, _, skipped = _range(f, [q])
    values = {"i2": _r(mid, 4), "i2_min": _r(lo, 4), "i2_max": _r(hi, 4), "corners_skipped": skipped}
    notes = [f"I2 from Q and df is {mid:.2f} (range {lo:.2f} to {hi:.2f} over rounding)."]
    status = "info"
    printed = None
    if rec.get("printed_i2") is not None:
        raw = rec["printed_i2"]
        form = rec.get("printed_i2_form", "percent")
        if form not in ("percent", "proportion"):
            raise RecordError("field 'printed_i2_form' must be 'percent' or 'proportion'")
        pct_sign = isinstance(raw, str) and raw.strip().endswith("%")
        if pct_sign:
            raw = raw.strip()[:-1]
        printed = _num({"v": raw}, "v")
        if form == "proportion" and (pct_sign or printed[0] > 1.0):
            raise RecordError(
                f"printed_i2 {rec['printed_i2']!r} reads as a percent, not a proportion; "
                "check 'printed_i2_form'")
        if form == "proportion":
            printed = (printed[0] * 100.0, printed[1] * 100.0)
    if printed is not None:
        if not q_based:
            notes.append("The paper's I2 may not be the Q-based one, so the printed value is not compared.")
        elif _matches(printed, lo, hi):
            status = "ok"
            notes.append(f"Printed I2 {rec['printed_i2']} matches.")
        else:
            status = "mismatch"
            notes.append(f"Printed I2 {rec['printed_i2']} does not match.")
    k = _int(rec, "k", required=False)
    if k is not None and df != k - 1:
        notes.append(f"df {df} is not k - 1 ({k - 1}); models with dependence or robust variance use other df.")
    return {"status": status, "values": values, "message": " ".join(notes)}


def _se_inputs(rec: dict, k=None):
    """The inputs that give the standard error: ('se', se) or ('ci', lower, upper, q)."""
    se = _num(rec, "se", required=False)
    ci = _pair(rec, "ci", required=False)
    if (se is None) == (ci is None):
        raise RecordError("give exactly one of 'se' or 'ci'")
    if se is not None:
        return "se", [se], None
    level = _level(rec, "ci_level", "0.95")
    method = rec.get("ci_method", "z")
    if method == "z":
        q = z_quantile((1.0 + level) / 2.0)
    elif method == "t_k1":
        if k is None or k < 2:
            raise RecordError("ci_method t_k1 needs k of at least 2")
        q = t_quantile((1.0 + level) / 2.0, k - 1)
    else:
        raise RecordError("field 'ci_method' must be 'z' or 't_k1'")
    return "ci", ci, q


def _spread_sum(rec: dict, key: str):
    """A printed variance, or a list of printed variance components (three-level models) whose
    rounding boxes add; the sum's lower corner is clipped at zero."""
    raw = rec.get(key)
    if not isinstance(raw, list):
        return _spread(rec, key, required=False)
    if not raw:
        raise RecordError(f"field '{key}' must not be an empty list")
    parts = [_spread({"v": x}, "v") for x in raw]
    return sum(p[0] for p in parts), sum(p[1] for p in parts), 0.0


def _scale(rec: dict) -> str:
    scale = rec.get("scale")
    if scale not in ("raw", "fisher_z"):
        raise RecordError("field 'scale' must be 'raw' or 'fisher_z'")
    return scale


def _prediction_interval(rec: dict) -> dict:
    mean = _num(rec, "mean")
    k = _int(rec, "k")
    scale = _scale(rec)
    tau = _spread(rec, "tau", required=False)
    tau2 = _spread_sum(rec, "tau2")
    if (tau is None) == (tau2 is None):
        raise RecordError("give exactly one of 'tau' or 'tau2'")
    plevel = _level(rec, "pi_level", "0.95")
    pi_pct = f"{plevel * 100:g}%"
    if k < 3:
        return {"status": "not_computable", "values": {"k_used": k},
                "message": "k below 3 leaves no degrees of freedom for the prediction interval"}
    mode, se_in, q = _se_inputs(rec, k)
    tcrit = t_quantile((1.0 + plevel) / 2.0, k - 2)
    fwd = math.atanh if scale == "fisher_z" else (lambda x: x)
    back = math.tanh if scale == "fisher_z" else (lambda x: x)

    def make(crit):
        def f(m, *rest):
            if mode == "se":
                se, tv = rest
            else:
                lo_ci, hi_ci, tv = rest
                se = (fwd(hi_ci) - fwd(lo_ci)) / (2.0 * q)
            var = tv * tv if tau is not None else tv
            if var < 0 or se < 0:
                raise ValueError("negative variance")
            half = crit * math.sqrt(var + se * se)
            return back(fwd(m) - half), back(fwd(m) + half)
        return f

    inputs = [mean] + se_in + [tau if tau is not None else tau2]
    mid, lo, hi, outs, skipped = _range(make(tcrit), inputs)
    zero = _zero(outs, skipped)
    values = {"pi": [_r(mid[0]), _r(mid[1])], "lower_range": [_r(lo[0]), _r(hi[0])],
              "upper_range": [_r(lo[1]), _r(hi[1])], "includes_zero": zero, "t_crit": _r(tcrit),
              "k_used": k, "k_unit": rec.get("k_unit", "not stated"), "scale": scale, "corners_skipped": skipped}
    msg = (f"{pi_pct} prediction interval {mid[0]:.4f} to {mid[1]:.4f} (k = {k} {values['k_unit']}, t = {tcrit:.4f} "
           f"on k - 2 df, {scale} scale); it includes zero at {zero}." + _skip_note(skipped, outs))
    status = "info"
    printed = _pair(rec, "printed_pi", required=False)
    if printed is not None:
        # A printed interval may use t on k - 2, t on k - 1 (Hartung-Knapp), or z (software defaults).
        boxes = {"t_k2": (lo, hi)}
        for name, crit in (("t_k1", t_quantile((1.0 + plevel) / 2.0, k - 1)), ("z", z_quantile((1.0 + plevel) / 2.0))):
            cmid, clo, chi, _, _ = _range(make(crit), inputs)
            values[f"pi_{name}"] = [_r(cmid[0]), _r(cmid[1])]
            boxes[name] = (clo, chi)
        matches = [name for name, (blo, bhi) in boxes.items()
                   if _matches(printed[0], blo[0], bhi[0]) and _matches(printed[1], blo[1], bhi[1])]
        values["printed_matches"] = matches
        status = "ok" if matches else "mismatch"
        msg += (f" Printed interval {rec['printed_pi']} matches with {', '.join(matches)}." if matches else
                f" Printed interval {rec['printed_pi']} does not match with t on k - 2, t on k - 1, or z.")
    return {"status": status, "values": values, "message": msg}


def _credibility_interval(rec: dict) -> dict:
    rho = _num(rec, "rho")
    sd = _spread(rec, "sd_rho")
    level = _level(rec, "level", "0.80")
    k = _int(rec, "k", required=False)
    p = (1.0 + level) / 2.0

    def make(q):
        return lambda r, s: (r - q * s, r + q * s)

    zq = z_quantile(p)
    zmid, zlo, zhi, zouts, skipped = _range(make(zq), [rho, sd])
    values = {"z_interval": [_r(zmid[0]), _r(zmid[1])], "z_lower_range": [_r(zlo[0]), _r(zhi[0])],
              "z_upper_range": [_r(zlo[1]), _r(zhi[1])], "includes_zero_z": _zero(zouts, skipped), "level": level,
              "corners_skipped": skipped}
    msg = (f"{level:.0%} credibility interval (z) {zmid[0]:.4f} to {zmid[1]:.4f}; "
           f"it includes zero at {values['includes_zero_z']}.")
    ranges = [(zlo, zhi)]
    if k is not None and k >= 2:
        tq = t_quantile(p, k - 1)
        tmid, tlo, thi, _, _ = _range(make(tq), [rho, sd])
        values.update({"t_interval": [_r(tmid[0]), _r(tmid[1])], "t_lower_range": [_r(tlo[0]), _r(thi[0])],
                       "t_upper_range": [_r(tlo[1]), _r(thi[1])]})
        msg += f" With t on {k - 1} df: {tmid[0]:.4f} to {tmid[1]:.4f}."
        ranges.append((tlo, thi))
    status = "info"
    printed = _pair(rec, "printed", required=False)
    if printed is not None:
        ok = any(_matches(printed[0], lo[0], hi[0]) and _matches(printed[1], lo[1], hi[1]) for lo, hi in ranges)
        status = "ok" if ok else "mismatch"
        msg += f" Printed interval {rec['printed']} {'matches' if ok else 'does not match'}."
    return {"status": status, "values": values, "message": msg}


def _dependence_bound(rec: dict) -> dict:
    mean = _num(rec, "mean")
    ci = _pair(rec, "ci")
    level = _level(rec, "ci_level", "0.95")
    n_es = _int(rec, "n_es")
    n_samples = _int(rec, "n_samples")
    scale = _scale(rec)
    if n_samples < 1 or n_es < 1:
        raise RecordError("n_es and n_samples must be at least 1")
    factor = math.sqrt(n_es / n_samples) if n_es > n_samples else 1.0
    q = z_quantile((1.0 + level) / 2.0)
    fwd = math.atanh if scale == "fisher_z" else (lambda x: x)
    back = math.tanh if scale == "fisher_z" else (lambda x: x)

    def f(m, lo_ci, hi_ci):
        se = (fwd(hi_ci) - fwd(lo_ci)) / (2.0 * q)
        half = q * se * factor
        return back(fwd(m) - half), back(fwd(m) + half)

    mid, lo, hi, outs, skipped = _range(f, [mean] + ci)
    zero = _zero(outs, skipped)
    values = {"factor": _r(factor), "bound": [_r(mid[0]), _r(mid[1])], "lower_range": [_r(lo[0]), _r(hi[0])],
              "upper_range": [_r(lo[1]), _r(hi[1])], "includes_zero": zero, "corners_skipped": skipped}
    msg = (f"Interval widened by sqrt({n_es}/{n_samples}) = {factor:.4f}: {mid[0]:.4f} to {mid[1]:.4f}; "
           f"it includes zero at {zero}. This is an approximate worst case for equal-sized samples."
           + _skip_note(skipped, outs))
    if n_es <= n_samples:
        msg = "No more effect sizes than samples, so no widening. " + msg
    return {"status": "info", "values": values, "message": msg}


def _convert(rec: dict) -> dict:
    src, dst = rec.get("from"), rec.get("to")
    value = _num(rec, "value")
    notes = []
    if (src, dst) == ("d", "r"):
        n1, n2 = _int(rec, "n1", required=False), _int(rec, "n2", required=False)
        if (n1 is None) != (n2 is None):
            raise RecordError("give both n1 and n2, or neither")
        if n1 is None:
            a = 4.0
            notes.append("Group sizes not given: a = 4, which assumes equal groups.")
        else:
            if n1 < 1 or n2 < 1:
                raise RecordError("n1 and n2 must be at least 1")
            a = (n1 + n2) ** 2 / (n1 * n2)
        f = lambda d: d / math.sqrt(d * d + a)
    elif (src, dst) == ("r", "d"):
        f = lambda r: 2.0 * r / math.sqrt(1.0 - r * r)
    elif (src, dst) == ("t", "r"):
        df = _int(rec, "df")
        if df < 1:
            raise RecordError("df must be at least 1")
        f = lambda t: t / math.sqrt(t * t + df)
        if rec.get("from_model_with_controls") is True:
            notes.append("The t comes from a model with controls, so the result is a partial correlation.")
    elif (src, dst) == ("or", "d"):
        f = lambda o: math.log(o) * math.sqrt(3.0) / math.pi
    elif (src, dst) == ("log_or", "d"):
        f = lambda lo: lo * math.sqrt(3.0) / math.pi
    elif (src, dst) == ("r", "z"):
        f = math.atanh
    elif (src, dst) == ("z", "r"):
        f = math.tanh
    else:
        raise RecordError(f"no conversion from {src!r} to {dst!r}")
    mid, lo, hi, outs, skipped = _range(f, [value])
    values = {"result": _r(mid), "range": [_r(lo), _r(hi)], "corners_skipped": skipped}
    msg = f"{src} {rec['value']} converts to {dst} {mid:.6f} (range {lo:.6f} to {hi:.6f})." + _skip_note(skipped, outs)
    status = "info"
    printed = _num(rec, "printed", required=False)
    if printed is not None:
        ok = _matches(printed, lo, hi)
        status = "ok" if ok else "mismatch"
        msg += f" Printed {rec['printed']} {'matches' if ok else 'does not match'}."
    if notes:
        msg += " " + " ".join(notes)
    return {"status": status, "values": values, "message": msg}


def _attenuation(rec: dict) -> dict:
    r = _num(rec, "r_obs")
    rxx = _num(rec, "rxx")
    ryy = _num(rec, "ryy")
    if rxx[0] <= 0 or ryy[0] <= 0:
        raise RecordError("reliabilities must be above zero")
    mid, lo, hi, outs, skipped = _range(lambda a, b, c: a / math.sqrt(b * c), [r, rxx, ryy])
    values = {"rho": _r(mid), "range": [_r(lo), _r(hi)], "corners_skipped": skipped}
    msg = f"Corrected rho = {mid:.6f} (range {lo:.6f} to {hi:.6f})." + _skip_note(skipped, outs)
    status = "info"
    printed = _num(rec, "printed_rho", required=False)
    if printed is not None:
        ok = _matches(printed, lo, hi)
        status = "ok" if ok else "mismatch"
        msg += f" Printed {rec['printed_rho']} {'matches' if ok else 'does not match'}."
    return {"status": status, "values": values, "message": msg}


def _reasons(rec: dict, key: str):
    raw = rec.get(key)
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise RecordError(f"field '{key}' must map each reason to a count")
    return sum(_int({"v": v}, "v") for v in raw.values())


def _counts(rec: dict, key: str):
    """One printed count, a list of printed counts, or a reason-to-count map; the sum, or None."""
    raw = rec.get(key)
    if raw is None:
        return None
    if isinstance(raw, dict):
        raw = list(raw.values())
    elif not isinstance(raw, list):
        raw = [raw]
    return sum(_int({"v": v}, "v") for v in raw)


def _unit(rec: dict, key: str):
    u = rec.get(key)
    if u is None:
        return None
    u = str(u).strip().lower()
    if u not in UNITS:
        raise RecordError(f"field '{key}' must be one of {', '.join(UNITS)}")
    return u


def _flow(rec: dict) -> dict:
    g = {k: _int(rec, k, required=False) for k in (
        "identified", "other_sources_identified", "duplicates_removed", "screened", "excluded_screening",
        "not_retrieved", "assessed_full_text", "included", "other_sources_included", "k_analyzed")}
    removed_other = _counts(rec, "removed_other") or 0
    excluded_ft = _reasons(rec, "excluded_full_text")
    inc_unit, k_unit = _unit(rec, "included_unit"), _unit(rec, "k_unit")
    steps = []

    def step(name, parts, printed_key, candidates):
        """candidates: (expected, layout note) pairs; the step is ok when the printed count equals any."""
        if any(p is None for p in parts) or g[printed_key] is None:
            steps.append({"step": name, "status": "not_computable"})
            return
        cands = candidates()
        hit = [c for c in cands if c[0] == g[printed_key]]
        expected, note = hit[0] if hit else cands[0]
        s = {"step": name, "expected": expected, "printed": g[printed_key], "status": "ok" if hit else "mismatch"}
        if note:
            s["layout"] = note
        steps.append(s)

    def screened():
        out = [(g["identified"] - g["duplicates_removed"] - removed_other, "")]
        if g["other_sources_identified"] is not None:
            out.append((out[0][0] + g["other_sources_identified"],
                        "PRISMA 2009 layout: records from other sources join before screening"))
        return out

    step("identified - removed before screening = screened",
         [g["identified"], g["duplicates_removed"]], "screened", screened)
    step("screened - excluded - not retrieved = assessed in full text",
         [g["screened"], g["excluded_screening"]], "assessed_full_text",
         lambda: [(g["screened"] - g["excluded_screening"] - (g["not_retrieved"] or 0), "")])
    if inc_unit not in (None, "articles", "reports"):
        steps.append({"step": "assessed - excluded with reasons + other sources = included", "status": "info",
                      "message": f"included is in {inc_unit}; the full-text count is in articles or reports; "
                                 f"not compared."})
    else:
        step("assessed - excluded with reasons + other sources = included",
             [g["assessed_full_text"], excluded_ft], "included",
             lambda: [(g["assessed_full_text"] - excluded_ft + (g["other_sources_included"] or 0), "")])
    if g["included"] is not None and g["k_analyzed"] is not None:
        if inc_unit and k_unit and inc_unit == k_unit:
            ok = g["included"] == g["k_analyzed"]
            steps.append({"step": "included = k analyzed", "expected": g["included"], "printed": g["k_analyzed"],
                          "status": "ok" if ok else "mismatch"})
        else:
            steps.append({"step": "included = k analyzed", "status": "info",
                          "message": f"included is in {inc_unit or 'an unstated unit'}; the analysis k is in "
                                     f"{k_unit or 'an unstated unit'}; not compared."})
    bad = [s for s in steps if s["status"] == "mismatch"]
    checked = [s for s in steps if s["status"] == "ok"]
    status = "mismatch" if bad else ("ok" if checked else "not_computable")
    parts = []
    for s in steps:
        if s["status"] in ("ok", "mismatch"):
            parts.append(f"{s['step']}: expected {s['expected']}, printed {s['printed']} ({s['status']}"
                         + (f"; {s['layout']}" if s.get("layout") else "") + ").")
        elif s["status"] == "info":
            parts.append(s["message"])
    return {"status": status, "values": {"steps": steps}, "message": " ".join(parts) or "No step could be checked."}


def _num_list(rec: dict, key: str, required: bool = True):
    raw = rec.get(key)
    if raw is None:
        if required:
            raise RecordError(f"missing field '{key}'")
        return None
    if not isinstance(raw, list) or not raw:
        raise RecordError(f"field '{key}' must be a non-empty list")
    return [_num({"v": x}, "v")[0] for x in raw]


def _cell_n(rec: dict) -> dict:
    ns = _num_list(rec, "cell_ns")
    ks = _num_list(rec, "cell_ks", required=False)
    used = _num(rec, "used_n")[0]
    if min(ns) <= 0:
        raise RecordError("cell sample sizes must be above zero")
    stats = {"min": min(ns), "max": max(ns), "arithmetic mean": sum(ns) / len(ns),
             "harmonic mean": harmonic_mean(ns), "median": median(ns)}
    # The 1.0 tolerance is a pragmatic bound set by this pack, not a published threshold.
    matches = [name for name, v in stats.items() if abs(v - used) <= 1.0]
    values = {k.replace(" ", "_"): _r(v, 2) for k, v in stats.items()}
    values["used_n"] = used
    values["used_n_matches"] = matches
    if ks:
        values["cell_k_range"] = [min(ks), max(ks)]
    msg = (f"Cell N runs {stats['min']:g} to {stats['max']:g}; arithmetic mean {stats['arithmetic mean']:.2f}, "
           f"harmonic mean {stats['harmonic mean']:.2f}, median {stats['median']:g}. The N used, {used:g}, "
           f"matches {', '.join(matches) if matches else 'none of these'}.")
    if ks:
        msg += f" Cell k runs {min(ks):g} to {max(ks):g}."
    return {"status": "info", "values": values, "message": msg}


def _study_table(rec: dict) -> dict:
    ns = _num_list(rec, "n")
    rs = _num_list(rec, "r", required=False)
    cols = {k: rec.get(k) for k in ("labels", "years", "sources")}
    for key, col in list(cols.items()) + [("r", rs)]:
        if col is not None and (not isinstance(col, list) or len(col) != len(ns)):
            raise RecordError(f"field '{key}' must have one entry per row of 'n'")
    for key, col in cols.items():
        if col is not None and not all(isinstance(x, (str, int, float)) and not isinstance(x, bool) for x in col):
            raise RecordError(f"field '{key}' must list text or numbers")
    labels = cols["labels"] or [f"row {i + 1}" for i in range(len(ns))]
    total = sum(ns)
    if total <= 0:
        raise RecordError("total N must be above zero")
    top = max(range(len(ns)), key=lambda i: ns[i])
    values = {"k": len(ns), "total_n": total, "largest": labels[top], "largest_share": _r(ns[top] / total, 4)}
    msg = (f"k = {len(ns)}, total N = {total:g}; the largest study ({labels[top]}) carries "
           f"{100 * ns[top] / total:.1f} percent of total N.")
    if rs:
        wmean = sum(n * r for n, r in zip(ns, rs)) / total
        values["n_weighted_mean_r"] = _r(wmean)
        msg += f" N-weighted mean r = {wmean:.4f}."
    groups = {}
    for i, n in enumerate(ns):
        key = (n, (cols["years"] or [None] * len(ns))[i], (cols["sources"] or [None] * len(ns))[i])
        groups.setdefault(key, []).append(labels[i])
    shared = [g for g in groups.values() if len(g) > 1]
    values["shared_rows"] = shared
    for g in shared:
        msg += f" Rows sharing N" + (", years, and source" if cols["years"] and cols["sources"] else "") + \
               f": {', '.join(str(x) for x in g)}."
    status = "info"
    bad = []
    pk = _int(rec, "printed_k", required=False)
    pn = _num(rec, "printed_total_n", required=False)
    if pk is not None:
        status = "ok"
        if pk != len(ns):
            bad.append(f"printed k {pk} is not the {len(ns)} rows listed")
    if pn is not None:
        status = "ok"
        if abs(pn[0] - total) > 0:
            bad.append(f"printed total N {rec['printed_total_n']} is not the sum {total:g}")
    if bad:
        status = "mismatch"
        msg += " " + "; ".join(bad).capitalize() + "."
    return {"status": status, "values": values, "message": msg}


HANDLERS = {"i2": _i2, "prediction_interval": _prediction_interval, "credibility_interval": _credibility_interval,
            "dependence_bound": _dependence_bound, "convert": _convert, "attenuation": _attenuation,
            "flow": _flow, "cell_n": _cell_n, "study_table": _study_table}


def run_record(rec, seen: set) -> dict:
    """One result per record; a malformed record gets status input_error."""
    base = {"id": None, "kind": None, "page": None, "locator": None}
    if not isinstance(rec, dict):
        return dict(base, status="input_error", values={}, message="record is not an object")
    # Echo only text; any other value (a list, an object, a non-finite number) is left out as None.
    base.update({k: rec[k] for k in base if isinstance(rec.get(k), str)})
    try:
        rid = rec.get("id")
        if not isinstance(rid, str) or not rid.strip():
            raise RecordError("missing field 'id'")
        if rid in seen:
            raise RecordError(f"duplicate id '{rid}'")
        seen.add(rid)
        for key in ("page", "locator"):
            if not isinstance(rec.get(key), str) or not rec[key].strip():
                raise RecordError(f"missing field '{key}'")
        if rec.get("alt_group") is not None and (not isinstance(rec["alt_group"], str)
                                                 or not rec["alt_group"].strip()):
            raise RecordError("field 'alt_group' must be a non-empty string")
        kind = rec.get("kind")
        if not isinstance(kind, str) or kind not in HANDLERS:
            raise RecordError(f"kind must be one of {', '.join(KINDS)}")
        try:
            out = HANDLERS[kind](rec)
        except (ValueError, ZeroDivisionError, OverflowError, TypeError) as e:
            raise RecordError(f"the values in this record cannot be computed ({type(e).__name__}: {e})")
        if not _finite(out["values"]):
            raise RecordError("a result is not a finite number; check the printed values")
    except RecordError as e:
        out = {"status": "input_error", "values": {}, "message": str(e)}
    return dict(base, **out)


def resolve_groups(records: list, results: list) -> list:
    """Records sharing an alt_group are alternative readings of one printed value. A mismatching
    record becomes info only when another member of the group has status ok; a sibling that made no
    comparison (no printed value, not_computable, input_error) does not count. A group whose members
    differ in kind is not resolved: each member keeps its result and gets a note."""
    groups: dict = {}
    for rec, res in zip(records, results):
        gid = rec.get("alt_group") if isinstance(rec, dict) else None
        if isinstance(gid, str) and gid.strip() and res["status"] != "input_error":
            groups.setdefault(gid, []).append(res)
    for gid, members in groups.items():
        if len(members) < 2:
            continue
        if len({m["kind"] for m in members}) > 1:
            for m in members:
                m["message"] += f" Group '{gid}' mixed kinds and was not resolved."
            continue
        matching = [m["id"] for m in members if m["status"] == "ok"]
        if not matching:
            continue
        for m in members:
            if m["status"] == "mismatch":
                m["status"] = "info"
                m["message"] += (f" Alternative reading in group '{gid}': not a flag, because another "
                                 f"alternative in the group matched ({', '.join(matching)}).")
            elif m["status"] == "ok":
                others = [x["id"] for x in members if x["status"] == "info" and "not a flag" in x["message"]]
                if others:
                    m["message"] += (f" Matching alternative in group '{gid}'; the alternatives "
                                     f"{', '.join(others)} do not match.")
    return results


def _finite(obj) -> bool:
    if isinstance(obj, float):
        return math.isfinite(obj)
    if isinstance(obj, dict):
        return all(_finite(v) for v in obj.values())
    if isinstance(obj, (list, tuple)):
        return all(_finite(v) for v in obj)
    return True


def verdict(results: list) -> str:
    if not results:
        return "NO_CHECKS"
    if any(r["status"] == "input_error" for r in results):
        return "INPUT_ERRORS_PRESENT"
    if any(r["status"] == "mismatch" for r in results):
        return "MISMATCHES_FOUND"
    return "OK"


def report(results: list) -> str:
    v = verdict(results)
    m = sum(r["status"] == "mismatch" for r in results)
    e = sum(r["status"] == "input_error" for r in results)
    lines = [f"VERDICT: {v}", "", "# Meta-analysis arithmetic (deterministic)", "",
             f"Checks: {len(results)} | mismatches: {m} | input errors: {e}", ""]
    for r in results:
        lines.append(f"- [{r['status'].upper()}] {r['id']} ({r['kind']}, p. {r['page']}; {r['locator']}): "
                     f"{r['message']}")
    return "\n".join(lines) + "\n"


def _no_constant(name: str):
    raise ValueError(f"{name} is not a number JSON allows")


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("Usage: ma_arith.py <input.json> <out.md>")
        return 2
    src, out = Path(argv[0]), Path(argv[1])
    try:
        records = json.loads(src.read_text(encoding="utf-8"), parse_constant=_no_constant)
    except (OSError, ValueError) as e:
        print(f"MA_ARITH: cannot read {src}: {e}")
        return 2
    except RecursionError:
        print(f"MA_ARITH: cannot read {src}: the JSON is nested too deeply")
        return 2
    if not isinstance(records, list):
        print(f"MA_ARITH: {src} must hold a JSON list of records")
        return 2
    seen = set()
    results = resolve_groups(records, [run_record(r, seen) for r in records])
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report(results), encoding="utf-8")
        out.with_suffix(".json").write_text(json.dumps(results, indent=2, allow_nan=False), encoding="utf-8")
    except OSError as e:
        print(f"MA_ARITH: cannot write {out}: {e}")
        return 2
    m = sum(r["status"] == "mismatch" for r in results)
    e = sum(r["status"] == "input_error" for r in results)
    print(f"MA_ARITH: {m} mismatches, {e} input errors, {len(results)} checks [VERDICT: {verdict(results)}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
