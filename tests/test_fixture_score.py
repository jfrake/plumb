"""plumb.fixture_score: a run's issues against a fixture's expected.yaml. Every run folder and
answer key here is a small fake written by the test."""
from __future__ import annotations
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from plumb import fixture_score

ROOT = Path(__file__).resolve().parents[1]


def _issue(id_, summary="", excerpt="", ms_page=None, severity="Weakens a claim", adjudication="paper",
           sources=(), **extra):
    rec = {"id": id_, "kind": "major", "title": f"Fake issue {id_}", "severity": severity,
           "adjudication": adjudication, "solvability": "new analysis", "summary": summary,
           "excerpt": excerpt, "ms_page": ms_page, "checkin": f"majors:{id_}", "sources": list(sources)}
    rec.update(extra)
    return rec


def _run(tmp_path, issues=None, depth="standard", stage4=None, validated=None):
    """A fake run folder plumb_output/<date>/ with its .workspace. issues=None writes no stage-5 file."""
    ws = tmp_path / "plumb_output" / "2026-10-05" / ".workspace"
    ws.mkdir(parents=True)
    (ws / "run.json").write_text(json.dumps({"depth": depth, "packs": ["archival"]}), encoding="utf-8")
    if issues is not None:
        (ws / "stage-5").mkdir()
        (ws / "stage-5" / "issues.json").write_text(json.dumps(issues), encoding="utf-8")
    for name, text in (stage4 or {}).items():
        (ws / "stage-4").mkdir(exist_ok=True)
        (ws / "stage-4" / name).write_text(text, encoding="utf-8")
    if validated is not None:
        (ws / "stage-7").mkdir()
        (ws / "stage-7" / "validated.json").write_text(json.dumps(validated), encoding="utf-8")
    return ws.parent


def _fixture(tmp_path, must_catch=(), must_not_flag=(), also_fair=(), checks=None):
    """A fake pack folder with one fixture and a checklist: packs/fake/fixtures/f-1/expected.yaml."""
    pack = tmp_path / "packs" / "fake"
    (pack / "fixtures" / "f-1").mkdir(parents=True)
    (pack / "checklists").mkdir()
    (pack / "checklists" / "fake.yaml").write_text(yaml.safe_dump(
        [{"id": k, "text": v, "adjudication": "paper"} for k, v in (checks or {}).items()]), encoding="utf-8")
    key = {"status": "pending_planting", "owner": "blind-agent", "synthetic": True, "module": "did",
           "label": "SYNTHETIC TEST PAPER, NOT REAL RESEARCH", "paper": "planted.pdf",
           "must_catch": list(must_catch), "must_not_flag": list(must_not_flag), "also_fair": list(also_fair)}
    (pack / "fixtures" / "f-1" / "expected.yaml").write_text(yaml.safe_dump(key), encoding="utf-8")
    return pack / "fixtures" / "f-1"


def _entry(check, page, locator, severity="Weakens a claim"):
    return {"check": check, "page": page, "locator": locator, "note": "why", "severity": severity}


def test_run_with_no_stage_5_file_is_a_clear_error(tmp_path):
    run = _run(tmp_path, issues=None)
    fx = _fixture(tmp_path, must_catch=[_entry("DD1", 11, "a sentence")])
    with pytest.raises(fixture_score.ScoreError, match="stage-5/issues.json"):
        fixture_score.score_paths(fx, run)


def test_check_id_on_the_issue_matches_first(tmp_path):
    run = _run(tmp_path, issues=[_issue("1", summary="Something unrelated.", check="DD1"),
                                 _issue("2", summary="Also unrelated.", check="DD3")])
    fx = _fixture(tmp_path, must_catch=[_entry("DD3", 4, "The twelve never-treated regions serve as the control group")])
    card = fixture_score.score_paths(fx, run)
    assert card["must_catch"] == [{"check": "DD3", "page": 4, "severity": "Weakens a claim", "result": "caught",
                                   "issue": "2", "strategy": "check", "survived": None}]


def test_check_id_named_in_sources_counts_as_a_check_id(tmp_path):
    run = _run(tmp_path, issues=[_issue("7", summary="No overlap here.", sources=["design_checks.md:DD5", "numbers:text:3"])])
    fx = _fixture(tmp_path, must_catch=[_entry("DD5", 5, "The joint test of the five leads confirms the identifying assumption.")])
    card = fixture_score.score_paths(fx, run)
    assert card["must_catch"][0]["result"] == "caught"
    assert card["must_catch"][0]["issue"] == "7"
    assert card["must_catch"][0]["strategy"] == "check"


def test_missed_entry_names_no_issue(tmp_path):
    run = _run(tmp_path, issues=[_issue("1", summary="Nothing to do with it.", check="DD1")])
    fx = _fixture(tmp_path, must_catch=[_entry("SC8", 13, "which gives a permutation p-value of 0.03")])
    card = fixture_score.score_paths(fx, run)
    assert card["must_catch"][0]["result"] == "missed"
    assert card["must_catch"][0]["issue"] is None
    assert card["must_catch"][0]["strategy"] is None


STAGE4 = """Pack: archival

# Design checks

Modules loaded: DiD (main)

## Issues
1. The twelve regions called never-treated adopt in 2019.
   Check: DD3. Design: DiD (main). Tag: [judgment]
   Paper's best case: they adopt in the last year.
   Evidence: Table 1 (p. 3).
   Excerpt: "The twelve never-treated regions serve as the control group throughout."
   Page: 4
   Severity: Weakens a claim
   What would settle it: drop them.
2. The pre-test is read as proof.
   Check: DD5. Design: DiD (main). Tag: [paper]
   Excerpt: "The joint test of the five leads (p = 0.31) confirms the identifying assumption."
   Page: 5
   Severity: Weakens a claim

## Checked and fine
- DD10: treatment is absorbing (p. 2).
"""


def test_check_id_recovered_from_the_stage_4_file_by_excerpt(tmp_path):
    run = _run(tmp_path, stage4={"design_checks.md": STAGE4}, issues=[
        _issue("1", summary="The control regions are not untreated.",
               excerpt="The twelve never-treated regions serve as the control group throughout.", ms_page=4)])
    fx = _fixture(tmp_path, must_catch=[_entry("DD3", 4, "Empirical strategy: regions serve as the control group")])
    card = fixture_score.score_paths(fx, run)
    assert card["must_catch"][0]["result"] == "caught"
    assert card["must_catch"][0]["issue"] == "1"
    assert card["must_catch"][0]["strategy"] == "stage-4"


def test_stage_4_checked_and_fine_lines_never_match(tmp_path):
    run = _run(tmp_path, stage4={"design_checks.md": STAGE4}, issues=[
        _issue("1", summary="Some other issue.", excerpt="A sentence the stage-4 file does not hold.", ms_page=2)])
    fx = _fixture(tmp_path, must_catch=[_entry("DD10", 2, "No region repealed the law")])
    card = fixture_score.score_paths(fx, run)
    assert card["must_catch"][0]["result"] == "missed"


def test_locator_sentence_inside_the_issue_excerpt(tmp_path):
    run = _run(tmp_path, issues=[_issue(
        "3", summary="The never-treated label is wrong.",
        excerpt="The twelve never-treated regions serve as the control group throughout.", ms_page=4)])
    fx = _fixture(tmp_path, must_catch=[_entry(
        "DD3", 4, "Empirical strategy: The twelve never-treated regions serve as the control group throughout.")])
    card = fixture_score.score_paths(fx, run)
    assert (card["must_catch"][0]["result"], card["must_catch"][0]["issue"], card["must_catch"][0]["strategy"]) \
        == ("caught", "3", "locator")


