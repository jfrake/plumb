"""plumb.run_compare: issues and Judgment calls matched across repeat runs of one paper. Every run
folder here is a small fake written by the test."""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from plumb import audit, run_compare

ROOT = Path(__file__).resolve().parents[1]

UNDERMINES = "Undermines the main claim"
WEAKENS = "Weakens a claim"


def _issue(id_, summary="", excerpt="", ms_page=None, severity=WEAKENS, title="", kind="major", **extra):
    rec = {"id": id_, "kind": kind, "title": title, "severity": severity, "adjudication": "judgment",
           "solvability": "new analysis", "summary": summary, "excerpt": excerpt, "ms_page": ms_page,
           "checkin": f"majors:{id_}", "sources": []}
    rec.update(extra)
    return rec


def _run(tmp_path, name, issues=None, depth="standard", pdf="paper.pdf", events=(), stage4=None, extra=None):
    """A fake run folder plumb_output/<name>/ with its .workspace. issues=None writes no stage-5 file.
    events are (stop, item, answer) triples recorded as Auto check-in answers."""
    ws = tmp_path / "plumb_output" / name / ".workspace"
    ws.mkdir(parents=True)
    run = {"depth": depth, "packs": ["archival"], "pdf_path": str(tmp_path / "drafts" / pdf)}
    run.update(extra or {})
    (ws / "run.json").write_text(json.dumps(run), encoding="utf-8")
    if issues is not None:
        (ws / "stage-5").mkdir()
        (ws / "stage-5" / "issues.json").write_text(json.dumps(issues), encoding="utf-8")
    for fname, text in (stage4 or {}).items():
        (ws / "stage-4").mkdir(exist_ok=True)
        (ws / "stage-4" / fname).write_text(text, encoding="utf-8")
    for stop, item, answer in events:
        audit.log_event(ws, "checkin", stop=stop, item=item, recommended="A. Keep", answer=answer, note="auto")
    return ws.parent


def _stage4(check, excerpt):
    return f"# Design\n\n## Issues\n\n1. Something.\n   Check: {check}.\n   Excerpt: \"{excerpt}\"\n"


# Three runs with partial overlap: issue 1 in every run by check id (severity disagrees in run b),
# issue 2 in runs a and b by text, and one issue unique to each run.
CONTROL_A = "The control group includes regions treated later in the panel, so the comparison is contaminated."
CONTROL_B = "The control group includes regions that are treated later in the panel; the comparison is contaminated."


def _three_runs(tmp_path):
    a = _run(tmp_path, "run-a", issues=[
        _issue("1", summary="Parallel trends fail in the pre-period.", severity=UNDERMINES, check="DD1"),
        _issue("2", summary=CONTROL_A),
        _issue("3", summary="The appendix tables omit the number of observations.", severity="Minor")])
    b = _run(tmp_path, "run-b", issues=[
        _issue("1", summary="Pre-trends are visible in Figure 2.", severity=WEAKENS, check="DD1"),
        _issue("2", summary=CONTROL_B),
        _issue("4", summary="The instrument fails the exclusion restriction because lenders see the shock.",
               severity=UNDERMINES)])
    c = _run(tmp_path, "run-c", issues=[
        _issue("1", summary="Leads are jointly significant.", severity=UNDERMINES, check="DD1"),
        _issue("5", summary="Standard errors are clustered at the wrong level.", severity="Minor")])
    return a, b, c


def _groups(card):
    """{frozenset of (run, id)} -> {run: strategy} for every group in the card."""
    return {frozenset((r, m["id"]) for r, m in g["members"].items()): {r: m["strategy"] for r, m in g["members"].items()}
            for g in card["groups"]}


# --- guards -----------------------------------------------------------------------------------


def test_one_run_is_refused(tmp_path):
    a = _run(tmp_path, "run-a", issues=[])
    with pytest.raises(run_compare.CompareError, match="at least two"):
        run_compare.compare_paths([a])


