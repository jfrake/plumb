#!/usr/bin/env python3
"""Run-to-run noise for comparisons between simulated conditions.

Usage: run_noise.py <comparisons.json>

Reads a JSON list of comparison records, one per difference between two simulated
conditions that the paper describes, and prints one JSON object to stdout. Writes no
files. Exit 0 on success; exit 2 on unreadable input or a bad record, with the message
on stderr. Standard library only.

Each computed or independence_unstated result carries inside_noise_if_independent, which is not a flag:
true when the claim is not "none" and z_max is below 1.645 (the lenient test behind inside_noise, applied
without requiring the paper to state independent draws), false otherwise, and null when z_max is null.
"""
from __future__ import annotations

import json
import math
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "skills" / "review" / "scripts"))
import pvalues  # noqa: E402

Z = 1.96
Z_ONE = 1.645
ASSUMPTIONS = ("Runs are independent across the two conditions (no shared landscapes or seeds), and the "
               "difference of the two means is approximately normal. The standard error of the difference "
               "is sqrt(sd_a^2 / runs_a + sd_b^2 / runs_b). The interval, z, and excludes_zero use the printed "
               "values and a two-sided 95 percent level. The flag inside_noise is set only when no rounding of "
               "the printed means and spreads gives |z| of 1.645 or more (the one-sided 5 percent level, the "
               "lenient reading of a directional claim whose test the paper does not state). The field "
               "inside_noise_if_independent applies the same test whether or not the paper states independent "
               "draws; it is not a flag. When conditions share draws, the independent-draws interval is an upper "
               "bound on the noise, so a difference outside it exceeds the noise either way.")
TOP = ("id", "label", "page", "location", "outcome", "a", "b", "spread_of", "claim", "common_random_numbers")
ARM = ("mean", "spread", "spread_kind", "runs")
SPREAD_KINDS = ("sd", "se", "ci95_halfwidth")
SPREAD_OF = ("runs", "agents", "unclear")
CLAIMS = ("meaningful", "significant", "none")
CRN = ("yes", "no", "unclear")
# Runs below this count are flagged as few: a pragmatic bound set by this pack, not a published threshold.
SMALL_RUNS = 30
# A runs_for_p05 above this is not stated: a pragmatic bound set by this pack, not a published threshold.
MAX_RUNS_STATED = 1e15


class InputError(Exception):
    pass


