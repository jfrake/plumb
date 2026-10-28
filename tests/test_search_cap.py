"""The search date cap: `search_before` in run.json, an evaluation option set by flag (setup never
asks for it), shown in the recap, the run README, and the audit package. Every path is under
tmp_path."""
from __future__ import annotations
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from plumb import rundir

ROOT = Path(__file__).resolve().parents[1]


def _pdf(folder: Path, name="fakepaper.pdf") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / name
    p.write_bytes(b"%PDF-1.4 fake")
    return p


def _cli(home, *args):
    env = dict(os.environ, PYTHONPATH=str(ROOT), HOME=str(home), PLUMB_CONFIG=str(home / "no-config.json"))
    return subprocess.run([sys.executable, "-m", "plumb", *args], capture_output=True, text=True, cwd=ROOT, env=env)


def _run(home) -> Path:
    proj = home / "proj"
    return Path(rundir.new_run(_pdf(proj), proj, home, "2026-09-26")["workspace"])


def test_set_search_before_writes_an_iso_date_and_keeps_the_other_keys(tmp_path):
    ws = _run(tmp_path)
    assert rundir.set_search_before(ws, "2026-01-15") == "2026-01-15"
    run = json.loads((ws / "run.json").read_text())
    assert run["search_before"] == "2026-01-15" and run["pdf_path"] and run["started"] == "2026-09-26"


@pytest.mark.parametrize("bad", ["15/01/2026", "2026-13-01", "January 15, 2026", "", "2026-1-5"])
def test_set_search_before_refuses_anything_but_an_iso_date(tmp_path, bad):
    ws = _run(tmp_path)
    with pytest.raises(ValueError):
        rundir.set_search_before(ws, bad)
    assert "search_before" not in json.loads((ws / "run.json").read_text())


def test_new_run_takes_the_cap_as_a_flag_for_a_scripted_run(tmp_path):
    proj = tmp_path / "proj"
    out = rundir.new_run(_pdf(proj), proj, tmp_path, "2026-09-26", search_before="2026-01-15")
    run = json.loads((Path(out["workspace"]) / "run.json").read_text())
    assert run["search_before"] == "2026-01-15"
    with pytest.raises(ValueError):
        rundir.new_run(_pdf(proj), proj, tmp_path, "2026-09-26", search_before="soon")


def test_cli_search_cap_and_run_dir_new_flag(tmp_path):
    proj = tmp_path / "proj"
    pdf = _pdf(proj)
    made = json.loads(_cli(tmp_path, "run-dir", "new", str(pdf), "--cwd", str(proj), "--date", "2026-09-26",
                           "--search-before", "2026-01-15").stdout)
    assert json.loads((Path(made["workspace"]) / "run.json").read_text())["search_before"] == "2026-01-15"
    plain = json.loads(_cli(tmp_path, "run-dir", "new", str(pdf), "--cwd", str(proj), "--date", "2026-09-26").stdout)
    ws = Path(plain["workspace"])
    assert "search_before" not in json.loads((ws / "run.json").read_text())
    r = _cli(tmp_path, "search-cap", str(ws), "2026-02-01")
    assert r.returncode == 0 and r.stdout.strip() == "2026-02-01"
    assert json.loads((ws / "run.json").read_text())["search_before"] == "2026-02-01"
    bad = _cli(tmp_path, "search-cap", str(ws), "Feb 2026")
    assert bad.returncode == 1 and "YYYY-MM-DD" in bad.stdout
    assert json.loads((ws / "run.json").read_text())["search_before"] == "2026-02-01"
    bad_flag = _cli(tmp_path, "run-dir", "new", str(pdf), "--cwd", str(proj), "--search-before", "Feb 2026")
    assert bad_flag.returncode == 1 and "YYYY-MM-DD" in bad_flag.stdout


def _setup_run(ws: Path, search_before: str = "") -> Path:
    ws.mkdir(parents=True, exist_ok=True)
    run = {"pdf_path": "/fake/fakepaper.pdf", "depth": "standard", "permission": "mine", "role": "author",
           "journal": "generic", "level": "standard", "outputs": ["issues_list"], "issues_list_mode": "full",
           "started": "2026-09-26"}
    if search_before:
        run["search_before"] = search_before
    (ws / "run.json").write_text(json.dumps(run))
    return ws


def test_recap_shows_the_cap_only_when_set(tmp_path):
    from plumb import progress
    capped = _setup_run(tmp_path / "a" / "plumb_output" / "2026-09-26" / ".workspace", "2026-01-15")
    lines = progress.recap(capped).splitlines()
    assert "| Search date cap | 2026-01-15 |" in lines
    plain = _setup_run(tmp_path / "b" / "plumb_output" / "2026-09-26" / ".workspace")
    # The recap always shows the cap row, so a missing cap is visible before the paper is read.
    assert "| Search date cap | None |" in progress.recap(plain).splitlines()


