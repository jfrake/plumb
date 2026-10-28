#!/usr/bin/env python3
"""Write one JSON file per database document for seeding the rating page, and the batch write lists.

items/<id>: public fields plus a seeded random order. matchdata/<refId>: owner-only match cards.
config/settings: the held-out paper's label, for the owner's rater slot.

Usage:
  python3 make_seed.py --items <items.json> --public <items_public.json> --matchdata <matchdata.json> \
      --out <seed folder> [--heldout A] [--seed 20261020]
"""
import argparse
import json
import random
import sys
from pathlib import Path


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--items", required=True)
    p.add_argument("--public", required=True)
    p.add_argument("--matchdata", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--heldout", default="A", help="paper key of the held-out paper")
    p.add_argument("--seed", type=int, default=20261020)
    a = p.parse_args(argv)

    rng = random.Random(a.seed)
    items = json.loads(Path(a.items).read_text(encoding="utf-8"))
    public = {x["id"]: x for x in json.loads(Path(a.public).read_text(encoding="utf-8"))}
    matchdata = json.loads(Path(a.matchdata).read_text(encoding="utf-8"))
    seed = Path(a.out)
    for sub in ("items", "matchdata", "config"):
        (seed / sub).mkdir(parents=True, exist_ok=True)

    labels = sorted({it["paper_label"] for it in items})
    rng.shuffle(labels)
    paper_order = {lab: i for i, lab in enumerate(labels)}
    ids = [it["id"] for it in items]
    rng.shuffle(ids)
    item_order = {iid: i for i, iid in enumerate(ids)}

    writes = []
    for iid, pub in public.items():
        doc = dict(pub, paper_order=paper_order[pub["paper_label"]], item_order=item_order[iid])
        doc.pop("id")
        f = seed / "items" / f"{iid}.json"
        f.write_text(json.dumps(doc, ensure_ascii=False))
        writes.append({"op": "set", "collection": "items", "doc_id": iid, "file_path": str(f.resolve())})
    for rid, m in matchdata.items():
        f = seed / "matchdata" / f"{rid}.json"
        f.write_text(json.dumps(m, ensure_ascii=False))
        writes.append({"op": "set", "collection": "matchdata", "doc_id": rid, "file_path": str(f.resolve())})
    heldout = next(it["paper_label"] for it in items if it["paper"] == a.heldout)
    f = seed / "config" / "settings.json"
    f.write_text(json.dumps({"heldout_label": heldout}))
    writes.append({"op": "set", "collection": "config", "doc_id": "settings", "file_path": str(f.resolve())})

    batches = [writes[i:i + 50] for i in range(0, len(writes), 50)]
    for n, b in enumerate(batches):
        (seed / f"batch_{n}.json").write_text(json.dumps(b))
    print(len(writes), "writes in", len(batches), "batches; held-out label", heldout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
