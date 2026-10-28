"""The run log, stage headers and time left, the end-of-run scoreboard, and the setup recap."""
from __future__ import annotations
import datetime
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from plumb import progress, rundir

ROOT = Path(__file__).resolve().parents[1]


def _cli(tmp_path, *args):
    env = dict(os.environ, PYTHONPATH=str(ROOT), HOME=str(tmp_path),
               PLUMB_CONFIG=str(tmp_path / "no-config.json"))
    return subprocess.run([sys.executable, "-m", "plumb", *args], capture_output=True, text=True,
                          cwd=ROOT, env=env)


def test_run_log_appends_one_timestamped_line_each(tmp_path):
    when = datetime.datetime(2000, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc)
    first = progress.log_line(tmp_path, "Dispatched the fake summary agent.", now=when)
    progress.log_line(tmp_path, "Ran   a fake\ncheck.", now=when)
    text = (tmp_path / "run_log.md").read_text()
    assert first == "- 2000-01-02T03:04:05Z Dispatched the fake summary agent."
    assert text == ("# Run log\n\n- 2000-01-02T03:04:05Z Dispatched the fake summary agent.\n"
                    "- 2000-01-02T03:04:05Z Ran a fake check.\n")


def test_run_log_refuses_an_empty_line_or_a_missing_workspace(tmp_path):
    with pytest.raises(ValueError):
        progress.log_line(tmp_path, "   ")
    with pytest.raises(ValueError):
        progress.log_line(tmp_path / "missing", "A line.")
    assert not (tmp_path / "missing").exists()


def test_runlog_cli(tmp_path):
    r = _cli(tmp_path, "runlog", str(tmp_path), "Retried a fake table.")
    assert r.returncode == 0 and r.stdout.strip().endswith("Retried a fake table.")
    assert (tmp_path / "run_log.md").read_text().count("\n- ") == 1
    bad = _cli(tmp_path, "runlog", str(tmp_path / "missing"), "A line.")
    assert bad.returncode == 1 and "not a run's workspace folder" in bad.stdout


def test_readme_lists_the_run_log(tmp_path):
    home = tmp_path / "home"
    proj = home / "proj"
    proj.mkdir(parents=True)
    pdf = proj / "fakepaper.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    ws = Path(rundir.new_run(pdf, proj, home.resolve(), "2026-09-26")["workspace"])
    assert "run_log.md" not in rundir.write_readme(ws).read_text()
    progress.log_line(ws, "A fake line.")
    text = rundir.write_readme(ws).read_text()
    assert "- `.workspace/run_log.md`: Run log: one timestamped line for each step the chat did not show." in text


def test_estimates_cover_every_stage_that_runs_at_each_depth():
    from plumb import depth
    table = progress.estimates()
    assert table["as_of"] and "five or more runs" in table["source"]
    for d in depth.DEPTHS:
        assert sorted(int(k) for k in table["minutes"][d]) == list(depth.STAGES[d]), d
        for lo, hi in table["minutes"][d].values():
            assert isinstance(lo, int) and isinstance(hi, int) and 0 < lo <= hi, d


def test_stage_header_and_time_left():
    assert progress.stage_header("standard", 3) == "Stage 3 of 8: Theory, about 10 to 15 minutes (estimate)."
    assert progress.stage_header("full", 0).startswith("Stage 0 of 8: Intake, about ")
    assert progress.time_left("standard", 6) == "About 25 to 40 minutes left (estimate)"
    assert progress.time_left("quick", 2) == "About 10 to 20 minutes left (estimate)"


@pytest.mark.parametrize("depth_name,stage", [("quick", 3), ("standard", 8), ("standard", -1), ("huge", 1)])
def test_stage_header_refuses_a_stage_that_does_not_run(depth_name, stage):
    with pytest.raises(ValueError):
        progress.stage_header(depth_name, stage)


def test_stage_header_cli(tmp_path):
    r = _cli(tmp_path, "stage-header", "deep", "7")
    assert r.returncode == 0
    assert json.loads(r.stdout) == {"header": "Stage 7 of 8: Output, about 10 to 20 minutes (estimate).",
                                    "left": "About 10 to 20 minutes left (estimate)"}
    bad = _cli(tmp_path, "stage-header", "quick", "4")
    assert bad.returncode == 1 and "does not run at Quick depth" in bad.stdout


