"""plumb validated: the three drop rules. All inputs are small fake files written by the tests."""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

import pytest

from plumb import checkin, validated

ROOT = Path(__file__).resolve().parents[1]


def _issue(id_, kind="major", severity="Weakens a claim", checkin_item=None, adjudication="judgment",
           excerpt="A fake sentence from the paper.", sources=(), title=None):
    return {"id": id_, "kind": kind, "title": title or f"Fake issue {id_}", "severity": severity,
            "adjudication": adjudication, "solvability": "new analysis", "excerpt": excerpt,
            "ms_page": 3, "summary": f"Fake summary for issue {id_}.", "checkin": checkin_item,
            "sources": list(sources)}


def _ws(tmp_path, depth="standard", before=(), after=None, flags=(), mode="full", unverified="", draft=None):
    ws = tmp_path / "ws"
    for d in ("stage-1", "stage-4", "stage-5", "stage-6"):
        (ws / d).mkdir(parents=True, exist_ok=True)
    (ws / "run.json").write_text(json.dumps({"depth": depth, "issues_list_mode": mode}))
    (ws / "stage-5" / "issues.json").write_text(json.dumps(list(before)))
    (ws / "stage-6" / "issues.json").write_text(json.dumps(list(before if after is None else after)))
    if draft is None:
        draft = "## Issues\n\n" + "\n\n".join(i.get("summary", "") for i in (before if after is None else after))
    (ws / "stage-6" / "draft.md").write_text(draft)
    (ws / "stage-1" / "flags.json").write_text(json.dumps(list(flags)))
    (ws / "stage-1" / "unverified_numbers.md").write_text(unverified)
    return ws


def _items(rows):
    return {r["item"]: r["reason"] for r in rows}


def test_all_kept_when_nothing_drops(tmp_path):
    ws = _ws(tmp_path, before=[_issue("1", checkin_item="majors:1", severity="Minor"),
                               _issue("2", checkin_item="majors:2", severity="Undermines the main claim")])
    kept, dropped = validated.build(ws)
    assert dropped == []
    assert [k["item"] for k in kept] == ["majors:2", "majors:1"]
    assert [k["id"] for k in kept] == ["1", "2"]


def test_rule_1_issue_cut_in_the_audit_is_dropped(tmp_path):
    a, b = _issue("1", checkin_item="majors:1"), _issue("2", checkin_item="majors:2")
    ws = _ws(tmp_path, before=[a, b], after=[a])
    kept, dropped = validated.build(ws)
    assert [k["item"] for k in kept] == ["majors:1"]
    assert _items(dropped) == {"majors:2": "overruled in the audit"}


def test_rule_2_major_the_user_dismissed_is_dropped(tmp_path):
    ws = _ws(tmp_path, before=[_issue("1", checkin_item="majors:1"), _issue("2", checkin_item="majors:2")])
    checkin.record(ws, "majors", "majors:2", "A. Keep it as a major issue (Recommended) | Fake.",
                   "C. The paper already addresses this | Fake.")
    kept, dropped = validated.build(ws)
    assert [k["item"] for k in kept] == ["majors:1"]
    assert _items(dropped) == {"majors:2": "you dismissed it"}


def test_rule_2_auto_answer_counts_as_kept(tmp_path):
    ws = _ws(tmp_path, before=[_issue("1", checkin_item="majors:1")])
    checkin.record(ws, "majors", "majors:1", "A. Keep it as a major issue (Recommended) | Fake.",
                   "A. Keep it as a major issue (Recommended) | Fake.", note="auto")
    kept, dropped = validated.build(ws)
    assert [k["item"] for k in kept] == ["majors:1"] and dropped == []


def test_rule_2_pruned_major_is_listed_as_dismissed(tmp_path):
    ws = _ws(tmp_path)
    (ws / "stage-4" / "questions.json").write_text(json.dumps([
        {"id": "majors:4", "stop": "majors", "text": "A fake pruned issue. More text.", "options": [],
         "recommended": "", "depends_on": ["against:1"], "prune_if": {"against:1": "C"}}]))
    checkin.record(ws, "against", "against:1", "A. Plausible, investigate further (Recommended) | Fake.",
                   "C. Not plausible here | Fake.")
    _, dropped = validated.build(ws)
    assert dropped == [{"item": "majors:4", "title": "A fake pruned issue.", "reason": "you dismissed it"}]


