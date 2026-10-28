#!/usr/bin/env python3
"""Find the PDF page and a bounding box for each issue.

Usage:
    python3 locate_issues.py <pdf> <issues.json> <locations.json>
    python3 locate_issues.py --page-offset <pdf>

<issues.json> is a JSON list of issue records. Each needs "id" and may carry "excerpt" (text
copied from the paper), "ms_page" (the page as the paper prints it), and "pdf_page" (a PDF page
already known, 1-based). <locations.json> maps each id to
{"pdf_page", "rect", "rects", "method", "label"}. method is one of exact, page_only,
approximate, not_found.

With --page-offset, print the fitted offset (PDF page minus printed page) as JSON: an integer,
or null when no single offset is seen on at least two pages.

Exit codes: 0 written; 2 the PDF or the issues file could not be read.
"""
from __future__ import annotations

import collections
import json
import re
import sys
import unicodedata
from pathlib import Path

FIRST_WORDS = 12
MIN_WORDS = 4


def key(word: str) -> str:
    """A comparison key: ligatures expanded, case folded, punctuation and quotes removed."""
    w = unicodedata.normalize("NFKC", word).casefold()
    return re.sub(r"[\W_]+", "", w)


def needle_keys(text: str) -> list:
    return [k for k in (key(w) for w in text.split()) if k]


def page_tokens(page) -> list:
    """(key, rect) per word, with a word hyphenated across a line end joined into one."""
    import pymupdf
    out = []
    words = page.get_text("words")
    i = 0
    while i < len(words):
        x0, y0, x1, y1, text, block, line, _ = words[i][:8]
        rect = pymupdf.Rect(x0, y0, x1, y1)
        rects = [rect]
        while (text.endswith("-") and i + 1 < len(words)
               and (words[i + 1][5], words[i + 1][6]) != (block, line)):
            i += 1
            nxt = words[i]
            text = text[:-1] + nxt[4]
            rects.append(pymupdf.Rect(nxt[:4]))
            block, line = nxt[5], nxt[6]
        k = key(text)
        if k:
            out.append((k, rects))
        i += 1
    return out


def find_on_page(tokens: list, keys: list):
    """Rects of the first run of tokens whose keys equal `keys`, or None."""
    n = len(keys)
    if n == 0:
        return None
    for s in range(len(tokens) - n + 1):
        if all(tokens[s + j][0] == keys[j] for j in range(n)):
            rects = []
            for _, rs in tokens[s:s + n]:
                rects.extend(rs)
            return rects
    return None


def find_across_page_break(tokens_a: list, tokens_b: list, keys: list):
    """Rects on tokens_a's page for the first run of tokens that starts in tokens_a and
    continues into tokens_b, or None if no such crossing run matches keys. A run fully
    contained in tokens_a or fully contained in tokens_b is not a crossing run and is
    left for find_on_page to report from its own page."""
    n = len(keys)
    if n == 0:
        return None
    na = len(tokens_a)
    combined_keys = [t[0] for t in tokens_a] + [t[0] for t in tokens_b]
    for s in range(na):
        if s + n <= na or s + n > len(combined_keys):
            continue
        if all(combined_keys[s + j] == keys[j] for j in range(n)):
            rects = []
            for idx in range(s, na):
                rects.extend(tokens_a[idx][1])
            return rects
    return None


def candidates(excerpt: str) -> list:
    """The full excerpt, then its first 12 words, then its longest sentence."""
    out = []
    full = needle_keys(excerpt)
    if full:
        out.append(full)
    if len(full) > FIRST_WORDS:
        out.append(full[:FIRST_WORDS])
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", excerpt.strip()) if s]
    if len(sentences) > 1:
        longest = needle_keys(max(sentences, key=lambda s: len(s.split())))
        if len(longest) >= MIN_WORDS and longest not in out:
            out.append(longest)
    return out


def line_rects(rects: list) -> list:
    """Merge word rects that share a line into one rect per line."""
    lines = []
    for r in rects:
        for i, l in enumerate(lines):
            if abs(l.y0 - r.y0) < 2 and abs(l.y1 - r.y1) < 2:
                lines[i] = l | r
                break
        else:
            lines.append(r)
    return lines


def printed_number(page):
    """The page number printed in the page's top or bottom lines, or None."""
    lines = [l.strip() for l in page.get_text().splitlines() if l.strip()]
    for l in lines[:2] + lines[-2:]:
        if re.fullmatch(r"\d{1,4}", l):
            return int(l)
    return None


