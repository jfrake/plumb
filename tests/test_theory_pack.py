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
PACK = ROOT / "packs" / "theory"
IDS = [f"T{i}" for i in range(1, 16)]
# sha256 of each file as its author committed it (the theory-pack branch, abf76fb).
AUTHOR = {
    "agents/argument-record.md": "7fd8556a94450f446edf6f82517d4d6ca2017e22f3df401d2d96630ac39aaa3d",
    "agents/construct-clarity.md": "45a53b03a162fd09c94e949e04b972c9cbc48f2bcf8a5dbecf8265feef405f6a",
    "agents/literature-fidelity.md": "2bd05fac06eaa31bdb2b4d1e32008c16a394403d6cfbb9cc947ca20a87206613",
    "agents/logic-checks.md": "b133f7bd86a1d18468e97fdcfb688dd83b5c9dc371a64d1cb8a6d00d4eff565b",
    "agents/proposition-audit.md": "37f1c18ee0a5c8933434246cb7c9e3b9f3cc5b282c4e6f212cb8b023697c9139",
    "checklists/theory.yaml": "6a77357a39fa71a10bc9f2a4a8cf17598ce5e3fa621b8dbfaa25047160e43d5e",
}
EM_DASH = chr(0x2014)
SLOTS = {"context": ["argument-record.md"], "theory": ["proposition-audit.md"],
         "diagnose": ["construct-clarity.md", "logic-checks.md", "literature-fidelity.md"]}


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
    assert p.name == "theory" and p.overlay is False
    assert [i["id"] for i in p.checklist] == IDS
    assert p.slots == SLOTS


# --- Task 9: turn-offs and notes for the chain ---

AUTHOR_RULES = [
    "A central proposition or process transition that does not follow from the stated premises or mechanisms is "
    "'Undermines the main claim'.",
    "A central construct that is undefined or defined circularly is 'Undermines the main claim' when the main argument "
    "turns on its meaning. Otherwise it is 'Weakens a claim'.",
    "A mischaracterization of prior work is 'Undermines the main claim' when the paper's stated gap rests on it. "
    "Otherwise it is 'Weakens a claim'.",
    "Demands for empirical tests, formal propositions, or a particular theory format are not raised. Each paper is "
    "judged by the standard of its type.",
]
DATA_AGENTS = {"construction-ledger-producer.md", "setting-research.md", "timeline-research.md", "face-validity.md"}
GATE = ("Apply this note only if `construction-ledger-producer.md` is turned off for this paper (the \"Turned off for "
        "this paper:\" line of this dispatch lists it). Otherwise ignore this note. ")
CORE = ("theory-logic.md", "theory-devil.md", "formal-model.md", "completeness.md", "boundary-conditions.md")
OWN = "packs/theory/agents/"
SECOND = "Apply this note only when the label says second type."


def _notes():
    return _pack().core_notes


def _owners(i):
    """Protocol headings that carry the id in brackets, or the pack's own notes that assign it (L17)."""
    heads = [a for a in SLOTS["diagnose"] + SLOTS["theory"]
             if re.search(rf"^###.*\[[^\]]*\b{i}\b", _agent(a), re.M)]
    notes = [k for k, v in _notes().items() if k.startswith(OWN)
             for n in v if re.search(rf"(?:checklist item|[Cc]ite) {i}\b|\b{i} (?:for|when)\b", n)]
    return heads + notes


def _core(name):
    return (SKILL / "agents" / name).read_text(encoding="utf-8")


def test_author_rules_are_unchanged_and_four_data_agents_turn_off():
    p = _pack()
    assert p.severity_rules == AUTHOR_RULES and p.read_checkin_lines == []
    assert {e["agent"] for e in p.turns_off} == DATA_AGENTS
    assert {e["reason"] for e in p.turns_off} == {"a conceptual argument needs no data research"}


def test_off_rule_for_theory_runs():
    built = _built()
    off = packs.core_adjust(built, _run(["theory"], overlays=["computational"]))["off"]
    assert set(off) == DATA_AGENTS | {"construction-ledger-checker.md", "construction-claim-audit.md"}
    assert off["face-validity.md"]["reason"] == "Turned off by the theory pack: a conceptual argument needs no data research"
    mixed = packs.core_adjust(built, _run(["experiments", "theory"]))["off"]
    assert set(mixed) == {"timeline-research.md"} and "no data" in mixed["timeline-research.md"]["reason"]
    assert "the paper has no data" not in mixed["timeline-research.md"]["reason"]
    assert packs.core_adjust(built, _run(["archival", "theory"]))["off"] == {}
    assert packs.core_adjust(built, _run(["theory", "qualitative"]))["off"] == {}
    assert packs.core_adjust(built, _run(["theory"], missing=["other"]))["off"] == {}
    assert set(packs.core_adjust(built, _run(["theory", "simulation"]))["off"]) == {"setting-research.md",
                                                                                   "timeline-research.md"}


def test_core_note_files_gate_on_the_ledger_turn_off():
    notes = _notes()
    for target in CORE + ("stage-4-compiler",):
        assert len(notes[target]) == 1 and notes[target][0].startswith(GATE), target
    assert notes["stress-test-prompt"] == ["Apply this note only when the label says primary type and the paper computes "
                                           "no estimates from data of its own (a table of estimates from prior "
                                           "studies does not count). Do not ask for empirical tests, formal "
                                           "propositions, or a particular theory format; judge the paper by the "
                                           "standard of its type."]
    assert "The skeptic's protected core problem may be narrowed, never dropped." in notes["stage-4-compiler"][0]
    assert "Turned off for this paper: <the files under off>." in (SKILL / "SKILL.md").read_text(encoding="utf-8")


