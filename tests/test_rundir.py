"""The output folder: root choice, dated run folders, "Somewhere else", resume, and older runs.
Every path is under pytest's tmp_path, which stands in for the home folder."""
from __future__ import annotations
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from plumb import audit, rundir

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def home(tmp_path):
    h = tmp_path / "home"
    h.mkdir()
    return h.resolve()


def _pdf(folder: Path, name="fakepaper.pdf") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / name
    p.write_bytes(b"%PDF-1.4 fake")
    return p


def test_root_is_the_working_directory_when_it_holds_the_pdf(home):
    proj = home / "projects" / "fake"
    pdf = _pdf(proj / "drafts")
    assert rundir.choose_root(pdf, proj, home) == proj.resolve()


def test_root_is_a_paper_folder_when_the_pdf_is_outside_the_working_directory(home):
    pdf = _pdf(home / "elsewhere")
    assert rundir.choose_root(pdf, home / "projects", home) == (home / "elsewhere" / "fakepaper").resolve()


@pytest.mark.parametrize("sub", ["", "Desktop", "Downloads", "Documents", "Dropbox",
                                 "Library/CloudStorage/Dropbox-FakeOrg", "Library/CloudStorage/iCloud Drive",
                                 "Library/Mobile Documents/com~apple~CloudDocs"])
def test_excluded_working_directories_use_a_paper_folder(home, sub):
    cwd = home / sub if sub else home
    pdf = _pdf(cwd)
    assert rundir.choose_root(pdf, cwd, home) == (cwd / "fakepaper").resolve()


def test_no_project_directory_uses_a_paper_folder(home):
    pdf = _pdf(home / "projects" / "fake")
    assert rundir.choose_root(pdf, None, home) == (home / "projects" / "fake" / "fakepaper").resolve()


def test_new_run_creates_dated_folder_and_first_run_json(home):
    proj = home / "proj"
    pdf = _pdf(proj)
    out = rundir.new_run(pdf, proj, home, "2026-09-26")
    ws = Path(out["workspace"])
    assert ws == (proj / "plumb_output" / "2026-09-26" / ".workspace").resolve()
    assert json.loads((ws / "run.json").read_text()) == {"pdf_path": str(pdf.resolve()), "started": "2026-09-26"}
    assert Path(out["run_dir"]) == ws.parent


def test_same_date_gets_a_numbered_folder(home):
    proj = home / "proj"
    pdf = _pdf(proj)
    names = [Path(rundir.new_run(pdf, proj, home, "2026-09-26")["run_dir"]).name for _ in range(3)]
    assert names == ["2026-09-26", "2026-09-26-2", "2026-09-26-3"]


def test_new_run_without_a_date_records_when_it_started(home):
    proj = home / "proj"
    ws = Path(rundir.new_run(_pdf(proj), proj, home)["workspace"])
    started = json.loads((ws / "run.json").read_text())["started"]
    assert started[:10] == ws.parent.name[:10] and "T" in started


def _snapshot(folder: Path) -> dict:
    return {str(f.relative_to(folder)): f.read_bytes() for f in sorted(folder.rglob("*")) if f.is_file()}


def test_fresh_run_beside_an_unfinished_run_gets_its_own_folder_and_leaves_the_old_one(home):
    """Ruling 21: a repeat run never resumes an unfinished run of the same PDF."""
    proj = home / "proj"
    pdf = _pdf(proj)
    old = rundir.new_run(pdf, proj, home, "2026-09-26")
    audit.log_event(Path(old["workspace"]), "checkin", stop="setup", item="setup:depth", recommended="", answer="A")
    before = _snapshot(Path(old["run_dir"]))
    index_before = rundir.index_path(home).read_text()
    fresh = rundir.new_run(pdf, proj, home, "2026-09-26", fresh=True)
    assert Path(fresh["run_dir"]).name == "2026-09-26-2"
    assert _snapshot(Path(old["run_dir"])) == before
    run = json.loads((Path(fresh["workspace"]) / "run.json").read_text())
    assert run["fresh"] is True and run["unfinished_run"] == old["run_dir"]
    assert audit.read_events(Path(fresh["workspace"])) == []
    # The old run stays unfinished in the index; only the new entry was added.
    entries = json.loads(rundir.index_path(home).read_text())
    assert [e for e in entries if e["run_dir"] == old["run_dir"]] == json.loads(index_before)
    assert {e["run_dir"]: e["finished"] for e in entries} == {old["run_dir"]: False, fresh["run_dir"]: False}


def test_find_returns_the_fresh_run_until_it_finishes_then_the_old_one(home):
    proj = home / "proj"
    pdf = _pdf(proj)
    old = rundir.new_run(pdf, proj, home, "2026-09-26")
    fresh = rundir.new_run(pdf, proj, home, "2026-09-26", fresh=True)
    assert rundir.find_unfinished(pdf, proj, home)["workspace"] == fresh["workspace"]
    # Stage 7 logs the final output event and `plumb log` then marks the index.
    audit.log_event(Path(fresh["workspace"]), "output", final=True, files=["issues_list.md"])
    assert rundir.mark_finished(Path(fresh["workspace"]), home)
    assert rundir.find_unfinished(pdf, proj, home)["workspace"] == old["workspace"]


