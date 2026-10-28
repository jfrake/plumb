from __future__ import annotations
import pytest
from plumb import outputs

GOOD_FIX = """## Issues
### 1. Pre-trends in hiring
Severity: Undermines the main claim
Fix: can't fix, narrow the claim
Treated firms were already diverging.
### 2. Clustering level
Severity: Weakens a claim
Fix: quick fix
Cluster at the state level.
## What I left out
Two minor wording points.
"""

def test_good_fix_list():
    assert outputs.validate_fix_list(GOOD_FIX) == []

def test_fix_list_order_by_consequence():
    bad = GOOD_FIX.replace("Severity: Undermines the main claim", "Severity: Minor", 1)
    assert any("consequence" in e for e in outputs.validate_fix_list(bad))

def test_fix_list_requires_tag_and_left_out():
    bad = GOOD_FIX.replace("Fix: quick fix\n", "").replace("## What I left out", "## Notes")
    errs = outputs.validate_fix_list(bad)
    assert any("Fix:" in e for e in errs) and any("left out" in e for e in errs)


def test_fix_list_requires_issues_header():
    bad = GOOD_FIX.replace("## Issues", "## Problems")
    errs = outputs.validate_fix_list(bad)
    assert any("Issues" in e for e in errs)


def test_fix_list_invalid_severity_value():
    bad = GOOD_FIX.replace("Severity: Undermines the main claim", "Severity: minor", 1)
    errs = outputs.validate_fix_list(bad)
    assert any("'minor'" in e and "has Severity" in e for e in errs)


def test_fix_list_invalid_fix_value():
    bad = GOOD_FIX.replace("Fix: quick fix", "Fix: Quick Fix", 1)
    errs = outputs.validate_fix_list(bad)
    assert any("'Quick Fix'" in e and "has Fix" in e for e in errs)

def test_recommendation_detected():
    assert outputs.has_recommendation("Recommendation: Major Revision")
    assert outputs.has_recommendation("\nReject\n")
    assert not outputs.has_recommendation("I recommend clustering at the firm level.")


@pytest.mark.parametrize("text", [
    "Recommendation: Reject",
    "Major Revision",
    "Minor Revision.",
    "major r&r",
    "R&R",
    "Revise and resubmit.",
    "My recommendation is to reject",
    "My recommendation is major revision",
    "I recommend rejection",
    "I recommend acceptance",
    "I recommend a major revision",
    "I recommend that the editor reject this paper",
    "Decision: accept",
    "Recommend: minor revisions",
    "Recommended decision: reject",
    "I would recommend rejecting the paper",
    "I recommend the paper be accepted",
])
def test_recommendation_true_cases(text):
    assert outputs.has_recommendation(text), f"Failed to detect: {text}"


@pytest.mark.parametrize("text", [
    "I recommend clustering at the firm level.",
    "I recommend you revise the introduction.",
    "You might revise the introduction.",
    "I would accept this assumption if you show the pre-trends.",
    "Reviewers often reject this argument, so address it.",
    "I recommend adding a placebo test.",
    "The authors reject the null hypothesis.",
    "Consider a major revision of Section 3.",
])
def test_recommendation_false_cases(text):
    assert not outputs.has_recommendation(text), f"False positive: {text}"


@pytest.mark.parametrize("text", [
    "We recommend acceptance.",
    "We recommend rejection of this paper.",
    "We recommend a major revision.",
    "We recommend a minor revision.",
    "Our recommendation is to reject.",
    "Our recommendation is major revision.",
    "I would recommend rejection.",
    "We would recommend acceptance.",
    "I recommend a revise and resubmit.",
    "We recommend a revise and resubmit.",
    "We recommend that the editor reject this paper.",
    "We recommend the paper be accepted.",
    "We would recommend rejecting the paper.",
])
def test_recommendation_we_and_would_forms(text):
    assert outputs.has_recommendation(text), f"Failed to detect: {text}"


@pytest.mark.parametrize("text", [
    "The authors recommend a policy change for widget exporters.",
    "We recommend the authors report the pooled difference.",
    "We recommend clustering at the firm level.",
    "We recommend adding a placebo test.",
    "We recommend you revise the introduction.",
    "We would recommend a longer pre-period for Fakeland.",
    "Our recommendation is to report the pooled difference.",
])
def test_recommendation_we_forms_that_advise_authors_pass(text):
    assert not outputs.has_recommendation(text), f"False positive: {text}"

