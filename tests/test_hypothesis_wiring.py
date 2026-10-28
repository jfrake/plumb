"""The hypothesis ledger's wiring: checklist, notes, labels, agents, stage files, and the pack agents that read it."""
from __future__ import annotations
import json
import re
from pathlib import Path

import pytest
import yaml

from plumb import checkin, packs, validated

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "review"
AGENTS = SKILL / "agents"
STAGES = SKILL / "stages"


def _read(path):
    return Path(path).read_text(encoding="utf-8")


# --- Task 1: the checklist, copied from spec section 4 ---

CHECKLIST = [
    ("HL1", "paper",
           "Every stated hypothesis is tested: the paper names a table, column, and term, a reported test "
           "statistic, or a figure it presents as the test, and says so when a hypothesis is left untested, "
           "with a reason"),
    ("HL2", "judgment",
           "Every result the paper presents in its abstract or conclusion as evidence for its theory maps to"
           " a stated hypothesis, or is labeled exploratory or post hoc"),
    ("HL3", "paper",
           "The verdict the paper gives each hypothesis (supported, marginally supported, partially "
           "supported, not supported) agrees with the estimate of its focal test under the paper's own "
           "stated criterion (significance level and tails), or, where the paper states none, under the "
           "thresholds its table notes use"),
    ("HL4", "paper",
           "A hypothesis called partially supported names which part held and which did not, and the part "
           "that held rests on the test the paper designates for the hypothesis"),
    ("HL5", "paper",
           "The sign of each focal test estimate matches the direction the hypothesis predicts on the scale "
           "the model estimates (once reverse-coded, rank, hazard, or time-to-event outcomes are accounted "
           "for), and no hypothesis is called supported by an estimate of the opposite sign or by a "
           "one-tailed p-value for an estimate in the wrong direction"),
    ("HL7", "paper",
           "A hypothesis framed as a null (no relationship or no difference, in either direction) is judged "
           "by that framing with a two-sided test: when its test does not reject, the paper calls it "
           "supported, and when its test rejects, not supported"),
    ("HL8", "paper",
           "A hypothesis that an effect differs across groups, periods, or conditions rests on a test of the"
           " difference (a pooled interaction or a test of equal coefficients), not on one estimate being "
           "significant and the other not"),
    ("HL9", "paper",
           "An interaction hypothesis is supported by its product term, estimated in a model that includes "
           "the product term, and the product term's sign fits the shape the hypothesis states (strengthens,"
           " weakens, reverses) given the sign of the effect it moderates; support is not drawn from the "
           "moderator's own coefficient or from a model without the product term"),
    ("HL10", "paper",
           "A U-shaped or inverted-U hypothesis is not called supported on the sign and significance of a "
           "squared term alone: the paper reports where the turning point lies against the observed range "
           "and the slopes at both ends, or an equivalent test (two lines, or the Lind and Mehlum test); a "
           "diminishing-returns hypothesis needs only the slope at the far end"),
    ("HL11", "paper",
           "A mediation hypothesis is supported by an estimate of the indirect effect with an interval, not "
           "by the causal-steps sequence alone; full mediation is not claimed because the direct effect lost"
           " significance; and a moderated-mediation hypothesis rests on an index of moderated mediation or "
           "an equivalent test, not on an indirect effect significant at one moderator value and not at "
           "another"),
    ("HL12", "paper",
           "Each hypothesis has the same number, direction, and constructs wherever the paper states or "
           "restates it (abstract, introduction, theory section, results, tables, discussion), and the "
           "numbering has no unexplained gaps; a paraphrase is not a finding"),
    ("HL13", "paper",
           "A hypothesis first stated after the results it concerns, or introduced by an unexpected finding,"
           " is labeled post hoc and kept apart from the a priori hypotheses in the abstract and conclusions"),
    ("HL14", "judgment",
           "The constructs a hypothesis names match the variables its test uses: the model's outcome is the "
           "hypothesis's outcome and its predictor the hypothesis's predictor, at the level the hypothesis "
           "states, or the paper states the link between them"),
    ("HL15", "paper",
           "When the paper designates one test of a hypothesis (a full model, a primary outcome, a stated "
           "column), its verdict rests on that test, and a verdict of support across specifications holds "
           "for the specifications the paper names"),
]


def test_checklist_matches_the_spec():
    items = yaml.safe_load(_read(SKILL / "checklists" / "hypotheses.yaml"))
    assert [(i["id"], i["adjudication"], i["text"]) for i in items] == CHECKLIST
    assert all(set(i) == {"id", "text", "adjudication"} for i in items)


