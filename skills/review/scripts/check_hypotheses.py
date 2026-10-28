#!/usr/bin/env python3
"""Deterministic checks on the hypothesis ledger: HL3, HL5, HL7, HL9, and HL15 flags, and HL8 facts.

Usage: check_hypotheses.py <ledger.json> <out.md> --json <out.json> [--tables <extracted_tables dir>]

Every estimate is read as printed, so its rounding is known, and a flag is raised only when the
verdict is wrong for every value the printed digits allow (verify_arithmetic.check_claim and
pvalues). HL3, HL5, and HL15 read only a row's focal tests (the focal-test table in
verify_hypothesis_ledger.py), except that a partially supported verdict is flagged only when every
cited test, focal or not, fails. A blank estimate is not computed. One flag per row per check, listing
every reason. The script never computes a value a test does not print. Table notes, for tests that print only marks, are read
from --tables, or from <workspace>/extracted_tables when the ledger sits in <workspace>/stage-1/.

Exit 0 when the report is written; 2 when an import fails or the ledger is missing, not valid
JSON, not a JSON object, or prints a number too long to read as a finite value. Standard library only.
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

USAGE = "Usage: check_hypotheses.py <ledger.json> <out.md> --json <out.json> [--tables <extracted_tables dir>]"
SUPPORTED = ("supported", "marginally supported")
# HL3 also reads a partial verdict, flagged only when every cited test, focal or not, fails.
HL3_VERDICTS = SUPPORTED + ("partially supported",)
TIE = 1e-9
# The one reason inference I13 reads as a verdict that holds only on a one-tailed reading. Emitted only when the
# split is between the test's tail readings; other straddles (rounding, a printed bound, the marks' convention or
# range, the parentheses) carry their own reasons.
TAILS_STRADDLE = "the readings straddle"
BLANK = "the estimate is blank (a cell left unverified or not copied)"


def _imports():
    """The repo's p-value routines. None, with the reason, when they cannot be imported."""
    try:
        import pvalues
        import verify_arithmetic
        import verify_hypothesis_ledger as gate
    except ImportError as exc:  # the caller turns this into exit 2
        return None, str(exc)
    return (pvalues, verify_arithmetic, gate), ""


# ---------------------------------------------------------------------------
# Reading the ledger
# ---------------------------------------------------------------------------

def _s(value):
    return value.strip() if isinstance(value, str) else ""


def _est(test):
    return test.get("estimate") if isinstance(test.get("estimate"), dict) else {}


def _tests(row):
    return [t for t in (row.get("tests") if isinstance(row.get("tests"), list) else []) if isinstance(t, dict)]


def _cites(row):
    cites = row.get("verdict_cites") if isinstance(row.get("verdict_cites"), list) else []
    return [t for t in _tests(row) if t.get("test_id") in cites]


def _verdict(row, test):
    return _s(test.get("verdict")) or _s(row.get("verdict"))


def _parse(pv, text):
    return pv.parse_printed(text) if _s(text) else None


def _levels(test):
    out = []
    for x in test.get("note_levels") if isinstance(test.get("note_levels"), list) else []:
        p = None
        if isinstance(x, str) and x.strip():
            try:
                p = float(x.strip().lstrip("<").strip())
            except ValueError:
                p = None
        if p is not None and 0 < p <= 1:
            out.append(p)
    return out


def _level(ledger, row, test, verdict, pv):
    """The level a verdict is held to, as (value, source), or (None, reason)."""
    if verdict == "marginally supported":
        levels = _levels(test)
        return (max(levels), "the largest level in the table note") if levels else (None, "no note levels")
    for text, source in ((row.get("claimed_level"), "the level the verdict sentence states"),
                         ((ledger.get("criterion") or {}).get("level") if isinstance(ledger.get("criterion"), dict) else "",
                          "the paper's stated criterion")):
        p = _parse(pv, text)
        if p and 0 < p[0] <= 1:
            return p[0], source
    levels = _levels(test)
    if levels:
        return max(levels), "the largest level in the table note"
    return None, "the paper states no level and the table note gives none"


def _tails(ledger, test):
    t = _s(test.get("tails"))
    if t in ("one", "two"):
        return t
    crit = ledger.get("criterion") if isinstance(ledger.get("criterion"), dict) else {}
    return _s(crit.get("tails")) if _s(crit.get("tails")) in ("one", "two") else "unstated"


def _cells(tests):
    out = []
    for t in tests:
        for c in t.get("cells") if isinstance(t.get("cells"), list) else []:
            if isinstance(c, str) and c not in out:
                out.append(c)
    return out