GOOD_REPORT = """You study how X affects Y.

However, I have several concerns that I outline below.

1. Identification. Treated firms were already diverging.

2. Measurement. The key variable mixes two constructs.
"""

def test_good_report():
    assert outputs.validate_report(GOOD_REPORT) == []

def test_report_numbering_and_blank_lines():
    bad = GOOD_REPORT.replace("\n\n2. Measurement", "\n3. Measurement")
    errs = outputs.validate_report(bad)
    assert any("numbered" in e for e in errs) and any("blank line" in e for e in errs)


def test_report_blank_line_message_mentions_prose():
    bad = GOOD_REPORT.replace("\n\n2. Measurement", "\n2. Measurement")
    errs = outputs.validate_report(bad)
    assert any("blank line" in e and "prose" in e for e in errs)

def test_report_rejects_markdown():
    assert outputs.validate_report(GOOD_REPORT + "\n# Heading\n- bullet\n")


# Fix advice that reads like a verdict on its words alone; none is flagged (Plan 1e wave A3).
@pytest.mark.parametrize("text", [
    "What would settle it: revise the paper to report first-stage F statistics",
    "The authors could revise the manuscript to include clustered errors",
    "We recommend revisions to the theory section so the mechanism is explicit",
    "I recommend accepting the authors' measure only after a placebo test",
    "We would recommend rejecting the null of parallel trends",
])
def test_fix_advice_is_not_a_verdict(text):
    assert not outputs.has_recommendation(text), f"False positive: {text}"
    assert outputs.desk_reject_phrases(text) == [], f"False positive: {text}"


# A verdict in a report or an issues list fails the same way it fails in the memo (wave A5).
VERDICTS = [
    "The paper should be rejected.",
    "I would recommend the editor reject this paper.",
    "I recommend that this paper be rejected.",
    "I recommend publication after minor changes.",
]


@pytest.mark.parametrize("phrase", VERDICTS)
def test_report_rejects_a_verdict(phrase):
    errs = outputs.validate_report(GOOD_REPORT + "\n" + phrase + "\n")
    assert any("editorial recommendation" in e or "desk-reject" in e for e in errs), phrase


@pytest.mark.parametrize("phrase", VERDICTS)
def test_issues_list_rejects_a_verdict(phrase):
    from tests.test_issues_list import FACTS, FULL
    for text, mode in ((FULL, "full"), (FACTS, "facts_only")):
        text = text.replace("## What I left out\n", f"{phrase}\n\n## What I left out\n", 1) \
            if mode == "full" else text.replace("## Dropped items", f"{phrase}\n\n## Dropped items", 1)
        errs = outputs.validate_issues_list(text, mode)
        assert any("editorial recommendation" in e or "desk-reject" in e for e in errs), (phrase, mode)


# A referee's report ends with the exact disclosure line (Plan 1e wave C2).
def test_referee_report_needs_the_disclosure_line_last():
    errs = outputs.validate_report(GOOD_REPORT, permission="journal")
    assert any("disclosure line" in e for e in errs)
    assert outputs.validate_report(GOOD_REPORT + "\n" + outputs.DISCLOSURE_LINE + "\n", permission="journal") == []
    moved = outputs.DISCLOSURE_LINE + "\n\n" + GOOD_REPORT
    assert any("disclosure line" in e for e in outputs.validate_report(moved, permission="journal"))
    assert outputs.validate_report(GOOD_REPORT, permission="mine") == []


def test_validate_output_cli_takes_the_permission(tmp_path):
    import subprocess, sys
    from pathlib import Path
    f = tmp_path / "r.txt"
    f.write_text(GOOD_REPORT)
    root = Path(__file__).resolve().parents[1]
    import os
    env = dict(os.environ, HOME=str(tmp_path), PLUMB_CONFIG=str(tmp_path / "no-config.json"))
    r = subprocess.run([sys.executable, "-m", "plumb", "validate-output", "report", str(f), "--permission", "journal"],
                       capture_output=True, text=True, cwd=root, env=env)
    assert r.returncode == 1 and "disclosure line" in r.stdout


def test_report_writer_and_stage_7_agree_on_the_disclosure_line():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "skills/review"
    writer = (root / "agents/report-writer.md").read_text(encoding="utf-8")
    seven = (root / "stages/stage-7-output.md").read_text(encoding="utf-8")
    assert "disclosure line" in writer.split("- End with the last reference", 1)[1].split("\n", 1)[0]
    assert outputs.DISCLOSURE_LINE in seven
    assert seven.count("plumb validate-output report {RUN}/mock_report.txt --permission <permission>") == 2