def test_retired_ids_are_absent():
    text = _read(SKILL / "checklists" / "hypotheses.yaml")
    assert "HL6" not in text and "HL16" not in text and "\u2014" not in text


# --- Task 4: the ledger pair's notes, and the label for a dropped hypothesis flag ---

def _pack(notes):
    return packs.Pack(name="survey", path=Path("."), detection_cues=[], slots={}, core_notes=notes)


def test_a_producer_note_reaches_the_checker():
    run = {"packs": ["survey"], "overlays": [], "types_without_pack": [], "primary_pack": "survey"}
    notes = packs.core_adjust({"survey": _pack({"hypothesis-ledger-producer.md": ["Read items as scales."]})},
                              run)["notes"]
    assert notes["hypothesis-ledger-checker.md"] == notes["hypothesis-ledger-producer.md"]
    assert notes["hypothesis-ledger-checker.md"][0]["text"] == "Read items as scales."


def test_a_note_keyed_to_the_checker_fails_validation(tmp_path):
    d = tmp_path / "packs" / "survey"
    (d / "agents").mkdir(parents=True)
    (d / "pack.yaml").write_text("name: survey\ndetection_cues: [questionnaire]\nslots: {}\n"
                                 "core_notes: {hypothesis-ledger-checker.md: {text: x}}\n", encoding="utf-8")
    with pytest.raises(packs.PackError, match="note hypothesis-ledger-producer.md instead"):
        packs.load_pack(d)


def test_dropped_hypothesis_flag_is_labeled_not_a_problem(tmp_path):
    ws = tmp_path / "ws"
    for d in ("stage-1", "stage-4", "stage-5", "stage-6"):
        (ws / d).mkdir(parents=True)
    (ws / "run.json").write_text(json.dumps({"depth": "quick", "issues_list_mode": "full"}))
    for d in ("stage-5", "stage-6"):
        (ws / d / "issues.json").write_text("[]")
    (ws / "stage-6" / "draft.md").write_text("## Issues\n")
    (ws / "stage-1" / "unverified_numbers.md").write_text("")
    item = "numbers:hyp:H2:HL3"
    (ws / "stage-1" / "flags.json").write_text(json.dumps([
        {"item": item, "kind": "number", "title": "H2 verdict", "summary": "H2 is called supported.",
         "excerpt": None, "ms_page": 15, "table": "Table 3", "cells": ["table_03.csv:4:2"]}]))
    checkin.record(ws, "numbers", item, "A. Real problem in the paper (Recommended)", "B. The ledger misread the paper")
    kept, dropped = validated.build(ws)
    assert kept == [] and {d["item"]: d["reason"] for d in dropped} == {item: "you marked it not a problem or misread"}


# --- Task 5: the producer, the checker, and the fingerprint line ---

LESSON_LINES = ("The contracts in `skills/review/shared/contracts.md` bind you.",
                "The works named in this file are background for you. Cite one in your output only if you fetched "
                "it in this run; otherwise state the concern without the citation.")
LEDGER_AGENTS = ("hypothesis-ledger-producer.md", "hypothesis-ledger-checker.md")
ENUMS = (
    "`directional`", "`null`", "`difference`", "`interaction`", "`curvilinear`", "`mediation`",
    "`moderated mediation`", "`research question`", "`other`",
    "`strengthens | weakens | reverses | substitutes | complements | other`",
    "`inverted U | U | diminishing returns | increasing returns | other`", "`larger in: <group>`",
    "`full | partial | unspecified`", "`from estimate`", "`yes`", "`unknown`",
    "`main effect | moderator main effect | product term | squared term | linear term of curve | indirect effect | "
    "direct effect | index of moderated mediation | difference test | subsample estimate | pooled estimate | "
    "meta-regression coefficient | figure | other`",
    "`positive | negative | not negative | not positive | none`", "`linear | logit or probit | count | hazard | other`",
    "`indirect effect with interval | Sobel test | causal steps only | index of moderated mediation | other`",
    "`coefficient | ratio | correlation | standardized`", "`printed estimate`", "`another number`", "`unstated`",
    "`supported | marginally supported | partially supported | not supported | mixed | none stated`",
    "`cited tests`", "`abstract | introduction | theory | methods | results | discussion | appendix`",
    "`none | exploratory | post hoc`", "`hypotheses` or `none`")
FOCAL_ROWS = (
    "| directional | main effect, pooled estimate, meta-regression coefficient |",
    "| interaction | product term |", "| curvilinear | squared term |", "| mediation | indirect effect |",
    "| moderated mediation | index of moderated mediation |", "| difference | difference test |",
    "| null | main effect | none |", "| research question, other | none | none |")