def test_runs_of_different_pdfs_are_refused_by_name(tmp_path):
    a = _run(tmp_path, "run-a", issues=[], pdf="paper.pdf")
    b = _run(tmp_path, "run-b", issues=[], pdf="other.pdf")
    with pytest.raises(run_compare.CompareError) as exc:
        run_compare.compare_paths([a, b])
    assert "paper.pdf" in str(exc.value) and "other.pdf" in str(exc.value)


def test_a_recorded_sha_decides_before_the_file_name(tmp_path):
    a = _run(tmp_path, "run-a", issues=[], pdf="paper.pdf", extra={"pdf_sha256": "aaa"})
    b = _run(tmp_path, "run-b", issues=[], pdf="paper.pdf", extra={"pdf_sha256": "bbb"})
    with pytest.raises(run_compare.CompareError, match="aaa"):
        run_compare.compare_paths([a, b])


def test_missing_stage_5_is_an_error_unless_quick(tmp_path):
    a = _run(tmp_path, "run-a", issues=[_issue("1", summary="x")])
    b = _run(tmp_path, "run-b", issues=None)
    with pytest.raises(run_compare.CompareError, match="stage-5/issues.json"):
        run_compare.compare_paths([a, b])
    q = _run(tmp_path, "run-q", issues=None, depth="quick")
    card = run_compare.compare_paths([a, q])
    assert [r["issues"] for r in card["runs"]] == [1, 0]
    assert card["runs"][1]["depth"] == "quick"
    assert card["unmatched"] == {"run-a": ["1"], "run-q": []}


# --- matching -----------------------------------------------------------------------------------


def test_explicit_check_id_matches_first_whatever_the_text(tmp_path):
    a = _run(tmp_path, "run-a", issues=[_issue("1", summary="Nothing alike here.", ms_page=3, check="DD1")])
    b = _run(tmp_path, "run-b", issues=[_issue("7", summary="Entirely different words.", ms_page=9, check="DD1")])
    card = run_compare.compare_paths([a, b])
    assert _groups(card) == {frozenset({("run-a", "1"), ("run-b", "7")}): {"run-a": None, "run-b": "check"}}
    assert card["matches_by_source"] == {"hand": 0, "check": 1, "stage-4": 0, "text": 0}


def test_different_explicit_check_ids_veto_a_text_match(tmp_path):
    a = _run(tmp_path, "run-a", issues=[_issue("1", summary=CONTROL_A, check="DD1")])
    b = _run(tmp_path, "run-b", issues=[_issue("1", summary=CONTROL_A, check="DD4")])
    card = run_compare.compare_paths([a, b])
    assert card["unmatched"] == {"run-a": ["1"], "run-b": ["1"]}


def test_stage_4_recovered_id_needs_the_same_page(tmp_path):
    a = _run(tmp_path, "run-a", issues=[_issue("1", summary="Attrition.", excerpt="Firms that exit are dropped.", ms_page=7)],
             stage4={"design.md": _stage4("DD2", "Firms that exit are dropped.")})
    b = _run(tmp_path, "run-b", issues=[_issue("2", summary="Survivorship.", excerpt="We drop exiting firms.", ms_page=7)],
             stage4={"design.md": _stage4("DD2", "We drop exiting firms.")})
    c = _run(tmp_path, "run-c", issues=[_issue("3", summary="Exit.", excerpt="Exiting firms leave the panel.", ms_page=9)],
             stage4={"design.md": _stage4("DD2", "Exiting firms leave the panel.")})
    card = run_compare.compare_paths([a, b, c])
    assert _groups(card) == {frozenset({("run-a", "1"), ("run-b", "2")}): {"run-a": None, "run-b": "stage-4"},
                             frozenset({("run-c", "3")}): {"run-c": None}}
    assert card["unmatched"] == {"run-a": [], "run-b": [], "run-c": ["3"]}