def _is_number(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _printed(x):
    """A value as the paper prints it: (value, half a unit of its last printed digit), or None.

    A string keeps its printed digits ("0.060"); a JSON number is read from its shortest form, which can
    only drop trailing zeros and so gives a wider rounding interval, never a narrower one."""
    if isinstance(x, bool) or not isinstance(x, (int, float, str)):
        return None
    if isinstance(x, str) and "_" in x:
        return None
    try:
        d = Decimal(x.strip() if isinstance(x, str) else repr(x))
        value, half = float(d), 0.5 * 10.0 ** d.as_tuple().exponent
    except (InvalidOperation, OverflowError, TypeError, ValueError):
        return None
    if not (d.is_finite() and math.isfinite(value) and math.isfinite(half)):
        return None
    return value, half


def validate(rec) -> None:
    """Raise InputError naming the record and field when a record is malformed."""
    if not isinstance(rec, dict):
        raise InputError(f"each record must be a JSON object, not {rec!r}")
    rid = rec.get("id", "?")
    for k in TOP:
        if k not in rec:
            raise InputError(f"record {rid}: missing field '{k}'")
    for k in ("id", "label", "page", "location", "outcome"):
        if isinstance(rec[k], float) and not math.isfinite(rec[k]):
            raise InputError(f"record {rid}: '{k}' must not be NaN or infinite")
    for arm in ("a", "b"):
        side = rec[arm]
        if not isinstance(side, dict):
            raise InputError(f"record {rid}: '{arm}' must be an object with {', '.join(ARM)}")
        for k in ARM:
            if k not in side:
                raise InputError(f"record {rid}: missing field '{arm}.{k}'")
        if _printed(side["mean"]) is None:
            raise InputError(f"record {rid}: '{arm}.mean' must be a number, or the number as printed")
        spread = _printed(side["spread"])
        if spread is None or spread[0] < 0:
            raise InputError(f"record {rid}: '{arm}.spread' must be a number that is not negative, "
                             "or that number as printed")
        if side["spread_kind"] not in SPREAD_KINDS:
            raise InputError(f"record {rid}: '{arm}.spread_kind' must be one of {', '.join(SPREAD_KINDS)}")
        runs = side["runs"]
        if not isinstance(runs, int) or isinstance(runs, bool) or runs < 1:
            raise InputError(f"record {rid}: '{arm}.runs' must be a whole number of at least 1")
    for k, allowed in (("spread_of", SPREAD_OF), ("claim", CLAIMS), ("common_random_numbers", CRN)):
        if rec[k] not in allowed:
            raise InputError(f"record {rid}: '{k}' must be one of {', '.join(allowed)}")


def t_crit(runs: int) -> float:
    """The two-sided 95 percent Student t critical value with runs - 1 degrees of freedom, by bisection
    on pvalues.p_student. Falls back to the normal value for a single run."""
    if runs < 2:
        return Z
    lo, hi = 1.0, 1000.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if pvalues.p_student(mid, runs - 1) > 0.05:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def arm_sd(side: dict, spread=None, crit: float = Z) -> float:
    """The standard deviation across runs implied by the reported spread (or by `spread`, when given).
    `crit` is the critical value a ci95_halfwidth spread is divided by."""
    kind, runs = side["spread_kind"], side["runs"]
    spread = _printed(side["spread"])[0] if spread is None else spread
    if kind == "sd":
        return spread
    if kind == "se":
        return spread * math.sqrt(runs)
    return (spread / crit) * math.sqrt(runs)


def run_record(rec: dict) -> dict:
    validate(rec)
    out = {k: rec[k] for k in ("id", "label", "page", "location", "outcome")}
    if rec["spread_of"] != "runs":
        where = "across agents within a run" if rec["spread_of"] == "agents" else "not stated as across runs"
        out.update(status="not_computable", flag=None,
                   reason=f"the reported spread is {where}, so it does not measure run-to-run noise")
        return out
    if rec["common_random_numbers"] == "yes":
        out.update(status="not_computable", flag=None,
                   reason=("the conditions share landscapes or seeds; the paired standard error of the "
                           "difference cannot be recovered from the spread of each condition"))
        return out
    (mean_a, half_a), (mean_b, half_b) = _printed(rec["a"]["mean"]), _printed(rec["b"]["mean"])
    (spread_a, sp_half_a), (spread_b, sp_half_b) = _printed(rec["a"]["spread"]), _printed(rec["b"]["spread"])
    n_a, n_b = rec["a"]["runs"], rec["b"]["runs"]
    too_large = InputError(f"record {rec['id']}: the numbers are too large to compute; check 'a' and 'b'")
    try:
        sd_a, sd_b = arm_sd(rec["a"]), arm_sd(rec["b"])
        diff = mean_a - mean_b
        se = math.sqrt(sd_a ** 2 / n_a + sd_b ** 2 / n_b)
        if se == 0:
            out.update(status="not_computable", flag=None, reason="both conditions report zero spread")
            return out
        z = diff / se
        # Smallest SD either convention allows: a half-width may have used t, which is at least 1.96.
        low_a = arm_sd(rec["a"], max(spread_a - sp_half_a, 0.0), t_crit(n_a))
        low_b = arm_sd(rec["b"], max(spread_b - sp_half_b, 0.0), t_crit(n_b))
        se_min = math.sqrt(low_a ** 2 / n_a + low_b ** 2 / n_b)
        z_max = None if se_min == 0 else (abs(diff) + half_a + half_b) / se_min
        pooled = math.sqrt((sd_a ** 2 + sd_b ** 2) / 2)
    except (OverflowError, ZeroDivisionError):
        raise too_large
    if not all(math.isfinite(v) for v in (sd_a, sd_b, diff, se, z) + ((z_max,) if z_max is not None else ())):
        raise too_large
    try:
        q = None if diff == 0 else Z ** 2 * (sd_a ** 2 + sd_b ** 2) / diff ** 2
    except (OverflowError, ZeroDivisionError):
        q = None
    unstatable = diff != 0 and (q is None or not math.isfinite(q) or q > MAX_RUNS_STATED)
    runs_for_p05 = None if (q is None or unstatable) else math.ceil(round(q, 9))
    excludes_zero = abs(z) >= Z
    small = min(n_a, n_b) < SMALL_RUNS
    stated = rec["common_random_numbers"] == "no"
    lenient = None if z_max is None else (rec["claim"] != "none" and z_max < Z_ONE)
    out.update(
        status="computed" if stated else "independence_unstated",
        sd_a=sd_a, sd_b=sd_b, diff=diff, se_diff=se, ci95=[diff - Z * se, diff + Z * se], z=z, z_max=z_max,
        excludes_zero=excludes_zero,
        standardized=diff / pooled if pooled > 0 else None,
        runs_for_p05=runs_for_p05,
        small_runs=small,
        note="; ".join(x for x in (
            ("fewer than 30 runs in a condition (a rule of thumb set by this pack, not a published "
             "threshold); the normal approximation understates the interval") if small else None,
            ("more runs than can be stated (a pragmatic bound of 1e15 set by this pack)")
            if unstatable else None) if x) or None,
        flag="inside_noise" if (stated and lenient) else None,
        inside_noise_if_independent=lenient,
    )
    return out


def main(argv: list) -> int:
    if len(argv) != 2:
        print("Usage: run_noise.py <comparisons.json>", file=sys.stderr)
        return 2
    try:
        records = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"cannot read {argv[1]}: {exc}", file=sys.stderr)
        return 2
    if not isinstance(records, list):
        print("the input must be a JSON list of records", file=sys.stderr)
        return 2
    try:
        results = [run_record(r) for r in records]
    except InputError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps({"assumptions": ASSUMPTIONS, "results": results}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
