from __future__ import annotations
import re
from pathlib import Path

import pytest
import yaml

from plumb import packs

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "review"
PACK = ROOT / "packs" / "configurational"
IDS = [f"B{i}" for i in range(1, 16)]
EM_DASH = chr(0x2014)


def _audit():
    return (SKILL / "agents" / "manuscript-audit.md").read_text(encoding="utf-8")


# --- Task 1: the manuscript audit types a QCA paper by its sets and records the analysis ---

FIELD = ("Configurational analysis: <\"none\", or: variant: <csQCA | fsQCA | mvQCA | more than one>; role: <main | "
         "secondary>; cases: <N as the paper prints it, with page>; conditions: <number>; outcome: <the outcome set; "
         "negation analyzed: yes | no>; software: <as named, with version, or \"not stated\">; membership scores "
         "printed: <table and page | no>>")
PARAGRAPH = ("Fill `Configurational analysis:` only when the paper runs a qualitative comparative analysis: it calibrates "
             "cases into sets (crisp, fuzzy, or multi-value), builds a truth table, and reports sufficient configurations "
             "with consistency and coverage, as a solution formula or a configuration chart. Temporal QCA counts. These do "
             "not count: \"configuration\" or \"bundle\" used for interaction terms or clusters estimated by regression, "
             "cluster or latent class analysis, necessary condition analysis (NCA) used alone, and coincidence analysis "
             "(CNA). Otherwise write \"none\". Role is main when a numbered hypothesis or the headline result rests on a QCA "
             "solution, and secondary when the QCA appears only as a robustness check, an appendix, or a complement no "
             "hypothesis rests on. Cases is the number of cases the paper says the analysis uses. Conditions is the number "
             "of conditions in the main truth table, not counting the outcome. Consistency, coverage, PRI, and membership "
             "scores are not estimates: do not list them under `Inference:` or `Nonlinear terms:`, and do not list a "
             "conjunction of conditions under `Nonlinear terms:`. Copy what the paper states; judge nothing.")
OVERLAY = "List the configurational overlay under `Overlays:` only when `Configurational analysis:` is not \"none\"."
QCA_TYPE = ("A paper whose main analysis is qualitative comparative analysis (QCA, csQCA, fsQCA, or mvQCA) is typed by "
            "the rules in this paragraph, treating its sets as its focal variables: memberships the authors assign case "
            "by case, by judgment, from interviews, observation, or documents they read are qualitative evidence; "
            "memberships calibrated by a stated rule from a measured variable take the type of that variable's source. "
            "When the sets come from more than one kind of source (interviews, observation, or documents read case by case; "
            "questionnaires; records), record two types: `qualitative` first when any set is assigned "
            "case by case, otherwise as the survey rule above says. Record the analysis itself under `Configurational "
            "analysis:`, where the configurational overlay picks it up; never record `other (QCA)`.")


def test_fingerprint_has_the_configurational_line():
    template = _audit().split("# Fingerprint\n", 1)[1].split("```", 1)[0]
    assert template.count(FIELD) == 1
    assert template.index("Simulation results:") < template.index("Configurational analysis:")
    assert template.rstrip().endswith(FIELD)


def test_configurational_paragraph_follows_the_simulation_results_paragraph():
    text = _audit()
    assert text.count(PARAGRAPH) == 1
    assert (text.index("Decide the scope from the paper's own wording; judge nothing.") < text.index(PARAGRAPH)
            < text.index("## Completion"))


def test_overlays_paragraph_lists_the_configurational_overlay():
    inference = 'List the inference overlay under `Overlays:` only when `Inference:` is not "none".'
    assert _audit().count(inference + " " + OVERLAY) == 1


def test_qca_papers_are_typed_by_their_sets():
    text = _audit()
    assert text.count(QCA_TYPE) == 1
    assert ("Documents coded into variables for statistical analysis are archival data, not qualitative evidence. "
            + QCA_TYPE) in text
    assert "other (QCA)" not in text.replace(QCA_TYPE, "")
    assert "since no pack checks QCA yet" not in text
    for s in (FIELD, PARAGRAPH, OVERLAY, QCA_TYPE):
        assert EM_DASH not in s


# --- Task 3: the pack's frame ---