def test_fresh_run_with_no_unfinished_run_names_none(home):
    proj = home / "proj"
    out = rundir.new_run(_pdf(proj), proj, home, "2026-09-26", fresh=True)
    run = json.loads((Path(out["workspace"]) / "run.json").read_text())
    assert run["fresh"] is True and "unfinished_run" not in run


def test_fresh_run_names_a_legacy_workspace_it_left_alone(home):
    proj = home / "proj"
    pdf = _pdf(proj)
    legacy = proj / "review_workspace"
    legacy.mkdir()
    (legacy / "run.json").write_text(json.dumps({"pdf_path": str(pdf.resolve())}))
    out = rundir.new_run(pdf, proj, home, "2026-09-26", fresh=True)
    run = json.loads((Path(out["workspace"]) / "run.json").read_text())
    assert run["unfinished_run"] == str(legacy.resolve())
    assert (legacy / "run.json").exists()


def test_find_breaks_a_same_name_tie_on_the_newest_start(home):
    # Start over, then move the second run "Somewhere else": both folders are named 2026-09-26.
    proj = home / "proj"
    pdf = _pdf(proj)
    first = Path(rundir.new_run(pdf, proj, home, "2026-09-26")["workspace"])
    second = Path(rundir.new_run(pdf, proj, home, "2026-09-26")["workspace"])
    for ws, t in ((first, "2026-09-26T09:00:00"), (second, "2026-09-26T11:00:00")):
        run = json.loads((ws / "run.json").read_text())
        (ws / "run.json").write_text(json.dumps(dict(run, started=t)))
    moved = Path(rundir.move_run(second.parent, home / "other", home)["workspace"])
    assert moved.parent.name == first.parent.name
    assert rundir.find_unfinished(pdf, proj, home)["workspace"] == str(moved.resolve())


def test_somewhere_else_moves_the_empty_run_folder(home):
    pdf = _pdf(home / "Downloads")
    first = rundir.new_run(pdf, home / "Downloads", home, "2026-09-26")
    moved = rundir.move_run(Path(first["run_dir"]), home / "reviews")
    assert Path(moved["workspace"]) == (home / "reviews" / "plumb_output" / "2026-09-26" / ".workspace").resolve()
    assert (Path(moved["workspace"]) / "run.json").exists()
    assert not (home / "Downloads" / "fakepaper").exists()
    assert pdf.exists()


def _finish(ws: Path):
    audit.log_event(ws, "output", final=True, files=["issues_list.md"])


def test_find_returns_the_newest_unfinished_run_for_this_pdf(home):
    proj = home / "proj"
    pdf, other = _pdf(proj), _pdf(proj, "otherpaper.pdf")
    old = rundir.new_run(pdf, proj, home, "2026-09-20")
    done = rundir.new_run(pdf, proj, home, "2026-09-25")
    _finish(Path(done["workspace"]))
    rundir.new_run(other, proj, home, "2026-09-26")
    found = rundir.find_unfinished(pdf, proj, home)
    assert found == {"workspace": old["workspace"], "legacy": False}
    newer = rundir.new_run(pdf, proj, home, "2026-09-20")
    assert rundir.find_unfinished(pdf, proj, home)["workspace"] == newer["workspace"]


def test_find_nothing(home):
    proj = home / "proj"
    assert rundir.find_unfinished(_pdf(proj), proj, home) == {"workspace": None, "legacy": False}


def test_find_and_adopt_a_legacy_workspace(home):
    proj = home / "proj"
    pdf = _pdf(proj)
    legacy = proj / "review_workspace"
    legacy.mkdir()
    (legacy / "run.json").write_text(json.dumps({"pdf_path": str(pdf.resolve()), "output": "fix_list",
                                                  "depth": "standard"}))
    audit.log_event(legacy, "checkin", stop="setup", item="setup:role", recommended="", answer="A. Mine", note="preference")
    found = rundir.find_unfinished(pdf, proj, home)
    assert found == {"workspace": str(legacy.resolve()), "legacy": True}
    out = rundir.adopt_legacy(legacy, pdf, proj, home)
    ws = Path(out["workspace"])
    assert not legacy.exists() and (ws / "run.json").exists()
    assert Path(out["run_dir"]).name == audit.read_events(ws)[0]["ts"][:10]


def test_legacy_run_with_stage_7_in_its_brief_is_finished(home):
    proj = home / "proj"
    pdf = _pdf(proj)
    legacy = proj / "review_workspace"
    legacy.mkdir()
    (legacy / "run.json").write_text(json.dumps({"pdf_path": str(pdf.resolve())}))
    (legacy / "brief.md").write_text("Stage 7: output written.\nDone.\n")
    assert rundir.find_unfinished(pdf, proj, home)["workspace"] is None


def test_legacy_workspace_for_a_different_pdf_is_not_offered_or_adopted(home):
    proj = home / "proj"
    a, b = _pdf(proj, "a.pdf"), _pdf(proj, "b.pdf")
    legacy = proj / "review_workspace"
    legacy.mkdir()
    (legacy / "run.json").write_text(json.dumps({"pdf_path": str(a.resolve()), "output": "fix_list",
                                                  "depth": "standard"}))
    assert rundir.find_unfinished(b, proj, home)["workspace"] is None
    with pytest.raises(ValueError):
        rundir.adopt_legacy(legacy, b, proj, home)
    assert legacy.exists()
    found = rundir.find_unfinished(a, proj, home)
    assert found == {"workspace": str(legacy.resolve()), "legacy": True}


