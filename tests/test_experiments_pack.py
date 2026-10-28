from __future__ import annotations
import hashlib
import re
import sys
from pathlib import Path

import pytest
import yaml

from plumb import packs

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "review"
PACK = ROOT / "packs" / "experiments"
IDS = [f"E{i}" for i in range(1, 16)]
# sha256 of each file as its author committed it (the experiments-pack branch, 9223fcc).
AUTHOR = {
    "agents/alternative-explanations.md": "58b208ccf0f548797b00c42daac5f10fd29958348ad475218b6ac886ec2d2d05",
    "agents/cross-study-consistency.md": "fff25044944c4a7aa0334d84353ba96a1916d3ca44730e18149201edd33e96c1",
    "agents/mechanism-isolation.md": "1cc3daddaa8036c2cd6d19d5b73283a09792a5d7fe10bfb1ca657218689cd559",
    "agents/methods-checks.md": "391221229dec10e76ad5b815573a61a4e53464a6b4a415e55f7a061e1e094ac0",
    "agents/sample-and-materials.md": "ab54082765893081961654a183ab8a3af477f7bff09c7993f6562bf6b6048a77",
    "checklists/experiments.yaml": "b297885fd3e247010253966c2501343f59c2232caddbbb167c75e580708e3b09",
}
EM_DASH = chr(0x2014)
SLOTS = {"context": ["sample-and-materials.md"], "theory": ["mechanism-isolation.md"],
         "diagnose": ["methods-checks.md", "alternative-explanations.md", "cross-study-consistency.md"]}


def _pack():
    return packs.load_pack(PACK)


def _built():
    return packs.load_all(ROOT / "packs")


def _run(names, overlays=(), missing=(), primary="first"):
    return {"packs": list(names) + list(overlays), "overlays": list(overlays), "types_without_pack": list(missing),
            "primary_pack": names[0] if primary == "first" else primary}


def _agent(name):
    return (PACK / "agents" / name).read_text(encoding="utf-8")


def _other(pack, name):
    return (ROOT / "packs" / pack / "agents" / name).read_text(encoding="utf-8")


# --- Task 1: the author's pack on the chain ---

def test_author_files_are_verbatim():
    for rel, digest in AUTHOR.items():
        assert hashlib.sha256((PACK / rel).read_bytes()).hexdigest() == digest, rel


def test_pack_loads_as_a_type_pack():
    p = _pack()
    assert p.name == "experiments" and p.overlay is False
    assert [i["id"] for i in p.checklist] == IDS
    assert p.slots == SLOTS


# --- Task 2: the pack's fields for the chain ---

AUTHOR_RULES = [
    "For theory-testing papers, a manipulation confounded with another construct that could produce the main effect "
    "by itself is 'Undermines the main claim'.",
    "A measured mediator meets the field's standard. A mechanism claim is weakened only when a specific, plausible "
    "rival would move the same mediator and the paper does not address it. Then it is 'Weakens a claim' if the "
    "mechanism is central, and 'Minor' otherwise.",
    "An underpowered focal study is 'Weakens a claim' unless it is the paper's only evidence for the main claim.",
    "For phenomenon-driven papers, demands for mechanism isolation are downgraded one level.",
]
ASSIGNED = "assigned at random by a stated procedure, by the researchers or an organization working with them"
ARCHIVAL_AGENTS = ("methods-checks.md", "adversarial-dgp.md", "mechanism-discrimination.md", "triangulation.md")


def test_author_rules_come_first_and_are_verbatim():
    rules = _pack().severity_rules
    assert rules[:4] == AUTHOR_RULES and len(rules) == 7
    for r in rules[4:]:
        assert "one level" not in r and "downgrade" not in r and EM_DASH not in r


def test_exclusion_rule_is_graded():
    rule = _pack().severity_rules[4]
    assert rule.startswith("Exclusions of participants on a measure the treatment could affect")
    for s in ("take-up or compliance, or a per-protocol sample",
              "no finding when the paper reports the estimate without the exclusion, on everyone assigned who has an "
              "outcome, and that estimate supports the claim.",
              "'Minor' when counts by condition are reported and similar and that estimate is not shown.",
              "'Weakens a claim' when counts by condition are missing or differ.",
              "'Undermines the main claim' only when the counts differ, the study carries the main claim, and that "
              "estimate is absent.",
              "A study carries the main claim when the main hypothesis rests on it and no other study in the paper "
              "supports the same hypothesis free of the same problem."):
        assert s in rule, s
    assert "when outcomes are missing, on everyone with an outcome" not in rule


