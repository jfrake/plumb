from __future__ import annotations
import re
from pathlib import Path

import pytest
import yaml

from plumb import packs

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "review"
PACK = ROOT / "packs" / "survey"
IDS = [f"S{i}" for i in range(1, 19)]
AGENTS = ("survey-numbers.md", "scale-provenance.md", "respondents-and-sources.md", "psychometrics.md",
          "claims-and-controls.md")
DIAGNOSE = ("respondents-and-sources.md", "psychometrics.md", "claims-and-controls.md")


def _audit():
    return (SKILL / "agents" / "manuscript-audit.md").read_text(encoding="utf-8")


def _agent(name):
    return (PACK / "agents" / name).read_text(encoding="utf-8")


# --- Task 1: the survey typing sentence and the fingerprint fields ---

def test_fingerprint_has_the_survey_fields():
    text = _audit()
    template = text.split("# Fingerprint", 1)[1].split("```", 1)[0]
    assert ("Survey data: <yes | no | some variables>; <who was asked, how they were reached, "
            "the stated response count>") in template
    assert ("Focal measures:\n- <variable>: role: <predictor | outcome | mediator | moderator>; source: "
            "<self-report | other rater: who | key informant: who | archival>; wave: <number | single>") in template
    assert template.index("Designs:") < template.index("Survey data:")
    for s in ("Under `Survey data:`", "Under `Focal measures:`", "Do not list controls.",
              "write \"Survey data: no\" and \"Focal measures: none\""):
        assert s in text, s


def test_survey_typing_sentence():
    text = _audit()
    assert "There is no correlational type" in text
    assert ("A paper is `survey` when its focal variables come from questionnaires (of employees, managers, "
            "founders, a firm's informant, or an online panel) and it names no design for identification") in text
    assert "when its focal variables also come from questionnaires, record `survey` as its second type." in text
    assert ("A paper that names no such design and whose focal variables come partly from questionnaires and partly "
            "from records is `survey`; record `archival` as its second type when the main outcome comes from records.") in text
    assert ("When the paper states no numbered hypotheses, list the predictor and outcome of the main result and of "
            "each result the abstract states.") in text



# --- Task 3: the pack frame ---

CHECKLIST = yaml.safe_load(r'''
S1: "For each hypothesized main or mediated relation whose predictor and outcome come from the same respondent, the paper names the method-bias risk and what the design does about it (a separate source, a time lag, a different response format, anonymity); a statistical test is not offered in place of a design remedy"
S2: "A single-factor test (a first unrotated factor explaining under half the variance, or a one-factor model fitting worse than the measurement model) is not offered as evidence that common method bias is absent"
S3: "A marker variable or latent method factor comes with its rationale (the marker is theoretically unrelated to the substantive constructs and shares their method), its results are reported, and the technique is not presented as proof that bias is absent"
S4: "The design the paper names (longitudinal, time-lagged, multi-wave, multi-source) matches the wave and source of each focal variable as the methods section reports them"
S5: "Every focal multi-item measure reports its source, its items or where to find them, its response scale, and any change from the original; ad hoc scales and single-item measures of latent constructs come with a validity argument"
S6: "The measures match their cited sources in item count, dimensions, and response format, or the paper discloses and justifies each change"
S7: "Reliability is reported for every multi-item reflective scale; a composite is not scored as one scale when the paper's own factor analysis shows more than one factor, and reliability is not offered as evidence of unidimensionality or validity"
S8: "Measurement-model fit is reported with more than one index, and the paper's reading of fit matches its own numbers and the cutoffs it cites; a comparison of means or paths across groups reports a test of measurement invariance"
S9: "Highly correlated focal constructs are shown to be distinct with a test that can detect their overlap (a disattenuated correlation with its interval, or a nested-model comparison); a variance inflation factor or the Fornell-Larcker rule alone does not settle it, and a disattenuated correlation at or above 1 is addressed"
S10: "The sampling frame, contacts, responses, usable responses, and response rate are reported and add up; nonresponse is assessed against what is known about nonrespondents or the population where the frame allows; a response rate, or a benchmark rate, is not offered as evidence of no bias; for multi-wave designs, the count at each wave is reported and those lost between waves are compared with those retained on earlier measures"
S11: "For crowdsourced or opt-in panel samples, the paper reports the platform, collection dates, how eligibility for the claimed population was verified, quality screens, exclusions by reason, and, for data collected in 2023 or later, what guards against automated or LLM-generated responses"
S12: "Firm- or unit-level constructs reported by one informant come with the informant's position and basis of knowledge, and a second source for the outcome or a stated reason why none exists"
S13: "Constructs aggregated from individual responses report within-group agreement and reliability with a reason for aggregating, and the analysis models or clusters the nesting"
S14: "Causal wording (effect, increases, drives, leads to) and prescriptive implications match what the design can show; a limitations sentence on cross-sectional data does not stand in for an argument about direction and confounding when the hypotheses and implications are causal"
S15: "When the paper offers a remedy for endogeneity (lags, added controls, a selection model, an instrument, a lagged dependent variable), the remedy fits the threat it names: controls or lags are not called a solution to endogeneity; a selection model names its exclusion variable; an instrument comes with an exclusion argument and first-stage strength"
S16: "Each control has a stated reason, is measured before or with the predictor (by wave, where waves exist), and is not plausibly a result of the predictor; results are shown with and without controls; control coefficients are not interpreted as findings"
S17: "A mediation claim tests the indirect effect itself, says the mediator was not assigned and what must hold for a causal reading, is not called full mediation because the direct effect lost significance, and treats measurement of the mediator in the same wave as the predictor or the outcome as a limit on the claim"
S18: "The printed correlation matrix is one that complete data could produce within rounding, or the paper says the correlations use pairwise deletion"
''')
TAGS = {"S3": "judgment", "S12": "judgment", "S6": "external"}
SEVERITIES = ("Undermines the main claim", "Weakens a claim", "Minor")
PRIMARY_GATE = "Apply this note only when the label says primary type."