@pytest.mark.parametrize("old,outputs,mode", [
    ("fix_list", ["issues_list"], "full"),
    ("report", ["report"], "full"),
    ("memo", ["issues_list"], "facts_only"),
])
def test_migrate_maps_the_old_output_field(tmp_path, old, outputs, mode):
    (tmp_path / "run.json").write_text(json.dumps({"output": old, "depth": "standard"}))
    run = rundir.migrate_run(tmp_path)
    assert run["outputs"] == outputs and run["issues_list_mode"] == mode and "output" not in run
    assert json.loads((tmp_path / "run.json").read_text()) == run


def test_migrate_uses_the_recorded_setup_answer(tmp_path):
    (tmp_path / "run.json").write_text(json.dumps({"depth": "standard"}))
    assert rundir.migrate_run(tmp_path, "B. Mock referee report")["outputs"] == ["report"]
    (tmp_path / "run.json").write_text(json.dumps({"depth": "standard"}))
    assert rundir.migrate_run(tmp_path, "A. Fix list")["outputs"] == ["issues_list"]


def test_migrate_quick_run_is_facts_only(tmp_path):
    (tmp_path / "run.json").write_text(json.dumps({"output": "report", "depth": "quick"}))
    run = rundir.migrate_run(tmp_path)
    assert run["outputs"] == ["issues_list"] and run["issues_list_mode"] == "facts_only"


def test_migrate_sets_aside_an_old_report_draft(tmp_path):
    (tmp_path / "stage-5").mkdir()
    (tmp_path / "stage-5" / "draft.txt").write_text("1. A fake comment.\n")
    (tmp_path / "brief.md").write_text("Stage 4: done.\nx\nStage 5: done.\ny\n")
    (tmp_path / "run.json").write_text(json.dumps({"output": "report", "depth": "standard"}))
    rundir.migrate_run(tmp_path)
    assert (tmp_path / "stage-5" / "draft_legacy.txt").exists() and not (tmp_path / "stage-5" / "draft.txt").exists()
    assert "Stage 5:" not in (tmp_path / "brief.md").read_text()
    assert "Stage 4:" in (tmp_path / "brief.md").read_text()


@pytest.mark.parametrize("text", ["No numbers were left unverified.\n", "(none)\n",
                                  "These cells were left unverified:\n- cell `Table 1:1:1`, p. 2\n"])
def test_migrate_never_resets_stage_1_on_a_current_run(tmp_path, text):
    (tmp_path / "stage-1").mkdir()
    (tmp_path / "stage-1" / "unverified_numbers.md").write_text(text)
    (tmp_path / "stage-1" / "flags.json").write_text("[]")
    (tmp_path / "brief.md").write_text("Stage 1: done.\ny\n")
    (tmp_path / "run.json").write_text(json.dumps({"outputs": ["issues_list"], "depth": "standard"}))
    for _ in range(2):
        rundir.migrate_run(tmp_path)
    assert "Stage 1:" in (tmp_path / "brief.md").read_text()


def test_migrate_resets_stage_1_on_an_old_run_with_no_flags_file(tmp_path):
    (tmp_path / "stage-1").mkdir()
    (tmp_path / "stage-1" / "unverified_numbers.md").write_text("Intro line.\n- Some fake number on page four\n")
    (tmp_path / "brief.md").write_text("Stage 1: done.\ny\n")
    (tmp_path / "run.json").write_text(json.dumps({"outputs": ["issues_list"], "depth": "standard"}))
    rundir.migrate_run(tmp_path)
    assert "Stage 1:" not in (tmp_path / "brief.md").read_text()


def test_migrate_resets_stage_1_when_old_unverified_lines_cannot_be_read(tmp_path):
    (tmp_path / "stage-1").mkdir()
    (tmp_path / "stage-1" / "unverified_numbers.md").write_text("- Some fake number on page four\n")
    (tmp_path / "brief.md").write_text("Stage 0: done.\nx\nStage 1: done.\ny\nStage 2: done.\nz\n")
    (tmp_path / "run.json").write_text(json.dumps({"outputs": ["issues_list"], "depth": "standard"}))
    rundir.migrate_run(tmp_path)
    brief = (tmp_path / "brief.md").read_text()
    assert "Stage 1:" not in brief and "Stage 0:" in brief and "Stage 2:" in brief


def test_migrate_keeps_stage_1_when_old_unverified_lines_are_read(tmp_path):
    (tmp_path / "stage-1").mkdir()
    (tmp_path / "stage-1" / "unverified_numbers.md").write_text("- Table 4, row 2, column 3 (p. 11)\n")
    (tmp_path / "brief.md").write_text("Stage 1: done.\ny\n")
    (tmp_path / "run.json").write_text(json.dumps({"outputs": ["issues_list"], "depth": "standard"}))
    rundir.migrate_run(tmp_path)
    assert "Stage 1:" in (tmp_path / "brief.md").read_text()


