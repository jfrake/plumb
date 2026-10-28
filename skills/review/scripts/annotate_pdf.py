#!/usr/bin/env python3
"""Write a copy of the paper with each issue pinned to its place. The original is never changed.

Usage:
    python3 annotate_pdf.py <pdf> <issues.json> <locations.json> <out.pdf>
    python3 annotate_pdf.py --check <annotated.pdf>

<issues.json> is a JSON list of issue records ("id", "title", "severity", "summary"), in the
order the index lists them. <locations.json> is what locate_issues.py writes. The copy starts
with index pages that link to each issue's page. Each issue is a highlight with a note, colored
by severity. An issue whose exact spot was not found gets a note at the top of its page; one
whose page was not found appears only in the index.

Exit codes: 0 written; 2 bad input (unreadable PDF or JSON, or <out.pdf> is the input PDF).
With --check: 0 when the file exists, opens as a PDF, and its first page is the index (it carries
the disclosure line); 1 otherwise, with the reason.
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

COLORS = {
    "Undermines the main claim": (1.0, 0.6, 0.6),
    "Weakens a claim": (1.0, 0.8, 0.5),
    "Minor": (1.0, 0.95, 0.5),
}
DEFAULT_COLOR = COLORS["Minor"]
DISCLOSURE = "Notes produced with Plumb, an AI review tool."
TITLE = "Plumb notes: where each issue is"
MARGIN, FONT_SIZE, LINE, INDENT = 54, 10, 15, 18
NOTE_STEP = 22
# PyMuPDF's base-14 fonts cover only Latin-1; titles and labels can carry curly quotes, en
# dashes, Greek letters, or math symbols, so index pages draw with this bundled Unicode font.
UNICODE_FONT = "cjk"
FONT_ALIAS = "plumbuni"


def color(severity) -> tuple:
    return COLORS.get(severity or "", DEFAULT_COLOR)


def note_text(issue: dict, extra: str = "") -> str:
    head = f"{issue['id']}. {issue.get('severity') or 'Minor'}."
    body = (issue.get("summary") or "").strip()
    return " ".join(p for p in (head, body, extra) if p)


def wrap(text: str, width: float, fontsize: float = FONT_SIZE, font=None) -> list:
    """Break text into lines no wider than `width` points, at spaces. A word wider than the line
    is cut. `font`, a pymupdf.Font, measures with the same metrics used to draw the text; the
    default (None) measures with PyMuPDF's built-in Helvetica, for callers that only need width."""
    import pymupdf
    measure = font.text_length if font is not None else (lambda s, fs: pymupdf.get_text_length(s, fontsize=fs))
    fits = lambda s: measure(s, fontsize) <= width
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}" if cur else word
        if fits(trial):
            cur = trial
            continue
        if cur:
            lines.append(cur)
        while not fits(word):
            n = len(word) - 1
            while n > 1 and not fits(word[:n]):
                n -= 1
            lines.append(word[:n])
            word = word[n:]
        cur = word
    if cur:
        lines.append(cur)
    return lines or [""]


def _flatten_label(label: str) -> str:
    """Turn a label like 'ms p. X (PDF p. Y[, approximate])' into 'ms p. X, PDF p. Y[,
    approximate]', so wrapping it in the index line's own parentheses doesn't nest ((...))."""
    return re.sub(r"\s\(([^()]*)\)$", r", \1", label)


def index_line(issue: dict, loc: dict) -> str:
    title = (issue.get("title") or "").strip()
    if loc.get("pdf_page") is None:
        where = "location not found"
    else:
        where = _flatten_label(loc.get("label") or "location not found")
    return f"{issue['id']}. {issue.get('severity') or 'Minor'}: {title} ({where})"


