"""Stage 0 gaps found in the Plan 1e integration review (2026-10-02)."""
from __future__ import annotations
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE0 = ROOT / "skills" / "review" / "stages" / "stage-0-intake.md"


def _text() -> str:
    return " ".join(STAGE0.read_text(encoding="utf-8").split())


def _redo_row(name: str) -> str:
    rows = re.findall(r"^\s+- ([^\n]+)", STAGE0.read_text(encoding="utf-8"), re.M)
    return next(r for r in rows if r.startswith(name + ":"))


def test_an_outputs_change_at_the_recap_rewrites_outputs_for_an_author():
    row = _redo_row("Outputs")
    assert "rerun the end of step 5" in row and "plumb filter-outputs" in row and "step 6" in row


def test_a_banned_journal_referee_passes_issues_list():
    assert "whose run stops at step 6. The mapped outputs list is then `issues_list`" in _text()


def test_every_overlay_pack_has_plain_words_at_the_overlay_question():
    text = _text()
    overlays = [p.parent.name for p in (ROOT / "packs").glob("*/pack.yaml")
                if re.search(r"^overlay:\s*true", p.read_text(encoding="utf-8"), re.M)]
    assert len(overlays) >= 6
    for pack in overlays:
        assert f" for {pack}" in text, pack


def test_other_is_a_type_with_no_pack():
    assert '"Other" is a type with no pack' in _text()


def test_a_journal_change_to_c_asks_the_detail_again():
    row = _redo_row("Permission or journal")
    assert "setup:journal_detail" in row


def test_a_verdict_is_removed_before_the_not_verified_block_and_cannot_loop():
    s7 = " ".join((ROOT / "skills" / "review" / "stages" / "stage-7-output.md").read_text(encoding="utf-8").split())
    removal = s7.index("names an editorial recommendation, a verdict, or a desk-reject signal")
    block = s7.index('a line "Not verified:"')
    assert removal < block
    assert "at most three removals" in s7 and "stage-7/withheld/" in s7


def _skill() -> str:
    return " ".join((ROOT / "skills" / "review" / "SKILL.md").read_text(encoding="utf-8").split())


def test_resume_mid_recap_takes_depth_from_the_recorded_answer():
    assert "take the depth from the recorded `setup:depth` answer and write it into `run.json` before anything below reads it" in _skill()


def test_a_change_to_quick_drops_the_stress_test_from_consent():
    assert "If the new depth is Quick, drop `codex_stress_test` from `egress` and remove `stress_test_provider`" in _redo_row("Depth")


def test_resume_rebuilds_the_task_list_for_the_depth():
    assert "rebuild the task list with only the stages that run at this depth" in _skill()
