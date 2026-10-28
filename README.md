# Plumb

A human-directed AI referee for management research. 

## Install

### Claude Code

    /plugin marketplace add <owner>/plumb
    /plugin install plumb@plumb
    /plumb:setup

### Claude desktop app

Build a zip of the repo and upload it.

    git archive --format=zip -o plumb.zip HEAD

Go to Your plugins in the desktop app and upload `plumb.zip`. Use it from the Claude tab or the Code tab.

### Codex

    bash adapters/codex/install.sh

This copies the skills into `~/.codex/skills` as `plumb-review`, `plumb-setup`, and `plumb-check-numbers`, and records the repo root. On Codex, call them by those names, for example `plumb-review` where Claude Code uses `/plumb:review`. Then copy `adapters/codex/AGENTS.md` into the folder where you run Codex, or merge it into your AGENTS.md.

In `~/.codex/config.toml`, set:

    [features]
    multi_agent = true

Turn on web search (`codex --search`). If you sign in to Codex with a personal ChatGPT plan, it may train on your content unless you turn that off. Plumb's consent check will ask about this.

At Standard and Deep depth, Plumb can use Codex for the stress test of the draft. It sends the paper's text and the draft's points to OpenAI, so the consent screen asks about OpenAI's training and retention settings. Without Codex, a fresh Claude agent runs the same stress test. If Codex sign-in fails while `OPENAI_API_KEY` is set in your shell, sign in again with the variable unset, for example `env -u OPENAI_API_KEY codex login`.

### After installing

Run the setup skill once, on any platform, before your first review. Plumb needs Python 3.9 or later.

## Run

    /plumb:review path/to/paper.pdf

## Depths

At the start of each run you choose how deep the review goes.

- **Quick** checks the tables, statistics, and arithmetic, whether the numbers in the text match the tables, and whether each work in the reference list exists with matching authors and year. It also shows a short summary of how it read the paper, for you to confirm. Its output is a list of the facts it checked. `/plumb:check-numbers` runs this depth.
- **Standard** runs every stage: understanding, theory, diagnosis, synthesis, audit, and output. Each research agent runs about 15 web searches. The audit includes a stress test of the draft. Codex runs it when it is installed and enabled and you agree to send the paper to OpenAI; otherwise a fresh Claude agent that has seen nothing else from the run does. The stress test is advisory and never stops the run. Quick has none.
- **Deep** runs the same stages with more searches (70-100 on the setting, 25-35 for each other research agent) and more revision cycles in the quality loops (4 instead of 2). Deep runs the same stress test.

## Packs

A pack adds checks for one kind of paper. Fourteen are built.

