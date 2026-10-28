# tests/test_audit_coverage_user_ruled_out.py
"""A finding resting on an alternative the user marked "C. Not plausible here" may be
EXCLUDED with `user_ruled_out: against:<n>`, but only when that answer is on record.

Fixture text below is invented for these tests; it describes no real paper.
"""
from __future__ import annotations

import importlib
import pathlib
import sys

from plumb import checkin

SD = pathlib.Path(__file__).resolve().parents[1] / "skills/review/scripts"
sys.path.insert(0, str(SD))
ac = importlib.import_module("audit_coverage")

REPORT = (
    "Referee Report on A Test Paper\n\n"
    "The paper studies a training program.\n\n"
    "MAJOR COMMENTS\n\n"
    "1. The sample is unclear. Table 2 drops firms without saying why.\n"
)

ALT_EXCERPT = "Alternative 2: a reverse-timing account could produce the same pattern of adoption."


def _workspace(tmp_path, rationale="user_ruled_out: against:2"):
    ws = tmp_path / "review_workspace"
    (ws / "stage-3").mkdir(parents=True)
    (ws / "stage-5").mkdir()
    (ws / "stage-3" / "theory_devil_report.md").write_text(f"## Alternative 2\n**Severity:** Fatal\n{ALT_EXCERPT}\n")
    (ws / "stage-5" / "clusters.md").write_text("# Synthesis Clusters\n")
    (ws / "stage-5" / "draft.txt").write_text(REPORT)
    (ws / "synthesis_coverage.md").write_text(
        "| finding_id | source_file | severity | disposition | target | rationale |\n"
        "|---|---|---|---|---|---|\n"
        f"| devil-alt-2 | stage-3/theory_devil_report.md | Undermines the main claim | EXCLUDED | - | {rationale} |\n\n"
        f"finding_id: devil-alt-2 source_excerpt: \"{ALT_EXCERPT}\"\n"
    )
    return ws


def test_user_ruled_out_passes_when_user_answered_c(tmp_path):
    ws = _workspace(tmp_path)
    checkin.record(ws, "against", "against:2", "A. Plausible, investigate further (Recommended)", "C. Not plausible here")
    code, msgs = ac.run_audit(ws, tmp_path)
    assert code == 0, msgs


def test_user_ruled_out_fails_without_a_recorded_answer(tmp_path):
    ws = _workspace(tmp_path)
    code, msgs = ac.run_audit(ws, tmp_path)
    assert code == 1
    assert any("against:2" in m and "not plausible" in m.lower() for m in msgs)


def test_user_ruled_out_fails_when_user_kept_the_alternative(tmp_path):
    ws = _workspace(tmp_path)
    checkin.record(ws, "against", "against:2", "A. Plausible, investigate further (Recommended)",
                   "A. Plausible, investigate further (Recommended)")
    code, msgs = ac.run_audit(ws, tmp_path)
    assert code == 1


def test_user_ruled_out_last_answer_wins(tmp_path):
    ws = _workspace(tmp_path)
    checkin.record(ws, "against", "against:2", "A. Plausible, investigate further (Recommended)", "C. Not plausible here")
    checkin.record(ws, "against", "against:2", "A. Plausible, investigate further (Recommended)",
                   "A. Plausible, investigate further (Recommended)")
    code, _ = ac.run_audit(ws, tmp_path)
    assert code == 1


def test_user_ruled_out_needs_an_against_item(tmp_path):
    ws = _workspace(tmp_path, rationale="user_ruled_out: the user disliked it")
    code, msgs = ac.run_audit(ws, tmp_path)
    assert code == 1
