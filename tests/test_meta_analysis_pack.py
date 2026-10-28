from __future__ import annotations
import re
from pathlib import Path

import pytest
import yaml

from plumb import packs

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "review"
PACK = ROOT / "packs" / "meta-analysis"
IDS = [f"M{i}" for i in range(1, 19)]


def _audit():
    return (SKILL / "agents" / "manuscript-audit.md").read_text(encoding="utf-8")


# --- Task 1: the manuscript audit types a meta-analysis and records its syntheses and counts ---

def test_fingerprint_has_meta_analysis_fields():
    text = _audit()
    template = text.split("# Fingerprint\n", 1)[1].split("```", 1)[0]
    assert "Synthesis: <" in template and "Meta-analytic counts: <" in template
    assert template.index("Designs:") < template.index("Synthesis:") < template.index("Meta-analytic counts:")
    for s in ("pooled effect sizes; meta-regression or subgroup moderators; MASEM; publication-bias correction; "
              "artifact corrections; second-order; systematic review without pooling",
              "articles or studies, independent samples, effect sizes, total N",
              "Write \"n/a\" in both fields when the paper is not a meta-analysis or systematic review "
              "(as its main or second type)."):
        assert s in text, s


def test_type_rules_for_meta_analysis():
    text = _audit()
    for s in ("A systematic review with or without pooled effect sizes, a meta-regression, a MASEM, or a "
              "second-order meta-analysis is `meta-analysis`.",
              "A narrative or integrative review that states no search and coding protocol is `theory`.",
              "A primary study that adds a short meta-analysis of its own studies, or uses a published pooled "
              "estimate as a benchmark, keeps its own type.",
              "A meta-analysis is not also `archival` or `survey` because it pools correlations or corrects for "
              "reliability; give it a second type only when the paper also collects and analyzes new primary data."):
        assert text.count(s) == 1, s
    assert "\u2014" not in text.split("There is no correlational type", 1)[1].split("\n", 1)[0]


POOLED = ("Pooled effect sizes, moderator and subgroup tests, and publication-bias tests in a meta-analysis are not "
          "estimates from data the paper collects: do not list them under `Inference:`, `Nonlinear terms:`, or "
          "`Market event analyses:`. List only estimates the paper computes from new primary data.")


def test_pooled_estimates_stay_off_the_overlay_lines():
    text = _audit()
    assert text.count(POOLED) == 1
    assert (text.index("For a meta-analysis, list under `Synthesis:`") < text.index(POOLED)
            < text.index("Overlays are packs that run alongside any paper type"))



# --- Task 3: the pack's frame ---