def test_a_shared_excerpt_matches_as_text(tmp_path):
    sentence = "We cluster standard errors at the state level."
    a = _run(tmp_path, "run-a", issues=[_issue("1", summary="Too few clusters.", excerpt=sentence)])
    b = _run(tmp_path, "run-b", issues=[_issue("4", summary="Inference is fragile.", excerpt=sentence)])
    card = run_compare.compare_paths([a, b])
    assert _groups(card) == {frozenset({("run-a", "1"), ("run-b", "4")}): {"run-a": None, "run-b": "text"}}


def test_three_runs_with_partial_overlap(tmp_path):
    a, b, c = _three_runs(tmp_path)
    card = run_compare.compare_paths([a, b, c])
    assert _groups(card) == {
        frozenset({("run-a", "1"), ("run-b", "1"), ("run-c", "1")}): {"run-a": None, "run-b": "check", "run-c": "check"},
        frozenset({("run-a", "2"), ("run-b", "2")}): {"run-a": None, "run-b": "text"},
        frozenset({("run-a", "3")}): {"run-a": None},
        frozenset({("run-b", "4")}): {"run-b": None},
        frozenset({("run-c", "5")}): {"run-c": None},
    }
    assert [r["issues"] for r in card["runs"]] == [3, 3, 2]
    assert card["unmatched"] == {"run-a": ["3"], "run-b": ["4"], "run-c": ["5"]}
    assert card["matches_by_source"] == {"hand": 0, "check": 2, "stage-4": 0, "text": 1}


def test_hand_match_joins_two_dissimilar_issues_before_the_automatic_strategies(tmp_path):
    a = _run(tmp_path, "run-a", issues=[_issue("9", summary="Alpha beta gamma delta.")])
    b = _run(tmp_path, "run-b", issues=[_issue("8", summary="Epsilon zeta eta theta.")])
    hand = tmp_path / "hand.yaml"
    hand.write_text(yaml.safe_dump([[{"run": "run-a", "id": "9"}, {"run": "run-b", "id": 8}]]), encoding="utf-8")
    card = run_compare.compare_paths([a, b], hand_matches=hand)
    assert _groups(card) == {frozenset({("run-a", "9"), ("run-b", "8")}): {"run-a": None, "run-b": "hand"}}
    assert card["matches_by_source"]["hand"] == 1
    assert card["hand_matches"] == {"file": str(hand), "pairs": 1}


def test_hand_match_naming_an_unknown_run_or_issue_is_an_error(tmp_path):
    a = _run(tmp_path, "run-a", issues=[_issue("9", summary="x")])
    b = _run(tmp_path, "run-b", issues=[_issue("8", summary="y")])
    hand = tmp_path / "hand.json"
    hand.write_text(json.dumps([[{"run": "run-a", "id": "9"}, {"run": "run-z", "id": "8"}]]), encoding="utf-8")
    with pytest.raises(run_compare.CompareError, match="run-z"):
        run_compare.compare_paths([a, b], hand_matches=hand)
    hand.write_text(json.dumps([[{"run": "run-a", "id": "9"}, {"run": "run-b", "id": "77"}]]), encoding="utf-8")
    with pytest.raises(run_compare.CompareError, match="77"):
        run_compare.compare_paths([a, b], hand_matches=hand)


# --- the two reliability numbers, and severity agreement ----------------------------------------


def test_mean_pairwise_jaccard_of_major_issues(tmp_path):
    # Major groups: a {1, 2}, b {1, 2, 4}, c {1}. ab 2/3, ac 1/2, bc 1/3; mean 1/2.
    a, b, c = _three_runs(tmp_path)
    card = run_compare.compare_paths([a, b, c])
    pairs = {tuple(p["runs"]): p for p in card["major_overlap"]["pairs"]}
    assert pairs[("run-a", "run-b")] == {"runs": ["run-a", "run-b"], "shared": 2, "union": 3, "jaccard": 2 / 3}
    assert pairs[("run-a", "run-c")] == {"runs": ["run-a", "run-c"], "shared": 1, "union": 2, "jaccard": 0.5}
    assert pairs[("run-b", "run-c")] == {"runs": ["run-b", "run-c"], "shared": 1, "union": 3, "jaccard": 1 / 3}
    assert card["major_overlap"]["mean"] == 0.5
    assert [r["major"] for r in card["runs"]] == [2, 3, 1]


