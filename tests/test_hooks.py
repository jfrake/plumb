from __future__ import annotations
import json, os, subprocess
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1] / "hooks"

def run(script, payload, env=None):
    # Ruling 4: invoke /bin/bash directly so an empty/restricted PATH in `env`
    # exercises the script under test, not bash's own process lookup.
    return subprocess.run(["/bin/bash", str(HOOKS / script)], input=json.dumps(payload), capture_output=True, text=True, env=env)

def test_hooks_json_wires_six_hooks():
    h = json.loads((HOOKS / "hooks.json").read_text())["hooks"]
    assert set(h) == {"PreCompact", "PreToolUse", "Notification", "SubagentStop", "Stop", "PostToolUse"}
    for event in ("SubagentStop", "Stop"):
        assert h[event][0]["hooks"][0]["command"] == 'bash "${CLAUDE_PLUGIN_ROOT}/hooks/record-usage.sh"'
    assert h["PostToolUse"][0]["matcher"] == "Bash"
    assert h["PostToolUse"][0]["hooks"][0]["command"] == 'bash "${CLAUDE_PLUGIN_ROOT}/hooks/bind-usage.sh"'

def test_protect_blocks_submitted(tmp_path):
    r = run("protect-files.sh", {"tool_name": "Write", "tool_input": {"file_path": str(tmp_path / "submitted" / "paper.tex")}})
    assert r.returncode == 2 and "deny" in r.stdout

def test_protect_allows_run_folder(tmp_path):
    f = tmp_path / "plumb_output" / "2026-09-26" / ".workspace" / "x.md"
    r = run("protect-files.sh", {"tool_name": "Write", "tool_input": {"file_path": str(f)}})
    assert r.returncode == 0


def test_protect_allows_run_folder_beside_a_submitted_paper(tmp_path):
    # The PDF is proj/submitted/fakepaper.pdf; its run folder is proj/submitted/fakepaper/plumb_output/.
    for name in ("issues_list.md", ".workspace/run.json"):
        f = tmp_path / "proj" / "submitted" / "fakepaper" / "plumb_output" / "2026-09-26" / name
        r = run("protect-files.sh", {"tool_name": "Write", "tool_input": {"file_path": str(f)}})
        assert r.returncode == 0 and "deny" not in r.stdout


def test_protect_still_blocks_the_submitted_paper(tmp_path):
    f = tmp_path / "proj" / "submitted" / "fakepaper.pdf"
    r = run("protect-files.sh", {"tool_name": "Write", "tool_input": {"file_path": str(f)}})
    assert r.returncode == 2 and "deny" in r.stdout


def test_protect_no_longer_exempts_the_old_workspace(tmp_path):
    f = tmp_path / "proj" / "submitted" / "review_workspace" / "x.md"
    r = run("protect-files.sh", {"tool_name": "Write", "tool_input": {"file_path": str(f)}})
    assert r.returncode == 2


def test_protect_denies_a_plumb_output_traversal_back_into_submitted(tmp_path):
    # proj/submitted/x/plumb_output/../paper.pdf lexically normalizes to
    # proj/submitted/paper.pdf: the raw glob exempts it, the normalized path must not.
    f = tmp_path / "proj" / "submitted" / "x" / "plumb_output" / ".." / "paper.pdf"
    r = run("protect-files.sh", {"tool_name": "Write", "tool_input": {"file_path": str(f)}})
    assert r.returncode == 2 and "deny" in r.stdout


def test_protect_allows_run_folder_with_spaces_in_the_path(tmp_path):
    f = tmp_path / "my paper" / "submitted" / "fakepaper" / "plumb_output" / "2026-09-26" / ".workspace" / "x.md"
    r = run("protect-files.sh", {"tool_name": "Write", "tool_input": {"file_path": str(f)}})
    assert r.returncode == 0 and "deny" not in r.stdout


