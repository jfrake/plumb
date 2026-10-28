from __future__ import annotations
import re
from pathlib import Path

import pytest
import yaml

from plumb import packs

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "review"
PACK = ROOT / "packs" / "inference"
IDS = ["I1", "I3", "I4", "I5", "I7", "I8", "I9", "I10", "I11", "I12", "I13", "I14", "I15", "I16"]
DEPENDENCE = ["I1", "I3", "I4", "I5", "I7", "I8", "I9", "I10"]
CLAIMS = ["I11", "I12", "I13", "I14", "I15", "I16"]
SEVERITIES = ("Undermines the main claim", "Weakens a claim", "Minor")


def _step_with(text, anchor):
    """The numbered step that contains anchor, found by its text, since a rebase may renumber steps."""
    steps = [s for s in re.split(r"\n(?=\d+\. )", text) if anchor in s]
    assert len(steps) == 1, (anchor, len(steps))
    return steps[0]


def _agent(name):
    return (PACK / "agents" / name).read_text(encoding="utf-8")


# --- Task 1: the Inference: fingerprint field and the setup question ---

def test_fingerprint_lists_inference_estimates_with_roles():
    text = (SKILL / "agents" / "manuscript-audit.md").read_text(encoding="utf-8")
    template = text.split("# Fingerprint", 1)[1].split("```", 1)[0]
    assert ("Inference:\n- <estimate: variable, table and column>: role: <main result | hypothesis>; errors: "
            "<as the paper states them, or \"not stated\">; clusters: <count, or \"not reported\">; treatment varies "
            "at: <level, or \"no treatment\">; treated groups: <count, or \"n/a\">") in template
    assert "plus at most one other estimate the abstract presents as a main finding" in text
    assert 'List the inference overlay under `Overlays:` only when `Inference:` is not "none".' in text


def test_fingerprint_counts_treated_groups_at_the_treatment_level():
    text = (SKILL / "agents" / "manuscript-audit.md").read_text(encoding="utf-8")
    assert ("nine treated provinces are nine treated groups whether the paper clusters by province or by firm"
            in text)
    assert "\u2014" not in text.split("Under `Inference:`", 1)[1].split("\n\n", 1)[0]


def test_stage_0_asks_about_inference_only_at_standard_and_deep():
    step = _step_with((SKILL / "stages" / "stage-0-intake.md").read_text(encoding="utf-8"),
                      "When no overlay is listed, ask none.")
    assert "the estimates and their standard errors for inference" in step
    assert "At Quick depth, do not ask about the inference overlay; it runs at Standard and Deep only." in step


# --- Task 4: the pack's frame ---

