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
PACK = ROOT / "packs" / "qualitative"
IDS = [f"Q{i}" for i in range(1, 16)]
# sha256 of each file as its author committed it (the qualitative-pack branch, e096a17).
AUTHOR = {
    "agents/alternative-interpretations.md": "0042d17a0bb3615c355a59078e3250dd66803e305efc61faec63be2031225c51",
    "agents/claim-to-excerpt.md": "2a8dfe6e04e760ec78bf3a039064bdfed10c1f9ecec8b784b56567ab6a3a75a5",
    "agents/fieldwork-and-evidence.md": "a2a74e18a5c25766ece010186f5b011fe8393c3af02a6c63b1bdff6ea804b30b",
    "agents/grounding-audit.md": "47115208bdcf5368a84c7650990cc4281b2a4de5ebbaf780d1c1096377ab3cbf",
    "agents/methods-checks.md": "276f609b118e812ac4360d21b1b11cd38569d48e01a71d7a628582ab71218008",
    "checklists/qualitative.yaml": "adbba89f6d172f4fab728df9b2f3c94f275245902e1b5990120957eba882c9e5",
}
EM_DASH = chr(0x2014)
SLOTS = {"context": ["fieldwork-and-evidence.md"], "theory": ["grounding-audit.md"],
         "diagnose": ["methods-checks.md", "claim-to-excerpt.md", "alternative-interpretations.md"]}


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
    assert p.name == "qualitative" and p.overlay is False
    assert [i["id"] for i in p.checklist] == IDS
    assert p.slots == SLOTS


# --- Task 6: the pack's notes for the chain ---

AUTHOR_RULES = [
    "For theory-building papers, a central construct or relationship in the model with no traceable grounding in the "
    "evidence is 'Undermines the main claim'.",
    "A central claim supported by excerpts from a single informant or episode, where the paper implies a broader "
    "pattern, is 'Weakens a claim'.",
    "A concept that relabels an existing construct without engaging it is 'Weakens a claim' when the concept is the "
    "paper's contribution.",
    "Demands for generalizability, inter-rater reliability, or sample-size justification are not raised unless the "
    "paper's genre or its own claims call for them.",
    "For phenomenon-driven papers, demands for theoretical novelty are downgraded one level.",
]
PRIMARY = "Apply this note only when the label says primary type."
PRIVACY_TARGETS = ("accuracy-audit.md", "adjacent-literature.md", "boundary-conditions.md", "contribution-auditor.md",
                   "contribution-research.md", "developmental-advisor.md", "editor-reader.md", "face-validity.md",
                   "missed-criticisms.md", "setting-research.md", "skeptical-reviewer.md", "theory-devil.md",
                   "theory-logic.md", "timeline-research.md")
SCOPE = "every finding about interview, field-observation, or documentary evidence"
OWN = "packs/qualitative/agents/"


def _notes():
    return _pack().core_notes


def _searches(text):
    low = text.lower()
    return "WebSearch" in text or "search the web" in low or "search budget" in low


def _pack_searchers():
    """Other packs' agents that search the web; an agent that says it does not search the web is left out."""
    found = []
    for path in sorted((ROOT / "packs").glob("*/agents/*.md")):
        if path.parent.parent.name == "qualitative":
            continue
        text = path.read_text(encoding="utf-8")
        if _searches(text) and "do not search the web" not in text.lower():
            found.append(f"packs/{path.parent.parent.name}/agents/{path.name}")
    return found


PACK_PRIVACY_TARGETS = _pack_searchers()


def _owners(i):
    """Protocol headings that carry the id in brackets, or the pack's own notes that assign it (L17)."""
    heads = [a for a in SLOTS["diagnose"] + SLOTS["theory"]
             if re.search(rf"^###.*\[[^\]]*\b{i}\b", _agent(a), re.M)]
    notes = [k for k, v in _notes().items() if k.startswith(OWN)
             for n in v if re.search(rf"(?:checklist item|[Cc]ite) {i}\b|\b{i} (?:for|when)\b", n)]
    return heads + notes


def test_author_rules_and_turns_off_are_unchanged():
    p = _pack()
    assert p.severity_rules == AUTHOR_RULES and p.turns_off == [] and p.read_checkin_lines == []
    assert packs.core_adjust(_built(), _run(["qualitative"]))["off"] == {}


