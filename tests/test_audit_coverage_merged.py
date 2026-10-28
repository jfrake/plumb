# tests/test_audit_coverage_merged.py
"""A MERGED finding must keep its distinct point in the issue it was merged into.

The coverage row's rationale carries `point: <the finding's point>`. The audit checks that
every number in the point (page, table, figure, model, and similar references aside)
appears in the target issue in stage-5/issues.json, or in the draft when the target is
not an issue id. All data here is fake.
"""
from __future__ import annotations

import importlib
import json
import pathlib
import sys

SD = pathlib.Path(__file__).resolve().parents[1] / "skills/review/scripts"
sys.path.insert(0, str(SD))
ac = importlib.import_module("audit_coverage")

HEADER = (
    "| finding_id | source_file | severity | disposition | target | rationale |\n"
    "|---|---|---|---|---|---|\n"
)
ISSUE_9 = {
    "id": "9", "kind": "major", "title": "The effect size is overstated.",
    "severity": "Weakens a claim", "summary": "One SD of X gives about 0.8 percent, not 1.0.",
    "why": "0.036 x 0.21 = 0.76 percent.", "settle": "Report the interval.",
}


def _ws(tmp_path, rows, issues=(ISSUE_9,), draft="Issue 9. One SD of X gives about 0.8 percent."):
    (tmp_path / "stage-5").mkdir()
    (tmp_path / "synthesis_coverage.md").write_text(HEADER + "".join(r + "\n" for r in rows))
    (tmp_path / "stage-5" / "draft.md").write_text(draft)
    if issues is not None:
        (tmp_path / "stage-5" / "issues.json").write_text(json.dumps(list(issues)))
    return tmp_path


def _merged_errors(ws):
    code, msgs = ac.run_audit(ws, ws)
    return code, [m for m in msgs if "merged" in m.lower() or "point" in m.lower()]


def test_lost_number_fails(tmp_path):
    # The case from the planted-paper run: the SD mismatch was merged into the effect-size
    # issue, which kept 0.21 but not 0.22.
    ws = _ws(tmp_path, ["| nf-10 | stage-1/numeric_fidelity.md | Minor | MERGED | 9 | "
                        "point: the SD of X is 0.21 in the text (p. 18) but 0.22 in Table 1 |"])
    code, errs = _merged_errors(ws)
    assert code == 1
    assert any("nf-10" in e and "0.22" in e for e in errs), errs


def test_kept_numbers_pass(tmp_path):
    issue = dict(ISSUE_9, why="0.036 x 0.21 = 0.76 percent; Table 1 gives the SD as 0.22, not 0.21.")
    ws = _ws(tmp_path, ["| nf-10 | stage-1/numeric_fidelity.md | Minor | MERGED | 9 | "
                        "point: the SD of X is 0.21 in the text (p. 18) but 0.22 in Table 1 |"],
             issues=[issue])
    code, msgs = ac.run_audit(ws, ws)
    assert code == 0, msgs


def test_number_in_the_draft_section_of_the_target_counts(tmp_path):
    draft = ("## Issues\n\n### 9. The effect size is overstated.\n\nTable 1 gives the SD as 0.22, not 0.21.\n\n"
             "### 10. Another issue.\n\nNothing here.\n")
    ws = _ws(tmp_path, ["| nf-10 | stage-1/x.md | Minor | MERGED | 9 | point: SD 0.21 in the text, 0.22 in Table 1 |"],
             draft=draft)
    code, msgs = ac.run_audit(ws, ws)
    assert code == 0, msgs


def test_number_in_another_draft_section_does_not_count(tmp_path):
    draft = ("## Issues\n\n### 9. The effect size is overstated.\n\nAbout 0.8 percent.\n\n"
             "### 10. Another issue.\n\nTable 1 gives the SD as 0.22.\n")
    ws = _ws(tmp_path, ["| nf-10 | stage-1/x.md | Minor | MERGED | 9 | point: SD 0.21 in the text, 0.22 in Table 1 |"],
             draft=draft)
    code, errs = _merged_errors(ws)
    assert code == 1
    assert any("0.22" in e for e in errs), errs


