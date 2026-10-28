"""Build the owner-only match data: one entry per referee item, with the paper's Plumb items as candidates.

Proposed strength comes from the referee row in the coding sheet: "Capped MATCH"/"Capped PARTIAL" for the
held-out paper, otherwise the first MATCH or PARTIAL in the row. A matched row with neither word is partial.

Usage: python3 build_matchdata.py <items.json> <coding_sheet.md> <matchdata.json>
"""
import json, re, sys


def sheet_rows(path):
    rows = {}
    for line in open(path, encoding="utf-8"):
        m = re.match(r"\|\s*([A-D]-R\d+[a-z]?)\s*\|", line)
        if m:
            rows[m.group(1)] = line
    return rows


def strength(row, has_match):
    if not has_match:
        return "none"
    m = re.search(r"Capped (MATCH|PARTIAL)", row or "") or re.search(r"\b(MATCH|PARTIAL)\b", row or "")
    return {"MATCH": "full", "PARTIAL": "partial"}[m.group(1)] if m else "partial"


def build(items, rows):
    plumb_by_paper = {}
    for it in items:
        if it["source"] == "plumb":
            plumb_by_paper.setdefault(it["paper"], []).append({"id": it["id"], "text": it["text"]})
    out = {}
    for it in items:
        if it["source"] != "referee":
            continue
        out[it["id"]] = {"paper_label": it["paper_label"], "ref_text": it["text"],
                         "candidates": plumb_by_paper.get(it["paper"], []), "proposed": it["match"],
                         "proposed_strength": strength(rows.get(it["sheet_row"]), bool(it["match"]))}
    return out


if __name__ == "__main__":
    items = json.load(open(sys.argv[1], encoding="utf-8"))
    out = build(items, sheet_rows(sys.argv[2]))
    with open(sys.argv[3], "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    from collections import Counter
    print(len(out), Counter(v["proposed_strength"] for v in out.values()))