def _where(test):
    parts = [_s(test.get("table")), _s(test.get("column")), _s(test.get("term"))]
    return ", ".join(p for p in parts if p) or _s(test.get("test_id")) or "a test"


def _p(x, level=None):
    """A p bound as printed in a reason: four decimals below 0.01 or within 0.005 of the level, else three."""
    near = level is not None and abs(x - level) <= 0.005 + TIE
    return f"{x:.4f}" if x < 0.01 or near else f"{x:.3f}"


def _blank(test):
    """True when a test's b, t, p, and interval are all empty: a cell left unverified, never 'no mark'."""
    est = _est(test)
    ci = est.get("ci") if isinstance(est.get("ci"), list) else []
    return not any(_s(est.get(k)) for k in ("b", "t", "p")) and not any(_s(c) for c in ci)


# ---------------------------------------------------------------------------
# Significance of one test against a level
# ---------------------------------------------------------------------------

def _record(test, directional, tails, pv):
    """A check_claim record from a test's printed numbers, or (None, reason). A ratio never
    uses its error (its p comes from the log scale); a standardized estimate uses its error only when the
    error belongs to the printed number."""
    est = _est(test)
    rec = {"id": test.get("test_id"), "directional": directional, "tails": tails}
    if _s(est.get("p")):
        rec["p"] = _s(est["p"])
        return rec, ""
    scale, se_of = _s(est.get("scale")) or "coefficient", _s(est.get("se_of"))
    if _s(est.get("se")) and _s(est.get("b")):
        if scale == "ratio":
            usable = False
        elif scale == "standardized":
            usable = se_of == "printed estimate"
        else:
            usable = se_of != "another number"
        if usable:
            rec["b"], rec["se"] = _s(est["b"]), _s(est["se"])
            return rec, ""
    if _s(est.get("t")):
        rec["t"] = _s(est["t"])
        return rec, ""
    if _s(est.get("se")) and scale == "ratio":
        return None, ("a ratio printed with an error only; its p comes from the log scale, so it needs a printed p, "
                      "z, or interval")
    if _s(est.get("se")) and scale == "standardized":
        return None, "a standardized estimate printed with an error that is not shown to belong to it"
    return None, "no p-value, usable standard error, or test statistic"


def _interval(test, need_two_sided, pv):
    """'rejects', 'does not reject', or (None, reason) for a printed interval at the two-sided level needed."""
    est = _est(test)
    ci = est.get("ci") if isinstance(est.get("ci"), list) else []
    if len(ci) != 2:
        return None, "no interval"
    lo, hi = _parse(pv, ci[0]), _parse(pv, ci[1])
    level_text = _s(est.get("ci_level")).rstrip("%").strip()
    try:
        conf = float(level_text)
    except ValueError:
        return None, "the interval's level is not stated"
    conf = conf / 100 if conf > 1 else conf
    if lo is None or hi is None or not 0 < conf < 1:
        return None, "the interval is not two plain numbers at a level between 0 and 100 percent"
    if lo[0] > hi[0]:
        return None, f"the interval [{ci[0]}, {ci[1]}] has its lower end above its upper end"
    null = 1.0 if _s(est.get("scale")) == "ratio" else 0.0
    alpha = 1 - conf
    contains = lo[0] + lo[1] < null and hi[0] - hi[1] > null
    excludes = lo[0] - lo[1] > null or hi[0] + hi[1] < null
    if contains:
        if alpha >= need_two_sided * (1 - TIE):
            return "does not reject", f"the {conf * 100:g} percent interval [{ci[0]}, {ci[1]}] contains {null:g}"
        return None, (f"the {conf * 100:g} percent interval contains {null:g}, but the verdict needs a "
                      f"{(1 - need_two_sided) * 100:g} percent interval")
    if excludes:
        if alpha <= need_two_sided * (1 + TIE):
            return "rejects", f"the {conf * 100:g} percent interval [{ci[0]}, {ci[1]}] excludes {null:g}"
        return None, f"the {conf * 100:g} percent interval excludes {null:g}, at a looser level than the verdict needs"
    return None, f"the interval [{ci[0]}, {ci[1]}] touches {null:g} within rounding"


def _note_text(test, tables):
    """The note of the table that holds a test's first cell, or None."""
    cells = test.get("cells") if isinstance(test.get("cells"), list) else []
    if tables is None or not cells or not isinstance(cells[0], str):
        return None
    name = cells[0].split(":", 1)[0]
    note = tables / (Path(name).stem + "_note.txt")
    try:
        return note.read_text(encoding="utf-8") if note.is_file() else None
    except (OSError, UnicodeDecodeError):
        return None


