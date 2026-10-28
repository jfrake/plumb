"""The issues-list validator and the report traceability check. The texts are fake."""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

from plumb import outputs

ROOT = Path(__file__).resolve().parents[1]

FULL = """## Issues

### 1. The fake instrument may fail

Severity: Undermines the main claim
Fix: new analysis
Where: ms p. 12 (PDF p. 14)

The fake instrument could move the outcome through a second channel. That would bias the estimate.

It matters for this journal because the claim is causal. Report the first stage and bound the estimate.

## Minor issues

- 2. A fake table omits its sample size. (ms p. 9 (PDF p. 11))

## What I left out

Nothing beyond the minor list.

## Dropped items

- A fake third point: overruled in the audit.
"""

VALIDATED = [
    {"id": "1", "summary": "The fake instrument could move the outcome through a second channel (p. 12). That would bias the estimate."},
    {"id": "2", "summary": "A fake table omits its sample size."},
]
DROPPED = [{"item": "majors:3", "title": "A fake third point", "reason": "overruled in the audit"}]

FACTS = """## Checked facts

### 1. A fake text figure does not match its table

Severity: Minor
Where: ms p. 4 (PDF p. 6, approximate)

The text gives 0.31 where the fake table shows 0.13.

## What was checked

Two fake tables were read twice and compared.

## Did we read it right?

You confirmed the summary.

## Dropped items

None.
"""


def test_full_list_passes():
    assert outputs.validate_issues_list(FULL, "full", VALIDATED, DROPPED) == []


def test_facts_only_list_passes():
    assert outputs.validate_issues_list(FACTS, "facts_only", [{"id": "1", "summary": ""}], []) == []


def test_bare_page_citation_fails():
    bad = FULL.replace("(ms p. 9 (PDF p. 11))", "(p. 9)")
    assert any("both numbers" in e for e in outputs.validate_issues_list(bad, "full"))


def test_page_numbers_in_references_are_not_citations():
    ok = FULL + "\nREFERENCES\n\nAuthor, A. (2001). A fake title. Fake Journal, 3(2), pp. 80-108.\n"
    assert outputs.validate_issues_list(ok, "full") == []


def test_page_cites_of_other_works_are_not_manuscript_citations():
    ok = FULL.replace("That would bias the estimate.", "That would bias the estimate (Author, 2009, p. 213).")
    assert outputs.validate_issues_list(ok, "full") == []
    bad = FULL.replace("That would bias the estimate.", "That would bias the estimate (see p. 213).")
    assert any("both numbers" in e for e in outputs.validate_issues_list(bad, "full"))


def test_where_line_required():
    bad = FULL.replace("Where: ms p. 12 (PDF p. 14)\n", "")
    assert any("'Where:' line" in e for e in outputs.validate_issues_list(bad, "full"))


def test_dropped_appendix_required_last_and_complete():
    assert any("Missing the '## Dropped items'" in e
               for e in outputs.validate_issues_list(FULL.split("## Dropped items")[0], "full"))
    moved = FULL.replace("## What I left out\n\nNothing beyond the minor list.\n\n", "") + \
        "\n## What I left out\n\nNothing.\n"
    assert any("last '##' section" in e for e in outputs.validate_issues_list(moved, "full"))
    assert any("dropped.json has 2" in e
               for e in outputs.validate_issues_list(FULL, "full", None, DROPPED * 2))


def test_facts_only_gives_no_fix():
    bad = FACTS.replace("Severity: Minor\n", "Severity: Minor\nFix: quick fix\n")
    assert any("no fixes" in e for e in outputs.validate_issues_list(bad, "facts_only"))


def test_numbering_and_summaries_follow_validated_json():
    extra = VALIDATED + [{"id": "3", "summary": "A fake point the list forgot."}]
    errs = outputs.validate_issues_list(FULL, "full", extra, DROPPED)
    assert any("validated.json has items [1, 2, 3]" in e for e in errs)
    assert any("Item 3 must include its summary" in e for e in errs)


def test_full_list_keeps_the_fix_list_checks():
    bad = FULL.replace("Fix: new analysis\n", "")
    assert any("'Fix:' line" in e for e in outputs.validate_issues_list(bad, "full"))


def test_recommendation_still_fails():
    bad = FACTS.replace("You confirmed the summary.", "Recommendation: reject.")
    assert any("recommendation" in e for e in outputs.validate_issues_list(bad, "facts_only"))