def test_locator_content_words_mostly_in_the_summary(tmp_path):
    run = _run(tmp_path, issues=[_issue(
        "4", summary="The joint test of the leads, with p = 0.31, is offered as confirmation of the "
                     "identifying assumption, but the pre-test has little power.", ms_page=5)])
    fx = _fixture(tmp_path, must_catch=[_entry(
        "DD5", 5, "Event-study estimates: The joint test of the five leads (p = 0.31) confirms the identifying assumption.")])
    card = fixture_score.score_paths(fx, run)
    assert card["must_catch"][0]["strategy"] == "locator"


def test_locator_with_few_shared_words_does_not_match(tmp_path):
    run = _run(tmp_path, issues=[_issue("5", summary="The sample excludes firms with fewer than ten employees.",
                                        excerpt="Firms with fewer than ten employees are excluded.", ms_page=5)])
    fx = _fixture(tmp_path, must_catch=[_entry(
        "DD5", 5, "Event-study estimates: The joint test of the five leads (p = 0.31) confirms the identifying assumption.")])
    card = fixture_score.score_paths(fx, run)
    assert card["must_catch"][0]["result"] == "missed"


def test_same_page_plus_the_checks_keywords(tmp_path):
    run = _run(tmp_path, issues=[_issue(
        "6", summary="Log headcount is measured in the current year and the law itself raises headcount, "
                     "so this covariate is moved by the treatment and belongs out of the main model.", ms_page=4)])
    fx = _fixture(tmp_path, must_catch=[_entry("DD11", 4, "Empirical strategy: because larger firms have more suppliers")],
                  checks={"DD11": "Covariates in the DiD that the paper's own theory, text, or results imply the "
                                  "treatment moves are not in the main model"})
    card = fixture_score.score_paths(fx, run)
    assert (card["must_catch"][0]["result"], card["must_catch"][0]["strategy"]) == ("caught", "page")


def test_keywords_on_another_page_do_not_match(tmp_path):
    run = _run(tmp_path, issues=[_issue(
        "6", summary="Log headcount is a covariate the treatment moves and belongs out of the main model.", ms_page=9)])
    fx = _fixture(tmp_path, must_catch=[_entry("DD11", 4, "Empirical strategy: because larger firms have more suppliers")],
                  checks={"DD11": "Covariates in the DiD that the paper's own theory, text, or results imply the "
                                  "treatment moves are not in the main model"})
    card = fixture_score.score_paths(fx, run)
    assert card["must_catch"][0]["result"] == "missed"


def test_same_page_without_the_keywords_does_not_match(tmp_path):
    run = _run(tmp_path, issues=[_issue("6", summary="The sample size in Table 2 disagrees with the text.", ms_page=4)])
    fx = _fixture(tmp_path, must_catch=[_entry("DD11", 4, "Empirical strategy: because larger firms have more suppliers")],
                  checks={"DD11": "Covariates in the DiD that the paper's own theory, text, or results imply the "
                                  "treatment moves are not in the main model"})
    card = fixture_score.score_paths(fx, run)
    assert card["must_catch"][0]["result"] == "missed"


def test_must_not_flag_is_flagged_when_an_issue_matches_and_clean_otherwise(tmp_path):
    run = _run(tmp_path, issues=[_issue("1", summary="The audits bound is fine.", check="DD6")])
    fx = _fixture(tmp_path, must_not_flag=[_entry("DD6", 8, "Supplier audits: up to 2.9, the breakdown value"),
                                           _entry("DD10", 2, "No region repealed the law")])
    card = fixture_score.score_paths(fx, run)
    assert [(r["check"], r["result"], r["issue"]) for r in card["must_not_flag"]] == \
        [("DD6", "flagged", "1"), ("DD10", "clean", None)]
    assert card["totals"]["must_not_flag"] == {"expected": 2, "clean": 1, "flagged": 1}


def test_also_fair_is_reported_but_never_counted_against(tmp_path):
    run = _run(tmp_path, issues=[_issue("1", summary="Reference year lies in the window.", check="DD4")])
    fx = _fixture(tmp_path, must_catch=[_entry("DD1", 11, "is similar to our main estimate", "Undermines the main claim")],
                  also_fair=[_entry("DD4", 5, "with the year before adoption as the omitted reference year"),
                             _entry("SC4", 12, "The pre-period is 2005 to 2012")])
    card = fixture_score.score_paths(fx, run)
    assert [(r["check"], r["result"]) for r in card["also_fair"]] == [("DD4", "caught"), ("SC4", "not caught")]
    assert card["totals"]["also_fair"] == {"expected": 2, "caught": 1}
    assert card["totals"]["must_catch"] == {"expected": 1, "caught": 0, "missed": 1}
    assert "1" not in [e["id"] for e in card["extras"]]


def test_totals_by_severity_and_by_adjudication(tmp_path):
    run = _run(tmp_path, issues=[_issue("1", summary="x", check="DD1", adjudication="paper", severity="Undermines the main claim"),
                                 _issue("2", summary="y", check="DD7", adjudication="judgment"),
                                 _issue("3", summary="z", check="A2", adjudication="paper", severity="Minor")])
    fx = _fixture(tmp_path, must_catch=[_entry("DD1", 11, "l1", "Undermines the main claim"),
                                        _entry("DD3", 4, "l2", "Weakens a claim"),
                                        _entry("DD7", 2, "l3", "Weakens a claim"),
                                        _entry("SC8", 13, "l4", "Minor")])
    card = fixture_score.score_paths(fx, run)
    assert card["by_severity"] == {"Undermines the main claim": {"expected": 1, "caught": 1},
                                   "Weakens a claim": {"expected": 2, "caught": 1},
                                   "Minor": {"expected": 1, "caught": 0}}
    assert card["by_adjudication"] == {"paper": {"issues": 2, "caught": 1, "extras": 1},
                                       "judgment": {"issues": 1, "caught": 1, "extras": 0}}


def test_extras_list_the_issues_that_match_nothing(tmp_path):
    run = _run(tmp_path, issues=[_issue("1", summary="Matches the key.", check="DD1"),
                                 _issue("2", summary="Matches nothing in the key.", ms_page=9, severity="Minor",
                                        adjudication="judgment", kind="minor")])
    fx = _fixture(tmp_path, must_catch=[_entry("DD1", 11, "l1", "Undermines the main claim")])
    card = fixture_score.score_paths(fx, run)
    assert card["extras"] == [{"id": "2", "kind": "minor", "severity": "Minor", "adjudication": "judgment",
                               "ms_page": 9, "title": "Fake issue 2", "summary": "Matches nothing in the key."}]


def test_depth_packs_and_fixture_facts_are_on_the_card(tmp_path):
    run = _run(tmp_path, issues=[], depth="full")
    fx = _fixture(tmp_path, must_catch=[_entry("DD1", 11, "l1")])
    card = fixture_score.score_paths(fx, run)
    assert card["depth"] == "deep"
    assert card["packs"] == ["archival"]
    assert (card["fixture"], card["pack"], card["module"], card["status"]) == ("f-1", "fake", "did", "pending_planting")
    assert card["issues"] == 0
    assert card["run"] == str(run / ".workspace")


def test_survived_reads_stage_7_validated(tmp_path):
    run = _run(tmp_path, issues=[_issue("1", summary="a", check="DD1"), _issue("2", summary="b", check="DD3")],
               validated=[{"id": "1", "source": "2", "kind": "major"}])
    fx = _fixture(tmp_path, must_catch=[_entry("DD1", 11, "l1"), _entry("DD3", 4, "l2")])
    card = fixture_score.score_paths(fx, run)
    assert [r["survived"] for r in card["must_catch"]] == [False, True]


MERGED = "merged into a kept issue in the audit"