@pytest.mark.parametrize("answer,permission,role", [("A. Mine", "mine", "author"),
                                                    ("B. Reviewing it", "journal", "referee")])
def test_migrate_maps_an_old_role_answer_to_permission(tmp_path, answer, permission, role):
    (tmp_path / "run.json").write_text(json.dumps({"output": "fix_list", "depth": "standard"}))
    run = rundir.migrate_run(tmp_path, role_answer=answer)
    assert run["permission"] == permission and run["role"] == role


def test_migrate_adds_permission_to_an_old_role_field(tmp_path):
    (tmp_path / "run.json").write_text(json.dumps({"output": "report", "depth": "standard", "role": "referee"}))
    run = rundir.migrate_run(tmp_path)
    assert run["permission"] == "journal" and run["role"] == "referee"


def test_migrate_run_cli_reads_the_old_role_answer(tmp_path):
    (tmp_path / "run.json").write_text(json.dumps({"depth": "standard"}))
    audit.log_event(tmp_path, "checkin", stop="setup", item="setup:role", recommended="",
                    answer="B. Reviewing it", note="preference")
    r = _cli(tmp_path, "migrate-run", str(tmp_path))
    assert r.returncode == 0 and json.loads(r.stdout)["permission"] == "journal"


def test_readme_says_whose_permission_and_never_role(home):
    proj = home / "proj"
    pdf = _pdf(proj)
    ws = Path(rundir.new_run(pdf, proj, home, "2026-09-26")["workspace"])
    run = json.loads((ws / "run.json").read_text())
    run.update({"role": "author", "permission": "author_asked", "outputs": ["issues_list"]})
    (ws / "run.json").write_text(json.dumps(run))
    text = rundir.write_readme(ws).read_text()
    assert "- Permission: The author asked you to read it" in text
    assert "role" not in text.lower()


def _delivered(ws: Path, name: str, body: str = "Fake output.\n") -> str:
    """Write a delivered file into the run folder and return its SHA-256."""
    import hashlib
    (ws.parent / name).write_text(body)
    return hashlib.sha256(body.encode()).hexdigest()


def _final(ws, sha, code, output="issues_list", name="issues_list.md", step="validate-output"):
    audit.log_event(ws, "verification", check="final", output=output, file=name, sha256=sha, step=step, exit=code)


def _issues_list_run(home) -> Path:
    proj = home / "proj"
    ws = Path(rundir.new_run(_pdf(proj), proj, home, "2026-09-26")["workspace"])
    run = json.loads((ws / "run.json").read_text())
    run.update({"outputs": ["issues_list"], "issues_list_mode": "full"})
    (ws / "run.json").write_text(json.dumps(run))
    return ws


def test_readme_uses_only_the_last_final_pass(home):
    ws = _issues_list_run(home)
    sha = _delivered(ws, "issues_list.md")
    _final(ws, sha, 0)
    audit.log_event(ws, "checkin", stop="draft", item="draft:ready", recommended="A", answer="A", note="")
    _final(ws, sha, 1)
    assert "- `issues_list.md`: Not verified." in rundir.write_readme(ws).read_text()
    # A failing pass before the last draft:ready answer no longer counts once a new pass passes.
    audit.log_event(ws, "checkin", stop="draft", item="draft:ready", recommended="A", answer="A", note="")
    _final(ws, sha, 0)
    assert "- `issues_list.md`: Verified." in rundir.write_readme(ws).read_text()


def test_readme_citation_lookup_with_network_trouble_is_not_a_failure(home):
    ws = _issues_list_run(home)
    sha = _delivered(ws, "issues_list.md")
    _final(ws, sha, 0)
    _final(ws, sha, 2, step="verify_citations")
    text = rundir.write_readme(ws).read_text()
    assert "- `issues_list.md`: Verified. Citation lookup was unavailable. The issues Plumb kept" in text


def test_readme_exit_2_from_any_other_check_is_a_failure(home):
    ws = _issues_list_run(home)
    sha = _delivered(ws, "issues_list.md")
    _final(ws, sha, 0, step="verify_citations")
    _final(ws, sha, 2, step="verify_quotes")
    assert "- `issues_list.md`: Not verified." in rundir.write_readme(ws).read_text()


def test_readme_ignores_final_events_for_a_file_that_has_since_changed(home):
    ws = _issues_list_run(home)
    old = _delivered(ws, "issues_list.md")
    _final(ws, old, 0)
    _delivered(ws, "issues_list.md", "Fake output, edited after the check.\n")
    assert "- `issues_list.md`: Not verified." in rundir.write_readme(ws).read_text()
    (ws.parent / "issues_list.md").unlink()
    assert "- `issues_list.md`: Not verified." in rundir.write_readme(ws).read_text()


