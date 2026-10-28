from __future__ import annotations
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE0 = ROOT / "skills" / "review" / "stages" / "stage-0-intake.md"
# What each Stage 0 step does, in Plan 1e's numbering: the recap is step 8, so dispatch is 9 and 10,
# setup round 2 is 11, the level map 12, and the rest of run.json 13.
ANCHORS = {1: "plumb run-dir new", 2: "The text check runs at the start of step 9",
           3: "Table pages are rendered at the start of step 9", 4: "plumb validate-packs",
           5: "Setup, round 1.", 6: "plumb referee-decision", 7: "Consent screen", 8: "Recap, after the consent check",
           9: "agents/paper-summary.md", 10: "agents/manuscript-audit.md", 11: "Setup, round 2.",
           12: "Map the check-in level", 13: "plumb core-adjust"}
# Every "Stage 0 step N" outside Stage 0, by the phrase around it, and what that step must do.
REFS = {"that Stage 0 step 1 creates": 1, "as in Stage 0 step 6": 6, "as Stage 0 step 7": 7,
        "the values from the text check at the start of Stage 0 step 9": 9, "written at Stage 0 step 13": 13}


def _steps():
    parts = re.split(r"\n(?=\d+\. )", STAGE0.read_text(encoding="utf-8"))
    return {int(p.split(".", 1)[0]): p for p in parts[1:]}


def test_stage_0_steps_are_numbered_as_plan_1e_numbers_them():
    steps = _steps()
    assert sorted(steps) == list(range(1, 14))
    for n, anchor in ANCHORS.items():
        assert anchor in steps[n], (n, anchor)


def test_every_reference_to_a_stage_0_step_names_the_right_step():
    steps = _steps()
    skill = (ROOT / "skills" / "review" / "SKILL.md").read_text(encoding="utf-8")
    for phrase, n in REFS.items():
        assert skill.count(phrase) == 1, phrase
        assert ANCHORS[n] in steps[n], (phrase, n)
    assert "Stage 0 runs `plumb models <depth>` at the end of step 5" in skill
    assert "plumb models <depth>" in steps[5]
    seen = 0
    for p in list((ROOT / "skills").rglob("*.md")) + list((ROOT / "packs").rglob("*.md")):
        if p == STAGE0:
            continue
        refs = re.findall(r"Stage 0 steps? \d+", p.read_text(encoding="utf-8"))
        seen += len(refs)
        if p.name == "SKILL.md" and p.parent.name == "review":
            assert len(refs) == len(REFS), refs
        else:
            assert not refs, (str(p.relative_to(ROOT)), refs)
    assert seen == len(REFS)


def test_nothing_reads_the_pdf_before_the_consent_check_and_the_recap():
    """A referee at a journal that bars AI tools stops at step 6, and an author run passes the consent
    check at step 7, before any script or agent opens the PDF. Both PDF scripts run in step 9."""
    text = STAGE0.read_text(encoding="utf-8")
    steps = _steps()
    for script in ("garble_score.py", "render_table_pages.py"):
        assert script in steps[9]
        assert all(script not in steps[n] for n in range(1, 9)), script
    assert text.index("plumb referee-decision") < text.index("garble_score.py")
    assert text.index("plumb consent-check") < text.index("garble_score.py")
    head = text.split("\n1. ", 1)[0]
    assert "Nothing from the manuscript enters this conversation" in head
    assert "including to look into a warning" in head
    assert steps[9].index("garble_score.py") < steps[9].index("agents/paper-summary.md")
    assert '"page_count"' in steps[9] and '"page_count"' not in steps[5]
