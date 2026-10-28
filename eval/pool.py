#!/usr/bin/env python3
"""Build the blind rating pool for one pilot paper.

Usage:
    python3 eval/pool.py --paper <name> --auto <run folder> --standard <run folder> \
        --baseline <baseline out folder> --out <pool folder> --raters r1,r2 [--seed N] [--no-rewrite] \
        [--stop-after-clusters | --clusters-from <clusters-only folder>/sealed/clusters.json [--hand-merges <file>]]

The hand pass takes two runs, so it checks the grouping that ships. First a clusters-only run with
--stop-after-clusters: it calls the clusterer and writes sealed/clusters.json and
sealed/near_misses.json, with no rewrite and no sheets. Read the near misses and write a
--hand-merges file of candidate-ref pairs. Then the real run into a new folder with --clusters-from
that clusters.json and --hand-merges: it reuses the checked groups without a call (refusing them if
the prompt, model, effort, or candidates changed), joins the hand pairs, rewrites, and writes the
sheets. A hand merge only joins; it cannot split a group the clusterer made.

--auto and --standard are Plumb run folders (plumb_output/<date>/ or their .workspace); --baseline is
the folder eval/baseline.py wrote for the paper. Any of the three may be left out, and the pool
records that source as missing. Every issue, and every point the Standard reviewer dropped at a
check-in, is a candidate. The candidates are grouped by meaning in one call to claude-fable-5-1
on the fixed prompt in eval/pool_cluster_prompt.txt, each group becomes one claim, and each claim is
rewritten into one neutral line by the same model on the fixed prompt in
eval/pool_rewrite_prompt.txt (key in ANTHROPIC_API_KEY; the texts are sent to Anthropic). With
--no-rewrite, a dry run, no call is made: candidates are merged by word overlap instead and each
claim keeps the first candidate's text.

Output, in --out:
    sealed/pool.json           every claim with its sources; not for the raters
    sealed/mapping.sealed.json claim id to sources; the rating step reads it only when told to
    sealed/near_misses.json    pairs for the hand pass: pairs the overlap rule would have merged or
                               nearly merged that the clusterer kept apart, and pairs the clusterer
                               merged with little word overlap; for a --hand-merges file
    sealed/clusters.json       the checked clustering reply, so a rerun after a failure does not pay twice
    sealed/rewrites.json       every finished rewrite, written as it lands
    raters/sheet-<rater>.csv   one per rater, shuffled by the seed, no source labels
    raters/instructions.txt    what the raters fill in
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from plumb import eval_pool  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--paper", required=True, help="a short name for the paper, recorded in the pool")
    ap.add_argument("--auto", help="the Auto run of record (plumb_output/<date>/)")
    ap.add_argument("--standard", help="the Standard run (plumb_output/<date>/)")
    ap.add_argument("--baseline", help="the eval/baseline.py out folder for this paper")
    ap.add_argument("--out", required=True, help="the pool folder to write; must be empty or absent")
    ap.add_argument("--raters", default="rater-1,rater-2", help="two rater names, comma separated")
    ap.add_argument("--author", help="the rater who wrote the paper (recorded; rate_analysis checks it)")
    ap.add_argument("--nonauthor", help="the other rater (recorded; rate_analysis checks it)")
    ap.add_argument("--joint", action="store_true", help="the joint paper: both raters must agree (recorded)")
    ap.add_argument("--seed", type=int, default=None,
                    help="seed for the claim ids and the sheet shuffle; drawn at random when not given; stored only in sealed/pool.json")
    ap.add_argument("--no-rewrite", action="store_true", help="skip the model rewrite (dry run)")
    ap.add_argument("--hand-merges", help="JSON or YAML list of [ref, ref] candidate pairs to merge (refs from near_misses.json)")
    ap.add_argument("--stop-after-clusters", action="store_true",
                    help="call the clusterer, write sealed/clusters.json and sealed/near_misses.json, and stop (no rewrite, no sheets)")
    ap.add_argument("--clusters-from", help="a clusters-only run's sealed/clusters.json; the real run reuses its checked groups")
    ap.add_argument("--accept-parse-count", action="store_true",
                    help="accept a baseline file whose entry and severity counts disagree, after checking it by hand (recorded)")
    args = ap.parse_args(argv)
    raters = tuple(r.strip() for r in args.raters.split(",") if r.strip())
    try:
        if len(raters) != 2:
            raise eval_pool.PoolError("--raters must name two raters, comma separated")
        pool = eval_pool.build(paper=args.paper, auto=args.auto, standard=args.standard, baseline=args.baseline,
                               out=args.out, raters=raters, seed=args.seed, rewrite_claims=not args.no_rewrite,
                               hand_merges=args.hand_merges, author=args.author, nonauthor=args.nonauthor,
                               joint=args.joint, accept_parse_count=args.accept_parse_count,
                               stop_after_clusters=args.stop_after_clusters, clusters_from=args.clusters_from)
    except eval_pool.PoolError as exc:
        print(f"pool: {exc}", file=sys.stderr)
        return 2
    if pool.get("clusters_only"):
        print(f"{pool['candidates']} candidates grouped into {pool['claims']} claims for {pool['paper']} in {args.out}; "
              "clusters-only run, no rewrite and no sheets")
        print(f"{pool['near_misses']} near misses in sealed/near_misses.json; pass sealed/clusters.json to the real run "
              "with --clusters-from")
        return 0
    how = "rewritten by " + pool["rewrite"]["model"] if pool["rewrite"]["done"] else "no rewrite (dry run)"
    print(f"{len(pool['claims'])} claims for {pool['paper']} in {args.out}; {how}")
    if pool["merge"] == "cluster":
        print(f"grouped by meaning by {pool['cluster']['model']} on {pool['cluster']['prompt_file']}")
    else:
        print("merged by word overlap (dry run)")
    print(f"{pool['near_misses']} near misses in sealed/near_misses.json; "
          f"{pool['hand_merges']['merged']} hand merges applied")
    for model, n in pool["baseline_counts"].items():
        print(f"{model}: {n} entries parsed from the run of record")
    for d in pool["departures"]:
        print(f"departure: {d['model']} parsed to {d['entries']} entries but {d['severity_labels']} severity labels; "
              "accepted by --accept-parse-count")
    if pool["missing"]:
        print("missing sources: " + ", ".join(pool["missing"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