def test_survey_pack_loads_as_a_type_pack():
    p = packs.load_pack(PACK)
    assert p.name == "survey" and p.overlay is False and p.turns_off == []
    assert [i["id"] for i in p.checklist] == IDS
    assert p.read_checkin_lines == ["Survey data:", "Focal measures:"]
    assert not any("correlational" in c.lower() for c in p.detection_cues)


def test_checklist_matches_the_spec():
    items = {i["id"]: i for i in packs.load_pack(PACK).checklist}
    for k in IDS:
        assert items[k]["text"] == CHECKLIST[k], k
        assert items[k]["adjudication"] == TAGS.get(k, "paper"), k


def test_severity_rules():
    rules = packs.load_pack(PACK).severity_rules
    assert len(rules) == 9
    starts = ("S14:", "S1 to S3:", "S9:", "S17:", "S14 and S15 findings drop one level", "S16:", "S18:", "S6:",
              "S4, S5, S7, S8, S10 to S13, and S15:")
    for rule, start in zip(rules, starts):
        assert rule.startswith(start), rule
    assert "The Stage 4 compiler applies this rule; pack agents do not." in rules[4]
    assert "no other study in the paper supplies that evidence" in rules[0]
    assert "and the paper reports no nested-model comparison" in rules[2]
    assert rules[1].endswith("The S1 finding is also 'Minor' when the paper states why a separate source or lag was not "
                             "feasible and reports a statistical remedy that meets S3.")
    assert rules[3] == ("S17: 'Undermines the main claim' when the mechanism is a stated contribution, the predictor, "
                        "mediator, and outcome are all measured in one wave, and no other study in the paper separates "
                        "them in time or manipulates the mediator. When the mediator shares a wave with only the "
                        "predictor or only the outcome, 'Weakens a claim'. Otherwise 'Weakens a claim'.")
    assert rules[8] == ("S4, S5, S7, S8, S10 to S13, and S15: at most 'Weakens a claim'. A finding that only notes "
                        "missing reporting is 'Minor' unless it concerns the main relation's sample or measures, and is "
                        "written once per check. When the paper fits no measurement model, a request for a confirmatory "
                        "model is 'Minor'.")


def test_core_notes_gate_on_primary_type():
    notes = packs.load_pack(PACK).core_notes
    claims = "packs/inference/agents/inference-claims.md"
    assert set(notes) == {"completeness.md", "face-validity.md", claims}
    assert len(notes["completeness.md"]) == 1 and len(notes["face-validity.md"]) == 2
    for key in ("completeness.md", "face-validity.md"):
        for t in notes[key]:
            assert t.startswith(PRIMARY_GATE), t
    assert "(Step 7, item 5)" in notes["face-validity.md"][0]
    assert "Skip the balance-table item." in notes["completeness.md"][0]
    assert len(notes[claims]) == 1 and "(check S17)" in notes[claims][0]
    assert notes[claims][0].startswith("Apply this note only when `archival` is not in `run.json` `packs`.")