def test_core_notes_reach_the_agents_the_rulings_name():
    assert set(_notes()) == {"stage-4-compiler", "stress-test-prompt", OWN + "grounding-audit.md",
                             OWN + "methods-checks.md", OWN + "claim-to-excerpt.md"} | set(PRIVACY_TARGETS) | set(
        PACK_PRIVACY_TARGETS)


def test_guard_notes_gate_on_the_primary_type():
    notes = _notes()
    for target in ("stage-4-compiler", "stress-test-prompt"):
        assert len(notes[target]) == 1 and notes[target][0].startswith(PRIMARY), target
    [face] = [n for n in notes["face-validity.md"] if n.startswith(PRIMARY)]
    assert "write 'No estimates to benchmark.' as your whole report and stop. Skip Step 7" in face
    assert (SKILL / "agents" / "face-validity.md").read_text(encoding="utf-8").count("### Step 7: ") == 1
    compiler = notes["stage-4-compiler"][0]
    assert "The skeptic's protected core problem may be narrowed, never dropped." in compiler
    assert "for a comparison case chosen for theoretical contrast, is fair" in compiler
    labels = packs.core_adjust(_built(), _run(["archival", "qualitative"]))["notes"]["face-validity.md"]
    assert {n["role"] for n in labels if n["pack"] == "qualitative"} == {"second type"}


def test_guard_is_scoped_to_qualitative_evidence():
    notes = _notes()
    assert ("Apply the qualitative pack's fourth severity rule to " + SCOPE + ", from core agents as well as pack "
            "agents: ") in notes["stage-4-compiler"][0]
    assert ("This is a qualitative paper: for findings about interview, field-observation, or documentary evidence, do "
            "not raise") in notes["stress-test-prompt"][0]


def test_privacy_note_reaches_every_searching_agent():
    notes = _notes()
    text = (PACK / "notes" / "privacy.md").read_text(encoding="utf-8").strip()
    assert text.startswith("Apply this note only when the paper says its site, organization, or informants are "
                           "anonymized or disguised.")
    searching = {p.name for p in (SKILL / "agents").glob("*.md") if _searches(p.read_text(encoding="utf-8"))}
    assert searching <= set(PRIVACY_TARGETS), searching - set(PRIVACY_TARGETS)
    for target in PRIVACY_TARGETS:
        assert notes[target].count(text) == 1, target
        assert (SKILL / "agents" / target).is_file(), target
    got = packs.core_adjust(_built(), _run(["archival", "qualitative"]))["notes"]
    assert all(any(n["text"] == text for n in got[target]) for target in PRIVACY_TARGETS)
    assert PACK_PRIVACY_TARGETS and set(PACK_PRIVACY_TARGETS) <= set(notes)
    for target in PACK_PRIVACY_TARGETS:
        assert notes[target].count(text) == 1, target
        assert (ROOT / target).is_file(), target
    every = packs.core_adjust(_built(), _run(["qualitative", "archival", "experiments", "survey", "theory"],
                                             overlays=["inference"]))["notes"]
    for target in PACK_PRIVACY_TARGETS:
        pack = target.split("/")[1]
        if pack in ("archival", "experiments", "survey", "theory"):
            assert any(n["text"] == text for n in every[target]), target
    alone = packs.core_adjust(_built(), _run(["qualitative"]))["notes"]
    assert not any(k in alone for k in PACK_PRIVACY_TARGETS)


def test_stress_prompt_carries_the_guard(tmp_path):
    adjust = packs.core_adjust(_built(), _run(["qualitative"]))
    packs.write_core_adjust(tmp_path, adjust)
    prompt = (tmp_path / "stage-6" / "stress_prompt.md").read_text(encoding="utf-8")
    assert "Pack note (qualitative, primary type): " + PRIMARY + " This is a qualitative paper:" in prompt


