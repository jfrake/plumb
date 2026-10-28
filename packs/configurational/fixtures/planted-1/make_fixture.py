#!/usr/bin/env python3
"""Seeded data for the planted-1 fixture. SYNTHETIC TEST PAPER, NOT REAL RESEARCH.

The 180 manufacturing firms, their records, the industry, and the Northfield Manufacturers'
Council are fictional. Usage: python3 make_fixture.py --out DIR. Writes DIR/memberships.csv and
DIR/script_inputs.json and nothing else. Standard library only.

Seed: SEED = 20260930 (random.Random). If a draw puts any fuzzy score other than the planted
alliance scores in [0.495, 0.505), or the two middle firms tie on ROA or size, the whole sample is
drawn again from the same generator, so the result is fixed by the seed.

Calibration: direct method. For raw value x with full-membership anchor f, crossover c, and
full-non-membership anchor n, the log odds are 3(x - c)/(f - c) when x >= c and -3(c - x)/(c - n)
when x < c; membership is exp(lo)/(1 + exp(lo)), computed in Decimal and written at six decimals,
half-up. Sample percentiles are nearest-rank: the 95th is the 171st of 180 firms in ascending
order, the 5th is the 9th, and the median is midway between the 90th and 91st (never a firm's own
value).

Anchors as the paper states them (Table 1 and the calibration section):
  HighROA      ROA; sample 95th percentile, median, 5th percentile (no reason given: plant P2)
  BoardIndep   share of independent directors; 0.80, 0.50, 0.20
  CEODuality   crisp; 1 when the CEO chairs the board, else 0
  RDIntensity  R&D spending over sales; 0.060, 0.025, 0.005
  FirmSize     log of employees; sample 95th percentile, median, 5th percentile (decoy D1)
  Alliances    count of active alliances; 6, 3, 1 (3 is the sample median; exactly 18 firms
               have 3 alliances and sit at 0.5: plant P3)
  OwnerConc    largest owner's share; 0.50, 0.25, 0.05 (used here; the paper's Table 1 leaves
               them out and the text says only "calibrated similarly": plant P1)

Fit figures: computed with fractions.Fraction from the six-decimal scores by the formulas of the
pack's spec (consistency, PRI, raw and unique coverage, solution consistency and coverage) and
printed at two decimals, rounding half-up.

Plant applied after computing: P5, configuration 2 of the presence solution prints PRI "0.86"
(its true PRI is at most 0.78). Nothing else is changed.
"""
from __future__ import annotations

import argparse
import json
import math
import random
from decimal import ROUND_HALF_UP, Decimal, getcontext
from fractions import Fraction
from pathlib import Path

SEED = 20260930
N = 180
LABEL = "SYNTHETIC TEST PAPER, NOT REAL RESEARCH"
SETS = ["HighROA", "BoardIndep", "CEODuality", "RDIntensity", "FirmSize", "Alliances", "OwnerConc"]
FIXED_ANCHORS = {
    "BoardIndep": (Decimal("0.80"), Decimal("0.50"), Decimal("0.20")),
    "RDIntensity": (Decimal("0.060"), Decimal("0.025"), Decimal("0.005")),
    "Alliances": (Decimal(6), Decimal(3), Decimal(1)),
    "OwnerConc": (Decimal("0.50"), Decimal("0.25"), Decimal("0.05")),
}
PRESENCE = ["BoardIndep*RDIntensity*~CEODuality", "BoardIndep*CEODuality*~OwnerConc", "BoardIndep*FirmSize*Alliances"]
ABSENCE = ["~BoardIndep*CEODuality*~RDIntensity", "~BoardIndep*~RDIntensity*~Alliances"]
PLANT_P5 = (1, "0.86")
SOURCE_TABLE3 = "Table 3, p. 10"
SOURCE_TABLEA1 = "Table A1, p. 12"
SOURCE_DESIGN = "Analysis and Results, pp. 8 and 9"
CUTOFF = "0.80"

getcontext().prec = 40


# --- draw the raw records ------------------------------------------------------------------

