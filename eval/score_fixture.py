#!/usr/bin/env python3
"""Score a Plumb run against a fixture's answer key.

Usage:
    python3 eval/score_fixture.py <fixture folder> <run folder or its .workspace> [--out score.json]

<fixture folder> is packs/<pack>/fixtures/<id>/, which holds expected.yaml. The run folder is
plumb_output/<date>/ (or its .workspace/). Prints the JSON scorecard, then a markdown report.
With --out, the JSON goes to that file as well.

Exit codes: 0 scored; 2 an input is missing or malformed (the message names it).
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from plumb import fixture_score  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("fixture", help="packs/<pack>/fixtures/<id>/")
    ap.add_argument("run", help="plumb_output/<date>/ or its .workspace/")
    ap.add_argument("--out", help="also write the JSON scorecard here")
    args = ap.parse_args(argv)
    try:
        card = fixture_score.score_paths(args.fixture, args.run)
    except fixture_score.ScoreError as exc:
        print(f"score_fixture: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(card, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    print()
    print(fixture_score.markdown(card), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
