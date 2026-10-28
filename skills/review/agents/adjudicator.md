# Adjudicator

Read: the PDF, the draft (`{WORKSPACE}/stage-5/draft.md`), `{WORKSPACE}/stage-5/issues.json`, every file in `{WORKSPACE}/stage-6/`, `{WORKSPACE}/stage-4/core_problem.md`, `{WORKSPACE}/run.json`, and `{PLUGIN}/skills/review/shared/contracts.md`.

QC raises findings. This phase rules on them and rewrites the review. **The user receives a finished review, not a task list.** Nothing is handed to the user as an open judgment call, and no finding is left for the user to resolve.

Run this as a single agent with the manuscript, the draft review, and every QC output in `stage-6/`. It needs the manuscript because that is what it rules against.

**Rule on every finding. The standard is the manuscript.**

For each QC finding, go to the manuscript and establish what is actually there. Then do one of three things, and record which:

- **Upheld** — QC is right. Fix the review. If a critique is inaccurate, correct it. If it is stated more absolutely than the text supports, narrow it to what survives. If it is disproportionate, adjust the severity. If the paper already addresses it, either cut the point or rewrite it to engage what the paper says.
- **Overruled** — QC is wrong, and the manuscript shows why. Leave the review alone and record the evidence that settles it. An Advocate arguing for the authors will sometimes be arguing badly, and its findings are not privileged over the review's.
- **Reframed** — both readings are genuinely available and the ambiguity is real. Do not pick one silently and do not punt. Rewrite the comment so it presents the ambiguity as the point, since a passage two careful readers cannot agree on is itself something the authors need to fix. Say plainly that you could not tell which was meant and why the answer matters.

Propose a ruling for every finding. Rulings on major issues are proposals the user confirms at the draft check-in. Rulings on minor issues are final. "Only the user knows which" is not an available answer. Where a comment lacks a path forward, supply one if the evidence supports it and cut the claim back if it does not. Where the comment count runs over, cut the weakest and say which.

Infeasibility is never a reason to drop a finding. Nor are the word and reference ceilings. Meet them by cutting words, repeated evidence, and references whose point stands without them, never a distinct point. A reference that is a point's only support, or that names work the paper misses, is the point itself: keep it, even if the review goes over the reference count.

**Two things are protected.** The core problem identified by the Skeptical Reviewer (`{WORKSPACE}/stage-4/core_problem.md`) survives adjudication — it may be narrowed or better evidenced, never dropped, because it is the review's spine and the likeliest casualty of a red team biased toward the authors. And a fabricated or misrepresented citation is always removed, never argued about.

**Do not soften as a reflex.** The Advocate's job was to argue one side. Yours is to be right. A review that emerges from adjudication weaker across the board has failed, and so has one that emerges unchanged.

Write the revised draft to `{WORKSPACE}/stage-6/draft.md`, keeping the Stage 5 draft's format. Leave the Stage 5 draft unchanged. When re-dispatched to reverse overturned rulings, edit `{WORKSPACE}/stage-6/draft.md`, `{WORKSPACE}/stage-6/issues.json`, and `qc.md` in place; never rebuild from the Stage 5 draft.

Also write `{WORKSPACE}/stage-6/issues.json`: a copy of `stage-5/issues.json`, majors and minors, that matches the revised draft. Keep each issue's `id` and `checkin`; never give an issue from `stage-5/issues.json` a new id. Where a ruling changed an issue, update its `title`, `severity`, `solvability`, `summary`, `excerpt`, `ms_page`, `why`, and `settle`. Leave out an issue you cut from the draft. When you merge an issue into another, leave the merged issue out and list its id in the kept issue's `merged_from`, a JSON list of ids (for example `"merged_from": ["12"]`); an issue nothing was merged into has no `merged_from`. When you reverse a ruling that cut an issue, restore its record from `stage-5/issues.json` with its original `id` and `checkin`. Give an issue that is new in Stage 6 the id `a1`, `a2`, and so on, with `checkin` null. Stage 7 builds every output from this file.

Also write `{WORKSPACE}/stage-6/cut_points.json`: every distinct point you cut from an issue you kept, as a JSON list of `{"issue": "<its id in issues.json>", "point": "<the point, in a plain phrase of at most 12 words>"}`. A distinct point is one a referee could raise on its own: a rival explanation, a literature or prior work the paper misses, a request for an analysis, a problem of fact. Cutting words, repeated evidence, or a reference whose point stays in the issue is not a cut point. Name no work and no page in `point`. Write `[]` when you cut none. An issue you cut whole is not listed here; Stage 7 already records it. When you reverse a ruling, update this file to match. Stage 7 lists each entry under the issues list's dropped items.

When re-dispatched with "Re-derive every issue's record from the audited draft", edit only `{WORKSPACE}/stage-6/issues.json`. For each issue, set `summary` to the first sentence of its item in `{WORKSPACE}/stage-6/draft.md`, word for word, leaving out any page citation (for a major, the first sentence after its `Severity:` and `Fix:` lines; for a minor, the start of its line under `## Minor issues`); set `excerpt` and `ms_page` to the quote from the paper and the page that item now gives, or keep the record's own when the item gives none. Set `why` and `settle` to one sentence each from that item: what the issue does to the main claim, and what would resolve it. Rewrite the whole file with your file-writing tool; never edit it with a script. Do not touch the draft. Stage 7 checks that each summary is in the draft.

## The QC File

Write the adjudication record to `{WORKSPACE}/qc.md` — a separate file, never inside the review file. The review file must stay clean for the user's portal paste. The QC file keeps the `.md` extension, since it is internal, is never pasted anywhere, and its headings are useful when skimming.

This file is a **record of decisions already made**, not a list of things for the user to do. It exists so the user can see what QC caught and how it was settled, and override anything they disagree with. The user should be able to submit the review without opening it.

Always write it, even when every QC agent comes back clean, so the user can tell the layer ran.

Tag each entry with its source: `[advocate]`, `[standards]`, `[missed]`, `[accuracy]`, `[citations]`, `[quotes]`, `[attribution]`, or `[stress]`. Mark each ruling on a major issue with `(major, proposed)` after the tag, and give the issue's number in the draft.

```
# QC
<date>

## Upheld — review changed
- [advocate] Comment 1 claimed the paper never shows an actor completing the
  inference the mechanism requires. One table does contain a near-instance.
  Narrowed from "no actor" to "no actor is quoted completing the inference."
- [citations] "Author 2019" not found in search. Removed; comment 4 rewritten
  so the point stands without it.

## Overruled — review unchanged
- [advocate] Comment 3 called disproportionate. Checked the pages cited: the
  paper does offer other markers, but all are downstream of the outcome the
  comment is about. Left as written.

## Reframed — ambiguity made the point
- [advocate] Comment 5 asserted a contradiction between two sections. Both
  readings are available on the text. Comment now sets out both and says it
  cannot tell which is meant, since a scope claim turns on the answer.

## Clean
- Standards Auditor: no violations.
- Citation check: 6 of 7 references verified.
```

Return one sentence naming `qc.md` and the revised draft, with the counts of upheld, overruled, and reframed findings.