CHECKLIST = {i["id"]: i for i in yaml.safe_load(r"""
- {id: I1, text: "The standard-error method and clustering level are stated for every estimate a hypothesis rests on, and the clustering level is not below the level at which the treatment or key regressor varies; a paper that clusters below that level states a design reason", adjudication: paper}
- {id: I3, text: "The number of clusters (per dimension, for multiway clustering) is reported for every clustered estimate where the count could be below about 50 or cannot be read from the text; with fewer than about 30 clusters, or clusters of very unequal size, the paper uses and names a small-sample method (wild cluster bootstrap, CR2 or Bell-McCaffrey degrees of freedom, randomization inference) and reports what was resampled, the number of replications, the bootstrap weights, and whether the null was imposed", adjudication: paper}
- {id: I4, text: "When few groups at the level where treatment varies are treated (a single treated firm, province, industry, or shock, or a handful), the number of treated groups is reported and inference does not rest on cluster-robust t tests or an unrestricted wild cluster bootstrap; the paper uses a method built for few treated groups (such as Conley-Taber, Ferman-Pinto, permutation over control units, or a subcluster bootstrap) and states its assumptions", adjudication: paper}
- {id: I5, text: "In a panel where the outcome and the treatment or key regressor persist over time, the standard errors allow correlation within a unit over time; heteroskedasticity-robust errors alone, or clustering on period alone, do not count", adjudication: paper}
- {id: I7, text: "The number of clusters does not exceed N or the number of units the paper describes; where the paper's own counts point to dropped singleton groups (N falls across columns on the same sample with no stated reason, or clusters exceed the units described), their handling is stated and the cluster count reported is the count after dropping", adjudication: paper}
- {id: I8, text: "When the treatment or outcome is geographic or shared by a subset of units (neighbors, an industry, a region) through shocks that period fixed effects do not absorb, dependence across those units is addressed with coarser clusters, spatial or cross-sectional robust errors, or a stated reason it is small", adjudication: judgment}
- {id: I9, text: "When observations are grouped in teams, sessions, classrooms, or other units whose members share shocks, or in the higher-level units of a multilevel model, and the number of groups is small, the errors respect the grouping, a finite-sample correction is used, and the number of independent groups is reported beside N", adjudication: paper}
- {id: I10, text: "When an estimated regressor enters a main-result or hypothesis regression (a frontier or productivity score, an estimated fixed effect, a predicted value, a control-function residual), the standard errors account for the first step by a stated correction or a bootstrap over both steps", adjudication: paper}
- {id: I11, text: "When one hypothesis is tested on several outcomes, treatments, or subgroups, the paper names the family and reports adjusted inference (familywise, false discovery rate, or a summary index) beside the unadjusted results, and any correction the paper claims matches its own p-values", adjudication: paper}
- {id: I12, text: "The specifications, samples, and estimators tried are disclosed, and the headline result is not shown to depend on a single analytic path, such as a threshold crossed only after added controls, a sample restriction, or a clustering choice with the alternatives unreported", adjudication: judgment}
- {id: I13, text: "Each test a hypothesis rests on can be recomputed from what is reported (coefficient, standard error, exact p-value or interval, N, number of clusters); one-tailed tests are stated, used only for directional hypotheses, and used consistently; the paper says which test its marks come from when that is not the standard error shown; and the text's significance wording agrees with the reported values, with no \"marginally significant\" or \"trend\" offered as support and no \"significant\" for an estimate whose interval covers zero", adjudication: paper}
- {id: I14, text: "For a paper aimed at SMJ, results are reported with standard errors or exact p-values and without asterisks, the text does not use cut-off levels of significance as the test of a hypothesis, and the size of each key effect is discussed", adjudication: external}
- {id: I15, text: "The size of each key effect is stated in the outcome's units or in standard deviations, with an interval, over a meaningful change in the regressor, and a small p-value in a large sample is not offered as evidence that an effect is large or important", adjudication: paper}
- {id: I16, text: "A non-significant estimate is not read as showing no effect, no difference, or a ruled-out mechanism unless its interval excludes effects of a size that would matter, and a claim that an effect differs across groups rests on a test of the difference, not on one estimate being significant and the other not", adjudication: judgment}
""")}


def test_inference_pack_loads_as_an_overlay():
    p = packs.load_pack(PACK)
    assert p.name == "inference" and p.overlay is True and p.turns_off == []
    assert "context" not in p.slots and "theory" not in p.slots
    assert [i["id"] for i in p.checklist] == IDS
    assert "setup_question" not in yaml.safe_load((PACK / "pack.yaml").read_text(encoding="utf-8"))


def test_checklist_matches_the_spec():
    items = {i["id"]: i for i in packs.load_pack(PACK).checklist}
    assert set(items) == set(CHECKLIST) and "I2" not in items and "I6" not in items
    for k in IDS:
        assert items[k]["text"] == CHECKLIST[k]["text"], k
        assert items[k]["adjudication"] == CHECKLIST[k]["adjudication"], k
    assert {k for k in IDS if items[k]["adjudication"] == "judgment"} == {"I8", "I12", "I16"}
    assert items["I14"]["adjudication"] == "external"


def test_severity_rules():
    rules = packs.load_pack(PACK).severity_rules
    assert len(rules) == 6
    first = rules[0]
    for s in ("main result", "'Undermines the main claim'", "(a) I1", "(b) I4", "(c) I13", "(d) I16", "at or above",
              "no rounding of the printed digits"):
        assert s in first, s
    assert not any("2.6" in r for r in rules)
    assert rules[1].startswith("Any other issue on an estimate whose role is main result is 'Weakens a claim'.")
    assert "capped at 'Weakens a claim'" in rules[2]
    assert rules[3].startswith("I14") and "'Minor'" in rules[3] and "precedence over rule 2" in rules[3]
    assert rules[4].startswith("I12") and "never the authors' intent" in rules[4]
    assert "once per check per paper" in rules[5]


