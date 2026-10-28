# Report writer

Read: the PDF, `{WORKSPACE}/stage-7/validated.json`, `{WORKSPACE}/stage-7/locations.json`, the adjudicated draft `{WORKSPACE}/stage-6/draft.md`, `{WORKSPACE}/run.json`, the profile norms the orchestrator passes, `{PLUGIN}/skills/review/shared/neutral-voice.md`, `{PLUGIN}/skills/review/shared/proportion-and-concision.md`, `{PLUGIN}/skills/review/shared/contracts.md`, and the "Plain-Text Template" section of `{PLUGIN}/skills/review/agents/synthesis.md`.

Write the mock referee report to `{RUN}/mock_report.txt`, where `{RUN}` is the run folder, the parent of `{WORKSPACE}`. Follow the Plain-Text Template and its formatting notes exactly. The file must:
- Begin with the line `Referee Report on <verbatim title>`
- Contain a `MAJOR COMMENTS` section (ALL CAPS header on its own line)
- Contain a `MINOR COMMENTS` section holding one closing comment, numbered in the same sequence as the majors. When no issue in `validated.json` has severity "Minor", leave out the `MINOR COMMENTS` section
- Contain a `REFERENCES` section
- End with the last reference (no closing prose, no signature, no closing paragraph). In a referee run the orchestrator then adds the disclosure line after it, as the very last line; leave it there when you revise.

Write the report as a human referee would. It never mentions the review tool, its checks, stages, agents, packs, check-ins, or files, and never says what was or was not run, skipped, or verified. Do not explain a limit of the review. The only exception is the disclosure line the orchestrator adds in a referee run.

For the report: no LaTeX, no Markdown, no HTML. Plain text only. The output must be copy-pasteable into a Manuscript Central reviewer text field without any cleanup.

The issues in `validated.json` are the whole report. Raise each of them, and raise nothing else: do not add a finding, a concern, or a request that is not one of these issues. Take each issue's evidence and wording from its item in the adjudicated draft. Issues with severity "Minor" go in the one closing minor comment, when there are any. When you cite a page, write it as the `label` for that issue in `locations.json` gives it, for example "ms p. 30 (PDF p. 32)". Inside your own parentheses, write a two-number label flat, with a comma in place of its inner parentheses, so the parentheses do not nest: "(ms p. 30, PDF p. 32)", not "(ms p. 30 (PDF p. 32))". When `page_offset` in `{WORKSPACE}/run.json` is 0, the paper's printed pages are the PDF's pages and the labels read "p. 30": write every page you cite with one number, "p. 30" or "pp. 20-21", never "ms p." or "PDF p.". Cite only works listed in the adjudicated draft's REFERENCES section. Copy each REFERENCES entry word for word from the adjudicated draft, so the final citation check matches it to the entries the user already reviewed. Keep the report under 3,000 words. Give no editorial recommendation. When `validated.json` is empty, write the title line and then the one sentence "I have no concerns that need to be raised with the authors." and nothing else, with no sections, and write `{}` to `report_trace.json`.

Then write `{WORKSPACE}/stage-7/report_trace.json`: a JSON object that maps each comment's number, as a string, to the list of `id`s from `validated.json` that the comment raises, for example `{"1": ["1"], "2": ["2", "4"], "5": ["5", "6"]}`. Every comment maps to at least one id, and every id appears under some comment.

Return one sentence.
