# Contracts for every agent

1. Cite a page, section, table, or quote for every claim about the paper. A claim with no location is not made.
2. The extracted table CSVs in `{WORKSPACE}/extracted_tables/` are authoritative for every digit. Read numbers from them, not from memory of the PDF.
3. When the construction ledger `{WORKSPACE}/stage-2/construction_ledger.json` exists, it is authoritative for how each variable or construct is built. `construction_ledger.md` is a readable copy that the checker regenerates from the corrected JSON; read the JSON when you need a field's exact value. A pack can turn the ledger off for a paper with no variables; `construction_ledger.md` then says so and the JSON does not exist.
4. Tag each finding with what can settle it: `paper`, `external`, or `judgment`.
5. External facts need a fetched source. Record the URL and a verbatim quote. Never confirm a citation from memory.
6. No superlative ("the largest", "never") without a full scan of the rows, columns, or text it covers.
7. Keep a verified fact apart from the inference built on it.
8. Before critiquing, state the paper's best version of the point in one sentence.
9. Severity labels are exactly: Undermines the main claim, Weakens a claim, Minor. Set severity with the contribution type in `run.json` and the journal norms. Leave a level shift that your pack.yaml states to the Stage 4 compiler.
10. Never write an editorial recommendation, a predicted decision, or a judgment that the paper is or is not ready.
11. Never predict the outcome of a check you ask the authors to run.
12. Raw data never leaves the machine. When code runs, return only code, logs, and summary tables.
13. Write every file with your file-writing tool, never through a shell command (no heredoc, no `echo >`, no `cat >`, no `tee`). Running a script that writes its own output file is fine. An inline script typed on the command line (`python -c`, `python - <<`, `node -e`, and the like) that writes or edits a file counts as a shell write: use your file-writing tool instead.
14. If a write inside the run folder is blocked, write the same content with your file-writing tool to a staging file under the system temp folder (`plumb-staging/<run date>/<name>`), and name both paths in your reply, the staging file and the file you meant to write, so the orchestrator can move it with `plumb put`.

## Required confirmation format

Write your full output to the file your instructions name. Do not return the report itself. Reply to the orchestrator in one sentence that names the file you wrote. If a stage gate reads a verdict from you, include its token exactly as your instructions give it. The gates read these tokens:

- Theory devil (Stage 3): `Verdict: Go`, `Verdict: Revise`, or `Verdict: Rethink`.
- Construction-claim audit (Stage 5): the `Verdict:` line in its `## Summary`: `CLEAN`, `CONTRADICTIONS FOUND`, `INFERENCES FLAGGED`, or `CONTRADICTIONS FOUND AND INFERENCES FLAGGED`.
- Synthesis critic (Stage 5): `VERDICT: CLEAN` or `VERDICT: REVISE`.
