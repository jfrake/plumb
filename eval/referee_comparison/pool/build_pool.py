#!/usr/bin/env python3
"""Build items.json, the blind item pool, from the coding sheet and the hand-checked one-line texts.

Usage:
  python3 build_pool.py --sheet <coding_sheet.md> --texts-dir <folder with texts_A.json ... texts_D.json> \
      --config <pool_config.json> --letters <folder of decision letters> --out <items.json>

The letters are read only to check that no item copies six or more consecutive words from a letter.
The config is private, because it names the papers and records the coding of individual issues:
  {"titles": {"A": str, ...},                     paper titles shown on the rating page
   "letters": {"A": "<file name>", ...},          one decision letter PDF per paper, in --letters
   "er_adds": {"<referee row>": "<ER key>"},      editor-reader findings credited to a row the run missed
   "split_override": [["<paper>", "<issue>", "<key>"]],  issue numbers whose credit goes to a split half
   "nonp_class": {"<key>": "<class>"},            Plumb issues with no sheet row of their own
   "er_only_nonp": ["<key>", ...],                of those, the ones only the editor reader raised
   "heldout_referee_only_items": ["<issue>", ...]} held-out issue numbers matched without a sheet row
"""
import argparse
import json
import random
import re
import sys
from pathlib import Path

# PARAMS
SEED = 20261020
PAPERS = ["A", "B", "C", "D"]
HELDOUT = "A"
CELLS = 11
BANNED = [r"\bplumb\b", r"\breview(?:er|ers)\b", r"\breferee", r"\beditor", r"\bAI\b", r"\bagents?\b",
          r"\bseverity\b", r"\bminor\b", r"\bmajor\b", r"\bundermines\b", r"\bweakens\b",
          r"\bauthors?\b", r"\byou\b", r"\byour\b", r"\bI\b", r"\bwe\b", r"\bour\b",
          r"\bsuggest", r"\brecommend", r"\bwonder", r"\bmight consider\b", "\u2014", "\u2013"]


def fail(msg):
    raise SystemExit(f"ERROR: {msg}")


# LOAD: sheet rows
def parse_sheet(path):
    rows, paper = {}, None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        m = re.match(r"## ([A-D])\b", line)
        if m:
            paper = m.group(1)
        m = re.match(r"\| ([A-D]-[RP]\d\d) \|", line)
        if m:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) != CELLS:
                fail(f"{m.group(1)}: {len(cells)} cells")
            rid = cells[0]
            if not rid.startswith(paper + "-"):
                fail(f"{rid} under section {paper}")
            if rid in rows:
                fail(f"duplicate sheet row {rid}")
            rows[rid] = {"paper": paper, "source": cells[2], "class": cells[4],
                         "severity": cells[7], "er": cells[8]}
    return rows


def issue_numbers(sev):
    nums = []
    for grp in re.findall(r"\(([^)]*)\)", sev):
        if "ER:" in grp:
            continue
        nums += [x.strip() for x in grp.split(",") if x.strip()]
    return nums


def letter_ngrams(letter_dir, letters, n=6):
    import pdfplumber  # only needed for the letter-overlap check
    grams = {}
    for p, f in letters.items():
        with pdfplumber.open(Path(letter_dir) / f) as pdf:
            text = " ".join((pg.extract_text() or "") for pg in pdf.pages)
        toks = re.findall(r"[a-z0-9]+", text.lower().replace("\u2019", "'"))
        grams[p] = {tuple(toks[i:i + n]) for i in range(len(toks) - n + 1)}
    return grams


