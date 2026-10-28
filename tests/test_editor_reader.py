"""The editor reader: five questions, calibration rules, inputs, and wiring."""
from __future__ import annotations
import re
import sys
from pathlib import Path

import yaml

from plumb import depth

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/review/scripts"))
import audit_coverage as ac  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "skills/review/agents/editor-reader.md"
CHECKLIST = ROOT / "skills/review/shared/editor-checklist.md"


def _flat(p: Path) -> str:
    return " ".join(p.read_text(encoding="utf-8").split())


def test_agent_asks_the_five_questions():
    text = _flat(AGENT)
    for q in ("### 1. Conversation and lineage", "### 2. Premise", "### 3. Constructs", "### 4. Setting",
              "### 5. Stakes"):
        assert q in text, q


def test_agent_states_the_calibration_rules():
    text = _flat(AGENT)
    for rule in ("Weakness or preference?", "Keep minor points minor.", "Arguments, not rulings.",
                 "Phenomenon first.", "Do not deepen a frame the evidence argues against.",
                 "Name a work only when it is in `{WORKSPACE}/stage-2/cocitation.md` or a "
                 "search you ran confirmed it.",
                 "The lists are outside data."):
        assert rule in text, rule
    assert "or that another frame or conversation would serve it better" in text
    assert "for a work from the list, its OpenAlex id" in text
    assert "Never quote a work you have not read." in text
    assert text.count("Never name a work from memory.") == 1


def test_agent_states_the_dev_test_rules():
    text = _flat(AGENT)
    rules = text.split("## Calibration rules", 1)[1].split("## The five questions", 1)[0]
    for rule in ("**Quote the whole passage.**", "including any sentence that qualifies or contradicts the point",
                 "Never use an ellipsis that drops a sentence relevant to the point.",
                 "**Search before saying \"not cited.\"**",
                 "search the paper's reference list and text for the authors and for the topic's key terms",
                 "Before a main point depends on a work, check whether the paper cites it; "
                 "if it does, start from how the paper uses it.",
                 "**Concurrent work is not ignored work.**",
                 "A work dated within about a year before the search cap (the \"Search cap:\" line in "
                 "`{WORKSPACE}/stage-2/cocitation.md`) counts as concurrent with the submission.",
                 "When the paper shows its own date and it is earlier, use that date.",
                 "Never present it as prior work the paper ignored.",
                 "**If the paper is already broad, suggest few works.**",
                 "The limit applies only to suggestions of further literatures for the paper to engage: across all "
                 "findings, suggest at most one or two further works when the paper is already broad.",
                 "Works used to define or check a construct, to test a premise, or as evidence for a point do not "
                 "count toward the limit.",
                 "**Quotations are exact.**",
                 "Copy every quotation exactly as the source prints it, including dashes and punctuation.",
                 "The plain-words and no-dash style rules apply to your own sentences, never to text inside "
                 "quotation marks.",
                 "**Keep minor points minor.**",
                 "Use \"Weakens a claim\" only when, to answer the point, the authors would have to change a main "
                 "claim or the evidence or argument for it; mark the rest Minor.",
                 "Use \"Undermines the main claim\" only when the point, if right, would make the main claim untenable."):
        assert rule in rules, rule
    assert rules.count("Keep minor points minor.") == 1
    for figurative in ("cuts the other way", "widen", "search_before"):
        assert figurative not in rules, figurative
    assert "for a work in the paper's own reference list, the pages where the paper cites it" in rules
    q1 = text.split("### 1. Conversation and lineage", 1)[1].split("### 2. Premise", 1)[0]
    assert ("Before you look at the classics list, check the paper's own reference list for foundational works "
            "on its topic that the paper cites only in passing.") in q1
    assert "When you say the paper cites a work only in passing, list every page where it cites it." in q1
    assert ("Always state the home-conversation answer as its own line in the output, even when you raise no "
            "finding on question 1") in q1
    out = text.split("## Output", 1)[1]
    assert "The home-conversation line for question 1 always appears, whether or not question 1 yields a finding." in out
    assert "`Home conversation:`" in out
    assert ("Sort the numbered findings from most to least consequential; put the one-line lines for questions "
            "with no finding after the list.") in out


