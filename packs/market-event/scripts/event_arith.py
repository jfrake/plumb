#!/usr/bin/env python3
"""Arithmetic for the market-event pack.

Recomputes what a paper's printed abnormal-return numbers imply: the cross-sectional t from a
mean CAR, its standard deviation, and N; the p-values and stars that t allows; whether window
CARs add up from daily or sub-window means; whether a share of positive CARs is possible with N;
whether sample counts reconcile; and how events spread over periods and dates. Every number comes
from the paper through the verify agent's inputs file; nothing is estimated. A result is flagged
only when no rounding of the printed digits could produce what the paper prints.

Usage: event_arith.py <inputs.json> <out.json>
Exit 0 when out.json is written. Exit 2 when the inputs cannot be read.
"""
from __future__ import annotations

import datetime
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "skills" / "review" / "scripts"))
import pvalues  # noqa: E402

KINDS = ("car_test", "window_sum", "sign", "sample_flow", "period_counts", "event_dates")

# Reasons that make a result a number flag. Every other reason is a fact for the diagnose agents.
FLAG_REASONS = {
    "t_mismatch",
    "stars_exceed",
    "stars_short",
    "p_mismatch",
    "sum_mismatch",
    "pct_not_achievable",
    "sign_z_mismatch",
    "step_mismatch",
    "flow_mismatch",
    "counts_sum_mismatch",
}

DEFAULT_STARS = {"*": 0.10, "**": 0.05, "***": 0.01}
NAMED_TEST = "cross-sectional t"
WINSORIZED = ("daily", "window", "none", "unstated")
MAX_TILINGS = 50
EPS = 1e-9


class RecordError(Exception):
    pass


def _fmt(v: float) -> str:
    if math.isinf(v):
        return "infinity"
    return f"{v:.4g}"


def _printed(rec: dict, key: str):
    """(value, half_unit) for a printed field. A string keeps its decimals; a JSON number is exact."""
    v = rec.get(key)
    if v is None:
        raise RecordError(f"missing field '{key}'")
    if isinstance(v, bool):
        raise RecordError(f"field '{key}' must be a number")
    if isinstance(v, (int, float)):
        raise RecordError(f"field '{key}' is a JSON number; copy printed values as strings so their rounding is kept")
    parsed = pvalues.parse_printed(v)
    if parsed is None:
        raise RecordError(f"field '{key}' is not a number: {v!r}")
    return parsed


def _tails(rec: dict) -> str:
    raw = str(rec.get("tails", "")).strip().lower().replace("-", " ")
    if raw in ("one", "one tailed", "1"):
        return "one"
    if raw in ("two", "two tailed", "2"):
        return "two"
    return "unstated"


def _int(rec: dict, key: str, minimum: int = 0) -> int:
    v = rec.get(key)
    if isinstance(v, bool) or not isinstance(v, int):
        raise RecordError(f"field '{key}' must be a whole number")
    if v < minimum:
        raise RecordError(f"field '{key}' must be at least {minimum}")
    return v


def _meets(a, b) -> bool:
    """Closed intervals a and b share a point."""
    return a[0] <= b[1] + EPS and b[0] <= a[1] + EPS


def _levels(rec: dict) -> dict:
    """The star key: each mark to a threshold strictly between 0 and 1; the default when none is given."""
    raw = rec.get("star_levels")
    if not raw:
        return DEFAULT_STARS
    if not isinstance(raw, dict) or not all(
            isinstance(m, str) and isinstance(v, (int, float)) and not isinstance(v, bool) and 0 < v < 1
            for m, v in raw.items()):
        raise RecordError("field 'star_levels' must map each mark to a threshold between 0 and 1")
    return raw


def _star_band(mark: str, levels: dict):
    """The p interval a printed mark stands for, with closed edges; None for an unknown mark."""
    ordered = sorted(levels.items(), key=lambda kv: -kv[1])
    if mark == "":
        return (ordered[0][1], 1.0)
    for i, (m, tau) in enumerate(ordered):
        if m == mark:
            nxt = ordered[i + 1][1] if i + 1 < len(ordered) else 0.0
            return (nxt, tau)
    return None