def test_readme_states_the_cap_only_when_set(tmp_path):
    capped = _setup_run(tmp_path / "a" / "plumb_output" / "2026-09-26" / ".workspace", "2026-01-15")
    text = rundir.write_readme(capped).read_text()
    assert "- Search date cap: 2026-01-15 (every agent was told to cite nothing published after this date, with the exemptions in its agent file, and the outputs were checked for later citations)" in text
    assert text.index("- Date: 2026-09-26") < text.index("- Search date cap:") < text.index("## Files")
    plain = _setup_run(tmp_path / "b" / "plumb_output" / "2026-09-26" / ".workspace")
    assert "Search date cap" not in rundir.write_readme(plain).read_text()


def test_audit_package_states_the_cap_under_models_and_settings(tmp_path):
    from plumb import audit
    capped = _setup_run(tmp_path / "a", "2026-01-15")
    audit.log_event(capped, "model", role="judgment", name="inherit")
    text = audit.render_package(capped).read_text()
    section = text[text.index("## Models and settings"):text.index("## Dependencies and warnings")]
    assert "role: judgment" in section
    assert "- Search date cap: 2026-01-15 (every agent was told to cite nothing published after this date, with the exemptions in its agent file, and the outputs were checked for later citations)" in section
    plain = _setup_run(tmp_path / "b")
    assert "Search date cap" not in audit.render_package(plain).read_text()
    (tmp_path / "no-run").mkdir()
    assert "Search date cap" not in audit.render_package(tmp_path / "no-run").read_text()


# Setup never asks for the cap. Only an evaluation run sets it, by flag on plumb run-dir new.

STAGE0 = ROOT / "skills" / "review" / "stages" / "stage-0-intake.md"


def _steps() -> dict:
    import re
    parts = re.split(r"\n(?=\d+\. )", STAGE0.read_text(encoding="utf-8"))
    return {int(p.split(".", 1)[0]): " ".join(p.split()) for p in parts[1:]}


def test_stage_0_setup_does_not_ask_for_a_cap():
    text = STAGE0.read_text(encoding="utf-8")
    for s in ("setup:search_before", "Cap web searches at a date", "No cap (Recommended)", "Yes, enter a date"):
        assert s not in text, s
    for n in (5, 8, 11):
        assert "search-cap" not in _steps()[n], n


def test_stage_0_sets_the_cap_only_from_the_evaluation_flag():
    one = _steps()[1]
    assert "evaluation option, never a setup question" in one
    assert "add `--search-before <date>` (YYYY-MM-DD) to `plumb run-dir new`" in one
    assert "A cap already in `run.json` stays as it is" in one


def test_stage_0_recap_shows_the_cap_but_does_not_offer_to_change_it():
    eight = _steps()[8]
    assert "output folder, and the search date cap when one is set" in eight
    assert "not offered for change below" in eight
    import re
    rows = re.findall(r"^\s+- ([^\n]+)", STAGE0.read_text(encoding="utf-8"), re.M)
    assert not [r for r in rows if r.startswith("Search date cap:")]


def test_stage_0_steps_keep_their_numbers():
    assert sorted(_steps()) == list(range(1, 14))


def test_readme_and_spec_name_the_search_cap():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "`python3 -m plumb run-dir new --search-before <date> <pdf>`" in readme and "submission date" in readme
    assert "No question asks about a search date cap" in readme
    spec = (ROOT / "docs/spec.md").read_text(encoding="utf-8")
    fourteen = spec[spec.index("## 14. Evaluation"):spec.index("## 15.")]
    assert "`search_before`" in fourteen and "`plumb run-dir new --search-before <date>`" in fourteen
    assert "evaluation option set by flag, not a setup question" in fourteen
    assert "`plumb search-cap <workspace> <date>`" in fourteen and "`eval/run_fixture.sh`" in fourteen
    assert "setup question or by" not in fourteen
    assert "`models.json`" in fourteen


def test_set_search_before_without_a_run_file_is_a_one_line_error(tmp_path):
    ws = tmp_path / "empty"
    ws.mkdir()
    with pytest.raises(ValueError) as err:
        rundir.set_search_before(ws, "2026-01-15")
    assert str(ws / "run.json") in str(err.value)
    r = _cli(tmp_path, "search-cap", str(ws), "2026-01-15")
    assert r.returncode == 1 and "run.json" in r.stdout and "Traceback" not in r.stderr


# The cap reaches every agent through the dispatch line, not only the agents whose files mention it.

def test_every_dispatch_carries_the_cap_line_when_run_json_has_one():
    skill = (ROOT / "skills/review/SKILL.md").read_text(encoding="utf-8")
    rule = next(l for l in skill.splitlines() if l.startswith("- When `run.json` has `search_before`"))
    assert "end every DISPATCH prompt" in rule and "pack agents and writers included" in rule
    assert '"Search date cap: <search_before>. Do not cite, quote, or rely on any work published or posted after' in rule
    assert "you already know it" in rule and "any agent can search" in rule


