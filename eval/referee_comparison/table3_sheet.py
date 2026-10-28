#!/usr/bin/env python3
"""Table 3 as reported: the referee points and the Plumb-only points (editor reader left out), by the coding
sheet's class, with the primary rater's blind ratings. Coverage counts come from count.py on the same sheet.

Usage:
  python3 table3_sheet.py --sheet <coding_sheet.md> --items <items.json> --ratings <ratings.json> \
      --out <table_3.tex> --summary <table3_sheet_summary.json>
The summary holds integers only; counts.json in this folder is that summary with the paper keys A to D.
"""
import argparse, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import count  # noqa: E402

CLASSES = ["factual", "substantive judgment", "preference"]
PAPERS = count.PAPERS


def stats(xs, answers):
    return {"n": len(xs), "valid": sum(answers[i["id"]]["correctness"] == "valid" for i in xs),
            "wrong": sum(answers[i["id"]]["correctness"] == "wrong" for i in xs),
            "serious": sum(answers[i["id"]]["importance"] != "Minor" for i in xs)}


def build(rows, items, answers):
    sheet = {r["id"]: r for r in rows}
    ref = [i for i in items if i["source"] == "referee"]
    po = [i for i in items if i["source"] == "plumb" and sheet.get(i["sheet_row"], {}).get("source") == "Plumb only"
          and sheet[i["sheet_row"]]["ER"] != "only"]
    cov = count.counts(rows)
    if (len(ref), len(po)) != (cov["M"], cov["m2"]):
        raise SystemExit(f"units do not match count.py: {len(ref)}/{cov['M']} referee, {len(po)}/{cov['m2']} Plumb only")
    for i in ref:
        assert i["class"] == sheet[i["sheet_row"]]["class"], i["id"]
    res = {"rows": {}, "by_paper": {}}
    for cls in CLASSES + ["all"]:
        sel = lambda xs: [i for i in xs if cls == "all" or i["class"] == cls]
        res["rows"][cls] = {"referee": stats(sel(ref), answers), "plumb_only": stats(sel(po), answers),
                            "also_raised": count.counts([r for r in rows if cls == "all" or r["class"] == cls])["m1"]}
    for pp in PAPERS:
        res["by_paper"][pp] = {"referee": stats([i for i in ref if i["paper"] == pp], answers),
                               "plumb_only": stats([i for i in po if i["paper"] == pp], answers)}
    return res


def latex(res):
    pct = lambda s, k: f"{round(100 * s[k] / s['n'])}\\%" if s["n"] else "--"
    out = ["\\begin{tabular}{lrrrcc}", "\\toprule",
           "Class & Referee points & Also raised by Plumb & Plumb only & Rated valid & Rated serious \\\\",
           " & & & & (referee / Plumb only) & (referee / Plumb only) \\\\", "\\midrule"]
    for cls in CLASSES + ["all"]:
        r = res["rows"][cls]; R, P = r["referee"], r["plumb_only"]
        if cls == "all":
            out.append("\\midrule")
        name = "All issues" if cls == "all" else cls.capitalize()
        out.append(f"{name} & {R['n']} & {r['also_raised']} ({round(100 * r['also_raised'] / R['n'])}\\%) & {P['n']} & "
                   f"{pct(R, 'valid')} / {pct(P, 'valid')} & {pct(R, 'serious')} / {pct(P, 'serious')} \\\\")
    out += ["\\bottomrule", "\\end{tabular}"]
    return "\n".join(out) + "\n"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sheet", required=True)
    p.add_argument("--items", required=True)
    p.add_argument("--ratings", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--summary", required=True)
    a = p.parse_args(argv)

    # INPUTS
    rows = count.parse_sheet(Path(a.sheet))
    count.check(rows)
    items = json.loads(Path(a.items).read_text(encoding="utf-8"))
    ratings = json.loads(Path(a.ratings).read_text(encoding="utf-8"))
    primary = [r["answers"] for r in ratings.values() if r.get("rater") == "primary"]
    if len(primary) != 1:
        raise SystemExit("the ratings file needs exactly one document labelled primary")

    # MAIN and SAVE
    res = build(rows, items, primary[0])
    Path(a.out).write_text(latex(res))
    Path(a.summary).write_text(json.dumps(res, indent=1))
    print(latex(res))
    print(json.dumps(res["by_paper"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
