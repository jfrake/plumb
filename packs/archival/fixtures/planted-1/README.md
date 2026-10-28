# planted-1: hand-planted archival test paper

**This is an altered test copy, not a real paper. Do not cite or quote it.** Numbers, two references, and several claims in `planted.pdf` are deliberately wrong. Every page carries a test-copy label and a watermark, and the paper has a neutral title.

## What it is

Plumb's only test paper built from real research rather than written by a model. It is derived from the accepted manuscript of a published article. The full citation is withheld for anonymous review.

The published article is the authoritative version; this copy differs from it on purpose.

The article's author, one of Plumb's authors and not the one who built the archival pack, chose all 12 errors by hand. They were applied by script from an error table that was locked (October 7, 2026, with its SHA-256 recorded) before Plumb was run on this paper in any form.

## Files

- `planted.pdf`: the test paper (57 pages).
- `expected.yaml`: the answer key. 12 `must_catch` entries; 5 `also_fair` entries for places where the same planted error shows up a second time; no `must_not_flag` decoys.

## The planted errors

| Kind | Count |
|---|---|
| A number in the text that doesn't match its table | 2 |
| A significance star the coefficient and standard error don't support | 2 |
| Arithmetic within a table that doesn't hold | 2 |
| A citation to a work that doesn't exist (fictional authors; any resemblance to real scholars is coincidental) | 2 |
| An archival design error (measurement timing, a falsification test, an overclaim, an omitted-variable bound) | 4 |

One error undermines the main claim; five weaken a claim; six are minor. The answer key gives the location, the original, and the reason for each.

## Running and scoring

- Give Plumb only `planted.pdf`, never this README or the answer key, which describe the planted errors. (`eval/run_fixture.sh` copies just the PDF into the run folder.)
- Run at Standard depth with web search capped at **2016-06-01** (`eval/run_fixture.sh` reads it from `expected.yaml`; by hand, use `python3 -m plumb run-dir new --search-before 2016-06-01 planted.pdf` from the repository root; setup does not ask for a cap), so research agents can't find the published article.
- Score with `python3 eval/score_fixture.py packs/archival/fixtures/planted-1 <run folder>`.
- Issues that match nothing in the key can be judged by hand against a private run on the unaltered manuscript, with only counts reported. They have not been judged yet; that waits on the run on the unaltered manuscript.
- Every catch the scorer credits is confirmed by hand: the issue must identify the planted change itself. In a real paper, comments about other problems can land on the same passages, and the automatic scorer can't tell them apart.
- Each `must_catch` entry has a `signature`, a list of regexes that name the planted change. The scorer credits an entry only to an issue that matches one of them and sits within one page of the error (or on a page the entry lists under `pages`). The signatures were added on 2026-10-19 after a hand check.
- `python3 eval/table2.py <score.json> --out table_2.tex` turns a scorecard saved with `--out` into a LaTeX table of recall by error kind and severity.

## License

`planted.pdf` is not covered by this repository's MIT license. It is derived from the authors' accepted manuscript, which is shared for non-commercial research use, such as testing Plumb or similar tools, under the publisher's author archiving policy. It was altered for testing and is labeled as a test copy on every page.