- **Archival** runs when you choose an archival paper type: identification, clustering, estimators for staggered adoption, first stages, and the setting's data-generating process.
- **Computational** is an overlay. It runs alongside any paper type when the paper builds a variable with a large language model, a classifier, a dictionary, a topic model, an embedding, an image model, or simulated respondents. It runs only if you agree at the start of the run. It checks validation on the paper's own data, whether prediction error is carried into the regressions or shown across prompts and models, disclosure of the model and prompt, training cutoffs against the sample years, leakage, and whether model output is read as causal.
- **Nonlinear** is an overlay. It runs alongside any paper type when a hypothesis rests on a squared term, an interaction, a logit, probit, count, or hazard model with an interaction, a log(1+y) outcome with many zeros, or a comparison of split samples. It runs only if you agree at the start of the run. It computes turning points and the slopes at the ends of the data, checks moderator values against the data's range, converts odds ratios at the base rate, and reads each claim against the test the paper offers for it.
- **Inference** is an overlay. It runs alongside any paper type, at Standard and Deep depth, when a hypothesis or the headline result rests on a coefficient and its standard error. It runs only if you agree at the start of the run. It records how each estimate's standard errors are computed, compares the clustering level with the level where treatment varies, counts clusters and treated groups, checks sentences that claim significance and stated effect sizes against the printed numbers, and reads multiple testing, significance wording, and nulls. For a paper aimed at SMJ it also checks the journal's 2016 reporting policy.
- **Survey** is a type pack. It runs when the paper type is survey: a questionnaire study that names no design for identification, or the second type of a design paper whose measures come from questionnaires. It checks whether each printed correlation table could come from any data, whether response counts, fit readings, and reliabilities match the paper's own numbers, who reported each variable and when, whether the scales hold up, and whether causal claims, controls, and mediation match a design that assigned nothing.
- **Market event** is an overlay. It runs alongside any paper type when a hypothesis rests on the stock market's reaction to announcements (cumulative abnormal returns). It runs only if you agree at the start of the run. It recomputes each t-statistic the paper identifies as the cross-sectional t from the mean, spread, and N; checks stars against the p-values the numbers allow, that window returns add up, and that sample counts reconcile; checks a few named events against outside records; and reads windows, confounding news, shared announcement dates, and the claims drawn from the reaction.
- **Network** is an overlay. It runs alongside any paper type when a hypothesis rests on a network measure other than a simple tie count, on a model of pairs of actors, on a whole-network model such as an ERGM or SAOM, or on a claim that an outcome spreads through ties. It runs only if you agree at the start of the run. It checks the arithmetic of density, degree, and dyad counts; the network's boundary, tie windows, and missing ties; affiliation data projected to one mode; brokerage measures against the number of contacts; standard errors for pairs that share an actor; tie-formation samples; whole-network model diagnostics; and claims of influence through ties.
- **Simulation** runs when you choose the simulation paper type: agent-based, NK landscape, March-style learning, system dynamics, and LLM multi-agent models whose results come from running code. It checks whether the model can be rebuilt from the paper, whether the code and run counts are reported, whether each reported difference is larger than run-to-run noise (a script does the arithmetic), whether claims stay inside the parameter region where the results hold, which model element produces each result, and whether the validation matches how far each claim reaches.
- **Meta-analysis** is a paper type. It runs on meta-analyses, meta-regressions, MASEM papers, and systematic reviews. It checks the flow of records, the search, the coding, and data sharing; recomputes conversions, I-squared, prediction and credibility intervals, and how far dependent effect sizes could widen an interval; compares the most heavily weighted primary studies with what was coded; and reads moderator, causal, and generality claims against what pooled evidence supports. It turns off the setting and timeline research, which do not fit a body of pooled studies.
- **Experiments** is a paper type. It runs on laboratory, online, field, vignette, conjoint, and audit experiments in which the treatment was assigned at random. It records each manipulation and measure word for word; checks random assignment, participant flow and exclusions, manipulation checks, power, the preregistration, each test statistic against its p-value, mediation, multiple testing, and whether claims reach past the sample and task; builds specific rival explanations; and reads the studies against each other. For a randomized encouragement design it runs the instrumental-variable checks that fit. It turns off the timeline research, since the treatment was assigned at random.
- **Qualitative** is a paper type. It runs on interview, case, ethnographic, process, and grounded-theory studies, and judges each by its own approach. It records the data, the coding structure, and every quoted excerpt; traces each construct and relationship in the model back to the evidence; checks each finding against the excerpts behind it; and builds specific rival readings. It asks for a larger sample, a reliability statistic, or statistical generalization only when the paper's own claims call for one, and no search tries to identify a disguised site.
- **Theory** is a paper type. It runs on conceptual papers, process models, typologies, integrative reviews, essays, and analytical models with proofs. It records the argument's definitions, premises, and propositions; checks whether each proposition follows, whether constructs are defined and used as defined, whether premises contradict each other, and whether the paper's account of prior work matches the works it cites. It turns off the checks that need data: the variable ledger, setting and timeline research, and magnitude benchmarks.
- **Configurational** is an overlay. It runs alongside the paper's type when the paper uses qualitative comparative analysis (crisp-set, fuzzy-set, or multi-value QCA), whether its sets come from interviews, records, or questionnaires. It runs only if you agree at the start of the run. It checks how each set is calibrated and whether its anchors have reasons; whether the truth table, its three thresholds, and a separate test of necessity are reported; whether the consistency, PRI, and coverage figures can all be true at once, recomputing them from printed membership scores when the paper prints them; and whether the paper's claims stay in set-theoretic terms, with robustness to its anchors and thresholds and links back to its cases.
- **Framing** is an overlay. It runs alongside any paper type, only if you agree at the start of the run. It records how the introduction frames its contribution: the move it makes, how strongly it makes it, how it portrays prior work, and whether the rest of the paper delivers that move. It then judges whether the frame carries the contribution, against how published introductions in the target journal frame theirs, and names the strongest frame the paper's own evidence can carry.

Papers of a type with no pack get the core checks only, and the review says so.

Every pack except framing comes with a test paper with planted errors and the list of what it must catch. The framing pack has only a placeholder answer key, with no test paper yet. One test paper has been signed off: the archival pack's hand-planted paper, `packs/archival/fixtures/planted-1`. A pack is ready only when all of its test papers are, so `python3 -m plumb validate-packs packs` (run from the repository root) still reports every pack as `pending_planting`, and a run logs that status for each pack it uses.