def _brief(ws: Path, *lines: str):
    (ws / "brief.md").write_text("\n".join(lines) + "\n")


def test_scoreboard_reads_each_stage_row_and_the_last_one_wins(tmp_path):
    (tmp_path / "run.json").write_text(json.dumps({"depth": "standard"}))
    _brief(tmp_path, "Stage 0: set up.", "Scoreboard 0: Done | Setup answered | Nothing",
           "Stage 1: numbers.", "Scoreboard 1: Done | 3 fake flags | 1 flag",
           "Scoreboard 1: Done | 2 fake flags | Nothing")
    table = progress.scoreboard(tmp_path)
    lines = table.splitlines()
    assert lines[0] == "| Stage | Status | Found | Needs you |" and lines[1] == "|---|---|---|---|"
    assert "| 0 Intake | Done | Setup answered | Nothing |" in lines
    assert "| 1 Verify | Done | 2 fake flags | Nothing |" in lines
    assert "| 7 Output | Not recorded |  |  |" in lines and len(lines) == 10


def test_scoreboard_marks_stages_quick_depth_skips(tmp_path):
    (tmp_path / "run.json").write_text(json.dumps({"depth": "quick"}))
    _brief(tmp_path, "Scoreboard 2: Done | The reading | You confirmed it | extra")
    table = progress.scoreboard(tmp_path)
    assert "| 3 Theory | Not run at Quick depth |  |  |" in table
    assert "| 2 Understand | Done | The reading | You confirmed it extra |" in table


def test_scoreboard_cli_with_no_brief(tmp_path):
    r = _cli(tmp_path, "scoreboard", str(tmp_path))
    assert r.returncode == 0 and r.stdout.count("| Not recorded |") == 8


def test_scoreboard_for_a_run_from_before_this_change(tmp_path):
    (tmp_path / "run.json").write_text(json.dumps({"tier": "full"}))
    _brief(tmp_path, "Stage 0: set up, from an older run.", "A second line.", "Stage 1: numbers checked.")
    table = progress.scoreboard(tmp_path)
    assert table.count("| Not recorded |") == 8 and "Not run at" not in table


def _setup_run(ws: Path, depth_name="standard", with_openai=False):
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "run.json").write_text(json.dumps({
        "pdf_path": "/fake/fakepaper.pdf", "depth": depth_name, "permission": "journal", "role": "referee",
        "journal": "orgsci", "level": "auto", "outputs": ["issues_list", "annotated_pdf"],
        "needs_zero_retention": False}))
    rec = {"role": "referee", "permission": "journal", "provider": "FakeProvider",
           "provider_trains_on_inputs": False, "retention_days": 30,
           "egress": ["manuscript_text", "search_queries"]}
    if with_openai:
        rec["egress"].append("codex_stress_test")
        # A referee at Organization Science needs zero retention for OpenAI too (wave C3).
        rec["stress_test_provider"] = {"provider": "OpenAI", "trains_on_inputs": False, "retention_days": 0,
                                       "zero_retention_confirmed": True}
    (ws / "consent.json").write_text(json.dumps(rec))
    return ws


def test_recap_lists_every_setting(tmp_path):
    ws = _setup_run(tmp_path / "plumb_output" / "2000-01-01" / ".workspace")
    table = progress.recap(ws, ROOT / "profiles")
    lines = table.splitlines()
    assert lines[:2] == ["| Setting | Your answer |", "|---|---|"]
    for row in ("| Permission | A journal sent it to you for review |", "| Journal | Organization Science |",
                "| Depth | Standard |", "| Check-in level | Auto |", "| Outputs | Issues list, Annotated PDF |",
                "| Stress test | A fresh Claude agent |",
                "| Provider and retention | FakeProvider, does not train on inputs, keeps inputs 30 days |",
                f"| Output folder | {ws.parent} |", "| Search date cap | None |"):
        assert row in lines, row
    assert len(lines) == 11 and "role" not in table.lower() and "—" not in table