# ---------------------------------------------------------------------------
# car_test
# ---------------------------------------------------------------------------

def _car_test(rec: dict, out: dict) -> None:
    mean, h_m = _printed(rec, "mean")
    n = _int(rec, "n", minimum=2)
    df = n - 1
    test = rec.get("test", "unspecified")
    named = test == NAMED_TEST or rec.get("formula_stated") is True
    values, reasons, facts = out["values"], out["reasons"], out["facts"]
    values["named"] = named
    p_raw = rec.get("p")
    if isinstance(p_raw, (int, float)) and not isinstance(p_raw, bool):
        raise RecordError("field 'p' is a JSON number; copy printed values as strings so their rounding is kept")

    recomputed = None
    if "sd" in rec or "se" in rec:
        key = "sd" if "sd" in rec else "se"
        s, h_s = _printed(rec, key)
        if s <= 0:
            raise RecordError(f"field '{key}' must be positive")
        scale = math.sqrt(n) if key == "sd" else 1.0
        t = abs(mean) / (s / scale)
        lo = max(0.0, abs(mean) - h_m) / ((s + h_s) / scale)
        hi = (abs(mean) + h_m) / ((s - h_s) / scale) if s - h_s > 0 else math.inf
        recomputed = (lo, hi)
        values["t_recomputed"] = t
        values["t_range"] = [lo, hi]
        facts.append(f"The cross-sectional t from mean {rec['mean']}, {key} {rec[key]}, and N {n} is {_fmt(t)} "
                     f"(between {_fmt(lo)} and {_fmt(hi)} for every rounding of the printed digits).")

    stat = None
    if "t" in rec:
        tv, h_t = _printed(rec, "t")
        stat = (max(0.0, abs(tv) - h_t), abs(tv) + h_t)
        values["t_printed_range"] = list(stat)
        if recomputed is not None and not _meets(stat, recomputed):
            ratio = abs(tv) / values["t_recomputed"] if values["t_recomputed"] > 0 else math.inf
            values["ratio_printed_to_recomputed"] = ratio
            if named:
                reasons.append("t_mismatch")
                facts.append(f"The printed t {rec['t']} cannot come from the printed mean, spread, and N, which "
                             f"allow {_fmt(recomputed[0])} to {_fmt(recomputed[1])}.")
            else:
                reasons.append("reported_stat_differs_from_cross_sectional_t")
                facts.append(f"The printed statistic {rec['t']} ({test}) is {_fmt(ratio)} times the cross-sectional "
                             f"t; the paper does not identify it as the cross-sectional t.")
        if recomputed is None and tv != 0:
            implied = abs(mean) * math.sqrt(n) / abs(tv)
            values["implied_sd"] = implied
            facts.append(f"Mean {rec['mean']} with t {rec['t']} and N {n} implies a cross-sectional standard "
                         f"deviation of {_fmt(implied)} if the statistic is the cross-sectional t.")
    elif recomputed is not None:
        stat = recomputed

    checked_sig = False
    if stat is not None and ("stars" in rec or "p" in rec):
        p_all = (pvalues.p_normal(stat[1]), pvalues.p_student(stat[0], df))
        p_t = (pvalues.p_student(stat[1], df), pvalues.p_student(stat[0], df))
        values["p_range"] = list(p_all)
        values["p_range_t"] = list(p_t)
        facts.append(f"The statistic allows p from {_fmt(p_all[0])} (normal) to {_fmt(p_all[1])} "
                     f"(Student t with {df} df).")
        # One-tailed or unstated tails also allow the halved (one-sided) p interval.
        readings = [p_all]
        readings_t = [p_t]
        if _tails(rec) != "two":
            readings.append((p_all[0] / 2, p_all[1] / 2))
            readings_t.append((p_t[0] / 2, p_t[1] / 2))
        values["tails"] = _tails(rec)
        # An unnamed printed statistic is described as itself, not as the cross-sectional t.
        if "t" in rec:
            unnamed_ref = (f"the printed statistic under any reference from the normal to Student t with {df} df "
                           f"({_fmt(p_all[0])} to {_fmt(p_all[1])}); the paper does not identify its test as "
                           f"the cross-sectional t")
        else:
            unnamed_ref = (f"the cross-sectional t ({_fmt(p_all[0])} to {_fmt(p_all[1])}); the paper does not "
                           f"identify its test as that t")
        need = None
        if "stars" in rec:
            checked_sig = True
            levels = _levels(rec)
            mark = str(rec["stars"]).strip()
            band = _star_band(mark, levels)
            if band is not None:
                need = (f"the mark {mark!r} needs at most {_fmt(band[1])}" if mark
                        else f"no mark needs at least {_fmt(band[0])}")
            if band is None:
                facts.append(f"The mark {mark!r} is not in the star levels {levels}; not checked.")
            elif not any(_meets(r, band) for r in readings):
                code = "stars_exceed" if p_all[0] > band[1] else "stars_short"
                if named:
                    reasons.append(code)
                    facts.append(f"The mark {mark!r} needs p between {_fmt(band[0])} and {_fmt(band[1])}; the "
                                 f"printed numbers allow {_fmt(p_all[0])} to {_fmt(p_all[1])}.")
                else:
                    reasons.append("stars_differ_from_cross_sectional_t")
                    facts.append(f"The mark {mark!r} does not fit {unnamed_ref}.")
            elif named and not any(_meets(r, band) for r in readings_t) and min(r[0] for r in readings_t) > band[1]:
                reasons.append("stars_exceed_under_t")
                facts.append(f"The mark {mark!r} fits the normal reference but not Student t with {df} df "
                             f"(p {_fmt(p_t[0])} to {_fmt(p_t[1])}).")
        if "p" in rec:
            checked_sig = True
            printed = pvalues.printed_p_range(str(rec["p"]))
            if printed is None:
                facts.append(f"The printed p {rec['p']!r} is not a number; not checked.")
            elif not any(_meets(r, printed) for r in readings):
                if named:
                    reasons.append("p_mismatch")
                    facts.append(f"The printed p {rec['p']} is outside {_fmt(p_all[0])} to {_fmt(p_all[1])}.")
                else:
                    reasons.append("p_differs_from_cross_sectional_t")
                    facts.append(f"The printed p {rec['p']} does not fit {unnamed_ref}.")
            if printed is not None and need is None:
                need = f"the printed p {rec['p']} is at most {_fmt(printed[1])}"
        if recomputed is not None:
            p_rec = (pvalues.p_normal(recomputed[1]), pvalues.p_student(recomputed[0], df))
            values["p_range_recomputed"] = list(p_rec)
            tail = f"; {need}" if need else ""
            facts.append(f"The recomputed t allows p from {_fmt(p_rec[0])} to {_fmt(p_rec[1])}{tail}.")

    if recomputed is None and "t" not in rec and not checked_sig:
        out["status"] = "not_computable"
        out["message"] = "needs sd, se, or t to check anything"