def test_grounding_audit_writes_its_gaps_as_findings():
    note = _notes()[OWN + "grounding-audit.md"][0]
    for s in ("`{WORKSPACE}/stage-4/grounding_issues.md`", "Its first line is `Pack: qualitative`", "Cite Q12",
              "Q3 for structure-model fit", "Q13 for relabeling",
              "each gap in structure-model fit when the paper presents a coding structure (an ethnography or case "
              "study without one gets no Q3 finding)", "When there are none, write 'None.' under the title."):
        assert s in note, s
    audit = _agent("grounding-audit.md")
    for verdict in ("*Not traceable:*", "*Thinly grounded:*", "*Asserted:*", "*Contradicted:*", "### Step 3: Structure-Model Fit"):
        assert verdict in audit, verdict
    assert "may write issues to a file in `{WORKSPACE}/stage-4/` whose first line is `Pack: <pack>`" in (
        SKILL / "stages" / "stage-3-theory.md").read_text(encoding="utf-8")


def test_methods_notes_scope_counts_ethics_and_positionality():
    methods = _agent("methods-checks.md")
    for h in ("### CHECK 9: ", "### CHECK 10: ", "### CHECK 11b: "):
        assert methods.count(h) == 1, h
    notes = _notes()[OWN + "methods-checks.md"]
    assert notes[1] == ("CHECK 11b applies only when the discrepancy changes which findings have evidence behind "
                        "them; otherwise rate the mismatch Low and cite Q6.")
    assert notes[2].startswith("In CHECK 10, a missing ethics or IRB statement is not a finding;")
    assert "In CHECK 9, a missing positionality statement is not a finding by itself;" in notes[2]
    assert methods.count("### CHECK 8: ") == 1
    assert ("In CHECK 8, the same holds for Confirmability: a missing positionality or reflexivity statement is not a "
            "finding by itself.") in notes[2]


def test_every_checklist_id_has_an_owner():
    for i in IDS:
        assert _owners(i), i
    assert "checklist item Q9" in _notes()[OWN + "methods-checks.md"][0]
    assert "checklist item Q5" in _notes()[OWN + "claim-to-excerpt.md"][0]
    assert "### Part 2: Field-Site Research" in _agent("fieldwork-and-evidence.md")
    assert "### Step 3: Check Each Match" in _agent("claim-to-excerpt.md")


# --- Task 7: the manuscript audit's qualitative sentence ---

QUAL_TYPE = ("A paper is `qualitative` when its findings rest on interviews, observation, or documents the authors "
             "coded or interpreted (a case study, a Gioia-style or grounded-theory study, an ethnography, a "
             "process study, or an interview study). Documents coded into variables for statistical analysis are "
             "archival data, not qualitative evidence. A paper whose main analysis is qualitative comparative "
             "analysis (QCA, csQCA, fsQCA, or mvQCA) is typed by the rules in this paragraph, treating its sets as "
             "its focal variables: memberships the authors assign case by case, by judgment, from interviews, "
             "observation, or documents they read are qualitative evidence; memberships calibrated by a stated "
             "rule from a measured variable take the type of that variable's source. When the sets come from more "
             "than one kind of source (interviews, observation, or documents read case by case; questionnaires; "
             "records), record two types: `qualitative` first when any set is assigned case by case, "
             "otherwise as the survey rule above says. Record the analysis itself under `Configurational "
             "analysis:`, where the configurational overlay picks it up; never record `other (QCA)`.")


def test_qualitative_type_sentence_routes_qca_to_the_overlay():
    text = (SKILL / "agents" / "manuscript-audit.md").read_text(encoding="utf-8")
    assert text.count(QUAL_TYPE) == 1
    assert "other (QCA)" not in text.replace(QUAL_TYPE, "")
    assert text.count("Documents coded into variables for statistical analysis are archival data") == 1
    line = text.split("There is no correlational type", 1)[1].split("\n", 1)[0]
    assert line.index("A paper is `experiments` when") < line.index(QUAL_TYPE) and EM_DASH not in line
    assert "QCA" not in "".join((PACK / "checklists" / "qualitative.yaml").read_text(encoding="utf-8"))


# --- Task 12: README and repo spec ---

def test_readme_and_spec_name_the_qualitative_pack():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    section = readme.split("## Packs", 1)[1].split("\n## ", 1)[0]
    assert "- **Qualitative** is a paper type." in section
    assert len(re.findall(r"A pack adds checks for one kind of paper\. \w+ are built\.", readme)) == 1
    spec = (ROOT / "docs" / "spec.md").read_text(encoding="utf-8")
    assert "The experiments, qualitative, and theory packs are type packs written by one of the authors" in spec