def test_fixtures_are_labeled_synthetic():
    for name in ("planted-1", "planted-2"):
        exp = yaml.safe_load((PACK / "fixtures" / name / "expected.yaml").read_text(encoding="utf-8"))
        assert exp["synthetic"] is True and exp["owner"] == "blind-agent", name
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


def test_validate_packs_lists_survey_as_a_type_pack():
    built = packs.load_all(ROOT / "packs")
    assert "survey" in built and built["survey"].overlay is False
    assert packs.run_packs(built, ["survey", "survey"], [])["packs"] == ["survey"]


# --- Task 4: the survey-numbers agent (verify) ---

def test_numbers_agent():
    assert packs.load_pack(PACK).slots.get("verify") == ["survey-numbers.md"]
    text = _agent("survey-numbers.md")
    for s in ("stage-1/survey_numbers.md", "## Matrices checked", "## Flags", "## Not found", "## Not computed",
              "Quick included", "Check: <S-id>. [paper] Table: <label>. Cells: <table:row:col, ...>."):
        assert s in text, s
    for step in ("### Step 1.", "### Step 2.", "### Step 3.", "### Step 4.", "### Step 5."):
        assert step in text, step
    for c in ("(S18)", "(S9)", "(S10)", "(S8)", "(S7)"):
        assert c in text, c
    assert "When `range_violations` is not empty and `psd` is null, the script did not run this check; skip this item." in text


def test_numbers_agent_runs_the_script_with_its_own_tools():
    text = _agent("survey-numbers.md")
    assert "tools: [Read, Write, Bash, Glob]" in text.split("---", 2)[1]
    assert "The orchestrator will provide `PDF_PATH`, `PAGE_COUNT`, `{WORKSPACE}`, and `{PLUGIN}`." in text
    assert ("`python3 {PLUGIN}/packs/survey/scripts/check_correlation_matrix.py {WORKSPACE}/extracted_tables "
            "{WORKSPACE}/stage-1/survey_matrix.json --out-md {WORKSPACE}/stage-1/survey_matrix.md`") in text
    assert "If it exits 2, write \"Correlation matrix not checked: <its message>\" under `## Not computed`" in text
    assert "with the file-writing tool" in text
    assert not re.search(r"(cat|echo|printf|tee)[^\n`]*>", text)
    assert (PACK / "scripts" / "check_correlation_matrix.py").exists()
    assert 'except a table whose reason begins "unreadable table", which goes under `## Not computed`' in text


def test_numbers_agent_reads_the_note_before_using_the_diagonal():
    text = _agent("survey-numbers.md")
    assert "read the table's note first and write down what the diagonal holds" in text
    assert "Use `pairs` only when the note says the diagonal (or the `diagonal_source` column) holds reliabilities." in text
    assert "Use `diag_below_offdiag` only when the note says the diagonal holds the square root of AVE" in text
    assert "not a cutoff from the literature; never call it one" in text
    assert "not that they are the same construct" in text


def test_numbers_agent_rereads_driving_cells_before_flagging():
    text = _agent("survey-numbers.md")
    assert "reread every cell in the rows and columns of the variables under `psd.driving_variables`" in text
    assert "the fault is the transcription: do not flag the matrix" in text


def test_numbers_agent_lists_blanked_cells_for_redispatch():
    text = _agent("survey-numbers.md")
    assert "List each blank cell under `## Not computed` as \"Cells: <table>:<row>:<col>\"" in text
    assert "`{WORKSPACE}/stage-1/unverified_numbers.md`" in text
    assert "The variable numbers in `survey_matrix.json` are positions in the matrix, not in the CSV" in text


# --- Task 5: the scale-provenance agent (context) ---

def test_provenance_agent():
    assert packs.load_pack(PACK).slots.get("context") == ["scale-provenance.md"]
    text = _agent("scale-provenance.md")
    for s in ("stage-2/scale_provenance.md", "## Measures checked", "## Not checked", "## Protocol (check S6)",
              "Search budget: about 10 searches at Standard depth, 20-30 at Deep. Read `depth` from `run.json`.",
              "except the cited scale sources themselves",
              "Check the main predictor, the main outcome, and each hypothesized mediator",
              "skills/review/shared/research-protocol.md"):
        assert s in text, s