JUDGMENT = {"B4", "B14", "B15"}
CHECKLIST = {
    "B1": "Every set in the analysis, the outcome and each condition (and any negated set the paper calibrates on its own), has a stated definition, raw measure, and source, and its calibration anchors: full membership, crossover, and full non-membership for a fuzzy set, or the cut points for a crisp or multi-value set.",
    "B2": "Each anchor comes with a stated reason: an external standard, theoretical or case knowledge, the labels of a survey scale, a break in the distribution, or prior practice. Anchors set at sample percentiles pass when the paper says why; they fail when applied by default with no reason, and especially when the paper cites an external standard for that set and does not use it.",
    "B3": "No case has a membership score of exactly 0.5 in any set, or the paper says how such cases were handled; the number of cases in the truth table equals the number the analysis uses, or the paper accounts for the difference.",
    "B4": "The distribution of membership in each set, and in the outcome set especially, is reported (for example, the share of cases above 0.5), and where membership is skewed the paper says how that bears on its consistency and coverage figures.",
    "B5": "The number of logically possible configurations (2^k for k crisp or fuzzy conditions; the product of the category counts for multi-value conditions) and the share of them with no cases are reported, and the paper defends the number of conditions relative to the number of cases.",
    "B6": "The truth table is reported, in the paper or a supplement, with each row's case count, raw consistency, and, for fuzzy sets, PRI; the raw consistency cutoff, the PRI cutoff for fuzzy sets, and the frequency cutoff are stated, with the share of cases the frequency cutoff keeps. No row or configuration the paper keeps has PRI below 0.50.",
    "B7": "The fit figures cohere: each configuration's unique coverage is at most its raw coverage; solution coverage is at least the largest raw coverage and at most the sum of raw coverages; unique coverages sum to at most solution coverage; each row's and configuration's PRI is at most its raw consistency; the frequency cutoff times the number of rows kept does not exceed the number of cases; and where the paper prints membership scores, the figures recomputed from them are consistent with the reported ones.",
    "B8": "Necessity is tested as its own step, for the outcome (and for its negation when the paper analyzes it), with consistency and coverage for each condition and a stated threshold. A condition called necessary passes that test, and its relevance is addressed (coverage or relevance of necessity). No condition is called necessary because it appears in every sufficient configuration. The order in which the paper presents necessity and sufficiency is never a finding by itself.",
    "B9": "The paper says which solution it interprets (conservative, intermediate, or parsimonious) and why; for an intermediate solution it lists the directional expectations; when it marks core and peripheral conditions it says how they were derived; and it excludes or discusses assumptions about logical remainders that contradict its own necessity results or are otherwise untenable.",
    "B10": "The software and its version are named, and the paper says whether more than one model fits the truth table equally well and, if so, which it reports and why.",
    "B11": "The presence and the absence of the outcome are analyzed separately, or the paper says why only one is; no claim about the absence of the outcome is derived by negating the solution for its presence.",
    "B12": "Claims from the QCA are stated in set-theoretic terms, as configurations that are sufficient or conditions that are necessary. QCA output is not read as the net effect of a single condition, is not described with significance or \"X increases Y\" language, and does not by itself support a hypothesis stated as a correlation or net effect; a condition that appears in some configurations is not described as mattering in all; and a configuration with low raw coverage is not described as the typical or main route to the outcome, nor coverage as variance explained.",
    "B13": "Robustness is reported for the calibration anchors (at least the crossover), the consistency and PRI cutoffs, and the frequency cutoff, saying what changed and which configurations survive.",
    "B14": "Solutions are linked back to cases: typical cases for each configuration are named or described (small N), or the cases each configuration covers are compared (large N), and cases that contradict a sufficient configuration are acknowledged.",
    "B15": "Claims about sequence, dynamics, or change over time rest on a temporal approach (temporal QCA, separate analyses by period, trajectory-based QCA, or pooled, between, and within consistency for a panel) or are scoped to cross-sectional configurations; a pooled panel of firm-years says whether consistency holds within and between units.",
}
RULES = [
    "When `Configurational analysis:` has role main, a finding is 'Undermines the main claim' in these cases only. (a) B8: a condition that a numbered hypothesis or the headline result states is necessary has no necessity test in the paper, or the paper's own necessity consistency for it is below the threshold the paper itself states. (b) B6 or B7: the configuration that the headline result or a numbered hypothesis rests on has a reported PRI below 0.50; or its PRI recomputed from printed membership scores is below 0.50, or its recomputed raw consistency is below 0.75, while the reported figure is at or above that value, with both judged by the rounding interval the script uses. The 0.50 PRI floor is from Greckhamer et al. (2018) and Mattke et al. (2022); the 0.75 consistency floor is Ragin's (2008) minimum as cited in Fiss (2011); treating a headline configuration below either as 'Undermines the main claim' is this pack's rule.",
    "Any other finding on an analysis with role main is at most 'Weakens a claim'. In particular: a condition called necessary whose necessity consistency is below the 0.90 convention, when the paper states no threshold of its own, is 'Weakens a claim'; any other recomputed mismatch on a headline figure is 'Weakens a claim'. A finding that only notes a missing report is 'Minor', and is written once per check. Missing reports are: software and version; model ambiguity; the share of logical remainders; the distribution of memberships; the truth table when the three thresholds and the fit of each configuration are stated; necessity figures for negated conditions; an analysis of the outcome's absence when the paper makes no claim about the absence; robustness that covers some but not all of the anchors, the consistency and PRI cutoffs, and the frequency cutoff; case linkage for memberships calibrated from records; the share of cases the frequency cutoff keeps; necessity figures for the outcome's absence; a reason for rows coded 0 at or above every stated cutoff; and which definition a stated share of logical remainders uses.",
    "When `Configurational analysis:` has role secondary, every finding is 'Minor', except that a B7 flag, or a configuration the paper keeps with PRI below 0.50, is 'Weakens a claim'.",
    "B4, B5, and B13 findings are never above 'Weakens a claim'. None of them turns on a numeric threshold for skew, for the ratio of conditions to cases, or for how much a solution may change; a solution that changes under other anchors or thresholds is expected, and a B13 finding is about what the paper reports.",
    "B10 findings are always 'Minor'.",
    "B15 is 'Weakens a claim' when the headline result or a numbered hypothesis claims an order in time; otherwise it is 'Minor'.",
]
NOTES = {
    "face-validity.md": "Consistency, coverage, PRI, and membership scores from a qualitative comparative analysis are not effect estimates: do not catalog or benchmark them in Steps 1 to 6. In Step 7, unless another pack's note tells you to skip Step 7, assess the raw measure behind each set calibrated by rule from a measured variable as you would any measure; whether the calibration anchors fit the set's definition belongs to the configurational pack (B1, B2). If the paper reports no other estimate, write 'No estimates to benchmark.' for Steps 1 to 6.",
    "completeness.md": "For a qualitative comparative analysis, the standard components (calibration table, truth table and thresholds, necessity analysis, robustness to anchors and thresholds) are the configurational pack's checks; do not list them under Step 3, and do not ask for a robustness check that varies a core assumption of the QCA.",
    "construction-ledger-producer.md": "For a qualitative comparative analysis, record each condition set with role `treatment` and each outcome set with role `DV`; put the raw measure and the calibration anchors, as the paper gives them, in `construction_formula`, and start `construction_caveats` with 'QCA set'. Write 'not stated' for anchors the paper does not give; do not judge them, since the configurational pack does. Record each set once, as a variable, and not also under `constructs`.",
    "theory-logic.md": "When a hypothesis states a net effect or a correlation and the paper tests it only with a qualitative comparative analysis, leave that mismatch to the configurational pack (B12); critique the argument itself.",
    "stage-4-compiler": "Findings under the configurational pack's B5 (conditions relative to cases) and B14 (configurations linked to cases) are not demands for statistical generalizability or a sample-size justification; the qualitative pack's fourth severity rule does not remove them. When a core or type-pack source and a configurational agent raise the same problem about the same set, configuration, or QCA table, write one issue under the configurational check id with the severity the configurational rules set. Archival severity rule 1 does not apply to an alternative explanation of a QCA configuration. Such a finding is 'Weakens a claim', and 'Undermines the main claim' only when the headline result or a numbered hypothesis states that the configuration causes the outcome and the paper gives no argument about direction or confounding.",
    "stress-test-prompt": "For a qualitative comparative analysis, do not ask for standard errors, p-values, significance tests, effect sizes, or statistical power for consistency, coverage, or a solution; they are not estimates. Asking whether the number of conditions suits the number of cases, or whether configurations hold in named cases, is fair.",
    "packs/qualitative/agents/methods-checks.md": "When the findings rest on a qualitative comparative analysis, the configurational pack checks the QCA itself: calibration, the truth table and its thresholds, necessity, logical remainders, fit, robustness, and whether solutions are linked back to cases (B1 to B15). Under CHECK 1, do not assess QCA as a named approach; check only the case, interview, or document work that produced the case evidence. Under CHECK 2, the logic of case selection stays yours (Q7, Q10); the number of conditions relative to cases is B5. Under CHECK 7, cases that contradict a sufficient configuration are B14.",
    "packs/qualitative/agents/grounding-audit.md": "When the findings are QCA solutions, treat each set (the outcome and each condition) as a construct and rate how the case evidence grounds its definition and the memberships assigned. Do not enter a configuration's sufficiency or a condition's necessity in the Relationship Ledger; the configurational pack checks those from the truth table (B6 to B9, B12). Enter as a relationship only a claim about why conditions combine or how they work together in the cases.",
    "packs/qualitative/agents/claim-to-excerpt.md": "A QCA configuration that no case description supports is B14, which the configurational pack owns; do not raise it under Q4. Check only the excerpts the paper quotes against the claims they are attached to.",
    "packs/qualitative/agents/alternative-interpretations.md": "Rival readings that come from the QCA procedure itself (calibration choices, skewed membership, assumptions about logical remainders, another model fitting the same truth table) belong to the configurational pack. Generate rivals about the cases and the evidence.",
    "packs/archival/agents/methods-checks.md": "For results from a qualitative comparative analysis (a truth table, consistency and coverage, a solution formula, or a configuration chart), leave to the configurational pack, which runs with you: CHECK 3, since QCA conditions are not controls; CHECK 6 and CHECK 7, since power, precision, and multiple testing do not apply to QCA solutions; CHECK 10 for consistency, coverage, and PRI, which are not effect sizes; and the calibration of raw measures into sets. CHECK 1 (a condition defined from the outcome), CHECK 4, CHECK 4b, and CHECK 8 apply to the QCA's sample and sets as to any analysis, and every check applies to regression estimates the paper also reports.",
    "packs/archival/agents/adversarial-dgp.md": "For a finding from a qualitative comparative analysis, alternatives about confounding, selection, or reverse causality are yours. In Step 4, do not treat consistency or coverage as the size of an effect; say whether the alternative could produce the configuration's consistency by itself. Artifacts of the QCA procedure (calibration, skew, remainders) belong to the configurational pack.",
    "packs/archival/agents/triangulation.md": "Leave to the configurational pack whether the QCA's fit figures agree with one another (B7) and whether claims about the absence of the outcome follow from the analysis of its presence (B11). Checking that the QCA and any regression the paper reports tell a consistent story stays yours.",
    "packs/survey/agents/claims-and-controls.md": "For results from a qualitative comparative analysis, leave causal or net-effect wording about configurations to the configurational pack (B12), and do not treat QCA conditions as controls under S16 or S17. S14 to S17 apply as usual to any regression the paper also reports.",
}
CORE = ("face-validity.md", "completeness.md", "construction-ledger-producer.md", "theory-logic.md",
        "stage-4-compiler", "stress-test-prompt")