def test_jaccard_is_none_when_neither_run_has_a_major_issue(tmp_path):
    a = _run(tmp_path, "run-a", issues=[_issue("1", summary="x", severity="Minor")])
    b = _run(tmp_path, "run-b", issues=[])
    card = run_compare.compare_paths([a, b])
    assert card["major_overlap"] == {"pairs": [{"runs": ["run-a", "run-b"], "shared": 0, "union": 0, "jaccard": None}],
                                     "mean": None}


def test_severity_agreement_over_matched_issues(tmp_path):
    # Group 1 is Undermines, Weakens, Undermines; group 2 is Weakens, Weakens; singletons do not count.
    a, b, c = _three_runs(tmp_path)
    card = run_compare.compare_paths([a, b, c])
    assert card["severity_agreement"] == {"matched": 2, "identical": 1, "share": 0.5}
    agree = {g["group"]: g["severity_identical"] for g in card["groups"]}
    assert agree == {1: False, 2: True, 3: None, 4: None, 5: None}


def test_judgment_items_identical_across_all_runs_overall_and_by_stop(tmp_path):
    common = [("setup", "setup:depth", "B. Standard"), ("majors", "majors:1", "A. Keep")]
    a = _run(tmp_path, "run-a", issues=[], events=common + [("read", "read:claim", "B. Narrow it"),
                                                            ("against", "against:1", "A. Yes")])
    b = _run(tmp_path, "run-b", issues=[], events=common + [("read", "read:claim", "B. Narrow it"),
                                                            ("against", "against:1", "B. No")])
    c = _run(tmp_path, "run-c", issues=[], events=common + [("read", "read:claim", "C. Drop it")])
    card = run_compare.compare_paths([a, b, c])
    j = card["judgment"]
    assert j["items"] == 3 and j["identical"] == 1 and j["share"] == 1 / 3
    assert j["by_stop"] == {"majors": {"items": 1, "identical": 1, "share": 1.0},
                            "read": {"items": 1, "identical": 0, "share": 0.0},
                            "against": {"items": 1, "identical": 0, "share": 0.0}}
    rows = {(r["stop"], r["item"]): r for r in j["rows"]}
    assert rows[("majors", "majors:1")] == {"stop": "majors", "item": "majors:1", "identical": True,
                                           "calls": {"run-a": "A", "run-b": "A", "run-c": "A"}}
    assert rows[("against", "against:1")]["calls"] == {"run-a": "A", "run-b": "B", "run-c": None}
    assert rows[("read", "read:claim")]["calls"] == {"run-a": "B", "run-b": "B", "run-c": "C"}


def test_judgment_share_is_none_with_no_judgment_items(tmp_path):
    a = _run(tmp_path, "run-a", issues=[], events=[("setup", "setup:depth", "B. Standard")])
    b = _run(tmp_path, "run-b", issues=[])
    card = run_compare.compare_paths([a, b])
    assert card["judgment"] == {"items": 0, "identical": 0, "share": None, "by_stop": {}, "rows": []}


# --- the report and the script --------------------------------------------------------------------


def test_markdown_lists_runs_groups_unmatched_and_judgment_rows(tmp_path):
    a, b, c = _three_runs(tmp_path)
    card = run_compare.compare_paths([a, b, c])
    text = run_compare.markdown(card)
    assert text.startswith("## 3 runs of paper.pdf")
    assert "| run-a | standard | 3 | 2 | 1 |" in text
    assert "mean pairwise Jaccard overlap of major issues: 0.500" in text
    assert "Judgment items identical across all runs: none recorded" in text
    assert "severity agreement over matched issues: 1 of 2" in text
    assert "matches by source: hand 0, check 2, stage-4 0, text 1" in text
    assert "| 1 | 1 (Undermines the main claim) | 1 (Weakens a claim) | 1 (Undermines the main claim) | no | check, check |" in text
    assert "| 2 | 2 (Weakens a claim) | 2 (Weakens a claim) | | yes | text |" in text
    assert "| 3 | 3 (Minor) | | | | |" in text
    assert "- run-a: 3" in text and "- run-b: 4" in text and "- run-c: 5" in text