def test_protect_denies_a_plumb_output_traversal_with_spaces_in_the_path(tmp_path):
    f = tmp_path / "my paper" / "submitted" / "x" / "plumb_output" / ".." / "paper.pdf"
    r = run("protect-files.sh", {"tool_name": "Write", "tool_input": {"file_path": str(f)}})
    assert r.returncode == 2 and "deny" in r.stdout


def _brief(folder, text, mtime):
    ws = folder / "plumb_output" / "2026-09-26" / ".workspace"
    ws.mkdir(parents=True)
    (ws / "brief.md").write_text(text)
    os.utime(ws / "brief.md", (mtime, mtime))


def test_precompact_prints_brief_in_the_project_run_folder(tmp_path):
    _brief(tmp_path, "Stage 3 done.", 1000000)
    r = run("pre-compact.sh", {"trigger": "auto"}, env={"CLAUDE_PROJECT_DIR": str(tmp_path), "PATH": "/usr/bin:/bin"})
    assert "Stage 3 done." in r.stdout


def test_precompact_takes_the_newest_brief_up_to_two_levels_down(tmp_path):
    _brief(tmp_path / "paper_a", "Older fake brief.", 1000000)
    _brief(tmp_path / "papers" / "fakepaper", "Newer fake brief.", 2000000)
    r = run("pre-compact.sh", {"trigger": "auto"}, env={"CLAUDE_PROJECT_DIR": str(tmp_path), "PATH": "/usr/bin:/bin"})
    assert "Newer fake brief." in r.stdout and "Older fake brief." not in r.stdout


def test_precompact_reads_the_run_index_first(tmp_path):
    # A run moved "Somewhere else", outside the project folder, is found through the index.
    moved = tmp_path / "elsewhere" / "plumb_output" / "2026-09-26"
    (moved / ".workspace").mkdir(parents=True)
    (moved / ".workspace" / "brief.md").write_text("Indexed fake brief.")
    done = tmp_path / "done" / "plumb_output" / "2026-09-25"
    (done / ".workspace").mkdir(parents=True)
    (done / ".workspace" / "brief.md").write_text("Finished fake brief.")
    index = tmp_path / "home" / ".config" / "plumb"
    index.mkdir(parents=True)
    (index / "runs.json").write_text(json.dumps([
        {"pdf_path": "/x/fakepaper.pdf", "run_dir": str(moved), "started": "2026-09-26", "finished": False},
        {"pdf_path": "/x/fakepaper.pdf", "run_dir": str(done), "started": "2026-09-25", "finished": True}]))
    _brief(tmp_path / "proj", "Project fake brief.", 1000000)
    r = run("pre-compact.sh", {"trigger": "auto"}, env={"CLAUDE_PROJECT_DIR": str(tmp_path / "proj"),
                                                       "HOME": str(tmp_path / "home"), "PATH": "/usr/bin:/bin"})
    assert "Indexed fake brief." in r.stdout
    assert "Finished fake brief." not in r.stdout and "Project fake brief." not in r.stdout


def test_precompact_ignores_the_old_workspace(tmp_path):
    ws = tmp_path / "review_workspace"; ws.mkdir(); (ws / "brief.md").write_text("Old layout brief.")
    r = run("pre-compact.sh", {"trigger": "auto"}, env={"CLAUDE_PROJECT_DIR": str(tmp_path), "PATH": "/usr/bin:/bin"})
    assert r.stdout == ""


def test_precompact_silent_and_zero_when_no_brief(tmp_path):
    r = run("pre-compact.sh", {"trigger": "auto"}, env={"CLAUDE_PROJECT_DIR": str(tmp_path), "PATH": "/usr/bin:/bin"})
    assert r.returncode == 0
    assert r.stdout == ""

def test_notify_never_fails():
    r = run("notify.sh", {"message": "hi"}, env={"PATH": "/nonexistent"})
    assert r.returncode == 0