def _agent(name):
    return _read(AGENTS / name)


def test_fingerprint_has_the_hypotheses_line():
    text = _agent("manuscript-audit.md")
    template = text.split("# Fingerprint\n", 1)[1].split("```", 1)[0]
    assert ("Contribution type: <type>\nHypotheses: <the labels as the paper numbers them, for example "
            "\"H1-H6, H3a, H3b\">, or \"none\"\n") in template
    definition = ("List every statement the paper tests on data it analyzes as a hypothesis, whatever it calls it "
                  "(hypothesis, proposition, prediction, research question). Propositions a theory paper derives, "
                  "propositions a qualitative study generates and does not test, and results of a simulation model "
                  "are not listed. When the paper states no hypotheses, write 'none'.")
    assert text.count(definition) == 1
    assert text.index(definition) < text.index("Under `Inference:`, list the estimates")
    assert "tested on data:" not in text and "**Hypothesis Framing Inventory:**" in text


@pytest.mark.parametrize("name", LEDGER_AGENTS)
def test_ledger_agents_follow_the_lessons(name):
    text = _agent(name)
    front = text.split("---", 2)[1]
    for key in ("name:", "description:", "maxTurns: 30", "tools: [Read, Write]"):
        assert key in front, key
    for s in LESSON_LINES + ("The orchestrator will provide `PDF_PATH`, `PAGE_COUNT`, `{WORKSPACE}`, and `{PLUGIN}`.",
                             "with the file-writing tool", "stage-1/hypothesis_ledger.json",
                             "Search the methods section, the results, every table and figure, the appendices, and "
                             "the footnotes"):
        assert s in text, s
    assert text.count("If the file is missing") + text.count("If it is missing") + text.count("is missing or") >= 3
    assert "\u2014" not in text and not re.search(r"(cat|echo|printf|tee)[^\n`]*>", text)


@pytest.mark.parametrize("name", LEDGER_AGENTS)
def test_ledger_agents_define_every_enum_and_the_focal_table(name):
    text = _agent(name)
    for s in ENUMS + FOCAL_ROWS:
        assert s in text, s
    assert "flipped once more when `moderator_note` is not empty" in text
    assert "a hypothesis that an effect is stronger in one group, tested only by split samples, is `difference`" in text


def test_producer_writes_unverified_and_the_checker_signs_off():
    producer, checker = _agent("hypothesis-ledger-producer.md"), _agent("hypothesis-ledger-checker.md")
    assert 'with `"verified": false` and `"checker_signoff": ""`' in producer
    assert "Reply to the orchestrator in one sentence with the number of rows and the number of rows with no test." \
        in producer
    assert "## Hypotheses and their tests" in producer and "The checker rewrites it." in producer
    for text in (producer, checker):
        assert "never an F or chi-square" in text and "a t or z printed there goes in `t`" in text
    for s in ("- `expected_sign` on the model's scale.", "- For interactions: `base_sign`, `shape`, and "
              "`moderator_note`.", "- Which test the verdict cites, and which is focal.",
              "- Whether a hypothesis has any test at all.", "- `type` `null`.", "- What the parentheses hold.",
              "Fill every estimate from `extracted_tables/`, never from the text",
              "stage-1/hypothesis_ledger_disputes.md", "Set `\"verified\": true` and `checker_signoff`",
              "Re-derive only these rows: <ids>", "Fill the estimates whose cells were written at the check-in; "
              "change nothing else.", "## Hypotheses and their tests",
              "H7 (interaction: slack weakens the negative effect of competition) -> Table 4, Model 3, Slack x "
              "Competition, -0.090 (0.030). The paper says: supported.", "H3 (directional, positive) -> no test found."):
        assert s in checker, s


# --- Task 6: Stage 1 builds the ledger and asks its questions ---

def _s1():
    return _read(STAGES / "stage-1-verify.md")


def test_stage_1_step_3_builds_the_ledger():
    step3 = _s1().split("\n3. ", 1)[1].split("\n4. ", 1)[0]
    for s in ("In parallel: dispatch `agents/numeric-fidelity.md`", "`agents/hypothesis-ledger-producer.md`",
              "`agents/hypothesis-ledger-checker.md`", "verify_hypothesis_ledger.py --skip", "`Hypotheses: none`",
              "At Standard and Deep", "At Quick, run the gate with `--allow-unverified`",
              "When the checker is not dispatched, the `--allow-unverified` pass is final",
              "\"Re-derive only these rows: <ids>\"", "once more with the gate report",
              "`{WORKSPACE}/stage-1/hypothesis_ledger.failed.json`", "and skip the script, the mapping check, and "
              "Stage 4's hypothesis audit", "check_hypotheses.py {WORKSPACE}/stage-1/hypothesis_ledger.json "
              "{WORKSPACE}/stage-1/hypothesis_checks.md --json {WORKSPACE}/stage-1/hypothesis_checks.json",
              '"check":"hypothesis_ledger_advisory"', '"check":"hypothesis_checks"', '"verdict":"SKIPPED"'):
        assert s in step3, s
    assert step3.count("once more with the gate report") == 1


