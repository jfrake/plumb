# tests/test_audit_coverage_vocabulary.py
"""The coverage audit uses the spec severity labels and reads the Stage 5 draft.

Fixture text below is invented for these tests; it describes no real paper.
"""
from __future__ import annotations

import importlib
import json
import pathlib
import sys

from plumb import outputs

SD = pathlib.Path(__file__).resolve().parents[1] / "skills/review/scripts"
sys.path.insert(0, str(SD))
ac = importlib.import_module("audit_coverage")

EXCERPT = "The instrument plausibly affects the outcome through a second channel the paper does not discuss."

REPORT = (
    "Referee Report on A Test Paper\n\n"
    "The paper studies a training program. The design is careful.\n\n"
    "MAJOR COMMENTS\n\n"
    f"1. The exclusion restriction is doubtful. {EXCERPT} I would suggest a placebo test.\n\n"
    "2. The sample is unclear. Table 2 drops firms without saying why.\n\n"
    "MINOR COMMENTS\n\n"
    "3. Minor comments. Table 1 lacks units. First, the notes omit the clustering level.\n\n"
    "REFERENCES\n\n"
    "Author, A. 2019. A methods paper. Journal of Tests, 1(1): 1-10.\n"
)

FIX_LIST = (
    "## Issues\n\n"
    "### 1. The exclusion restriction is doubtful\n\n"
    "Severity: Undermines the main claim\n"
    "Fix: new analysis\n\n"
    f"{EXCERPT} Run a placebo test on the untreated group.\n\n"
    "### 2. The sample is unclear\n\n"
    "Severity: Weakens a claim\n"
    "Fix: quick fix\n\n"
    "Table 2 drops firms without saying why. Report the sample flow.\n\n"
    "## Minor issues\n\n"
    "- Table 1 lacks units.\n\n"
    "## What I left out\n\n"
    "I left out presentation points already in the minor list.\n"
)


def _coverage(severity: str) -> str:
    return (
        "| finding_id | source_file | severity | disposition | target | rationale |\n"
        "|---|---|---|---|---|---|\n"
        f"| mc-1 | stage-4/methods_checks.md | {severity} | INCLUDED_MAJOR | 1 | lead framing |\n"
        "| fv-1 | stage-4/face_validity.md | Weakens a claim | INCLUDED_MAJOR | 2 | sample flow |\n\n"
        f"finding_id: mc-1 source_excerpt: \"{EXCERPT}\"\n"
    )


def _workspace(tmp_path, severity="Undermines the main claim", draft=("draft.txt", REPORT)):
    ws = tmp_path / "review_workspace"
    (ws / "stage-4").mkdir(parents=True)
    (ws / "stage-5").mkdir()
    (ws / "stage-4" / "methods_checks.md").write_text(
        f"## Finding 1\n**Severity:** High\n{EXCERPT}\n"
    )
    (ws / "stage-5" / "clusters.md").write_text("# Synthesis Clusters\n\n## Cluster 1: the exclusion restriction\n")
    (ws / "synthesis_coverage.md").write_text(_coverage(severity))
    if draft:
        (ws / "stage-5" / draft[0]).write_text(draft[1])
    return ws


def test_severity_labels_match_output_validator():
    assert ac.SEVERITIES == outputs.SEVERITIES


def test_well_formed_coverage_passes_with_report(tmp_path):
    ws = _workspace(tmp_path)
    code, msgs = ac.run_audit(ws, tmp_path)
    assert code == 0, msgs


def test_well_formed_coverage_passes_with_fix_list(tmp_path):
    ws = _workspace(tmp_path, draft=("draft.md", FIX_LIST))
    code, msgs = ac.run_audit(ws, tmp_path)
    assert code == 0, msgs


def test_old_serious_label_fails(tmp_path):
    ws = _workspace(tmp_path, severity="Serious")
    code, msgs = ac.run_audit(ws, tmp_path)
    assert code == 1
    assert "INVALID SEVERITY LABELS:" in msgs
    assert any("'Serious'" in m for m in msgs)


def test_old_moderate_label_fails():
    entries = [{"finding_id": "x", "source_file": "stage-4/face_validity.md", "severity": "Moderate",
                "disposition": "INCLUDED_MINOR", "target": "3", "rationale": "r"}]
    errs = ac.check_severity_labels(entries)
    assert len(errs) == 1 and "Moderate" in errs[0]


def test_spec_labels_pass():
    entries = [{"finding_id": s, "source_file": "f.md", "severity": s, "disposition": "INCLUDED_MAJOR",
                "target": "1", "rationale": "r"} for s in outputs.SEVERITIES]
    assert ac.check_severity_labels(entries) == []


def test_upstream_undermines_label_counts_as_serious(tmp_path):
    ws = tmp_path
    (ws / "stage-4").mkdir()
    (ws / "stage-4" / "core_problem.md").write_text(
        "1. The design cannot separate the two mechanisms.\n   Proposed severity: Undermines the main claim\n"
    )
    found = ac.find_serious_findings(ws)
    assert [f[0] for f in found] == ["stage-4/core_problem.md"]


def test_missing_draft_is_infrastructure_error(tmp_path):
    ws = _workspace(tmp_path, draft=None)
    code, msgs = ac.run_audit(ws, tmp_path)
    assert code == 2 and "no draft" in msgs[0]


def test_both_drafts_resolved_by_run_json(tmp_path):
    ws = _workspace(tmp_path)
    (ws / "stage-5" / "draft.md").write_text(FIX_LIST)
    (ws / "run.json").write_text(json.dumps({"output": "fix_list"}))
    path, err = ac.find_draft(ws)
    assert err == "" and path.name == "draft.md"


def test_coverage_gap_by_source_uses_stage_paths(tmp_path):
    ws = _workspace(tmp_path)
    (ws / "stage-4" / "face_validity.md").write_text("Severity: Serious\nA second serious finding.\n")
    (ws / "stage-4" / "completeness.md").write_text("**Severity:** Serious\nA dropped finding.\n")
    code, msgs = ac.run_audit(ws, tmp_path)
    assert code == 1
    assert any("stage-4/completeness.md: 1 Serious upstream but 0 coverage row(s)" in m for m in msgs)


def test_template_drafts_pass_output_validators():
    assert outputs.validate_report(REPORT) == []
    assert outputs.validate_fix_list(FIX_LIST) == []
