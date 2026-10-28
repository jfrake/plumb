#!/usr/bin/env python3
"""Check a paper's own reference list: does each cited work exist, with matching authors and year?

A thin wrapper over verify_citations.py. It reads the reference section from the PDF's text
layer, writes the entries in the plain-text REFERENCES form verify_citations.py parses, and
runs the same lookups (Crossref, Semantic Scholar, OpenAlex). The body has no citations, so
the dangling-citation check finds nothing.

Usage:
    python3 check_reference_list.py <pdf> <output.md> [mailto]

Exit codes:
    0  every listed work was found with matching authors
    1  at least one work was not found or its authors do not match (findings about the paper)
    2  the lookups could not run (network trouble), or no reference section was found
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_citations as vc  # noqa: E402

HEADING = re.compile(r"^\s*(references|bibliography|works cited|literature cited)\s*$", re.I)
STOP = re.compile(r"^\s*(appendix|online appendix|supplementary|tables?|figures?)\b", re.I)
PARTICLE = r"(?:van|von|de|der|den|del|della|di|da|le|la|du|ten|ter)"
NAME = r"[A-Z][A-Za-z'’\-]+"
# "Surname, J." or "Surname, Jane" (optionally with particles or several capitalized words).
ENTRY_START = re.compile(rf"^(?:{PARTICLE}\s+)*{NAME}(?:\s+{NAME})*,\s*(?:[A-Z]\.|[A-Z][a-z])")
YEAR = re.compile(r"\b(?:19|20)\d{2}[a-z]?\b")


def split_entries(lines: list) -> list:
    """Join wrapped lines into entries. A line starts a new entry only when it looks like
    'Surname, X' and the entry so far already has a year, so a wrapped author list stays whole."""
    entries, cur = [], []
    for line in lines:
        s = line.strip()
        if not s or s.isdigit():
            continue
        if ENTRY_START.match(s) and cur and YEAR.search(" ".join(cur)):
            entries.append(" ".join(cur))
            cur = [s]
        else:
            cur.append(s)
    if cur:
        entries.append(" ".join(cur))
    return entries


def reference_entries(pdf_path) -> list:
    import pymupdf
    doc = pymupdf.open(str(pdf_path))
    lines = []
    for page in doc:
        lines.extend(page.get_text().splitlines())
    starts = [i for i, line in enumerate(lines) if HEADING.match(line)]
    if not starts:
        return []
    body = []
    for line in lines[starts[0] + 1:]:
        if STOP.match(line):
            break
        body.append(line)
    return split_entries(body)


def main(argv: list | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) < 2:
        print("Usage: check_reference_list.py <pdf> <output.md> [mailto]")
        return 2
    pdf, out = Path(args[0]), Path(args[1])
    if len(args) > 2:
        vc.MAILTO = args[2]
    out.parent.mkdir(parents=True, exist_ok=True)
    entries = reference_entries(pdf)
    if not entries:
        out.write_text("# Reference List Check\n\nNo reference section was found in the PDF text, "
                       "so no works were looked up.\n", encoding="utf-8")
        print("No reference section found")
        return 2
    listing = out.parent / "reference_list_input.txt"
    listing.write_text("REFERENCES\n\n" + "\n\n".join(entries) + "\n", encoding="utf-8")
    return vc.verify_references(str(listing), str(out))


if __name__ == "__main__":
    sys.exit(main())
