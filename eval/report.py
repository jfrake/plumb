#!/usr/bin/env python3
"""Planted-error detection by depth, and the Auto-run reliability numbers when available.

Usage:
    python3 eval/report.py <fixture folder>=<run folder> [...] [--manifest pairs.txt] \
        [--runs <run folder> ...] [--hand-matches pairs.yaml] [--json report.json]

Each pair is a fixture folder (packs/<pack>/fixtures/<id>/) and the run folder scored against it
(plumb_output/<date>/ or its .workspace). --manifest adds one pair per line in the same form;
blank lines and lines starting with # are skipped. Every pair is scored with plumb.fixture_score,
and the report lists each run, then the totals by depth: must_catch caught, must_not_flag
flagged, also_fair caught, and must_catch by severity. With --runs, the Auto run folders go to
eval/compare_runs.py for the reliability numbers, with --hand-matches passed through.

Exit codes: 0 done; 2 a pair is malformed or an input is missing (the message names it).
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import compare_runs  # noqa: E402
from plumb import fixture_score  # noqa: E402
from plumb.depth import DEPTHS  # noqa: E402
from plumb.validated import SEVERITIES  # noqa: E402


class ReportError(Exception):
    """A pair is malformed or an input is missing."""


def parse_pair(spec: str) -> tuple:
    fixture, sep, run = spec.partition("=")
    if not sep or not fixture.strip() or not run.strip():
        raise ReportError(f"each pair is fixture=run, not {spec!r}")
    return Path(fixture.strip()), Path(run.strip())


def read_manifest(path) -> list:
    p = Path(path)
    if not p.is_file():
        raise ReportError(f"{p} is missing")
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            out.append(parse_pair(s))
    return out


def score_pairs(pairs: list) -> list:
    cards = []
    for fixture, run in pairs:
        try:
            cards.append(fixture_score.score_paths(fixture, run))
        except fixture_score.ScoreError as exc:
            raise ReportError(f"{fixture} against {run}: {exc}")
    return cards


def _empty() -> dict:
    return {"runs": 0, "must_catch": {"expected": 0, "caught": 0}, "must_not_flag": {"expected": 0, "flagged": 0},
            "also_fair": {"expected": 0, "caught": 0},
            "by_severity": {s: {"expected": 0, "caught": 0} for s in SEVERITIES}}


def by_depth(cards: list) -> dict:
    """Totals per depth over every card scored at it, in depth order, depths with no run left out."""
    out = {}
    for card in cards:
        row = out.setdefault(card["depth"], _empty())
        row["runs"] += 1
        t = card["totals"]
        for part, key in (("must_catch", "caught"), ("must_not_flag", "flagged"), ("also_fair", "caught")):
            row[part]["expected"] += t[part]["expected"]
            row[part][key] += t[part][key]
        for sev, v in card["by_severity"].items():
            row["by_severity"].setdefault(sev, {"expected": 0, "caught": 0})
            row["by_severity"][sev]["expected"] += v["expected"]
            row["by_severity"][sev]["caught"] += v["caught"]
    return {d: out[d] for d in list(DEPTHS) + [d for d in out if d not in DEPTHS] if d in out}


def _share(hit: int, expected: int) -> str:
    return f"{hit} of {expected} ({round(100 * hit / expected) if expected else 0}%)"


def _line(*cells) -> str:
    return "| " + " | ".join(str("" if c is None else c).replace("|", "/") for c in cells) + " |"


def _table(header: tuple, rows: list) -> list:
    return [_line(*header), "|" + "|".join("---" for _ in header) + "|"] + rows


def markdown(cards: list, table: dict) -> str:
    lines = ["## planted-error detection", "", "### each run", ""]
    lines += _table(("fixture", "pack", "depth", "must_catch caught", "must_not_flag flagged", "also_fair caught", "run"), [
        _line(c["fixture"], c["pack"], c["depth"], f"{c['totals']['must_catch']['caught']} of {c['totals']['must_catch']['expected']}",
              f"{c['totals']['must_not_flag']['flagged']} of {c['totals']['must_not_flag']['expected']}",
              f"{c['totals']['also_fair']['caught']} of {c['totals']['also_fair']['expected']}", c["run"]) for c in cards])
    lines += ["", "### by depth", ""]
    lines += _table(("depth", "runs", "must_catch caught", "must_not_flag flagged", "also_fair caught")
                    + tuple(f"{s} caught" for s in SEVERITIES), [
        _line(d, r["runs"], _share(r["must_catch"]["caught"], r["must_catch"]["expected"]),
              _share(r["must_not_flag"]["flagged"], r["must_not_flag"]["expected"]),
              _share(r["also_fair"]["caught"], r["also_fair"]["expected"]),
              *[_share(r["by_severity"].get(s, {}).get("caught", 0), r["by_severity"].get(s, {}).get("expected", 0))
                for s in SEVERITIES]) for d, r in table.items()])
    return "\n".join(lines) + "\n"


def reliability(runs: list, hand_matches=None) -> str:
    """Runs eval/compare_runs.py over the Auto run folders, with the hand-match file passed
    through; its card prints before this line."""
    if not runs:
        return "reliability: pass --runs <auto run folders> to run eval/compare_runs.py"
    argv = [str(r) for r in runs]
    if hand_matches:
        argv += ["--hand-matches", str(hand_matches)]
    code = compare_runs.main(argv)
    return f"reliability: compare_runs.py exited {code}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pairs", nargs="*", metavar="FIXTURE=RUN", help="a fixture folder and the run folder scored against it")
    ap.add_argument("--manifest", help="a file of fixture=run lines")
    ap.add_argument("--runs", nargs="*", default=[], help="Auto run folders for eval/compare_runs.py")
    ap.add_argument("--hand-matches", help="passed through to eval/compare_runs.py")
    ap.add_argument("--json", help="also write the full report here")
    args = ap.parse_args(argv)
    try:
        pairs = [parse_pair(p) for p in args.pairs]
        if args.manifest:
            pairs += read_manifest(args.manifest)
        if not pairs:
            raise ReportError("no pairs given; pass fixture=run or --manifest")
        cards = score_pairs(pairs)
    except ReportError as exc:
        print(f"report: {exc}", file=sys.stderr)
        return 2
    table = by_depth(cards)
    if args.json:
        Path(args.json).write_text(json.dumps({"runs": cards, "by_depth": table}, indent=2) + "\n", encoding="utf-8")
    print(markdown(cards, table))
    print(reliability(args.runs, args.hand_matches))
    return 0


if __name__ == "__main__":
    sys.exit(main())