# ---------------------------------------------------------------------------
# window_sum
# ---------------------------------------------------------------------------

def _items(rec: dict) -> list:
    raw = rec.get("items")
    if not isinstance(raw, list) or len(raw) < 2:
        raise RecordError("field 'items' must be a list of at least two windows")
    items = []
    for it in raw:
        if not isinstance(it, dict):
            raise RecordError("each item must be an object")
        start, end = _int_any(it, "start"), _int_any(it, "end")
        if start > end:
            raise RecordError(f"item {it.get('label')!r} starts after it ends")
        value, half = _printed(it, "value")
        items.append({"label": str(it.get("label", f"[{start}, {end}]")), "start": start, "end": end,
                      "value": value, "half": half, "n": _int(it, "n", minimum=1)})
    return items


def _int_any(it: dict, key: str) -> int:
    v = it.get(key)
    if isinstance(v, bool) or not isinstance(v, int):
        raise RecordError(f"item field '{key}' must be a whole number")
    return v


def tilings(items: list, target: int, limit: int = MAX_TILINGS) -> list:
    """Every list of two or more other items that covers items[target]'s days exactly, in order,
    without overlap. At most `limit` tilings."""
    w = items[target]
    parts = [j for j, it in enumerate(items)
             if j != target and w["start"] <= it["start"] and it["end"] <= w["end"]]
    by_start = {}
    for j in parts:
        by_start.setdefault(items[j]["start"], []).append(j)
    found = []
    # Backward pass: which positions can still reach end + 1.
    reach = {w["end"] + 1: True}
    for pos in range(w["end"], w["start"] - 1, -1):
        reach[pos] = any(reach.get(items[j]["end"] + 1, False) for j in by_start.get(pos, []))
    if not reach[w["start"]]:
        return found

    def walk(pos, chosen):
        if len(found) >= limit:
            return
        if pos == w["end"] + 1:
            if len(chosen) >= 2:
                found.append(list(chosen))
            return
        for j in by_start.get(pos, []):
            if not reach.get(items[j]["end"] + 1, False):
                continue
            chosen.append(j)
            walk(items[j]["end"] + 1, chosen)
            chosen.pop()

    walk(w["start"], [])
    return found