JUDGMENT = {"M16", "M17"}
EXTERNAL = {"M6", "M7"}
CHECKLIST = {
    "M1": "A flow of records (identified, removed before screening, screened, excluded with reasons, assessed in full text, included) is reported with counts at every stage, the counts add up, and the included count matches the k analyzed in the same unit",
    "M2": "The search can be repeated: the databases and other sources, the search strings, the date range or the date the search ended, and any hand searching, reference chasing, or calls for unpublished work",
    "M3": "Unpublished work (dissertations, working papers, conference papers, data from authors) was sought, and published and unpublished effect sizes are compared, or the paper explains why neither was possible",
    "M4": "Inclusion and exclusion criteria are stated as rules set before coding; more than one person screened or coded, or a second person checked the coding, and agreement is reported (one overall figure, or agreement on effect size and N, is enough); the paper says whether it coded only hypothesized effects or all reported ones, and states how effect directions were aligned",
    "M5": "Every effect size conversion is documented and uses the right formula and degrees of freedom; regression coefficients, standardized betas, and partial correlations are not pooled with zero-order correlations without a stated method and a result with them removed; and effect sizes measured at different levels of analysis are not pooled without a level moderator or a stated reason",
    "M6": "For the included studies that carry the most weight, the coded sample size and data source, and the coded effect size where the primary study reports the same statistic, match what the primary study reports",
    "M7": "No sample enters twice: articles that reuse the same data set, survey wave, or panel are identified and treated as one sample; in a second-order or umbrella review, primary studies shared by the included meta-analyses are identified",
    "M8": "Dependent effect sizes (several from one sample or study) are handled by averaging, one per sample, a multilevel or multivariate model, or robust variance estimation, and k, standard errors, and tests reflect independent samples, not effect sizes",
    "M9": "The model (fixed, random, or mixed effects), the between-study variance estimator, and the tradition (Hunter-Schmidt psychometric or Hedges-Olkin) are stated, statistics from the two traditions are labeled where they are mixed, and the inference matches the model: a fixed-effect result is not generalized beyond the studies included",
    "M10": "Heterogeneity is reported as tau (or tau-squared, or SD rho) on the effect size scale with a prediction or credibility interval; I-squared and Q are not read as the range of true effects, and any claim that the effect holds across settings fits that interval",
    "M11": "Corrections for measurement error or range restriction state each input and where it came from (the same measure and population), use the direct or indirect range restriction model that fits, report corrected and uncorrected estimates side by side, and say what reliability means for any firm-level archival measure they correct",
    "M12": "Outliers and influential studies are examined with a stated rule or influence diagnostics suited to the model, and the main estimate is reported with and without them and without any single study that carries a large share of the weight",
    "M13": "A MASEM states its pooling method (univariate, two-stage, or one-stage), the sample size used to fit the model and why, the number of studies and total N behind each cell of the pooled matrix, the missing cells, and heterogeneity, and does not read fit statistics as if they came from one sample",
    "M14": "Publication bias and selective reporting are assessed with more than one method and read with their caveats: fail-safe N alone does not count, funnel asymmetry is not equated with publication bias, a trim-and-fill estimate under heterogeneity is not read as the true effect, and the paper notes when its tests assume independent effect sizes that are not independent",
    "M15": "Moderators are tested in a model with residual heterogeneity (mixed-effects meta-regression, or a test of the difference between subgroups), with the k in each subgroup, attention to moderators that move together, and a correction or caveat for the number of tests, and moderator and boundary-condition claims rest on those tests",
    "M16": "Causal, mechanism, and mediation claims fit the design: pooled correlations from observational studies, study-level moderators, and meta-analytic mediation are described as associations unless the primary designs were coded and the claim rests on the designs that support it",
    "M17": "The size of the pooled effect is described against a benchmark suited to the field or in substantive units, not by Cohen's small, medium, and large labels",
    "M18": "The coded data set (effect sizes, sample sizes, moderator codes), the coding manual, and the analysis code are available, or the paper says why not",
}
RULE_OWNERS = {"S1": "synthesis-model.md", "S2": "synthesis-model.md", "S3": "synthesis-claims.md",
               "S4": "evidence-base.md", "S5": "synthesis-model.md", "S6": "evidence-base.md",
               "S7": ("evidence-base.md", "synthesis-model.md"), "S8": "synthesis-claims.md"}
SCOPE_OPEN = "For the pooled effect sizes in this paper,"
SCOPE_CLOSE = "For any new estimate the paper computes from primary data of its own, work as usual."
SEVERITIES = ("Undermines the main claim", "Weakens a claim", "Minor")
INFERENCE_NOTE = ("Pooled effect sizes, moderator and subgroup tests, and publication-bias tests from the "
                  "meta-analysis belong to the meta-analysis pack (M8, M10, M14, M15, M17): skip them in every check. "
                  "Keep every estimate the paper computes from new primary data.")
NONLINEAR_NOTE = ("Study-level moderators in the meta-analysis (subgroups and meta-regression terms) and the effect "
                  "sizes it converts belong to the meta-analysis pack (M5, M15): skip them.")
PACK_NOTES = {
    "packs/inference/agents/inference-numbers.md": INFERENCE_NOTE,
    "packs/inference/agents/inference-dependence.md": INFERENCE_NOTE,
    "packs/inference/agents/inference-claims.md": INFERENCE_NOTE,
    "packs/nonlinear/agents/nonlinear-numbers.md": NONLINEAR_NOTE,
    "packs/nonlinear/agents/nonlinear-claims.md": NONLINEAR_NOTE,
    "packs/survey/agents/survey-numbers.md": ("Skip a correlation matrix pooled across primary studies; the "
                                              "meta-analysis pack checks it (M13)."),
    "packs/archival/agents/methods-checks.md": ("Pooled effect sizes and moderator tests from the meta-analysis belong "
                                                "to the meta-analysis pack: apply your checks only to estimates the "
                                                "paper computes from new primary data."),
}


def _pack():
    return packs.load_pack(PACK)