def test_checklist_carries_the_dev_test_checks():
    text = _flat(CHECKLIST)
    q1 = text.split("## 1. Conversation and lineage", 1)[1].split("## 2. Premise", 1)[0]
    assert q1.index("First, before the classics list, check the paper's own reference list") < q1.index(
        "Then check the classics list")
    assert "Before calling a work absent, search the reference list and the text for its authors" in q1
    assert "When you say the paper cites a work only in passing, list every page where it cites it." in q1
    assert "Before a main point depends on a work, check whether the paper cites it" in q1
    assert "rest a main point" not in text and "rest a main point" not in _flat(AGENT)
    assert "against the \"Search cap:\" line in `{WORKSPACE}/stage-2/cocitation.md`" in q1
    assert "A work dated within about a year before that date is concurrent" in q1
    assert "suggest at most one or two further works" in q1
    assert "do not count toward the limit" in q1
    assert "Always state, as its own line in the output and even when you raise no finding here" in q1
    q2 = text.split("## 2. Premise", 1)[1].split("## 3. Constructs", 1)[0]
    assert "quote the whole relevant passage, including any sentence that qualifies or contradicts the point" in q2
    last = text.split("## Before you write", 1)[1]
    assert "cut the works suggested elsewhere to the one or two most central" in last
    assert "the authors would have to change a main claim or the evidence or argument for it" in last
    assert "Sort the numbered findings from most to least consequential;" in last
    assert "cuts the other way" not in text and "search_before" not in text


def test_agent_reads_its_inputs_and_writes_its_file():
    text = _flat(AGENT)
    for f in ("{WORKSPACE}/stage-2/cocitation.md", "{WORKSPACE}/stage-2/setting.md",
              "{WORKSPACE}/stage-2/contribution.md", "{WORKSPACE}/stage-1/reference_list.md",
              "{PLUGIN}/skills/review/shared/editor-checklist.md", "{PLUGIN}/skills/review/shared/research-protocol.md",
              "{PLUGIN}/skills/review/shared/contracts.md",
              "{WORKSPACE}/stage-3/editor_reader.md"):
        assert f in text, f
    assert "Question to the authors:" in text


def test_editor_reader_tolerates_missing_inputs():
    text = _flat(AGENT)
    assert "A file in this list that does not exist was turned off or failed for this paper; work without it." in text


def test_search_budget():
    assert depth.limits("standard")["searches"]["editor-reader"] == "about 10"
    assert depth.limits("deep")["searches"]["editor-reader"] == "about 20"
    text = _flat(AGENT)
    assert "Search budget: about 10 searches at Standard depth, about 20 at Deep." in text


def test_checklist_marks_the_framing_pack_checks():
    text = _flat(CHECKLIST)
    for item in ("(framing) Check whether the framing claims more agency", "(framing) Check whether the motivation is only a gap",
                 "(framing) Check whether the paper states its core point in one sentence"):
        assert item in text, item
    assert "Items marked (framing) repeat a framing pack check." in text


def test_checklist_covers_each_question_and_quotes_no_letter():
    text = _flat(CHECKLIST)
    for h in ("## 1. Conversation and lineage", "## 2. Premise", "## 3. Constructs", "## 4. Setting",
              "## 5. Stakes"):
        assert h in text, h
    assert "Reviewer #" not in text and "R1" not in text and "R2" not in text


def _checklist_ids() -> list[str]:
    return re.findall(r"^- \[(\d[a-z])\] ", CHECKLIST.read_text(encoding="utf-8"), flags=re.M)


def test_checklist_items_carry_unique_ids():
    ids = _checklist_ids()
    assert len(ids) == 28
    assert len(ids) == len(set(ids))
    text = CHECKLIST.read_text(encoding="utf-8")
    sections = re.split(r"^## ", text, flags=re.M)[1:]
    for sec in sections:
        head = sec.split("\n", 1)[0]
        n = head.split(".", 1)[0]
        if n.isdigit():
            body_ids = re.findall(r"^- \[(\d[a-z])\] ", sec, flags=re.M)
            assert body_ids, head
            assert all(i.startswith(n) for i in body_ids), head
            assert body_ids == [n + c for c in "abcdefghij"[:len(body_ids)]], head
    # every bullet in a numbered section has an id
    for sec in sections:
        if sec.split(".", 1)[0].isdigit():
            bullets = re.findall(r"^- ", sec, flags=re.M)
            assert len(bullets) == len(re.findall(r"^- \[\d[a-z]\] ", sec, flags=re.M))


def test_agent_requires_the_checks_section():
    text = _flat(AGENT)
    sec = text.split("### Checks section", 1)[1]
    assert "`## Checks`" in sec
    assert "After the numbered findings and the no-finding lines" in sec
    assert "`- 1a: finding <n>`" in sec
    assert "`- 1a: checked, <one short clause on what you checked and what you found>`" in sec
    assert "`- 1a: skipped, <reason>` only when a pack note tells you to skip the item" in sec
    assert "so that each id appears exactly once" in sec
    assert "must reflect a real look at the paper" in sec
    assert "never a guess" in sec
    assert "leave out severity labels and the words Serious, High, and Fatal" in sec


