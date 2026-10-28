#!/usr/bin/env python3
"""Write a LaTeX booktabs table of recall on a planted fixture, by error kind and by severity.

Usage:
    python3 eval/table2.py <score.json> --out <table.tex>

<score.json> is the scorecard from `eval/score_fixture.py ... --out score.json`. Every must_catch
row must carry a `kind` (from the fixture's expected.yaml); the kinds are the five in the
planted-1 README. The table note states how many catches were matched by signature.

Exit codes: 0 written; 2 the scorecard is missing or malformed (the message names it).
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

# The planted-1 README's five error kinds, in its order.
KINDS = (
    ("text_table", "Text number does not match its table"),
    ("star", "Significance star not supported"),
    ("arithmetic", "Arithmetic within a table does not hold"),
    ("citation", "Citation to a nonexistent work"),
    ("design", "Archival design error"),
)
SEVERITIES = ("Undermines the main claim", "Weakens a claim", "Minor")


class TableError(Exception):
    """The scorecard is missing or has the wrong shape."""


def load_rows(path) -> list:
    f = Path(path)
    if not f.is_file():
        raise TableError(f"{f} is missing.")
    try:
        card = json.loads(f.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise TableError(f"{f} is not valid JSON: {exc}")
    rows = card.get("must_catch") if isinstance(card, dict) else None
    if not isinstance(rows, list) or not rows:
        raise TableError(f"{f} has no must_catch rows.")
    known = {k for k, _ in KINDS}
    for n, r in enumerate(rows):
        if not isinstance(r, dict) or r.get("result") not in ("caught", "missed"):
            raise TableError(f"{f}: must_catch[{n}] has no caught/missed result.")
        if r.get("kind") not in known:
            raise TableError(f"{f}: must_catch[{n}] kind {r.get('kind')!r} is not one of {sorted(known)}; "
                             "add `kind` to the fixture's expected.yaml and score again.")
        if r.get("severity") not in SEVERITIES:
            raise TableError(f"{f}: must_catch[{n}] severity {r.get('severity')!r} is not one of {list(SEVERITIES)}.")
    return rows


def _count(rows, pred) -> tuple:
    sel = [r for r in rows if pred(r)]
    return len(sel), sum(r["result"] == "caught" for r in sel)


def _line(label: str, planted: int, caught: int) -> str:
    return f"{label} & {planted} & {caught} & {caught / planted:.3f} \\\\"


def render(rows: list) -> str:
    """The table as LaTeX text."""
    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Recall on the planted archival test paper}",
        r"\label{tab:recall_planted}",
        r"\begin{threeparttable}",
        r"\begin{tabular}{lrrr}",
        r"\toprule",
        r" & Planted & Caught & Recall \\",
        r"\midrule",
        r"\multicolumn{4}{l}{\textit{By error kind}} \\",
    ]
    for key, label in KINDS:
        planted, caught = _count(rows, lambda r, k=key: r["kind"] == k)
        if planted:
            lines.append(_line(label, planted, caught))
    lines += [r"\midrule", r"\multicolumn{4}{l}{\textit{By severity}} \\"]
    for sev in SEVERITIES:
        planted, caught = _count(rows, lambda r, s=sev: r["severity"] == s)
        if planted:
            lines.append(_line(sev, planted, caught))
    planted, caught = _count(rows, lambda r: True)
    lines += [r"\midrule", _line("All planted errors", planted, caught), r"\bottomrule", r"\end{tabular}"]
    by_sig = sum(r["result"] == "caught" and r.get("strategy") == "signature" for r in rows)
    note = (r"\textit{Note:} Recall is caught divided by planted. "
            f"{by_sig} of {caught} catches were matched by signature: an issue counts as catching a planted "
            "error only if its text matches a regular expression in the answer key that names the planted "
            "change and it sits within one page of the error or on a page the key lists.")
    lines += [r"\begin{tablenotes}[flushleft]", r"\footnotesize", f"\\item {note}", r"\end{tablenotes}",
              r"\end{threeparttable}", r"\end{table}"]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("score", help="scorecard JSON from eval/score_fixture.py --out")
    ap.add_argument("--out", required=True, help="where to write the .tex table")
    args = ap.parse_args(argv)
    try:
        rows = load_rows(args.score)
    except TableError as exc:
        print(f"table2: {exc}", file=sys.stderr)
        return 2
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(rows), encoding="utf-8")
    print(f"table2: wrote {out} ({len(rows)} planted errors)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
