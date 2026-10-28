#!/usr/bin/env python3
"""Coverage counts from the coding sheet, and, when run folders are given, check-ins and cost from the run logs.

Usage:
  python3 count.py --sheet <coding_sheet.md> --out <counts.md>
      [--run B=<run folder> --run C=<run folder> --run D=<run folder> --repo <plumb checkout>]
The sheet has one section per paper, headed "## A", "## B", "## C" or "## D", each holding a Markdown table
whose header row starts with "id". Paper A is the held-out paper, scored on its capped run.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# PARAMS
PAPERS = ["A", "B", "C", "D"]  # coverage tables pool all four
HELDOUT = "A"
RUN_CLASS = re.compile(r"(?:V2|Capped) (MATCH|PARTIAL|MISSED|DROPPED)")
TYPES = ["verifiable (paper)", "verifiable (external)", "judgment"]
CLASSES = ["factual", "substantive judgment", "preference"]
WEAK_PARTIAL = re.compile(r"\(weak\)|[Gg]enerous partial|listed, not questioned")
SOURCES = {"both", "referees only", "Plumb only"}
VALIDITY = {"valid", "doubtful", "wrong"}
ER_VALUES = {"", "adds", "also", "weak", "only"}
JUDGMENT_STOPS = ("numbers", "read", "against", "majors", "minors", "draft")


# LOAD: parse the sheet's tables
def parse_sheet(path: Path) -> list[dict]:
    rows, paper, header = [], None, None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        m = re.match(r"^## ([A-D])\b", line)
        if m:
            paper, header = m.group(1), None
            continue
        if not line.startswith("|") or paper is None:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells[0] == "id":
            header = cells
            continue
        if set(line.replace("|", "").strip()) <= {"-"}:
            continue
        if header is None or len(cells) != len(header):
            raise SystemExit(f"malformed row in paper {paper} (row {len(rows) + 1})")
        rows.append({"paper": paper, **dict(zip(header, cells))})
    return rows


def check(rows: list[dict]) -> None:
    ids = Counter(r["id"] for r in rows)
    dup = [k for k, v in ids.items() if v > 1]
    if dup:
        raise SystemExit(f"duplicate ids: {dup}")
    for r in rows:
        if r["source"] not in SOURCES:
            raise SystemExit(f"{r['id']}: bad source {r['source']!r}")
        if r["type"] not in TYPES:
            raise SystemExit(f"{r['id']}: bad type {r['type']!r}")
        if r["class"] not in CLASSES:
            raise SystemExit(f"{r['id']}: bad class {r['class']!r}")
        if r["type"] == "judgment" and r["class"] == "factual":
            raise SystemExit(f"{r['id']}: judgment rows split into substantive judgment or preference only")
        if r["type"].startswith("verifiable") and r["class"] != "factual" and not r["class note"]:
            raise SystemExit(f"{r['id']}: verifiable row moved off factual needs a class note")
        if r["ER"] not in ER_VALUES:
            raise SystemExit(f"{r['id']}: bad ER {r['ER']!r}")
        val = r["validity (Plumb-only)"].split(":", 1)[0].strip()
        if r["source"] == "Plumb only":
            if val not in VALIDITY:
                raise SystemExit(f"{r['id']}: Plumb-only row needs a validity call")
        elif val:
            raise SystemExit(f"{r['id']}: validity given on a referee row")
        if r["source"] != "Plumb only" and not re.match(r"((V2|Capped) (MATCH|PARTIAL|MISSED|DROPPED)|Merges)", r["notes"]):
            raise SystemExit(f"{r['id']}: referee row note must start with the run class or 'Merges'")
        # Held-out paper only: its editor reader ran inside the run, so "only" on a referee row marks
        # output cover that comes solely from it
        if r["source"] != "Plumb only" and r["ER"] == "only" and (r["source"] != "both" or r["paper"] != HELDOUT):
            raise SystemExit(f"{r['id']}: ER 'only' on a referee row is allowed only for held-out rows the output raises")


def v2_class(r: dict) -> str:
    m = RUN_CLASS.search(r["notes"])
    if r["notes"].startswith("Merges") and "higher class" in r["notes"]:
        return "MATCH"
    return m.group(1) if m else "?"


# BUILD: coverage counts
def counts(rows: list[dict]) -> dict:
    ref = [r for r in rows if r["source"] != "Plumb only"]
    po = [r for r in rows if r["source"] == "Plumb only"]
    po_v2 = [r for r in po if r["ER"] != "only"]
    # base m1 leaves out held-out rows raised only through an editor reader finding; +ER puts them back
    base = [r for r in ref if r["source"] == "both" and r["ER"] != "only"]
    val = lambda rs: sum(r["validity (Plumb-only)"].startswith("valid") for r in rs)
    return {
        "M": len(ref),
        # m1 counts MATCH and every PARTIAL, weak partials included
        "m1": len(base),
        "m1_weak": sum(v2_class(r) == "PARTIAL" and bool(WEAK_PARTIAL.search(r["notes"])) for r in base),
        "m1_match": sum(v2_class(r) == "MATCH" for r in base),
        "m1_er": sum(r["source"] == "both" or r["ER"] == "adds" for r in ref),
        "m2": len(po_v2),
        "m2_er": len(po),
        "m3": val(po_v2),
        "m3_er": val(po),
        "doubtful": sum(r["validity (Plumb-only)"].startswith("doubtful") for r in po),
        "wrong": sum(r["validity (Plumb-only)"].startswith("wrong") for r in po),
    }


def pct(a: int, b: int) -> str:
    return f"{100 * a / b:.0f}%" if b else "n/a"


# BUILD: run logs (optional)
def _events(run: Path) -> list[dict]:
    return [json.loads(l) for l in (run / ".workspace/audit/events.jsonl").read_text().splitlines() if l.strip()]


def checkins(run: Path) -> dict:
    ev = _events(run)
    ci = [e for e in ev if e["kind"] == "checkin"]
    level = next((e["answer"] for e in ci if e.get("item") == "setup:level"), "?")
    judg = [e for e in ci if e.get("stop") in JUDGMENT_STOPS]
    by_stop = Counter(e["stop"] for e in judg)
    auto = Counter(e["stop"] for e in judg if str(e.get("note", "")).startswith("auto"))
    user = [e for e in judg if not str(e.get("note", "")).startswith("auto")]
    diverge = [e for e in judg if e.get("recommended") and str(e["answer"])[:1] != str(e["recommended"])[:1]]
    out = [e for e in ev if e["kind"] == "output"]
    return {"level": level, "by_stop": by_stop, "auto": auto, "user": user, "diverge": diverge,
            "qc_rulings": sum(e["kind"] == "qc_ruling" for e in ev), "output_ts": out[-1]["ts"] if out else None}


def override(run: Path, repo: Path) -> dict:
    p = subprocess.run([sys.executable, str(repo / "eval/override_rate.py"), str(run)],
                       capture_output=True, text=True, cwd=repo)
    if p.returncode != 0:
        raise SystemExit(f"override_rate failed for {run}: {p.stderr}")
    return json.loads(p.stdout.split("\n\n## override rate")[0])


def usage(run: Path, tz: ZoneInfo) -> dict:
    u = json.loads((run / ".workspace/usage.json").read_text())
    started = json.loads((run / ".workspace/run.json").read_text())["started"]
    return {"u": u, "started": datetime.fromisoformat(started).replace(tzinfo=tz)}


def hms(sec: float) -> str:
    sec = int(round(sec))
    return f"{sec // 3600}h {sec % 3600 // 60:02d}m"


def coverage_lines(rows: list[dict]) -> list[str]:
    L = ["## 1. Coverage", "",
         "M = distinct referee issues (editor and duplicate points merged). m1 = M also raised by Plumb: MATCH or PARTIAL, "
         "weak partials included. m2 = Plumb-only issues. m3 = m2 coded valid. \"+ER\" adds the editor reader findings. "
         "m1 and m2 are not additive: some Plumb-only issues also give partial cover to a referee row.", "",
         "| paper | M | m1 | m1 / M | m1 MATCH only | of m1, weak partials | m1 +ER | m2 | m3 | m2 +ER | m3 +ER | doubtful | wrong |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for p in PAPERS + ["Total"]:
        c = counts(rows if p == "Total" else [r for r in rows if r["paper"] == p])
        L.append(f"| {p} | {c['M']} | {c['m1']} | {pct(c['m1'], c['M'])} | {c['m1_match']} | {c['m1_weak']} | {c['m1_er']} | "
                 f"{c['m2']} | {c['m3']} | {c['m2_er']} | {c['m3_er']} | {c['doubtful']} | {c['wrong']} |")
    L += ["", "## 2. By class", "",
          "| paper | class | M | m1 | m1 / M | m1 MATCH only | m1 +ER | m2 | m3 | m2 +ER | m3 +ER | close calls |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for p in ["Total"] + PAPERS:
        sub = rows if p == "Total" else [r for r in rows if r["paper"] == p]
        for k in CLASSES + ["all"]:
            cs = sub if k == "all" else [r for r in sub if r["class"] == k]
            c = counts(cs)
            L.append(f"| {p} | {k} | {c['M']} | {c['m1']} | {pct(c['m1'], c['M'])} | {c['m1_match']} | {c['m1_er']} | "
                     f"{c['m2']} | {c['m3']} | {c['m2_er']} | {c['m3_er']} | {sum(bool(r['class note']) for r in cs)} |")
    L += ["", "| type | " + " | ".join(CLASSES) + " |", "|---|" + "---|" * len(CLASSES)]
    for t in TYPES:
        L.append(f"| {t} | " + " | ".join(str(sum(r['type'] == t and r['class'] == k for r in rows)) for k in CLASSES) + " |")
    L += ["", "## 3. By type", "",
          "| paper | type | M | m1 | m1 / M | m1 +ER | m2 | m3 | m2 +ER | m3 +ER |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for p in PAPERS + ["Total"]:
        sub = rows if p == "Total" else [r for r in rows if r["paper"] == p]
        for t in TYPES:
            c = counts([r for r in sub if r["type"] == t])
            L.append(f"| {p} | {t} | {c['M']} | {c['m1']} | {pct(c['m1'], c['M'])} | {c['m1_er']} | "
                     f"{c['m2']} | {c['m3']} | {c['m2_er']} | {c['m3_er']} |")
    L += ["", "Referee issues not in the run's output, by run class:", ""]
    for p in PAPERS:
        miss = [r for r in rows if r["paper"] == p and r["source"] == "referees only"]
        cl = Counter(v2_class(r) for r in miss)
        L.append(f"- {p}: {len(miss)} ({', '.join(f'{k} {v}' for k, v in sorted(cl.items()))}); "
                 f"editor reader adds {sum(r['ER'] == 'adds' for r in miss)}")
    return L


def run_lines(runs: dict, repo: Path, tz: ZoneInfo) -> list[str]:
    L = ["", "## 4. Check-ins", "",
         "| paper | check-in level | judgment-stop check-ins | taken by the tool (auto) | answered by the user | "
         "user overrules (override_rate.py) | auto answers off the recommendation | QC rulings logged |",
         "|---|---|---|---|---|---|---|---|"]
    for p, run in runs.items():
        ci, ov = checkins(run), override(run, repo)
        L.append(f"| {p} | {ci['level']} | {sum(ci['by_stop'].values())} | {sum(ci['auto'].values())} | {len(ci['user'])} | "
                 f"{ov['totals']['overrides']} of {ov['totals']['answers']} | {len(ci['diverge'])} | {ci['qc_rulings']} |")
    L += ["", "## 5. Wall time and cost per run", "",
          "| paper | wall clock, start to final output | active session time | agents | transcripts unreadable | "
          "API-equivalent cost | cost complete? | unpriced models |", "|---|---|---|---|---|---|---|---|"]
    for p, run in runs.items():
        us, ci = usage(run, tz), checkins(run)
        u = us["u"]
        wall = (datetime.fromisoformat(ci["output_ts"]) - us["started"]).total_seconds() if ci["output_ts"] else 0
        L.append(f"| {p} | {hms(wall)} | {hms(u['total']['seconds'])} | {u['agents']} | {u['missing_transcripts']} of {u['agents']} | "
                 f"${u['total']['cost_usd']:.2f} | {'yes' if u['total']['cost_complete'] else 'no (partial)'} | "
                 f"{', '.join(u['unpriced_models'])} |")
    return L


# OUTPUT
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sheet", required=True, help="the private coding sheet")
    ap.add_argument("--out", required=True, help="Markdown file to write")
    ap.add_argument("--run", action="append", default=[], metavar="PAPER=DIR", help="a run folder for one paper")
    ap.add_argument("--repo", help="a Plumb checkout, for eval/override_rate.py (needed with --run)")
    ap.add_argument("--tz", default="UTC", help="time zone of run.json 'started', which carries no offset")
    a = ap.parse_args(argv)
    rows = parse_sheet(Path(a.sheet))
    check(rows)
    L = ["# Referee comparison counts", "", "Generated by `count.py` from the coding sheet. Do not edit by hand.", ""]
    L += coverage_lines(rows)
    if a.run:
        if not a.repo:
            ap.error("--run needs --repo")
        runs = {}
        for spec in a.run:
            paper, _, path = spec.partition("=")
            if paper not in PAPERS or not path:
                ap.error(f"--run takes PAPER=DIR with PAPER in {PAPERS}")
            runs[paper] = Path(path)
        L += run_lines(runs, Path(a.repo), ZoneInfo(a.tz))
    Path(a.out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {a.out}: {len(rows)} sheet rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