def test_pipeline_ids_are_not_required(tmp_path):
    ws = _ws(tmp_path, ["| a-1 | stage-1/x.md | Minor | MERGED | 9 | point: numbers:text:8 and maj-6 give 0.8 percent |"])
    code, msgs = ac.run_audit(ws, ws)
    assert code == 0, msgs


def test_page_table_and_model_references_are_not_required(tmp_path):
    ws = _ws(tmp_path, ["| a-1 | stage-4/x.md | Minor | MERGED | 9 | "
                        "point: on p. 18 and pp. 20-21, Table 3, Figure 2 and Model 5 report 0.76 percent |"])
    code, msgs = ac.run_audit(ws, ws)
    assert code == 0, msgs


def test_number_forms_match(tmp_path):
    # .21 and 0.21 are the same number; 1.0 and 1 are the same number.
    ws = _ws(tmp_path, ["| a-1 | stage-4/x.md | Minor | MERGED | 9 | point: .21 and 1 percent |"])
    code, msgs = ac.run_audit(ws, ws)
    assert code == 0, msgs


def test_point_without_numbers_passes(tmp_path):
    ws = _ws(tmp_path, ["| a-1 | stage-4/x.md | Minor | MERGED | 9 | "
                        "point: the paper does not say how dates were mapped |"])
    code, msgs = ac.run_audit(ws, ws)
    assert code == 0, msgs


def test_missing_point_fails(tmp_path):
    ws = _ws(tmp_path, ["| a-1 | stage-4/x.md | Minor | MERGED | 9 | Edge-of-significance point made in issue 9 |"])
    code, errs = _merged_errors(ws)
    assert code == 1
    assert any("a-1" in e and "point:" in e for e in errs), errs


def test_minor_target_and_hash_forms(tmp_path):
    minor = {"id": "m3", "kind": "minor", "summary": "N is 337 in the text and 339 in the tables."}
    ws = _ws(tmp_path, [
        "| a-1 | stage-4/x.md | Minor | MERGED | m3 | point: N is 337 in the text and 339 in the tables |",
        "| a-2 | stage-4/x.md | Minor | MERGED | #9 | point: about 0.8 percent |",
    ], issues=[ISSUE_9, minor])
    code, msgs = ac.run_audit(ws, ws)
    assert code == 0, msgs


def test_number_in_a_different_issue_does_not_count(tmp_path):
    other = {"id": "m2", "kind": "minor", "summary": "The SD is 0.22 in Table 1."}
    ws = _ws(tmp_path, ["| nf-10 | stage-1/x.md | Minor | MERGED | 9 | point: SD 0.21 in the text, 0.22 in the table |"],
             issues=[ISSUE_9, other], draft="Issue 9 ... 0.21. Minor m2 ... 0.22.")
    code, errs = _merged_errors(ws)
    assert code == 1
    assert any("0.22" in e for e in errs), errs


def test_unknown_target_falls_back_to_the_draft(tmp_path):
    ws = _ws(tmp_path, ["| a-1 | stage-4/x.md | Minor | MERGED | comment 4 | point: 0.44 versus 0.47 |"],
             draft="... the draft says 0.44 and 0.47 ...")
    code, msgs = ac.run_audit(ws, ws)
    assert code == 0, msgs


def test_no_issues_file_falls_back_to_the_draft(tmp_path):
    ws = _ws(tmp_path, ["| a-1 | stage-4/x.md | Minor | MERGED | 9 | point: 0.44 versus 0.47 |"],
             issues=None, draft="... 0.44 ...")
    code, errs = _merged_errors(ws)
    assert code == 1
    assert any("0.47" in e for e in errs), errs


def test_synthesis_prompt_asks_for_the_point():
    syn = (pathlib.Path(__file__).resolve().parents[1] / "skills/review/agents/synthesis.md").read_text()
    text = " ".join(syn.split())
    assert "point:" in text and "every number in the point" in text