def _note(test, tables, va):
    """The parsed note of the table that holds a test's first cell, or None."""
    text = _note_text(test, tables)
    return va.parse_note(text) if text is not None else None


def _held(test, tables, va):
    """What the note says its parentheses and brackets hold ('se', 't', 'p', 'ambiguous'), in any wording. Read
    from the note's clauses directly, so a note with no key to the marks, or one that names marginal effects, odds
    ratios, bootstrap, or standardized coefficients, still counts. An empty set when the note does not say."""
    text = _note_text(test, tables)
    if text is None:
        return set()
    note = " ".join(text.replace("\u2212", "-").split())
    return {kind for clause in va._CLAUSE.split(note) for _, kind in va._clause_value_kinds(clause) if kind}


def _df(test, pv):
    """The degrees of freedom the paper prints for a linear model's t statistic, or None. A df recorded for any
    other family (a z, chi-square, or F test, or a model's residual or LR df) is ignored."""
    if test.get("model_family") != "linear":
        return None
    p = _parse(pv, _est(test).get("df"))
    return p[0] if p and p[0] > 0 and math.isfinite(p[0]) else None


def _t_readings(rec, df, pv):
    """The p intervals for a printed statistic under t(df), with the tails readings check_claim uses."""
    bounds = pv.abs_t_bounds(rec.get("b"), rec["se"]) if rec.get("se") else pv.abs_t_bounds_from_t(rec.get("t", ""))
    if bounds is None:
        return None
    two, one = pv.p_range(*bounds, df=df), pv.p_range(*bounds, df=df, one_tailed=True)
    dist = f"t({df:g})"
    if rec["tails"] == "one":
        return {f"one-tailed, as the paper states, {dist}": one}
    if rec["tails"] == "two" or not rec["directional"]:
        return {f"two-sided, {dist}": two}
    return {f"two-sided, {dist}": two, f"one-tailed, which the paper does not state, {dist}": one}


def _z_cut(level):
    """The two-sided normal critical value for a level."""
    from statistics import NormalDist
    return NormalDist().inv_cdf(1 - level / 2)


def _abs_z_low(rec, pv):
    bounds = pv.abs_t_bounds(rec.get("b"), rec["se"]) if rec.get("se") else pv.abs_t_bounds_from_t(rec.get("t", ""))
    return bounds[0] if bounds else None


def significance(test, level, directional, tails, tables, mods, strict=False, flag_on="fails"):
    """Whether a test meets 'p < level' under the paper's readings: ('fails' | 'passes' | None, detail).
    'fails' means every reading lies above the level; 'passes' means every reading lies below it. flag_on is the
    state that would raise the caller's flag. When the note does not say what the parentheses hold and reading
    them as a standard error gives flag_on while reading them as a t statistic does not, the test is not
    computable."""
    pv, va, _ = mods
    if _blank(test):
        return None, BLANK
    est = _est(test)
    if not _s(est.get("se")) or _s(est.get("t")):
        return _significance(test, level, directional, tails, tables, mods, strict)
    moved = dict(test, estimate=dict(est, t=est["se"], se=""))
    held = _held(test, tables, va)
    if held == {"se"}:
        return _significance(test, level, directional, tails, tables, mods, strict)
    if held == {"t"}:
        return _significance(moved, level, directional, tails, tables, mods, strict)
    as_se = _significance(test, level, directional, tails, tables, mods, strict)
    as_t = _significance(moved, level, directional, tails, tables, mods, strict)
    if as_se[0] != flag_on or as_t[0] == flag_on:
        return as_se
    inner = [d.replace(TAILS_STRADDLE, "the tail readings split at") for d in (as_se[1], as_t[1])]
    return None, (f"the table note does not say whether the parentheses hold standard errors or t statistics, and "
                  f"the readings disagree (as a standard error: {inner[0]}; as a t statistic: {inner[1]})")