def annotate(pdf: Path, issues: list, locations: dict, out: Path) -> dict:
    import pymupdf
    doc = pymupdf.open(str(pdf))
    width, height = doc[0].rect.width, doc[0].rect.height
    n_pages = doc.page_count
    font = pymupdf.Font(UNICODE_FONT)
    rows = max(1, int((height - 2 * MARGIN) // LINE) - 3)
    # Each issue's index entry, wrapped; an entry never splits across index pages.
    pages, cur, used = [], [], 0
    for issue in issues:
        loc = locations.get(str(issue["id"]), {})
        lines = wrap(index_line(issue, loc), width - 2 * MARGIN - INDENT, font=font)
        if cur and used + len(lines) > rows:
            pages.append(cur)
            cur, used = [], 0
        cur.append((issue, loc, lines))
        used += len(lines)
    pages.append(cur)
    n_index = len(pages)
    for k in range(n_index):
        doc.new_page(pno=k, width=width, height=height)
    placed = {"highlight": 0, "page_note": 0, "index_only": 0}
    for k, entries in enumerate(pages):
        page = doc[k]
        page.insert_font(fontname=FONT_ALIAS, fontbuffer=font.buffer)
        y = MARGIN + FONT_SIZE
        page.insert_text((MARGIN, y), TITLE if k == 0 else TITLE + " (continued)", fontsize=12, fontname=FONT_ALIAS)
        y += LINE
        page.insert_text((MARGIN, y), DISCLOSURE, fontsize=FONT_SIZE, fontname=FONT_ALIAS)
        y += 2 * LINE
        for issue, loc, lines in entries:
            top = y
            for j, text in enumerate(lines):
                page.insert_text((MARGIN + (INDENT if j else 0), y), text, fontsize=FONT_SIZE, color=(0, 0, 0),
                                  fontname=FONT_ALIAS)
                y += LINE
            target = loc.get("pdf_page")
            if target is not None and 1 <= target <= n_pages:
                hit = pymupdf.Rect(MARGIN, top - FONT_SIZE, width - MARGIN, y - LINE + 3)
                page.insert_link({"kind": pymupdf.LINK_GOTO, "from": hit,
                                  "page": target - 1 + n_index, "to": pymupdf.Point(0, 0)})
    notes_on_page = collections.Counter()
    for issue in issues:
        loc = locations.get(str(issue["id"]), {})
        target = loc.get("pdf_page")
        if target is None or not 1 <= target <= n_pages:
            placed["index_only"] += 1
            continue
        page_index = target - 1 + n_index
        page = doc[page_index]
        rects = [pymupdf.Rect(r) for r in (loc.get("rects") or ([loc["rect"]] if loc.get("rect") else []))]
        if rects:
            annot = page.add_highlight_annot(rects)
            content = note_text(issue)
            placed["highlight"] += 1
        else:
            # Further notes on the same page step across so they don't stack on one icon.
            n = notes_on_page[page_index]
            notes_on_page[page_index] += 1
            point = pymupdf.Point(MARGIN / 2 + n * NOTE_STEP, MARGIN / 2)
            annot = page.add_text_annot(point, "")
            content = note_text(issue, "(exact spot not found)")
            placed["page_note"] += 1
        annot.set_colors(stroke=color(issue.get("severity")))
        annot.set_info(title="Plumb", content=content)
        annot.update()
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.subset_fonts()  # keep only the glyphs actually used, not the whole bundled CJK font
    doc.save(str(out), garbage=3, deflate=True)
    return placed


def check(path: Path) -> str:
    """The reason an annotated PDF fails its final check, or "" when it passes."""
    import pymupdf
    if not path.is_file():
        return f"{path.name} does not exist."
    try:
        doc = pymupdf.open(str(path))
        first = doc[0].get_text() if doc.page_count else ""
    except (RuntimeError, ValueError) as exc:
        return f"{path.name} cannot be opened as a PDF: {exc}"
    if DISCLOSURE not in " ".join(first.split()):
        return f"{path.name} does not start with the index page."
    return ""


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) == 2 and args[0] == "--check":
        reason = check(Path(args[1]))
        print(reason or "OK")
        return 1 if reason else 0
    if len(args) != 4:
        print("Usage: annotate_pdf.py <pdf> <issues.json> <locations.json> <out.pdf>")
        return 2
    pdf, out = Path(args[0]), Path(args[3])
    if out.resolve() == pdf.resolve():
        print("The output must be a new file. Plumb never changes the original PDF.")
        return 2
    try:
        issues = json.loads(Path(args[1]).read_text(encoding="utf-8"))
        locations = json.loads(Path(args[2]).read_text(encoding="utf-8"))
        placed = annotate(pdf, issues, locations, out)
    except (RuntimeError, OSError, ValueError) as exc:
        print(f"Could not write the annotated PDF: {exc}")
        return 2
    print(json.dumps(placed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