def test_dropout_is_rated_apart_from_exclusions():
    rule = _pack().severity_rules[4]
    assert ("Dropout that leaves outcomes missing is 'Minor' when counts by condition are reported and similar, and "
            "'Weakens a claim' when they are missing or differ and the paper reports no bounds or sensitivity analysis "
            "for the missing outcomes.") in rule


def test_automatic_patterns_are_scoped_to_the_main_claim():
    rule = _pack().severity_rules[6]
    assert rule.startswith("The experiments methods agent's automatic high-severity patterns (its CHECK 12b) are "
                           "'Undermines the main claim' only when the study carries the main claim (as the exclusions "
                           "rule defines it) and the pattern bears on the main hypothesis;")
    assert ("the registered primary outcome is not reported or does not support the claim. Otherwise each is 'Weakens "
            "a claim'.") in rule
    assert _agent("methods-checks.md").count("### CHECK 12b: ") == 1


def test_encouragement_rule_matches_the_iv_module():
    rule = _pack().severity_rules[5]
    iv = yaml.safe_load((ROOT / "packs" / "archival" / "modules" / "iv.yaml").read_text(encoding="utf-8"))
    assert "(" + ", ".join(iv["encouragement"]) + ")" in rule
    assert "'Undermines the main claim' only for IV1 with IV2 in the cases the module states" in rule
    assert "never judged as conditioning on a post-treatment variable" in rule
    assert "`IV (encouragement)`" in rule


def test_timeline_is_off_only_when_every_type_pack_is_experiments():
    built = _built()
    off = packs.core_adjust(built, _run(["experiments"]))["off"]
    assert set(off) == {"timeline-research.md"}
    assert off["timeline-research.md"]["reason"] == (
        "Turned off by the experiments pack: the treatment was assigned at random by a stated procedure")
    assert set(packs.core_adjust(built, _run(["experiments"], overlays=["inference", "nonlinear"]))["off"]) == {
        "timeline-research.md"}
    assert packs.core_adjust(built, _run(["experiments", "archival"]))["off"] == {}
    assert packs.core_adjust(built, _run(["archival", "experiments"]))["off"] == {}
    assert packs.core_adjust(built, _run(["experiments"], missing=["other"]))["off"] == {}


def test_read_checkin_shows_designs():
    assert _pack().read_checkin_lines == ["Designs:"]
    assert packs.core_adjust(_built(), _run(["experiments"]))["read_lines"]["experiments"] == ["Designs:"]


def test_notes_to_other_packs_reach_them_only_when_they_run():
    built = _built()
    alone = packs.core_adjust(built, _run(["experiments"]))["notes"]
    assert not any(k.startswith(("packs/inference/", "packs/archival/", "packs/survey/")) for k in alone)
    inf = packs.core_adjust(built, _run(["experiments"], overlays=["inference"]))["notes"]
    got = [n for n in inf["packs/inference/agents/inference-claims.md"] if n["pack"] == "experiments"]
    assert len(got) == 1 and got[0]["role"] == "primary type"
    for order in (["experiments", "archival"], ["archival", "experiments"]):
        both = packs.core_adjust(built, _run(order))["notes"]
        for a in ARCHIVAL_AGENTS:
            got = [n for n in both[f"packs/archival/agents/{a}"] if n["pack"] == "experiments"]
            assert len(got) == 1 and ASSIGNED in got[0]["text"], a
            assert "variation not assigned that way" in got[0]["text"], a


def test_cluster_randomized_designs_have_one_owner_of_the_treated_count():
    built = _built()
    inf = packs.core_adjust(built, _run(["experiments"], overlays=["inference"]))["notes"]
    got = [n for n in inf["packs/inference/agents/inference-dependence.md"] if n["pack"] == "experiments"]
    assert len(got) == 1
    assert "skip I4 as well as I3 and I9" in got[0]["text"]
    assert "the experiments pack's methods agent owns the number of treated clusters" in got[0]["text"]
    assert ("Keep I1 for randomized comparisons (the experiments pack leaves the clustering level to you), and keep "
            "every check for estimates from variation not assigned that way.") in got[0]["text"]
    assert "Keep I1 and the other checks" not in got[0]["text"]
    dependence = _other("inference", "inference-dependence.md")
    for h in ("### I3. ", "### I4. ", "### I9. "):
        assert dependence.count(h) == 1, h
    alone = packs.core_adjust(built, _run(["experiments"]))["notes"]
    assert "packs/inference/agents/inference-dependence.md" not in alone