def _significance(test, level, directional, tails, tables, mods, strict):
    """significance() for one reading of the parentheses. A statistic printed without a p is read under t(df)
    when the paper prints df, else under the normal, whose p is the smallest any df allows: enough to say a test
    fails, never (with strict, for a finding that needs the test to reject) that it rejects."""
    pv, va, _ = mods
    rec, why = _record(test, directional, tails, pv)
    if rec is not None:
        df = None if "p" in rec else _df(test, pv)
        if df is not None:
            values = _t_readings(rec, df, pv)
            if not values:
                return None, "the printed statistic is not a plain number"
        else:
            rec["claim"] = {"op": "<", "level": repr(level)}
            res = va.check_claim(rec)
            if res["status"] != "ok" or not res["values"]:
                return None, res["detail"] or "not computable"
            values = res["values"]
        shown = "; ".join(f"{k}: p {_p(v[0], level)} to {_p(v[1], level)}" for k, v in values.items())
        if all(v[0] > level * (1 + TIE) for v in values.values()):
            return "fails", shown
        if all(v[1] < level * (1 - TIE) for v in values.values()):
            if strict and "p" not in rec and df is None:
                return None, (f"{shown} under the normal; a statistic printed without a p or its degrees of freedom "
                              f"is not read as rejecting, since in a small sample the t distribution puts p higher")
            return "passes", shown
        states = [(k.startswith("one-tailed"), _state(v[0], v[1], level)) for k, v in values.items()]
        if _tails_split(states):
            return None, f"{shown}; {TAILS_STRADDLE} {level:g}"
        printed = _s(_est(test).get("p")) if "p" in rec else ""
        if printed.lstrip("pP= ").startswith(("<", "\u2264")):
            return None, f"{shown}; the printed bound {printed!r} does not settle p < {level:g}"
        return None, f"{shown}; the printed digits straddle {level:g}"
    need = level if tails == "two" or not directional else 2 * level
    state, detail = _interval(test, need, pv)
    if state == "does not reject":
        return "fails", detail
    if state == "rejects":
        return "passes", detail
    if detail != "no interval":
        return None, detail
    parsed = _note(test, tables, va)
    markers = (parsed["markers"] or None) if parsed else None
    if markers is None:
        return None, why + "; no interval, and no table note whose key to the marks can be read"
    marks = _s(_est(test).get("marks"))
    if marks and marks not in markers:
        return None, f"the mark {marks!r} is not in the note's key ({_key(markers)})"
    # The mark puts the starred p in [lo, hi): below its own level and at or above the next stricter one (no mark:
    # at or above the loosest). Every tails reading the paper allows is tried: two-sided marks on a one-tailed test
    # halve p, one-sided marks on a two-sided test double it. Marks are two-sided, one-sided, or (a silent note)
    # either. 'fails' needs every reading at or above the level, 'passes' every reading below it.
    hi = markers[marks] if marks else 1.0
    lo = max([v for v in markers.values() if v < hi * (1 - TIE)], default=0.0)
    star_sides = [side for side, ok in (("two", parsed["tails"] != "one"), ("one", parsed["tails"] != "two")) if ok]
    test_sides = [side for side, ok in (("one", directional and tails != "two"),
                                        ("two", not (directional and tails == "one"))) if ok]
    factor = {("two", "one"): 0.5, ("one", "two"): 2.0}
    readings = [(ss, ts, factor.get((ss, ts), 1.0)) for ss in star_sides for ts in test_sides]
    factors = [f for _, _, f in readings]
    if lo * min(factors) >= level * (1 - TIE):
        if not marks:
            return "fails", f"the estimate carries no significance mark (the note's key: {_key(markers)})"
        return "fails", f"the mark {marks!r} claims p < {hi:g} only (the note's key: {_key(markers)})"
    if marks and hi * max(factors) <= level * (1 + TIE):
        return "passes", f"the mark {marks!r} claims p < {hi:g}"
    shown = f"the mark {marks!r}" if marks else "no significance mark"
    states = {(ss, ts): _mark_state(lo * f, hi * f, level) for ss, ts, f in readings}
    if _tails_split([(ts == "one", st) for (_, ts), st in states.items()]):
        return None, (f"{TAILS_STRADDLE} {level:g}: {shown} meets it on a one-tailed reading of the test and not on "
                      f"the two-sided one (the note's key: {_key(markers)})")
    by_star = {ss: sorted(st for (s2, _), st in states.items() if s2 == ss) for ss in star_sides}
    if len(star_sides) == 2 and by_star["two"] != by_star["one"]:
        return None, (f"the table note does not say whether its marks are one- or two-sided, and {shown} meets "
                      f"{level:g} under one convention and not the other (the note's key: {_key(markers)})")
    span = "; ".join(f"[{_p(lo * f, level)}, {_p(hi * f, level)})" for f in sorted(set(factors)))
    return None, (f"{shown} puts p in {span}, a range that straddles {level:g} (the note's key: {_key(markers)})"
                  if marks else f"no significance mark puts p at or above {_p(lo * min(factors), level)}, a bound "
                  f"below {level:g} (the note's key: {_key(markers)})")


def _state(lo, hi, level):
    """'passes', 'fails', or 'mid' for a p interval [lo, hi] against 'p < level'."""
    if lo > level * (1 + TIE):
        return "fails"
    if hi < level * (1 - TIE):
        return "passes"
    return "mid"


