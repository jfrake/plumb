#!/usr/bin/env python3
"""Build ratings.json and matches.json from the rating page's raw database dumps.

Usage:
  python3 export.py --raw <raw dump folder> --items <items.json> --matchdata <matchdata.json> \
      --rater <document id>=primary --rater <document id>=second --out <export folder> [--heldout A]
The raw folder holds ratings/<document id>.json and matches/<referee item id>.json, one file per database
document. The primary rater rates every item; the second rater rates the held-out paper's items only.
A referee item with no confirmed match keeps the proposed match from matchdata.json. Notes are dropped.
"""
import argparse
import json
import sys
from pathlib import Path

LABELS = {"correctness": {"valid", "doubtful", "wrong"},
          "importance": {"Undermines the main claim", "Weakens a claim", "Minor"},
          "kind": {"factual", "substantive judgment", "preference"}}
ROLES = {"primary", "second"}


def build(items: dict, matchdata: dict, cards: dict, docs: dict, raters: dict, heldout: str):
    R = {i for i, it in items.items() if it["source"] == "referee"}
    assert set(matchdata) == R, "matchdata must hold exactly the referee items"
    assert set(cards) <= R, set(cards) - R
    out = {}
    for r in sorted(R):
        if r in cards:
            out[r] = {"strength": cards[r]["strength"], "match": cards[r]["match"], "origin": "confirmed"}
        else:
            m = matchdata[r]
            assert (m["proposed_strength"] == "none") == (not m["proposed"]), r
            out[r] = {"strength": m["proposed_strength"], "match": m["proposed"], "origin": "proposed"}
        for pid in out[r]["match"]:
            p = items[pid]
            assert p["source"] == "plumb" and p["paper"] == items[r]["paper"], (r, pid)
    assert set(docs) == set(raters), set(docs) ^ set(raters)
    ratings = {}
    for uid, d in docs.items():
        ans = {i: {k: a[k] for k in LABELS} for i, a in d["answers"].items()}
        for i, a in ans.items():
            assert i in items and all(a[k] in LABELS[k] for k in LABELS), (uid, i)
        ratings[uid] = {"rater": raters[uid], "answers": ans}
    for uid, role in raters.items():
        if role == "primary":
            assert set(ratings[uid]["answers"]) == set(items), "the primary rater must rate every item"
        else:
            held = {i for i, it in items.items() if it["paper"] == heldout}
            assert set(ratings[uid]["answers"]) == held, "the second rater rates the held-out paper's items"
    return out, ratings


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--raw", required=True)
    p.add_argument("--items", required=True)
    p.add_argument("--matchdata", required=True)
    p.add_argument("--rater", action="append", required=True, metavar="DOC_ID=ROLE")
    p.add_argument("--out", required=True)
    p.add_argument("--heldout", default="A")
    a = p.parse_args(argv)
    raters = dict(x.split("=", 1) for x in a.rater)
    if not set(raters.values()) <= ROLES or "primary" not in raters.values():
        p.error("--rater roles are primary and second, and one must be primary")

    # LOAD
    raw = Path(a.raw)
    items = {it["id"]: it for it in json.loads(Path(a.items).read_text(encoding="utf-8"))}
    matchdata = json.loads(Path(a.matchdata).read_text(encoding="utf-8"))
    cards = {f.stem: json.loads(f.read_text(encoding="utf-8")) for f in (raw / "matches").glob("*.json")}
    docs = {f.stem: json.loads(f.read_text(encoding="utf-8")) for f in (raw / "ratings").glob("*.json")}

    # MAIN
    out, ratings = build(items, matchdata, cards, docs, raters, a.heldout)

    # SAVE
    dst = Path(a.out)
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "matches.json").write_text(json.dumps(out, indent=1))
    (dst / "ratings.json").write_text(json.dumps(ratings, indent=1))
    print(f"matches: {sum(v['origin'] == 'confirmed' for v in out.values())} confirmed, "
          f"{sum(v['origin'] == 'proposed' for v in out.values())} proposed; ratings: "
          + ", ".join(f"{v['rater']} {len(v['answers'])}" for v in ratings.values()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