def test_read_checkin_shows_the_inference_lines():
    assert packs.load_pack(PACK).read_checkin_lines == ["Inference:"]


def test_journal_rules_row_is_complete():
    rows = yaml.safe_load((PACK / "data" / "journal_rules.yaml").read_text(encoding="utf-8"))
    assert list(rows) == ["smj"]
    row = rows["smj"]
    for key in ("rule", "quote", "quote_effect_sizes", "source", "url", "checked_on"):
        assert str(row.get(key) or "").strip(), key
    assert "10.1002/smj.2477" in row["source"] and "significance" in row["quote"].lower()
    assert len(row["quote"]) >= 40 and "\u2014" not in row["quote"] + row["rule"]
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", str(row["checked_on"]))


def test_fixture_is_labeled_synthetic():
    exp = yaml.safe_load((PACK / "fixtures" / "planted-1" / "expected.yaml").read_text(encoding="utf-8"))
    assert exp["synthetic"] is True and exp["owner"] == "blind-agent" and exp["journal"] == "smj"
    assert exp["label"] == "SYNTHETIC TEST PAPER, NOT REAL RESEARCH"
    assert exp["status"] in ("pending_planting", "ready")
    for key in ("must_catch", "must_not_flag", "also_fair"):
        for item in exp.get(key) or []:
            assert {"check", "page", "locator", "note"} <= set(item), item
            assert item["check"] in IDS, item
    for item in exp.get("must_catch") or []:
        assert item.get("severity") in SEVERITIES, item
    plants = {(i["check"], str(i["page"])) for i in exp.get("must_catch") or []}
    for d in exp.get("must_not_flag") or []:
        assert (d["check"], str(d["page"])) not in plants, d



# --- Task 5: the inference-numbers agent (verify slot) ---

def test_numbers_agent():
    assert packs.load_pack(PACK).slots.get("verify") == ["inference-numbers.md"]
    text = _agent("inference-numbers.md")
    for s in ("stage-1/inference_numbers.md", "stage-1/inference_ledger.md", "## Tables read", "## Flags", "## Notes",
              "## Not computed", "Record: <id>. Table: <label>. Cells: <table:row:col, ...>.",
              "Other estimates of the same result with other errors", "never flag it",
              "Flag nothing as missing", "Do not copy the core's star flags"):
        assert s in text, s
    for kind in ("`family`", "`magnitude`", "`interval`"):
        assert kind in text, kind
    assert "star_schemes" not in text and "--stars" not in text


def test_numbers_agent_runs_both_scripts_with_its_own_tools():
    text = _agent("inference-numbers.md")
    assert "tools: [Read, Write, Bash, Glob]" in text.split("---", 2)[1]
    assert "The orchestrator will provide `PDF_PATH`, `PAGE_COUNT`, `{WORKSPACE}`, and `{PLUGIN}`." in text
    assert ("`python3 {PLUGIN}/skills/review/scripts/verify_arithmetic.py --claims "
            "{WORKSPACE}/stage-1/significance_claims.json {WORKSPACE}/stage-1/inference_claims_check.md "
            "--json {WORKSPACE}/stage-1/inference_claims_check.json`") in text
    assert ("`python3 {PLUGIN}/packs/inference/scripts/inference_arith.py "
            "{WORKSPACE}/stage-1/inference_inputs.json {WORKSPACE}/stage-1/inference_arith.json`") in text
    assert "with the file-writing tool" in text
    assert not re.search(r"(cat|echo|printf|tee)[^\n`]*>", text)


def test_numbers_agent_stops_at_quick_and_counts_treated_groups():
    text = _agent("inference-numbers.md")
    assert "If `depth` is `quick`" in text and "Not run at Quick depth; the core star check ran." in text
    assert "nine treated provinces are nine treated groups whether the paper clusters by province or by firm" in text
    assert '"tails": "unstated"' in text and '"directional": true' in text


# --- Task 6: the inference-dependence agent ---