def _mark_state(lo, hi, level):
    """_state for a mark's half-open interval [lo, hi): at or above the level fails, at or below it passes."""
    if lo >= level * (1 - TIE):
        return "fails"
    if hi <= level * (1 + TIE):
        return "passes"
    return "mid"


def _tails_split(states):
    """True when the verdict holds only on a one-tailed reading of the test: some reading passes, every passing
    reading is one-tailed, and every two-sided reading (at least one) fails outright."""
    two = [st for one, st in states if not one]
    return (any(st == "passes" for _, st in states) and all(one for one, st in states if st == "passes")
            and bool(two) and all(st == "fails" for st in two))


def _key(markers):
    return ", ".join(f"{m} p<{v:g}" for m, v in sorted(markers.items(), key=lambda kv: -kv[1]))


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------

def _focal(row, tests, gate):
    return [t for t in tests if gate.is_focal(row.get("type"), t.get("term_kind"))]


def _partial_blocked(row, tests):
    """For a partial verdict, the cited tests a check cannot read (a 'not negative' or 'not positive' sign) block it:
    the flag fires only when every cited test, focal or not, fails."""
    return row.get("verdict") == "partially supported" and len(tests) != len(_cites(row))


def check_hl3(ledger, row, tables, mods, out):
    pv, _, gate = mods
    if row.get("verdict") not in HL3_VERDICTS or row.get("type") == "null":
        return
    partial = row.get("verdict") == "partially supported"
    if partial:
        tests = [t for t in _cites(row) if t.get("expected_sign") not in ("not negative", "not positive")]
    else:
        tests = [t for t in _focal(row, _cites(row), gate)
                 if _verdict(row, t) in HL3_VERDICTS and t.get("expected_sign") not in ("not negative", "not positive")]
    if not tests:
        return
    reasons, unknown = [], []
    for t in tests:
        verdict = "partially supported" if partial else _verdict(row, t)
        level, source = _level(ledger, row, t, verdict, pv)
        if level is None:
            unknown.append((t, source))
            continue
        directional = t.get("expected_sign") in ("positive", "negative")
        state, detail = significance(t, level, directional, _tails(ledger, t), tables, mods)
        if state == "fails":
            reasons.append(f"{_where(t)} is called {verdict} at p < {level:g} ({source}), but {detail}")
        elif state is None:
            unknown.append((t, detail))
    if reasons and not unknown and len(reasons) == len(tests) and not _partial_blocked(row, tests):
        out.flag(row, "HL3", tests, reasons)
    for t, detail in unknown:
        out.not_computed(row, "HL3", [t], detail)


def check_hl5(ledger, row, tables, mods, out):
    pv, _, gate = mods
    if row.get("verdict") not in ("supported", "marginally supported", "partially supported"):
        return
    if row.get("type") == "interaction":
        return
    signed = ("positive", "negative", "not negative", "not positive")
    tests = [t for t in _focal(row, _cites(row), gate) if t.get("expected_sign") in signed]
    if not tests:
        return
    if row.get("verdict") == "partially supported":
        # Every cited test, focal or not, must go against the prediction; a test with no predicted sign blocks it.
        tests = _cites(row)
        if any(t.get("expected_sign") not in signed for t in tests):
            return
    reasons, unknown = [], []
    for t in tests:
        est, want = _est(t), t.get("expected_sign")
        ratio = _s(est.get("scale")) == "ratio"
        sign = gate.printed_sign(est.get("b"), ratio=ratio)
        if sign is None:
            unknown.append((t, f"the estimate {_s(est.get('b'))!r} has no sign as printed"))
            continue
        against = "against 1" if ratio else ""
        tail_note = "; the paper states one-tailed tests, and a one-tailed p for an estimate in the wrong direction does not support it" \
            if _tails(ledger, t) == "one" else ""
        if want in ("positive", "negative"):
            if sign != want:
                reasons.append(f"{_where(t)} is {sign}{(' ' + against) if against else ''} ({_s(est.get('b'))}), "
                               f"but the hypothesis predicts {want} on the model's scale{tail_note}")
            continue
        excluded = "negative" if want == "not negative" else "positive"
        if sign != excluded:
            continue
        level, source = _level(ledger, row, t, _verdict(row, t), pv)
        if level is None:
            unknown.append((t, source))
            continue
        state, detail = significance(t, level, False, "two", tables, mods, strict=True, flag_on="passes")
        if state == "passes":
            reasons.append(f"{_where(t)} is {sign} and significant ({detail}), but the hypothesis says "
                           f"the effect is {want}")
        elif state is None:
            unknown.append((t, detail))
    if reasons and not unknown and len(reasons) == len(tests):
        out.flag(row, "HL5", tests, reasons)
    for t, detail in unknown:
        out.not_computed(row, "HL5", [t], detail)


