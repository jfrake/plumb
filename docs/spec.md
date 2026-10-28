# Plumb: design spec

Draft of September 25, 2026.

## 1. Research question and claim

Peer review mixes verification with judgment. Machines can do verification. They do judgment unevenly. Plumb is an open referee that stops to ask a person wherever it may be crossing that line. Its logs show where reviewers and the tool disagree, and blind ratings show which of them was right.

The research question is where AI review needs a human: at which stage, for which kind of paper, and when people are right to overrule the tool. The tool is the instrument. The check-in log is the data. An override alone shows disagreement, not error, so blind raters (section 14) judge each override. The finding we are after is variation the design does not build in, such as which kinds of judgment call reviewers overrule most.

The proposal opens on the journal's own AI Task Force editorial, "More Versus Better" (Organization Science 37(3), 2026). That editorial reports a 42% rise in submissions and falling review quality. It also says bans are "unrealistic and counterproductive," and that "Journals need tools and policies that maintain volume at sustainable levels or facilitate low-cost rejections of low-quality AI-driven research." The proposal names two risks and says how the evaluation measures them. One is that a pre-submission referee helps weak papers get submitted. The other is that authors start writing for the AI referee.

## 2. Organizing idea: what can settle a check

Every check in every pack declares one of three adjudication types. This idea came from Author B.

| Type | What settles it | Practice | Examples |
|---|---|---|---|
| Paper | The manuscript itself | Recompute or match | Quotes, numbers against tables, stars against p-values, claims that the paper omits something, superlatives, "already addressed" |
| External | A source outside the paper | Look up or reproduce | Citation existence and support, preregistration, facts about the setting, the authors' code |
| Judgment | Nothing outside | A human decides at a check-in | Severity, contribution, alternative explanations, fit with the journal's standards |

Nothing outside settles a Judgment item, but that does not make one answer enough. A single draw is one sample of what the model might say, and it may not give the reviewer what they need to decide at the check-in. The Stage 2 evaluation tests whether repeated draws earn their cost (section 14).

Fail-closed gates apply only to the Paper and External types. Claims that no prior work exists look External but cannot be settled, because no source proves absence. They never pass a gate and always go to the reviewer. The headline figure plots override rates by adjudication type, stage, and pack. Low overrides on Paper and External checks and high overrides on Judgment calls follow from the design, so they confirm the tool works as built rather than count as a finding. The finding is how overrides vary within the Judgment type, and whether blind raters side with the reviewer or the tool.

## 3. Users, modes, and outputs