def test_rule_2_dropped_minor_matched_by_its_text(tmp_path):
    minor = _issue("m2", kind="minor", severity="Minor", checkin_item="minors:5")
    minor["summary"] = "A fake minor point about labels. It matters little."
    ws = _ws(tmp_path, before=[minor])
    checkin.record(ws, "minors", "minors:2", "Keep (Recommended)", "Drop: A fake minor point about labels.")
    kept, dropped = validated.build(ws)
    assert kept == [] and _items(dropped) == {"minors:5": "you dismissed it"}


def test_rule_2_keep_only_first_three_minors(tmp_path):
    minors = [_issue(f"m{n}", kind="minor", severity="Minor", checkin_item=f"minors:{n}") for n in range(1, 6)]
    ws = _ws(tmp_path, before=minors)
    checkin.record(ws, "minors", "minors:list", "A. Keep all (Recommended)", "B. Keep only the first three")
    kept, dropped = validated.build(ws)
    assert [k["item"] for k in kept] == ["minors:1", "minors:2", "minors:3"]
    assert _items(dropped) == {"minors:4": "you dismissed it", "minors:5": "you dismissed it"}


def test_rule_2_minor_matched_by_text_survives_renumbering(tmp_path):
    # Synthesis renumbered the minors: the "Drop:" answer was recorded against "minors:2", but
    # its text names whichever minor is now numbered 5. The dismissal must follow the text, not
    # the stale key, or the minor the user kept gets dropped and the one they dropped is kept.
    m1 = _issue("m1", kind="minor", severity="Minor", checkin_item="minors:2")
    m1["summary"] = "Alpha point about labels. It matters little."
    m2 = _issue("m2", kind="minor", severity="Minor", checkin_item="minors:5")
    m2["summary"] = "Beta point about labels. It matters little."
    ws = _ws(tmp_path, before=[m1, m2])
    checkin.record(ws, "minors", "minors:2", "Keep (Recommended)", "Drop: Beta point about labels.")
    kept, dropped = validated.build(ws)
    assert [k["item"] for k in kept] == ["minors:2"]
    assert _items(dropped) == {"minors:5": "you dismissed it"}


def test_rule_2_suffixed_replay_id_is_not_double_counted(tmp_path):
    # The check-in replay protocol answers a re-asked question under a suffixed id ("majors:1:r")
    # and then copies that same answer under the base id ("majors:1") so later stages see it. The
    # dismissal is one event, not two.
    ws = _ws(tmp_path, before=[_issue("1", checkin_item="majors:1")])
    checkin.record(ws, "majors", "majors:1:r", "A. Keep it as a major issue (Recommended) | Fake.",
                   "C. The paper already addresses this | Fake.")
    checkin.record(ws, "majors", "majors:1", "A. Keep it as a major issue (Recommended) | Fake.",
                   "C. The paper already addresses this | Fake.", note="replayed; judgment")
    kept, dropped = validated.build(ws)
    assert kept == []
    assert dropped == [{"item": "majors:1", "title": "Fake issue 1", "reason": "you dismissed it"}]


def _flag(item, kind="number", **extra):
    base = {"item": item, "kind": kind, "title": f"Fake flag {item}", "summary": f"Fake flag summary {item}.",
            "excerpt": None, "ms_page": 4}
    base.update(extra)
    return base


def test_rule_3_issue_on_unverified_numbers_is_dropped(tmp_path):
    flag = _flag("numbers:text:1", cells=["Table 2:3:4"])
    ws = _ws(tmp_path, before=[_issue("1", adjudication="paper", sources=["numbers:text:1"])], flags=[flag],
             unverified="- cell `Table 2:3:4`, p. 9\n")
    kept, dropped = validated.build(ws)
    assert kept == []
    assert _items(dropped) == {"numbers:text:1": "numbers not verified", "issue 1": "numbers not verified",
                               "cell:Table 2:3:4": "numbers not verified"}


