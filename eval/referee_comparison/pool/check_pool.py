"""Validate the blind item pool: labels, lengths, matches, and no source cues in item text.

Usage: python3 check_pool.py <items.json>   (exit 0 when valid, 1 otherwise)
"""
import json, re, sys

CLASSES = {"factual", "substantive judgment", "preference"}
SOURCES = {"referee", "plumb"}
PAPERS = {"A", "B", "C", "D"}
CUES = [r"\bplumb\b", r"\bthe authors? should\b", r"\bI (?:would|suggest|recommend)\b", r"\breviewer\b",
        r"\breferee\b", r"\bagent\b", r"\bundermines the main claim\b", r"\bweakens a claim\b",
        r"\b[a-z]+-[a-z]+ (?:check|agent)\b", r"\bcheck id\b", r"\bstage \d\b", r"\[\w+:\w+\]"]


def validate(items):
    errs, by_id = [], {}
    for it in items:
        iid = it.get("id", "?")
        if iid in by_id:
            errs.append(f"{iid}: duplicate id")
        by_id[iid] = it
        if not re.fullmatch(r"i-[0-9a-f]{6}", iid):
            errs.append(f"{iid}: id must be i-<6 hex>")
        if it.get("source") not in SOURCES:
            errs.append(f"{iid}: bad source {it.get('source')!r}")
        if it.get("class") not in CLASSES:
            errs.append(f"{iid}: bad class {it.get('class')!r}")
        if it.get("paper") not in PAPERS:
            errs.append(f"{iid}: bad paper {it.get('paper')!r}")
        text = it.get("text", "")
        n = len(text.split())
        if not 12 <= n <= 45:
            errs.append(f"{iid}: text has {n} words; use 12 to 45")
        for cue in CUES:
            if re.search(cue, text, re.IGNORECASE):
                errs.append(f"{iid}: source cue {cue!r} in text")
                break
    for iid, it in by_id.items():
        for m in it.get("match", []):
            other = by_id.get(m)
            if other is None:
                errs.append(f"{iid}: match {m} not in pool")
                continue
            if other.get("paper") != it.get("paper"):
                errs.append(f"{iid}: match {m} is on another paper")
            if other.get("source") == it.get("source"):
                errs.append(f"{iid}: match {m} has the same source")
            if iid not in other.get("match", []):
                errs.append(f"{iid}: match {m} is not mutual")
    return errs


if __name__ == "__main__":
    errs = validate(json.load(open(sys.argv[1], encoding="utf-8")))
    print("\n".join(errs) or "OK")
    sys.exit(1 if errs else 0)
