# Issues list writer

Read: the PDF, the adjudicated draft `{WORKSPACE}/stage-6/draft.md` (there is none at Quick depth), `{WORKSPACE}/stage-7/validated.json`, `{WORKSPACE}/stage-7/dropped.json`, `{WORKSPACE}/stage-7/locations.json`, `{WORKSPACE}/qc.md` (if it exists), `{WORKSPACE}/run.json`, `{PLUGIN}/skills/review/shared/neutral-voice.md`, and `{PLUGIN}/skills/review/shared/contracts.md`.

The orchestrator passes `MODE=full` or `MODE=facts_only`.

`validated.json` is the whole list. Write one item for each issue in it, numbered with its `id`, in its order, and no other item. Open each item with its `summary`, copied word for word; if the summary cites a page, write that citation as the issue's `label`. Take `Severity:` from its `severity` and, under `MODE=full`, `Fix:` from its `fix`. Cite a page only as the `label` for that issue in `locations.json` gives it, for example "ms p. 30 (PDF p. 32)", so every page you cite carries both numbers. When `page_offset` in `{WORKSPACE}/run.json` is 0, the paper's printed pages are the PDF's pages and the labels read "p. 30": write every page you cite with one number, "p. 30" or "pp. 20-21", never "ms p." or "PDF p.".

## MODE=full

Run one agent with the manuscript and the finished review. Its job is triage, not analysis, and it is the only artifact the authors see.

From everything the review raises, identify every kept major issue, ordered by consequence whether or not it can be fixed, each tagged with its solvability.

For each one, state the problem in a sentence, say why it matters for this paper at this journal, and give a **concrete solution**: the specific move, section, analysis, reframing, or citation that fixes it, at enough resolution that they could start on it that afternoon. Where a fix has more than one defensible route, name the routes and say which you would take. For an item tagged `can't fix, narrow the claim`, give rescoping advice instead of a fix: say which claim to narrow and how far.

Say plainly what you are leaving out and why, in a line or two, under `## What I left out`. A colleague needs to know whether the items are the whole list or the top of a longer one.

The issues list is written to the authors in the neutral voice (`shared/neutral-voice.md`), using the same second-person address and the same directness as a review. It is a senior colleague telling them where to spend their remaining time.

**Format the issues list for scanning, not for a submission portal.** This is the one place where the review's formatting conventions do not carry over, and getting it wrong is the failure mode this section exists to prevent. A referee report is unbroken prose because it is pasted into a portal field. An issues list is read by a colleague on a deadline who needs to find the items and start on the first one, so it must be structured. Use `##` section headings and `###` headings for the numbered items, with the number inside the heading text (`### 1. Argue the rule...`) rather than as an ordered-list marker, which keeps a formatter from renumbering them. Break the reasoning into paragraphs of three to six sentences. Use bold sparingly, to name the case or the move a paragraph is about. Bullets are allowed here and only here, for lists of genuinely parallel short items such as housekeeping. Do not hard-wrap. Let the editor soft-wrap. An issues list that arrives as a sequence of 300-word slabs with no visible structure has failed regardless of how good the content is, because the recipient cannot see the items without reading the whole thing.

Use exactly this format:

```
## Issues

### 1. <Issue title>

Severity: <Undermines the main claim | Weakens a claim | Minor>
Fix: <quick fix | new analysis | new data | can't fix, narrow the claim>
Where: <the issue's label from locations.json>

<The summary from validated.json, word for word. Why it matters for this
paper at this journal. A concrete fix, naming the alternative routes where
there is more than one. For "can't fix, narrow the claim", say how to
rescope the claim.>

### 2. <Issue title>

...

## Minor issues

- <id>. <The summary from validated.json, word for word.> (<the issue's label, flat>)

## What I left out

<A line or two on what you left out and why.>

## Dropped items

- <title>: <reason>

REFERENCES

<Only when the body cites any work. One reference per paragraph, blank line between: Author, A., and Author, B. (Year). Title. Journal, volume(issue), pages.>
```

- Number the `### N.` headings with each issue's `id`, in order, ordered by consequence whether or not the issue can be fixed: every "Undermines the main claim" item before every "Weakens a claim" item.
- `Severity:`, `Fix:`, and `Where:` each start their own line, in plain text (no bold), with the value copied exactly from the lists above.
- Issues with severity "Minor" go in the `## Minor issues` list, each line starting with its `id`, never under `###` headings. Write the label there flat, with a comma in place of its inner parentheses, so the parentheses do not nest: "(ms p. 4, PDF p. 4)", not "(ms p. 4 (PDF p. 4))".
- Cite only works already listed in the adjudicated draft's REFERENCES section. Copy each REFERENCES entry word for word from the adjudicated draft, so the final citation check matches it to the entries the user already reviewed.
- When every issue is Minor, `## Issues` has no `###` item and goes straight to `## Minor issues`. When `validated.json` is empty, write the one line "No issues survived the checks." under `## Issues`, and leave out `## Minor issues`.

Keep the list above `## Dropped items` under about 2,000 words. Everything that does not survive that cut is already in the draft, which is the user's to draw on if the conversation goes further.

## MODE=facts_only

Used at Quick depth, and for a referee whose journal bars AI drafting. List what the paper or an outside source settled. Give no fixes, no judgment of the paper, no opening, and no review prose.

Use exactly this format:

```
## Checked facts

### 1. <Title>

Severity: <severity>
Where: <the issue's label from locations.json>

<The summary from validated.json, word for word. One more sentence of evidence, if needed.>

## What was checked

<One line per check that ran, with its result: the tables read twice and compared, the arithmetic, the numbers in the text against the tables, the reference list, and, at Standard or Deep depth, the quotes and citations. Numbers left unverified are in the dropped items below, not here.>

## Did we read it right?

<At Quick depth only: the user's answer at the read check, in one or two sentences, or the sentence the orchestrator gives when the check was skipped. Leave this section out at Standard and Deep depth.>

## Dropped items

- <title>: <reason>
```

## Dropped items

Write `## Dropped items` as the last `##` section; a REFERENCES block, when there is one, follows it. Give one line per entry in `dropped.json`, in the form "- <title>: <reason>", with the reason copied exactly. An entry with a `source` is a finding left out at synthesis, and its `title` is only the finding's id: for its title, write a plain phrase of at most 12 words saying what the finding was, from its row in `{WORKSPACE}/synthesis_coverage.md` and its `source` file. Cite no work and no page on these lines. When `dropped.json` is empty, write "None."

Write `{RUN}/issues_list.md`, where `{RUN}` is the run folder, the parent of `{WORKSPACE}`. Return one sentence.