def test_recap_names_codex_and_its_terms_and_quick_has_no_stress_test(tmp_path):
    ws = _setup_run(tmp_path / "a" / ".workspace", with_openai=True)
    table = progress.recap(ws, codex_enabled=True, codex_on_path=True)
    assert "| Stress test | Codex, which sends the paper to OpenAI |" in table
    assert "; OpenAI, does not train on inputs, keeps nothing (stress test) |" in table
    quick = _setup_run(tmp_path / "b" / ".workspace", depth_name="quick")
    assert "| Stress test | None at Quick depth |" in progress.recap(quick, codex_enabled=True, codex_on_path=True)


def test_recap_before_consent_and_without_a_run_file(tmp_path):
    ws = _setup_run(tmp_path / "c" / ".workspace")
    (ws / "consent.json").unlink()
    assert "| Provider and retention | Not recorded yet |" in progress.recap(ws)
    with pytest.raises(ValueError):
        progress.recap(tmp_path / "missing")


def test_recap_marks_checked_facts_only_outputs(tmp_path):
    ws = _setup_run(tmp_path / "e" / ".workspace")
    run = json.loads((ws / "run.json").read_text())
    run["journal"], run["outputs"], run["issues_list_mode"] = "orgsci", ["issues_list", "editor_memo"], "facts_only"
    (ws / "run.json").write_text(json.dumps(run))
    assert "| Outputs | Issues list, Checked-facts memo for an editor (checked facts only) |" in progress.recap(ws)
    run["issues_list_mode"] = "full"
    (ws / "run.json").write_text(json.dumps(run))
    assert "(checked facts only)" not in progress.recap(ws)


def test_recap_cli(tmp_path):
    ws = _setup_run(tmp_path / "d" / ".workspace")
    r = _cli(tmp_path, "recap", str(ws), "--profiles", str(ROOT / "profiles"))
    assert r.returncode == 0 and "| Journal | Organization Science |" in r.stdout
    assert "| Stress test | A fresh Claude agent |" in r.stdout
    bad = _cli(tmp_path, "recap", str(tmp_path / "missing"))
    assert bad.returncode == 1 and "run.json" in bad.stdout


def test_recap_answer_is_a_preference_never_an_override(tmp_path):
    from plumb import audit, checkin
    for level in checkin.LEVELS:
        assert "setup" in checkin.stops_for(level, "quick") and "setup" in checkin.stops_for(level, "deep")
    checkin.record(tmp_path, "setup", "setup:recap", "A. Start the review (Recommended)", "B. Change something",
                   "preference")
    checkin.record(tmp_path, "setup", "setup:recap", "A. Start the review (Recommended)",
                   "A. Start the review (Recommended)", "preference")
    counts = audit.counts(tmp_path)
    assert counts["override"] == 0 and counts["user_answers"] == 0


def test_recap_survives_a_broken_consent_file(tmp_path):
    ws = _setup_run(tmp_path / "e" / ".workspace")
    (ws / "consent.json").write_text("{not json")
    assert "| Provider and retention | Not recorded yet |" in progress.recap(ws)
    (ws / "consent.json").write_text(json.dumps({"role": "referee"}))
    assert "| Stress test | A fresh Claude agent |" in progress.recap(ws, codex_enabled=True, codex_on_path=True)
    (ws / "consent.json").write_text("[]")
    assert "| Provider and retention | Not recorded yet |" in progress.recap(ws)


def test_stage_0_header_needs_no_depth():
    assert progress.stage_header("none", 0) == "Stage 0 of 8: Intake."
    assert progress.time_left("none", 0) == ""
    with pytest.raises(ValueError):
        progress.stage_header("none", 1)


def test_stage_0_header_cli_without_a_depth(tmp_path):
    r = _cli(tmp_path, "stage-header", "none", "0")
    assert r.returncode == 0
    assert json.loads(r.stdout) == {"header": "Stage 0 of 8: Intake.", "left": ""}


def test_header_counts_the_stages_that_run_at_quick():
    assert progress.stage_header("quick", 7) == \
        "Stage 7 of 8: Output (stage 4 of 4 at Quick depth), about 5 to 10 minutes (estimate)."
    assert progress.stage_header("quick", 0).startswith("Stage 0 of 8: Intake (stage 1 of 4 at Quick depth), ")


