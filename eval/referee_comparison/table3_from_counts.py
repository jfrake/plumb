#!/usr/bin/env python3
"""Recompute the Table 3 percentages from the public aggregate counts in counts.json.

Usage: python3 eval/referee_comparison/table3_from_counts.py [--counts counts.json] [--json]
Prints one row per class: referee points, also raised by Plumb (with its share), Plumb-only points,
rated valid (referee / Plumb only), and rated serious (referee / Plumb only). Exits 1 if the counts
do not add up (classes to the total, papers to the total, or a part larger than its whole).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLASSES = ["factual", "substantive judgment", "preference"]
PAPERS = ["A", "B", "C", "D"]
SUMMED = ["referee_points", "plumb_only", "referee_valid", "referee_serious", "referee_wrong",
          "plumb_only_valid", "plumb_only_serious", "plumb_only_wrong"]


def check(counts: dict) -> list:
    errs = []
    cls, total = counts["classes"], counts["classes"]["all"]
    for k in SUMMED + ["also_raised"]:
        if sum(cls[c][k] for c in CLASSES) != total[k]:
            errs.append(f"classes do not sum to the total for {k}")
    for k in SUMMED:
        if sum(counts["papers"][p][k] for p in PAPERS) != total[k]:
            errs.append(f"papers do not sum to the total for {k}")
    for name, row in list(cls.items()) + list(counts["papers"].items()):
        for k, v in row.items():
            if not isinstance(v, int) or isinstance(v, bool) or v < 0:
                errs.append(f"{name}: {k} is not a count")
        if row.get("also_raised", 0) > row["referee_points"]:
            errs.append(f"{name}: also_raised exceeds referee_points")
        for side, n in (("referee", "referee_points"), ("plumb_only", "plumb_only")):
            if row[f"{side}_valid"] + row[f"{side}_wrong"] > row[n] or row[f"{side}_serious"] > row[n]:
                errs.append(f"{name}: {side} ratings exceed its points")
    return errs


def pct(a: int, n: int):
    return round(100 * a / n) if n else None


def rows(counts: dict) -> dict:
    out = {}
    for c in CLASSES + ["all"]:
        r = counts["classes"][c]
        out[c] = {"referee_points": r["referee_points"], "also_raised": r["also_raised"],
                  "also_raised_pct": pct(r["also_raised"], r["referee_points"]), "plumb_only": r["plumb_only"],
                  "valid_pct": [pct(r["referee_valid"], r["referee_points"]), pct(r["plumb_only_valid"], r["plumb_only"])],
                  "serious_pct": [pct(r["referee_serious"], r["referee_points"]),
                                  pct(r["plumb_only_serious"], r["plumb_only"])]}
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--counts", default=str(HERE / "counts.json"))
    p.add_argument("--json", action="store_true", help="print the rows as JSON")
    a = p.parse_args(argv)
    counts = json.loads(Path(a.counts).read_text(encoding="utf-8"))
    errs = check(counts)
    if errs:
        print("\n".join(errs), file=sys.stderr)
        return 1
    res = rows(counts)
    if a.json:
        print(json.dumps(res, indent=1))
        return 0
    f = lambda v: "--" if v is None else f"{v}%"
    print("class | referee points | also raised | Plumb only | valid (referee / Plumb only) | serious (referee / Plumb only)")
    for c, r in res.items():
        print(f"{c} | {r['referee_points']} | {r['also_raised']} ({f(r['also_raised_pct'])}) | {r['plumb_only']} | "
              f"{f(r['valid_pct'][0])} / {f(r['valid_pct'][1])} | {f(r['serious_pct'][0])} / {f(r['serious_pct'][1])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