def check_hl7(ledger, row, tables, mods, out):
    pv, _, gate = mods
    if row.get("type") != "null" or row.get("verdict") not in ("supported", "not supported"):
        return
    focal = _focal(row, _tests(row), gate)
    tests = [t for t in focal if t.get("designated") == "yes"] or _focal(row, _cites(row), gate)
    if not tests:
        return
    states, unknown, details = [], [], []
    for t in tests:
        level, source = _level(ledger, row, t, "supported", pv)
        if level is None:
            unknown.append((t, source))
            continue
        flag_on = "fails" if row.get("verdict") == "not supported" else "passes"
        state, detail = significance(t, level, False, "two", tables, mods, strict=True, flag_on=flag_on)
        if state is None:
            unknown.append((t, detail))
            continue
        states.append(state)
        details.append(f"{_where(t)}: {detail}, two-sided, against {level:g}")
    for t, detail in unknown:
        out.not_computed(row, "HL7", [t], detail)
    if unknown or not states:
        return
    verdict = row.get("verdict")
    if verdict == "not supported" and all(s == "fails" for s in states):
        out.flag(row, "HL7", tests, [f"the null hypothesis is called not supported, but its test does not reject "
                                     f"it ({d})" for d in details])
    if verdict == "supported" and all(s == "passes" for s in states):
        out.flag(row, "HL7", tests, [f"the null hypothesis is called supported, but its test rejects it ({d})"
                                     for d in details])


def check_hl9(ledger, row, tables, mods, out):
    pv, _, gate = mods
    if row.get("type") != "interaction" or row.get("verdict") not in SUPPORTED:
        return
    tests, cited = _tests(row), _cites(row)
    products = [t for t in cited if t.get("term_kind") == "product term"]
    reasons, used = [], []
    if tests and all(t.get("model_includes_product") is False for t in tests):
        reasons.append("no model the row's tests come from includes the product term")
        used = tests
    cites_figure = any(t.get("term_kind") == "figure" for t in cited)
    if not products and not cites_figure and any(t.get("term_kind") == "product term" for t in tests):
        reasons.append("the verdict cites no product term although one is in the row's tests")
        used = used or cited
    if products:
        want, why = gate.product_sign(row)
        if want is None:
            out.not_computed(row, "HL9", products, why)
        else:
            signs = [(t, gate.printed_sign(_est(t).get("b"), ratio=_s(_est(t).get("scale")) == "ratio")) for t in products]
            if any(s is None for _, s in signs):
                out.not_computed(row, "HL9", [t for t, s in signs if s is None], "a product term has no sign as printed")
            elif all(s != want for _, s in signs):
                coded = "; the moderator is coded against the hypothesis's wording" if _s(row.get("moderator_note")) else ""
                for t, s in signs:
                    against = " against 1" if _s(_est(t).get("scale")) == "ratio" else ""
                    reasons.append(f"{_where(t)} is {s}{against} ({_s(_est(t).get('b'))}), but '{row.get('shape')}' with a "
                                   f"{row.get('base_sign')} base effect needs a {want} product term{coded}")
                used = used + [t for t in products if t not in used]
    if reasons:
        out.flag(row, "HL9", used or tests, reasons)


def check_hl15(ledger, row, tables, mods, out):
    pv, _, gate = mods
    if row.get("verdict") not in SUPPORTED:
        return
    cited_ids = [t.get("test_id") for t in _cites(row)]
    reasons, used, unknown = [], [], []
    if row.get("type") == "null":
        return
    focal = [t for t in _focal(row, _tests(row), gate) if t.get("expected_sign") not in ("not negative", "not positive")]
    candidates = [("designated", t) for t in focal if t.get("designated") == "yes" and t.get("test_id") not in cited_ids]
    scope = row.get("verdict_scope")
    if isinstance(scope, list):
        candidates += [("scope", t) for t in focal if t.get("test_id") in scope]
    for why, t in candidates:
        level, source = _level(ledger, row, t, _verdict(row, t), pv)
        if level is None:
            unknown.append((t, source))
            continue
        directional = t.get("expected_sign") in ("positive", "negative")
        state, detail = significance(t, level, directional, _tails(ledger, t), tables, mods)
        if state == "fails":
            used.append(t)
            if why == "designated":
                reasons.append(f"the paper names {_where(t)} as the test, and it fails p < {level:g} ({detail}); "
                               f"the verdict cites another test")
            else:
                reasons.append(f"the verdict of support covers {_where(t)}, which fails p < {level:g} ({detail})")
        elif state is None:
            unknown.append((t, detail))
    if reasons:
        out.flag(row, "HL15", used, reasons)
    for t, detail in unknown:
        out.not_computed(row, "HL15", [t], detail)