- **Audiences.** Primary: authors and friendly reviewers (a colleague running it on the author's draft with the author's permission). Secondary: journal referees and editors. Journal-level use at intake is future potential only. The tool NEVER asks the user's role. Setup asks what output they want and whose permission covers the manuscript; the journal profile gates what may be produced. Editor output = checked-facts memo + neutral summary, no recommendation.
- **Author mode** runs on the author's own paper (or a colleague runs it on the author's behalf) before submission. It always runs, subject to the consent record in section 9.
- **Referee mode** runs only where the journal profile allows it (section 8).
- At setup the user picks any combination of the outputs below. Each shows only validated issues: ones that survived the audit, that the user kept at the check-ins, and whose facts are confirmed. Dropped items are listed at the end of the issues list with the reason, including findings left out at synthesis and distinct points the audit cut from issues it kept. Every page citation gives the printed page and the PDF page, as in "ms p. 30 (PDF p. 32)", or one number when the two are the same.
  - **Annotated PDF.** With the fix list, a copy of the manuscript annotated where each problem occurs. The proposal describes this as an author output.
  - **Issues list.** A `.md` list in Author B's advisor format: `##` sections, `###` numbered headings, and for each item the problem, why it matters for this paper at this journal, and a concrete fix with alternative routes named. It includes an explicit "what I left out" line and runs to about 2,000 words at most. Items are ordered by consequence, fixable or not. Each carries a solvability tag: quick fix, new analysis, new data, or "can't fix, narrow the claim." For the last tag, the advice is how to rescope the claim.
  - **Mock referee report.** Plain `.txt` with a single numbered sequence and a blank line before every comment. A validator checks it after saving. It has a length ceiling and no floor.
  - **Checked-facts memo for an editor.** Offered only when a journal sent the paper for review, the journal allows AI tools in review, and the depth is Standard or Deep. It opens with a neutral summary of the paper (claims, data, design, main result). Then come the five most serious validated issues, each with severity, both page numbers, what the paper claims there, the problem with its evidence, why it matters for the main claim, and what would settle it. When fewer than five survive, one sentence says so. It never carries a verdict, a score, or a desk-reject signal. Three things keep it that way: it has a fixed two-part layout, a check blocks explicit verdict wording, and the user reads the memo before using it. The no-recommendation validator checks it, with desk-reject patterns added, and it goes through the same final verification as the other outputs. A new agent on the judgment model writes it from `validated.json`, `locations.json`, and `paper_summary.md` alone.
  - The annotated PDF highlights each issue on its page, colored by severity, with an index page that links to each one. The original PDF is never changed.
  - At Quick depth, and in referee mode where the journal bars AI drafting of reviews, the issues list holds **checked facts only** and no report is written.
  - Outputs go to a dated `plumb_output/` folder in the project folder, or in a folder named after the paper next to the PDF, with a README. The working files sit in a hidden `.workspace/` folder there.
- **No editorial recommendation anywhere.** No accept or reject, no AE recommendation word, no base rates, and no readiness signal.
- Severity labels: "Undermines the main claim," "Weakens a claim," "Minor."
- Every run also writes an **audit package** (section 10) and a neutral paper summary.

## 4. Architecture

The shell comes from Author A's plugin and the stage body comes from Author B's pipeline. It is a Claude Code plugin with one phase file per stage, paths through `${CLAUDE_PLUGIN_ROOT}`, and an on-disk workspace. A cumulative brief carries context between agents, and the PreCompact hook re-injects it. The plugin keeps Author A's resume check, HARD and ADVISORY gate tiers, the two-tier error recovery, and the unattended contract where the run writes `FAILED.txt` rather than ship a bad review. Model names live in one config file with role slots, not in prompts.

Stages always run in order. Packs add work in named slots and never reorder stages.

