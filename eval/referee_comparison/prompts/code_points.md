# Coding agent: the coding sheet

Source: the design spec for the blind rating (October 20, 2026), the class definitions shown to the rater, and the checks in `count.py` and `pool/build_pool.py`. The coding agent got its instructions in a working session, and those instructions were not saved as a separate file. This file gives the rules the spec sets and the scripts enforce, which is what the coded sheet had to satisfy.

A Claude model, run through Claude Code, read each paper's first-round referee reports and the Plumb run on that paper. It wrote one row per distinct point in a coding sheet, one section per paper (headed `## A` to `## D`).

## Rows

- Referee rows (`<paper>-R<nn>`): one per distinct referee point. Merge duplicate points across referees and the editor into one row.
- Plumb rows (`<paper>-P<nn>`): one per Plumb issue that no referee raised.

## Columns

Each row has eleven cells, the first being `id`. The scripts read these columns by header name (`count.py`) or by position (`pool/build_pool.py`: source third, class fifth, the severity cell with the matching Plumb issue numbers in parentheses eighth, ER ninth):

- `source`: `both` (the referees and Plumb raised it), `referees only`, or `Plumb only`.
- `type`: `verifiable (paper)`, `verifiable (external)`, or `judgment`.
- `class`: `factual`, `substantive judgment`, or `preference`.
  - Factual: the paper or an outside source can settle it, such as a number that does not match its table or a misdescribed citation.
  - Substantive judgment: a call about the design, the argument, or the contribution that affects whether the claims hold.
  - Preference: a matter of framing, emphasis, or style that does not change whether the claims hold.
  - A `judgment` row is never `factual`. A `verifiable` row coded other than `factual` needs a `class note` saying why.
- `validity (Plumb-only)`: only on Plumb-only rows, starting with `valid`, `doubtful`, or `wrong`.
- `ER`: editor-reader credit: empty, `adds` (the editor reader raised a point the run missed), `also`, `weak`, or `only`.
- `notes`: a referee row starts with the run class (`MATCH`, `PARTIAL`, `MISSED`, or `DROPPED`, prefixed by the run name) or with `Merges`. Weak partials are marked `(weak)`, `generous partial`, or `listed, not questioned`.

## Rules

- Paraphrase. Never quote a referee letter in the sheet.
- Results are reported only as counts.