def _expected():
    return yaml.safe_load((PACK / "fixtures" / "planted-1" / "expected.yaml").read_text(encoding="utf-8"))


def test_pack_loads_as_a_type_pack():
    p = _pack()
    assert p.name == "meta-analysis" and p.overlay is False
    assert [i["id"] for i in p.checklist] == IDS
    assert p.read_checkin_lines == ["Synthesis:", "Meta-analytic counts:"]
    assert "theory" not in p.slots


def test_checklist_matches_the_spec():
    items = {i["id"]: i for i in _pack().checklist}
    for k in IDS:
        assert items[k]["text"] == CHECKLIST[k], k
        tag = "judgment" if k in JUDGMENT else ("external" if k in EXTERNAL else "paper")
        assert items[k]["adjudication"] == tag, k


def test_severity_rules_set_levels_only():
    rules = _pack().severity_rules
    assert [r.split(" ", 1)[0] for r in rules] == [f"S{i}" for i in range(1, 9)]
    assert "'Undermines the main claim'" in rules[0] and "every corner of the rounding box" in rules[0]
    assert "'robust' alone does not count" in rules[0] and "80% if unstated" in rules[0]
    assert "sqrt(effect sizes / independent samples)" in rules[1] and "`dependence_bound`" in rules[1]
    assert "at most 'Weakens a claim'" in rules[3] and "always 'Minor'" in rules[7]
    assert "(a line this pack sets, not a published threshold)" in rules[5]
    for r in rules:
        assert "one level" not in r and "downgrade" not in r


def test_turns_off_and_core_notes():
    p = _pack()
    assert [e["agent"] for e in p.turns_off] == ["timeline-research.md", "setting-research.md"]
    assert all(e["reason"] for e in p.turns_off)
    core = {"construction-ledger-producer.md", "face-validity.md", "completeness.md", "contribution-research.md",
            "boundary-conditions.md"}
    assert set(p.core_notes) == core | set(PACK_NOTES)
    for target in core:
        notes = p.core_notes[target]
        assert len(notes) == 1 and notes[0].startswith(SCOPE_OPEN) and notes[0].endswith(SCOPE_CLOSE), target
    ledger = p.core_notes["construction-ledger-producer.md"][0]
    assert "That is correct for this paper and is not a missing source." in ledger and "`time-invariant`" in ledger
    assert ("Do not set `no_entries_reason` because the paper collects no data: the pooled constructs and coded "
            "moderators are its entries.") in ledger
    assert "skip Step 5" in p.core_notes["face-validity.md"][0]


def _run(names, missing=(), primary="first"):
    return {"packs": list(names), "overlays": [], "types_without_pack": list(missing),
            "primary_pack": names[0] if primary == "first" else primary}


def test_meta_analysis_alone_turns_off_timeline_and_setting():
    built = packs.load_all(ROOT / "packs")
    adjust = packs.core_adjust(built, _run(["meta-analysis"]))
    assert set(adjust["off"]) == {"timeline-research.md", "setting-research.md"}
    assert adjust["off"]["timeline-research.md"]["reason"].startswith("Turned off by the meta-analysis pack: ")
    notes = adjust["notes"]
    assert notes["construction-ledger-checker.md"] == notes["construction-ledger-producer.md"]
    assert notes["face-validity.md"][0]["role"] == "primary type"
    assert adjust["read_lines"]["meta-analysis"] == ["Synthesis:", "Meta-analytic counts:"]


def test_a_second_type_keeps_timeline_and_setting_on():
    built = packs.load_all(ROOT / "packs")
    assert packs.core_adjust(built, _run(["meta-analysis", "archival"]))["off"] == {}
    run = _run(["meta-analysis"], missing=["experiments"], primary=None)
    adjust = packs.core_adjust(built, run)
    assert adjust["off"] == {} and adjust["notes"]["face-validity.md"][0]["role"] == "second type"


def test_notes_to_other_packs():
    notes = _pack().core_notes
    for target, text in PACK_NOTES.items():
        assert notes[target] == [text], target


