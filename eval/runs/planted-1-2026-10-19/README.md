# Stored run: planted-1, 2026-10-19

This folder holds the files of one Standard run of Plumb on `packs/archival/fixtures/planted-1/planted.pdf` that the scorer reads. Every file is an unchanged copy from the run's workspace except `run.json`.

In `run.json`, `pdf_path` was changed from the run's local path to the repository copy of the paper, `packs/archival/fixtures/planted-1/planted.pdf`. That copy is byte-identical to the PDF the run read (sha256 `503916c610cb1c6535e4852fbf355410f08edb6b6f9d5fd57d391ca6be95ed61`). No other field was changed.

`stage-7/dropped.json` records the issues the audit merged into other issues. The scorer uses it to mark a caught issue that was merged into a kept issue as surviving, and to name the issue it went into (`merged_into`).