def test_readme_marks_the_annotated_pdf_from_its_final_check(home):
    ws = _issues_list_run(home)
    run = json.loads((ws / "run.json").read_text())
    run["outputs"] = ["annotated_pdf"]
    (ws / "run.json").write_text(json.dumps(run))
    sha = _delivered(ws, "fakepaper_annotated.pdf")
    _final(ws, sha, 1, output="annotated_pdf", name="fakepaper_annotated.pdf", step="check")
    assert "- `fakepaper_annotated.pdf`: Not verified." in rundir.write_readme(ws).read_text()
    audit.log_event(ws, "checkin", stop="draft", item="draft:ready", recommended="A", answer="A", note="")
    _final(ws, sha, 0, output="annotated_pdf", name="fakepaper_annotated.pdf", step="check")
    assert "- `fakepaper_annotated.pdf`: Verified." in rundir.write_readme(ws).read_text()


def test_readme_marks_each_output_verified_or_not(home):
    proj = home / "proj"
    pdf = _pdf(proj)
    ws = Path(rundir.new_run(pdf, proj, home, "2026-09-26")["workspace"])
    run = json.loads((ws / "run.json").read_text())
    run.update({"outputs": ["issues_list", "annotated_pdf", "report"], "issues_list_mode": "full"})
    (ws / "run.json").write_text(json.dumps(run))
    il, rep = _delivered(ws, "issues_list.md"), _delivered(ws, "mock_report.txt")
    for step, code in (("validate-output", 0), ("verify_quotes", 0)):
        audit.log_event(ws, "verification", check="final", output="issues_list", file="issues_list.md",
                        sha256=il, step=step, exit=code)
    audit.log_event(ws, "verification", check="final", output="report", file="mock_report.txt",
                    sha256=rep, step="validate-output", exit=1)
    text = rundir.write_readme(ws).read_text()
    assert "- `issues_list.md`: Verified." in text
    assert "- `mock_report.txt`: Not verified." in text and "- `fakepaper_annotated.pdf`: Not verified." in text


def test_migrate_leaves_a_new_run_alone(tmp_path):
    new = {"outputs": ["issues_list", "annotated_pdf"], "issues_list_mode": "full", "depth": "deep"}
    (tmp_path / "run.json").write_text(json.dumps(new))
    assert rundir.migrate_run(tmp_path) == new


def test_migrate_reruns_synthesis_for_an_old_fix_list_run(tmp_path):
    (tmp_path / "stage-5").mkdir()
    (tmp_path / "stage-5" / "draft.md").write_text("## Issues\n")
    (tmp_path / "brief.md").write_text("Stage 4: done.\nStage 5: done.\nStage 6: done.\n")
    (tmp_path / "run.json").write_text(json.dumps({"output": "fix_list", "depth": "standard"}))
    rundir.migrate_run(tmp_path)
    assert (tmp_path / "brief.md").read_text() == "Stage 4: done.\n"


def test_migrate_keeps_the_brief_of_a_current_run(tmp_path):
    (tmp_path / "brief.md").write_text("Stage 4: done.\nStage 5: done.\n")
    (tmp_path / "run.json").write_text(json.dumps({"outputs": ["issues_list"], "issues_list_mode": "full"}))
    rundir.migrate_run(tmp_path)
    assert (tmp_path / "brief.md").read_text() == "Stage 4: done.\nStage 5: done.\n"


def test_run_index_finds_a_run_moved_somewhere_else(home):
    proj = home / "proj"
    pdf = _pdf(proj)
    first = rundir.new_run(pdf, proj, home, "2026-09-26")
    moved = rundir.move_run(Path(first["run_dir"]), home / "reviews", home)
    assert rundir.find_unfinished(pdf, proj, home) == {"workspace": moved["workspace"], "legacy": False}
    assert json.loads(rundir.index_path(home).read_text()) == [
        {"pdf_path": str(pdf.resolve()), "run_dir": moved["run_dir"], "started": "2026-09-26", "finished": False}]


def test_run_index_marks_a_finished_run_through_the_log(home):
    proj = home / "proj"
    pdf = _pdf(proj)
    ws = Path(rundir.new_run(pdf, proj, home, "2026-09-26")["workspace"])
    r = _cli(home, "log", str(ws), "output", '{"final":true,"files":["issues_list.md"]}')
    assert r.returncode == 0
    assert json.loads(rundir.index_path(home).read_text())[0]["finished"] is True
    assert rundir.find_unfinished(pdf, proj, home)["workspace"] is None


def test_mark_finished_never_creates_the_index(home, tmp_path):
    assert rundir.mark_finished(tmp_path / "x" / ".workspace", home) is False
    assert not rundir.index_path(home).exists()


def test_readme_names_the_chosen_files_and_the_record(home):
    proj = home / "proj"
    pdf = _pdf(proj)
    ws = Path(rundir.new_run(pdf, proj, home, "2026-09-26")["workspace"])
    run = json.loads((ws / "run.json").read_text())
    run.update({"depth": "standard", "level": "light", "journal": "orgsci", "role": "author",
                "outputs": ["issues_list", "annotated_pdf"], "issues_list_mode": "full"})
    (ws / "run.json").write_text(json.dumps(run))
    (ws / "qc.md").write_text("# QC\n")
    text = rundir.write_readme(ws, ROOT / "profiles").read_text()
    for s in ("Paper: fakepaper.pdf", "Depth: Standard", "Check-in level: Light", "Journal: Organization Science",
              "Date: 2026-09-26", "`issues_list.md`", "`fakepaper_annotated.pdf`", "`paper_summary.md`",
              "`.workspace/qc.md`", "`.workspace/run.json`"):
        assert s in text, s
    assert "mock_report.txt" not in text and "consent.json" not in text
    assert "—" not in text