| Stage | Core | From |
|---|---|---|
| 0 Intake | Extract text and tables. Detect paper type and contribution type. Load journal profile. Consent record. | Author A: extraction and classifier. Author B: routing and profiles. |
| 1 Verify | Table transcription (two independent transcriptions of each table, compared cell by cell), arithmetic and significance stars (`verify_arithmetic.py`), numbers in the text against the tables, the hypothesis ledger, which maps each hypothesis to its test (`check_hypotheses.py`), pack verify agents, and a lookup of each entry in the paper's reference list (`check_reference_list.py`) | Author A |
| 2 Understand | Paper summary, construction ledger, setting research (about 15 searches at Standard, 70-100 at Deep) | Author A |
| 3 Theory | Argument map with falsifiability checks, mechanism discrimination, theory devil, run in parallel with the contribution auditor, adjacent-literature scout, boundary-conditions agent, and editor reader (conversation, premise, constructs, setting, stakes; fed by Stage 2's citation gap lists) | Author A and Author B |
| 4 Diagnose | Face validity, completeness, skeptical reviewer, developmental advisor, plus pack agents | Author A and Author B |
| 5 Synthesize | Cluster on one noun phrase, coverage ledger (`audit_coverage.py`), caps of 6-8 comments with minors in one closing comment and 8-12 manuscript references, a theory-methods balance check on the first three comments, severity from contribution type and journal | Author A's ledger and clustering, Author B's caps and balance check |
| 6 Audit | Blinded paper's advocate (does not read discovery outputs), standards auditor, missed-criticisms pass, accuracy audit collapsed to one pass that tags each claim by adjudication type, quote matching (`verify_quotes.py`), citation existence (`verify_citations.py`, with the contact email in config), and claim attribution (`verify_claim_attribution.py`) on the tool's own draft, a stress test at Standard and Deep (Codex when installed, enabled, and consented; otherwise a fresh Claude agent on the judgment model; advisory) | Author B's QC, Author A's missed-criticisms and accuracy rules 1, 14, 15 |
| 7 Output | Any of issues list, annotated PDF, mock report, and, for a referee, the checked-facts memo for an editor, built from validated issues only. Audit package. | Author B's memo format, Author A's validator |

Adjudication follows Author B's model: every QC finding is ruled upheld, overruled, or reframed against the manuscript and recorded in the QC record. Two findings are protected. The skeptic's core problem may be narrowed but never dropped. A fabricated or misrepresented citation in the tool's own draft is always removed, never argued about. Author A's rule also applies: infeasibility is never a reason to drop a finding silently. Rulings on major issues go to the human at a check-in (section 7). The clustering tiebreaker changes from "generality of supporting literature" to the size of the threat to the claim, to correct Author A's lean toward methods.

## 5. Packs

A pack is a folder: `pack.yaml` (name, detection cues, slots, stages it turns off, severity rules), `agents/`, `checklists/` (each item tagged with its adjudication type), optional `scripts/`, and required `fixtures/` (a planted-error test paper and the list of what it must catch). Someone other than the pack's author plants the errors. A fixture counts as ready only after the pack's authors have read its test paper; until then `plumb validate-packs` reports the pack as `pending_planting`, and a run that uses it logs that status. A pack may set `overlay: true`. An overlay runs alongside any paper type when intake finds its cues and the user agrees at the start of the run; `plumb run-packs` lists it after the type packs. Seven packs are overlays: computational, nonlinear, inference, market-event (abnormal stock returns around announcements), network, configurational, and framing (how the introduction argues its contribution).

> **Ruled:** The checklist tags record each check's type, and many pack agents copy them into their findings, but no script reads them during a run. The fail-closed gates are scripts on numbers, quotes, and citations, which are Paper or External by construction, so they do not need the tag. The Stage 2 override analysis uses the adjudication label that synthesis writes on each issue in `stage-5/issues.json`, counting Paper and External as verifiable, and reports how often that label agrees with the authors' own coding of each issue as verifiable or judgment. Check-ins with no issue behind them are reported by stage. Whether findings should carry their checklist ids and tags through to the issue record is decided after that analysis.

| Pack | Owner | Base | Adds |
|---|---|---|---|
| Archival causal | Author A | Author A's methods checks, construction ledger, adversarial data-generating process, face validity, triangulation, mechanism discrimination | Author B's "industry-year fixed effects with industry-level arguments" and "lags as an endogeneity fix" items. Code and data path (section 6). |
| Computational | Author A | New | Measure validation, leakage, sensitivity to model and prompt, error propagation into later regressions, provenance. An agent recomputes F1 from the printed precision and recall, and accuracy, precision, and recall from a printed confusion matrix; the pack has no script. |
| Experiments | Author B | Author B's module | Author A's inference blocks (power, multiple testing, mediation identification, conjoint). Update the mediation guidance to current practice without going against field norms: accept bootstrapped indirect effects (PROCESS or equivalent) for inference, and flag confounding of the mediator as a separate issue, asking for a sensitivity analysis or a design that manipulates the mediator, with severity scaled to how central the mediation claim is. Add demand and Hawthorne effects as alternative explanations. Scripts: balance table, minimum detectable effect, sample-flow counts. |
| Qualitative | Author B | Author B's module | Author A's setting research adapted to the field site. A claim-to-excerpt map. A construct-to-codes ledger. |
| Theory | Author B | Author B's `theoretical.md` | Author A's theory logic and mechanism discrimination applied to propositions. The formal-model agent. No data-source research. |

Routing: the tool detects the paper type and the contribution type, and the user confirms both at setup. A paper can have two methods. The primary type sets severity. Findings from the second pack are capped at "Weakens a claim" unless they undermine the main claim. Types with no pack run the core only, and the output says the methods diagnosis is limited. If the user overrides the detected contribution type, the output says so.

The survey pack is the type pack for questionnaire studies. It adds two fingerprint lines (`Survey data:` and `Focal measures:`), shows them at the read check-in through `read_checkin_lines`, adds notes to completeness and face validity when it is the primary pack, and turns nothing off. Its verify agent runs a standard-library script that checks each printed correlation matrix against the rounding of its cells.

The simulation pack is a type pack for papers whose results come from running a simulation model; it turns off setting and timeline research, which have nothing to study in such a paper.

The meta-analysis pack is a type pack for meta-analyses and systematic reviews. It turns off the setting and timeline research and adds notes to five core agents and to the inference, nonlinear, survey, and archival agents that could read its pooled numbers.

The experiments, qualitative, and theory packs are type packs written by one of the authors and fitted to the pack mechanism through `pack.yaml` alone: his severity rules plus the chain's, turn-offs (timeline research for experiments; the ledger, setting and timeline research, and face validity for theory; nothing for qualitative), and notes to core agents, to other packs' agents, and to their own agents. The configurational pack is an overlay for qualitative comparative analysis. A QCA paper takes the type its sets' sources give it (qualitative, archival, or survey), and the overlay adds its checks through a verify agent that runs a standard-library script and three diagnose agents, with notes to core agents and to those three packs' agents; it turns nothing off.

A pack changes the core only through three `pack.yaml` fields, which `plumb/packs.py` checks when it loads the pack. `turns_off` lists core agents the pack turns off; only the construction ledger producer, setting research, timeline research, and face validity may be listed, and turning off the producer turns off the whole ledger unit. An agent is off only when every paper type chosen for the run has a pack and every such pack lists it; overlays never count. `core_notes` gives a note, as text or as a file in the pack, to a core agent, another pack's agent (`packs/<pack>/agents/<file>`, applied only when that pack runs), the Stage 4 compiler (`stage-4-compiler`), or the stress-test prompt (`stress-test-prompt`); notes apply whenever the pack runs and the target agent is not turned off, labeled with its role in the run. A note to the ledger producer also reaches the ledger checker. `read_checkin_lines` names fingerprint lines shown at the "Did we read the paper right?" check-in. `plumb core-adjust` works this out at intake, writes it to `run.json` as `core_adjust`, and leaves a stub file in place of each turned-off agent's output.

The core also checks every significance star against its coefficient and standard error, using the key under the table. Only a star that claims more than the numbers allow is flagged. Notes Plumb cannot fully read are skipped and counted, and a stated one-tailed test is honored.

> **Ruled:** No light variant for now. Detection cues gate only overlays. A paper typed archival gets the archival pack whether or not it names a design, so a paper that adds controls and writes "X increases Y" already runs the pack, with `Designs: none` and no design modules loaded. The pilot checks whether the archival agents over-flag such papers. A severity rule for that case is added only if they do.

Contribution types and what weighs most:
- **Theory testing:** identification and measurement.
- **Theory building:** grounding and plausibility, with identification demands downgraded.
- **Phenomenon-driven:** description and scope.
- **Methodological:** validation against ground truth.
- **Replication:** fidelity and power, with complaints about novelty suppressed.

## 6. Code and data path (archival pack, R and Python)

- **Read:** compare the code with the paper's description of variables, samples, fixed effects, clustering, and any hard-coded numbers.
- **Reproduce:** run the authors' code in a sandboxed copy of the package and check it produces the paper's numbers. Mismatches appear at the number-flags check-in.
- **Probe:** new analyses run with the user's approval. This is planned for 2027.
- Plumb never sends data files. The model sees the code and what it prints. Code can print rows of data, so the user attests that the data agreement allows sending printed output to the model provider (section 9).
- Anti-p-hacking rules apply. Every analysis is logged and reported whatever it shows. Tests challenge the claim, never rescue it. Each new analysis is a check-in.

> **Ruled:** The code and data path is not built in version 1, and the pack specs defer it. When it is built, what the authors' code prints goes to the model under the user's attestation in the consent record (section 9). No scrubber is planned, because none can reliably tell a printed data frame from a summary table.

## 7. Check-ins

The user picks the check-in level at the start of every run, on the first setup screen next to the depth, from most human control to least: Hands-on, Standard, Light, or Auto. After the consent questions and before anything reads the paper, setup shows a recap of every choice (permission, journal, depth, level, outputs, stress test, provider and retention, output folder) and asks one question, start or change something. That stop is asked at every level and is recorded as a preference, never an override. The level can be lowered partway through a run. Every screen follows one template: one sentence on what the tool did, findings in plain words with no agent names, lettered options with the recommended one first, and the time left. Packs must follow this template. On Claude Code and the Claude desktop app, the multiple-choice prompt delivers it. On Codex, it is lettered choices in chat.

Each stop runs as rounds, following the Grill Me method:
- The tool never asks the user a fact that the paper or an outside source can settle. An agent finds it.
- Each round asks every judgment call whose prerequisites are already answered, each with a recommended answer.
- Answers prune or unblock later questions. For example, an alternative explanation marked "not plausible" removes the major issues built on it.
- A stop ends when no open question remains.

| # | Check-in | After stage | Hands-on | Standard | Light | Auto |
|---|---|---|---|---|---|---|
| 1 | Set up this run | 0 | yes | yes | yes | yes |
| 2 | Number flags: real problem or extraction error | 1 | yes | yes | | |
| 3 | Did we read the paper right? | 2 | yes | yes | | |
| 4 | What is this paper arguing against? | 3 | yes | yes | | |
| 5 | Major issues, one card each: keep, downgrade, already addressed (give the page), dig deeper | 4 | yes | yes | yes | |
| 6 | Minor issues from the held list | 5 | one at a time | as a list | | |
| 7 | Review the draft and the QC record, including the adjudicator's proposed ruling and evidence on each major issue, which the user confirms or overturns | 7 | yes | yes | yes | |

Auto keeps only setup and logs every choice. The user wins every disagreement. Removing fabricated or misrepresented citations from the tool's own draft stays automatic.

## 8. Journal profiles

Each profile has two parts. The policy part is read from a journal AI policy dataset (Harmon 2026). It covers 92 journals, generated September 21, 2026, and every quote carries its source URL and retrieval date. The norms part is written by hand: bar, caps, tone, contribution weights, and journal notes, starting from Author B's notes and including the Organization Science "merely empirical" rule.

Referee mode rules:
- Off where uploading manuscripts is banned. Among the journals with a profile, that is SMJ, AMJ, and ASQ. A referee at a journal with no profile must confirm its policy, as the last rule says.
- Conditional where the journal allows tools that do not retain or train on manuscripts. For Organization Science and Management Science it needs an API account under zero data retention.
- Where AI drafting is barred, no report is written, and the issues list and annotated PDF hold checked facts only.
- Where the policy is silent on drafting, a mock report is allowed, with a disclosure line. That includes Organization Science.
- Management Science requires the conclusions to be the reviewer's own. Plumb treats it like Organization Science: all outputs, with a disclosure line on the report. The referee reads and adopts what they use.
- Journals not in the dataset stay off unless the referee confirms "My journal allows AI tools in review". The confirmation goes in the consent record and the audit package. The run then treats the journal as silent on drafting (a mock report with a disclosure line is allowed) and requires zero data retention. A journal whose profile bans uploading stays off.

We propose the profile format as a standard any journal could publish, and offer to pilot the Organization Science profile.

## 9. Consent and confidentiality

A consent record at setup is a hard gate. It answers three questions:
1. **Whose material is this?** For an author: do all coauthors agree? For a referee: what does the journal allow? (The author's consent at submission is asked only for a journal whose profile requires it.) For a replication package: does the data agreement allow this processing? For qualitative excerpts: a one-line attestation that the ethics approval and any site agreement allow sending the manuscript to a model provider. It is asked only in author runs, and only an explicit No blocks the run.
2. **What leaves the machine?** Manuscript text goes to the model provider, and search queries go to the search engine. Setup states this as a notice; starting the review at the recap is the agreement. Once the code and data path exists, what the authors' code prints goes to the model. Data files never leave.
3. **Under what terms?** Provider, training setting, and retention period. The training and retention answers are saved in the user's config and asked again after 90 days; zero data retention, where a journal needs it, is asked on every run.

The run does not start if a required consent is missing. The author and referee choice is self-reported, and the proposal says so.

In the Stage 1 pilot, the only referee reports used are the first-round referee reports the authors received on their own manuscripts. A Claude model, run through Claude Code, read them, rewrote each referee point as a one-line claim, and coded the classes and the matches. Results are reported only as counts, and no report is quoted. Referee reports on other people's manuscripts enter only in Stage 2, under the consent rule in section 14.

Models:
- Claude through the user's account is the default. Setup asks whether training is on for consumer plans.
- Other models are opt-in and blocked on free or personal tiers that train on inputs.
- Codex is optional. It runs only as the stress test, at Standard and Deep depth; without it a fresh Claude agent on the judgment model runs the same prompt with no memory of the run. When Codex runs, the consent screen names OpenAI as a second provider, with its own training and retention answers. A referee at a journal that requires zero data retention must confirm it for OpenAI too, or a fresh Claude agent runs the stress test instead; the run continues.
- Gemini is dropped.
- The interface is model-agnostic. A run of one open-weight model at Quick depth, with the quality gap reported, is planned, not built (section 13).

We also propose an author checkbox at Organization Science submission: "I consent to reviewers using AI tools that meet the journal's standards."

## 10. Audit package

One file per run. It contains:
- every verification and its result
- what the accuracy audit changed
- the QC adjudication record
- every check-in and override
- the consent record
- what left the machine and to which provider
- model versions and settings: the exact model ids observed in the transcripts, the roles that used each, and the call counts, from `models.json` in the run folder, or the configured aliases marked as not observed where usage was not measured; and the search date cap when one was set
- the dependencies used
- tokens, time, and API-equivalent cost by stage and by model, where the platform runs plugin hooks (the run folder's README repeats them)

A referee can attach it where a journal requires disclosure.

## 11. Voice and feedback

- The neutral default uses rules both systems agree on. Second person. No verdict language, summary section, reassurance, or closer. No predicted results for requested tests. No scaffolding between comments. Spell out niche acronyms. Cite to establish, not to prove.
- A learned voice is an optional per-user overlay in a fixed rule format: rule, banned forms, rewrite pairs, provenance. Verbatim example passages stay local and never ship. The overlay changes style only, never the structural bans.
- Author B's voice rules are organized under "Proportion and concision," emphasizing clarity and appropriate scope in the feedback.
- During a run the chat speaks in the first person and in plain words, with no agent, file, gate, or verdict names. It shows a stage header with a time estimate by depth, labeled "(estimate)" until medians from five or more measured runs replace the table. Findings appear as they arrive, marked provisional until the audit. Each stage ends with a result, and the run ends with one scoreboard of every stage. Everything else (dispatches, commands, retries, revision cycles) goes to a run log in the workspace. A warning exit reads as a warning. A blocked write inside the run folder is reported, logged, and written another way, and anything blocked outside it stops that step. Every agent writes files with the file-writing tool, never through shell commands.
- Feedback loop: Author B's post-run prompt and dated log. Add a diff of the user's edited file against the draft, and a promotion step that folds log entries into the overlay and marks entries that have been superseded.

## 12. Platforms

The tool is a set of small skills that chain, following Superpowers:
- `review` is the orchestrator.
- `check-numbers` is a short alias for Quick depth.
- `setup` configures the install.
- `writing-packs`, for contributors, is planned.

Stage files use six abstract actions (ask, dispatch, run in parallel, task list, web, run a command). One reference file per platform maps them to that platform's tools. Progress shows as a native task list, which replaces the browser progress page. There is no session-start hook. Claude Code and the Claude desktop app install the same plugin. Codex runs the same skill folders through a small adapter. It asks check-in questions as lettered choices in chat, and an AGENTS.md repeats the subagent instruction as a workaround for a known Codex issue. All three are built to run at every depth. Running open-weight models through `codex --oss` (gpt-oss through Ollama or LM Studio) at Quick depth, with the quality gap reported, is planned, not built (section 13). Every file copied from earlier tools passes a review for anything personal, confidential, or off-spec.

## 13. Dependencies for version 1

- **Required:** Claude Code, Python 3.9 or later, pymupdf, pdfplumber, requests, pyyaml. No hard-coded paths.
- **Optional, offered by the setup wizard:** Codex. A local open-weight model is planned, not built: setup does not offer one yet. Tables are read by two independent model transcriptions of each table's page image, compared cell by cell, so no table extractor is needed.
- **Hooks:** keep PreCompact and protect-files. Rewrite the notification hook to work on other systems. Drop stop-reminder. Add a usage hook on SubagentStop and Stop that records where each transcript is while a run is active; Stage 7 reads the transcripts and totals them.
- **Dropped:** Gemini, LaTeX, poppler.
- **Depth tiers:** Quick runs stages 0, 1, and 7, plus a check of the paper's reference list and the "Did we read the paper right?" check (Stage 2's construction ledger and summary, without web research). Standard runs everything. Deep runs everything with more searches (70-100 on the setting and 25-35 for each other research agent, against about 15 at Standard; the editor reader about 20, against about 10) and more revision cycles in each quality loop (4, against 2 at Standard). At Standard, only the Stage 2 summary compiler uses the config's mechanical model; every other agent, the table transcribers and the Stage 4 compiler included, uses the judgment model. At Deep, every agent uses the judgment model and may take more turns and write longer notes, with the same output caps. Standard and Deep run the stress test, through Codex or a fresh Claude agent; Quick has none.

> **Ruled:** The Docling table extractor (`extract_tables.py`, its dependency check, and its config key) was removed in PR #8, with `verify_reconciliation.py`, which no stage called either.

## 14. Evaluation

**Stage 1 (fall 2026).** Two tests, both on the authors' own material, so Stage 1 needed no IRB. Scripts in `eval/` produce every number, and the README says how to rebuild both tables from files in this repository. Referee reports and drafts stay private. Code, fixtures, and summary results are public.

- **Planted errors.** One Standard run on the hand-planted archival test paper (`packs/archival/fixtures/planted-1`), which carries 12 planted errors. Plumb caught 11. The run the scorer reads is stored in `eval/runs/planted-1-2026-10-19/`.
- **Referee comparison.** Plumb was run on four of the authors' own manuscripts and compared with the first-round referee reports each received (section 9). Every referee point and every Plumb point was coded as factual, substantive judgment, or preference, and an author of the papers rated the points blind to their source. The code, prompts, and aggregate counts are in `eval/referee_comparison/`.
- **Controls:** web search capped at each paper's submission date, in both tests. The cap is an evaluation option set by flag, not a setup question: `search_before` in `run.json`. Three routes write it: `plumb run-dir new --search-before <date>` when the run folder is made, `eval/run_fixture.sh`, which passes the `search_before` date in the fixture's `expected.yaml` to that flag, and `plumb search-cap <workspace> <date>` for an existing run. A `search_before` already in `run.json` stays in force. Every dispatched agent is told the cap, and Stage 7 fails an output that cites work dated after it; the model versions reported are the observed ids in `models.json`.

**Stage 2 (January to May 2027).** The colleague runs, the outside expert, the blind raters, and referee reports on other people's manuscripts move to Stage 2, with everything below that needs them. A university IRB covers them; the protocol is filed by November 15, 2026.

- **Headline, blind head-to-head at the issue level.** Sources:
  - ChatGPT and Claude on one fixed prompt (`eval/baseline.py`)
  - Plumb on Auto
  - Plumb on Standard, run by an author, and by a colleague who has not seen the referee reports
  - referee reports on other people's manuscripts, per paper, with the authors' consent and as the journal's policy allows

  All issues are pooled, deduplicated, and rewritten as one-line claims with page references (`eval/pool.py`). The authors rate correctness and one outside expert rates importance, both blind to source (`eval/rate_analysis.py`). The main number is valid, important issues found by only one source. The pool also includes points the reviewer overruled at a check-in, so the ratings show whether the reviewer or the tool was right on each override.
- **Planted errors** per pack fixture, reported by depth.
- **Reliability:** three runs per paper, overlap of major issues, recorded model versions, archived raw outputs. For Judgment items, compare the calls across the three runs. Where they often split, repeated draws are worth showing at the check-in. Where they agree, a single draw stays.
- **Costly overrides:** dismissed points the blind raters judged correct and important, reported by stage, pack, and adjudication type. Points the real referees also raised are reported alongside.
- **The "more" question:** pilot users report whether the tool changed when or whether they submitted.

Deferred: Refine as a source, and the full 8-12 papers (2027). Real corrected or retracted errors are on the back burner. Paired runs of the old and new pipelines on about six papers of different types happen after version 1 works.

## 15. Repository and scrub

- Before the repository goes public, every file is checked for personal paths, emails, manuscript numbers, and confidential text. `tests/test_scrub.py` fails if any of them comes back.

## 16. Team

- **Author A:** core shell, Verify, archival and computational packs, code and data path, audit package, scrub.
- **Author B:** theory, qualitative, and experiments packs, journal profiles, advocate and adjudication, memo and feedback loop, consent record.
- **Both:** check-in screens, evaluation, proposal.

## 17. Submission package

- **Proposal, 1,500-2,000 words:** question, adjudication types, design and check-ins, journal profiles as a standard, evaluation and pilot, consent and ethics.
- **Technical appendix:** architecture, pack format, profile schema, audit package format, pilot results, 2027 roadmap.
- **README:** install, a sample run, a short GIF of one check-in.

2027 roadmap:
- full evaluation with Refine
- editor mode (screening numbers, citations, and code with no decision)
- probing analyses
- browser check-in forms
- a standalone command-line version
- local-model mode
- R&R response-letter mode
- packs for the remaining types, open to outside contributors

## 18. Open items

- **Resolved (from the journal AI policy census):** the INFORMS leadership note does not bind reviewers. Assuming the note meant is the INFORMS Open Forum post of August 27, 2023, by Christopher Tang, VP of Publications, it sets no society-wide rule. Its two prohibition sentences quote the *INFORMS Journal on Computing*'s own policy as an example, and Tang delegated the rule to the editors of each journal. The rule in force is the INFORMS umbrella updated May 28, 2025, which permits AI tools in review if they "do not retain, share, or train on manuscript content." Management Science's own page still carries older 2023-generation wording. Plumb treats Management Science like any journal that allows AI tools in review, with zero data retention (section 8).
- How to keep web searches in referee mode from revealing the manuscript's subject.
- **Resolved October 5, 2026:** referee reports on other people's manuscripts enter the evaluation in Stage 2, per paper, with the authors' consent and as the journal's policy allows (section 14).
- Whether Organization Science requires replication packages.
- Measured cost and time per run.
- **Resolved:** the name is Plumb.