A pack can also turn off core checks that do not fit its papers, such as setting research for a paper with no data, and can add notes to core checks. Before the review starts, Plumb tells you what will be skipped, and the outputs say what did not run.

On every paper, Plumb checks each significance star against its coefficient and standard error, using the key printed under the table. It flags only a star that claims more than the numbers allow. A stated one-tailed test is honored. Notes Plumb cannot fully read are skipped, and the run counts the skips. Plumb also skips tables it cannot read as coefficient and standard error, including abnormal-return mean tables, which the market-event overlay checks when it runs, and percentage cells.

On every paper that states hypotheses, Plumb maps each hypothesis to the test the paper offers for it and shows you that mapping at the numbers check-in. It then checks each verdict against its estimate: the significance level the paper claims, the sign, a null hypothesis judged by its own framing, an interaction read by its product term, and the test the paper names as the test. It also flags a hypothesis that is never tested, one stated differently in different places, and one stated only after its results. A paper with no hypotheses skips these checks.

## Outputs

At the start of each run you pick any of the outputs below. Each one shows only the issues that survived the audit, that you kept at the check-ins, and whose facts were confirmed.

- **Issues list** (`issues_list.md`). The issues, most serious first. At Standard and Deep depth each comes with a fix. At Quick depth it lists checked facts only. Items Plumb dropped are listed at the end, with the reason.
- **Annotated PDF** (`<paper>_annotated.pdf`). A copy of your paper with each issue highlighted on its page. Red marks an issue that undermines the main claim, orange one that weakens a claim, and yellow a minor one. Page 1 is an index that links to each issue. Your PDF is never changed.
- **Mock referee report** (`mock_report.txt`). Plain text, ready to paste into a journal's review form. It is not offered at Quick depth.
- **Checked-facts memo for an editor** (`editor_memo.md`). A neutral summary of the paper, then the five most serious issues that survived the checks. Each gives its severity, both page numbers, what the paper claims there, the problem, why it matters for the main claim, and what would settle it. It never gives a recommendation, a score, or a desk-reject signal. Three things keep it that way: it has a fixed two-part layout, a check blocks explicit verdict wording, and you read the memo before using it. It is offered only when a journal sent you the paper for review and allows AI tools in review, at Standard or Deep depth.

Each page citation gives the page printed on the paper and the page your PDF viewer shows, as in "ms p. 30 (PDF p. 32)".

## During a run

At the start of each run, the first screen asks the depth and how often to check in. The questions end with a table of your choices, and you can change any of them before the review starts. No question asks about a search date cap. An evaluation run can cap its web searches at the paper's submission date with `python3 -m plumb run-dir new --search-before <date> <pdf>` (from the repository root), or through `eval/run_fixture.sh`, which reads the date from the fixture's `expected.yaml`. During the run the chat shows a header when each stage starts, with a time estimate for your depth. Findings appear as they arrive, marked provisional until the audit. Each stage ends with a short result, and the run ends with one scoreboard of every stage. Everything else the run does goes to `.workspace/run_log.md`. The time estimates come from `plumb/estimates.json` and stay labeled as estimates until measured runs replace them.

## Where the files go

Each run gets its own folder, `plumb_output/<date>/`. It sits in your project folder when the paper is inside it. Otherwise Plumb makes a folder named after the paper, next to the PDF. You can pick another place at the start of the run. The run folder holds your outputs, the paper summary, and a `README.md` that says what each file is. Everything else the run wrote is in a hidden `.workspace/` folder inside it.

## Tokens, time, and cost

In Claude Code and the desktop app's Code tab, Plumb's hooks note where each agent's transcript is while a run is active. At the end of the run, the run folder's `README.md` and the audit package report the input, output, cache-write, and cache-read tokens, the time, and an API-equivalent cost, by stage and by model. The cost uses the dated price table in `plumb/prices.json`: it is what the tokens would cost on Anthropic's API. On a subscription plan it is not what you pay. Tokens from a Codex stress test are counted when Codex reports them, without a price. The Claude tab and Codex run no hooks, so there the README says "Usage not measured in this app." The run also writes `.workspace/models.json`, a record of the exact model ids observed in the transcripts after the run, the work each did (mechanical or judgment), and the call counts. The settings name models by tier alias, so the same settings can resolve to a different id on another day; where usage was not measured the record lists the configured aliases and says they are not observed ids.

## Run the tests

From the repository root:

```
python3 -m pip install -r requirements-dev.txt
python3 -m pytest
```