def fitted_offset(doc):
    """One constant offset (PDF page minus printed page) seen on at least two pages, or None."""
    offsets = collections.Counter()
    for i, page in enumerate(doc):
        n = printed_number(page)
        if n is not None:
            offsets[(i + 1) - n] += 1
    if not offsets:
        return None
    off, count = offsets.most_common(1)[0]
    return off if count >= 2 else None


def ms_to_pdf(doc, ms_page, offset):
    """(pdf_page, method) for a printed page number, or (None, "not_found")."""
    if ms_page is None or str(ms_page).strip() == "":
        return None, "not_found"
    label = str(ms_page).strip()
    if doc.get_page_labels():
        hits = doc.get_page_numbers(label)
        if hits:
            return hits[0] + 1, "page_only"
    if not label.isdigit():
        return None, "not_found"
    n = int(label)
    if offset is not None and 1 <= n + offset <= doc.page_count:
        return n + offset, "page_only"
    if 1 <= n <= doc.page_count:
        return n, "approximate"
    return None, "not_found"


def page_label(ms_page, pdf_page, method) -> str:
    if pdf_page is None:
        return "location not found"
    pdf = f"PDF p. {pdf_page}" + (", approximate" if method == "approximate" else "")
    if ms_page is None or str(ms_page).strip() == "":
        return pdf
    if method != "approximate" and str(ms_page).strip() == str(pdf_page):
        return f"p. {pdf_page}"
    return f"ms p. {str(ms_page).strip()} ({pdf})"


def locate(doc, issue: dict, tokens_by_page: list, offset) -> dict:
    ms_page = issue.get("ms_page")
    known = issue.get("pdf_page")
    mapped, map_method = ms_to_pdf(doc, ms_page, offset)
    target = known or mapped
    excerpt = (issue.get("excerpt") or "").strip()
    for keys in candidates(excerpt) if excerpt else []:
        pages = []
        for i, toks in enumerate(tokens_by_page):
            rects = find_on_page(toks, keys)
            if rects is not None:
                pages.append((i + 1, rects))
        for i in range(len(tokens_by_page) - 1):
            rects = find_across_page_break(tokens_by_page[i], tokens_by_page[i + 1], keys)
            if rects is not None:
                pages.append((i + 1, rects))
        if pages:
            if target is not None:
                pages.sort(key=lambda pr: abs(pr[0] - target))
            pdf_page, rects = pages[0]
            lines = line_rects(rects)
            union = lines[0]
            for l in lines[1:]:
                union = union | l
            return {"pdf_page": pdf_page, "rect": [round(v, 2) for v in union],
                    "rects": [[round(v, 2) for v in l] for l in lines], "method": "exact",
                    "label": page_label(ms_page, pdf_page, "exact")}
    if known:
        method = "page_only"
    else:
        method = map_method
    return {"pdf_page": target, "rect": None, "rects": [], "method": method,
            "label": page_label(ms_page, target, method)}


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) == 2 and args[0] == "--page-offset":
        import pymupdf
        try:
            doc = pymupdf.open(args[1])
        except (RuntimeError, OSError, ValueError) as exc:
            print(f"Could not read the input: {exc}")
            return 2
        print(json.dumps(fitted_offset(doc)))
        return 0
    if len(args) != 3:
        print("Usage: locate_issues.py <pdf> <issues.json> <locations.json> | --page-offset <pdf>")
        return 2
    import pymupdf
    try:
        doc = pymupdf.open(args[0])
        issues = json.loads(Path(args[1]).read_text(encoding="utf-8"))
    except (RuntimeError, OSError, ValueError) as exc:
        print(f"Could not read the input: {exc}")
        return 2
    tokens_by_page = [page_tokens(p) for p in doc]
    offset = fitted_offset(doc)
    out = {str(i["id"]): locate(doc, i, tokens_by_page, offset) for i in issues}
    Path(args[2]).parent.mkdir(parents=True, exist_ok=True)
    Path(args[2]).write_text(json.dumps(out, indent=2), encoding="utf-8")
    counts = collections.Counter(v["method"] for v in out.values())
    print(json.dumps({m: counts.get(m, 0) for m in ("exact", "page_only", "approximate", "not_found")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