def hl8_facts(ledger, row, mods, out):
    pv, _, _ = mods
    if row.get("type") != "difference":
        return
    if any(t.get("term_kind") == "difference test" for t in _cites(row)):
        return
    subs = [t for t in _tests(row) if t.get("term_kind") == "subsample estimate"]
    if len(subs) != 2:
        if subs:
            out.not_computed(row, "HL8", subs, f"{len(subs)} subsample estimates; the facts need exactly two")
        return
    if row.get("independent") != "yes":
        out.not_computed(row, "HL8", subs, f"independent is '{row.get('independent')}'; the samples may share units")
        return
    a, b = _est(subs[0]), _est(subs[1])
    parsed = [_parse(pv, a.get("b")), _parse(pv, a.get("se")), _parse(pv, b.get("b")), _parse(pv, b.get("se"))]
    if any(p is None or not math.isfinite(p[0]) for p in parsed) or parsed[1][0] <= 0 or parsed[3][0] <= 0:
        out.not_computed(row, "HL8", subs, "each subsample needs a finite printed estimate and a positive standard "
                                           "error")
        return
    (ba, hba), (sa, hsa), (bb, hbb), (sb, hsb) = parsed
    d, hd = ba - bb, hba + hbb
    d_lo, d_hi = d - hd, d + hd
    abs_lo = 0.0 if d_lo <= 0 <= d_hi else min(abs(d_lo), abs(d_hi))
    abs_hi = max(abs(d_lo), abs(d_hi))
    se_lo = math.hypot(max(0.0, sa - hsa), max(0.0, sb - hsb))
    se_hi = math.hypot(sa + hsa, sb + hsb)
    if not all(math.isfinite(x) for x in (d_lo, d_hi, se_lo, se_hi)):
        out.not_computed(row, "HL8", subs, "the estimates are too large to difference as finite numbers")
        return
    z_lo = abs_lo / se_hi
    z_hi = abs_hi / se_lo if se_lo > 0 else math.inf
    p_lo, p_hi = pv.p_range(z_lo, z_hi)
    fact = {"id": _s(row.get("id")) or "?", "check": "HL8", "b_a": _s(a.get("b")), "se_a": _s(a.get("se")),
            "b_b": _s(b.get("b")), "se_b": _s(b.get("se")), "independent": True,
            "difference": [d_lo, d_hi], "se": [se_lo, se_hi], "abs_z": [z_lo, z_hi if math.isfinite(z_hi) else None],
            "p_two_sided": [p_lo, p_hi],
            "tests": [_s(subs[0].get("test_id")) or "?", _s(subs[1].get("test_id")) or "?"], "cells": _cells(subs)}
    out.facts.append(fact)


class Report:
    def __init__(self):
        self.flags, self.facts, self.unknown = [], [], []

    def flag(self, row, check, tests, reasons):
        rid = _s(row.get("id")) or "?"
        table = next((_s(t.get("table")) for t in tests if _s(t.get("table"))), "")
        self.flags.append({"id": rid, "check": check, "item": f"numbers:hyp:{rid}:{check}",
                           "page": _s(row.get("verdict_page")) or _s(row.get("page")), "table": table,
                           "cells": _cells(tests), "reasons": list(reasons)})

    def not_computed(self, row, check, tests, detail):
        self.unknown.append({"id": _s(row.get("id")) or "?", "check": check,
                             "tests": [_s(t.get("test_id")) or "?" for t in tests], "detail": detail,
                             "cells": _cells(tests)})


CHECKS = (check_hl3, check_hl5, check_hl7, check_hl9, check_hl15)


def run(ledger, tables, mods):
    out = Report()
    rows = ledger.get("hypotheses") if isinstance(ledger.get("hypotheses"), list) else []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            out.unknown.append({"id": f"<index {i}>", "check": "-", "tests": [], "detail": "row is not an object",
                                "cells": []})
            continue
        for check in CHECKS:
            check(ledger, row, tables, mods, out)
        hl8_facts(ledger, row, mods, out)
    return out


PLAIN = re.compile(r"[-+]?(\d+\.?\d*|\.\d+)", re.ASCII)