def test_stage_1_round_1_refills_the_ledger():
    assert ("Also DISPATCH `agents/hypothesis-ledger-checker.md` again when `stage-1/hypothesis_checks.md` lists "
            "under `## Not computed` a written cell or a cell of a table copied in at round 1, with \"Fill the "
            "estimates whose cells were written at the check-in; change nothing else.\"") in _s1()


def test_stage_1_round_2_mapping_and_flags():
    text = _s1()
    mapping = text.index("Round 2 starts with the mapping check")
    assert mapping < text.index("   - Round 2, each discrepancy")
    for s in ("Item id `numbers:hyp:mapping`", "\"A. The mapping is right (Recommended)\"", "\"B. Correct a line\"",
              "The mapping check has no record in `flags.json`.", "take A and record it with `--note auto`",
              "`numbers:hyp:<hypothesis id>:<check>`", "\"B. The ledger misread the paper\"",
              "for a `numbers:hyp:*` item, \"B. The ledger misread the paper\".",
              "rewrite the `numbers:hyp:` records in `flags.json`"):
        assert s in text, s


def test_stage_1_resume_replays_mapping_and_hyp_flags():
    resume = _s1().split("\nResume.", 1)[1]
    assert "Replay `numbers:hyp:mapping` first" in resume
    assert "Drop again each `numbers:hyp:*` flag answered B as well." in resume


# --- Task 7: the Stage 4 hypothesis audit ---

ACTIVE = ["HL1", "HL2", "HL3", "HL4", "HL5", "HL7", "HL8", "HL9", "HL10", "HL11", "HL12", "HL13", "HL14", "HL15"]
RULES = (
    "1. \"The issue is 'Undermines the main claim' in three cases, and only these, all on the main hypothesis. (a) "
    "HL3: the hypothesis is called supported and every reading of every focal cited test's p-value lies above the "
    "largest threshold the paper uses. (b) HL5: the hypothesis is called supported and every focal cited estimate has "
    "the sign opposite to the one it predicts on the model's scale. (c) HL9: the hypothesis is called supported and "
    "the product term's sign contradicts the stated shape, or no model the paper shows includes the product term.\"",
    "2. \"Any other issue on the main hypothesis is 'Weakens a claim'. A verdict that cites a coefficient other than "
    "the product term while a product term with a supportive sign sits in the same table is 'Minor'. In a logit or "
    "probit model, HL9 findings are at most 'Weakens a claim' and say that the sign is read on the model's index "
    "scale.\"",
    "3. \"On other hypotheses, findings are capped at 'Weakens a claim'. An HL3 mismatch that does not change which "
    "hypotheses the text calls supported (for example 'p < .01' claimed where p < .05 holds, or a mark at a looser "
    "level than the verdict needs) is 'Minor'.\"",
    "4. \"HL1 is 'Weakens a claim'; it is 'Minor' when the paper says the hypothesis is not tested and why. HL2 is "
    "'Weakens a claim' when an unhypothesized result appears in the abstract or conclusion as a finding of the theory. "
    "An unhypothesized result anywhere else, and a result labeled exploratory or post hoc, is not a finding.\"",
    "5. \"HL4, HL12, HL13, and HL14 are 'Minor', except: HL4 is 'Weakens a claim' when the designated test fails and "
    "only another test passes; HL12 is 'Weakens a claim' when a hypothesis's direction differs between two statements "
    "and the later statement matches the estimate; HL14 is 'Weakens a claim' when the test's outcome is a different "
    "construct from the hypothesis's outcome and the paper states no link. A proxy the paper argues for, even weakly, "
    "is not an HL14 finding. These findings report the mismatch and never state or imply why it arose.\"",
    "6. \"HL7 is 'Weakens a claim'; it is 'Minor' when the paper reads the same result correctly elsewhere in the "
    "text.\"",
    "7. \"HL15 is 'Minor' when the only failing test is one the paper's robustness sentence names, unless it is the "
    "designated test or the main hypothesis's only focal test; otherwise the general rules apply.\"",
    "8. \"Findings the ledger raises only because no owner runs (HL8, HL10, HL11) are capped at 'Weakens a claim'. HL8 "
    "is 'Minor' when the ledger's own difference facts show the difference is distinguishable from zero at the "
    "paper's level.\"",
    "9. \"A finding that only notes a missing report is written once per check per paper, listing every hypothesis it "
    "applies to.\"")


