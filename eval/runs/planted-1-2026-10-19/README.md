# Stored run: planted-1, 2026-10-19

This folder holds the files of one Standard run of Plumb on `packs/archival/fixtures/planted-1/planted.pdf` that the scorer reads. Every file is an unchanged copy from the run's workspace except `run.json`.

In `run.json`, `pdf_path` was changed from the run's local path to the repository copy of the paper, `packs/archival/fixtures/planted-1/planted.pdf`. That copy is byte-identical to the PDF the run read (sha256 `503916c610cb1c6535e4852fbf355410f08edb6b6f9d5fd57d391ca6be95ed61`). No other field was changed.

`stage-7/dropped.json` records the issues the audit merged into other issues. The scorer uses it to mark a caught issue that was merged into a kept issue as surviving, and to name the issue it went into (`merged_into`).

`outputs/` holds the finished files the run delivered: `issues_list.md` (the issues Plumb kept, most serious first, each with a fix, and the dropped items at the end), `mock_report.txt` (a mock referee report), and `paper_summary.md` (a neutral summary of the paper). They are copies of what the run delivered, with one correction. In `issues_list.md`, three minor items cited a page from before the audit corrected it: item 9 (p. 17, corrected to p. 13), item 15 (p. 57, corrected to p. 56), and item 29 (p. 17, corrected to p. 54). The corrected pages are the ones in the run's own `stage-7/validated.json` and in `mock_report.txt`. Nothing else was changed. The run took 2 hours 27 minutes at Standard depth with every check-in set to Auto.

## Where each planted error appears in the issues list

The scorer names the issue that caught each error by its id in `stage-5/issues.json`. The issues list numbers its items 1 to 31. This table links the two through `stage-7/validated.json`, where each item's `source` is its stage-5 id. "Merged" means the audit folded the catching issue into the item named. The full description of each error is in `packs/archival/fixtures/planted-1/expected.yaml`.

| Error | Page | What was planted | Issues list item |
|---|---|---|---|
| P1 | 12 | The text gives a final sample of 337 speeches; Table 2 and Figure 2 give 339 | 6 (merged) |
| P2 | 18 | The text gives BR's standard deviation as 0.21; Table 1 gives 0.22 | Missed |
| P3 | 56 | Model 2's BR coefficient carries three stars its standard error cannot support | 6 |
| P4 | 56 | Business media fear in Model 4 carries stars with a standard error of 2.924 | 15 |
| P5 | 57 | Model 5's adjusted R-squared is 0.261; its R-squared, N, and df imply 0.216 | 16 |
| P6 | 54 | A 0/1 dummy with mean 0.29 has a printed SD of 0.64 | 29 |
| P7 | 3 | Brandvold and Halvorsen (2011) does not exist | 11 |
| P8 | 9 | Thessaly (2008) does not exist and is the only citation for a step in H1 | 10 |
| P9 | 16 | The fear moderator's window runs through the day after the speech | 7 (merged) |
| P10 | 25 | The pre-speech placebo is significant, but the text says it did not predict | 1 |
| P11 | 25 | The paper claims to prove causation "around the world" from a U.S. event study | 3 |
| P12 | 24 | Two controls exceed the ITCV threshold, which the text says is larger than every control's impact | 1 (merged) |
