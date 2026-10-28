# Rewriting agent: one-line items for the blind pool

Source: the design spec and implementation plan for the blind rating (October 20, 2026). These are the instructions the rewriting agent worked from.

You write the item pool. Each item is one point about one paper, rewritten so a rater cannot tell whether a human referee or Plumb raised it.

## What gets an item

- One item per referee row of the coding sheet. Duplicate points across referees are already merged into one row.
- One item per Plumb row, and one per Plumb issue that matched a referee row. A matched pair gives two items.

## How each item reads

- The `text` is one sentence of 12 to 45 words, declarative or a question, in a neutral voice. It says what is wrong or missing, and where.
- Paraphrase in your own words. Never quote a referee letter. No item may share six or more consecutive words with a decision letter (`pool/build_pool.py` checks this).
- Leave out every source cue. No "the authors should", no "Plumb flags", no agent or check names, no check ids, no stage numbers, and no severity labels such as "undermines the main claim" or "weakens a claim". Also avoid first or second person, "suggest", "recommend", "wonder", "might consider", and dashes. `pool/check_pool.py` and `pool/build_pool.py` reject these.
- Keep lengths alike, so long referee points and short Plumb lines look the same.

## Fields

Each element of `items.json` is:
`{"id": "i-<6 hex>", "paper": "A"|"B"|"C"|"D", "paper_label": "Paper A"|"Paper B"|"Paper C"|"Paper D", "title": str, "text": str, "source": "referee"|"plumb", "class": "factual"|"substantive judgment"|"preference", "er_only": bool, "match": [ids of the other source's items on the same paper], "sheet_row": str}`

- Ids are random hex.
- `paper_label` letters are assigned in random order, not in the order of the paper keys.
- `title` is the paper's title as printed on its first page.
- A Plumb item that only the editor reader raised has `er_only: true`.
- A match links items from different sources on the same paper, and every match is mutual.