def _audit():
    return _read(AGENTS / "hypothesis-audit.md")


def test_audit_agent_follows_the_lessons():
    text = _audit()
    front = text.split("---", 2)[1]
    for key in ("name:", "description:", "maxTurns: 30", "tools: [Read, Write]"):
        assert key in front, key
    for s in LESSON_LINES + (
            "The orchestrator will provide `PDF_PATH`, `PAGE_COUNT`, `{WORKSPACE}`, and `{PLUGIN}`.",
            "{WORKSPACE}/stage-4/hypothesis_audit.md", "with the file-writing tool",
            "Check: <HL-id>. Unit: Hypothesis <id>. Tag: [paper | external | judgment]", "Paper's best case:",
            "Excerpt: \"<one sentence copied word for word from the paper where the problem shows>\"",
            "Page: <the page the paper prints there; for something missing, the page of the section where it belongs>",
            "Severity: <Undermines the main claim | Weakens a claim | Minor>", "What would settle it:",
            "## Checked and fine", "If there are no issues, write \"None.\" under \"## Issues\".",
            "Flag an absence only after searching the methods section, the results, the appendices, the footnotes, "
            "and every table and figure, and name where you looked.",
            "Never predict the result of an analysis you suggest.",
            "Definitions, for when you find them yourself:", "`{WORKSPACE}/stage-1/dropped_flags.md`",
            "`{WORKSPACE}/stage-2/construction_ledger.json`", "`{PLUGIN}/skills/review/checklists/hypotheses.yaml`"):
        assert s in text, s
    assert text.count("If the file is missing") + text.count("If it is missing") + text.count("If either is missing") >= 6
    assert "\u2014" not in text and not re.search(r"(cat|echo|printf|tee)[^\n`]*>", text)
    assert "search the web" not in text.lower() and "Pack:" not in text


def test_audit_carries_the_nine_severity_rules():
    text = _audit()
    for rule in RULES:
        assert text.count(rule) == 1, rule[:40]
    assert "Each sets a level; none shifts one." in text


def test_audit_reads_run_json_packs_once_and_names_owners():
    text = _audit()
    assert "read `packs` once, when you start, and decide the three fallbacks below from it then; do not read it again" \
        in text
    owners = text.split("## Who owns the fallbacks", 1)[1].split("\n## ", 1)[0]
    assert ("HL8 runs here only when none of `nonlinear`, `inference`, `archival`, `experiments`, `meta-analysis` is "
            "in `packs`.") in owners
    assert "HL10 runs here only when `nonlinear` is not in `packs`." in owners
    assert "HL11 runs here only when neither `survey` nor `experiments` is in `packs`." in owners
    assert "archival" not in owners.split("HL11 runs here", 1)[1]
    assert "The moderated-mediation part (an index of moderated mediation or an equivalent test) runs here on every "\
        "run; no pack owns it." in owners
    assert "when `configurational` is in `packs`, a hypothesis the paper tests, or says it tests, with a qualitative "\
        "comparative analysis" in owners
    assert "A `numbers:hyp:*` item listed there is not raised" in text
    assert "draws no issue built on its Stage 1 flag" in text


def test_every_active_id_has_a_protocol_heading():
    ids = [i["id"] for i in yaml.safe_load(_read(SKILL / "checklists" / "hypotheses.yaml"))]
    assert ids == ACTIVE
    body = re.sub(r"```.*?```", "", _audit(), flags=re.S).split("## Protocol", 1)[1]
    assert re.findall(r"^### (HL\d+)\. ", body, re.M) == ACTIVE
    for i in ("HL3", "HL5", "HL7", "HL9", "HL15"):
        section = body.split(f"### {i}. ", 1)[1].split("\n### ", 1)[0]
        assert f"`numbers:hyp:<id>:{i}`" in section and "cite its item id" in section, i


# --- Task 8: Stage 2, Stage 4, synthesis, and the core agents that read the ledger ---

VERDICT_SKIP = ("Skip a sentence that gives a verdict on a numbered hypothesis (it names a hypothesis and says "
                "supported, not supported, partially supported, or consistent with); the hypothesis ledger checks "
                "those.")