def test_readme_says_the_run_started_fresh_beside_an_unfinished_run(home):
    proj = home / "proj"
    pdf = _pdf(proj)
    old = rundir.new_run(pdf, proj, home, "2026-09-26")
    ws = Path(rundir.new_run(pdf, proj, home, "2026-09-26", fresh=True)["workspace"])
    text = rundir.write_readme(ws).read_text()
    assert f"- Started fresh: an unfinished run of this paper, `{old['run_dir']}`, was left as it was." in text
    plain = rundir.write_readme(Path(old["workspace"])).read_text()
    assert "Started fresh" not in plain


def _cli(home, *args):
    env = dict(os.environ, HOME=str(home))
    return subprocess.run([sys.executable, "-m", "plumb", *args], capture_output=True, text=True, cwd=ROOT, env=env)


def test_run_dir_cli(home):
    proj = home / "proj"
    pdf = _pdf(proj)
    made = json.loads(_cli(home, "run-dir", "new", str(pdf), "--cwd", str(proj), "--date", "2026-09-26").stdout)
    assert made["workspace"].endswith("plumb_output/2026-09-26/.workspace")
    found = json.loads(_cli(home, "run-dir", "find", str(pdf), "--cwd", str(proj)).stdout)
    assert found["workspace"] == made["workspace"]
    no_cwd = json.loads(_cli(home, "run-dir", "new", str(pdf), "--date", "2026-09-26").stdout)
    assert no_cwd["root"] == str((proj / "fakepaper").resolve())
    moved = json.loads(_cli(home, "run-dir", "move", no_cwd["run_dir"], str(home / "reviews")).stdout)
    assert moved["root"] == str((home / "reviews").resolve())


def test_run_dir_new_fresh_cli(home):
    proj = home / "proj"
    pdf = _pdf(proj)
    old = json.loads(_cli(home, "run-dir", "new", str(pdf), "--cwd", str(proj), "--date", "2026-09-26").stdout)
    r = _cli(home, "run-dir", "new", str(pdf), "--cwd", str(proj), "--date", "2026-09-26", "--fresh")
    assert r.returncode == 0, r.stderr
    fresh = json.loads(r.stdout)
    assert fresh["run_dir"].endswith("plumb_output/2026-09-26-2")
    run = json.loads((Path(fresh["workspace"]) / "run.json").read_text())
    assert run["fresh"] is True and run["unfinished_run"] == old["run_dir"]
    assert "--fresh" in _cli(home, "run-dir", "new", "--help").stdout


def test_migrate_run_cli_reads_the_recorded_answer(tmp_path):
    (tmp_path / "run.json").write_text(json.dumps({"depth": "standard"}))
    audit.log_event(tmp_path, "checkin", stop="setup", item="setup:output", recommended="",
                    answer="B. Mock referee report", note="preference")
    r = _cli(tmp_path, "migrate-run", str(tmp_path))
    assert r.returncode == 0 and json.loads(r.stdout)["outputs"] == ["report"]


def _measured_report():
    row = {"input": 100, "output": 20, "cache_write": 5, "cache_read": 1000, "seconds": 65.0,
           "cost_usd": 0.5, "cost_complete": True}
    return {"measured": True, "method": "", "price_table": {"as_of": "2000-01-01", "source": "Fake."},
            "sessions": 1, "agents": 2, "missing_transcripts": 0, "codex": None, "unpriced_models": [],
            "by_stage": [dict(stage="0", **row)], "by_model": [dict(model="claude-fakeopus-1", **row)],
            "total": dict(row)}


def test_readme_reports_usage_or_says_it_was_not_measured(home):
    from plumb import usage
    ws = _issues_list_run(home)
    text = rundir.write_readme(ws).read_text()
    assert "## Usage\n\nUsage was not recorded for this run.\n\n## The record" in text
    usage.write_report(ws)
    text = rundir.write_readme(ws).read_text()
    assert "## Usage\n\nUsage not measured in this app.\n\n## The record" in text
    assert "`.workspace/usage.json`" in text
    (ws / "usage.json").write_text(json.dumps(_measured_report()))
    text = rundir.write_readme(ws).read_text()
    assert text.index("## Files") < text.index("## Usage") < text.index("## The record")
    assert "| claude-fakeopus-1 | 100 | 20 | 5 | 1,000 | 1m 05s | $0.50 |" in text
    assert "it is not what you pay" in text and "role" not in text.lower() and "—" not in text


# plumb put: the blocked-write workaround moves a staging file into the run folder (task-4 fix
# rounds 1-2, spec 2026-09-28 section 5). The run folder, not `.workspace`, is the boundary: it
# holds the delivered outputs (README.md, issues_list.md, the annotated PDF, mock_report.txt)
# beside `.workspace`, and never the paper's PDF, which lives at the run folder's grandparent.