def test_archival_primary_gets_the_methods_checks_note():
    built = packs.load_all(ROOT / "packs")
    adjust = packs.core_adjust(built, _run(["archival", "meta-analysis"]))
    got = [n for n in adjust["notes"]["packs/archival/agents/methods-checks.md"] if n["pack"] == "meta-analysis"]
    assert [n["text"] for n in got] == [PACK_NOTES["packs/archival/agents/methods-checks.md"]]
    assert got[0]["role"] == "second type"
    alone = packs.core_adjust(built, _run(["meta-analysis"]))["notes"]
    assert not any(k.startswith("packs/") for k in alone)


def test_fixture_is_labeled_synthetic():
    exp = _expected()
    assert exp["synthetic"] is True and exp["owner"] == "blind-agent"
    assert exp["label"] == "SYNTHETIC TEST PAPER, NOT REAL RESEARCH"
    assert exp["status"] in ("pending_planting", "ready")
    for key in ("must_catch", "must_not_flag", "also_fair"):
        for item in exp.get(key) or []:
            assert {"check", "page", "locator", "note"} <= set(item), item
            assert item["check"] in IDS, item
    for item in exp.get("must_catch") or []:
        assert item.get("severity") in SEVERITIES, item
    plants = {(i["check"], str(i["page"]), i["locator"]) for i in exp.get("must_catch") or []}
    for d in exp.get("must_not_flag") or []:
        assert (d["check"], str(d["page"]), d["locator"]) not in plants, d


# --- Task 4: synthesis-numbers agent (verify slot) ---

def _agent(name):
    return (PACK / "agents" / name).read_text(encoding="utf-8")


LESSON_LINES = ("The contracts in `skills/review/shared/contracts.md`",
                "The works named in this file are background for you. Cite one in your output only if you "
                "fetched it in this run; otherwise state the concern without the citation.")


def test_numbers_agent():
    assert _pack().slots.get("verify") == ["synthesis-numbers.md"]
    text = _agent("synthesis-numbers.md")
    for s in LESSON_LINES + ("stage-1/meta-analysis_numbers.md", "## Checks run", "## Flags", "## Not computed",
                             "Quick", "Record: <id>. Table: <label>. Cells: <table:row:col, ...>.",
                             "Flag nothing as missing"):
        assert s in text, s
    for kind in ("flow", "convert", "dependence_bound", "i2", "prediction_interval", "credibility_interval",
                 "attenuation", "study_table", "cell_n"):
        assert f"`{kind}`" in text, kind
    assert "is never a flag here" in text


def test_numbers_agent_runs_the_script_with_its_own_tools():
    text = _agent("synthesis-numbers.md")
    assert "tools: [Read, Write, Bash, Glob]" in text.split("---", 2)[1]
    assert "The orchestrator will provide `PDF_PATH`, `PAGE_COUNT`, `{WORKSPACE}`, and `{PLUGIN}`." in text
    assert ("`python3 {PLUGIN}/packs/meta-analysis/scripts/ma_arith.py "
            "{WORKSPACE}/stage-1/ma_arith_input.json {WORKSPACE}/stage-1/ma_arith.md`") in text
    assert "with the file-writing tool" in text
    assert not re.search(r"(cat|echo|printf|tee)[^\n`]*>", text)
    assert (PACK / "scripts" / "ma_arith.py").exists()


def test_numbers_agent_passes_independent_samples_and_q_based():
    text = _agent("synthesis-numbers.md")
    assert "Pass the number of independent samples as `k` when the paper reports it" in text
    assert "pass the printed tau-squared components as a list in `tau2`" in text
    assert "`q_based` true" in text
    assert "write two records, one per scale" in text
    assert "`ci_method` `t_k1`" in text


def test_numbers_agent_follows_the_scripts_readings():
    text = _agent("synthesis-numbers.md")
    for s in ("A comma is read only as a thousands separator: when the paper prints a decimal comma, write a "
              "decimal point with the same digits",
              "it accepts other sources joining before screening (PRISMA 2009) or at the included count (PRISMA 2020)",
              "The script accepts a printed interval computed with t on k - 2, t on k - 1, or z",
              "Give `printed_k` and `printed_total_n` only when the paper prints an exact figure for the same rows; "
              "a total given as 'about' or 'over' is not one.",
              "\"every computable corner\""):
        assert s in text, s


def test_hyphenated_pack_item_ids_record_and_replay(tmp_path):
    from plumb import checkin
    item = "numbers:pack:meta-analysis:1"
    checkin.record(tmp_path, "numbers", item, "A. Real problem in the paper (Recommended)", "B. Extraction error")
    assert ("numbers", item) in checkin.answered(tmp_path)
    assert checkin.answers(tmp_path)[item] == "B. Extraction error"