def _clip(v: float, lo: float, hi: float) -> float:
    return min(hi, max(lo, v))


def _alliance_counts(latent: list) -> list:
    order = sorted(range(N), key=lambda i: (latent[i], i))
    bands = [(15, 0), (30, 1), (37, 2), (18, 3), (30, 4), (20, 5), (15, 6), (10, 7), (5, 8)]
    counts = [0] * N
    pos = 0
    for size, value in bands:
        for i in order[pos:pos + size]:
            counts[i] = value
        pos += size
    return counts


def _draw(rng: random.Random) -> dict:
    z = {k: [rng.gauss(0, 1) for _ in range(N)] for k in ("bi", "rd", "al", "sz", "oc", "e")}
    dual = [1 if rng.random() < 0.40 else 0 for _ in range(N)]
    bi = [Decimal(f"{_clip(0.52 + 0.17 * v, 0.05, 0.95):.3f}") for v in z["bi"]]
    rd = [Decimal(f"{_clip(math.exp(math.log(0.022) + 0.75 * v), 0.0010, 0.1500):.4f}") for v in z["rd"]]
    sz = [Decimal(f"{6.4 + 1.1 * v:.3f}") for v in z["sz"]]
    oc = [Decimal(f"{_clip(0.27 + 0.13 * v, 0.03, 0.90):.3f}") for v in z["oc"]]
    al = _alliance_counts(z["al"])
    roa = []
    for i in range(N):
        b, r, a, s = z["bi"][i], z["rd"][i], z["al"][i], z["sz"][i]
        core = min(b, max(r, min(a, s)))
        v = 0.035 + 0.030 * core + 0.010 * b - 0.006 * dual[i] + 0.022 * z["e"][i]
        roa.append(Decimal(f"{v:.4f}"))
    return {"HighROA": roa, "BoardIndep": bi, "CEODuality": dual, "RDIntensity": rd, "FirmSize": sz,
            "Alliances": [Decimal(a) for a in al], "OwnerConc": oc}


def _percentile_anchors(values: list):
    s = sorted(values)
    if s[89] == s[90]:
        return None
    return s[170], (s[89] + s[90]) / 2, s[8]


def _calibrate(x: Decimal, f: Decimal, c: Decimal, n: Decimal) -> Decimal:
    lo = 3 * (x - c) / (f - c) if x >= c else -3 * (c - x) / (c - n)
    m = lo.exp() / (1 + lo.exp())
    return m.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def build() -> tuple:
    rng = random.Random(SEED)
    while True:
        raw = _draw(rng)
        anchors = dict(FIXED_ANCHORS)
        roa_a = _percentile_anchors(raw["HighROA"])
        sz_a = _percentile_anchors(raw["FirmSize"])
        if roa_a is None or sz_a is None:
            continue
        anchors["HighROA"], anchors["FirmSize"] = roa_a, sz_a
        mem = {"CEODuality": raw["CEODuality"]}
        ok = True
        for s in SETS:
            if s == "CEODuality":
                continue
            col = [_calibrate(x, *anchors[s]) for x in raw[s]]
            for x, m in zip(raw[s], col):
                planted = s == "Alliances" and x == 3
                if Decimal("0.495") <= m < Decimal("0.505") and not planted:
                    ok = False
            mem[s] = col
        if ok:
            return raw, anchors, mem


# --- fit figures ---------------------------------------------------------------------------

def _fr(v) -> Fraction:
    return Fraction(v) if isinstance(v, int) else Fraction(v)


def _term_x(label: str, mem: dict) -> list:
    out = []
    for i in range(N):
        vals = []
        for part in label.split("*"):
            neg = part.startswith("~")
            v = _fr(mem[part.lstrip("~")][i])
            vals.append(1 - v if neg else v)
        out.append(min(vals))
    return out


def _cons(x, y):
    return sum(min(a, b) for a, b in zip(x, y)) / sum(x)


def _cov(x, y):
    return sum(min(a, b) for a, b in zip(x, y)) / sum(y)


def _pri(x, y):
    m = sum(min(a, b, 1 - b) for a, b in zip(x, y))
    return (sum(min(a, b) for a, b in zip(x, y)) - m) / (sum(x) - m)