def _diagnose_common(name, owned, out_file, heading):
    p = packs.load_pack(PACK)
    text = _agent(name)
    assert f"stage-4/{out_file}" in text and f"Pack: inference\n# {heading}" in text
    for c in owned:
        assert re.search(rf"^### {c}\. ", text, re.M), c
    for s in ("Excerpt:", "Page:", "Estimate: <estimate> (<role>)", "## Checked and fine",
              "Severity: <Undermines the main claim | Weakens a claim | Minor>", "Never predict",
              "The works named in this file are background for you.", "skills/review/shared/contracts.md",
              "Flag an absence only after searching the methods section, the appendices, the footnotes, and every table, "
              "and name where you looked.",
              "Write a finding that only notes a missing report once per check, listing every estimate it applies to.",
              "Reply to the orchestrator in one sentence", "read `Designs:` as corrected there"):
        assert s in text, s
    for rule in p.severity_rules:
        assert rule in text
    assert "maxTurns: 30" in text.split("---", 2)[1]
    return text


def test_dependence_agent():
    assert packs.load_pack(PACK).slots.get("diagnose", [])[:1] == ["inference-dependence.md"]
    text = _diagnose_common("inference-dependence.md", DEPENDENCE, "inference_dependence.md", "Inference dependence")
    assert "up to 3 web fetches" in text and "Search before you fetch" in text


def test_dependence_agent_undermines_only_with_the_papers_own_coarser_estimate():
    text = _agent("inference-dependence.md")
    i1 = text.split("### I1. ", 1)[1].split("\n### ", 1)[0]
    assert "Only when that estimate exists" in i1 and "Without it, the issue is 'Weakens a claim'." in i1
    assert "Whether the corrected standard error is that large is not yours to decide." in i1
    assert "2.6" not in text


def test_dependence_agent_counts_treated_groups_not_clusters():
    text = _agent("inference-dependence.md")
    i4 = text.split("### I4. ", 1)[1].split("\n### ", 1)[0]
    assert "Count treated groups at the level where treatment varies, from the ledger, not clusters." in i4
    assert "write one issue under I4, cite I1 in it, and rate it at the higher of the severities I1 and I4 each give" in i4
    assert "caps the issue at 'Weakens a claim'" in i4 and "When `Designs:` lists SC" in i4


def test_dependence_agent_narrow_checks_and_exclusions():
    text = _agent("inference-dependence.md")
    for s in ("a firm panel with thousands of firms needs no count", "Never raise singletons for a paper whose counts are consistent",
              "Period fixed effects absorb shocks common to all units in a period.",
              "A generated outcome's first-step error sits in the residual; do not raise it.",
              "When `Designs:` lists IV, skip shift-share estimates", "When `survey` is in `run.json` `packs`, the survey pack checks only the justification for aggregating",
              "When `experiments` is in `run.json` `packs`, skip I3 and I9 for randomized designs",
              "When `computational` is in `run.json` `overlays`, skip every variable listed under `Generated variables:`",
              "the RD module owns it (RD8)", "the market event-study pack owns them", "the network pack owns it",
              "generalized synthetic control estimator in every check", "skip shift-share estimates in every check"):
        assert s in text, s


def test_diagnose_agents_skip_dropped_flags_and_their_records():
    for name in ("inference-dependence.md", "inference-claims.md"):
        text = _agent(name)
        assert "{WORKSPACE}/stage-1/dropped_flags.md" in text
        assert "whose `id` matches a dropped flag's `Record:`" in text
        assert "map it to that flag's `Record:` line" in text
        assert "If the file is missing, no flag was dropped." in text


# --- Task 7: the inference-claims agent and coverage ---

def test_claims_agent():
    assert packs.load_pack(PACK).slots.get("diagnose") == ["inference-dependence.md", "inference-claims.md"]
    text = _diagnose_common("inference-claims.md", CLAIMS, "inference_claims.md", "Inference claims")
    assert "You do not search the web." in text