def link_keys(rows, cfg):
    """Every item key with its paper, source, class and editor-reader flag, and the referee-Plumb links."""
    er_adds = cfg["er_adds"]
    split = {(p, n): k for p, n, k in cfg["split_override"]}
    p_by_issue = {}
    for rid, r in rows.items():
        if "-P" in rid:
            for num in issue_numbers(r["severity"]):
                p_by_issue.setdefault((r["paper"], num), []).append(rid)
    keys = {}
    for rid, r in rows.items():
        src = "referee" if "-R" in rid else "plumb"
        if src == "plumb" and r["source"] != "Plumb only":
            fail(f"{rid}: source {r['source']}")
        keys[rid] = {"paper": r["paper"], "source": src, "class": r["class"],
                     "er_only": src == "plumb" and r["er"] == "only"}
    links = []
    for rid, r in rows.items():
        if "-R" not in rid:
            continue
        if r["er"] == "adds":
            if rid not in er_adds:
                fail(f"{rid}: ER adds row without an ER item")
            links.append((rid, er_adds[rid]))
        if r["source"] == "both":
            nums = issue_numbers(r["severity"])
            if not nums:
                fail(f"{rid}: both but no issue numbers")
            for num in nums:
                k = split.get((r["paper"], num))
                if k is None:
                    prow = p_by_issue.get((r["paper"], num), [])
                    if len(prow) > 1:
                        fail(f"{rid}: issue {num} maps to several P rows {prow}")
                    k = prow[0] if prow else f"{r['paper']}-issue-{num}"
                links.append((rid, k))
        elif r["source"] != "referees only":
            fail(f"{rid}: source {r['source']}")
    if set(er_adds) != {rid for rid, r in rows.items() if r["er"] == "adds"}:
        fail("ER adds rows do not match er_adds")
    for _, k in links:
        if k not in keys:
            if k not in cfg["nonp_class"]:
                fail(f"no class for {k}")
            keys[k] = {"paper": k.split("-")[0], "source": "plumb", "class": cfg["nonp_class"][k],
                       "er_only": k in set(cfg["er_only_nonp"])}
    if set(cfg["nonp_class"]) - set(keys):
        fail(f"unused nonp_class keys {set(cfg['nonp_class']) - set(keys)}")
    held = {k.split("-issue-")[1] for k in keys if k.startswith(f"{HELDOUT}-issue-")}
    if held != set(cfg["heldout_referee_only_items"]):
        fail(f"held-out matched non-row issues {sorted(held)} differ from the config's list")
    return keys, links


def text_problems(k, text, paper, grams):
    out = []
    n = len(text.split())
    if not 12 <= n <= 45:
        out.append(f"{k}: {n} words")
    for pat in BANNED:
        if re.search(pat, text, re.IGNORECASE if pat not in (r"\bI\b", r"\bAI\b") else 0):
            out.append(f"{k}: banned pattern {pat!r}")
    toks = re.findall(r"[a-z0-9]+", text.lower())
    if any(tuple(toks[i:i + 6]) in grams.get(paper, set()) for i in range(len(toks) - 5)):
        out.append(f"{k}: six-word overlap with the letter")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sheet", required=True)
    ap.add_argument("--texts-dir", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--letters", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    cfg = json.loads(Path(a.config).read_text(encoding="utf-8"))
    rows = parse_sheet(a.sheet)
    texts = {}
    for p in PAPERS:
        t = json.loads((Path(a.texts_dir) / f"texts_{p}.json").read_text(encoding="utf-8"))
        dup = set(t) & set(texts)
        if dup:
            fail(f"duplicate text keys {dup}")
        texts.update(t)

    # BUILD: keys and links
    keys, links = link_keys(rows, cfg)
    if set(keys) != set(texts):
        fail(f"keys without text {sorted(set(keys) - set(texts))}; texts without key {sorted(set(texts) - set(keys))}")

    # BUILD: ids, labels, items
    rng = random.Random(SEED)
    order = PAPERS[:]
    while order == PAPERS:
        rng.shuffle(order)
    label = {p: f"Paper {'ABCD'[i]}" for i, p in enumerate(order)}
    ids, used = {}, set()
    for k in sorted(keys):
        while True:
            h = f"i-{rng.getrandbits(24):06x}"
            if h not in used:
                used.add(h)
                ids[k] = h
                break
    match = {k: [] for k in keys}
    for x, y in links:
        if ids[y] not in match[x]:
            match[x].append(ids[y])
        if ids[x] not in match[y]:
            match[y].append(ids[x])

    grams = letter_ngrams(a.letters, cfg["letters"])
    problems, items = [], []
    for k, meta in keys.items():
        problems += text_problems(k, texts[k], meta["paper"], grams)
        items.append({"id": ids[k], "paper": meta["paper"], "paper_label": label[meta["paper"]],
                      "title": cfg["titles"][meta["paper"]], "text": texts[k], "source": meta["source"],
                      "class": meta["class"], "er_only": meta["er_only"], "match": match[k], "sheet_row": k})
    if problems:
        print("\n".join(problems))
        raise SystemExit(1)
    rng.shuffle(items)

    # SAVE
    Path(a.out).write_text(json.dumps(items, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for p in PAPERS:
        ps = [i for i in items if i["paper"] == p]
        ref = [i for i in ps if i["source"] == "referee"]
        print(f"{p}: referee {len(ref)} (matched {sum(bool(i['match']) for i in ref)}), plumb {len(ps) - len(ref)}")
    print("total", len(items))
    return 0


if __name__ == "__main__":
    sys.exit(main())
