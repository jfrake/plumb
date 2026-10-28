"""Build the case data for planted-2. SYNTHETIC TEST PAPER, NOT REAL RESEARCH.

The hospital, its 16 units, and every informant are fictional. The codes are
drawn with a fixed seed (SEED = 20260930) under the structural rules below, so
they stand in for the crisp memberships the fictional authors assigned case by
case from interviews.

Usage: python3 make_fixture.py --out DIR
Writes DIR/memberships.csv and DIR/script_inputs.json and nothing else.

Coding rules (crisp sets, as the paper states them):
  Reliable  (outcome) 1 when informants in at least two roles (nurses and
            physicians) described handoffs over the study year as complete and
            routine, and no informant described a handoff gap that reached a
            patient; otherwise 0.
  Protocol  1 when informants described a written handoff protocol that staff
            followed at every shift change, not one kept only on file.
  Champion  1 when informants in at least two roles named the same clinician as
            the person who kept handoffs on track.
  Huddles   1 when informants described a safety huddle held at the start of
            most shifts.
  Staffing  1 when informants in at least two roles described staffing as
            adequate on most shifts and no informant described routine
            borrowing of nurses from other units.
  Tenure    1 when most of the nurses interviewed had more than three years on
            the unit.
  Digital   1 when handoffs were recorded in the electronic handoff tool rather
            than on paper or orally only.
  Leader    1 when informants described the nurse manager as present at shift
            change on most days.

Structure: exactly 8 units are in Reliable. One unit (Protocol, ~Champion) and
one unit (~Protocol, Champion) are the only units in their rows, and both are
in Reliable. Each of the other six reliable units shares all seven codes with
one unit outside Reliable (a contradictory row). Two more units outside
Reliable sit in rows of their own. Every condition and its negation hold for
fewer than all eight reliable units, so no condition reaches 0.90 necessity
consistency.

Fit figures are computed exactly with fractions.Fraction and printed at two
decimals, rounding half-even. The two configurations each cover one of the
eight reliable units: raw and unique coverage 1/8 = 0.125, printed 0.12;
solution coverage 2/8, printed 0.25; consistency 1.00.

Plants: none in the numbers. The planted errors (B5, B14, B10) are in the
paper's text only; Table 2's 0.12 + 0.12 against 0.25 is a rounding decoy.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import random
from decimal import ROUND_HALF_EVEN, Decimal
from fractions import Fraction
from pathlib import Path

SEED = 20260930
OUTCOME = "Reliable"
CONDITIONS = ["Protocol", "Champion", "Huddles", "Staffing", "Tenure", "Digital", "Leader"]
SETS = [OUTCOME] + CONDITIONS
CONSISTENCY_CUTOFF = "0.80"
SOURCE_FIT = "Table 2, p. 6"
SOURCE_DESIGN = "p. 3"
SOURCE_CASES = "Table 1, p. 5"


def _rand_row(rng: random.Random) -> tuple:
    return tuple(rng.randint(0, 1) for _ in CONDITIONS)


def _draw(rng: random.Random):
    while True:
        used = set()
        units = []
        rest = [rng.randint(0, 1) for _ in CONDITIONS[2:]]
        protocol_led = (1, 0) + tuple(rest)
        rest = [rng.randint(0, 1) for _ in CONDITIONS[2:]]
        champion_led = (0, 1) + tuple(rest)
        used |= {protocol_led, champion_led}
        units.append((1, protocol_led))
        units.append((1, champion_led))
        ok = True
        for _ in range(6):
            row = _rand_row(rng)
            if row in used:
                ok = False
                break
            used.add(row)
            units.append((1, row))
            units.append((0, row))
        for _ in range(2):
            row = _rand_row(rng)
            if row in used:
                ok = False
                break
            used.add(row)
            units.append((0, row))
        if not ok:
            continue
        reliable = [row for y, row in units if y == 1]
        if any(len({r[j] for r in reliable}) < 2 for j in range(len(CONDITIONS))):
            continue
        rng.shuffle(units)
        return units, protocol_led, champion_led


def _label(row: tuple) -> str:
    return "*".join(("" if v else "~") + name for name, v in zip(CONDITIONS, row))


def _print2(x: Fraction) -> str:
    d = Decimal(x.numerator) / Decimal(x.denominator)
    return str(d.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN))


def _fit(units, terms):
    y = [u[0] for u in units]
    sum_y = sum(y)

    def member(row, term):
        return 1 if row == term else 0

    out = []
    sol = [max(member(r, t) for t in terms) for _, r in units]
    sol_xy = sum(min(s, yy) for s, yy in zip(sol, y))
    sol_cov = Fraction(sol_xy, sum_y)
    sol_con = Fraction(sol_xy, sum(sol))
    for t in terms:
        x = [member(r, t) for _, r in units]
        xy = sum(min(a, b) for a, b in zip(x, y))
        others = [u for u in terms if u != t]
        sol_wo = [max([member(r, o) for o in others] or [0]) for _, r in units]
        cov_wo = Fraction(sum(min(s, yy) for s, yy in zip(sol_wo, y)), sum_y)
        out.append({"label": _label(t), "raw_consistency": _print2(Fraction(xy, sum(x))), "pri": None,
                    "raw_coverage": _print2(Fraction(xy, sum_y)), "unique_coverage": _print2(sol_cov - cov_wo),
                    "headline": True})
    return out, _print2(sol_con), _print2(sol_cov)


def build():
    rng = random.Random(SEED)
    units, protocol_led, champion_led = _draw(rng)
    ids = [f"U{i:02d}" for i in range(1, len(units) + 1)]
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["unit"] + SETS)
    cases = []
    for uid, (y, row) in zip(ids, units):
        vals = [str(y)] + [str(v) for v in row]
        w.writerow([uid] + vals)
        cases.append(dict(zip(SETS, vals)))
    terms, sol_con, sol_cov = _fit(units, [protocol_led, champion_led])
    records = [
        {"id": "t2-presence", "kind": "fit_table", "source": SOURCE_FIT, "cells": [], "outcome": "presence",
         "terms": terms, "solution_consistency": sol_con, "solution_coverage": sol_cov,
         "consistency_cutoff": CONSISTENCY_CUTOFF, "crisp_outcome": True, "split_unclear": False},
        {"id": "design", "kind": "design", "source": SOURCE_DESIGN, "cells": [], "variant": "csQCA",
         "conditions": len(CONDITIONS), "n_cases": len(units)},
        {"id": "case-data", "kind": "memberships", "source": SOURCE_CASES, "cells": [], "variant": "csQCA",
         "sets": SETS, "outcome": OUTCOME, "conditions": CONDITIONS, "compare": ["t2-presence"],
         "cases": cases},
    ]
    return buf.getvalue(), json.dumps(records, indent=1) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description="Write memberships.csv and script_inputs.json for planted-2.")
    p.add_argument("--out", required=True, help="output folder")
    a = p.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    csv_text, json_text = build()
    (out / "memberships.csv").write_text(csv_text, encoding="utf-8")
    (out / "script_inputs.json").write_text(json_text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
