#!/usr/bin/env python3
"""Print the preregistered numbers for one paper from the two filled rating sheets.

Usage:
    python3 eval/rate_analysis.py --sheet <rater>=<sheet.csv> --sheet <rater>=<sheet.csv> \
        --mapping <pool folder>/sealed/mapping.sealed.json --author <rater> --nonauthor <rater> \
        [--joint] [--json result.json]
    python3 eval/rate_analysis.py --pool <result.json> <result.json> ... [--json pooled.json]

Validity is the author's correctness call and importance the non-author's severity (top two
levels count); --joint makes both raters required to agree on each, for the joint paper. The
mapping is read only from --mapping, so run this only after both sheets lock. The rater names
and the roles must match what pool.py recorded. Prints the JSON result, then a markdown report;
with --json the JSON goes to that file as well. --pool takes the result files of several papers
and prints the per-paper and pooled numbers.

Exit codes: 0 done; 2 an input is missing, malformed, or not fully filled (the message names it).
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from plumb import eval_rate  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sheet", action="append", default=[], metavar="RATER=PATH", help="a filled sheet; give two")
    ap.add_argument("--mapping", help="mapping.sealed.json from the pool folder")
    ap.add_argument("--author", help="the rater who wrote the paper (validity)")
    ap.add_argument("--nonauthor", help="the other rater (importance)")
    ap.add_argument("--joint", action="store_true", help="both raters must agree (the joint paper)")
    ap.add_argument("--json", help="also write the JSON result here")
    ap.add_argument("--pool", nargs="*", metavar="RESULT_JSON", help="result files of several papers to pool")
    args = ap.parse_args(argv)
    try:
        if args.pool is not None:
            results = []
            for path in args.pool:
                try:
                    results.append(json.loads(Path(path).read_text(encoding="utf-8")))
                except (OSError, ValueError) as exc:
                    raise eval_rate.RateError(f"cannot read {path}: {exc}")
            result = eval_rate.pooled(results)
            text = json.dumps(result, indent=2)
            if args.json:
                Path(args.json).write_text(text + "\n", encoding="utf-8")
            print(text)
            print()
            print(eval_rate.pooled_markdown(result), end="")
            return 0
        if not args.mapping:
            raise eval_rate.RateError("--mapping is required; the sealed mapping is never found on its own")
        if not args.author or not args.nonauthor:
            raise eval_rate.RateError("--author and --nonauthor are required")
        sheets = {}
        for spec in args.sheet:
            rater, sep, path = spec.partition("=")
            if not sep or not rater.strip() or not path.strip():
                raise eval_rate.RateError(f"--sheet takes RATER=PATH, not {spec!r}")
            sheets[rater.strip()] = eval_rate.read_sheet(path.strip())
        result = eval_rate.analyse(sheets, eval_rate.read_mapping(args.mapping), author=args.author,
                                   nonauthor=args.nonauthor, joint=args.joint)
    except eval_rate.RateError as exc:
        print(f"rate_analysis: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(result, indent=2)
    if args.json:
        Path(args.json).write_text(text + "\n", encoding="utf-8")
    print(text)
    print()
    print(eval_rate.markdown(result), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