def test_rule_3_reference_lookup_failed_is_dropped(tmp_path):
    ws = _ws(tmp_path, depth="quick", flags=[_flag("ref:1", kind="reference", lookup_failed=True),
                                            _flag("ref:2", kind="reference", lookup_failed=False)])
    kept, dropped = validated.build(ws)
    assert [k["item"] for k in kept] == ["ref:2"]
    assert _items(dropped) == {"ref:1": "lookup failed"}


def test_quick_depth_applies_only_rule_3_and_is_facts_only(tmp_path):
    ws = tmp_path / "ws"
    (ws / "stage-1").mkdir(parents=True)
    (ws / "run.json").write_text(json.dumps({"depth": "quick", "issues_list_mode": "full"}))
    (ws / "stage-1" / "flags.json").write_text(json.dumps([
        _flag("numbers:text:1", cells=["Table 1:1:1"]), _flag("numbers:arith:T1:c:sum", table="Table 3"),
        _flag("numbers:table:x", kind="table")]))
    (ws / "stage-1" / "unverified_numbers.md").write_text("- table `Table 3`, p. 12\n")
    kept, dropped = validated.build(ws)
    assert [k["item"] for k in kept] == ["numbers:text:1"]
    assert kept[0]["kind"] == "number" and kept[0]["severity"] == "Minor"
    assert _items(dropped) == {"numbers:arith:T1:c:sum": "numbers not verified", "table:Table 3": "numbers not verified"}


def test_extraction_error_answer_drops_the_flag(tmp_path):
    ws = _ws(tmp_path, depth="quick", flags=[_flag("numbers:text:2")])
    checkin.record(ws, "numbers", "numbers:text:2", "A. Real problem in the paper (Recommended)", "B. Extraction error")
    kept, dropped = validated.build(ws)
    assert kept == [] and _items(dropped) == {"numbers:text:2": "you marked it an extraction error"}


def test_pack_flag_answered_b_drops_with_its_own_reason(tmp_path):
    ws = _ws(tmp_path, depth="quick", flags=[_flag("numbers:pack:nonlinear:1")])
    checkin.record(ws, "numbers", "numbers:pack:nonlinear:1", "A. Real problem in the paper (Recommended)",
                   "B. Not a problem or misread")
    kept, dropped = validated.build(ws)
    assert kept == [] and _items(dropped) == {"numbers:pack:nonlinear:1": "you marked it not a problem or misread"}


def test_facts_only_keeps_settled_issues_and_unfolded_facts(tmp_path):
    ws = _ws(tmp_path, mode="facts_only",
             before=[_issue("1", adjudication="judgment"), _issue("2", adjudication="paper", sources=["numbers:text:1"]),
                     _issue("3", adjudication="external", excerpt=None)],
             flags=[_flag("numbers:text:1"), _flag("numbers:text:2")])
    kept, _ = validated.build(ws)
    assert [k["title"] for k in kept] == ["Fake issue 2", "Fake issue 3", "Fake flag numbers:text:2"]


def test_full_mode_leaves_stage_1_facts_to_synthesis(tmp_path):
    ws = _ws(tmp_path, before=[_issue("1")], flags=[_flag("numbers:text:1")])
    kept, _ = validated.build(ws)
    assert [k["kind"] for k in kept] == ["major"]


def test_missing_excerpt_on_a_judgment_issue(tmp_path):
    ws = _ws(tmp_path, before=[_issue("1", excerpt=""), _issue("2", adjudication="external", excerpt=None)])
    with pytest.raises(validated.MissingExcerpt) as err:
        validated.build(ws)
    assert [i["id"] for i in err.value.issues] == ["1"]
    kept, _ = validated.build(ws, allow_missing_excerpt=True)
    assert kept[0]["excerpt"] is None