def _window_sum(rec: dict, out: dict) -> None:
    measure = rec.get("measure")
    level = rec.get("winsorized_level")
    if level not in WINSORIZED:
        raise RecordError(f"field 'winsorized_level' must be one of {', '.join(WINSORIZED)}")
    items = _items(rec)
    if measure != "CAR":
        out["status"] = "not_computable"
        out["message"] = f"measure {measure!r} does not add across windows; only CAR (a sum) does"
        return
    checked = []
    for i, w in enumerate(items):
        found = tilings(items, i)
        differs = False
        for tiling in found:
            if any(items[j]["n"] != w["n"] for j in tiling):
                differs = True
                continue
            total = sum(items[j]["value"] for j in tiling)
            gap = abs(total - w["value"])
            tol = sum(items[j]["half"] for j in tiling) + w["half"]
            ok = gap <= tol + EPS
            labels = [items[j]["label"] for j in tiling]
            checked.append({"window": w["label"], "parts": labels, "sum": total, "value": w["value"],
                            "gap": gap, "tolerance": tol, "ok": ok})
            if not ok:
                code = "sum_mismatch" if level in ("daily", "none") else "sum_mismatch_unflagged"
                if code not in out["reasons"]:
                    out["reasons"].append(code)
                out["facts"].append(f"{w['label']} is printed as {_fmt(w['value'])}, but {' + '.join(labels)} "
                                    f"sum to {_fmt(total)} (gap {_fmt(gap)}, rounding allows {_fmt(tol)}).")
        if differs:
            if "n_differs" not in out["reasons"]:
                out["reasons"].append("n_differs")
            out["facts"].append(f"Some ways of adding up {w['label']} use windows with a different N; means add "
                                f"only over the same events, so those were not checked.")
    out["values"]["tilings"] = checked
    if level not in ("daily", "none") and "sum_mismatch_unflagged" in out["reasons"]:
        out["facts"].append(f"Extreme values were handled at level {level!r}, which can break additivity, so a "
                            f"gap is a fact, not a flag.")


# ---------------------------------------------------------------------------
# sign
# ---------------------------------------------------------------------------

def _binomial_two_sided(ks: list, n: int) -> dict:
    """Exact two-sided sign-test p at 0.5 for each k: twice the smaller tail, capped at 1. One pass with
    exact integer counts and running sums."""
    coef, run = [1], 1
    for i in range(n):
        run = run * (n - i) // (i + 1)
        coef.append(run)
    prefix, total = [], 0
    for c in coef:
        total += c
        prefix.append(total)
    out = {}
    for k in ks:
        lower = prefix[k]
        upper = total - (prefix[k - 1] if k > 0 else 0)
        out[str(k)] = min(1.0, 2 * min(lower, upper) / 2 ** n)
    return out


