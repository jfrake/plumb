#!/usr/bin/env python3
"""Check descriptive network numbers against the counts they come from.

Usage: python3 check_network_numbers.py <input.json>

The network pack's verify agent writes the input: a JSON list of records, each with
id, kind, page, and location, and reported values as strings exactly as printed.
The script prints {"assumptions": [...], "results": [...]} as JSON and writes no file.
Exit 0 on success; exit 2 on unreadable input, an unknown kind, or a missing field.
Counts above 10**12 are reported as input_error; that limit is a pragmatic bound set by this pack.
"""
from __future__ import annotations

import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

COMMON = ("id", "kind", "page", "location")
KINDS = {
    "summary": ("same_network", "actors", "ties", "directed"),
    "dyads": ("actors", "periods", "reported_dyads", "sampling"),
    "response": ("actors", "respondents", "directed"),
    "range": ("measure", "value"),
}
SAMPLING = ("full", "sampled", "unclear")
RANGE_MEASURES = ("density", "clustering")
DEGREE_KINDS = ("total", "in", "out", "unstated")
MAX_COUNT = 10**12
ASSUMPTIONS = [
    "summary: a simple graph (no self-ties, at most one tie per pair, or per direction when directed, "
    "each tie counted once); checked only when the paper states the counts and the statistic for the same network",
    "dyads: the largest possible count is periods x n x n2 when pairs join two sets, periods x n(n-1)/2 when "
    "the paper states that each unordered pair appears once, and periods x n(n-1) otherwise",
    "response: shares of pairs by who responded; no rule for coding a tie from one report is assumed",
    "tolerance: a printed value with d decimals agrees with a computed value c when |c - r| <= 0.5 x 10^-d; "
    "a comma in a printed value is an input error",
    "mean degree: when the paper does not say whether a directed mean degree counts in, out, or total ties, "
    "either reading is accepted",
]


class InvalidRecord(Exception):
    """The input cannot be read at all: exit 2."""


class InputError(Exception):
    """One value in an otherwise complete record cannot be used: that record is reported as input_error."""


def printed(value):
    """Read a value as printed ('0.12', '5.00', '12%'). Return (number, decimals shown)."""
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise InputError(f"cannot read the printed value {value!r}")
    text = str(value).strip()
    percent = text.endswith("%")
    if percent:
        text = text[:-1].strip()
    if "," in text:
        raise InputError(f"cannot read the printed value {value!r}; a comma is not read in a printed statistic")
    try:
        number = Decimal(text)
    except InvalidOperation:
        raise InputError(f"cannot read the printed value {value!r}") from None
    if not number.is_finite():
        raise InputError(f"cannot read the printed value {value!r}")
    decimals = max(0, -number.as_tuple().exponent)
    result = float(number)
    if result in (float("inf"), float("-inf")):
        raise InputError(f"the printed value {value!r} is too large to read")
    if percent:
        result /= 100.0
        decimals += 2
    return result, decimals


def agrees(computed: float, value) -> bool:
    number, decimals = printed(value)
    return abs(computed - number) <= 0.5 * 10 ** (-decimals) + 1e-12


def whole(rec: dict, key: str, minimum: int) -> int:
    v = rec[key]
    if isinstance(v, bool) or not isinstance(v, int) or v < minimum:
        raise InputError(f"'{key}' must be a whole number of at least {minimum}, not {v!r}")
    if v > MAX_COUNT:
        raise InputError(f"'{key}' is larger than {MAX_COUNT}, a pragmatic bound set by this pack")
    return v


def yes_no(rec: dict, key: str, default=None) -> bool:
    v = rec.get(key, default)
    if not isinstance(v, bool):
        raise InputError(f"'{key}' must be true or false, not {v!r}")
    return v


def result(rec, quantity, status="computed", computed=None, reported=None, flag=None, note=""):
    return {"id": rec["id"], "kind": rec["kind"], "page": rec["page"], "location": rec["location"],
            "quantity": quantity, "status": status, "computed": computed, "reported": reported,
            "flag": flag, "note": note}


def summary(rec: dict) -> list:
    if not yes_no(rec, "same_network"):
        return [result(rec, "summary", status="not_checked",
                       note="different_networks: the paper does not state the counts and the statistic for one network")]
    n = whole(rec, "actors", 2)
    ties = whole(rec, "ties", 0)
    directed = yes_no(rec, "directed")
    pairs = n * (n - 1) if directed else n * (n - 1) // 2
    out = []
    density = ties / pairs
    if density > 1:
        out.append(result(rec, "density", computed=density, reported=None if rec.get("density") is None else str(rec["density"]),
                          flag="density_out_of_range", note=f"{ties} ties exceed the {pairs} possible pairs"))
    elif rec.get("density") is not None:
        ok = agrees(density, rec["density"])
        out.append(result(rec, "density", computed=density, reported=rec["density"],
                          flag=None if ok else "density_mismatch", note=f"{ties} ties / {pairs} possible pairs"))
    if rec.get("mean_degree") is not None:
        kind = rec.get("degree_kind")
        if directed and kind not in DEGREE_KINDS:
            raise InputError("directed data need degree_kind total, in, out, or unstated")
        if not directed and kind not in (None, "total"):
            raise InputError("undirected data have only total degree")
        if kind == "unstated":
            options = [(ties / n, f"in or out degree: {ties} ties / {n} actors"),
                       (2 * ties / n, f"total degree: 2 x {ties} ties / {n} actors")]
            fits = [o for o in options if agrees(o[0], rec["mean_degree"])]
            mean, basis = fits[0] if fits else options[0]
            ok = bool(fits)
            note = basis + "; the paper does not say which degree, so either reading is accepted"
        else:
            mean = ties / n if kind in ("in", "out") else 2 * ties / n
            ok = agrees(mean, rec["mean_degree"])
            note = f"{'1' if kind in ('in', 'out') else '2'} x {ties} ties / {n} actors"
        out.append(result(rec, "mean_degree", computed=mean, reported=rec["mean_degree"],
                          flag=None if ok else "mean_degree_mismatch", note=note))
    if not out:
        out.append(result(rec, "summary", status="not_checked", note="no density or mean degree given"))
    return out


