"""Score a blind agent's guesses of each item's source, and write the public projection of the pool.

Usage:
  python3 score_guess.py <items.json> --public <items_public.json>
  python3 score_guess.py <items.json> <guesses.json>
"""
import json, sys


def public(items):
    return [{k: it[k] for k in ("id", "paper_label", "title", "text")} for it in items]


def score(items, guesses):
    by = {g["id"]: g for g in guesses}
    missing = [it["id"] for it in items if it["id"] not in by]
    if missing:
        raise ValueError(f"no guess for {len(missing)} items: {missing[:5]}")
    right = [it for it in items if by[it["id"]]["guess"] == it["source"]]
    cc = [it["id"] for it in right if by[it["id"]]["confidence"] == "high"]
    return {"n": len(items), "accuracy": round(len(right) / len(items), 3), "confident_correct": cc}


if __name__ == "__main__":
    items = json.load(open(sys.argv[1], encoding="utf-8"))
    if sys.argv[2] == "--public":
        with open(sys.argv[3], "w", encoding="utf-8") as f:
            json.dump(public(items), f, indent=1, ensure_ascii=False)
    else:
        print(json.dumps(score(items, json.load(open(sys.argv[2], encoding="utf-8"))), indent=1))