def test_core_note_anchors_exist():
    assert "### Part 1: " in _core("theory-logic.md") and "### Part 3: " in _core("theory-logic.md")
    assert "Do NOT read beyond page 30" in _core("theory-logic.md")
    assert _core("theory-devil.md").count("### Challenge 1: Alternative Theory Completeness") == 1
    assert "### Audit 4: " in _core("formal-model.md") and "### Audit 5: " in _core("formal-model.md")
    comp = _core("completeness.md")
    for s in ("### Step 1: ", "### Step 3: ", "**For empirical-causal papers:**", "**For papers with heterogeneity "
              "claims:**", "**For papers with policy implications:**", "**For papers with formal models:**"):
        assert comp.count(s) == 1, s


def test_second_type_runs_only_the_proposition_and_construct_audits():
    notes = _notes()
    for agent in ("logic-checks.md", "literature-fidelity.md"):
        stub = [n for n in notes[OWN + agent] if n.startswith(SECOND)]
        assert len(stub) == 1 and "'# Not run'" in stub[0], agent
    assert "A stage-4 file that starts `# Not run` holds no findings" in (
        SKILL / "stages" / "stage-4-diagnose.md").read_text(encoding="utf-8")
    rival = [n for n in notes[OWN + "proposition-audit.md"] if n.startswith(SECOND)]
    assert len(rival) == 1 and "Obvious rival addressed" in rival[0]
    assert "Obvious rival addressed?" in _agent("proposition-audit.md")
    second = packs.core_adjust(_built(), _run(["experiments", "theory"]))["notes"]
    assert {n["role"] for n in second[OWN + "logic-checks.md"]} == {"second type"}


def test_proposition_audit_writes_its_gaps_as_findings():
    note = _notes()[OWN + "proposition-audit.md"][0]
    for s in ("`{WORKSPACE}/stage-4/proposition_issues.md`", "Its first line is `Pack: theory`", "Cite T4", "T11 when",
              "When there are none, write 'None.' under the title."):
        assert s in note, s
    audit = _agent("proposition-audit.md")
    for s in ("*Does not follow:*", "*Follows with gaps:*", "*Named only:*", "*Missing:*", "**Coverage:**"):
        assert s in audit, s


def test_proposition_issues_cover_peripheral_units():
    note = _notes()[OWN + "proposition-audit.md"][0]
    assert ("Write one finding for each unit, central or peripheral, that you rate Does not follow or Follows with "
            "gaps, for each proposition that states no direction or does not name the constructs it relates (T4),") in note
    assert "A gap in a peripheral unit is 'Minor'." in note


def test_narrative_reviews_reconcile_with_the_meta_analysis_type_rule():
    audit = _core("manuscript-audit.md")
    assert audit.count("A narrative or integrative review that states no search and coding protocol is `theory`.") == 1
    assert "*Integrative review or theory synthesis:*" in _agent("argument-record.md")
    assert "**Integrative review or theory synthesis:**" in _agent("logic-checks.md")
    reviews = [n for n in _notes()[OWN + "logic-checks.md"] if n.startswith("In CHECK 7, for an integrative review")]
    assert len(reviews) == 1 and "do not ask for a systematic search, screening counts, or coding reliability" in reviews[0]


def test_gated_notes_to_other_types():
    notes = _notes()
    assert any(n.startswith("Apply this note only when `meta-analysis` is in `run.json` `packs`.") and "(M1 to M4)" in n
               for n in notes[OWN + "logic-checks.md"])
    assert any(n.startswith("Apply this note only when `simulation` is in `run.json` `packs`.") and "(K11 and K12)" in n
               for n in notes[OWN + "proposition-audit.md"])
    assert notes[OWN + "construct-clarity.md"][0].startswith(
        "Apply this note only when `qualitative` is in `run.json` `packs`.")
    assert "### CHECK 5: Distinct from Existing Constructs [T13]" in _agent("construct-clarity.md")


def test_every_checklist_id_has_an_owner():
    for i in IDS:
        assert _owners(i), i


# --- Task 10: the manuscript audit's theory sentence ---

THEORY_TYPE = ("A paper is `theory` when its main contribution is a conceptual argument or an analytical model whose "
               "results are proved, and `simulation` when its results come from running a computational model. If the "
               "Table and Figure Inventory contains any table of estimates the paper itself computes "
               "(coefficients with standard errors, p-values, or confidence intervals; a table that "
               "reports estimates from prior studies does not count), `theory` may be the primary type "
               "only with a data type as the second type.")


def test_theory_type_sentence():
    text = _core("manuscript-audit.md")
    assert text.count(THEORY_TYPE) == 1
    line = text.split("There is no correlational type", 1)[1].split("\n", 1)[0]
    assert line.index("A paper is `qualitative` when") < line.index(THEORY_TYPE) and EM_DASH not in line


# --- Task 12: README and repo spec ---

def test_readme_and_spec_name_the_theory_pack():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    section = readme.split("## Packs", 1)[1].split("\n## ", 1)[0]
    assert "- **Theory** is a paper type." in section
    assert len(re.findall(r"A pack adds checks for one kind of paper\. \w+ are built\.", readme)) == 1
    spec = (ROOT / "docs" / "spec.md").read_text(encoding="utf-8")
    assert "The experiments, qualitative, and theory packs are type packs written by one of the authors" in spec