LABEL = "SYNTHETIC TEST PAPER, NOT REAL RESEARCH"


def _pack():
    return packs.load_pack(PACK)


def _built():
    return packs.load_all(ROOT / "packs")


def _run(types, overlay=True):
    names = list(types) + (["configurational"] if overlay else [])
    return {"packs": names, "overlays": ["configurational"] if overlay else [], "types_without_pack": [],
            "primary_pack": types[0]}


def test_pack_loads_as_an_overlay():
    p = _pack()
    assert p.name == "configurational" and p.overlay is True and p.turns_off == []
    assert p.read_checkin_lines == ["Configurational analysis:"]
    assert "context" not in p.slots and "theory" not in p.slots
    assert [i["id"] for i in p.checklist] == IDS


def test_checklist_matches_the_spec():
    items = {i["id"]: i for i in _pack().checklist}
    for k in IDS:
        assert items[k]["text"] == CHECKLIST[k], k
        assert items[k]["adjudication"] == ("judgment" if k in JUDGMENT else "paper"), k


def test_severity_rules_are_the_spec_rules():
    rules = _pack().severity_rules
    assert rules == RULES
    for r in rules:
        assert "one level" not in r and "downgrade" not in r and EM_DASH not in r


def test_detection_cues():
    cues = " ".join(_pack().detection_cues)
    for s in ("fsQCA", "csQCA", "mvQCA", "truth table", "PRI", "Tosmana", "SetMethods", "crossover point",
              "configuration chart with filled and crossed circles"):
        assert s in cues, s
    assert "coincidence" not in cues.lower()


