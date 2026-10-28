#!/usr/bin/env python3
"""Find pages that carry table captions and render them to PNG for transcription.

index.json holds one entry per table: a table continued across pages (the same
table number on consecutive pages, or a caption that says "continued") is one
entry whose "pages" and "images" list every page, so one transcriber pair reads
all of it into one CSV. "page" and "image" name the entry's first page.
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

import pymupdf

CAPTION = re.compile(r"^\s*Table\s+([A-Z]?\d+[A-Za-z]?)\b", re.M | re.I)
CONTINUED = re.compile(r"^\s*Table\s+([A-Z]?\d+[A-Za-z]?)\b[^\n]*\bcontinued\b", re.M | re.I)


def caption_pages(pdf) -> list:
    found = []
    with pymupdf.open(pdf) as doc:
        for i, page in enumerate(doc):
            text = page.get_text()
            labels = sorted(set(CAPTION.findall(text)), key=str)
            if labels:
                found.append({"page": i + 1, "labels": labels,
                              "continued": sorted(set(CONTINUED.findall(text)), key=str)})
    return found


def group_tables(found: list) -> list:
    """Merge continuation pages into the entry of the table they continue."""
    entries = []
    for f in found:
        target = None
        for label in f["labels"]:
            for e in reversed(entries):
                if label in e["labels"] and (label in f["continued"] or f["page"] == e["pages"][-1] + 1):
                    target = e
                    break
            if target:
                break
        if target:
            target["pages"].append(f["page"])
            target["labels"] = sorted(set(target["labels"]) | set(f["labels"]), key=str)
        else:
            entries.append({"page": f["page"], "pages": [f["page"]], "labels": list(f["labels"])})
    return entries


def render(pdf, out_dir: Path, entries: list, dpi: int) -> tuple:
    out_dir.mkdir(parents=True, exist_ok=True)
    with pymupdf.open(pdf) as doc:
        num_pages = len(doc)
        for e in entries:
            e["images"] = []
            for page_num in e["pages"]:
                if page_num < 1 or page_num > num_pages:
                    return None, f"page {page_num} is outside this PDF (it has {num_pages} pages)"
                name = f"page_{page_num:03d}.png"
                doc[page_num - 1].get_pixmap(dpi=dpi).save(out_dir / name)
                e["images"].append(name)
            e["page"] = e["pages"][0]
            e["image"] = e["images"][0]
    return entries, None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf"); ap.add_argument("out_dir")
    ap.add_argument("--pages", default=""); ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--table", default="", help="with --pages: add the pages to this table's entry")
    a = ap.parse_args(argv)
    out = Path(a.out_dir)
    index_path = out / "index.json"
    existing = json.loads(index_path.read_text()) if index_path.exists() else []
    for e in existing:
        e.setdefault("pages", [e["page"]])
        e.setdefault("images", [e["image"]] if e.get("image") else [])
    if a.table and not a.pages:
        print("--table needs --pages", file=sys.stderr)
        return 1
    if a.pages:
        pages = [int(p) for p in a.pages.split(",") if p.strip()]
        if a.table:
            owner = next((e for e in existing if a.table in e["labels"]), None)
            if owner is None:
                print(f"no entry for table {a.table} in {index_path}", file=sys.stderr)
                return 1
            owner["pages"] = sorted(set(owner["pages"]) | set(pages))
            done, error = render(a.pdf, out, [owner], a.dpi)
            if error:
                print(error, file=sys.stderr)
                return 1
            index_path.write_text(json.dumps(existing, indent=1))
            return 0
        wanted = [{"page": p, "pages": [p], "labels": []} for p in pages]
    else:
        wanted = group_tables(caption_pages(a.pdf))
    if not wanted and not existing:
        out.mkdir(parents=True, exist_ok=True)
        (out / "no_tables.flag").write_text("no table captions found\n")
        return 2
    have = {p for e in existing for p in e["pages"]}
    to_render = [w for w in wanted if not set(w["pages"]) & have]
    rendered, error = render(a.pdf, out, to_render, a.dpi)
    if error:
        print(error, file=sys.stderr)
        return 1
    merged = existing + rendered
    merged.sort(key=lambda e: e["page"])
    index_path.write_text(json.dumps(merged, indent=1))
    flag_path = out / "no_tables.flag"
    if flag_path.exists():
        flag_path.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main())