def test_claims_agent_gates_i14_on_smj_and_reads_the_data_file():
    i14 = _agent("inference-claims.md").split("### I14. ", 1)[1].split("\n### ", 1)[0]
    assert "only when `run.json` `journal` is `smj`" in i14 and "`journal_rules.yaml`" in i14
    assert "SMJ's editorial policy (Bettis et al. 2016)" in i14 and "check the current author guidelines" in i14
    assert "never from a journal profile" in i14 and "profiles/" not in _agent("inference-claims.md")


def test_claims_agent_builds_on_core_star_flags_and_honors_tails():
    text = _agent("inference-claims.md")
    i13 = text.split("### I13. ", 1)[1].split("\n### ", 1)[0]
    assert "`stars_vs_se`" in i13 and "one-tailed" in i13 and "marginally significant" in i13
    assert "a mark one level too generous is 'Weakens a claim'" in i13
    i12 = text.split("### I12. ", 1)[1].split("\n### ", 1)[0]
    assert "never call the paper p-hacked" in i12


def test_claims_agent_exclusions():
    text = _agent("inference-claims.md")
    for s in ("When `experiments` is in `run.json` `packs`, skip randomized designs",
              "heterogeneity tests from machine-learning estimators",
              "When `nonlinear` is in `run.json` `overlays`, leave the size of every term listed under `Nonlinear terms:`",
              "when `nonlinear` is in `run.json` `overlays`, leave that claim to the nonlinear pack",
              "must be the paper's own word or the paper's own main effect"):
        assert s in text, s
    assert "{WORKSPACE}/stage-1/dropped_flags.md" in text and "whose `id` matches a dropped flag's `Record:`" in text


def test_every_active_check_is_owned_by_one_diagnose_agent():
    owners = {}
    for name in packs.load_pack(PACK).slots["diagnose"]:
        for c in re.findall(r"^### (I\d+)\. ", _agent(name), re.M):
            owners.setdefault(c, []).append(name)
    assert sorted(owners, key=lambda c: int(c[1:])) == IDS
    assert all(len(v) == 1 for v in owners.values()), owners


def test_agents_leave_car_mean_tables_to_the_market_event_pack():
    numbers = _agent("inference-numbers.md")
    assert "Tables of mean tests on abnormal returns (CAR or CAAR by event window) belong to the market event-study pack" in numbers
    assert "a sentence that reports a mean test on abnormal returns" in numbers
    assert '"abnormal-return mean tests, which the market-event overlay checks when it runs", which you leave out' in numbers
    assert "abnormal-return mean tests, which the market-event overlay checks when it runs" in (SKILL / "scripts" / "verify_arithmetic.py").read_text(encoding="utf-8")
    dep = _agent("inference-dependence.md")
    assert "Skip tables of mean tests on abnormal returns (CAR or CAAR by event window) in every check, I8 included" in dep
    i13 = _agent("inference-claims.md").split("### I13. ", 1)[1].split("\n### ", 1)[0]
    assert "Read the core star results for regression-coefficient tables only" in i13
    assert "you do not list, discuss, or re-read their marks" in i13
    # Final fix C: the exclusions hold only when the market-event overlay runs.
    gate = "when `market-event` is in `run.json` `overlays`; otherwise read them as any other table (a mean over its SD is not a coefficient over its SE)"
    assert "belong to the market event-study pack: leave them out of every step " + gate in numbers
    assert "`{WORKSPACE}/run.json`: `depth` and `overlays`." in numbers
    assert "you do not list, discuss, or re-read their marks " + gate in i13
    assert "the market event-study pack owns them " + gate in dep



# --- Task 8: the archival hand-off ---

def test_core_note_hands_off_to_methods_checks():
    notes = packs.load_pack(PACK).core_notes["packs/archival/agents/methods-checks.md"]
    assert len(notes) == 1
    for s in ("CHECK 5", "Cragg-Donald", "CHECK 7b", "Panel Methods", "CHECK 7;", "CHECK 6", "separation",
              "CHECK 10", "plausibility against benchmarks", "Report none of these.", "CHECK 4b",
              "DiD estimates included", "generated regressor"):
        assert s in notes[0], s
    assert "\u2014" not in notes[0]