def test_stage_2_copies_the_mapping_outside_the_cap():
    step3 = _read(STAGES / "stage-2-understand.md").split("\n3. ", 1)[1].split("\n4. ", 1)[0]
    assert ("copy that block after the summary, for reference only; it does not count toward the cap either") in step3
    assert "\"Hypotheses and their tests\"" in step3


def test_stage_4_dispatches_the_audit_and_merges_by_hypothesis():
    s4 = _read(STAGES / "stage-4-diagnose.md")
    step1 = s4.split("1. In parallel:", 1)[1].split("\n2. ", 1)[0]
    assert ("   - `agents/hypothesis-audit.md`, unless `stage-1/hypothesis_ledger.json` is missing (the ledger was "
            "skipped at Stage 1 or quarantined as `hypothesis_ledger.failed.json`) or its `mode` is `none`") in step1
    assert "about the same variable, term, table, or hypothesis, write one issue" in s4


def test_synthesis_reads_hypothesis_checks():
    text = _read(AGENTS / "synthesis.md")
    assert "`{WORKSPACE}/stage-1/hypothesis_checks.md`" in text
    assert "`{WORKSPACE}/stage-4/hypothesis_audit.md` (if it exists)" in text
    assert "say in one plain sentence that the hypothesis checks did not run" in text


def test_numeric_fidelity_leaves_verdict_sentences():
    text = _read(AGENTS / "numeric-fidelity.md")
    for head, nxt in (("### Check A6: ", "### Check A7: "), ("### Pass B3: ", "### Pass B4: ")):
        assert VERDICT_SKIP in text.split(head, 1)[1].split(nxt, 1)[0], head


def test_core_readers_use_the_ledger():
    audit4 = _read(AGENTS / "formal-model.md").split("### Audit 4: ", 1)[1].split("### Audit 5: ", 1)[0]
    assert "`{WORKSPACE}/stage-1/hypothesis_ledger.json`" in audit4 and "Hypothesis Framing Inventory" in audit4
    assert ("A stated hypothesis with no test is the hypothesis audit's (HL1); do not raise it. Keep predictions the "
            "argument map derives that the paper does not state as hypotheses.") in _read(AGENTS / "completeness.md")
    for name in ("skeptical-reviewer.md", "face-validity.md"):
        text = _read(AGENTS / name)
        assert "`{WORKSPACE}/stage-1/hypothesis_ledger.json`" in text and "`carries_main_result: true`" in text, name



# --- Task 9: the inference pack reads the ledger ---

def _pack_agent(pack, name):
    return _read(ROOT / "packs" / pack / "agents" / name)


FOCAL_DEF = ("A ledger test is focal when its `term_kind` fits its row's `type`: a main effect, pooled estimate, or "
             "meta-regression coefficient for a directional or null row; the product term for an interaction; the "
             "squared term for a curve; the indirect effect for mediation; the index of moderated mediation; the "
             "difference test for a difference row.")


def test_inference_numbers_leaves_ledger_verdicts():
    text = _pack_agent("inference", "inference-numbers.md")
    assert FOCAL_DEF in text
    assert "When the ledger exists, take the columns a hypothesis rests on from its focal tests." in text
    assert ("leave out a sentence whose `table` and `cells` match a focal test that a ledger verdict cites "
            "(`verdict_cites`); match by cells") in text
    assert "take `directional` (true when the test's `expected_sign` is positive or negative) and `tails` from the ledger" \
        in text


def test_inference_claims_hands_verdicts_to_the_audit():
    text = _pack_agent("inference", "inference-claims.md")
    i13 = text.split("### I13. ", 1)[1].split("### I14. ", 1)[0]
    assert ("A verdict on a hypothesis whose focal test is in `stage-1/hypothesis_ledger.json` belongs to the core "
            "hypothesis audit; do not raise it. Keep tails, 'marginally significant' wording, recomputability, and "
            "marks from another test for those sentences too.") in i13
    assert "For rule 1(c), the main result's p interval must lie entirely above" in i13
    i16 = text.split("### I16. ", 1)[1].split("### Exclusions", 1)[0]
    assert ("When `nonlinear` is not in `run.json` `packs`, add the ledger's `difference` rows, with their subsample "
            "estimates, to the comparisons you check; when it is, leave them to the nonlinear pack.") in i16
    assert FOCAL_DEF in text
    assert "{WORKSPACE}/stage-1/hypothesis_checks.md" in text
    assert ("Read `{WORKSPACE}/stage-1/hypothesis_checks.md` when it exists. A hypothesis row listed under "
            "`## Not computed` with the reason \"the readings straddle\" is a verdict that holds only on one tail "
            "reading; the tails point for it is yours. When the paper states no tails for that verdict, say so and "
            "ask the paper to state its tails, rated as any other undeclared one-tailed test.") in i13
    assert "stage-1/hypothesis_checks.md" in text.split("### I13. ", 1)[0]


