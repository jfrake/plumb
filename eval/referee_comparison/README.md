# Referee comparison (Table 3)

This folder holds the code, prompts, and aggregate counts for the comparison of Plumb with the first-round referee reports the authors received on four of their own manuscripts. Plumb was run on each of the four papers with web search capped at that paper's submission date. Paper A is archival. It was held out from development of the editor reader, which was developed on papers B to D. Paper B is an experiment, paper C is qualitative with an event study, and paper D is a theory paper.

No confidential material is here. The only data file is `counts.json`, which holds integers under class names and the paper keys A to D. The ratings in it are the primary rater's blind ratings. Plumb-only points leave out those raised only by the editor reader. The per-paper rows have no "also raised" count, because the summary they come from records that count by class only.

## Rerun the Table 3 percentages

```
python3 eval/referee_comparison/table3_from_counts.py
```

It reads `counts.json`, checks that the classes and the papers add up to the totals, and prints each class with its referee points, the points Plumb also raised, the Plumb-only points, and the shares rated valid and serious for both sources. Add `--json` for machine-readable output. `tests/test_referee_comparison.py` checks the printed numbers against Table 3.

## Pipeline

The steps ran in this order. Every script takes its inputs as flags and prints `--help`.

| Step | Script or prompt | What it does |
|---|---|---|
| 1 | `prompts/code_points.md` | A Claude model, run through Claude Code, codes each referee point and each Plumb issue into the coding sheet: source, type, class, validity of Plumb-only points, and editor-reader credit. |
| 2 | `count.py` | Validates the coding sheet and writes the coverage counts by paper, class, and type. Given run folders, it also tallies check-ins and cost from the run logs. |
| 3 | `prompts/rewrite_items.md`, `pool/build_pool.py` | The agent rewrites every point as a neutral one-line item. The script builds `items.json` from the sheet and those texts, assigns random ids and paper labels, and rejects source cues and any six-word overlap with a decision letter. |
| 4 | `pool/check_pool.py` | Validates the pool: labels, lengths, mutual same-paper matches, and no source cues. |
| 5 | `prompts/source_guess.md`, `pool/score_guess.py` | A blind agent guesses each item's source from the public fields alone. The script writes that public projection and scores the guesses. |
| 6 | `prompts/match_points.md`, `pool/build_matchdata.py` | Builds one match card per referee item, with the proposed Plumb match and strength. |
| 7 | `pool/make_seed.py`, `rating_page.html` | Writes the database documents that seed the rating page. The page shows one item at a time and saves each rater's answers; its owner-only tab confirms the matches. |
| 8 | `prompts/rating_instructions.md` | The instructions the rater saw. |
| 9 | `export.py` | Turns the page's raw database dumps into `ratings.json` and `matches.json`. |
| 10 | `table3_sheet.py` | Writes Table 3 as reported, on the coding sheet's units, and the integer summary that `counts.json` reproduces. |
| 11 | `table3.py` | An alternative Table 3 on the rater's own classes, with agreement between the two raters on the held-out paper. |

## Private inputs

These inputs stay outside the repository. They hold referee report content, the manuscripts, or the identity of the papers and raters, and the referee reports are confidential to the review process.

- The coding sheet and the hand-checked item texts (`texts_A.json` to `texts_D.json`). They paraphrase individual referee points.
- The decision letters and referee reports. Only `pool/build_pool.py` reads them, and only to check for copied wording.
- `pool_config.json` for `pool/build_pool.py`. It holds the paper titles and letter file names, which identify the papers, and the per-issue coding.
- `items.json`, `items_public.json`, `matchdata.json`, `guesses.json`, the seed files, and the raw and exported ratings and matches. They hold item text or rater identities.
- The Plumb run folders, which hold the manuscripts' text.

## Tests

`tests/test_referee_comparison.py` runs with the rest of the suite. It uses small made-up fixtures only. Every item text, sheet row, and rating in it is fake.