def test_every_dropped_item_is_written_with_its_reason(tmp_path):
    a, b = _issue("1", checkin_item="majors:1"), _issue("2", checkin_item="majors:2")
    ws = _ws(tmp_path, before=[a, b], after=[a], flags=[_flag("ref:1", kind="reference", lookup_failed=True)])
    assert validated.write(ws) == {"kept": 1, "dropped": 2}
    dropped = json.loads((ws / "stage-7" / "dropped.json").read_text())
    assert {d["reason"] for d in dropped} == {"overruled in the audit", "lookup failed"}
    assert all(set(d) == {"item", "title", "reason"} for d in dropped)
    assert json.loads((ws / "stage-7" / "validated.json").read_text())[0]["id"] == "1"


def test_each_item_gets_one_reason_the_most_specific_first(tmp_path):
    # Minors dropped at the minors check-in are not in the regenerated draft, so the adjudicator
    # leaves them out of stage 6. The user's answer is still the reason.
    minors = [_issue(f"m{n}", kind="minor", severity="Minor", checkin_item=f"minors:{n}") for n in range(1, 6)]
    minors[1]["summary"] = "A fake minor point about labels. It matters little."
    cut = _issue("1", checkin_item="majors:1", adjudication="paper", sources=["numbers:text:1"])
    ws = _ws(tmp_path, before=[cut] + minors, after=minors[2:3],
             flags=[_flag("numbers:text:1", cells=["Table 2:3:4"])], unverified="- cell `Table 2:3:4`, p. 9\n")
    checkin.record(ws, "minors", "minors:list", "A. Keep all (Recommended)", "B. Keep only the first three")
    checkin.record(ws, "minors", "minors:2", "Keep (Recommended)", "Drop: A fake minor point about labels.")
    kept, dropped = validated.build(ws)
    assert [k["item"] for k in kept] == ["minors:3"]
    items = [d["item"] for d in dropped]
    assert len(items) == len(set(items)), items
    assert _items(dropped) == {"numbers:text:1": "numbers not verified", "cell:Table 2:3:4": "numbers not verified",
                               "majors:1": "overruled in the audit", "minors:1": "overruled in the audit",
                               "minors:2": "you dismissed it", "minors:4": "you dismissed it",
                               "minors:5": "you dismissed it"}


def test_restored_issue_keeps_its_id_and_is_kept_once(tmp_path):
    a = _issue("1", checkin_item="majors:1")
    restored = dict(a, title="Fake issue 1, restored")
    ws = _ws(tmp_path, before=[a], after=[restored])
    kept, dropped = validated.build(ws)
    assert [k["title"] for k in kept] == ["Fake issue 1, restored"] and dropped == []
    assert kept[0]["source"] == "1"


def test_draft_review_drop_counts_as_dismissed(tmp_path):
    a, added = _issue("1", checkin_item="majors:1"), _issue("a1")
    ws = _ws(tmp_path, before=[a], after=[a, added])
    kept, _ = validated.build(ws)
    assert sorted(k["source"] for k in kept) == ["1", "a1"]
    checkin.record(ws, "draft", "draft:drop:1", "Keep (Recommended)", "Drop: Fake issue 1")
    checkin.record(ws, "draft", "draft:drop:a1", "Keep (Recommended)", "Drop: Fake issue a1")
    kept, dropped = validated.build(ws)
    assert kept == []
    assert _items(dropped) == {"majors:1": "you dismissed it", "issue a1": "you dismissed it"}


def test_draft_review_drop_of_a_fact(tmp_path):
    ws = _ws(tmp_path, depth="quick", flags=[_flag("numbers:text:1"), _flag("numbers:text:2")])
    checkin.record(ws, "draft", "draft:drop:numbers:text:2", "Keep (Recommended)", "Drop: Fake flag")
    kept, dropped = validated.build(ws)
    assert [k["source"] for k in kept] == ["numbers:text:1"]
    assert _items(dropped) == {"numbers:text:2": "you dismissed it"}