def test_survey_mirror_note_holds_in_either_order():
    built = _built()
    for order in (["survey", "experiments"], ["experiments", "survey"]):
        notes = packs.core_adjust(built, _run(order))["notes"]["packs/survey/agents/claims-and-controls.md"]
        got = [n for n in notes if n["pack"] == "experiments"]
        assert len(got) == 1 and got[0]["text"].startswith(
            "Apply S14 to S16 only to studies whose predictor was measured, not assigned, whatever the order of the "
            "packs in `run.json` `packs`"), order
    survey = _other("survey", "claims-and-controls.md")
    for h in ("### S14. ", "### S15. ", "### S16. "):
        assert survey.count(h) == 1, h


SURVEY_SPLIT = {
    "packs/survey/agents/psychometrics.md": ("skip S5, S6, and S7", ("### S5. ", "### S6. ", "### S7. ")),
    "packs/survey/agents/respondents-and-sources.md": ("skip S1", ("### S1. ",)),
}


def test_survey_measurement_checks_yield_randomized_measures_in_either_order():
    built = _built()
    for order in (["survey", "experiments"], ["experiments", "survey"]):
        notes = packs.core_adjust(built, _run(order))["notes"]
        for agent, (skip, heads) in SURVEY_SPLIT.items():
            got = [n for n in notes[agent] if n["pack"] == "experiments"]
            assert len(got) == 1, (order, agent)
            text = got[0]["text"]
            assert text.startswith("For the outcome and mediator scales in a randomized comparison (a treatment assigned "
                                   "at random by a stated "
                                   "procedure, by the researchers or an organization working with them)"), agent
            assert skip in text and "whatever the order of the packs in `run.json` `packs`" in text, agent
            assert "its CHECK 4 [E9] and CHECK 9 [E13]" in text, agent
            assert "for any study in the paper that assigns no treatment that way." in text, agent
            body = _other("survey", agent.rsplit("/", 1)[1])
            for h in heads:
                assert body.count(h) == 1, h
    methods = _agent("methods-checks.md")
    assert methods.count("### CHECK 4: Measures [E9]") == 1 and methods.count("### CHECK 9: Mediation [E13]") == 1
    alone = packs.core_adjust(built, _run(["experiments"]))["notes"]
    assert not any(a in alone for a in SURVEY_SPLIT)


def test_notes_to_other_packs_name_sections_that_exist():
    notes = _pack().core_notes
    claims = _other("inference", "inference-claims.md")
    for h in ("### I12. ", "### I13. ", "### I14. ", "### I15. ", "### I16. "):
        assert claims.count(h) == 1, h
    assert "skip I15 and I16 for them" in notes["packs/inference/agents/inference-claims.md"][0]
    methods = _other("archival", "methods-checks.md")
    assert methods.count("### CHECK 9: ") == 1 and methods.count("- **Vignette experiments:**") == 1
    assert "the vignette-experiment bullet in CHECK 9" in notes["packs/archival/agents/methods-checks.md"][0]
    assert "alternative-explanations agent" in notes["packs/archival/agents/adversarial-dgp.md"][0]
    assert "mechanism-isolation agent" in notes["packs/archival/agents/mechanism-discrimination.md"][0]
    assert "cross-study-consistency agent" in notes["packs/archival/agents/triangulation.md"][0]
    assert _other("archival", "triangulation.md").count("### Step 1: Catalog All Results") == 1


# --- Task 3: pack notes that fit the author's agents to the chain ---

OWN = "packs/experiments/agents/"
LEVELS = ("Write the rule's level in your Severity line as Low for 'Minor', Moderate for 'Weakens a claim', and High "
          "only for 'Undermines the main claim'.")


def _own(agent):
    return _pack().core_notes[OWN + agent]