def test_synthesis_numbers_routes_not_computable():
    text = (ROOT / "packs" / "meta-analysis" / "agents" / "synthesis-numbers.md").read_text(encoding="utf-8")
    assert "A result with status `not_computable`, or an `input_error` you could not fix, goes under `## Not computed`" in text


# --- Task 5: primary-studies agent (context slot) ---

def test_primary_studies_agent():
    assert _pack().slots.get("context") == ["primary-studies.md"]
    text = _agent("primary-studies.md")
    for s in LESSON_LINES + ("The orchestrator will provide `PDF_PATH`, `PAGE_COUNT`, and `{WORKSPACE}`.",
                             "stage-2/primary_studies.md", "## Studies checked", "## Shared samples",
                             "## Data link", "## Could not establish",
                             "about 15 searches at Standard depth, 25-35 at Deep. Read `depth` from `run.json`.",
                             "When `run.json` has `search_before`, cap searches at that date",
                             "you set no severity and write no issues"):
        assert s in text, s
    assert "If the file is missing" in text


def test_primary_studies_checks_effect_size_only_with_open_full_text():
    text = _agent("primary-studies.md")
    assert "only when you have the open full text" in text
    assert "Do not add more as k grows" in text
    assert "a composite of several measures, a reverse-scored measure, a corrected value, or a subsample" in text


def test_primary_studies_respects_referee_mode():
    text = _agent("primary-studies.md")
    assert "If `role` is `referee` and the link is not labeled anonymized, do not follow it." in text
    assert "WEB-fetch that journal's author guidelines page" in text
    assert "Never take author rules from a journal profile" in text


def test_primary_studies_labels_its_count():
    text = (ROOT / "packs" / "meta-analysis" / "agents" / "primary-studies.md").read_text(encoding="utf-8")
    assert "These counts are a pragmatic bound set by this pack, not a published threshold" in text
    assert "say how many included studies were not checked" in text
    assert "If the link does not open, say so under `## Could not establish`." in text
    assert "separate samples with the dependence modelled" in text


def test_numbers_agent_fix_round_1():
    text = _agent("synthesis-numbers.md")
    for s in ("I-squared based on tau-squared; not recomputed", "`printed_i2_form`", "`alt_group`",
              "`pi_level`", "removed before screening other than duplicates", "marked ineligible by automation tools",
              "every included study", "range restriction", "never a hand sum", "every value is a string, `page` included",
              "only when the paper says its I-squared is computed from Q"):
        assert s in text, s
    assert "Set `q_based` to true only when Q and df are printed on the same row" not in text
    assert "pass the total tau-squared across levels as `tau2`" not in text


# --- Task 6: evidence-base agent (diagnose slot) ---

DROPPED = ("(`<n>` is the flag's position under `## Flags` in `meta-analysis_numbers.md`; map it to that flag's "
           "`Record:` line)")


def _rules_for(agent):
    out = []
    for rule in _pack().severity_rules:
        owners = RULE_OWNERS[rule.split(" ", 1)[0]]
        if agent in (owners if isinstance(owners, tuple) else (owners,)):
            out.append(rule)
    return out


def test_evidence_base_agent():
    assert "evidence-base.md" in _pack().slots.get("diagnose", [])
    text = _agent("evidence-base.md")
    assert "stage-4/evidence_base.md" in text
    for c in ("M1", "M2", "M3", "M4", "M6", "M7", "M14", "M18"):
        assert re.search(rf"^### {c}\. ", text, re.M), c
    rules = _rules_for("evidence-base.md")
    assert [r.split(" ", 1)[0] for r in rules] == ["S4", "S6", "S7"]
    for rule in rules:
        assert rule in text, rule[:40]
    assert "An end date (\"through December 2022\") meets the purpose" in text
    assert "One overall agreement figure, or agreement on effect size and N, is enough" in text
    assert ("A count that does not add up changes the included k only when the included count itself fails its "
            "step.") in text
    assert DROPPED in text