def test_facts_only_skips_the_excerpt_check_for_judgment_issues(tmp_path):
    ws = _ws(tmp_path, mode="facts_only", before=[_issue("1", excerpt=""), _issue("2", adjudication="paper")])
    kept, _ = validated.build(ws)
    assert [k["title"] for k in kept] == ["Fake issue 2"]


def test_cli(tmp_path):
    ws = _ws(tmp_path, before=[_issue("1", excerpt="")])
    run = lambda *a: subprocess.run([sys.executable, "-m", "plumb", "validated", str(ws), *a],
                                    capture_output=True, text=True, cwd=ROOT)
    r = run()
    assert r.returncode == 1 and "has no excerpt" in r.stdout
    r = run("--allow-missing-excerpt")
    assert r.returncode == 0 and json.loads(r.stdout) == {"kept": 1, "dropped": 0}
    (ws / "stage-6" / "issues.json").unlink()
    r = run()
    assert r.returncode == 2 and "missing" in r.stdout


# The outputs carry only audited text: every kept issue's summary is in stage-6/draft.md.

def test_summary_not_in_the_audited_draft_fails(tmp_path):
    a, b = _issue("1", checkin_item="majors:1"), _issue("2", checkin_item="majors:2")
    ws = _ws(tmp_path, before=[a, b], draft="## Issues\n\n### 1. Fake\n\nFake summary for issue 1.\n")
    with pytest.raises(validated.UnauditedSummary) as err:
        validated.build(ws)
    assert [i["id"] for i in err.value.issues] == ["2"]
    assert "stage-6/draft.md" in str(err.value) and "Issue 2" in str(err.value)


def test_summary_found_across_a_line_break_and_a_page_citation(tmp_path):
    a = _issue("1", checkin_item="majors:1")
    a["summary"] = "The fake estimate on page three rests on one fake sample."
    ws = _ws(tmp_path, before=[a], draft="### 1. Fake\n\nThe fake estimate on page three (ms p. 3 (PDF p. 5))\n"
                                         "rests on one fake sample. More text.\n")
    kept, _ = validated.build(ws)
    assert [k["source"] for k in kept] == ["1"]


def test_dropped_issue_summary_is_not_checked(tmp_path):
    a, b = _issue("1", checkin_item="majors:1"), _issue("2", checkin_item="majors:2")
    ws = _ws(tmp_path, before=[a, b], after=[a], draft="Fake summary for issue 1.")
    kept, _ = validated.build(ws)
    assert [k["source"] for k in kept] == ["1"]


def test_empty_summary_fails(tmp_path):
    a = _issue("1", checkin_item="majors:1")
    a["summary"] = ""
    ws = _ws(tmp_path, before=[a], draft="Some fake audited text.")
    with pytest.raises(validated.UnauditedSummary):
        validated.build(ws)


def test_missing_audited_draft_is_an_input_error(tmp_path):
    ws = _ws(tmp_path, before=[_issue("1")])
    (ws / "stage-6" / "draft.md").unlink()
    with pytest.raises(validated.InputError, match="draft.md"):
        validated.build(ws)