def _owners(i):
    """Protocol headings that carry the id in brackets, or the pack's own notes that assign it (L17)."""
    heads = [a for a in SLOTS["diagnose"] + SLOTS["theory"]
             if re.search(rf"^###.*\[[^\]]*\b{i}\b", _agent(a), re.M)]
    notes = [k for k, v in _pack().core_notes.items() if k.startswith(OWN)
             for n in v if re.search(rf"(?:checklist item|[Cc]ite) {i}\b|\b{i} (?:for|when)\b", n)]
    return heads + notes


def test_own_notes_name_sections_that_exist():
    methods = _agent("methods-checks.md")
    for note in _own("methods-checks.md"):
        for n in re.findall(r"CHECK (\d+b?)", note):
            assert methods.count(f"### CHECK {n}: ") == 1, n
    assert methods.count("### Methods Summary") == 1
    alt = _agent("alternative-explanations.md")
    assert alt.count("**Category A: Confounded Manipulation**") == 1
    assert alt.count("**Category B: Demand Characteristics and Experimenter Effects**") == 1
    assert _agent("cross-study-consistency.md").count("**Difference-in-significance error (mandatory check):**") == 1


def test_cutoff_note_names_numbers_that_are_in_the_agent():
    methods = _agent("methods-checks.md")
    note = _own("methods-checks.md")[0]
    for s in ("fewer than about 30-50", "more than about 5 percentage points", "t between 2.0 and 2.5",
              "about 10-15 tasks"):
        assert s in note and s in methods, s
    assert "In CHECK 10, ask instead whether the paper checks how responses change across task order." in note


def test_severity_notes_quote_the_rules():
    rules = _pack().severity_rules
    notes = _own("methods-checks.md")
    assert rules[4] in notes[1] and LEVELS in notes[1]
    assert ("This rule governs every exclusion on a measure the treatment could affect, whatever the first automatic "
            "pattern of CHECK 12b says.") in notes[1]
    assert "use the attrition line of CHECK 2, without its number, only for dropout that leaves outcomes missing" in (
        notes[1])
    assert rules[6] in notes[2] and LEVELS in notes[2]
    assert rules[5] in notes[6] and LEVELS in notes[6]


def test_p_value_recipe_is_exact():
    sys.path.insert(0, str(SKILL / "scripts"))
    import pvalues
    note = _own("methods-checks.md")[3]
    assert "`pvalues._betai(df2 / 2, df1 / 2, df2 / (df2 + df1 * F))`" in note
    f_p = lambda f, d1, d2: pvalues._betai(d2 / 2, d1 / 2, d2 / (d2 + d1 * f))
    # Values recomputed with SciPy in the experiments grill (2026-09-28).
    assert abs(f_p(4.12, 1, 96) - 0.045146) < 5e-7
    assert abs(f_p(3.10, 2, 57) - 0.052723) < 5e-7
    assert abs(pvalues.p_student(2.00, 30) - 0.054625) < 5e-7
    assert abs(pvalues.p_normal(3.84 ** 0.5) - 0.050044) < 5e-7
    assert pvalues.printed_p_range("p = .000") == (0.0, 0.0005)
    for s in ("'p = .000' means below .0005", "Read a test as one-tailed only when the paper says so.",
              "subtract one for each covariate", "with the pooled SD, with the square root of the summed variances, "
              "and with the control group's SD"):
        assert s in note, s


def test_undeclared_one_tailed_tests_are_not_mismatches():
    note = _own("methods-checks.md")[3]
    assert ("record an undeclared one-tailed test under E6, at most 'Weakens a claim' and never an automatic "
            "high-severity pattern; when `inference` is in `run.json` `overlays`, leave it to that pack's I13.") in note
    assert "one-tailed tests for them" in _pack().core_notes["packs/inference/agents/inference-claims.md"][0]


def test_field_interventions_and_effect_sizes():
    notes = _own("methods-checks.md")
    assert notes[10].startswith("In CHECK 3, a missing manipulation check is a finding only for manipulations of "
                                "perceptions or psychological states.")
    assert "ask for treatment fidelity or take-up instead" in notes[10]
    assert notes[11].startswith("In CHECK 5 and CHECK 14, leave comparison with benchmarks from outside the paper to "
                                "the core face-validity agent;")
    assert ("In CHECK 14, a paper that reports an effect size with each focal test but does not discuss its magnitude "
            "is Low.") in notes[11]
    assert (SKILL / "agents" / "face-validity.md").is_file()