def _run_folder(tmp_path):
    run = tmp_path / "root" / "plumb_output" / "2026-09-28"
    (run / ".workspace").mkdir(parents=True)
    (run / ".workspace" / "run.json").write_text(
        json.dumps({"pdf_path": str(tmp_path / "root" / "fakepaper.pdf"), "started": "2026-09-28"}),
        encoding="utf-8")
    (tmp_path / "root" / "fakepaper.pdf").write_bytes(b"%PDF-1.4 fake")
    return run


def test_put_moves_the_staging_file_into_the_workspace(tmp_path):
    run = _run_folder(tmp_path)
    staging = tmp_path / "staging.md"
    staging.write_text("blocked content", encoding="utf-8")
    dest = rundir.put(run, ".workspace/run_log.md", staging)
    assert Path(dest) == run / ".workspace" / "run_log.md"
    assert (run / ".workspace" / "run_log.md").read_text(encoding="utf-8") == "blocked content"
    assert not staging.exists()


def test_put_allows_a_target_at_the_run_folder_level(tmp_path):
    # README.md, issues_list.md, the annotated PDF, and mock_report.txt all live beside
    # .workspace, not inside it (task-4-rereview-1.md).
    run = _run_folder(tmp_path)
    staging = tmp_path / "staging.md"
    staging.write_text("# Plumb review", encoding="utf-8")
    dest = rundir.put(run, "README.md", staging)
    assert Path(dest) == run / "README.md"
    assert (run / "README.md").read_text(encoding="utf-8") == "# Plumb review"


def test_put_creates_parent_folders(tmp_path):
    run = _run_folder(tmp_path)
    staging = tmp_path / "staging.md"
    staging.write_text("x", encoding="utf-8")
    dest = rundir.put(run, ".workspace/stage-7/report.md", staging)
    assert Path(dest) == run / ".workspace" / "stage-7" / "report.md"
    assert (run / ".workspace" / "stage-7" / "report.md").read_text(encoding="utf-8") == "x"


def test_put_refuses_a_target_that_traverses_outside_the_run_folder(tmp_path):
    run = _run_folder(tmp_path)
    staging = tmp_path / "staging.md"
    staging.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        rundir.put(run, "../escape.md", staging)
    assert staging.exists()
    assert not (run.parent / "escape.md").exists()


def test_put_refuses_an_absolute_target_outside_the_run_folder(tmp_path):
    run = _run_folder(tmp_path)
    staging = tmp_path / "staging.md"
    staging.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        rundir.put(run, "/etc/passwd", staging)
    assert staging.exists()


def test_put_refuses_the_papers_pdf_location(tmp_path):
    # The run folder's grandparent (<root>) is where the PDF lives; a target that resolves there
    # is refused the same as any other escape (task-4-rereview-1.md).
    run = _run_folder(tmp_path)
    staging = tmp_path / "staging.md"
    staging.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        rundir.put(run, "../../fakepaper.pdf", staging)
    assert (tmp_path / "root" / "fakepaper.pdf").read_bytes() == b"%PDF-1.4 fake"
    assert staging.exists()