def test_skill_shows_the_stage_0_header_and_rebuilds_the_task_list_after_the_recap():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "skills/review"
    skill = (root / "SKILL.md").read_text(encoding="utf-8")
    stage0 = (root / "stages/stage-0-intake.md").read_text(encoding="utf-8")
    assert "plumb stage-header none 0" in skill
    recap = stage0[stage0.index("8. Recap"):stage0.index("9. Only now")]
    assert "TASKLIST" in recap and "runs at the chosen depth" in recap


def test_scoreboard_counts_stage_1_and_4_from_their_files(tmp_path):
    """Found for Stages 1 and 4 comes from flags.json and questions.json, not the brief (wave C9)."""
    from plumb import checkin
    (tmp_path / "run.json").write_text(json.dumps({"depth": "standard"}))
    _brief(tmp_path, "Scoreboard 1: Done | 99 fake flags | 1 flag you kept",
           "Scoreboard 4: Done | 99 fake issues | Nothing")
    (tmp_path / "stage-1").mkdir()
    flags = [{"id": "1", "item": "numbers:cell:1", "kind": "cell"},
             {"id": "2", "item": "numbers:text:1", "kind": "number"},
             {"id": "3", "item": "numbers:pack:inference:1", "kind": "number"},
             {"id": "4", "item": "numbers:hyp:1", "kind": "number"},
             {"id": "5", "item": "ref:2", "kind": "reference"}]
    (tmp_path / "stage-1" / "flags.json").write_text(json.dumps(flags))
    (tmp_path / "stage-4").mkdir()
    cards = [{"id": "majors:1", "stop": "majors", "depends_on": [], "prune_if": {}},
             {"id": "majors:2", "stop": "majors", "depends_on": ["against:1"], "prune_if": {"against:1": "C"}},
             {"id": "majors:3", "stop": "majors", "depends_on": [], "prune_if": {}}]
    (tmp_path / "stage-4" / "questions.json").write_text(json.dumps(cards))
    checkin.record(tmp_path, "against", "against:1", "A. Plausible (Recommended)", "C. Not plausible")
    table = progress.scoreboard(tmp_path)
    assert "| 1 Verify | Done | 1 cell flag, 3 number flags, 1 reference flag | 1 flag you kept |" in table
    assert "| 4 Diagnose | Done | 2 major issues | Nothing |" in table


def test_skill_says_where_the_scoreboard_counts_come_from():
    from pathlib import Path
    skill = (Path(__file__).resolve().parents[1] / "skills/review/SKILL.md").read_text(encoding="utf-8")
    assert "`plumb scoreboard` counts Found for Stages 1 and 4" in skill


def test_estimates_add_time_for_each_pack(tmp_path):
    """Stages 1, 3, and 4 take longer with each pack the run uses (wave C10)."""
    table = progress.estimates()
    assert sorted(table["per_pack"]) == ["1", "3", "4"]
    lo, hi = table["per_pack"]["4"]
    assert progress.stage_header("standard", 4, packs=2) == \
        f"Stage 4 of 8: Diagnose, about {15 + 2 * lo} to {25 + 2 * hi} minutes (estimate)."
    assert progress.stage_header("standard", 2, packs=2) == progress.stage_header("standard", 2)
    assert progress.stage_header("standard", 3, packs=0) == "Stage 3 of 8: Theory, about 10 to 15 minutes (estimate)."
    base = progress.time_left("standard", 1)
    assert base != progress.time_left("standard", 1, packs=1)
    r = _cli(tmp_path, "stage-header", "standard", "4", "--packs", "2")
    assert json.loads(r.stdout)["header"] == progress.stage_header("standard", 4, packs=2)


def test_skill_passes_the_pack_count_to_the_header():
    from pathlib import Path
    skill = (Path(__file__).resolve().parents[1] / "skills/review/SKILL.md").read_text(encoding="utf-8")
    assert "`--packs <N>`, with N the number of names in `packs` in `run.json`" in skill