def test_report_comment_must_trace_to_a_validated_issue():
    report = "Referee Report on A Fake Paper\n\n1. First fake comment.\n\n2. Second fake comment.\n"
    assert outputs.report_trace_errors(report, {"1": ["1"], "2": ["2"]}, VALIDATED) == []
    errs = outputs.report_trace_errors(report, {"1": ["1"]}, VALIDATED)
    assert errs == ["Comment 2 does not trace to an issue in validated.json.",
                    "Issue 2 in validated.json is not raised in any comment."]
    errs = outputs.report_trace_errors(report, {"1": ["1"], "2": ["9"]}, VALIDATED)
    assert "not in validated.json" in errs[0]


def test_validate_output_cli(tmp_path):
    f, v, d = tmp_path / "issues_list.md", tmp_path / "validated.json", tmp_path / "dropped.json"
    f.write_text(FULL); v.write_text(json.dumps(VALIDATED)); d.write_text(json.dumps(DROPPED))
    run = lambda *a: subprocess.run([sys.executable, "-m", "plumb", "validate-output", *a],
                                    capture_output=True, text=True, cwd=ROOT)
    r = run("issues_list", str(f), "--mode", "full", "--validated", str(v), "--dropped", str(d))
    assert r.returncode == 0 and r.stdout.strip() == "OK"
    rep, trace = tmp_path / "mock_report.txt", tmp_path / "trace.json"
    rep.write_text("Referee Report on A Fake Paper\n\n1. A fake comment.\n")
    trace.write_text(json.dumps({"1": ["7"]}))
    r = run("report", str(rep), "--trace", str(trace), "--validated", str(v))
    assert r.returncode == 1 and "not in validated.json" in r.stdout


def test_flattened_page_citation_is_accepted():
    """annotate_pdf.py's display form 'ms p. X, PDF p. Y' (comma, no nested parens) must
    pass the both-page-numbers check the same as the nested 'ms p. X (PDF p. Y)' form."""
    flat = FULL.replace("(ms p. 9 (PDF p. 11))", "(ms p. 9, PDF p. 11)")
    assert outputs.validate_issues_list(flat, "full") == []
    flat_approx = FACTS.replace("Where: ms p. 4 (PDF p. 6, approximate)", "Where: ms p. 4, PDF p. 6, approximate")
    assert outputs.validate_issues_list(flat_approx, "facts_only") == []