def test_markdown_judgment_table(tmp_path):
    a = _run(tmp_path, "run-a", issues=[], events=[("majors", "majors:1", "A. Keep"), ("read", "read:claim", "B. Narrow")])
    b = _run(tmp_path, "run-b", issues=[], events=[("majors", "majors:1", "A. Keep")])
    text = run_compare.markdown(run_compare.compare_paths([a, b]))
    assert "Judgment items identical across all runs: 1 of 2 (0.500)" in text
    assert "- majors: 1 of 1" in text and "- read: 0 of 1" in text
    assert "| majors | majors:1 | A | A | yes |" in text
    assert "| read | read:claim | B | | no |" in text


def test_script_prints_the_json_then_the_markdown(tmp_path):
    a, b, c = _three_runs(tmp_path)
    out = tmp_path / "compare.json"
    proc = subprocess.run([sys.executable, str(ROOT / "eval" / "compare_runs.py"), str(a), str(b / ".workspace"), str(c),
                           "--out", str(out)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    head, sep, tail = proc.stdout.partition("\n## ")
    card = json.loads(head)
    assert card["major_overlap"]["mean"] == 0.5
    assert sep and "| 2 | 2 (Weakens a claim) |" in tail
    assert json.loads(out.read_text())["severity_agreement"]["share"] == 0.5


def test_script_takes_a_hand_match_file(tmp_path):
    a = _run(tmp_path, "run-a", issues=[_issue("9", summary="Alpha beta gamma delta.")])
    b = _run(tmp_path, "run-b", issues=[_issue("8", summary="Epsilon zeta eta theta.")])
    hand = tmp_path / "hand.yaml"
    hand.write_text(yaml.safe_dump([[{"run": "run-a", "id": "9"}, {"run": "run-b", "id": "8"}]]), encoding="utf-8")
    proc = subprocess.run([sys.executable, str(ROOT / "eval" / "compare_runs.py"), str(a), str(b),
                           "--hand-matches", str(hand)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert "matches by source: hand 1, check 0, stage-4 0, text 0" in proc.stdout
    assert f"hand matches: 1 pair from {hand}" in proc.stdout


def test_script_exits_non_zero_with_a_clear_message_for_different_pdfs(tmp_path):
    a = _run(tmp_path, "run-a", issues=[], pdf="paper.pdf")
    b = _run(tmp_path, "run-b", issues=[], pdf="other.pdf")
    proc = subprocess.run([sys.executable, str(ROOT / "eval" / "compare_runs.py"), str(a), str(b)],
                          capture_output=True, text=True)
    assert proc.returncode == 2
    assert "not of one paper" in proc.stderr and "other.pdf" in proc.stderr
    assert proc.stdout == ""


# --- review fixes ---------------------------------------------------------------------------------

FIRMS = "Standard errors are clustered at the wrong level for firms."
PANEL = "Standard errors are clustered at the wrong level in the industry year panel."


def test_best_candidate_wins_within_a_strategy_whatever_the_input_order(tmp_path):
    # A1 and B2 share every word, as do A2 and B1; A1 and B1 share most. First fit would pair A1
    # with B1. A1 and B2 are major, so the right pairing gives a Jaccard of 1.0 and the wrong one 0.
    a = _run(tmp_path, "run-a", issues=[_issue("A1", summary=FIRMS, severity=UNDERMINES),
                                        _issue("A2", summary=PANEL, severity="Minor")])
    b = _run(tmp_path, "run-b", issues=[_issue("B1", summary=PANEL, severity="Minor"),
                                        _issue("B2", summary=FIRMS, severity=UNDERMINES)])
    card = run_compare.compare_paths([a, b])
    assert set(_groups(card)) == {frozenset({("run-a", "A1"), ("run-b", "B2")}),
                                  frozenset({("run-a", "A2"), ("run-b", "B1")})}
    assert card["major_overlap"]["mean"] == 1.0


def test_excerpt_containment_outranks_word_share(tmp_path):
    sentence = "We cluster at the state level."
    a = _run(tmp_path, "run-a", issues=[_issue("A1", summary=FIRMS, excerpt=sentence)])
    b = _run(tmp_path, "run-b", issues=[_issue("B1", summary=FIRMS + " Clustering is too coarse."),
                                        _issue("B2", summary="Inference is fragile.", excerpt=sentence)])
    card = run_compare.compare_paths([a, b])
    assert frozenset({("run-a", "A1"), ("run-b", "B2")}) in _groups(card)


def test_a_check_id_on_any_group_member_vetoes_a_text_join(tmp_path):
    # b1 joined a1 by text and carries no check id; c1 reads like b1 but carries DD4 against a1's DD1.
    a = _run(tmp_path, "run-a", issues=[_issue("1", summary=FIRMS, check="DD1")])
    b = _run(tmp_path, "run-b", issues=[_issue("1", summary=FIRMS)])
    c = _run(tmp_path, "run-c", issues=[_issue("1", summary=FIRMS, check="DD4")])
    card = run_compare.compare_paths([a, b, c])
    assert set(_groups(card)) == {frozenset({("run-a", "1"), ("run-b", "1")}), frozenset({("run-c", "1")})}


def test_hand_pairs_that_tie_one_issue_to_two_issues_of_one_run_are_refused_at_load(tmp_path):
    a = _run(tmp_path, "run-a", issues=[_issue("1", summary="x")])
    b = _run(tmp_path, "run-b", issues=[_issue("2", summary="y"), _issue("3", summary="z")])
    hand = tmp_path / "hand.json"
    hand.write_text(json.dumps([[{"run": "run-a", "id": "1"}, {"run": "run-b", "id": "2"}],
                                [{"run": "run-a", "id": "1"}, {"run": "run-b", "id": "3"}]]), encoding="utf-8")
    with pytest.raises(run_compare.CompareError, match=r"run-a:1 .*run-b:2.*run-b:3"):
        run_compare.compare_paths([a, b], hand_matches=hand)


def test_a_hand_pair_that_could_not_end_in_one_group_is_an_error(tmp_path):
    # a:1 is paired with b:2 and c:3; b:2 is paired with c:4. One group cannot hold both c:3 and c:4.
    a = _run(tmp_path, "run-a", issues=[_issue("1", summary="x")])
    b = _run(tmp_path, "run-b", issues=[_issue("2", summary="y")])
    c = _run(tmp_path, "run-c", issues=[_issue("3", summary="z"), _issue("4", summary="w")])
    hand = tmp_path / "hand.json"
    hand.write_text(json.dumps([[{"run": "run-a", "id": "1"}, {"run": "run-b", "id": "2"}],
                                [{"run": "run-a", "id": "1"}, {"run": "run-c", "id": "3"}],
                                [{"run": "run-b", "id": "2"}, {"run": "run-c", "id": "4"}]]), encoding="utf-8")
    with pytest.raises(run_compare.CompareError, match=r"run-b:2 and run-c:4"):
        run_compare.compare_paths([a, b, c], hand_matches=hand)


def test_markdown_states_that_numbered_items_compare_by_number(tmp_path):
    a = _run(tmp_path, "run-a", issues=[], events=[("majors", "majors:1", "A. Keep")])
    b = _run(tmp_path, "run-b", issues=[], events=[("majors", "majors:1", "A. Keep")])
    text = run_compare.markdown(run_compare.compare_paths([a, b]))
    bullet = next(l for l in text.splitlines() if l.startswith("- Judgment items identical"))
    note = text.splitlines()[text.splitlines().index(bullet) + 1]
    assert "numbered items (majors:N, minors:N) are compared by number, not by matched issue" in note
    # The note is there even when no Judgment item was recorded.
    c = _run(tmp_path, "run-c", issues=[])
    assert "compared by number, not by matched issue" in run_compare.markdown(run_compare.compare_paths([a, c]))


def test_judgment_rows_sort_naturally_within_a_stop(tmp_path):
    ev = [("majors", f"majors:{n}", "A. Keep") for n in (10, 2, 1)] + [("numbers", "numbers:text:3", "A. Keep")]
    a = _run(tmp_path, "run-a", issues=[], events=ev)
    b = _run(tmp_path, "run-b", issues=[], events=ev)
    rows = run_compare.compare_paths([a, b])["judgment"]["rows"]
    assert [r["item"] for r in rows] == ["numbers:text:3", "majors:1", "majors:2", "majors:10"]


def test_same_named_run_folders_are_told_apart_by_the_shortest_path_suffix(tmp_path):
    # eval/run_fixture.sh names every run by its date, so three repeat runs share "2026-10-05".
    runs = [_run(tmp_path / f"o{n}", "2026-10-05", issues=[_issue("1", summary=FIRMS)]) for n in (1, 2, 3)]
    card = run_compare.compare_paths(runs)
    names = [r["name"] for r in card["runs"]]
    assert names == ["o1/plumb_output/2026-10-05", "o2/plumb_output/2026-10-05", "o3/plumb_output/2026-10-05"]
    assert [r["path"] for r in card["runs"]] == [str(r) for r in runs]
    text = run_compare.markdown(card)
    assert f"- o1/plumb_output/2026-10-05: {runs[0]}" in text
    assert "| o1/plumb_output/2026-10-05 | standard | 1 |" in text
    hand = tmp_path / "hand.yaml"
    hand.write_text(yaml.safe_dump([[{"run": str(runs[0]) + "/", "id": "1"},
                                     {"run": str(runs[1] / ".workspace") + "/", "id": "1"}]]), encoding="utf-8")
    assert run_compare.compare_paths(runs, hand_matches=hand)["matches_by_source"]["hand"] == 1


def test_the_same_run_given_twice_is_refused(tmp_path):
    a = _run(tmp_path, "run-a", issues=[])
    with pytest.raises(run_compare.CompareError, match="given twice"):
        run_compare.compare_paths([a, a / ".workspace"])


def test_a_workspace_path_names_the_run_by_its_folder(tmp_path):
    a = _run(tmp_path, "run-a", issues=[])
    b = _run(tmp_path, "run-b", issues=[])
    card = run_compare.compare_paths([a / ".workspace", b])
    assert [r["name"] for r in card["runs"]] == ["run-a", "run-b"]
    assert card["runs"][0]["path"] == str(a / ".workspace")


def test_pdf_file_names_compare_case_folded(tmp_path):
    a = _run(tmp_path, "run-a", issues=[], pdf="Paper.PDF")
    b = _run(tmp_path, "run-b", issues=[], pdf="paper.pdf")
    card = run_compare.compare_paths([a, b])
    assert card["paper"] == {"kind": "file", "value": "paper.pdf", "unlabeled": []}


def test_only_pdf_sha256_is_read_as_the_sha(tmp_path):
    a = _run(tmp_path, "run-a", issues=[], extra={"sha256": "aaa"})
    b = _run(tmp_path, "run-b", issues=[], extra={"sha256": "bbb"})
    assert run_compare.compare_paths([a, b])["paper"]["kind"] == "file"


def test_report_names_a_run_with_no_pdf_label(tmp_path):
    a = _run(tmp_path, "run-a", issues=[])
    b = _run(tmp_path, "run-b", issues=[], extra={"pdf_path": None})
    card = run_compare.compare_paths([a, b])
    assert card["paper"]["unlabeled"] == ["run-b"]
    assert "runs with no PDF label (no pdf_path in run.json), compared on trust: run-b" in run_compare.markdown(card)