def _merge_run(tmp_path, stage6=None, dropped=None, validated=None):
    """Issue 1 was merged into issue 2 in the audit; issue 2 reached validated.json as record 1."""
    run = _run(tmp_path, issues=[_issue("1", summary="a", check="DD1", sources=["x-1 stage-4/x.md"]),
                                 _issue("2", summary="b", check="DD3", sources=["y-1 stage-4/y.md"])],
               validated=validated if validated is not None else [
                   {"id": "1", "source": "2", "kind": "major",
                    "sources": ["y-1 stage-4/y.md", "x-1 stage-4/x.md"]}])
    ws = run / ".workspace"
    if stage6 is not None:
        (ws / "stage-6").mkdir()
        (ws / "stage-6" / "issues.json").write_text(json.dumps(stage6), encoding="utf-8")
    if dropped is not None:
        (ws / "stage-7" / "dropped.json").write_text(json.dumps(dropped), encoding="utf-8")
    fx = _fixture(tmp_path, must_catch=[_entry("DD1", 11, "l1"), _entry("DD3", 4, "l2")])
    return fixture_score.score_paths(fx, run)


def test_an_issue_merged_into_a_validated_issue_survived(tmp_path):
    card = _merge_run(tmp_path, stage6=[_issue("2", merged_from=["1"])])
    rows = card["must_catch"]
    assert [r["survived"] for r in rows] == [True, True]
    assert rows[0]["merged_into"] == "2"
    assert "merged_into" not in rows[1]


def test_without_stage_6_the_merge_is_read_from_dropped_json(tmp_path):
    # The kept issue carries the merged issue's sources, which names the issue it went into.
    card = _merge_run(tmp_path, dropped=[{"item": "majors:1", "title": "Fake issue 1", "reason": MERGED}])
    rows = card["must_catch"]
    assert [r["survived"] for r in rows] == [True, True]
    assert rows[0]["merged_into"] == "2"


def test_a_merge_into_an_issue_that_stage_7_dropped_did_not_survive(tmp_path):
    card = _merge_run(tmp_path, stage6=[_issue("2", merged_from=["1"])],
                      dropped=[{"item": "majors:1", "title": "Fake issue 1", "reason": MERGED}], validated=[])
    assert [r["survived"] for r in card["must_catch"]] == [False, False]
    assert "merged_into" not in card["must_catch"][0]


def test_a_drop_for_another_reason_did_not_survive(tmp_path):
    card = _merge_run(tmp_path, dropped=[{"item": "majors:1", "title": "Fake issue 1",
                                          "reason": "overruled in the audit"}])
    assert [r["survived"] for r in card["must_catch"]] == [False, True]


def test_every_catch_in_the_stored_planted_run_survived():
    card = fixture_score.score_paths(ROOT / "packs" / "archival" / "fixtures" / "planted-1",
                                     ROOT / "eval" / "runs" / "planted-1-2026-10-19")
    caught = [r for r in card["must_catch"] if r["result"] == "caught"]
    assert len(caught) == 11
    assert all(r["survived"] is True for r in caught)
    assert {r["issue"]: r["merged_into"] for r in caught if "merged_into" in r} == {"12": "9", "16": "14", "5": "1"}


def test_markdown_table_lists_each_entry_and_the_totals(tmp_path):
    run = _run(tmp_path, issues=[_issue("1", summary="a", check="DD1", severity="Undermines the main claim"),
                                 _issue("9", summary="An extra the key does not name.", ms_page=7)])
    fx = _fixture(tmp_path, must_catch=[_entry("DD1", 11, "l1", "Undermines the main claim"), _entry("DD3", 4, "l2")],
                  must_not_flag=[_entry("DD10", 2, "l3")])
    card = fixture_score.score_paths(fx, run)
    text = fixture_score.markdown(card)
    assert "| DD1 | 11 | Undermines the main claim | caught | 1 | check |" in text
    assert "| DD3 | 4 | Weakens a claim | missed | | |" in text
    assert "| DD10 | 2 | clean | | |" in text
    assert "must_catch: 1 of 2 caught" in text
    assert "must_not_flag: 1 of 1 clean" in text
    assert "depth: deep" not in text and "depth: standard" in text
    assert "| 9 | major | Weakens a claim | 7 | An extra the key does not name. |" in text
    assert chr(0x2014) not in text