def test_stage_1_quick_path_says_what_exit_2_means():
    text = _read(STAGES / "stage-1-verify.md")
    quick = text.split("   - At Quick,", 1)[1].split("\n   - ", 1)[0]
    assert "exits 2" in quick
    assert "hypothesis checks did not run" in quick



# --- Task 10: the nonlinear pack reads the ledger ---

def test_nonlinear_numbers_takes_the_curve_claim_from_the_ledger():
    text = _pack_agent("nonlinear", "nonlinear-numbers.md")
    assert ("set `claim` from its `shape`: \"monotone\" for diminishing returns or increasing returns, and reversal "
            "for every other shape") in text
    assert "build a `difference` record for each `difference` row of the ledger whose comparison is not listed" in text
    assert "{WORKSPACE}/stage-1/hypothesis_ledger.json" in text


def test_nonlinear_claims_leaves_the_product_sign_to_hl9():
    n4 = _pack_agent("nonlinear", "nonlinear-claims.md").split("### N4. ", 1)[1].split("### N5. ", 1)[0]
    assert "Read the hypothesis's direction from the ledger's `shape` and `base_sign`" in n4
    assert "Whether the product term's sign fits that shape is the core hypothesis audit's (HL9); do not raise it." in n4
    n1 = _pack_agent("nonlinear", "nonlinear-claims.md").split("### N1. ", 1)[1].split("\n### ", 1)[0]
    assert ("A squared term whose sign contradicts the hypothesized shape is the core hypothesis audit's (HL5); do "
            "not raise it.") in n1



# --- Task 11: archival hands null framing to the ledger and reads its mediation rows ---

def test_triangulation_hands_null_framing_to_the_ledger():
    text = _pack_agent("archival", "triangulation.md")
    assert "Hypothesis framing consistency (mandatory check)" not in text
    assert "| Hypothesis framing consistency |" not in text
    assert ("**Hypothesis framing:** the core hypothesis ledger checks null-hypothesis framing on every run (its HL7); "
            "do not check it here.") in text
    assert ("When `nonlinear` is in `run.json` `packs`, leave comparisons of split samples within one study to the "
            "nonlinear pack; keep comparisons across studies.") in text
    assert "`{WORKSPACE}/stage-1/hypothesis_ledger.json`" in text and "**Run record:** `{WORKSPACE}/run.json`" in text
    assert "**Difference-in-significance error in heterogeneity results (mandatory check):**" in text


def test_archival_mediation_reads_evidence_kind():
    block = _pack_agent("archival", "methods-checks.md").split("#### If Mediation Analysis:", 1)[1].split("\n#### ", 1)[0]
    assert "- **The ledger's mediation rows:** when `{WORKSPACE}/stage-1/hypothesis_ledger.json` exists" in block
    assert "`evidence_kind`" in block and "Keep identification and causal wording." in block



# --- Task 12: survey S17 and meta-analysis M15 and M16 read the ledger ---

def test_survey_and_meta_analysis_read_the_ledger():
    s17 = _pack_agent("survey", "claims-and-controls.md").split("### S17. ", 1)[1].split("\n## ", 1)[0]
    assert "`{WORKSPACE}/stage-1/hypothesis_ledger.json` and each test's `evidence_kind`" in s17
    ma = _pack_agent("meta-analysis", "synthesis-claims.md")
    m15 = ma.split("### M15. ", 1)[1].split("### M16. ", 1)[0]
    m16 = ma.split("### M16. ", 1)[1].split("### M17. ", 1)[0]
    assert "Check the ledger's `difference` rows as moderator claims" in m15
    assert "read the ledger's `mediation` rows and each test's `evidence_kind`" in m16
    assert "- `{WORKSPACE}/stage-1/hypothesis_ledger.json`, if it exists:" in ma



# --- Task 13: the experiments pack's notes to its own agents ---

EXP_CROSS = ("The core hypothesis ledger checks null-hypothesis framing on every run (its HL7). Skip 'Hypothesis framing "
             "consistency (mandatory check)' and leave its row out of your table. Read the difference rows of "
             "`{WORKSPACE}/stage-1/hypothesis_ledger.json` as comparisons to check; if the file is missing, work as "
             "before. When `nonlinear` is in `run.json` `packs`, leave the ledger's difference rows within one study to "
             "the nonlinear pack, whether or not they are listed under `Nonlinear terms:`; keep comparisons across "
             "studies.")