def test_core_notes_are_the_spec_notes():
    notes = _pack().core_notes
    assert set(notes) == set(NOTES)
    for target, text in NOTES.items():
        assert notes[target] == [text], target


@pytest.mark.parametrize("type_pack,own", [
    ("archival", ("packs/archival/",)),
    ("qualitative", ("packs/qualitative/",)),
    ("survey", ("packs/survey/",)),
])
def test_notes_reach_only_the_packs_that_run(type_pack, own):
    adjust = packs.core_adjust(_built(), _run([type_pack]))
    got = {t for t, ns in adjust["notes"].items() for n in ns if n["pack"] == "configurational"}
    want = {t for t in NOTES if not t.startswith("packs/") or t.startswith(own)}
    want.add("construction-ledger-checker.md")
    assert got == want
    for t in got:
        assert all(n["role"] == "overlay" for n in adjust["notes"][t] if n["pack"] == "configurational")


@pytest.mark.parametrize("type_pack", ["archival", "qualitative", "survey"])
def test_turn_offs_equal_those_of_the_type_pack_alone(type_pack):
    built = _built()
    assert packs.core_adjust(built, _run([type_pack]))["off"] == packs.core_adjust(built, _run([type_pack], False))["off"]


@pytest.mark.parametrize("fixture", ["planted-1", "planted-2"])
def test_fixture_is_labeled_synthetic(fixture):
    exp = yaml.safe_load((PACK / "fixtures" / fixture / "expected.yaml").read_text(encoding="utf-8"))
    assert exp["synthetic"] is True and exp["owner"] == "blind-agent" and exp["label"] == LABEL
    assert exp["status"] in ("pending_planting", "ready")
    assert isinstance(exp.get("must_not_raise"), list)
    assert all(isinstance(s, str) for s in exp["must_not_raise"])


