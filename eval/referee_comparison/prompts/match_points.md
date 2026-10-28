# Matching: referee points and Plumb issues

Source: the design spec and implementation plan for the blind rating (October 20, 2026), Task 3, and `pool/build_matchdata.py`.

## Proposed matches (coding agent)

- Each referee row of the coding sheet names the Plumb issues that raise the same point, in the severity cell, and the run class in its notes.
- `pool/build_matchdata.py` turns this into one match card per referee item: the referee point, every Plumb item on the same paper as a candidate, the proposed match, and a proposed strength. `MATCH` becomes `full`, `PARTIAL` becomes `partial`, and a row with no match is `none`. On the held-out paper the capped run's class is used.

## Confirmation (an author, not blind)

- The match tab of the rating page shows each referee point beside the Plumb issue or issues proposed for it.
- The author picks `full`, `partial`, or `none`, and can re-match to other Plumb issues from the same paper with a searchable picker.
- A match to a Plumb issue on another paper is rejected by `pool/check_pool.py` and by `table3.py`.
- The match tab is visible only to the page owner; the rater's view never shows it.