def _too_long(ledger):
    """The first estimate printed as a number too long to read as a finite value, as '<row>, <test>', or ''."""
    rows = ledger.get("hypotheses") if isinstance(ledger.get("hypotheses"), list) else []
    for row in rows:
        if not isinstance(row, dict):
            continue
        for t in _tests(row):
            est = _est(t)
            ci = est.get("ci") if isinstance(est.get("ci"), list) else []
            for v in [est.get(k) for k in ("b", "se", "t", "p")] + ci:
                s = _s(v).replace("\u2212", "-").replace(",", "").lstrip("pP<>= ")
                if PLAIN.fullmatch(s) and not math.isfinite(float(s)):
                    return f"{_s(row.get('id')) or '?'}, {_s(t.get('test_id')) or '?'}"
    return ""


def _z(x):
    return "unbounded" if x is None else f"{x:.3f}"


def render(out, n_rows):
    lines = ["# Hypothesis checks", "", f"Rows read: {n_rows}. Flags: {len(out.flags)}.", "", "## Flags", ""]
    if not out.flags:
        lines.append("None.")
    for n, f in enumerate(out.flags, 1):
        page = f" (p. {f['page']})" if f["page"] else ""
        lines.append(f"{n}. {f['id']}: {'; '.join(f['reasons'])}.{page} Check: {f['check']}. [paper] "
                     f"Hypothesis: {f['id']}. Item: {f['item']}. Table: {f['table'] or 'none'}. "
                     f"Cells: {', '.join(f['cells']) or 'none'}.")
    lines += ["", "## Facts", ""]
    if not out.facts:
        lines.append("None.")
    for f in out.facts:
        lines.append(f"- {f['id']} (HL8, never a flag): b_a {f['b_a']} (se_a {f['se_a']}), b_b {f['b_b']} "
                     f"(se_b {f['se_b']}), independent: difference {f['difference'][0]:.3f} to "
                     f"{f['difference'][1]:.3f}, standard error {f['se'][0]:.4f} to {f['se'][1]:.4f}, |z| "
                     f"{f['abs_z'][0]:.3f} to {_z(f['abs_z'][1])}, two-sided p {_p(f['p_two_sided'][0])} to "
                     f"{_p(f['p_two_sided'][1])}. Cells: {', '.join(f['cells'])}.")
    lines += ["", "## Not computed", ""]
    if not out.unknown:
        lines.append("None.")
    for u in out.unknown:
        tests = f" ({', '.join(str(t) for t in u['tests'])})" if u["tests"] else ""
        lines.append(f"- {u['id']} {u['check']}{tests}: {u['detail']}. Cells: {', '.join(u['cells']) or 'none'}.")
    return "\n".join(lines) + "\n"


def main(argv):
    mods, why = _imports()
    if mods is None:
        print(f"check_hypotheses.py: cannot import the p-value routines: {why}", file=sys.stderr)
        return 2
    opts, positional, i = {}, [], 0
    while i < len(argv):
        if argv[i] in ("--json", "--tables"):
            if i + 1 >= len(argv):
                print(USAGE, file=sys.stderr)
                return 2
            opts[argv[i]] = argv[i + 1]
            i += 2
        else:
            positional.append(argv[i])
            i += 1
    if len(positional) != 2 or "--json" not in opts:
        print(USAGE, file=sys.stderr)
        return 2
    ledger_path = Path(positional[0])
    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError, RecursionError) as exc:
        print(f"check_hypotheses.py: ledger not readable as JSON: {exc}", file=sys.stderr)
        return 2
    if not isinstance(ledger, dict):
        print("check_hypotheses.py: the ledger must be a JSON object", file=sys.stderr)
        return 2
    bad = _too_long(ledger)
    if bad:
        print(f"check_hypotheses.py: the ledger prints a number too long to read as a finite value ({bad})",
              file=sys.stderr)
        return 2
    tables = Path(opts["--tables"]) if "--tables" in opts else ledger_path.resolve().parent.parent / "extracted_tables"
    out = run(ledger, tables if tables.is_dir() else None, mods)
    rows = ledger.get("hypotheses") if isinstance(ledger.get("hypotheses"), list) else []
    md, js = Path(positional[1]), Path(opts["--json"])
    md.parent.mkdir(parents=True, exist_ok=True)
    js.parent.mkdir(parents=True, exist_ok=True)
    try:
        payload = json.dumps({"flags": out.flags, "facts": out.facts, "not_computed": out.unknown}, indent=2,
                             allow_nan=False)
    except ValueError as exc:
        print(f"check_hypotheses.py: a value in the ledger is too long to read as a finite number: {exc}",
              file=sys.stderr)
        return 2
    md.write_text(render(out, len(rows)), encoding="utf-8")
    js.write_text(payload + "\n", encoding="utf-8")
    print(f"HYPOTHESIS_CHECKS: {len(out.flags)} flags, {len(rows)} rows, {len(out.unknown)} not computed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
