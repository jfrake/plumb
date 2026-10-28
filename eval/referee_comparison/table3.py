#!/usr/bin/env python3
"""Table 3 from the item pool, the exported ratings, and the confirmed matches: referee points, points Plumb
also raised, Plumb-only points, and blind-rated validity and importance, by the primary rater's class.

Usage:
  python3 table3.py --items <items.json> --ratings <ratings.json> --matches <matches.json> \
      --out <table_3.tex> [--summary <summary.json>] [--heldout A]
Exit 0 on success, 2 when a rating or match is missing (the message names the ids).
The ratings file maps a rater document id to {"rater": "primary" | "second", "answers": {...}}.
"""
import argparse, json, sys

CLASSES = ["factual", "substantive judgment", "preference"]
SERIOUS = {"Undermines the main claim", "Weakens a claim"}
ROLES = ("primary", "second")


class MissingData(Exception):
    pass


def build(items, ratings, matches, heldout="A"):
    # INPUTS: check completeness before computing anything
    by_id = {it["id"]: it for it in items}
    for who in ROLES:
        if sum(1 for r in ratings.values() if r.get("rater") == who) > 1:
            raise MissingData(f"more than one ratings document is labelled {who}; assign raters by document id at export")
    primary = next((r["answers"] for r in ratings.values() if r.get("rater") == "primary"), None)
    if primary is None:
        raise MissingData("no ratings from the primary rater")
    unrated = [i for i in by_id if i not in primary or primary[i].get("kind") not in CLASSES]
    if unrated:
        raise MissingData(f"unrated or unclassified items: {unrated}")
    # The rater's class, not the agent's, sets each item's row
    cls_of = {i: primary[i]["kind"] for i in by_id}
    refs = [it for it in items if it["source"] == "referee"]
    unmatched = [r["id"] for r in refs if r["id"] not in matches]
    if unmatched:
        raise MissingData(f"unconfirmed matches: {unmatched}")
    matched_plumb = set()
    for r in refs:
        m = matches[r["id"]]
        for pid in m["match"]:
            if by_id.get(pid, {}).get("paper") != r["paper"]:
                raise MissingData(f"{r['id']}: match {pid} is on another paper or missing")
            if m["strength"] != "none":
                matched_plumb.add(pid)

    def share(ids, test):
        return round(sum(1 for i in ids if test(primary[i])) / len(ids), 3) if ids else None

    # MAIN: one row per class plus the total
    rows = {}
    for cls in CLASSES + ["all"]:
        sel = [it for it in items if cls == "all" or cls_of[it["id"]] == cls]
        r_ids = [it["id"] for it in sel if it["source"] == "referee"]
        p_ids = [it["id"] for it in sel if it["source"] == "plumb"]
        rows[cls] = {
            "referee": len(r_ids),
            "also_raised": sum(1 for i in r_ids if matches[i]["strength"] != "none"),
            "plumb_only": sum(1 for i in p_ids if i not in matched_plumb),
            "referee_valid": share(r_ids, lambda a: a["correctness"] == "valid"),
            "plumb_valid": share(p_ids, lambda a: a["correctness"] == "valid"),
            "referee_serious": share(r_ids, lambda a: a["importance"] in SERIOUS),
            "plumb_serious": share(p_ids, lambda a: a["importance"] in SERIOUS),
        }

    # Agreement between the two raters on the held-out paper
    agreement = {"n": 0}
    second = next((r["answers"] for r in ratings.values() if r.get("rater") == "second"), None)
    if second:
        both = [i for i in second if i in primary and by_id.get(i, {}).get("paper") == heldout]

        def agree(field):
            return round(sum(1 for i in both if second[i][field] == primary[i][field]) / len(both), 3) if both else None
        agreement = {"n": len(both), "correctness": agree("correctness"), "importance": agree("importance")}
    same = sum(1 for it in items if it.get("class") == cls_of[it["id"]])
    class_agreement = {"n": len(items), "share": round(same / len(items), 3) if items else None}
    return {"rows": rows, "agreement": agreement, "class_agreement": class_agreement}


def _pct(x):
    return "--" if x is None else f"{round(100 * x)}\\%"


def latex(res):
    out = ["\\begin{tabular}{lrrrrrrr}", "\\toprule",
           " & Referee & Also raised & Plumb & \\multicolumn{2}{c}{Rated valid} & \\multicolumn{2}{c}{Rated serious} \\\\",
           "Class & points & by Plumb & only & Referee & Plumb & Referee & Plumb \\\\", "\\midrule"]
    for cls in CLASSES + ["all"]:
        r = res["rows"][cls]
        if cls == "all":
            out.append("\\midrule")
        out.append(f"{cls.capitalize()} & {r['referee']} & {r['also_raised']} & {r['plumb_only']} & "
                   f"{_pct(r['referee_valid'])} & {_pct(r['plumb_valid'])} & "
                   f"{_pct(r['referee_serious'])} & {_pct(r['plumb_serious'])} \\\\")
    out += ["\\bottomrule", "\\end{tabular}"]
    return "\n".join(out) + "\n"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--items", required=True)
    p.add_argument("--ratings", required=True)
    p.add_argument("--matches", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--summary")
    p.add_argument("--heldout", default="A", help="paper key of the held-out paper (default A)")
    a = p.parse_args(argv)

    def load(f):
        with open(f, encoding="utf-8") as fh:
            return json.load(fh)
    try:
        res = build(load(a.items), load(a.ratings), load(a.matches), a.heldout)
    except MissingData as e:
        print(f"table3: {e}", file=sys.stderr)
        return 2
    # SAVE
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(latex(res))
    if a.summary:
        with open(a.summary, "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=1)
    print(json.dumps(res["rows"]["all"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
