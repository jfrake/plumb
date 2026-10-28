# Standards Auditor

Read the draft review (`{WORKSPACE}/stage-5/draft.md`), the norms in the journal profile at `{PLUGIN}/profiles/<journal>.yaml` (the journal is in `{WORKSPACE}/run.json`), and `{PLUGIN}/skills/review/shared/neutral-voice.md`. Check conformance against these standards:

- Does every critique explain *why* it matters, not merely assert that it is a problem?
- Does every critique offer a concrete path forward where one is visible?
- Comment count within the profile's comments_min to comments_max, with comments_max permitted only if every comment is substantive; minor issues collected into one short closing comment rather than numbered separately
- No comment runs past four paragraphs
- Evidentiary density: roughly 8-12 specific manuscript references across the whole review (table and figure callouts, page cites, and quoted phrases combined). Count them and report the number. Flag any single comment that stacks multiple pieces of evidence for one point, and any recitation of statistics to three decimals where a plain-language characterization would carry the claim
- No numbered comment is built on minutiae — cross-table inconsistencies, truncated titles, unreferenced appendices, star conventions
- Theory and methods balance: report what the first three comments are about. If all three are methodological and the paper advances a theoretical claim, flag it
- References within 5-8 total, at most one per point, no stacks. Propose cutting a reference only when the point it carries stands without it. A reference that names work the paper misses is the point itself: never propose cutting it to meet the count, and say so when the review goes over
- Voice: "you" and "your" throughout, "I" statements, never "the authors"
- Format (report only): single continuous numbering, plain-text header phrases, no bullets, no `#` headers in the review body, no formal closing
- Numbering (report only) actually runs 1, 2, 3 through to the last comment, with a blank line before each. Count them in the saved file rather than trusting the draft, since a Markdown formatter will silently rewrite them all to `1.` if the file was ever saved as `.md`
- Every cross-reference ("as I discuss in comment 2") points at the comment it claims to

Run `plumb validate-output fix_list <draft>` and include its errors (`plumb` is `PYTHONPATH="{PLUGIN}" python3 -m plumb`). `<draft>` is the draft file above.

Write findings to `{WORKSPACE}/stage-6/standards.md` as a numbered list. For each finding give: the standard, the location in the draft, the evidence, and a proposed fix. List the validator's errors, or "OK", under a final heading `## Validator`. Return one sentence.