def test_pack_notes_fit_the_checks_section():
    theory = _flat(ROOT / "packs/theory/notes/editor-reader.md")
    assert "skipped, pack note" in theory and "3a to 3d" in theory
    meta = yaml.safe_load((ROOT / "packs/framing/pack.yaml").read_text(encoding="utf-8"))
    note = " ".join(meta["core_notes"]["editor-reader.md"][0]["text"].split())
    assert "skipped, pack note" in note
    framing_ids = re.findall(r"^- \[(\d[a-z])\] \(framing\)", CHECKLIST.read_text(encoding="utf-8"), flags=re.M)
    assert framing_ids == ["1j", "2d", "5c"]


def test_audit_coverage_ignores_the_checks_section(tmp_path):
    ids = _checklist_ids()
    lines = ["Home conversation: x.", "", "1. **Question:** 2", "   **Proposed severity:** Minor", "",
             "## Checks"]
    lines += [f"- {i}: finding 1" if i == "2a" else
              f"- {i}: skipped, pack note: theory pack" if i.startswith("3") else
              f"- {i}: checked, defined on p. 4 and used the same way after" for i in ids]
    ws = tmp_path
    (ws / "stage-3").mkdir()
    (ws / "stage-3/editor_reader.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert ac.find_serious_findings(ws) == []
    # a real top-severity finding in the same file is still found
    (ws / "stage-3/editor_reader.md").write_text(
        "\n".join(lines) + "\n\n**Proposed severity:** Undermines the main claim\n", encoding="utf-8")
    assert len(ac.find_serious_findings(ws)) == 1


def test_stage_3_dispatches_the_editor_reader():
    step1 = _flat(ROOT / "skills/review/stages/stage-3-theory.md").split(" 2. ", 1)[0]
    assert "`agents/editor-reader.md`" in step1


def test_synthesis_reads_it_and_writes_judgment_points_as_questions():
    text = _flat(ROOT / "skills/review/agents/synthesis.md")
    assert "`{WORKSPACE}/stage-3/editor_reader.md`" in text
    assert ("For a finding from `{WORKSPACE}/stage-3/editor_reader.md` whose adjudication type is judgment, "
            "write the issue around its `Question to the authors:` line.") in text
    assert "The issue title stays a complete declarative sentence that states the point" in text
    assert "The question is the first sentence of the body, in place of the problem sentence" in text
    assert "open with the question" not in text
    raw = (ROOT / "skills/review/agents/synthesis.md").read_text(encoding="utf-8")
    assert "draft check-in.\n\n8f. **Core problem" in raw


def test_contribution_auditor_leaves_positioning_to_the_editor_reader():
    text = _flat(ROOT / "skills/review/agents/contribution-auditor.md")
    assert "Which conversation in its own field does it join?" not in text
    assert "of any age" in text
    assert "Does that claim appear, in whole or in substantial part, in prior published work?" in text
    novelty = [ln for ln in (ROOT / "skills/review/agents/contribution-auditor.md").read_text(
        encoding="utf-8").splitlines() if ln.startswith("Pressure-test the novelty claim.")]
    assert len(novelty) == 1 and "—" not in novelty[0]


def test_theory_pack_note_skips_constructs():
    meta = yaml.safe_load((ROOT / "packs/theory/pack.yaml").read_text(encoding="utf-8"))
    assert meta["core_notes"]["editor-reader.md"] == [{"file": "notes/editor-reader.md"}]
    note = _flat(ROOT / "packs/theory/notes/editor-reader.md")
    assert note.startswith("Skip question 3 (Constructs)")


def test_framing_pack_note_narrows_the_editor_reader():
    meta = yaml.safe_load((ROOT / "packs/framing/pack.yaml").read_text(encoding="utf-8"))
    note = " ".join(meta["core_notes"]["editor-reader.md"][0]["text"].split())
    assert "Skip every checklist item marked (framing): 1j (whether the framing fits the findings), 2d, and 5c." in note
    assert "raise only what a search shows" in note
    # framing_diagnosis.md is written after the editor reader runs; the record exists by Stage 2.
    assert "`{WORKSPACE}/stage-2/framing_record.md`" in note
    assert "framing_diagnosis" not in note


def test_framing_pack_gives_the_conversation_question_to_the_editor_reader():
    meta = yaml.safe_load((ROOT / "packs/framing/pack.yaml").read_text(encoding="utf-8"))
    aud = " ".join(meta["core_notes"]["contribution-auditor.md"][0]["text"].split())
    assert "Which conversation the paper joins belongs to the editor reader." in aud
    diag = _flat(ROOT / "packs/framing/agents/framing-diagnosis.md")
    assert "which conversation it joins belongs to the editor reader" in diag


def test_qualitative_privacy_note_reaches_the_editor_reader():
    meta = yaml.safe_load((ROOT / "packs/qualitative/pack.yaml").read_text(encoding="utf-8"))
    assert {"file": "notes/privacy.md"} in meta["core_notes"]["editor-reader.md"]

