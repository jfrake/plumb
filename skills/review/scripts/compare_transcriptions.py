#!/usr/bin/env python3
"""Compare two independent table transcriptions cell by cell.

Each reading may also hold the table's note (table_NN_note.txt). Notes that agree after
whitespace is normalized are written beside the agreed CSV. Notes that differ are recorded in
disagreements.json with reason "note" and whole_table false; no note is written, and any note
an earlier run wrote is removed, so the star check skips that table. Nobody is asked about a note.
A heading row that only one reading kept (a leading row with no digit, as a heading printed over several columns) is set aside before the shapes are compared, and recorded with reason "header_rows" and whole_table false.

A table whose two readings differ in shape, or that only one reading has, gets no
agreed CSV, and any agreed CSV an earlier run wrote for it is removed. It is recorded in disagreements.json with whole_table true and the path
to each reading, and printed to stdout, so it is never dropped silently.
"""
from __future__ import annotations
import csv
import json
import sys
from pathlib import Path


def normalize(cell: str) -> str:
    return cell.strip().replace("−", "-").replace("–", "-")


def _read(path: Path) -> list:
    with open(path, newline="", encoding="utf-8") as fh:
        return [[normalize(c) for c in row] for row in csv.reader(fh)]


def _note(folder: Path, name: str) -> str:
    f = folder / name.replace(".csv", "_note.txt")
    return f.read_text(encoding="utf-8").strip() if f.exists() else ""


def _drop_note(out: Path, name: str) -> None:
    """Remove a note an earlier run left, so the star check never reads a stale key."""
    (out / name.replace(".csv", "_note.txt")).unlink(missing_ok=True)


def _has_digit(row: list) -> bool:
    return any(ch.isdigit() for c in row for ch in c)


def _lead(rows: list) -> int:
    """Leading rows with no digit: column headers and headings over them."""
    n = 0
    for r in rows:
        if _has_digit(r):
            break
        n += 1
    return n


def _rows(n: int) -> str:
    return f"{n} heading row" + ("" if n == 1 else "s")


def _differs(a: list, b: list) -> bool:
    return len(a) != len(b) or any(len(x) != len(y) for x, y in zip(a, b))


def compare(a_rows: list, b_rows: list) -> dict:
    a = [[normalize(c) for c in r] for r in a_rows]
    b = [[normalize(c) for c in r] for r in b_rows]
    extra = None
    if _differs(a, b):
        la, lb = _lead(a), _lead(b)
        # One reading kept a heading row the other did not: set the extra leading rows aside,
        # but only when both readings have numeric rows to compare.
        if la != lb and la < len(a) and lb < len(b):
            cut = abs(la - lb)
            extra = {"row": None, "col": None, "a": _rows(cut if la > lb else 0),
                     "b": _rows(cut if lb > la else 0), "reason": "header_rows", "whole_table": False}
            a, b = (a[cut:], b) if la > lb else (a, b[cut:])
    if _differs(a, b):
        shape = lambda t: f"{len(t)} rows x {max((len(r) for r in t), default=0)} cols"
        return {"shape_match": False, "agreed": None,
                "disagreements": [{"row": None, "col": None, "a": shape(a), "b": shape(b),
                                   "reason": "shape", "whole_table": True}]}
    agreed, dis = [], []
    for i, (ra, rb) in enumerate(zip(a, b)):
        row = []
        for j, (ca, cb) in enumerate(zip(ra, rb)):
            if ca == cb:
                row.append(ca)
            else:
                row.append("")
                dis.append({"row": i, "col": j, "a": ca, "b": cb, "reason": "cell"})
        agreed.append(row)
    if extra:
        dis.append(extra)
    return {"shape_match": True, "agreed": agreed, "disagreements": dis}


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) != 3:
        print("usage: compare_transcriptions.py <dir_a> <dir_b> <out_dir>", file=sys.stderr)
        return 2
    da, db, out = Path(argv[0]), Path(argv[1]), Path(argv[2])
    out.mkdir(parents=True, exist_ok=True)
    names = sorted({p.name for p in da.glob("table_*.csv")} | {p.name for p in db.glob("table_*.csv")})
    all_dis = []
    for name in names:
        pa, pb = da / name, db / name
        if not pb.exists() or not pa.exists():
            reason = "missing_in_b" if not pb.exists() else "missing_in_a"
            all_dis.append({"table": name, "row": None, "col": None,
                            "a": "present" if pa.exists() else "absent",
                            "b": "present" if pb.exists() else "absent", "reason": reason,
                            "whole_table": True,
                            "a_file": str(pa) if pa.exists() else None,
                            "b_file": str(pb) if pb.exists() else None})
            _drop_note(out, name)
            (out / name).unlink(missing_ok=True)
            continue
        res = compare(_read(pa), _read(pb))
        for d in res["disagreements"]:
            entry = {"table": name, **d}
            if d.get("whole_table"):
                entry.update(a_file=str(pa), b_file=str(pb))
            all_dis.append(entry)
        if res["agreed"] is not None:
            with open(out / name, "w", newline="", encoding="utf-8") as fh:
                csv.writer(fh).writerows(res["agreed"])
            na, nb = _note(da, name), _note(db, name)
            if " ".join(normalize(na).split()) == " ".join(normalize(nb).split()) and na:
                (out / name.replace(".csv", "_note.txt")).write_text(na + "\n", encoding="utf-8")
                continue
            _drop_note(out, name)
            if " ".join(normalize(na).split()) != " ".join(normalize(nb).split()):
                all_dis.append({"table": name, "row": None, "col": None, "a": na, "b": nb,
                                "reason": "note", "whole_table": False})
        else:
            _drop_note(out, name)
            (out / name).unlink(missing_ok=True)
    (out / "disagreements.json").write_text(json.dumps(all_dis, indent=1))
    for d in all_dis:
        if d.get("whole_table"):
            print(f"WHOLE-TABLE DISAGREEMENT: {d['table']} ({d['reason']}): not verified, no agreed CSV written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