def test_put_refuses_a_symlinked_directory_that_escapes_the_run_folder(tmp_path):
    run = _run_folder(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (run / "escape_dir").symlink_to(outside, target_is_directory=True)
    staging = tmp_path / "staging.md"
    staging.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        rundir.put(run, "escape_dir/leaked.md", staging)
    assert not (outside / "leaked.md").exists()
    assert staging.exists()


def test_put_refuses_a_symlinked_file_that_escapes_the_run_folder(tmp_path):
    run = _run_folder(tmp_path)
    outside_file = tmp_path / "outside.md"
    outside_file.write_text("original", encoding="utf-8")
    (run / "escape_link.md").symlink_to(outside_file)
    staging = tmp_path / "staging.md"
    staging.write_text("blocked content", encoding="utf-8")
    with pytest.raises(ValueError):
        rundir.put(run, "escape_link.md", staging)
    assert outside_file.read_text(encoding="utf-8") == "original"
    assert staging.exists()


def test_put_refuses_a_missing_staging_file(tmp_path):
    run = _run_folder(tmp_path)
    with pytest.raises(ValueError):
        rundir.put(run, "README.md", tmp_path / "missing.md")
    assert not (run / "README.md").exists()


# The boundary argument itself must be a real Plumb run folder (task-4-rereview-2.md): widening
# to {RUN} in round 2 put the paper's own folder exactly one level above a mis-set {RUN}, with no
# traversal or symlink needed to reach the PDF as a direct child.

def test_put_refuses_the_papers_own_folder_as_the_run_folder(tmp_path):
    paper_folder = tmp_path / "root"
    paper_folder.mkdir()
    pdf = paper_folder / "fakepaper.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    staging = tmp_path / "staging.md"
    staging.write_text("overwrite attempt", encoding="utf-8")
    with pytest.raises(ValueError):
        rundir.put(paper_folder, "fakepaper.pdf", staging)
    assert pdf.read_bytes() == b"%PDF-1.4 fake"
    assert staging.exists()


def test_put_refuses_a_project_root_as_the_run_folder(tmp_path):
    proj = tmp_path / "proj"
    (proj / "src").mkdir(parents=True)
    (proj / "README.md").write_text("a project, not a run", encoding="utf-8")
    staging = tmp_path / "staging.md"
    staging.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        rundir.put(proj, "README.md", staging)
    assert staging.exists()


def test_put_refuses_a_plain_directory_as_the_run_folder(tmp_path):
    plain = tmp_path / "just_a_folder"
    plain.mkdir()
    staging = tmp_path / "staging.md"
    staging.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        rundir.put(plain, "notes.md", staging)
    assert staging.exists()


def test_put_refuses_a_workspace_whose_parent_is_not_plumb_output(tmp_path):
    # .workspace/run.json exists, but the folder above it is not named plumb_output: still not a
    # real run folder.
    fake_run = tmp_path / "not_plumb_output" / "2026-09-28"
    (fake_run / ".workspace").mkdir(parents=True)
    (fake_run / ".workspace" / "run.json").write_text("{}", encoding="utf-8")
    staging = tmp_path / "staging.md"
    staging.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        rundir.put(fake_run, "README.md", staging)
    assert staging.exists()


def test_put_still_works_for_a_real_run_folder(tmp_path):
    run = _run_folder(tmp_path)
    staging = tmp_path / "staging.md"
    staging.write_text("a real write", encoding="utf-8")
    dest = rundir.put(run, "mock_report.txt", staging)
    assert Path(dest) == run / "mock_report.txt"
    assert (run / "mock_report.txt").read_text(encoding="utf-8") == "a real write"


def test_put_refuses_a_pdf_target_that_is_not_the_annotated_copy(tmp_path):
    run = _run_folder(tmp_path)
    staging = tmp_path / "staging.md"
    staging.write_text("overwrite attempt", encoding="utf-8")
    with pytest.raises(ValueError):
        rundir.put(run, "paper.pdf", staging)
    assert staging.exists()
    assert not (run / "paper.pdf").exists()


def test_put_allows_the_annotated_pdf_target(tmp_path):
    run = _run_folder(tmp_path)
    staging = tmp_path / "staging.pdf"
    staging.write_bytes(b"%PDF-1.4 annotated")
    dest = rundir.put(run, "fakepaper_annotated.pdf", staging)
    assert Path(dest) == run / "fakepaper_annotated.pdf"
    assert (run / "fakepaper_annotated.pdf").read_bytes() == b"%PDF-1.4 annotated"


def test_put_cli(tmp_path):
    run = _run_folder(tmp_path)

    outside = tmp_path / "for_outside.md"
    outside.write_text("x", encoding="utf-8")
    bad = _cli(tmp_path, "put", str(run), "../escape.md", "--from", str(outside))
    assert bad.returncode == 2 and outside.exists()

    missing = _cli(tmp_path, "put", str(run), "README.md", "--from", str(tmp_path / "nope.md"))
    assert missing.returncode == 2

    staging = tmp_path / "staging.md"
    staging.write_text("hello", encoding="utf-8")
    r = _cli(tmp_path, "put", str(run), ".workspace/run_log.md", "--from", str(staging))
    assert r.returncode == 0
    assert (run / ".workspace" / "run_log.md").read_text(encoding="utf-8") == "hello"
    assert not staging.exists()

    not_a_run = tmp_path / "root"  # the paper's own folder, not a run folder
    pdf_staging = tmp_path / "pdf_staging.md"
    pdf_staging.write_text("overwrite attempt", encoding="utf-8")
    wrong_folder = _cli(tmp_path, "put", str(not_a_run), "fakepaper.pdf", "--from", str(pdf_staging))
    assert wrong_folder.returncode == 2 and pdf_staging.exists()

    bad_pdf = _cli(tmp_path, "put", str(run), "paper.pdf", "--from", str(pdf_staging))
    assert bad_pdf.returncode == 2 and pdf_staging.exists()


# Plan 1e wave C11: the PDF guard ignores case, and a directory or the run folder itself is refused.

@pytest.mark.parametrize("target", ["paper.PDF", "copy.Pdf", ".", "", ".workspace", "sub/.."])
def test_put_refuses_an_uppercase_pdf_a_directory_or_the_run_folder(tmp_path, target):
    run = _run_folder(tmp_path)
    staging = tmp_path / "staging.md"
    staging.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        rundir.put(run, target, staging)
    assert staging.exists() and (run / ".workspace" / "run.json").is_file()


def test_put_takes_an_uppercase_annotated_copy(tmp_path):
    run = _run_folder(tmp_path)
    staging = tmp_path / "staging.pdf"
    staging.write_bytes(b"%PDF-1.4 fake")
    assert rundir.put(run, "fakepaper_annotated.PDF", staging).endswith("fakepaper_annotated.PDF")


def test_contracts_tell_an_agent_what_to_do_when_a_write_is_blocked():
    text = (Path(__file__).resolve().parents[1] / "skills/review/shared/contracts.md").read_text(encoding="utf-8")
    assert "blocked" in text and "name both paths in your reply" in text and "plumb put" in text


def test_readme_marks_a_withheld_output(home):
    ws = _issues_list_run(home)
    withheld = ws / "stage-7" / "withheld"
    withheld.mkdir(parents=True)
    (withheld / "issues_list.md").write_text("x")
    assert "- `issues_list.md`: Withheld." in rundir.write_readme(ws).read_text()