def test_provenance_agent_never_guesses():
    text = _agent("scale-provenance.md")
    assert "Never guess a scale's contents." in text
    assert "each with the URL and a verbatim quote that supports it" in text
    assert "If the file is missing, use the Standard budget and no date cap." in text



# --- Task 6: the respondents-and-sources agent (diagnose) ---

TEMPLATE_LINES = ("Excerpt:", "Page:", "Paper's best case:", "What would settle it:", "## Checked and fine",
                  "Severity: <Undermines the main claim | Weakens a claim | Minor>")


def _headings(text):
    return re.findall(r"^### (S\d+)\. ", text, re.M)


def test_respondents_agent():
    p = packs.load_pack(PACK)
    assert p.slots.get("diagnose", [])[:1] == ["respondents-and-sources.md"]
    text = _agent("respondents-and-sources.md")
    assert _headings(text) == ["S1", "S2", "S3", "S4", "S10", "S11", "S12"]
    assert "stage-4/respondents_and_sources.md" in text
    for s in TEMPLATE_LINES:
        assert s in text, s
    assert p.severity_rules[1] in text and p.severity_rules[8] in text
    assert "`Designs:` (read as corrected in `brief.md`)" in text
    assert "number flags the user marked as not a problem or misread" in text
    assert "(`<n>` is the flag's position under `## Flags` in `survey_numbers.md`)" in text


def test_respondents_agent_scopes_s1():
    text = _agent("respondents-and-sources.md")
    assert "Skip moderation hypotheses" in text and "deflate interactions rather than create them" in text
    assert "private states only the respondent can report" in text
    assert "Never flag the choice of label" in text


def test_respondents_agent_dates_the_llm_clause_and_scopes_s10():
    text = _agent("respondents-and-sources.md")
    assert "For data collected in 2023 or later, also ask what guards against automated or LLM-generated responses; do not ask it of earlier data." in text
    assert "an opt-in panel goes to S11 only" in text
    assert "When `experiments` is in `run.json` `packs`, apply this check only to studies that assign nothing" in text


def test_respondents_agent_leaves_ties_to_the_network_pack():
    text = _agent("respondents-and-sources.md")
    assert "When `network` is in `run.json` `overlays`" in text and "missing ties and actors belong to that pack" in text


# --- Task 7: the psychometrics agent (diagnose) ---

def test_psychometrics_agent():
    p = packs.load_pack(PACK)
    assert p.slots.get("diagnose", [])[:2] == ["respondents-and-sources.md", "psychometrics.md"]
    text = _agent("psychometrics.md")
    assert _headings(text) == ["S5", "S6", "S7", "S8", "S9", "S13", "S18"]
    assert "stage-4/psychometrics.md" in text
    for s in TEMPLATE_LINES:
        assert s in text, s
    for i in (2, 6, 7, 8):
        assert p.severity_rules[i] in text, i
    assert "number flags the user marked as not a problem or misread" in text
    assert "(match the dropped flag's `Table:`, check, and `Cells:` to the records there)" in text
    assert "(such as rwg), the share of variance between groups (ICC(1))" in text
    assert ("When the paper compares latent or scale means, or paths, across groups (a multigroup model; countries, "
            "genders, cohorts), ask whether it reports a test of measurement invariance at the level the comparison "
            "needs (configural, metric, scalar) (Vandenberg and Lance 2000; Putnick and Bornstein 2016); state no "
            "cutoff for the change in fit.") in text
    assert "(`<n>` is the flag's position under `## Flags` in `survey_numbers.md`)" in text
    assert "When `inference` is in `run.json` `overlays`, leave the nesting half to that pack" in text
    assert "When it is not, and `archival` is in `run.json` `packs`, leave the nesting half" in text


def test_psychometrics_agent_treats_the_screen_as_a_filter():
    text = _agent("psychometrics.md")
    assert "A pair listed as screened in Stage 1 becomes an issue only in three cases" in text
    assert "The .85 screen is Plumb's reading filter, not a cutoff from the literature; never present it as one." in text
    assert "State no numeric threshold." in text


def test_psychometrics_agent_skips_s6_without_provenance_and_formative_indices():
    text = _agent("psychometrics.md")
    assert "It is not written at Quick depth. If it is missing, skip S6 and say so under \"Checked and fine\"." in text
    assert "do not ask it of formative indices or counts" in text
    assert "When `computational` is in `run.json` `overlays`, skip every variable listed under `Generated variables:`" in text