def test_check_7b_waits_for_the_papers_own_coarser_estimate():
    text = (ROOT / "packs" / "archival" / "agents" / "methods-checks.md").read_text(encoding="utf-8")
    bullet = text.split("- **Inference at the wrong cluster level for the treatment.**", 1)[1].split("\n", 1)[0]
    assert "30-50% SE inflation" not in bullet and "between 2.0 and 2.5" not in bullet
    assert "Rate **Moderate**." in bullet and "Rate **High** only when the paper itself also reports" in bullet
    assert "Do not infer the corrected standard error from the t-statistic" in bullet
    assert "\u2014" not in bullet


def test_task8_fix_round_1():
    m = (ROOT / "packs" / "archival" / "agents" / "methods-checks.md").read_text(encoding="utf-8")
    assert "call it Moderate, unless the pattern states its own rule." in m
    assert "not by your discretion (unless the pattern states its own rule)" in m
    assert "for the clustering error, rate **Moderate**" in m
    assert "20-30 groups" not in m and "MacKinnon and Webb 2017" in m
    note = packs.load_pack(PACK).core_notes["packs/archival/agents/methods-checks.md"][0]
    for s in ("except SC and shift-share IV estimates", "DiD estimates included", "minimum detectable effect",
              "bullets 1, 2, and 5 of CHECK 6 (keep separation, events per variable, the minimum detectable effect, and whether a positive finding's interval is informative)", "fourth pattern", "higher-level units"):
        assert s in note, s
    dep = (ROOT / "packs" / "inference" / "agents" / "inference-dependence.md").read_text(encoding="utf-8")
    assert "only when `run.json` `packs` lists `network`" in dep and "Aronow, Samii, and Assenova 2015" in dep


def test_final_fix_wave_a():
    claims = _agent("inference-claims.md")
    excl = claims.split("### I16. ", 1)[1].split("\n## Output", 1)[0].split("### Exclusions\n", 1)[1]
    assert "When `Designs:` lists SC, skip estimates from a synthetic control, synthetic difference-in-differences, or generalized synthetic control estimator in every check" in excl
    assert "When `Designs:` lists IV, skip shift-share estimates in every check" in excl
    step1 = _agent("inference-numbers.md").split("### Step 1. The ledger", 1)[1].split("\n### ", 1)[0]
    assert "When `Designs:` lists SC or IV, leave out synthetic control and shift-share estimates in every step." in step1
    assert "also `Designs:`, for the exclusion in Step 1" in _agent("inference-numbers.md")
    note = packs.load_pack(PACK).core_notes["packs/archival/agents/methods-checks.md"][0]
    assert ("This applies to every estimate, DiD estimates included, except SC and shift-share IV estimates, which stay "
            "with the design-checks agent, and takes precedence over the design-module and nonlinear hand-offs in your "
            "instructions for these items.") in note
    assert "first five bullets" not in note and "hand-offs above" not in note
    i9 = _agent("inference-dependence.md").split("### I9. ", 1)[1].split("\n### ", 1)[0]
    assert "or in the higher-level units of a multilevel model" in i9
    rdd = (ROOT / "packs" / "archival" / "modules" / "rdd.md").read_text(encoding="utf-8")
    assert ("RD inference (RD1) and clustering on the running variable (RD8) are this module's; the inference overlay "
            "skips clustering on the running variable.") in rdd
    rd6 = rdd.split("### RD6. ", 1)[1].split("\n### ", 1)[0]
    assert "Bandwidth, kernel, and polynomial variants are robustness of one test and stay with RD6." in rd6
    assert ("Several RD outcomes offered for one claim are a family for the inference overlay (I11) when it runs, and "
            "for methods-checks CHECK 7 otherwise.") in rd6
    assert "Counting RD specifications across bandwidths" not in rdd and "Leave the count of specifications" not in rdd


# --- Task 10: README and repo spec ---

def test_readme_and_spec_name_the_inference_overlay():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert len(re.findall(r"A pack adds checks for one kind of paper\. \w+ are built\.", readme)) == 1
    assert readme.index("- **Nonlinear** is an overlay.") < readme.index("- **Inference** is an overlay.")
    assert "- **Inference** is an overlay." in readme
    spec = (ROOT / "docs" / "spec.md").read_text(encoding="utf-8")
    assert "Seven packs are overlays: computational, nonlinear, inference, market-event" in spec