def test_cli_unaudited_summary_exits_3(tmp_path):
    ws = _ws(tmp_path, before=[_issue("1")], draft="Other fake text.")
    r = subprocess.run([sys.executable, "-m", "plumb", "validated", str(ws)], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 3 and "Issue 1" in r.stdout and "word for word" in r.stdout


# Every file plumb validated loads is checked for shape; a bad one is exit 2, one line, naming it.

@pytest.mark.parametrize("stage", ["stage-5", "stage-6"])
def test_issue_file_that_is_not_a_list_is_an_input_error(tmp_path, stage):
    ws = _ws(tmp_path, before=[_issue("1")])
    (ws / stage / "issues.json").write_text(json.dumps({"issues": [_issue("1")]}))
    with pytest.raises(validated.InputError, match=f"{stage}/issues.json"):
        validated.build(ws)


@pytest.mark.parametrize("field", ["id", "kind", "summary", "checkin"])
def test_issue_record_missing_a_field_is_an_input_error(tmp_path, field):
    bad = _issue("1")
    del bad[field]
    ws = _ws(tmp_path, before=[_issue("1")], after=[bad])
    with pytest.raises(validated.InputError, match=f"record 1 has no '{field}'"):
        validated.build(ws)


def test_flag_and_question_and_run_shapes_are_checked(tmp_path):
    ws = _ws(tmp_path, depth="quick", flags=[{"kind": "number"}])
    with pytest.raises(validated.InputError, match="flags.json: record 1 has no 'item'"):
        validated.build(ws)
    ws = _ws(tmp_path / "b", before=[_issue("1")])
    (ws / "stage-4" / "questions.json").write_text(json.dumps([["not a record"]]))
    with pytest.raises(validated.InputError, match="questions.json: record 1 is not a JSON object"):
        validated.build(ws)
    (ws / "stage-4" / "questions.json").unlink()
    (ws / "run.json").write_text("[]")
    with pytest.raises(validated.InputError, match="run.json must be a JSON object"):
        validated.build(ws)


def test_cli_malformed_issue_file_exits_2_with_one_line(tmp_path):
    ws = _ws(tmp_path, before=[_issue("1")])
    (ws / "stage-6" / "issues.json").write_text(json.dumps({"issues": []}))
    r = subprocess.run([sys.executable, "-m", "plumb", "validated", str(ws)], capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 2 and "stage-6/issues.json" in r.stdout
    assert len(r.stdout.strip().splitlines()) == 1 and "Traceback" not in r.stderr


def test_check_issues_cli(tmp_path):
    ws = _ws(tmp_path, before=[_issue("1")])
    run = lambda p: subprocess.run([sys.executable, "-m", "plumb", "check-issues", str(p)],
                                   capture_output=True, text=True, cwd=ROOT)
    r = run(ws / "stage-5" / "issues.json")
    assert r.returncode == 0 and r.stdout.strip() == "OK"
    (ws / "stage-6" / "issues.json").write_text("[{\"id\": \"1\"}")
    r = run(ws / "stage-6" / "issues.json")
    assert r.returncode == 2 and "not valid JSON" in r.stdout
    r = run(ws / "stage-6" / "missing.json")
    assert r.returncode == 2 and "missing" in r.stdout


# Runs from before flags.json wrote unverified_numbers.md "one line each with the page".
LEGACY_UNVERIFIED = """# Unverified numbers

- numbers:cell:Table 2:3:4, p. 9
- `Table 2:5:1` (p. 10)
- Table 4, row 2, column 3 (p. 11)
- numbers:table:Table 5, p. 12
- Table 6, whole table, p. 13
"""


def test_old_unverified_line_forms_are_read(tmp_path):
    ws = _ws(tmp_path, unverified=LEGACY_UNVERIFIED)
    assert validated.unverified(ws) == (["Table 2:3:4", "Table 2:5:1", "Table 4:2:3"], ["Table 5", "Table 6"])
    assert validated.unparsed_unverified(ws) == []
    _, dropped = validated.build(ws)
    assert _items(dropped) == {"cell:Table 2:3:4": "numbers not verified", "cell:Table 2:5:1": "numbers not verified",
                               "cell:Table 4:2:3": "numbers not verified", "table:Table 5": "numbers not verified",
                               "table:Table 6": "numbers not verified"}


def test_unparsed_unverified_lines_are_reported(tmp_path):
    ws = _ws(tmp_path, unverified="None.\n\n- cell `Table 1:1:1`, p. 2\n- Some fake number on page four\n")
    assert validated.unverified(ws) == (["Table 1:1:1"], [])
    assert validated.unparsed_unverified(ws) == ["- Some fake number on page four"]


@pytest.mark.parametrize("record,draft", [
    ("The fake estimate rests on one fake sample.", "**The fake estimate** rests on _one_ fake `sample`."),
    ("**The fake estimate** rests on *one* fake `sample`.", "The fake estimate rests on one fake sample."),
])
def test_summary_match_ignores_markdown_emphasis(tmp_path, record, draft):
    a = _issue("1", checkin_item="majors:1")
    a["summary"] = record
    ws = _ws(tmp_path, before=[a], draft=f"### 1. Fake\n\n{draft}\n")
    kept, _ = validated.build(ws)
    assert [k["source"] for k in kept] == ["1"]


# Points lost inside the pipeline reach the dropped items too: findings left out at synthesis
# (every exclusion but a duplicate) and distinct points the audit cut from issues it kept.

COVERAGE = """# Synthesis coverage

| finding_id | source_file | severity | disposition | target | rationale |
|---|---|---|---|---|---|
| core-1 | stage-4/core_problem.md | Weakens a claim | INCLUDED_MAJOR | 1 | Lead |
| adj-1 | stage-3/adjacent.md | Weakens a claim | MERGED | 1 | Carried in issue 1 |
| dup-1 | stage-4/face_validity.md | Minor | EXCLUDED | core-1 | duplicate_of: core-1 |
| fn-4 | stage-2/dgp_map.md | Minor | EXCLUDED | footnote 4 | addressed_by_paper_appendix: footnote 4 |
| low-1 | stage-1/flags.json | Minor | EXCLUDED | - | low_confidence_minor_only: Low (a fake \\| note) |
| alt-2 | stage-3/alternatives.md | Weakens a claim | EXCLUDED | - | user_ruled_out: against:2 |
"""


def test_synthesis_exclusions_are_dropped_except_duplicates(tmp_path):
    ws = _ws(tmp_path, before=[_issue("1", checkin_item="majors:1")])
    (ws / "synthesis_coverage.md").write_text(COVERAGE)
    kept, dropped = validated.build(ws)
    assert [k["item"] for k in kept] == ["majors:1"]
    assert _items(dropped) == {
        "finding fn-4": "left out because the paper already does it",
        "finding low-1": "left out as a low-confidence minor point",
        "finding alt-2": "you ruled out the alternative it rests on",
    }
    assert next(d for d in dropped if d["item"] == "finding fn-4")["source"] == "stage-2/dgp_map.md"


def test_points_cut_from_kept_issues_are_dropped(tmp_path):
    ws = _ws(tmp_path, before=[_issue("1", checkin_item="majors:1")])
    (ws / "stage-6" / "cut_points.json").write_text(json.dumps(
        [{"issue": "1", "point": "the classic lay-belief work in personnel selection"}]))
    kept, dropped = validated.build(ws)
    assert [k["item"] for k in kept] == ["majors:1"]
    assert dropped == [{"item": "issue 1", "title": "the classic lay-belief work in personnel selection",
                        "reason": validated.CUT_PART}]


def test_no_cut_points_file_drops_nothing(tmp_path):
    ws = _ws(tmp_path, before=[_issue("1", checkin_item="majors:1")])
    assert validated.build(ws)[1] == []


def test_bad_cut_points_file_is_an_input_error(tmp_path):
    ws = _ws(tmp_path, before=[_issue("1", checkin_item="majors:1")])
    (ws / "stage-6" / "cut_points.json").write_text(json.dumps({"issue": "1"}))
    with pytest.raises(validated.InputError):
        validated.build(ws)


def test_prompts_keep_points_over_ceilings_and_record_cuts():
    def flat(rel):
        return " ".join((ROOT / rel).read_text(encoding="utf-8").split())
    adj = flat("skills/review/agents/adjudicator.md")
    assert "Nor are the word and reference ceilings" in adj
    assert "`{WORKSPACE}/stage-6/cut_points.json`" in adj and "Write `[]` when you cut none" in adj
    std = flat("skills/review/agents/standards-auditor.md")
    assert "Propose cutting a reference only when the point it carries stands without it" in std
    syn = flat("skills/review/agents/synthesis.md")
    assert "never mark a finding MERGED in name only" in syn
    writer = flat("skills/review/agents/issues-list-writer.md")
    assert "An entry with a `source` is a finding left out at synthesis" in writer
    aud = flat("skills/review/agents/contribution-auditor.md")
    assert "past 10-20 years" not in aud and "of any age" in aud
    assert "Which conversation in its own field does it join?" not in aud