def test_m6_needs_same_statistic_and_no_documented_reason():
    text = _agent("evidence-base.md")
    assert ("Flag a difference only when the primary study reports the same statistic for the same construct pair "
            "and the same sample, and the meta-analysis documents no composite, reverse scoring, correction, or "
            "subsample that explains it.") in text
    assert "A study the lookups could not reach is not a finding." in text
    assert "report the lead, tag it external, and say what would settle it" in text


def test_evidence_base_reads_share_and_accepts_modelled_dependence():
    text = (ROOT / "packs" / "meta-analysis" / "agents" / "evidence-base.md").read_text(encoding="utf-8")
    assert "as `primary_studies.md` gives it under `## Studies checked`" in text
    assert "When no share is given, rate the finding 'Minor'" in text
    assert "an unchecked study is not a finding" in text
    assert "separate samples with the dependence modelled" in text


# --- Task 7: synthesis-model agent (diagnose slot) ---

MAIN_CONTRIBUTION = ("The stated main contribution is the one the abstract or introduction calls main, or the "
                     "first one it states when it calls none main.")


def test_model_agent():
    assert "synthesis-model.md" in _pack().slots.get("diagnose", [])
    text = _agent("synthesis-model.md")
    assert "stage-4/synthesis_model.md" in text
    for c in ("M5", "M8", "M9", "M10", "M11", "M12", "M13"):
        assert re.search(rf"^### {c}\. ", text, re.M), c
    rules = _rules_for("synthesis-model.md")
    assert [r.split(" ", 1)[0] for r in rules] == ["S1", "S2", "S5", "S7"]
    for rule in rules:
        assert rule in text, rule[:40]
    assert "never ask for a particular one" in text


def test_model_agent_reads_the_papers_own_interval():
    text = _agent("synthesis-model.md")
    assert ("the 95% prediction interval for a Hedges-Olkin or random-effects model, and the credibility interval "
            "at the paper's level for Hunter-Schmidt, taking the z-based one") in text
    assert '"Robust" alone is not such a claim' in text
    assert "An interval that includes zero at only some corners does not meet S1" in text
    assert ("An interval that includes zero at every computable corner, with corners left out, does not meet S1 or "
            "S2 either.") in text
    assert ("When the paper prints a 95 percent prediction interval and Stage 1 finds that it matches, apply S1 to "
            "the printed interval.") in text
    assert MAIN_CONTRIBUTION in text and DROPPED in text


# --- Final fix wave A ---

def test_non_95_interval_gets_a_95_percent_record_for_s1():
    numbers = _agent("synthesis-numbers.md")
    assert ("When you give `pi_level`, also write a second `prediction_interval` record for the same estimate with "
            "the same inputs and no `pi_level` and no `printed_pi`") in numbers
    assert "say that the two records share one estimate" in numbers
    assert "or the added 95 percent record) takes no `alt_group`" in numbers
    model = _agent("synthesis-model.md")
    assert "read S1 from the 95 percent record" in model
    assert ("Stage 1 also computed the 95 percent interval for the same estimate in a record with no `pi_level`; "
            "apply S1 to that one") in model


def test_unapplied_s1_caps_generality_finding():
    assert ("When S1 is left unapplied, a finding about a claim of generality is at most 'Weakens a claim'."
            in _agent("synthesis-model.md"))


def test_hunter_schmidt_method_states_model_and_estimator():
    text = _agent("synthesis-model.md")
    assert ("In the Hunter-Schmidt (psychometric) tradition, naming the method states both the model (random "
            "effects) and the between-study variance estimator: that is not a reporting gap") in text


def test_shared_database_is_not_a_shared_sample():
    for name in ("evidence-base.md", "primary-studies.md"):
        text = _agent(name)
        assert ("A shared database (Compustat, CRSP, SDC, a national survey) over overlapping years is not by "
                "itself a shared sample") in text, name
        assert "the same firms or people over the same period" in text, name


def test_evidence_base_carries_main_contribution_and_m18_scope():
    text = _agent("evidence-base.md")
    assert MAIN_CONTRIBUTION in text
    assert ("Unshared data leave a main estimate impossible to check (S7) only when the paper also prints no "
            "included-study table with each study's N and effect size.") in text


def test_primary_studies_names_the_share_denominator():
    text = _agent("primary-studies.md")
    assert ("its N divided by the total N the paper prints for the pooled analysis of that relationship, or, if "
            "the paper prints none, by the sum of the table rows the `study_table` record used. Name the "
            "denominator you used.") in text
    assert "(<share of total N>, of <total N>: <printed total | row sum>)" in text