# --- Task 8: the claims-and-controls agent (diagnose), coverage, and the shared rules ---

def test_claims_agent():
    p = packs.load_pack(PACK)
    assert p.slots.get("diagnose") == list(DIAGNOSE)
    text = _agent("claims-and-controls.md")
    assert _headings(text) == ["S14", "S15", "S16", "S17"]
    assert "stage-4/claims_and_controls.md" in text
    for s in TEMPLATE_LINES:
        assert s in text, s
    for i in (0, 3, 5, 8):
        assert p.severity_rules[i] in text, i
    assert p.severity_rules[4] not in text
    assert "the Stage 4 compiler applies it; do not apply it yourself" in text
    assert "Do not demand a natural experiment" in text


def test_claims_agent_limits_itself_behind_a_design_pack():
    text = _agent("claims-and-controls.md")
    assert ("When `archival` or `experiments` is in `run.json` `packs` ahead of `survey`, or `experiments` is in "
            "`run.json` `types_without_pack`, apply S14 to S17 only to "
            "studies or relations whose predictor was measured, not assigned or identified by a design.") in text
    assert ("When `experiments` is in `run.json` `packs`, or `experiments` is in `run.json` `types_without_pack`, "
            "apply S17 only to mediations whose predictor was measured") in text
    assert "raise under S15 only added controls or a lagged dependent variable called a solution to endogeneity" in text
    assert "Do not ask a paper that offers no remedy to list every source of endogeneity" in text


def test_every_checklist_id_is_owned_by_one_diagnose_agent():
    owners = {}
    for name in DIAGNOSE:
        for cid in _headings(_agent(name)):
            owners.setdefault(cid, []).append(name)
    assert sorted(owners, key=lambda c: int(c[1:])) == IDS
    assert all(len(v) == 1 for v in owners.values()), owners


def test_every_survey_agent_handles_a_missing_or_negative_survey_field():
    for name in AGENTS:
        text = _agent(name)
        assert "If `Survey data:` says \"no\", write the output file with \"Not applicable: no questionnaire data.\"" in text, name
        assert "If either field is missing" in text or "If a field is missing" in text, name
        assert "User corrections" in text, name


def test_diagnose_files_start_with_the_pack_line():
    for name in DIAGNOSE:
        text = _agent(name)
        assert "Its first line is `Pack: survey`." in text and "```markdown\nPack: survey\n" in text, name


def test_survey_agents_follow_the_authoring_lessons():
    for name in AGENTS:
        text = _agent(name)
        front = text.split("---", 2)[1]
        for key in ("name:", "description:", "maxTurns:"):
            assert key in front, (name, key)
        assert "The works named in this file are background for you." in text, name
        assert "The orchestrator will provide `PDF_PATH`, `PAGE_COUNT`" in text, name
        assert "skills/review/shared/contracts.md" in text, name
        assert not re.search(r"(cat|echo|printf|tee)[^\n`]*>", text), name
        assert chr(0x2014) not in text, name
    for name in DIAGNOSE:
        text = _agent(name)
        assert "Flag an absence only after searching the methods section, the appendices, the footnotes, and every table, and name where you looked." in text, name
        assert "Never predict the result of an analysis you suggest." in text, name


# --- Task 11: README and repo spec ---

def test_readme_and_spec_name_the_survey_pack():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "- **Survey** is a type pack." in readme
    assert readme.index("- **Inference** is an overlay.") < readme.index("- **Survey** is a type pack.")
    assert len(re.findall(r"A pack adds checks for one kind of paper\. \w+ are built\.", readme)) == 1
    spec = (ROOT / "docs" / "spec.md").read_text(encoding="utf-8")
    assert "The survey pack is the type pack for questionnaire studies." in spec
    for sentence in re.findall(r"Those types are [^.]*\.", spec):
        assert "survey" not in sentence, sentence


def test_inference_i1_keeps_so_does_after_the_pass_sentence():
    text = (ROOT / "packs" / "inference" / "agents" / "inference-dependence.md").read_text(encoding="utf-8")
    assert ("Clustering at or above the treatment level passes. So does an unclustered cross-section with "
            "individually assigned treatment. A multilevel model with random effects at or above the level") in text
    assert "with few groups, I9 still asks for a finite-sample correction (McNeish and Stapleton 2016)." in text