def test_flag_cap_reaches_the_citation_script_and_the_output_check(tmp_path):
    # With setup no longer asking, the flag is the way in: the run.json it writes still caps
    # cocitation.py and the post-cap output check.
    import importlib
    sys.path.insert(0, str(ROOT / "skills/review/scripts"))
    cc = importlib.import_module("cocitation")
    from plumb import outputs
    proj = tmp_path / "proj"
    out = rundir.new_run(_pdf(proj), proj, tmp_path, "2026-09-26", search_before="2016-06-01")
    run = json.loads((Path(out["workspace"]) / "run.json").read_text())
    assert cc.cap_for(run) == "2016-06-01"
    assert outputs.post_cap_errors("Okafor (2019) shows it.", run["search_before"])
    plain = json.loads((Path(_run(tmp_path / "b"))) .joinpath("run.json").read_text())
    assert "search_before" not in plain and cc.cap_for(plain) == "2026-09-26"


def test_old_run_with_a_recorded_cap_answer_still_resumes(tmp_path):
    # A run from before the question was removed holds a setup:search_before answer in its events.
    # The commands a resume calls must still read it without error.
    ws = _setup_run(tmp_path / "proj" / "plumb_output" / "2026-09-26" / ".workspace", "2016-06-01")
    for item, rec, ans, note in (
            ("setup:depth", "A. Standard (Recommended)", "A. Standard (Recommended)", ""),
            ("setup:level", "A. Standard (Recommended)", "A. Standard (Recommended)", ""),
            ("setup:search_before", "A. No cap (Recommended)", "B. Yes, enter a date", "2016-06-01")):
        args = ["checkin", str(ws), "setup", item, rec, ans] + (["--note", note] if note else [])
        r = _cli(tmp_path, *args)
        assert r.returncode == 0, r.stdout + r.stderr
    answered = _cli(tmp_path, "answered", str(ws))
    assert answered.returncode == 0, answered.stderr
    assert ["setup", "setup:search_before"] in json.loads(answered.stdout)
    labels = _cli(tmp_path, "answered", str(ws), "--labels")
    assert labels.returncode == 0 and json.loads(labels.stdout)["setup:search_before"] == "B. Yes, enter a date"
    recap = _cli(tmp_path, "recap", str(ws))
    assert recap.returncode == 0, recap.stderr
    assert "| Search date cap | 2016-06-01 |" in recap.stdout
    stops = _cli(tmp_path, "stops", "standard", "standard")
    assert stops.returncode == 0, stops.stderr
    assert isinstance(json.loads(stops.stdout), list)


def test_research_protocol_states_the_cap():
    proto = (ROOT / "skills/review/shared/research-protocol.md").read_text(encoding="utf-8")
    section = proto[proto.index("## Search Date Cap"):]
    assert "`search_before`" in section and "even when a search returns it or you already know it" in section
    assert "A later published version of the paper under review is the paper itself" in section


def test_stage_7_passes_run_json_to_every_validate_output_call():
    stage7 = (ROOT / "skills/review/stages/stage-7-output.md").read_text(encoding="utf-8")
    import re
    calls = re.findall(r"`plumb validate-output (?:issues_list|report|editor_memo) [^`]*`", stage7)
    assert len(calls) == 6
    assert all(c.endswith("--run {WORKSPACE}/run.json`") for c in calls)


@pytest.mark.parametrize("text", [
    "Graebner et al. (2023) set the bar for phenomenon-based work.",
    "Single cases generalize to theory (Yin, 2018; Mitchell 2023).",
    "As Graebner, Knott, Lieberman and Mitchell (2023, p. 4) argue.",
    "See Smith & Jones (2024a).",
])
def test_post_cap_citations_fail(text):
    from plumb import outputs
    errs = outputs.post_cap_errors(text, "2022-03-30")
    assert len(errs) == 1 and "capped at 2022-03-30" in errs[0]


@pytest.mark.parametrize("text", [
    "Graebner et al. (2021) set the bar.",
    "The sample ends in December 2023 (p. 7).",
    "In 2024, the firm went public.",
    "Single cases generalize to theory (Yin, 2018).",
    "Smith (2022) is in the cap's own year.",
])
def test_pre_cap_citations_and_plain_dates_pass(text):
    from plumb import outputs
    assert outputs.post_cap_errors(text, "2022-03-30") == []


def test_no_cap_means_no_check():
    from plumb import outputs
    assert outputs.post_cap_errors("Graebner et al. (2023).", "") == []


def test_validate_output_reads_the_cap_from_run_json(tmp_path):
    ws = _run(tmp_path)
    rundir.set_search_before(ws, "2022-03-30")
    report = tmp_path / "mock_report.txt"
    report.write_text("1. The framing follows Graebner et al. (2023), which postdates the submission.\n", encoding="utf-8")
    capped = _cli(tmp_path, "validate-output", "report", str(report), "--run", str(ws / "run.json"))
    assert capped.returncode == 1 and "capped at 2022-03-30" in capped.stdout
    uncapped = _cli(tmp_path, "validate-output", "report", str(report))
    assert "capped at" not in uncapped.stdout


def test_a_cap_in_the_user_request_is_applied():
    stage0 = Path(__file__).resolve().parents[1] / "skills" / "review" / "stages" / "stage-0-intake.md"
    text = " ".join(stage0.read_text(encoding="utf-8").split())
    assert "only when the user's request or the prompt of a scripted evaluation run gives a cap" in text