Two name checks in `tests/test_scrub.py` and `tests/test_archival_modules.py` read a list of banned names from an untracked local file (`tests/.scrub_names.local`, or the path in `PLUMB_SCRUB_NAMES`; see `tests/scrub_names.py`). Without that file they are skipped.

## Reproducing the paper's tables

Both tables can be rebuilt from files in this repository, with no model calls.

- **Table 2** (recall on the planted archival test paper). The run it scores is stored in `eval/runs/planted-1-2026-10-19/`, holding only the files the grader reads and a README on how they were copied. From the repository root:

  ```
  python3 eval/score_fixture.py packs/archival/fixtures/planted-1 eval/runs/planted-1-2026-10-19 --out score.json
  python3 eval/table2.py score.json --out table_2.tex
  ```

- **Table 3** (referee points and Plumb's points, by class). The percentages come from the integer counts in `eval/referee_comparison/counts.json`:

  ```
  python3 eval/referee_comparison/table3_from_counts.py
  ```

  `eval/referee_comparison/README.md` describes the scripts that produced those counts and which of their inputs stay private.

## Evaluation

Each pack's test paper comes with an answer key, `fixtures/<id>/expected.yaml`, that lists what a run must catch, what it must not flag, and what is fair to raise. `python3 eval/score_fixture.py <fixture folder> <run folder>` scores a finished run against that key. Each entry is matched to an issue in `stage-5/issues.json` by a check id the issue carries, by the check id in the stage-4 file the issue came from, by its locator sentence, or by its page and the check's keywords, and the report says which. An issue is assigned to one entry only; the matching strategies run in that order, and within one strategy a must_catch entry takes an issue first, then also_fair, then must_not_flag. The priority holds only within a strategy: a must_not_flag entry matched by an earlier strategy takes the issue before a must_catch entry that a later strategy would match. It prints a JSON scorecard and a markdown table with totals by severity and by adjudication type, the run's depth, and the issues that match nothing in the key. A Quick run writes no `stage-5/issues.json` (its issues list holds checked facts only); the scorer reads those checked facts from `stage-7/validated.json` instead, and the card says so. With neither file a Quick run scores as zero issues: every must_catch entry missed and every must_not_flag entry clean. `bash eval/run_fixture.sh <fixture folder> <quick|standard|deep> <output folder>` runs Plumb on the fixture's paper at that depth with every check-in on Auto, then scores the run. Its headless call is untested until the first full run. `python3 eval/compare_runs.py <run folder> <run folder> ...` compares repeat runs of one paper: it matches each run's issues to the others' by the same key (a shared check id, a stage-4 check id with the same page, then text overlap), with a `--hand-matches` file applied first, and prints the mean pairwise Jaccard overlap of major issues, the share of Judgment items with the same call in every run (overall and by stop), severity agreement over the matched issues, and the issues each run alone raised. It refuses runs of different PDFs.

The scripts from here on are Stage 2 study tools; none of them produced Table 2 or Table 3. Table 3 comes from `eval/referee_comparison/` (see "Reproducing the paper's tables"). `eval/baseline.py` is the study's fixed-prompt comparison condition: it sends a paper and the prompt in `eval/baseline_prompt.txt` to `gpt-6-astra` and `claude-fable-5-1` over their APIs, three runs each, and archives every request and response in a folder you name outside the repo. It needs the `openai` and `anthropic` packages and keys in `OPENAI_API_KEY` and `ANTHROPIC_API_KEY`; a review never does. Run it only on papers whose consent record covers sending them to both providers. The PDF is sent to OpenAI and Anthropic; Anthropic retains it for up to 30 days.

The Stage 2 scripts below turn the study's runs into its numbers, in this order. `python3 eval/pool.py --paper <name> --auto <run folder> --standard <run folder> --baseline <baseline folder> --out <pool folder> --raters <a>,<b> --author <rater> --nonauthor <rater> [--joint]` builds the blind rating pool for one paper: every issue from the Auto and Standard runs, every point the Standard reviewer dropped at a check-in (kept on the claim as an overruled point with its stop and item id, and credited to no source), and every item in each baseline model's run of record. The pool groups these candidates by meaning. It applies the de-duplication standard Plumb's synthesis step applies before it clusters, which is stricter than its construct-level clustering, because the study asks whether sources found the same problem, not the same construct. One streamed call sends every candidate's text and page, numbered in an order set by a hash of each candidate (not by source), with no source label or severity, to `claude-fable-5-1` with its own ceiling of 64000 output tokens on the fixed prompt in `eval/pool_cluster_prompt.txt` (sha256 `e09ab796ed8d317aceb7f5c98b8a9621aeeb4fd67fb451a0bf48871cc649b75e`, fixed and checked in `plumb/eval_pool.py`), which returns groups of candidates that raise the same problem and keeps candidates apart when in doubt. A reply that leaves out a candidate, repeats one, or names one that does not exist stops the pool. Each group becomes one claim, holding every source in it and the union of their pages; a source with two candidates in one claim keeps the highest of their severities. pool.json records the call's model, usage, and request id, the ceiling, and the order the candidates were sent in. Each claim is then rewritten into one neutral line with page references by the same model on the fixed prompt in `eval/pool_rewrite_prompt.txt` (its sha256 is also fixed and checked before every call). The word-overlap rule (more than half of the shorter text's content words in the longer, with the printed pages agreeing) is now only the dry run's fallback, since a dry run calls no model; pool.json says which merge ran. The pool folder must be outside the repo. A baseline item's merge text is its title and its "what is wrong" field; its severity is read from the severity field only, and a file whose entry count and severity-label count disagree stops the pool unless `--accept-parse-count` is passed after a human check, which pool.json records as a departure. It writes `sealed/pool.json`, `sealed/mapping.sealed.json` (claim id to sources, types, and overruled points; closed until both sheets lock), `sealed/near_misses.json` (the pairs for a human check, in both directions, taken from the clustering before any hand merge: pairs from different sources that the overlap rule would have merged or nearly merged but the clustering kept apart, and pairs the clustering merged with less than 0.3 overlap), `sealed/clusters.json` (the checked clustering reply), `sealed/rewrites.json` (every finished rewrite, written as it lands), and `raters/sheet-<rater>.csv` per rater with random claim ids and the same "p. N" or "pp. N-M" page form on every claim, no source labels. The claim ids and the shuffle come from a seed drawn at random, or from `--seed`, and either way the seed is stored only in `sealed/pool.json` and never printed. The hand pass checks the grouping that ships, in two runs. First a clusters-only run with `--stop-after-clusters`: it calls the clusterer and writes `sealed/clusters.json` and `sealed/near_misses.json`, with no rewrite and no sheets. Read the near misses and write a file of candidate-ref pairs. Then the real run, into a new folder, with `--clusters-from <clusters-only folder>/sealed/clusters.json --hand-merges <file>`: it reuses those checked groups without another call, refuses them if the clustering prompt, the model, the effort, or the candidates have changed since, joins the hand pairs, rewrites, and writes the sheets; pool.json records the clusters file and its sha256 and the hand merges. The clusterer's merges are checked and recorded but cannot be reversed by the hand pass: a hand merge only joins claims, and there are no hand splits. A dry run with `--no-rewrite` names its sheets `sheet-<rater>.DRYRUN.csv` with a banner row; they must not be rated, and its near misses come from the overlap rule, not the clustering. Within one folder, the caches in `sealed/clusters.json` and `sealed/rewrites.json` mean a real run that fails partway can be run again into the same folder and pays only for what is still missing. The one result carried between folders is the clusters-only run's `sealed/clusters.json`, and only through `--clusters-from`; rewrites are never carried. The clustering and the rewrite need the `anthropic` package (its 1.x releases need Python 3.10); everything else keeps the 3.9 floor. `python3 eval/rate_analysis.py --sheet <rater>=<csv> --sheet <rater>=<csv> --mapping <pool folder>/sealed/mapping.sealed.json --author <rater> --nonauthor <rater> [--joint]` then prints, for that paper, the valid and important claims found by only one source, as counts and shares, under the author-validity and non-author-importance rule and under full agreement, by adjudication type with External apart, percent agreement and Cohen's kappa for correctness and importance, the share of claims each rater recognized, the headline on unrecognized claims, which sources were missing for the paper, and for each overruled point whether the blind ratings sided with the reviewer or the tool, by stop, pack, and adjudication type; the rater names and the author, non-author, and joint flags must match what `pool.py` recorded, and `--pool <result.json> ...` prints the per-paper and pooled numbers. `python3 eval/override_rate.py <run folder>` prints a Standard run's override rate with its denominators, by stage, stop, pack, and adjudication type, including demotions, alternatives marked handled, and audit rulings overturned, which never enter the pool. `python3 eval/report.py <fixture folder>=<run folder> ... [--runs <auto run folders> --hand-matches <file>]` scores every fixture run with the scorer, prints planted-error detection by depth, and hands the Auto run folders to `eval/compare_runs.py` for the reliability numbers.