EXP_METHODS = ("In CHECK 9, read `evidence_kind` for each mediation row of `{WORKSPACE}/stage-1/hypothesis_ledger.json` "
               "as the list of mediation claims to check; if the file is missing, work as before. Also flag full "
               "mediation claimed because the direct effect lost significance; a non-significant direct effect is "
               "not evidence of none (checklist item E13).")


def test_experiments_notes_hand_framing_to_the_ledger():
    notes = packs.load_pack(ROOT / "packs" / "experiments").core_notes
    own = "packs/experiments/agents/"
    assert notes[own + "cross-study-consistency.md"][-1] == EXP_CROSS
    assert notes[own + "methods-checks.md"][-1] == EXP_METHODS
    author_agent = _pack_agent("experiments", "cross-study-consistency.md")
    assert author_agent.count("**Hypothesis framing consistency (mandatory check):**") == 1
    assert _pack_agent("experiments", "methods-checks.md").count("### CHECK 9: ") == 1
    got = packs.core_adjust(packs.load_all(ROOT / "packs"), {"packs": ["experiments"], "overlays": [],
                                                             "types_without_pack": [], "primary_pack": "experiments"})
    assert any(n["text"] == EXP_CROSS for n in got["notes"][own + "cross-study-consistency.md"])


# --- Fix round 4-6: a missing table, blank-cell addresses, quarantine rename, exit 2 ---

MISSING_TABLE = "If a table a test needs is missing from `extracted_tables/` while others are there"
BLANK_ADDRESS = "Give each blank cell its address in `cells`"


@pytest.mark.parametrize("name", ["hypothesis-ledger-producer.md", "hypothesis-ledger-checker.md"])
def test_ledger_agents_do_not_read_a_missing_table_from_the_pdf(name):
    text = _read(AGENTS / name)
    assert MISSING_TABLE in text
    assert "do not read it from the PDF" in text
    assert "under `## Not computed`" in text
    assert BLANK_ADDRESS in text
    assert "`<table>:<row>:<col>` of each cell it would need" in text


def test_producer_writes_not_computed_in_the_readable_copy():
    text = _read(AGENTS / "hypothesis-ledger-producer.md")
    assert "a `## Not computed` section" in text.split("## Output", 1)[1]


def test_quarantine_renames_the_readable_copy_and_exit_2_is_explained():
    s1 = _read(STAGES / "stage-1-verify.md")
    assert ("rename the ledger to `{WORKSPACE}/stage-1/hypothesis_ledger.failed.json` and the readable copy to "
            "`{WORKSPACE}/stage-1/hypothesis_ledger.failed.md`") in s1
    assert "`check_hypotheses.py` exits 2 when it cannot read the ledger" in s1
    assert "record it under the check-in's not-computed list" in s1
    assert "do not stop the review" in s1


# --- Task 15: README and repo spec (post-1e item 19) ---

def test_readme_and_spec_name_the_hypothesis_ledger():
    readme = _read(ROOT / "README.md")
    assert ("On every paper that states hypotheses, Plumb maps each hypothesis to the test the paper offers for it and "
            "shows you that mapping at the numbers check-in.") in readme
    spec = _read(ROOT / "docs" / "spec.md")
    assert "hypothesis ledger, which maps each hypothesis to its test (`check_hypotheses.py`)" in spec


def test_ledger_agents_record_printed_df():
    root = Path(__file__).resolve().parents[1] / "skills" / "review" / "agents"
    prod = (root / "hypothesis-ledger-producer.md").read_text(encoding="utf-8")
    chk = (root / "hypothesis-ledger-checker.md").read_text(encoding="utf-8")
    assert "`df` (the degrees of freedom the paper prints for that test's t statistic" in prod
    assert "`df` (the printed degrees of freedom for that test's t statistic" in chk


# --- Final fix wave A: declined items and the mapping check on resume ---

def test_audit_lists_the_hyp_items_it_declines():
    text = _audit().split("## Output", 1)[1]
    assert "list each `numbers:hyp:` item you examined and did not raise" in text
    assert "- Declined `<item id>`: <reason>" in text


def test_synthesis_treats_a_declined_item_as_picked_up():
    text = _read(AGENTS / "synthesis.md")
    assert ("a flag whose item id `hypothesis_audit.md` lists as declined under \"Checked and fine\" counts as "
            "picked up") in text


def test_resume_leaves_the_mapping_check_out_of_dropped_flags():
    resume = _s1().split("\nResume.", 1)[1]
    assert ("`dropped_flags.md` from the round 2 items answered B or C (never `numbers:hyp:mapping`, which is not a "
            "flag)") in resume