def _sign_z(k: int, n: int, p0: float, corrected: bool) -> float:
    d = k - n * p0
    if corrected:
        d = math.copysign(max(0.0, abs(d) - 0.5), d)
    return d / math.sqrt(n * p0 * (1 - p0))


def _sign(rec: dict, out: dict) -> None:
    n = _int(rec, "n", minimum=1)
    values, reasons, facts = out["values"], out["reasons"], out["facts"]
    if "n_positive" in rec:
        k = _int(rec, "n_positive")
        if k > n:
            raise RecordError("field 'n_positive' exceeds n")
        k_lo = k_hi = k
    elif "pct_positive" in rec:
        v, h = _printed(rec, "pct_positive")
        k_lo = max(0, math.ceil(n * (v - h - EPS) / 100.0))
        k_hi = min(n, math.floor(n * (v + h + EPS) / 100.0))
    else:
        raise RecordError("needs 'pct_positive' or 'n_positive'")
    wide = k_hi - k_lo + 1 > 50
    ks = [] if k_lo > k_hi else ([k_lo, k_hi] if wide else list(range(k_lo, k_hi + 1)))
    values["possible_k"] = ks
    if not ks:
        reasons.append("pct_not_achievable")
        facts.append(f"No count of positive CARs out of {n} gives the printed {rec['pct_positive']} percent.")
        return
    if wide:
        facts.append(f"Positive CARs: every count from {k_lo} to {k_hi} of {n}.")
    else:
        facts.append(f"Positive CARs: {', '.join(str(k) for k in ks)} of {n}.")
    if n <= 5000:
        eval_ks = ks
        if wide and k_lo <= n / 2 <= k_hi:
            eval_ks = sorted(set(ks) | {n // 2, -(-n // 2)})
        values["binomial_p"] = _binomial_two_sided(eval_ks, n)
        if wide:
            ps = values["binomial_p"].values()
            facts.append(f"Exact two-sided sign-test p at 0.5: p from {_fmt(min(ps))} to {_fmt(max(ps))} over "
                         f"counts {k_lo} to {k_hi}.")
        else:
            facts.append("Exact two-sided sign-test p at 0.5: "
                         + ", ".join(f"{_fmt(values['binomial_p'][str(k)])} for {k}" for k in ks) + ".")
    test = rec.get("test", "unspecified")
    p0, h_p = None, 0.0
    if rec.get("p0") is not None:
        p0, h_p = _printed(rec, "p0")
    elif test == "sign":
        p0 = 0.5
    if "z" in rec:
        if p0 is None:
            facts.append("The z is not checked: a generalized sign test needs the estimation-window share (p0), "
                         "which the paper does not give.")
        else:
            if not (0 < p0 - h_p and p0 + h_p < 1):
                raise RecordError("field 'p0' must lie between 0 and 1")
            zv, h_z = _printed(rec, "z")
            # Both forms of z fall as p0 rises (k is between 0 and n), so the ends of p0's rounding bound them.
            # z also rises with k, so a wide range of counts is bounded by its two ends.
            zs, spans = [], []
            for k in ks:
                for corrected in (False, True):
                    zs.append(_sign_z(k, n, p0, corrected))
                    ends = (_sign_z(k, n, p0 + h_p, corrected), _sign_z(k, n, p0 - h_p, corrected))
                    spans.append([min(ends), max(ends)])
            if wide:
                spans = [[min(sp[0] for sp in spans), max(sp[1] for sp in spans)]]
            values["z_candidates"] = zs
            values["z_ranges"] = spans
            printed_z = (zv - h_z, zv + h_z)
            if not any(_meets(printed_z, s) for s in spans):
                if any(_meets((-printed_z[1], -printed_z[0]), s) for s in spans):
                    facts.append(f"The sign of z differs from the printed value {rec['z']}; its size fits.")
                else:
                    reasons.append("sign_z_mismatch")
                    facts.append(f"The printed z {rec['z']} matches none of "
                                 + ", ".join(_fmt(z) for z in zs) + " (with and without continuity correction).")
    if "mean" in rec:
        m, _ = _printed(rec, "mean")
        # The rounding box of the share: the whole box must lie strictly on the far side of 50.
        if "n_positive" in rec:
            box = (100.0 * k_lo / n, 100.0 * k_hi / n)
        else:
            box = (v - h, v + h)
        shares = [100.0 * k / n for k in ks]
        if (m > 0 and box[1] < 50 - EPS) or (m < 0 and box[0] > 50 + EPS):
            reasons.append("majority_against_mean")
            facts.append(f"The mean CAR is {rec['mean']}, but the share of positive CARs is "
                         f"{_fmt(shares[0])} percent: most events move the other way.")
        if "median" in rec:
            med, _ = _printed(rec, "median")
            if m * med < 0:
                reasons.append("median_against_mean")
                facts.append(f"The median CAR {rec['median']} and the mean {rec['mean']} have opposite signs.")


# ---------------------------------------------------------------------------
# sample_flow, period_counts, event_dates
# ---------------------------------------------------------------------------

def _sample_flow(rec: dict, out: dict) -> None:
    running = _int(rec, "start")
    steps = rec.get("steps")
    if not isinstance(steps, list) or not steps:
        raise RecordError("field 'steps' must be a non-empty list")
    final = _int(rec, "final")
    trail = []
    for st in steps:
        if not isinstance(st, dict):
            raise RecordError("each step must be an object")
        running -= _int(st, "removed")
        trail.append(running)
        if "remaining" in st and _int(st, "remaining") != running:
            out["reasons"].append("step_mismatch")
            out["facts"].append(f"After '{st.get('label', '')}', the paper says {st['remaining']} remain; the "
                                f"counts give {running}.")
    out["values"]["running"] = trail
    if running != final:
        out["reasons"].append("flow_mismatch")
        out["facts"].append(f"{rec['start']} minus the removals is {running}, but the paper's final sample is {final}.")


def _period_counts(rec: dict, out: dict) -> None:
    counts = rec.get("counts")
    if not isinstance(counts, dict) or not counts:
        raise RecordError("field 'counts' must map periods to counts")
    for label, c in counts.items():
        if isinstance(c, bool) or not isinstance(c, int) or c < 0:
            raise RecordError(f"count for {label!r} must be a whole number")
    total = sum(counts.values())
    if total == 0:
        raise RecordError("counts sum to zero")
    ordered = sorted(counts.items(), key=lambda kv: -kv[1])
    out["values"].update({"sum": total, "largest": ordered[0][0], "largest_share": ordered[0][1] / total,
                          "two_largest_share": sum(c for _, c in ordered[:2]) / total})
    out["facts"].append(f"The largest period, {ordered[0][0]}, holds {_fmt(ordered[0][1] / total)} of {total} "
                        f"events; the two largest hold {_fmt(out['values']['two_largest_share'])}.")
    if "total" in rec and _int(rec, "total") != total:
        out["reasons"].append("counts_sum_mismatch")
        out["facts"].append(f"The period counts sum to {total}, not the printed total {rec['total']}.")


def _add_weekdays(day: datetime.date, k: int) -> datetime.date:
    step = 1 if k > 0 else -1
    while k != 0:
        day += datetime.timedelta(days=step)
        if day.weekday() < 5:
            k -= step
    return day


def _event_dates(rec: dict, out: dict) -> None:
    raw = rec.get("dates")
    window = rec.get("window")
    if not isinstance(raw, list) or len(raw) < 2:
        raise RecordError("field 'dates' must list at least two dates")
    if (not isinstance(window, list) or len(window) != 2
            or not all(isinstance(x, int) and not isinstance(x, bool) for x in window) or window[0] > window[1]):
        raise RecordError("field 'window' must be [a, b] with whole numbers a <= b")
    if window[1] - window[0] > 2520:
        out["status"] = "not_computable"
        out["message"] = ("window wider than 2,520 trading days (ten years), a pragmatic bound set by this pack")
        return
    days, moved = [], 0
    for s in raw:
        try:
            d = datetime.date.fromisoformat(str(s))
        except ValueError:
            raise RecordError(f"unparseable date {s!r}")
        if d.weekday() >= 5:
            try:
                d += datetime.timedelta(days=7 - d.weekday())
            except OverflowError:
                raise RecordError(f"date {s!r} is too close to the calendar's limit")
            moved += 1
        days.append(d)
    a, b = window
    spans = []
    for d in days:
        try:
            first = _add_weekdays(d, a) if a else d
            span, cur = [], first
            for _ in range(b - a + 1):
                span.append(cur)
                cur = _add_weekdays(cur, 1)
        except OverflowError:
            raise RecordError(f"the window around date {d.isoformat()} runs past the calendar's limit")
        spans.append(set(span))
    n = len(days)
    shared = sum(1 for i, d in enumerate(days) if days.count(d) > 1)
    overlap = sum(1 for i in range(n) if any(spans[i] & spans[j] for j in range(n) if j != i))
    cover = {}
    for sp in spans:
        for d in sp:
            cover[d] = cover.get(d, 0) + 1
    out["values"].update({"n": n, "moved": moved, "distinct_dates": len(set(days)),
                          "share_shared_day0": shared / n, "share_overlapping": overlap / n,
                          "max_windows_one_day": max(cover.values())})
    out["facts"].append(f"{n} events on {len(set(days))} distinct dates; {_fmt(shared / n)} share a day 0 with "
                        f"another event and {_fmt(overlap / n)} have a window that overlaps another's; at most "
                        f"{max(cover.values())} windows cover one weekday. Trading days are approximated by "
                        f"weekdays with no holiday calendar; {moved} weekend dates moved to Monday.")


HANDLERS = {"car_test": _car_test, "window_sum": _window_sum, "sign": _sign, "sample_flow": _sample_flow,
            "period_counts": _period_counts, "event_dates": _event_dates}


def run_record(rec: dict, seen: set) -> dict:
    out = {"id": rec.get("id"), "kind": rec.get("kind"), "check": rec.get("check", "R10"),
           "analysis": rec.get("analysis"), "source": rec.get("source"), "status": "ok", "values": {},
           "reasons": [], "flag": False, "facts": [], "message": ""}
    try:
        rid = rec.get("id")
        if not isinstance(rid, str) or not rid:
            raise RecordError("missing field 'id'")
        if rid in seen:
            raise RecordError(f"duplicate id {rid!r}")
        seen.add(rid)
        if not isinstance(rec.get("kind"), str) or rec["kind"] not in HANDLERS:
            raise RecordError(f"unknown kind {rec.get('kind')!r}; expected one of {', '.join(KINDS)}")
        HANDLERS[rec["kind"]](rec, out)
    except RecordError as exc:
        out.update({"status": "invalid", "message": str(exc), "values": {}, "reasons": [], "facts": []})
    out["flag"] = out["status"] == "ok" and any(r in FLAG_REASONS for r in out["reasons"])
    return out


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("usage: event_arith.py <inputs.json> <out.json>", file=sys.stderr)
        return 2
    src, dst = Path(argv[0]), Path(argv[1])
    try:
        records = json.loads(src.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"cannot read {src}: {exc}", file=sys.stderr)
        return 2
    if not isinstance(records, list):
        print(f"{src} must hold a JSON list of records", file=sys.stderr)
        return 2
    seen = set()
    results = [run_record(r if isinstance(r, dict) else {"id": None}, seen) for r in records]
    dst.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