def test_script_prints_json_then_markdown_and_exits_zero(tmp_path):
    run = _run(tmp_path, issues=[_issue("1", summary="a", check="DD1")])
    fx = _fixture(tmp_path, must_catch=[_entry("DD1", 11, "l1")])
    proc = subprocess.run([sys.executable, str(ROOT / "eval" / "score_fixture.py"), str(fx), str(run)],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    head, sep, tail = proc.stdout.partition("\n## ")
    card = json.loads(head)
    assert card["totals"]["must_catch"] == {"expected": 1, "caught": 1, "missed": 0}
    assert sep and "| DD1 | 11 |" in tail


def test_script_accepts_the_workspace_itself_and_writes_the_card_to_a_file(tmp_path):
    run = _run(tmp_path, issues=[_issue("1", summary="a", check="DD1")])
    fx = _fixture(tmp_path, must_catch=[_entry("DD1", 11, "l1")])
    out = tmp_path / "score.json"
    proc = subprocess.run([sys.executable, str(ROOT / "eval" / "score_fixture.py"), str(fx), str(run / ".workspace"),
                           "--out", str(out)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(out.read_text())["must_catch"][0]["result"] == "caught"


def test_script_exits_non_zero_with_a_clear_message_when_stage_5_is_missing(tmp_path):
    run = _run(tmp_path, issues=None)
    fx = _fixture(tmp_path, must_catch=[_entry("DD1", 11, "l1")])
    proc = subprocess.run([sys.executable, str(ROOT / "eval" / "score_fixture.py"), str(fx), str(run)],
                          capture_output=True, text=True)
    assert proc.returncode == 2
    assert "stage-5/issues.json" in proc.stderr
    assert proc.stdout == ""


RUNNER = ROOT / "eval" / "run_fixture.sh"

FAKE_CLAUDE = """#!/bin/bash
# A stand-in for the claude CLI: records its arguments and writes one or two run folders in the cwd,
# each with a synthesis-shaped issue (excerpt and ms_page, no check field), as a real run would.
printf '%s\\n' "$@" > claude_args.txt
write_run() {
  ws="plumb_output/$1/.workspace"
  mkdir -p "$ws/stage-5"
  if [ -n "${PLUMB_FAKE_CAP:-}" ]; then
    printf '{"depth": "%s", "packs": ["fake"], "search_before": "%s"}' "$PLUMB_FAKE_DEPTH" "$PLUMB_FAKE_CAP" > "$ws/run.json"
  else
    printf '{"depth": "%s", "packs": ["fake"]}' "$PLUMB_FAKE_DEPTH" > "$ws/run.json"
  fi
  printf '[{"id": "1", "kind": "major", "title": "%s", "severity": "Weakens a claim", "adjudication": "paper", "summary": "The never-treated label is wrong.", "excerpt": "The twelve never-treated regions serve as the control group throughout.", "ms_page": 4, "checkin": "majors:1", "sources": []}]' "$2" > "$ws/stage-5/issues.json"
}
write_run 2026-10-05 older
touch -t 202601010000 plumb_output/2026-10-05
if [ -n "${PLUMB_FAKE_SECOND:-}" ]; then write_run 2026-10-05-2 newer; fi
"""


def _fixture_with_paper(tmp_path, overlay=False):
    fx = _fixture(tmp_path, must_catch=[_entry(
        "DD3", 4, "Empirical strategy: The twelve never-treated regions serve as the control group throughout.")],
        must_not_flag=[_entry("DD10", 2, "Setting: No region repealed the law")])
    (fx / "planted.pdf").write_bytes(b"%PDF-1.4 fake\n")
    if overlay:
        (fx.parents[1] / "pack.yaml").write_text("name: fake\noverlay: true\n", encoding="utf-8")
    return fx


def test_runner_parses_under_bash():
    assert subprocess.run(["/bin/bash", "-n", str(RUNNER)], capture_output=True, text=True).returncode == 0


def test_runner_dry_run_prints_the_headless_command_and_runs_nothing(tmp_path):
    fx = _fixture_with_paper(tmp_path)
    out = tmp_path / "runs"
    proc = subprocess.run(["/bin/bash", str(RUNNER), str(fx), "deep", str(out), "--dry-run"],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert "claude" in proc.stdout and "-p" in proc.stdout and "/plumb:review" in proc.stdout
    assert "Deep" in proc.stdout and "Auto" in proc.stdout
    assert not (out / "f-1-deep" / "plumb_output").exists()


def test_runner_rejects_an_unknown_depth(tmp_path):
    fx = _fixture_with_paper(tmp_path)
    proc = subprocess.run(["/bin/bash", str(RUNNER), str(fx), "medium", str(tmp_path / "runs")],
                          capture_output=True, text=True)
    assert proc.returncode != 0 and "quick, standard, or deep" in proc.stderr


def test_runner_runs_the_cli_in_the_work_folder_then_scores_the_newest_run(tmp_path):
    fx = _fixture_with_paper(tmp_path)
    fake = tmp_path / "claude"
    fake.write_text(FAKE_CLAUDE)
    fake.chmod(0o755)
    out = tmp_path / "runs"
    env = dict(os.environ, CLAUDE_BIN=str(fake), PLUMB_FAKE_DEPTH="quick")
    proc = subprocess.run(["/bin/bash", str(RUNNER), str(fx), "quick", str(out)], capture_output=True, text=True, env=env)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    work = out / "f-1-quick"
    assert (work / "planted.pdf").is_file()
    args = (work / "claude_args.txt").read_text()
    assert "-p" in args and "/plumb:review" in args and "planted.pdf" in args and "Quick" in args
    card = json.loads((work / "score.json").read_text())
    assert card["depth"] == "quick"
    assert card["totals"]["must_catch"] == {"expected": 1, "caught": 1, "missed": 0}
    assert card["must_catch"][0]["strategy"] == "locator"
    assert "| DD3 | 4 |" in proc.stdout


def test_runner_loads_its_own_checkout_and_passes_extra_flags_whole(tmp_path):
    """The claude call gets --plugin-dir <this checkout> as one argument (the repo path has a space),
    and every extra argument after the output folder arrives as one argument, spaces included."""
    fx = _fixture_with_paper(tmp_path)
    fake_dir = tmp_path / "bin with space"
    fake_dir.mkdir()
    fake = fake_dir / "claude"
    fake.write_text(FAKE_CLAUDE)
    fake.chmod(0o755)
    out = tmp_path / "runs"
    env = dict(os.environ, CLAUDE_BIN=str(fake), PLUMB_FAKE_DEPTH="quick")
    proc = subprocess.run(["/bin/bash", str(RUNNER), str(fx), "quick", str(out), "--allowedTools", "Bash,Read",
                           "--settings", '{"a b": 1}'], capture_output=True, text=True, env=env)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    args = (out / "f-1-quick" / "claude_args.txt").read_text().split("\n")
    assert args[:3] == ["-p", "--plugin-dir", str(ROOT)]
    assert "--permission-mode" in args and args[args.index("--permission-mode") + 1] == "acceptEdits"
    assert args[args.index("--settings") + 1] == '{"a b": 1}'
    assert args[args.index("--allowedTools") + 1] == "Bash,Read"


def test_runner_keeps_a_caller_supplied_permission_mode(tmp_path):
    fx = _fixture_with_paper(tmp_path)
    fake = tmp_path / "claude"
    fake.write_text(FAKE_CLAUDE)
    fake.chmod(0o755)
    env = dict(os.environ, CLAUDE_BIN=str(fake), PLUMB_FAKE_DEPTH="quick")
    proc = subprocess.run(["/bin/bash", str(RUNNER), str(fx), "quick", str(tmp_path / "runs"),
                           "--permission-mode", "plan"], capture_output=True, text=True, env=env)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    args = (tmp_path / "runs" / "f-1-quick" / "claude_args.txt").read_text().split("\n")
    assert args.count("--permission-mode") == 1 and args[args.index("--permission-mode") + 1] == "plan"


def test_runner_fails_when_the_cli_leaves_no_run_folder(tmp_path):
    fx = _fixture_with_paper(tmp_path)
    fake = tmp_path / "claude"
    fake.write_text("#!/bin/bash\nexit 0\n")
    fake.chmod(0o755)
    env = dict(os.environ, CLAUDE_BIN=str(fake))
    proc = subprocess.run(["/bin/bash", str(RUNNER), str(fx), "standard", str(tmp_path / "runs")],
                          capture_output=True, text=True, env=env)
    assert proc.returncode != 0 and "no run folder" in proc.stderr


def test_real_did_key_catches_paraphrased_issues_and_keeps_must_not_flag_clean(tmp_path):
    """The archival did-1 key (read only) against two issues written the way synthesis writes them:
    no check id, no excerpt, a paraphrase of the plant. DD1 matches on the locator's content words;
    DD11, worded without the locator's words, on its page plus the check's and the note's keywords.
    Nothing in must_not_flag is hit."""
    run = _run(tmp_path, issues=[
        _issue("1", summary="The headline rests on the pooled TWFE coefficient although the Callaway-Sant'Anna "
                            "overall ATT has the opposite sign; the text calls them similar and concludes the "
                            "result is not an artifact of staggered adoption.", ms_page=11,
               severity="Undermines the main claim"),
        _issue("2", summary="The headline model controls for firm size measured after treatment, and the law "
                            "itself raises firm size, so this covariate is moved by the treatment and is a bad "
                            "control.", ms_page=4)])
    card = fixture_score.score_paths(ROOT / "packs" / "archival" / "fixtures" / "did-1", run)
    by = {r["check"]: r for r in card["must_catch"]}
    assert (by["DD1"]["result"], by["DD1"]["issue"], by["DD1"]["strategy"]) == ("caught", "1", "locator")
    assert (by["DD11"]["result"], by["DD11"]["issue"], by["DD11"]["strategy"]) == ("caught", "2", "page")
    assert [r["result"] for r in card["must_not_flag"]] == ["clean", "clean", "clean"]
    assert card["extras"] == []


# One-to-one assignment: the did-1 key reuses DD6 (must_not_flag p.8, also_fair p.5) and DD4
# (must_catch p.6, also_fair p.5), so an issue must land on one entry only, by page when its id recurs.

def test_also_fair_issue_on_its_page_leaves_must_not_flag_with_the_same_check_clean(tmp_path):
    run = _run(tmp_path, issues=[_issue("1", summary="No sensitivity analysis for the main outcome.", ms_page=5, check="DD6")])
    fx = _fixture(tmp_path, must_not_flag=[_entry("DD6", 8, "Supplier audits: up to 2.9, the breakdown value")],
                  also_fair=[_entry("DD6", 5, "Event-study estimates: The joint test of the five leads")])
    card = fixture_score.score_paths(fx, run)
    assert card["must_not_flag"][0]["result"] == "clean"
    assert (card["also_fair"][0]["result"], card["also_fair"][0]["issue"]) == ("caught", "1")


def test_a_recurring_check_id_needs_the_page_to_agree(tmp_path):
    run = _run(tmp_path, issues=[_issue("1", summary="Reference year inside the window.", ms_page=5, check="DD4")])
    fx = _fixture(tmp_path, must_catch=[_entry("DD4", 6, "Figure 1 note: with 95 percent confidence intervals")],
                  also_fair=[_entry("DD4", 5, "Empirical strategy: with the year before adoption as the omitted reference year")])
    card = fixture_score.score_paths(fx, run)
    assert card["must_catch"][0]["result"] == "missed"
    assert (card["also_fair"][0]["result"], card["also_fair"][0]["issue"]) == ("caught", "1")


def test_a_recurring_check_id_from_stage_4_needs_the_page_too(tmp_path):
    run = _run(tmp_path, stage4={"design_checks.md": STAGE4.replace("Check: DD5.", "Check: DD4.")}, issues=[
        _issue("1", summary="x", excerpt="The joint test of the five leads (p = 0.31) confirms the identifying assumption.",
               ms_page=5)])
    fx = _fixture(tmp_path, must_catch=[_entry("DD4", 6, "Figure 1 note: with 95 percent confidence intervals")],
                  also_fair=[_entry("DD4", 5, "Empirical strategy: with the year before adoption")])
    card = fixture_score.score_paths(fx, run)
    assert card["must_catch"][0]["result"] == "missed"
    assert (card["also_fair"][0]["result"], card["also_fair"][0]["strategy"]) == ("caught", "stage-4")


def test_a_check_id_that_occurs_once_still_matches_without_a_page(tmp_path):
    run = _run(tmp_path, issues=[_issue("1", summary="x", check="DD1")])
    fx = _fixture(tmp_path, must_catch=[_entry("DD1", 11, "l1")])
    assert fixture_score.score_paths(fx, run)["must_catch"][0]["result"] == "caught"


def test_one_issue_is_never_credited_to_two_must_catch_entries(tmp_path):
    both = ("The twelve never-treated regions serve as the control group throughout, and log headcount in the "
            "current year is a covariate because larger firms have more suppliers.")
    run = _run(tmp_path, issues=[_issue("1", summary=both, ms_page=4)])
    fx = _fixture(tmp_path, must_catch=[
        _entry("DD3", 4, "Empirical strategy: The twelve never-treated regions serve as the control group throughout."),
        _entry("DD11", 4, "Empirical strategy: log headcount in the current year, because larger firms have more suppliers")])
    card = fixture_score.score_paths(fx, run)
    assert sorted(r["result"] for r in card["must_catch"]) == ["caught", "missed"]
    assert card["totals"]["must_catch"] == {"expected": 2, "caught": 1, "missed": 1}


def test_a_strong_match_later_in_the_key_beats_a_weak_one_earlier(tmp_path):
    """Entry DD3 (first in the key) matches issue 1 only by locator; entry DD7 matches issue 1 by
    check id. Strategies run globally, so issue 1 goes to DD7 and DD3 is missed."""
    run = _run(tmp_path, issues=[_issue(
        "1", summary="The twelve never-treated regions serve as the control group throughout.", ms_page=2, check="DD7")])
    fx = _fixture(tmp_path, must_catch=[
        _entry("DD3", 4, "Empirical strategy: The twelve never-treated regions serve as the control group throughout."),
        _entry("DD7", 2, "Setting: Each regional assembly announced its adoption two years before the law took effect")])
    card = fixture_score.score_paths(fx, run)
    assert [(r["check"], r["result"], r["strategy"]) for r in card["must_catch"]] == \
        [("DD3", "missed", None), ("DD7", "caught", "check")]


def test_a_stage_4_check_id_vetoes_locator_and_page_credit_for_another_check(tmp_path):
    """The issue quotes the joint-test sentence, which is must_catch DD5's locator, but the stage-4
    file says that excerpt belongs to DD6 (an id the key does not list here), so the locator and
    page strategies do not credit DD5 with it; the issue is an extra."""
    stage4 = STAGE4.replace("Check: DD5.", "Check: DD6.")
    run = _run(tmp_path, stage4={"design_checks.md": stage4}, issues=[_issue(
        "1", summary="No sensitivity analysis to parallel-trends violations is reported for the main outcome.",
        excerpt="The joint test of the five leads (p = 0.31) confirms the identifying assumption.", ms_page=5)])
    fx = _fixture(tmp_path, must_catch=[_entry(
        "DD5", 5, "Event-study estimates: The joint test of the five leads (p = 0.31) confirms the identifying assumption.")],
        checks={"DD5": "Pre-period coefficients are read as evidence with limited power: a pre-trend test that "
                       "fails to reject is not offered as proof of parallel trends"})
    card = fixture_score.score_paths(fx, run)
    assert card["must_catch"][0]["result"] == "missed"
    assert [e["id"] for e in card["extras"]] == ["1"]


def test_without_a_recovered_id_the_locator_still_credits(tmp_path):
    run = _run(tmp_path, issues=[_issue(
        "1", summary="The pre-test is read as proof.",
        excerpt="The joint test of the five leads (p = 0.31) confirms the identifying assumption.", ms_page=5)])
    fx = _fixture(tmp_path, must_catch=[_entry(
        "DD5", 5, "Event-study estimates: The joint test of the five leads (p = 0.31) confirms the identifying assumption.")])
    assert fixture_score.score_paths(fx, run)["must_catch"][0]["strategy"] == "locator"


# Depth and the Quick ruling: Quick runs Stages 0, 1, 2, and 7 and writes no stage-5/issues.json.

QUICK_NOTE = "Quick writes no stage-5/issues.json; every design entry counts as missed"


def test_quick_run_with_no_stage_5_scores_as_zero_issues(tmp_path):
    run = _run(tmp_path, issues=None, depth="quick")
    fx = _fixture(tmp_path, must_catch=[_entry("DD1", 11, "l1"), _entry("DD3", 4, "l2")],
                  must_not_flag=[_entry("DD10", 2, "l3")], also_fair=[_entry("DD4", 5, "l4")])
    card = fixture_score.score_paths(fx, run)
    assert card["depth"] == "quick" and card["issues"] == 0
    assert [r["result"] for r in card["must_catch"]] == ["missed", "missed"]
    assert [r["result"] for r in card["must_not_flag"]] == ["clean"]
    assert [r["result"] for r in card["also_fair"]] == ["not caught"]
    assert QUICK_NOTE in card["issues_from"]
    assert QUICK_NOTE in fixture_score.markdown(card)


def test_card_head_says_where_the_issues_came_from(tmp_path):
    run = _run(tmp_path, issues=[_issue("1", summary="a", check="DD1")])
    fx = _fixture(tmp_path, must_catch=[_entry("DD1", 11, "l1")])
    card = fixture_score.score_paths(fx, run)
    assert card["issues_from"] == "stage-5/issues.json"
    assert "issues from: stage-5/issues.json" in fixture_score.markdown(card)


def test_depth_comes_from_the_tier_key_or_the_recorded_answer(tmp_path):
    run = _run(tmp_path, issues=[], depth="standard")
    ws = run / ".workspace"
    (ws / "run.json").write_text(json.dumps({"tier": "full", "packs": []}), encoding="utf-8")
    fx = _fixture(tmp_path, must_catch=[_entry("DD1", 11, "l1")])
    assert fixture_score.score_paths(fx, run)["depth"] == "deep"
    (ws / "run.json").write_text(json.dumps({"packs": []}), encoding="utf-8")
    (ws / "audit").mkdir()
    (ws / "audit" / "events.jsonl").write_text(json.dumps(
        {"ts": "2026-10-05T00:00:00", "kind": "checkin", "stop": "setup", "item": "setup:depth",
         "recommended": "A. Standard (Recommended)", "answer": "B. Quick", "note": None}) + "\n", encoding="utf-8")
    assert fixture_score.score_paths(fx, run)["depth"] == "quick"


def test_a_run_with_no_depth_and_no_answer_is_standard(tmp_path):
    run = _run(tmp_path, issues=[], depth="standard")
    (run / ".workspace" / "run.json").write_text(json.dumps({"packs": []}), encoding="utf-8")
    fx = _fixture(tmp_path, must_catch=[_entry("DD1", 11, "l1")])
    assert fixture_score.score_paths(fx, run)["depth"] == "standard"


def test_an_unknown_depth_is_a_score_error(tmp_path):
    run = _run(tmp_path, issues=[], depth="medium")
    fx = _fixture(tmp_path, must_catch=[_entry("DD1", 11, "l1")])
    with pytest.raises(fixture_score.ScoreError, match="depth"):
        fixture_score.score_paths(fx, run)


def test_a_malformed_run_json_is_a_score_error(tmp_path):
    run = _run(tmp_path, issues=[], depth="standard")
    (run / ".workspace" / "run.json").write_text("{not json", encoding="utf-8")
    fx = _fixture(tmp_path, must_catch=[_entry("DD1", 11, "l1")])
    with pytest.raises(fixture_score.ScoreError, match="run.json"):
        fixture_score.score_paths(fx, run)
    (run / ".workspace" / "run.json").write_text("[]", encoding="utf-8")
    with pytest.raises(fixture_score.ScoreError, match="run.json"):
        fixture_score.score_paths(fx, run)


def test_runner_scores_the_newest_run_folder_by_mtime_not_by_name(tmp_path):
    """"2026-10-05/" sorts after "2026-10-05-2/", so a name sort would pick the older run."""
    fx = _fixture_with_paper(tmp_path)
    fake = tmp_path / "claude"
    fake.write_text(FAKE_CLAUDE)
    fake.chmod(0o755)
    out = tmp_path / "runs"
    env = dict(os.environ, CLAUDE_BIN=str(fake), PLUMB_FAKE_DEPTH="standard", PLUMB_FAKE_SECOND="1")
    proc = subprocess.run(["/bin/bash", str(RUNNER), str(fx), "standard", str(out)], capture_output=True, text=True, env=env)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    card = json.loads((out / "f-1-standard" / "score.json").read_text())
    assert card["run"].rstrip("/").endswith("2026-10-05-2/.workspace")


def test_runner_prompt_answers_every_setup_question(tmp_path):
    fx = _fixture_with_paper(tmp_path)
    proc = subprocess.run(["/bin/bash", str(RUNNER), str(fx), "standard", str(tmp_path / "runs"), "--dry-run"],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    for phrase in ("It's mine or my coauthors'", "Organization Science", "A. Standard (Recommended)", "D. Auto",
                   "A. Issues list", "Outputs will go to", "coauthors agree", "A. Yes, or the paper quotes none",
                   "manuscript_text", "search_queries", "never run plumb provider-facts set", "B. Skip it", "A. Start the review",
                   "setup:type", "fake", "the detected second type", "setup:contribution", "B. Skip them",
                   "setup:journal_confirm", "A. Keep"):
        assert phrase in proc.stdout, phrase


def test_runner_prompt_runs_the_overlay_when_the_fixture_pack_is_one(tmp_path):
    fx = _fixture_with_paper(tmp_path, overlay=True)
    proc = subprocess.run(["/bin/bash", str(RUNNER), str(fx), "deep", str(tmp_path / "runs"), "--dry-run"],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert "A. Run the fake checks" in proc.stdout and "B. Skip them" in proc.stdout


# Minor: check-id tokens compare case folded (synthesis sources carry lowercase slugs), an id with
# punctuation (core:literature) matches a whole source string, and only unindented numbered lines
# start a stage-4 entry.

def test_check_id_tokens_compare_case_folded(tmp_path):
    run = _run(tmp_path, issues=[_issue("1", summary="x", sources=["design_checks.md:dd5"]),
                                 _issue("2", summary="y", sources=["core:literature"])])
    fx = _fixture(tmp_path, must_catch=[_entry("DD5", 5, "l1"), _entry("core:literature", 2, "l2")])
    card = fixture_score.score_paths(fx, run)
    assert [(r["result"], r["issue"], r["strategy"]) for r in card["must_catch"]] == \
        [("caught", "1", "check"), ("caught", "2", "check")]


def test_an_indented_numbered_line_does_not_start_a_stage_4_entry(tmp_path):
    stage4 = STAGE4.replace("   Evidence: Table 1 (p. 3).",
                            "   Evidence: Table 1 (p. 3).\n   1. The cohort adopts in 2019.\n   Check: DD9.")
    run = _run(tmp_path, stage4={"design_checks.md": stage4}, issues=[_issue(
        "1", summary="x", excerpt="The twelve never-treated regions serve as the control group throughout.", ms_page=4)])
    fx = _fixture(tmp_path, must_catch=[_entry("DD3", 4, "l1"), _entry("DD9", 4, "l2")])
    card = fixture_score.score_paths(fx, run)
    assert [(r["check"], r["result"]) for r in card["must_catch"]] == [("DD3", "caught"), ("DD9", "missed")]
    assert fixture_score.stage4_checks(run / ".workspace")[0][1] == {"DD3", "DD9"}


def test_real_experiments_key_strips_study_labels_and_matches_by_page(tmp_path):
    """The experiments planted-1 key (read only), whose locators carry labels like "Study 1,
    participants:" and which reuses E2, E3, E6, and E7 across parts. Issue 1 quotes E2's locator
    sentence (p. 3), so E2 on p. 3 is caught by locator and the must_not_flag E2 on p. 7 stays
    clean. Issue 2 paraphrases the E13 plant on p. 7 without its locator's words, so the page plus
    the check's and the note's keywords catch it."""
    run = _run(tmp_path, issues=[
        _issue("1", summary="The error degrees of freedom do not fit the analyzed sample.",
               excerpt="leaving 392 participants, 98 per cell", ms_page=3),
        _issue("2", summary="The mediator is measured after the outcome, and the indirect effect is said to "
                            "establish the mechanism; a mediator measured after the outcome cannot carry a "
                            "bootstrapped indirect effect as evidence of mechanism.", ms_page=7)])
    card = fixture_score.score_paths(ROOT / "packs" / "experiments" / "fixtures" / "planted-1", run)
    by = {(r["check"], r["page"]): r for r in card["must_catch"]}
    assert (by[("E2", 3)]["result"], by[("E2", 3)]["issue"], by[("E2", 3)]["strategy"]) == ("caught", "1", "locator")
    assert (by[("E13", 7)]["result"], by[("E13", 7)]["issue"], by[("E13", 7)]["strategy"]) == ("caught", "2", "page")
    assert [r["result"] for r in card["must_not_flag"]] == ["clean"] * 6
    assert card["extras"] == []
    assert card["totals"]["must_catch"] == {"expected": 8, "caught": 2, "missed": 6}


# A Quick run writes no stage-5/issues.json but its stage-7/validated.json holds the checked facts,
# each with the quoted sentence and page. These records copy the shape of a real Quick run on the
# did-1 fixture (a synthetic paper), trimmed.

def _validated(id_, title, summary, excerpt, page):
    return {"id": id_, "source": f"numbers:text:{id_}", "item": f"numbers:text:{id_}", "kind": "number",
            "title": title, "severity": "Minor", "summary": summary, "excerpt": excerpt, "ms_page": page,
            "pdf_page": None, "adjudication": "paper", "fix": None, "sources": [],
            "why_it_matters": None, "settle": None}


QUICK_VALIDATED = [
    _validated("1", "Robustness estimate with the opposite sign is called similar",
               "Appendix A calls the Callaway and Sant'Anna overall ATT of -1.26 (SE 1.14) similar to the main "
               "two-way fixed effects estimate of +2.84 (SE 1.12).",
               "The overall ATT of " + chr(0x2212) + "1.26 (standard error 1.14) is similar to our main two-way fixed "
               "effects estimate, and we conclude that our main result is not an artifact of staggered adoption.", 11),
    _validated("2", "Control group of never-treated regions contradicts the adoption schedule",
               "Section 4.2 says twelve never-treated regions serve as the control group, but Table 1 shows those "
               "twelve regions adopting the law in 2019.",
               "The twelve never-treated regions serve as the control group throughout.", 4),
    _validated("3", "Permutation p-value of 0.03 is not attainable with ten units",
               "With ten units the smallest attainable p-value is 1/10 = 0.10.",
               "Harrowmere" + chr(0x2019) + "s ratio of 3.83 is the largest of the ten, which gives a permutation "
               "p-value of 0.03, significant at 5 percent.", 13),
    _validated("6", "Preferred specification controls for an outcome of the treatment",
               "Table 3 column 2 controls for log headcount, which Table 5 shows the law itself raises.",
               "Column 2 adds log headcount and regional GDP growth and is our preferred specification.", 5),
]


def test_quick_run_scores_the_checked_facts_in_stage_7_validated(tmp_path):
    run = _run(tmp_path, issues=None, depth="quick", validated=QUICK_VALIDATED)
    card = fixture_score.score_paths(ROOT / "packs" / "archival" / "fixtures" / "did-1", run)
    assert card["issues"] == 4
    assert card["issues_from"] == "stage-7/validated.json (Quick: checked facts only)"
    by = {r["check"]: r for r in card["must_catch"]}
    for check, issue in (("DD1", "1"), ("DD3", "2"), ("SC8", "3")):
        assert by[check]["result"] == "caught" and by[check]["issue"] == issue, check
        assert by[check]["strategy"] in ("locator", "page"), check
        assert by[check]["survived"] is True
    assert [r["result"] for r in card["must_not_flag"]] == ["clean", "clean", "clean"]
    assert [e["id"] for e in card["extras"]] == ["6"]
    assert "issues from: stage-7/validated.json (Quick: checked facts only)" in fixture_score.markdown(card)


def test_a_standard_run_with_only_stage_7_validated_scores_it_too(tmp_path):
    run = _run(tmp_path, issues=None, depth="standard", validated=QUICK_VALIDATED[1:2])
    fx = _fixture(tmp_path, must_catch=[_entry(
        "DD3", 4, "Empirical strategy: The twelve never-treated regions serve as the control group throughout.")])
    card = fixture_score.score_paths(fx, run)
    assert card["issues_from"] == "stage-7/validated.json"
    assert card["must_catch"][0]["result"] == "caught"


def test_quick_run_with_neither_file_still_scores_as_zero_issues(tmp_path):
    run = _run(tmp_path, issues=None, depth="quick")
    fx = _fixture(tmp_path, must_catch=[_entry("DD1", 11, "l1")])
    card = fixture_score.score_paths(fx, run)
    assert card["issues"] == 0 and QUICK_NOTE in card["issues_from"]


def _fake(tmp_path):
    fake = tmp_path / "claude"
    fake.write_text(FAKE_CLAUDE)
    fake.chmod(0o755)
    return fake


def test_runner_dry_run_without_a_cap_says_nothing_about_a_cap(tmp_path):
    fx = _fixture_with_paper(tmp_path)
    proc = subprocess.run(["/bin/bash", str(RUNNER), str(fx), "quick", str(tmp_path / "runs"), "--dry-run"],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    # Setup no longer asks about a cap, so the prompt answers no cap question.
    assert "setup:search_before" not in proc.stdout
    assert "--search-before" not in proc.stdout and "Search date cap" not in proc.stdout


def test_runner_search_before_flag_puts_the_cap_in_the_prompt_and_not_in_the_claude_flags(tmp_path):
    fx = _fixture_with_paper(tmp_path)
    fake = _fake(tmp_path)
    out = tmp_path / "runs"
    env = dict(os.environ, CLAUDE_BIN=str(fake), PLUMB_FAKE_DEPTH="quick", PLUMB_FAKE_CAP="2016-06-01")
    proc = subprocess.run(["/bin/bash", str(RUNNER), str(fx), "quick", str(out), "--search-before", "2016-06-01"],
                          capture_output=True, text=True, env=env)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    args = (out / "f-1-quick" / "claude_args.txt").read_text()
    assert "--search-before" not in args.split("\n")
    assert "plumb run-dir new adding --search-before 2016-06-01" in args
    assert "setup:search_before" not in args


def test_runner_reads_the_cap_from_the_answer_key_when_no_flag_is_given(tmp_path):
    fx = _fixture_with_paper(tmp_path)
    key = fx / "expected.yaml"
    key.write_text(key.read_text() + "\nsearch_before: '2016-06-01'\n", encoding="utf-8")
    proc = subprocess.run(["/bin/bash", str(RUNNER), str(fx), "quick", str(tmp_path / "runs"), "--dry-run"],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert "--search-before 2016-06-01" in proc.stdout


def test_runner_rejects_a_cap_that_is_not_a_date(tmp_path):
    fx = _fixture_with_paper(tmp_path)
    for bad in ["2016-6-1", "June 2016", "2016-13-01"]:
        proc = subprocess.run(["/bin/bash", str(RUNNER), str(fx), "quick", str(tmp_path / "runs"),
                               "--search-before", bad, "--dry-run"], capture_output=True, text=True)
        assert proc.returncode != 0 and "YYYY-MM-DD" in proc.stderr, bad
    proc = subprocess.run(["/bin/bash", str(RUNNER), str(fx), "quick", str(tmp_path / "runs"), "--search-before"],
                          capture_output=True, text=True)
    assert proc.returncode != 0 and "needs a date" in proc.stderr


def test_runner_fails_loudly_when_the_run_did_not_record_the_cap(tmp_path):
    fx = _fixture_with_paper(tmp_path)
    fake = _fake(tmp_path)
    env = dict(os.environ, CLAUDE_BIN=str(fake), PLUMB_FAKE_DEPTH="quick")
    env.pop("PLUMB_FAKE_CAP", None)
    proc = subprocess.run(["/bin/bash", str(RUNNER), str(fx), "quick", str(tmp_path / "runs"),
                           "--search-before", "2016-06-01"], capture_output=True, text=True, env=env)
    assert proc.returncode != 0
    assert "asked for a search cap of 2016-06-01" in proc.stderr


# Signatures: a signed key entry is caught only by an issue whose full text matches one of its
# regexes and whose page is near the entry's. All issues and keys below are fake.

SAMPLE_LOC = "Methods: The final sample thus consisted of 337 speeches given by the three chairs"
SAMPLE_NOTE = "the final sample of speeches is 337 in the text but the tables report 339 speeches"


def _signed(page, locator, note, signature, pages=None, kind=None, severity="Minor"):
    e = {"check": "A2", "page": page, "locator": locator, "note": note, "severity": severity,
         "signature": list(signature)}
    if pages is not None:
        e["pages"] = list(pages)
    if kind is not None:
        e["kind"] = kind
    return e


def test_signature_blocks_a_page_only_false_credit(tmp_path):
    # The issue sits on the entry's page and shares its words (final sample, speeches, chairs, tables),
    # but it is about fixed effects, not the 337 against 339 count.
    wrong = _issue("m12", ms_page=12, summary="The final sample of speeches by the three chairs is modelled "
                   "without chair fixed effects in the tables, so the final estimates mix chairs.")
    unsigned = {k: v for k, v in _signed(12, SAMPLE_LOC, SAMPLE_NOTE, ["x"]).items() if k != "signature"}
    run = _run(tmp_path, issues=[wrong])
    fx = _fixture(tmp_path, must_catch=[unsigned])
    before = fixture_score.score_paths(fx, run)["must_catch"][0]
    # Unsigned, the shared words on the same page are enough for a (false) credit.
    assert (before["result"], before["issue"]) == ("caught", "m12")
    assert before["strategy"] in ("locator", "page")

    signed = _signed(12, SAMPLE_LOC, SAMPLE_NOTE, [r"\b337\b.{0,120}\b339\b"])
    (fx / "expected.yaml").write_text(yaml.safe_dump({"must_catch": [signed]}), encoding="utf-8")
    after = fixture_score.score_paths(fx, run)["must_catch"][0]
    assert (after["result"], after["issue"], after["strategy"]) == ("missed", None, None)


def test_signature_with_page_tolerance_credits_the_right_issue(tmp_path):
    # Key page 56; the right issue says 57 (the table runs over two pages), a wrong one quotes the row on 56.
    loc = "Table 2, row BR: 0.036*** 0.034** 0.045*** 0.041**"
    wrong = _issue("4", ms_page=56, excerpt="0.036*** 0.034** 0.045*** 0.041**",
                   summary="The word-count row in Table 2 cannot be read as printed.")
    right = _issue("9", ms_page=57, summary="The main coefficient supports two stars one-tailed, not three.")
    far = _issue("20", ms_page=30, summary="Another coefficient supports two stars, not three.")
    entry = _signed(56, loc, "Model 2 BR ratio is 2.00, below 2.33", [r"\btwo stars\b|\bthree stars\b"])
    run = _run(tmp_path, issues=[far, wrong, right])
    fx = _fixture(tmp_path, must_catch=[entry])
    row = fixture_score.score_paths(fx, run)["must_catch"][0]
    assert (row["result"], row["issue"], row["strategy"]) == ("caught", "9", "signature")
    assert row["signed"] is True


def test_signature_pages_list_widens_the_window(tmp_path):
    entry = _signed(54, "Table 1, row 18 Speech location: 0.29 0.64", "a 0/1 dummy cannot have SD 0.64",
                    [r"\b0\.64\b"], pages=[17], kind="arithmetic")
    on_17 = _issue("m22", ms_page=17, summary="Table 1 prints an SD of 0.64 for the location dummy.")
    on_30 = _issue("m30", ms_page=30, summary="An SD of 0.64 appears again.")
    fx = _fixture(tmp_path, must_catch=[entry])
    row = fixture_score.score_paths(fx, _run(tmp_path / "a", issues=[on_30, on_17]))["must_catch"][0]
    assert (row["result"], row["issue"], row["kind"]) == ("caught", "m22", "arithmetic")
    row = fixture_score.score_paths(fx, _run(tmp_path / "b", issues=[on_30]))["must_catch"][0]
    assert row["result"] == "missed"


def test_signature_reads_every_string_field_of_the_issue(tmp_path):
    entry = _signed(16, "Methods: a three-day window (t-1 to t+1)", "window runs to t+1", [r"\bday after\b"])
    issue = _issue("16", ms_page=16, summary="The moderator window is too wide.",
                   why="It includes the day after the speech.", sources=["stage-4/x.md"])
    card = fixture_score.score_paths(_fixture(tmp_path, must_catch=[entry]), _run(tmp_path, issues=[issue]))
    assert card["must_catch"][0]["issue"] == "16"


def test_entry_without_a_signature_scores_as_before(tmp_path):
    run = _run(tmp_path, issues=[_issue("1", summary="Something unrelated.", check="DD1"),
                                 _issue("2", summary="Also unrelated.", check="DD3", ms_page=40)])
    fx = _fixture(tmp_path, must_catch=[_entry("DD3", 4, "The twelve never-treated regions serve as the control group")])
    card = fixture_score.score_paths(fx, run)
    # A check-id match far from the key's page still counts, and the row keeps its old shape.
    assert card["must_catch"] == [{"check": "DD3", "page": 4, "severity": "Weakens a claim", "result": "caught",
                                   "issue": "2", "strategy": "check", "survived": None}]


PLANTED_1 = ROOT / "packs" / "archival" / "fixtures" / "planted-1"


def _planted_1_rows(tmp_path, issues):
    """The planted-1 must_catch rows for fake issues, keyed P1..P12 in key order. Only the real
    answer key is read; every issue is written by the test."""
    card = fixture_score.score_paths(PLANTED_1, _run(tmp_path, issues=issues))
    return {f"P{n + 1}": r for n, r in enumerate(card["must_catch"])}


def test_planted_1_p4_only_star_issue_is_not_credited_to_p3(tmp_path):
    # Fake issues about the Model 4 business media fear star (P4) only, in star wording.
    p4 = _issue("m6", ms_page=57, summary="Business media fear in Model 4 carries two stars, not none: 0.005 "
                "with a standard error of 2.924.",
                sources=["numbers:arith:2:Business media fear/Model 4:stars_vs_se"])
    p4_no_se = _issue("m7", ms_page=56, summary="A control in Model 4 shows two stars, not three; its "
                      "coefficient cannot reach that level.")
    rows = _planted_1_rows(tmp_path, [p4, p4_no_se])
    assert (rows["P3"]["result"], rows["P3"]["issue"]) == ("missed", None)
    assert (rows["P4"]["result"], rows["P4"]["issue"]) == ("caught", "m6")


def test_planted_1_p3_is_credited_when_the_star_is_tied_to_br(tmp_path):
    for n, text in enumerate(("The main coefficient supports two stars one-tailed, not three.",
                              "BR in Model 2 is 0.036 with SE 0.018, which supports two stars, not three.",
                              "Table 2 prints 0.036*** for Model 2.")):
        rows = _planted_1_rows(tmp_path / str(n), [_issue("9", ms_page=57, summary=text)])
        assert (rows["P3"]["result"], rows["P3"]["issue"]) == ("caught", "9"), text


def test_planted_1_row_11_sd_of_0_64_is_not_credited_to_p6(tmp_path):
    # A fake issue about another Table 1 row that happens to print 0.64.
    row11 = _issue("m30", ms_page=54, summary="Table 1 row 11 reports an SD of 0.64 that does not match the "
                   "variable's range in the Methods.")
    rows = _planted_1_rows(tmp_path / "a", [row11])
    assert (rows["P6"]["result"], rows["P6"]["issue"]) == ("missed", None)
    right = _issue("m22", ms_page=17, summary="Table 1 prints an SD of 0.64 for the Washington, D.C. location "
                   "dummy, which is impossible for a 0/1 variable.")
    rows = _planted_1_rows(tmp_path / "b", [row11, right])
    assert (rows["P6"]["result"], rows["P6"]["issue"]) == ("caught", "m22")


def test_planted_1_p9_needs_the_window_not_a_bare_day_after(tmp_path):
    bare = _issue("14", ms_page=16, summary="Market reaction on the day after a speech is not studied.")
    rows = _planted_1_rows(tmp_path / "a", [bare])
    assert rows["P9"]["result"] == "missed"
    right = _issue("16", ms_page=16, summary="The fear moderator is averaged over a window that includes the "
                   "day after the speech.")
    rows = _planted_1_rows(tmp_path / "b", [bare, right])
    assert (rows["P9"]["result"], rows["P9"]["issue"]) == ("caught", "16")


@pytest.mark.parametrize("field, value", [("signature", "not a list"), ("signature", []),
                                          ("signature", ["("]), ("pages", ["56"])])
def test_bad_signature_or_pages_is_a_clear_error(tmp_path, field, value):
    entry = dict(_entry("DD1", 4, "a sentence"), **{field: value})
    fx = _fixture(tmp_path, must_catch=[entry])
    with pytest.raises(fixture_score.ScoreError, match=field):
        fixture_score.score_paths(fx, _run(tmp_path, issues=[]))