def test_encouragement_note_reads_the_iv_module():
    note = _own("methods-checks.md")[6]
    iv = yaml.safe_load((ROOT / "packs" / "archival" / "modules" / "iv.yaml").read_text(encoding="utf-8"))
    ids = [i for i in iv["encouragement"]]
    assert "`{PLUGIN}/packs/archival/modules/iv.md`" in note and "`IV (encouragement)`" in note
    assert re.findall(r"IV\d+", note.split(" That rule reads: ", 1)[0]) == ids
    assert "Ignore `IV (encouragement)`; the experiments pack handles it." in _other("archival", "design-checks.md")
    assert "The experiments pack reads this file" in (ROOT / "packs" / "archival" / "modules" / "iv.md").read_text(
        encoding="utf-8")


def test_gated_notes_mirror_the_other_packs():
    notes = _own("methods-checks.md")
    assert notes[7].startswith("Apply this note only when `inference` is in `run.json` `overlays`.")
    assert "When `experiments` is in `run.json` `packs`, skip I3 and I9 for randomized designs" in _other(
        "inference", "inference-dependence.md")
    assert "keep the number of clusters and the small-cluster correction, which that pack leaves to you" in notes[7]
    assert notes[8].startswith("Apply this note only when `survey` is in `run.json` `packs`.")
    assert "(its S11 and S14 to S17)" in notes[8]
    assert ("When `experiments` is in `run.json` `packs`, apply this check only to studies that assign nothing"
            in _other("survey", "respondents-and-sources.md"))
    assert "apply S17 only to mediations whose predictor was measured, not manipulated" in _other(
        "survey", "claims-and-controls.md")
    assert notes[9].startswith("Apply this note only when `nonlinear` is in `run.json` `overlays`.")
    assert _own("cross-study-consistency.md")[0].startswith(
        "Apply this note only when `nonlinear` is in `run.json` `overlays`.")
    assert "When `experiments` is in `run.json` `packs`, skip randomized designs" in _other(
        "inference", "inference-claims.md")


def test_core_adjust_delivers_own_notes_with_the_role():
    built = _built()
    primary = packs.core_adjust(built, _run(["experiments"]))["notes"]
    assert len(primary[OWN + "methods-checks.md"]) == 13
    assert {n["role"] for n in primary[OWN + "methods-checks.md"]} == {"primary type"}
    second = packs.core_adjust(built, _run(["archival", "experiments"]))["notes"]
    assert {n["role"] for n in second[OWN + "alternative-explanations.md"]} == {"second type"}


def test_every_checklist_id_has_an_owner():
    for i in IDS:
        assert _owners(i), i


# --- Task 4: the manuscript audit's experiments sentence ---

EXP_TYPE = ("A paper is `experiments` when the treatment was assigned at random by a stated procedure, by the "
            "researchers or an organization working with them (a laboratory, online, field, vignette, "
            "conjoint, or audit experiment); a natural experiment or quasi-experiment, in which no one "
            "assigned the treatment that way, is `archival`.")


def test_experiments_type_sentence():
    text = (SKILL / "agents" / "manuscript-audit.md").read_text(encoding="utf-8")
    assert text.count(EXP_TYPE) == 1
    line = text.split("There is no correlational type", 1)[1].split("\n", 1)[0]
    assert line.index("record `archival` as its second type when the main outcome comes from records.") < line.index(
        EXP_TYPE)
    assert EM_DASH not in line
    assert text.count("- IV (encouragement):") == 1 and text.count("a randomized experiment is not DiD or IV") == 1


# --- Task 12: README and repo spec ---

def test_readme_and_spec_name_the_experiments_pack():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    section = readme.split("## Packs", 1)[1].split("\n## ", 1)[0]
    assert "- **Experiments** is a paper type." in section
    order = ["- **Meta-analysis** is a paper type.", "- **Experiments** is a paper type.",
             "- **Qualitative** is a paper type.", "- **Theory** is a paper type."]
    assert [section.index(s) for s in order] == sorted(section.index(s) for s in order)
    assert len(re.findall(r"A pack adds checks for one kind of paper\. \w+ are built\.", readme)) == 1
    spec = (ROOT / "docs" / "spec.md").read_text(encoding="utf-8")
    assert "The experiments, qualitative, and theory packs are type packs written by one of the authors" in spec
