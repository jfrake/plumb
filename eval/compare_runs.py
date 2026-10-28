#!/usr/bin/env python3
"""Compare repeat runs of one paper: matched issues, major-issue overlap, and Judgment calls.

Usage:
    python3 eval/compare_runs.py <run folder> <run folder> [<run folder> ...] [--hand-matches pairs.yaml] [--out compare.json]

Each run folder is plumb_output/<date>/ (or its .workspace/); two at least, all of one PDF. The
hand-match file is YAML or JSON: a list of pairs, each pair two {run, id} mappings naming a run by
the name the report prints (the shortest path suffix that tells the runs apart) or by a path to its
folder or workspace, and an issue by its stage-5 id. Hand matches apply before the automatic
strategies. Runs of different PDFs are refused: by pdf_sha256 where run.json records it, else by the
PDF's file name. Prints the JSON scorecard, then a markdown report. With --out, the JSON
goes to that file as well.

Exit codes: 0 compared; 2 an input is missing or malformed, or the runs are not of one paper (the
message says which).
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from plumb import run_compare  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", nargs="+", help="plumb_output/<date>/ or its .workspace/, two or more")
    ap.add_argument("--hand-matches", help="YAML or JSON file of issue pairs a human judged the same")
    ap.add_argument("--out", help="also write the JSON scorecard here")
    args = ap.parse_args(argv)
    try:
        card = run_compare.compare_paths(args.runs, hand_matches=args.hand_matches)
    except run_compare.CompareError as exc:
        print(f"compare_runs: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(card, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    print()
    print(run_compare.markdown(card), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