def test_model_agent_uses_the_dependence_bound():
    text = _agent("synthesis-model.md")
    assert "take the Stage 1 `dependence_bound` result for the estimate the main claim rests on and apply S2" in text
    assert "say it is an approximate worst case for equal-sized samples" in text
    assert "Do not say what a corrected analysis would show." in text


# --- Task 8: synthesis-claims agent (diagnose slot) and coverage ---

DIAGNOSE = ("evidence-base.md", "synthesis-model.md", "synthesis-claims.md")


def test_claims_agent():
    assert _pack().slots.get("diagnose") == list(DIAGNOSE)
    text = _agent("synthesis-claims.md")
    assert "stage-4/synthesis_claims.md" in text and "stage-3/argument_map.md" in text
    for c in ("M15", "M16", "M17"):
        assert re.search(rf"^### {c}\. ", text, re.M), c
    rules = _rules_for("synthesis-claims.md")
    assert [r.split(" ", 1)[0] for r in rules] == ["S3", "S8"]
    for rule in rules:
        assert rule in text, rule[:40]
    assert "Do not offer Bosco's cut points as benchmarks for strategy" in text
    assert MAIN_CONTRIBUTION in text


def test_claims_agent_ignores_terms_of_art():
    text = _agent("synthesis-claims.md")
    assert '"effect size", "moderating effect", "main effect", and "true score effect"' in text
    assert "so never flag them" in text
    assert "Moderator and boundary-condition claims belong to M15; do not raise them here." in text


def test_every_check_is_owned_once():
    checklist = yaml.safe_load((PACK / "checklists" / "meta-analysis.yaml").read_text(encoding="utf-8"))
    ids = [item["id"] for item in checklist]
    assert ids == IDS
    owned = []
    for path in sorted((PACK / "agents").glob("*.md")):
        text = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8"), flags=re.S)
        heads = re.findall(r"^### (M\d+)\. ", text, re.M)
        if path.name not in DIAGNOSE:
            assert heads == [], path.name
        owned += heads
    assert sorted(owned, key=lambda x: int(x[1:])) == ids


def test_claims_agent_exempts_qualified_claims_and_field_benchmarks():
    text = _agent("synthesis-claims.md")
    assert "A causal verb the paper itself qualifies as an association, or a claim kept to the pooled correlation, is not a finding." in text
    assert "a Cohen label beside them is not a finding" in text


@pytest.mark.parametrize("name", DIAGNOSE)
def test_diagnose_agents_share_the_contract(name):
    text = _agent(name)
    front = text.split("---", 2)[1]
    for key in ("name:", "description:", "maxTurns:"):
        assert key in front, key
    for s in LESSON_LINES + (
            "The orchestrator will provide `PDF_PATH`, `PAGE_COUNT`, and `{WORKSPACE}`.",
            "If the file is missing", "Its first line is `Pack: meta-analysis`.", "Pack: meta-analysis\n",
            "Check: <M-id>. Unit: <estimate | moderator | table | section>. Tag: [paper | external | judgment]",
            "Paper's best case:", "Excerpt:", "Page:", "What would settle it:", "## Checked and fine",
            "Severity: <Undermines the main claim | Weakens a claim | Minor>",
            "Flag an absence only after searching the methods section, the appendices, the footnotes, and every "
            "table, and name where you looked.",
            "Never predict the result of an analysis you suggest.",
            "Definitions, for when you find them yourself:", "systematic review without pooling"):
        assert s in text, s
    assert "—" not in text
    assert not re.search(r"(cat|echo|printf|tee)[^\n`]*>", text)


# --- Task 10: README and repo spec ---

def test_readme_and_spec_name_the_meta_analysis_pack():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    section = readme.split("## Packs", 1)[1].split("\n## ", 1)[0]
    assert "- **Meta-analysis** is a paper type." in section
    assert section.index("- **Simulation** runs when") < section.index("- **Meta-analysis** is a paper type.")
    assert len(re.findall(r"A pack adds checks for one kind of paper\. \w+ are built\.", readme)) == 1
    spec = (ROOT / "docs" / "spec.md").read_text(encoding="utf-8")
    assert "The meta-analysis pack is a type pack for meta-analyses and systematic reviews." in spec
