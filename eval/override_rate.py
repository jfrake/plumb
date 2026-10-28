#!/usr/bin/env python3
"""The override rate of one Standard run, by stage, stop, pack, and adjudication type.

Usage:
    python3 eval/override_rate.py <run folder or its .workspace> [--json overrides.json]

Reads audit/events.jsonl and the stage files. An override is a final answer at a judgment stop
that differs from the recommended option (plumb.checkin.is_override); the denominator is every
answer the user gave at those stops that could have been one (plumb.checkin.counts_as_user_answer).
Demotions, alternatives marked handled, and audit rulings overturned count here though they
never enter the rating pool. Prints the JSON table, then a markdown report.

Exit codes: 0 done; 2 the run folder is missing or malformed.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from plumb import eval_override  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run", help="plumb_output/<date>/ or its .workspace/")
    ap.add_argument("--json", help="also write the JSON table here")
    args = ap.parse_args(argv)
    try:
        table = eval_override.override_rate(args.run)
    except eval_override.OverrideError as exc:
        print(f"override_rate: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(table, indent=2)
    if args.json:
        Path(args.json).write_text(text + "\n", encoding="utf-8")
    print(text)
    print()
    print(eval_override.markdown(table), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