def test_report_with_majors_only_and_no_minor_comments_passes(tmp_path):
    """With no Minor issue in validated.json the report has no MINOR COMMENTS section, and the
    report check and the trace check both accept it."""
    majors = [{"id": "1", "title": "Fake one", "severity": "Undermines the main claim"},
              {"id": "2", "title": "Fake two", "severity": "Weakens a claim"}]
    text = ("Referee Report on A Fake Paper\n\nMAJOR COMMENTS\n\n1. First fake comment.\n\n"
            "2. Second fake comment.\n\nREFERENCES\n\nFake, A. (2020). A fake title. Fake Journal, 1(1), 1-2.\n")
    assert "MINOR COMMENTS" not in text
    assert outputs.validate_report(text) == []
    assert outputs.report_trace_errors(text, {"1": ["1"], "2": ["2"]}, majors) == []
    rep, trace, v = tmp_path / "mock_report.txt", tmp_path / "trace.json", tmp_path / "validated.json"
    rep.write_text(text); trace.write_text(json.dumps({"1": ["1"], "2": ["2"]})); v.write_text(json.dumps(majors))
    r = subprocess.run([sys.executable, "-m", "plumb", "validate-output", "report", str(rep), "--trace", str(trace),
                        "--validated", str(v)], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0 and r.stdout.strip() == "OK", r.stdout


ALL_MINOR = """## Issues

## Minor issues

- 1. A fake table omits its sample size. (ms p. 9, PDF p. 11)
- 2. A fake figure has no axis label. (PDF p. 12)

## What I left out

Nothing.

## Dropped items

- A fake third point: overruled in the audit.
"""

EMPTY = """## Issues

No issues survived the checks.

## What I left out

Nothing.

## Dropped items

- A fake third point: overruled in the audit.
"""


def test_full_list_with_only_minor_issues_passes():
    kept = [{"id": "1", "severity": "Minor", "summary": "A fake table omits its sample size."},
            {"id": "2", "severity": "Minor", "summary": "A fake figure has no axis label."}]
    assert outputs.validate_issues_list(ALL_MINOR, "full", kept, DROPPED) == []


def test_full_list_with_no_issues_passes_with_its_one_line():
    assert outputs.validate_issues_list(EMPTY, "full", [], DROPPED) == []
    bad = EMPTY.replace("No issues survived the checks.\n\n", "")
    assert any("No issues survived the checks." in e for e in outputs.validate_issues_list(bad, "full", [], DROPPED))


def test_full_list_still_needs_numbered_items_when_a_major_survives():
    kept = [{"id": "1", "severity": "Weakens a claim", "summary": "A fake table omits its sample size."},
            {"id": "2", "severity": "Minor", "summary": "A fake figure has no axis label."}]
    errs = outputs.validate_issues_list(ALL_MINOR, "full", kept, DROPPED)
    assert any("No numbered '### N. title' items found." in e for e in errs)


def test_full_mode_recommendation_check_covers_the_dropped_appendix():
    bad = FULL.replace("- A fake third point: overruled in the audit.",
                       "- A fake third point: overruled in the audit.\n\nRecommendation: reject.")
    assert any("recommendation" in e for e in outputs.validate_issues_list(bad, "full"))
    errs = outputs.validate_issues_list(FULL.replace("Nothing beyond the minor list.", "Recommendation: reject."), "full")
    assert sum("recommendation" in e for e in errs) == 1


def test_report_with_no_surviving_issue_passes(tmp_path):
    text = f"Referee Report on A Fake Paper\n\n{outputs.REPORT_NO_ISSUES}\n"
    assert outputs.validate_report(text, validated=[]) == []
    assert outputs.report_trace_errors(text, {}, []) == []
    assert any("numbered" in e for e in outputs.validate_report("Referee Report on A Fake Paper\n\nNothing.\n",
                                                                 validated=[]))
    assert any("numbered" in e for e in outputs.validate_report(text))
    rep, trace, v = tmp_path / "mock_report.txt", tmp_path / "trace.json", tmp_path / "validated.json"
    rep.write_text(text); trace.write_text("{}"); v.write_text("[]")
    r = subprocess.run([sys.executable, "-m", "plumb", "validate-output", "report", str(rep), "--trace", str(trace),
                        "--validated", str(v)], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0 and r.stdout.strip() == "OK", r.stdout


def test_report_never_talks_about_the_tool_that_wrote_it():
    """A mock report reads as a human referee's: no word on skipped checks, files, or the tool."""
    base = "Referee Report on A Fake Paper\n\nMAJOR COMMENTS\n\n1. The control group changes in Table 3.\n\nREFERENCES\n\nNone.\n"
    assert outputs.tool_talk_errors(base) == []
    for leak in ("Setting research and timeline research were skipped by design, because the paper uses no data.",
                 "Plumb flagged this table.", "At the check-in the author kept this point.",
                 "See validated.json for the list.", "Only three issues survived the checks."):
        bad = base.replace("Table 3.", "Table 3. " + leak)
        assert any("human referee" in e for e in outputs.validate_report(bad)), leak
    # Words a referee may well use about a paper stay allowed.
    for fine in ("By design, the control group never adopts.", "The authors hold an M.D. and a Ph.D.",
                 "The robustness checks in Table 4 help.", "The talent pipeline narrows at stage two."):
        assert outputs.tool_talk_errors(base.replace("Table 3.", "Table 3. " + fine)) == [], fine
    signed = base + "\n" + outputs.DISCLOSURE_LINE + "\n"
    assert outputs.tool_talk_errors(signed) == []
    assert not any("human referee" in e for e in outputs.validate_report(signed, permission="journal"))


def test_meta_sentences_go_to_the_issues_list_and_memo_but_never_to_the_report():
    stage7 = (ROOT / "skills" / "review" / "stages" / "stage-7-output.md").read_text(encoding="utf-8")
    assert "tell whichever writer runs" not in stage7
    assert "Never pass either sentence to the report writer" in stage7
    writer = (ROOT / "skills" / "review" / "agents" / "report-writer.md").read_text(encoding="utf-8")
    assert "Write the report as a human referee would." in writer