def _two(v: Fraction) -> str:
    q = math.floor(v * 100 + Fraction(1, 2))
    return f"{q // 100}.{q % 100:02d}"


def fit(labels: list, y: list, mem: dict) -> dict:
    xs = [_term_x(t, mem) for t in labels]
    sol = [max(col) for col in zip(*xs)]
    sol_cov = _cov(sol, y)
    terms = []
    for i, t in enumerate(labels):
        rest = [max(col) for col in zip(*[x for j, x in enumerate(xs) if j != i])]
        terms.append({"label": t, "raw_consistency": _cons(xs[i], y), "pri": _pri(xs[i], y),
                      "raw_coverage": _cov(xs[i], y), "unique_coverage": sol_cov - _cov(rest, y)})
    return {"terms": terms, "solution_consistency": _cons(sol, y), "solution_coverage": sol_cov}


def _record(rid: str, source: str, outcome: str, f: dict, headline: bool) -> dict:
    terms = [{"label": t["label"], "raw_consistency": _two(t["raw_consistency"]), "pri": _two(t["pri"]),
              "raw_coverage": _two(t["raw_coverage"]), "unique_coverage": _two(t["unique_coverage"]),
              "headline": headline} for t in f["terms"]]
    return {"id": rid, "kind": "fit_table", "source": source, "cells": [], "outcome": outcome, "terms": terms,
            "solution_consistency": _two(f["solution_consistency"]),
            "solution_coverage": _two(f["solution_coverage"]), "consistency_cutoff": CUTOFF,
            "crisp_outcome": False, "split_unclear": False}


def _assert_rules(pres: dict, absn: dict) -> None:
    for i, t in enumerate(pres["terms"]):
        assert "BoardIndep" in t["label"].split("*"), t
        assert t["pri"] >= Fraction(1, 2), t
        if i != PLANT_P5[0]:
            assert t["raw_consistency"] >= Fraction(4, 5), t
    c2 = pres["terms"][PLANT_P5[0]]
    assert _two(c2["raw_consistency"]) == "0.81" and c2["pri"] <= Fraction(78, 100), c2
    assert any("RDIntensity" in t["label"].split("*") for t in pres["terms"])
    sets = [set(t["label"].split("*")) for t in pres["terms"]]
    assert all(not (a <= b) for i, a in enumerate(sets) for j, b in enumerate(sets) if i != j)
    for t in absn["terms"]:
        assert t["raw_consistency"] >= Fraction(4, 5) and t["pri"] >= Fraction(1, 2), t


def main() -> int:
    ap = argparse.ArgumentParser(description="Write the planted-1 fixture data (synthetic).")
    ap.add_argument("--out", required=True, help="directory for memberships.csv and script_inputs.json")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    raw, anchors, mem = build()
    half = sum(1 for v in mem["Alliances"] if v == Decimal("0.500000"))
    assert half == 18, half
    y = [_fr(v) for v in mem["HighROA"]]
    pres = fit(PRESENCE, y, mem)
    absn = fit(ABSENCE, [1 - v for v in y], mem)
    _assert_rules(pres, absn)
    t3 = _record("t3-presence", SOURCE_TABLE3, "presence", pres, True)
    t3["terms"][PLANT_P5[0]]["pri"] = PLANT_P5[1]
    a1 = _record("a1-absence", SOURCE_TABLEA1, "absence", absn, False)
    design = {"id": "design", "kind": "design", "source": SOURCE_DESIGN, "cells": [], "variant": "fsQCA",
              "conditions": 6, "n_cases": N, "frequency_cutoff": 2, "cases_in_truth_table": 162}
    lines = [",".join(["firm"] + SETS)]
    for i in range(N):
        row = [f"F{i + 1:03d}"]
        for s in SETS:
            row.append(str(mem[s][i]) if s == "CEODuality" else f"{mem[s][i]:.6f}")
        lines.append(",".join(row))
    (out / "memberships.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "script_inputs.json").write_text(json.dumps([t3, a1, design], indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