def test_validate_packs_lists_the_overlay():
    loaded = _built()
    assert loaded["configurational"].overlay and loaded["configurational"].fixture_status == "pending_planting"


# --- Task 4: qca-numbers agent (verify slot) ---

def _agent(name):
    return (PACK / "agents" / name).read_text(encoding="utf-8")


LESSON_LINES = ("The contracts in `skills/review/shared/contracts.md` bind you.",
                "The works named in this file are background for you. Cite one in your output only if you "
                "fetched it in this run; otherwise state the concern without the citation.")


def _script():
    import importlib.util
    spec = importlib.util.spec_from_file_location("qca_check", PACK / "scripts" / "qca_check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_numbers_agent():
    assert _pack().slots.get("verify") == ["qca-numbers.md"]
    text = _agent("qca-numbers.md")
    for s in LESSON_LINES + ("stage-1/configurational_numbers.md", "## Records checked", "## Flags",
                             "## Rounding-sensitive", "## Facts for the diagnose agents", "## Not computed",
                             "Quick", "Record: <id>. Table: <label>. Cells: <table:row:col, ...>.",
                             "Flag nothing as missing"):
        assert s in text, s
    for kind in ("fit_table", "truth_table", "design", "necessity", "memberships"):
        assert f"`{kind}`" in text, kind


def test_numbers_agent_runs_the_script_with_its_own_tools():
    text = _agent("qca-numbers.md")
    assert "tools: [Read, Write, Bash, Glob]" in text.split("---", 2)[1]
    assert "The orchestrator will provide `PDF_PATH`, `PAGE_COUNT`, `{WORKSPACE}`, and `{PLUGIN}`." in text
    assert ("`python3 {PLUGIN}/packs/configurational/scripts/qca_check.py {WORKSPACE}/stage-1/qca_inputs.json "
            "{WORKSPACE}/stage-1/qca_check.json`") in text
    assert "with the file-writing tool" in text and "Do not compute by hand" in text
    assert not re.search(r"(cat|echo|printf|tee)[^\n`]*>", text)


def test_numbers_agent_copies_printed_strings_and_splits_solutions():
    text = _agent("qca-numbers.md")
    for s in ("exactly as printed", "`percent: true`", "one record per solution", "`split_unclear: true`",
              "never a count you make", "A crisp membership is the string \"0\" or \"1\".",
              "conditions joined by `*`, with `~` before a negated condition", "`states_half`",
              "For mvQCA, build no `memberships` record.", "not the number of rows coded 1",
              "`observed_rows` is the number of rows with at least one case", "are in the same unit"):
        assert s in text, s


def test_numbers_agent_reason_map_matches_the_script():
    text = _agent("qca-numbers.md")
    block = text.split("The check id follows the reason:\n", 1)[1].split("\n\n", 1)[0]
    listed = {}
    for line in block.splitlines():
        check, reasons = line[2:].split(": ", 1)
        for r in re.findall(r"`([a-z_0-9]+)`", reasons):
            listed[r] = check
    assert listed == _script().REASON_CHECK


def test_numbers_agent_names_every_fact_the_script_writes():
    text = _agent("qca-numbers.md")
    for fact in ("logical_rows", "least_remainder_share", "remainder_share_unmatched", "remainder_share_matches",
                 "cases_short_of_n", "cases_in_table", "printed_half_row_unknown", "share_above_half",
                 "term_below_cutoff", "headline_terms", "rows_coded_0_meeting_every_cutoff", "consistency_gap",
                 "in_negated_solution", "recomputed_pri_below_floor", "recomputed_consistency_below_floor",
                 "at_printed_values:<record>", "observed_rows", "cases_in_rows", "cases_left_out"):
        assert f"`{fact}`" in text, fact
    source = (PACK / "scripts" / "qca_check.py").read_text(encoding="utf-8")
    for fact in re.findall(r'out\.fact\("B\d+", "([a-z_0-9]+)"', source):
        assert f"`{fact}`" in text, fact


# --- Task 5: qca-calibration agent (diagnose slot) ---

def _rule(n):
    return '"' + RULES[n - 1] + '"'


ISSUE_LINES = ("   Paper's best case: <one sentence>", "   Excerpt: \"<one sentence copied word for word from the paper",
               "   Page: <the page the paper prints there", "   Severity: <Undermines the main claim | Weakens a claim | "
               "Minor>", "   What would settle it:", "## Checked and fine")


def test_calibration_agent():
    assert _pack().slots.get("diagnose", [])[:1] == ["qca-calibration.md"]
    text = _agent("qca-calibration.md")
    assert "Write `{WORKSPACE}/stage-4/qca_calibration.md`. Its first line is `Pack: configurational`." in text
    assert "   Check: <B-id>. Unit: set. Tag: [paper | external | judgment]" in text
    for s in ISSUE_LINES:
        assert s in text, s
    assert re.findall(r"^### (B\d+)\. ", text, re.M) == ["B1", "B2", "B3", "B4"]
    for n in (2, 3, 4):
        assert _rule(n) in text, n
    assert _rule(1) not in text


def test_calibration_agent_passes_reasoned_percentiles_and_scale_labels():
    b2 = _agent("qca-calibration.md").split("### B2.", 1)[1].split("### B3.", 1)[0]
    for s in ("pass when the paper says why", "Memberships a survey calibrates from scale labels have a stated reason.",
              "cites an external standard for that set elsewhere", "the choice of anchor is never a finding"):
        assert s in b2, s


def test_calibration_agent_takes_b3_from_the_papers_own_count():
    b3 = _agent("qca-calibration.md").split("### B3.", 1)[1].split("### B4.", 1)[0]
    for s in ("never from the rebuilt truth-table rows alone", "\"printed 0.50\", not exactly 0.5",
              "unless the paper prints three or more decimals or says the score is 0.5", "A shortfall the paper explains"):
        assert s in b3, s
    b4 = _agent("qca-calibration.md").split("### B4.", 1)[1].split("### Guardrails", 1)[0]
    assert "No numeric threshold decides skew" in b4


def test_calibration_agent_reads_the_ledger_and_dropped_flags():
    text = _agent("qca-calibration.md")
    for s in ("`{WORKSPACE}/stage-2/construction_ledger.json`, if it exists", "start with \"QCA set\"",
              "`numbers:pack:configurational:<n>`", "`{WORKSPACE}/stage-1/dropped_flags.md`"):
        assert s in text, s


# --- Task 6: qca-analysis agent (diagnose slot) ---

def test_analysis_agent():
    assert _pack().slots["diagnose"][:2] == ["qca-calibration.md", "qca-analysis.md"]
    text = _agent("qca-analysis.md")
    assert "Write `{WORKSPACE}/stage-4/qca_analysis.md`. Its first line is `Pack: configurational`." in text
    assert "   Check: <B-id>. Unit: <configuration | set | table>. Tag: [paper | external | judgment]" in text
    for s in ISSUE_LINES:
        assert s in text, s
    assert re.findall(r"^### (B\d+)\. ", text, re.M) == [f"B{i}" for i in range(5, 12)]
    for n in (1, 2, 3, 4, 5):
        assert _rule(n) in text, n
    assert "The first rule is applied by you alone" in text


def test_analysis_agent_turns_flags_into_issues_and_keeps_facts_as_facts():
    text = _agent("qca-analysis.md")
    b7 = text.split("### B7.", 1)[1].split("### B8.", 1)[0]
    for s in ("Results under `## Rounding-sensitive` are not issues.", "are facts, never issues",
              "`term_below_cutoff`", "is not an error"):
        assert s in b7, s
    b6 = text.split("### B6.", 1)[1].split("### B7.", 1)[0]
    for s in ("A consistency cutoff of 0.75 or 0.80 passes", "never a finding", "`rows_coded_0_meeting_every_cutoff`",
              "raise it only when the paper gives no reason anywhere", "`in_negated_solution`",
              "counts as a reported PRI below 0.50 for rule 1(b)"):
        assert s in b6, s
    assert "`recomputed_pri_below_floor`" in text and "`recomputed_consistency_below_floor`" in text


def test_analysis_agent_b8_catches_necessity_by_presence_in_every_configuration():
    b8 = _agent("qca-analysis.md").split("### B8.", 1)[1].split("### B9.", 1)[0]
    for s in ("\"because X appears in all configurations, X is necessary\"", "apply rule 1(a)",
              "The order in which the paper presents necessity and sufficiency is never a finding by itself.",
              "the paper's or the 0.90 convention"):
        assert s in b8, s


def test_analysis_agent_never_requires_a_solution_type_or_esa():
    b9 = _agent("qca-analysis.md").split("### B9.", 1)[1].split("### B10.", 1)[0]
    assert "The choice of solution type is never a finding by itself" in b9
    assert "Enhanced Standard Analysis is not required." in b9
    b10 = _agent("qca-analysis.md").split("### B10.", 1)[1].split("### B11.", 1)[0]
    assert "ask only for the disclosure" in b10



# --- Task 7: qca-interpretation agent (diagnose slot), ownership, and authoring rules ---

AGENTS = ("qca-numbers.md", "qca-calibration.md", "qca-analysis.md", "qca-interpretation.md")
DIAGNOSE = AGENTS[1:]


def test_interpretation_agent():
    assert _pack().slots["diagnose"] == list(DIAGNOSE)
    text = _agent("qca-interpretation.md")
    assert "Write `{WORKSPACE}/stage-4/qca_interpretation.md`. Its first line is `Pack: configurational`." in text
    assert "   Check: <B-id>. Unit: <claim | configuration>. Tag: [paper | external | judgment]" in text
    for s in ISSUE_LINES:
        assert s in text, s
    assert re.findall(r"^### (B\d+)\. ", text, re.M) == ["B12", "B13", "B14", "B15"]
    for n in (2, 3, 4, 6):
        assert _rule(n) in text, n
    assert _rule(1) not in text
    for s in ("`Inference:` and `Nonlinear terms:` lines", "Hypothesis Framing Inventory"):
        assert s in text, s


def test_interpretation_agent_b12_and_b14():
    text = _agent("qca-interpretation.md")
    b12 = text.split("### B12.", 1)[1].split("### B13.", 1)[0]
    for s in ("declared supported by a QCA table, which is the headline failure", "coverage described as variance explained",
              "A p-value from a stated permutation or bootstrap test of consistency is not a finding."):
        assert s in b12, s
    b13 = text.split("### B13.", 1)[1].split("### B14.", 1)[0]
    assert "A one-sentence claim of robustness" in b13
    b14 = text.split("### B14.", 1)[1].split("### B15.", 1)[0]
    assert "not a demand for statistical generalization or for a larger sample" in b14


def test_every_check_is_owned_by_one_diagnose_agent():
    owners = {}
    for a in DIAGNOSE:
        for c in re.findall(r"^### (B\d+)\. ", _agent(a), re.M):
            assert c not in owners, c
            owners[c] = a
    assert sorted(owners, key=lambda c: int(c[1:])) == IDS
    assert not re.findall(r"^### B\d+", _agent("qca-numbers.md"), re.M)


def test_every_configurational_agent_follows_the_authoring_rules():
    for a in AGENTS:
        text = _agent(a)
        head = text.split("---", 2)[1]
        for k in ("name:", "description:", "maxTurns:"):
            assert k in head, (a, k)
        for s in LESSON_LINES:
            assert s in text, (a, s)
        assert text.split("## Input", 1)[1].lstrip().startswith(
            "The orchestrator will provide `PDF_PATH`, `PAGE_COUNT`,"), a
        for s in ('If it says "none" or is missing', "If you find none, write \"None.\"", "20-page chunks",
                  "Role: main when a numbered hypothesis or the headline result",
                  "User corrections", "Reply to the orchestrator in one sentence that names the file you wrote."):
            assert s in text, (a, s)
        assert EM_DASH not in text, a
        assert not re.search(r"(cat|echo|printf|tee)[^\n`]*>", text), a
    for a in DIAGNOSE:
        text = _agent(a)
        for s in ("Never predict the result", "`{WORKSPACE}/stage-0/contribution_defense.md`",
                  "`{WORKSPACE}/stage-1/configurational_numbers.md`", "Flag an absence only after searching",
                  "name where you looked"):
            assert s in text, (a, s)


# --- Task 10: README, repo spec, and Stage 0 (deferred to post-1e items 17 and 18) ---

def test_readme_and_spec_name_the_configurational_overlay():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    section = readme.split("## Packs", 1)[1].split("\n## ", 1)[0]
    assert "- **Configurational** is an overlay." in section
    assert section.index("- **Theory** is a paper type.") < section.index("- **Configurational** is an overlay.")
    assert "Papers built on qualitative comparative analysis get core checks only for now." not in readme
    assert len(re.findall(r"A pack adds checks for one kind of paper\. \w+ are built\.", readme)) == 1
    spec = (ROOT / "docs" / "spec.md").read_text(encoding="utf-8")
    assert "The configurational pack is an overlay for qualitative comparative analysis." in spec
    assert "run the core only until a configurational overlay exists" not in spec


def test_stage_0_asks_about_the_configurational_overlay():
    text = (SKILL / "stages" / "stage-0-intake.md").read_text(encoding="utf-8")
    step11 = text.split("\n11. ", 1)[1].split("\n12. ", 1)[0]
    assert "the QCA (its variant, cases, and conditions) for configurational" in step11
    assert "setup:overlay:<pack>" in step11
    assert "At Quick depth, do not ask about the configurational overlay" not in step11


def test_final_fix_a_agent_sentences():
    analysis = _agent("qca-analysis.md")
    b6 = analysis.split("### B6.", 1)[1].split("### B7.", 1)[0]
    assert "(the numbers agent's `consistency_gap` fact), that gap is its stated cutoff" in b6
    assert "at three or more decimals counts as a reported PRI below 0.50 for rule 1(b)" in b6
    rule = analysis.split("For rule 1(b),", 1)[1].split("\n", 1)[0]
    assert "or a PRI the paper prints below 0.50 at three or more decimals for a headline configuration (B6)" in rule
    numbers = _agent("qca-numbers.md")
    assert 'a figure the paper prints as "1" stays "1"' in numbers
    flags = numbers.split("## Flags\n", 1)[1].split("\n", 1)[0]
    assert flags.endswith('For a number taken from the text, write "Cells: none."')