def dyads(rec: dict) -> list:
    n = whole(rec, "actors", 2)
    periods = whole(rec, "periods", 1)
    reported = whole(rec, "reported_dyads", 0)
    sampling = rec["sampling"]
    if sampling not in SAMPLING:
        raise InputError(f"'sampling' must be one of {', '.join(SAMPLING)}, not {sampling!r}")
    each_once = yes_no(rec, "each_pair_once", False)
    if rec.get("actors_other_side") is not None:
        n2 = whole(rec, "actors_other_side", 1)
        maximum, basis = periods * n * n2, f"{periods} x {n} x {n2}"
    elif each_once:
        maximum, basis = periods * n * (n - 1) // 2, f"{periods} x {n} x {n - 1} / 2"
    else:
        maximum, basis = periods * n * (n - 1), f"{periods} x {n} x {n - 1}"
    out = [result(rec, "dyads", computed=maximum, reported=reported,
                  flag="dyads_exceed_risk_set" if reported > maximum else None,
                  note=f"largest possible count {basis} = {maximum}")]
    if sampling == "sampled":
        total = whole(rec, "ties", 0) + whole(rec, "sampled_nonties", 0)
        if reported > total:
            flag, note = "sampled_count_exceeded", f"the model's N exceeds ties plus sampled non-ties ({total})"
        elif reported < total:
            flag, note = None, f"the model's N is {total - reported} below ties plus sampled non-ties ({total})"
        else:
            flag, note = None, f"ties plus sampled non-ties = {total}"
        out.append(result(rec, "sampled_count", computed=total, reported=reported, flag=flag, note=note))
    return out


def response(rec: dict) -> list:
    n = whole(rec, "actors", 2)
    m = whole(rec, "respondents", 0)
    directed = yes_no(rec, "directed")
    if m > n:
        return [result(rec, "response", reported=m, flag="respondents_exceed_actors",
                       note=f"{m} respondents but {n} actors")]
    pairs = n * (n - 1) // 2
    both = m * (m - 1) // 2
    neither = (n - m) * (n - m - 1) // 2
    computed = {"pairs": pairs, "both_pairs": both, "both_share": both / pairs,
                "any_pairs": pairs - neither, "any_share": (pairs - neither) / pairs}
    if directed:
        computed.update({"ordered_pairs": n * (n - 1), "sender_pairs": m * (n - 1), "sender_share": m / n})
    return [result(rec, "response", computed=computed, reported=m,
                   note="pairs with one respondent are only partly observed under any coding rule")]


def value_range(rec: dict) -> list:
    measure = rec["measure"]
    if measure not in RANGE_MEASURES:
        raise InputError(f"'measure' must be one of {', '.join(RANGE_MEASURES)}, not {measure!r}")
    number, _ = printed(rec["value"])
    bad = number < 0 or number > 1
    return [result(rec, measure, computed=number, reported=rec["value"],
                   flag="out_of_range" if bad else None, note="must lie between 0 and 1")]


HANDLERS = {"summary": summary, "dyads": dyads, "response": response, "range": value_range}


def validate(rec) -> None:
    if not isinstance(rec, dict):
        raise InvalidRecord(f"each record must be an object, not {rec!r}")
    for key in COMMON:
        if key not in rec:
            raise InvalidRecord(f"record {rec.get('id')!r} is missing '{key}'")
    if not isinstance(rec["kind"], str) or rec["kind"] not in KINDS:
        raise InvalidRecord(f"record {rec['id']!r} has unknown kind {rec['kind']!r}; kinds are {', '.join(KINDS)}")
    need = list(KINDS[rec["kind"]])
    if rec["kind"] == "dyads" and rec.get("sampling") == "sampled":
        need += ["ties", "sampled_nonties"]
    for key in need:
        if key not in rec:
            raise InvalidRecord(f"record {rec['id']!r} ({rec['kind']}) is missing '{key}'")


def run(records: list) -> dict:
    for rec in records:
        validate(rec)
    results = []
    for rec in records:
        try:
            results.extend(HANDLERS[rec["kind"]](rec))
        except InputError as exc:
            results.append(result(rec, rec["kind"], status="input_error", note=str(exc)))
    return {"assumptions": ASSUMPTIONS, "results": results}


def main(argv: list) -> int:
    if len(argv) != 2:
        print("usage: check_network_numbers.py <input.json>", file=sys.stderr)
        return 2
    try:
        records = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"cannot read {argv[1]} as JSON: {exc}", file=sys.stderr)
        return 2
    if not isinstance(records, list):
        print("the input must be a JSON list of records", file=sys.stderr)
        return 2
    try:
        out = run(records)
    except InvalidRecord as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
