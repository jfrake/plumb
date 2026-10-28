"""The usage hooks record pointers for a run only after that run's own `usage mark` call has
bound the session to it (Task 4 fix round 1: binding moved from first-hook-wins to mark time).
Fix round 2: concurrent SubagentStops must never lose a pointer, a corrupt file (non-UTF-8 bytes
or a schema-invalid entry, not just bad JSON) is quarantined the same way, and `_mark_target`
finds the workspace positional regardless of option order. HOME is always the test's folder."""
from __future__ import annotations
import datetime
import json
import os
import shlex
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

from plumb import usage

ROOT = Path(__file__).resolve().parents[1]
STOP_HOOK = ROOT / "hooks" / "record-usage.sh"
BIND_HOOK = ROOT / "hooks" / "bind-usage.sh"


def _ago(minutes: float) -> str:
    """An ISO timestamp `minutes` before the real current time, with milliseconds. The hooks
    prune fixture entries against the real clock (UNBOUND_TTL 24h, BOUND_TTL 7 days in
    plumb/usage.py), so a `mark_active(..., now=...)` fixture must stay relative to when the
    suite actually runs, not a date fixed at authoring time."""
    return (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=minutes)).isoformat(
        timespec="milliseconds")


def _no_python_path(tmp_path):
    """A PATH with `cat` and `mkdir` (bind-usage.sh's fast path needs them) but no `python3`, so a
    test can prove Python was never started: if it had been, "python3: command not found" would
    land in hook_errors.log via the wrapper's own stderr redirect."""
    fake = tmp_path / "fakebin"
    fake.mkdir(exist_ok=True)
    for tool, real in (("cat", "/bin/cat"), ("mkdir", "/bin/mkdir")):
        link = fake / tool
        if not link.exists():
            link.symlink_to(real)
    return str(fake)


def _run(script, home, payload, path=None):
    env = {"HOME": str(home), "PATH": path if path is not None else os.environ["PATH"]}
    stdin = json.dumps(payload) if isinstance(payload, dict) else payload
    return subprocess.run(["/bin/bash", str(script)], input=stdin, capture_output=True, text=True, env=env)


def _hook(home, payload, path=None):
    return _run(STOP_HOOK, home, payload, path)


def _bind(home, ws, cwd, session_id, path=None):
    """Simulate the PostToolUse Bash payload for the `plumb usage mark <ws> --cwd <cwd>` call a
    session makes; this is how a session actually gets bound to a run."""
    command = "plumb usage mark {} --cwd {}".format(shlex.quote(str(ws)), shlex.quote(str(cwd)))
    payload = {"session_id": session_id, "cwd": str(cwd), "hook_event_name": "PostToolUse",
               "tool_name": "Bash", "tool_input": {"command": command}}
    return _run(BIND_HOOK, home, payload, path)


def _setup(tmp_path):
    home, proj = tmp_path / "home", tmp_path / "proj"
    ws = proj / "plumb_output" / "2026-09-27" / ".workspace"
    ws.mkdir(parents=True)
    home.mkdir()
    return home, proj, ws


def _fake_transcripts(tmp_path, session="sess-1", agent="a1"):
    parent = tmp_path / "transcripts" / f"{session}.jsonl"
    sub = parent.parent / session / "subagents"
    sub.mkdir(parents=True)
    parent.write_text("")
    (sub / f"agent-{agent}.jsonl").write_text("")
    (sub / f"agent-{agent}.meta.json").write_text(json.dumps({"agentType": "general-purpose",
                                                              "description": "Fake dispatch", "model": "fake"}))
    return parent


def _pointers(ws):
    p = ws / "usage" / "hook_events.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []


def _sessions(home, ws):
    for e in json.loads(usage.active_path(home).read_text()):
        if e["workspace"] == str(Path(ws).resolve()):
            return e["sessions"]
    raise AssertionError(f"no entry for {ws}")


# --- mark_active: entry shape, gone folders, a corrupt file ---

def test_mark_adds_one_unbound_entry_per_run(tmp_path):
    home, proj, ws = _setup(tmp_path)
    usage.mark_active(ws, proj, home, now="2026-09-27T10:00:00+00:00")
    e = usage.mark_active(ws, proj, home, now="2026-09-27T11:00:00+00:00")
    entries = json.loads(usage.active_path(home).read_text())
    assert entries == [e] and e["sessions"] == [] and e["marked"] == "2026-09-27T11:00:00+00:00"
    assert (ws / "usage").is_dir()


def test_mark_drops_runs_whose_folder_is_gone_and_replaces_a_bad_file(tmp_path):
    home, proj, ws = _setup(tmp_path)
    usage.active_path(home).parent.mkdir(parents=True)
    usage.active_path(home).write_text("not json")
    usage.mark_active(ws, proj, home)
    gone = tmp_path / "gone" / ".workspace"
    gone.mkdir(parents=True)
    usage.mark_active(gone, proj, home)
    shutil.rmtree(gone)
    usage.mark_active(ws, proj, home)
    assert [e["workspace"] for e in json.loads(usage.active_path(home).read_text())] == [str(ws.resolve())]


def test_resuming_keeps_earlier_bound_sessions_and_logs_when_each_one_bound(tmp_path):
    # Final ruling I1: the run keeps its list of bound sessions, and every bind is logged in the
    # run's own folder, so the report can give each session a window from its bind to the next
    # bind by another session.
    home, proj, ws = _setup(tmp_path)
    usage.mark_active(ws, proj, home, now=_ago(120))
    assert _bind(home, ws, proj, "sess-1").returncode == 0
    usage.mark_active(ws, proj, home, now=_ago(0))  # resume
    assert _bind(home, ws, proj, "sess-2").returncode == 0
    assert set(_sessions(home, ws)) == {"sess-1", "sess-2"}
    binds = [json.loads(l) for l in (ws / "usage" / "binds.jsonl").read_text().splitlines()]
    assert [b["session_id"] for b in binds] == ["sess-1", "sess-2"]
    assert usage._ts(binds[0]["ts"]) <= usage._ts(binds[1]["ts"])


def test_clear_removes_the_file_when_no_run_is_left(tmp_path):
    home, proj, ws = _setup(tmp_path)
    usage.mark_active(ws, proj, home)
    assert usage.clear_active(ws, home) is True
    assert not usage.active_path(home).exists() and usage.clear_active(ws, home) is False


def test_corrupt_active_runs_file_is_quarantined_once_and_treated_as_empty(tmp_path):
    home, proj, ws = _setup(tmp_path)
    usage.active_path(home).parent.mkdir(parents=True)
    usage.active_path(home).write_text("not json")
    r = _hook(home, {"session_id": "sess-1", "cwd": str(proj), "hook_event_name": "Stop"})
    assert r.returncode == 0 and r.stdout == ""
    assert not usage.active_path(home).exists()
    corrupt = usage.active_path(home).parent / "active_runs.corrupt"
    assert corrupt.read_text() == "not json"
    log = usage.error_log(home).read_text()
    assert "record_usage" in log and log.count("\n") == 1


# --- the fast paths: no active run, and no python for an ordinary Bash command ---

def test_stop_hook_does_nothing_without_an_active_run(tmp_path):
    home, proj, ws = _setup(tmp_path)
    r = _hook(home, {"session_id": "s", "cwd": str(proj), "hook_event_name": "Stop"})
    assert r.returncode == 0 and r.stdout == "" and r.stderr == ""
    assert _pointers(ws) == [] and not (home / ".config").exists()


def test_posttooluse_wrapper_starts_no_python_for_an_ordinary_bash_command(tmp_path):
    home, proj, ws = _setup(tmp_path)
    payload = {"session_id": "s", "cwd": str(proj), "hook_event_name": "PostToolUse",
               "tool_name": "Bash", "tool_input": {"command": "ls -la"}}
    r = _run(BIND_HOOK, home, payload, path=_no_python_path(tmp_path))  # python3 not on PATH
    assert r.returncode == 0 and r.stdout == "" and r.stderr == ""
    assert not usage.error_log(home).exists()  # would exist if python had been started and failed


# --- binding at mark time, and the two false-binding cases from the review ---

def test_bind_records_a_subagent_pointer_for_the_bound_session(tmp_path):
    home, proj, ws = _setup(tmp_path)
    marked = _ago(5)
    usage.mark_active(ws, proj, home, now=marked)
    assert _bind(home, ws, proj, "sess-1").returncode == 0
    parent = _fake_transcripts(tmp_path)
    r = _hook(home, {"session_id": "sess-1", "transcript_path": str(parent), "cwd": str(proj / "sub"),
                     "hook_event_name": "SubagentStop", "agent_id": "a1", "agent_type": "general-purpose"})
    assert r.returncode == 0 and r.stdout == ""
    [p] = _pointers(ws)
    assert p["event"] == "SubagentStop" and p["session_id"] == "sess-1" and p["agent_id"] == "a1"
    assert p["agent_transcript"] == str(parent.parent / "sess-1" / "subagents" / "agent-a1.jsonl")
    assert p["description"] == "Fake dispatch" and p["run_marked"] == marked
    assert "sess-1" in _sessions(home, ws)


def test_stop_hook_records_a_main_session_pointer_once_bound(tmp_path):
    home, proj, ws = _setup(tmp_path)
    usage.mark_active(ws, proj, home)
    assert _bind(home, ws, proj, "sess-1").returncode == 0
    _hook(home, {"session_id": "sess-1", "transcript_path": "/x/sess-1.jsonl", "cwd": str(proj),
                 "hook_event_name": "Stop"})
    [p] = _pointers(ws)
    assert p["event"] == "Stop" and p["transcript_path"] == "/x/sess-1.jsonl" and "agent_id" not in p


def test_unbound_session_in_the_same_folder_is_never_recorded(tmp_path):
    # Reviewer scenario (a): a second session in the marked folder finishes a reply before the
    # Plumb session ever calls `usage mark` (so it never binds), and must not be recorded.
    home, proj, ws = _setup(tmp_path)
    usage.mark_active(ws, proj, home)
    r = _hook(home, {"session_id": "sess-B", "transcript_path": "/x/b.jsonl", "cwd": str(proj),
                     "hook_event_name": "Stop"})
    assert r.returncode == 0
    assert _pointers(ws) == [] and _sessions(home, ws) == []


def test_bound_session_not_captured_by_a_later_run_in_the_same_folder(tmp_path):
    # Reviewer scenario (b): session A, bound to run1, must not be recorded into run2, started
    # from a different session C in the same folder.
    home, proj, run1 = _setup(tmp_path)
    usage.mark_active(run1, proj, home, now=_ago(60))
    assert _bind(home, run1, proj, "sess-A").returncode == 0
    run2 = proj / "plumb_output" / "2026-09-27-2" / ".workspace"
    run2.mkdir(parents=True)
    usage.mark_active(run2, proj, home, now=_ago(0))
    assert _bind(home, run2, proj, "sess-C").returncode == 0
    _hook(home, {"session_id": "sess-A", "transcript_path": "/x/a.jsonl", "cwd": str(proj), "hook_event_name": "Stop"})
    _hook(home, {"session_id": "sess-C", "transcript_path": "/x/c.jsonl", "cwd": str(proj), "hook_event_name": "Stop"})
    assert [p["session_id"] for p in _pointers(run1)] == ["sess-A"]
    assert [p["session_id"] for p in _pointers(run2)] == ["sess-C"]


def test_bind_hook_handles_a_workspace_path_with_spaces(tmp_path):
    home, proj, _ = _setup(tmp_path)
    ws = proj / "my paper" / "plumb_output" / "2026-09-27" / ".workspace"
    ws.mkdir(parents=True)
    usage.mark_active(ws, proj, home)
    assert _bind(home, ws, proj, "sess-1").returncode == 0
    assert _sessions(home, ws) == ["sess-1"]


def test_bound_session_is_followed_after_it_changes_folder(tmp_path):
    home, proj, ws = _setup(tmp_path)
    usage.mark_active(ws, proj, home)
    assert _bind(home, ws, proj, "sess-1").returncode == 0
    _hook(home, {"session_id": "sess-1", "transcript_path": "/x/a.jsonl", "cwd": str(proj), "hook_event_name": "Stop"})
    _hook(home, {"session_id": "sess-1", "transcript_path": "/x/a.jsonl", "cwd": str(tmp_path), "hook_event_name": "Stop"})
    assert len(_pointers(ws)) == 2


def test_start_over_in_the_same_session_records_for_the_new_run(tmp_path):
    home, proj, old = _setup(tmp_path)
    usage.mark_active(old, proj, home, now=_ago(60))
    assert _bind(home, old, proj, "sess-1").returncode == 0
    _hook(home, {"session_id": "sess-1", "transcript_path": "/x/a.jsonl", "cwd": str(proj), "hook_event_name": "Stop"})
    new = proj / "plumb_output" / "2026-09-27-2" / ".workspace"
    new.mkdir(parents=True)
    usage.mark_active(new, proj, home, now=_ago(0))
    assert _bind(home, new, proj, "sess-1").returncode == 0
    _hook(home, {"session_id": "sess-1", "transcript_path": "/x/a.jsonl", "cwd": str(proj), "hook_event_name": "Stop"})
    assert len(_pointers(old)) == 1 and len(_pointers(new)) == 1


def test_hook_skips_a_run_whose_folder_was_deleted_after_binding(tmp_path):
    home, proj, ws = _setup(tmp_path)
    usage.mark_active(ws, proj, home)
    assert _bind(home, ws, proj, "sess-1").returncode == 0
    shutil.rmtree(ws)
    r = _hook(home, {"session_id": "sess-1", "transcript_path": "/x/a.jsonl", "cwd": str(proj), "hook_event_name": "Stop"})
    assert r.returncode == 0 and not ws.exists()


# --- expiry ---

def test_unbound_entry_older_than_24_hours_is_pruned(tmp_path):
    # Reviewer scenario (c).
    home, proj, ws = _setup(tmp_path)
    usage.mark_active(ws, proj, home, now="2026-09-01T00:00:00+00:00")
    r = usage.record_hook({"session_id": "sess-1", "cwd": str(proj), "hook_event_name": "Stop"}, home,
                          now="2026-09-01T23:00:00+00:00")  # 23 hours after marking: not pruned yet
    assert r is None and usage.active_path(home).exists()
    r = usage.record_hook({"session_id": "sess-1", "cwd": str(proj), "hook_event_name": "Stop"}, home,
                          now="2026-09-02T01:00:00+00:00")  # 25 hours after marking, never bound
    assert r is None
    assert not usage.active_path(home).exists()


def test_bound_entry_with_no_activity_for_7_days_is_pruned(tmp_path):
    home, proj, ws = _setup(tmp_path)
    usage.mark_active(ws, proj, home, now="2026-09-01T00:00:00+00:00")
    assert _bind(home, ws, proj, "sess-1").returncode == 0
    r = usage.record_hook({"session_id": "sess-1", "cwd": str(proj), "hook_event_name": "Stop"}, home,
                          now="2026-09-09T00:00:01+00:00")  # 8 days after the bind, no activity since
    assert r is None
    assert not usage.active_path(home).exists()


def test_marking_again_revives_a_run_past_its_expiry_window(tmp_path):
    home, proj, ws = _setup(tmp_path)
    usage.mark_active(ws, proj, home, now="2026-09-01T00:00:00+00:00")
    usage.mark_active(ws, proj, home, now="2026-09-03T00:00:00+00:00")  # resume, 48h later: revives it
    assert usage.active_path(home).exists()
    entries = json.loads(usage.active_path(home).read_text())
    assert entries[0]["marked"] == "2026-09-03T00:00:00+00:00"


# --- fix round 2: concurrent SubagentStops must not lose pointers ---

def test_parallel_subagent_stops_lose_no_pointers(tmp_path):
    # Reviewer measurement: 8 parallel SubagentStop hook processes, one bound session, before the
    # fix lost about 2% of pointers to a FileNotFoundError on a shared active_runs.tmp name.
    home, proj, ws = _setup(tmp_path)
    usage.mark_active(ws, proj, home)
    assert _bind(home, ws, proj, "sess-1").returncode == 0

    n_workers, n_events = 8, 40
    failures = []

    def worker(worker_id):
        for i in range(n_events):
            r = _hook(home, {"session_id": "sess-1", "transcript_path": "/x/a.jsonl", "cwd": str(proj),
                             "hook_event_name": "SubagentStop", "agent_id": f"w{worker_id}-{i}",
                             "agent_type": "general-purpose"})
            if r.returncode != 0 or r.stdout != "":
                failures.append(r)

    threads = [threading.Thread(target=worker, args=(w,)) for w in range(n_workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert failures == []
    pointers = _pointers(ws)
    assert len(pointers) == n_workers * n_events
    assert len({p["agent_id"] for p in pointers}) == n_workers * n_events
    # record-usage.sh's `2>>hook_errors.log` creates the file on any successful run too (the shell
    # opens the redirect target regardless), so check its content is empty, not that it's absent.
    log = usage.error_log(home)
    assert not log.exists() or log.read_text() == ""


# --- fix round 2: non-UTF-8 bytes and schema-invalid entries are quarantined like bad JSON ---

def _corrupt(home):
    usage.active_path(home).parent.mkdir(parents=True, exist_ok=True)
    return usage.active_path(home)


def _assert_quarantined(home, proj, ws, original_bytes):
    r = _hook(home, {"session_id": "sess-1", "cwd": str(proj), "hook_event_name": "Stop"})
    assert r.returncode == 0 and r.stdout == ""
    assert not usage.active_path(home).exists()
    corrupt = usage.active_path(home).parent / "active_runs.corrupt"
    assert corrupt.read_bytes() == original_bytes
    log = usage.error_log(home).read_text()
    assert "record_usage" in log and log.count("\n") == 1
    # `plumb usage mark` must never crash on this either, and must work normally afterward.
    mark = _cli(home, "usage", "mark", str(ws), "--cwd", str(proj))
    assert mark.returncode == 0


def test_non_utf8_bytes_are_quarantined(tmp_path):
    home, proj, ws = _setup(tmp_path)
    raw = b"\xff\xfe\x00garbage"
    _corrupt(home).write_bytes(raw)
    _assert_quarantined(home, proj, ws, raw)


def test_schema_invalid_int_workspace_is_quarantined(tmp_path):
    home, proj, ws = _setup(tmp_path)
    raw = json.dumps([{"workspace": 5, "cwd": None, "marked": "2026-09-27T10:00:00+00:00",
                       "sessions": [], "last_activity": "2026-09-27T10:00:00+00:00"}]).encode()
    _corrupt(home).write_bytes(raw)
    _assert_quarantined(home, proj, ws, raw)


def test_schema_invalid_null_sessions_is_quarantined(tmp_path):
    home, proj, ws = _setup(tmp_path)
    raw = json.dumps([{"workspace": str(ws), "cwd": None, "marked": "2026-09-27T10:00:00+00:00",
                       "sessions": None, "last_activity": "2026-09-27T10:00:00+00:00"}]).encode()
    _corrupt(home).write_bytes(raw)
    _assert_quarantined(home, proj, ws, raw)


def test_schema_invalid_naive_timestamp_is_quarantined(tmp_path):
    home, proj, ws = _setup(tmp_path)
    raw = json.dumps([{"workspace": str(ws), "cwd": None, "marked": "2026-09-27T10:00:00",
                       "sessions": [], "last_activity": "2026-09-27T10:00:00"}]).encode()
    _corrupt(home).write_bytes(raw)
    _assert_quarantined(home, proj, ws, raw)


def test_schema_invalid_old_session_id_format_is_quarantined(tmp_path):
    # The f91ed38 shape, before "sessions" existed.
    home, proj, ws = _setup(tmp_path)
    raw = json.dumps([{"workspace": str(ws), "cwd": str(proj), "marked": "2026-09-27T10:00:00+00:00",
                       "session_id": None}]).encode()
    _corrupt(home).write_bytes(raw)
    _assert_quarantined(home, proj, ws, raw)


# --- fix round 2: _mark_target finds the workspace regardless of option order ---

def test_bind_hook_finds_the_workspace_when_cwd_option_comes_first(tmp_path):
    home, proj, ws = _setup(tmp_path)
    usage.mark_active(ws, proj, home)
    command = "plumb usage mark --cwd {} {}".format(shlex.quote(str(proj)), shlex.quote(str(ws)))
    payload = {"session_id": "sess-1", "cwd": str(proj), "hook_event_name": "PostToolUse",
               "tool_name": "Bash", "tool_input": {"command": command}}
    r = _run(BIND_HOOK, home, payload)
    assert r.returncode == 0
    assert _sessions(home, ws) == ["sess-1"]


# --- hook safety: exits 0, prints nothing, errors go to the log file ---

def test_hook_logs_a_traceback_for_a_non_dict_payload_and_still_exits_0(tmp_path):
    home, proj, ws = _setup(tmp_path)
    usage.mark_active(ws, proj, home)
    r = _hook(home, "not a payload")
    assert r.returncode == 0 and r.stdout == ""
    assert "record_usage" in usage.error_log(home).read_text()


def test_stop_hook_exits_0_when_python_is_missing(tmp_path):
    home, proj, ws = _setup(tmp_path)
    usage.mark_active(ws, proj, home)
    r = _hook(home, {}, path=str(tmp_path / "nothing"))
    assert r.returncode == 0 and r.stdout == ""
    assert usage.error_log(home).exists()


def test_bind_hook_exits_0_when_python_is_missing(tmp_path):
    home, proj, ws = _setup(tmp_path)
    usage.mark_active(ws, proj, home)
    r = _bind(home, ws, proj, "sess-1", path=_no_python_path(tmp_path))
    assert r.returncode == 0 and r.stdout == ""
    assert usage.error_log(home).exists()


def _cli(home, *args):
    env = dict(os.environ, PYTHONPATH=str(ROOT), HOME=str(home), PLUMB_CONFIG=str(home / "none.json"))
    return subprocess.run([sys.executable, "-m", "plumb", *args], capture_output=True, text=True, env=env, cwd=ROOT)


def test_cli_marks_and_the_final_output_event_clears(tmp_path):
    home, proj, ws = _setup(tmp_path)
    r = _cli(home, "usage", "mark", str(ws), "--cwd", str(proj))
    assert r.returncode == 0 and json.loads(r.stdout)["cwd"] == str(proj.resolve())
    assert _cli(home, "log", str(ws), "output", '{"final":true,"files":[]}').returncode == 0
    assert not usage.active_path(home).exists()



# --- final ruling I1: the reviewer's "oldsession" scenario, through the real hook scripts ---

def _stamp():
    import datetime
    time.sleep(0.02)
    t = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    time.sleep(0.02)
    return t


def _assistant(mid, inp, sidechain=False):
    return json.dumps({"type": "assistant", "timestamp": _stamp(), "isSidechain": sidechain,
                       "message": {"id": mid, "model": "claude-fakeopus-1", "usage": {
                           "input_tokens": inp, "output_tokens": 1, "cache_creation_input_tokens": 0,
                           "cache_read_input_tokens": 0}}}) + "\n"


def _append(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        fh.write(text)


def test_old_session_working_after_a_resume_elsewhere_is_not_counted(tmp_path):
    # Session 1 runs the start of the run, session 2 resumes it, and session 1 then keeps working
    # on something else, with a Stop after session 2's last hook. Session 1 counts only until
    # session 2 marked; session 2 counts from its mark to the report, including main-session
    # messages after its last hook.
    home, proj, ws = _setup(tmp_path)
    t1, t2 = tmp_path / "tr" / "s1.jsonl", tmp_path / "tr" / "s2.jsonl"
    stop = lambda sid, t: _hook(home, {"session_id": sid, "transcript_path": str(t), "cwd": str(proj),
                                       "hook_event_name": "Stop"})
    _append(t1, _assistant("s1-pre", 900000))
    usage.mark_active(ws, proj, home)
    assert _bind(home, ws, proj, "sess-1").returncode == 0
    _append(t1, _assistant("s1m1", 100))
    stop("sess-1", t1)
    _append(t2, _assistant("s2-pre", 700000))
    usage.mark_active(ws, proj, home)  # resume in session 2
    assert _bind(home, ws, proj, "sess-2").returncode == 0
    _append(t2, _assistant("s2m1", 30))
    sub = t2.parent / "sess-2" / "subagents" / "agent-b1.jsonl"
    _append(sub, _assistant("b1m1", 40, sidechain=True))
    _hook(home, {"session_id": "sess-2", "transcript_path": str(t2), "cwd": str(proj),
                 "hook_event_name": "SubagentStop", "agent_id": "b1", "agent_type": "general-purpose"})
    _append(t1, _assistant("s1-unrelated", 500000))  # session 1, after the resume
    stop("sess-1", t1)  # later than session 2's last hook
    _append(t2, _assistant("s2m7", 5))  # session 2, after its last hook
    rep = usage.report(ws, prices={"models": []})
    assert rep["total"]["input"] == 100 + 30 + 40 + 5
    assert rep["sessions"] == 2 and rep["agents"] == 1


# --- final ruling (minor): _mark_target handles shell separators, ~, and $VAR ---

def test_mark_target_strips_trailing_shell_separators():
    for sep in (";", "; ", " && ", " || ", " | ", "&&", "|"):
        cmd = "plumb usage mark /w/.workspace" + sep + "echo /other"
        assert usage._mark_target(cmd) == "/w/.workspace", cmd
    assert usage._mark_target("plumb usage mark '/my w/.workspace';next") == "/my w/.workspace"


def test_mark_target_ignores_tokens_after_a_separator():
    assert usage._mark_target("plumb usage mark --cwd /p; echo /other") is None
    assert usage._mark_target("plumb usage mark --cwd /p && ls /x") is None
    assert usage._mark_target("cd /p && plumb usage mark /w --cwd /p") == "/w"


def test_mark_target_expands_home_and_variables(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("PLUMB_TEST_WS", str(tmp_path / "ws"))
    assert usage._mark_target("plumb usage mark ~/runs/.workspace") == str(tmp_path / "home" / "runs" / ".workspace")
    assert usage._mark_target("plumb usage mark $PLUMB_TEST_WS --cwd /p") == str(tmp_path / "ws")
    assert usage._mark_target('plumb usage mark "${PLUMB_TEST_WS}/x"') == str(tmp_path / "ws" / "x")


def test_bind_hook_binds_a_mark_followed_by_another_command(tmp_path):
    home, proj, ws = _setup(tmp_path)
    usage.mark_active(ws, proj, home)
    command = "plumb usage mark {} --cwd {}; echo done".format(shlex.quote(str(ws)), shlex.quote(str(proj)))
    payload = {"session_id": "sess-1", "cwd": str(proj), "hook_event_name": "PostToolUse",
               "tool_name": "Bash", "tool_input": {"command": command}}
    assert _run(BIND_HOOK, home, payload).returncode == 0
    assert _sessions(home, ws) == ["sess-1"]


# --- headless fix: a workspace held in a shell variable set earlier in the same command ---

def _headless_mark_payload(home, proj, ws, session_id="sess-1"):
    """The PostToolUse payload the did-1-quick headless run produced (2026-10-06): the workspace is
    a shell variable assigned earlier in the same command line, so the hook's own environment
    cannot expand it; the expanded path is only in what `plumb usage mark` printed."""
    command = ('cd "{p}" && export PYTHONPATH="/plugins/plumb" && P="$PYTHONPATH" && '
               'W="$PWD/plumb_output/2026-09-27/.workspace" && python3 -m plumb usage mark "$W" --cwd "$PWD" '
               '&& python3 -m plumb deps').format(p=proj)
    entry = usage.mark_active(ws, proj, home)
    stdout = json.dumps(entry) + "\n" + json.dumps({"missing_required": [], "codex": True})
    return {"session_id": session_id, "transcript_path": "/t/sess-1.jsonl", "cwd": str(proj),
            "permission_mode": "acceptEdits", "hook_event_name": "PostToolUse", "tool_name": "Bash",
            "tool_input": {"command": command, "description": "Mark the run"},
            "tool_response": {"stdout": stdout, "stderr": "", "interrupted": False, "isImage": False,
                              "noOutputExpected": False},
            "tool_use_id": "toolu_x", "duration_ms": 900}


def test_bind_hook_binds_a_workspace_set_in_a_shell_variable_in_the_same_command(tmp_path):
    home, proj, ws = _setup(tmp_path)
    payload = _headless_mark_payload(home, proj, ws)
    assert _run(BIND_HOOK, home, payload).returncode == 0
    assert _sessions(home, ws) == ["sess-1"]
    errors = home / ".config" / "plumb" / "hook_errors.log"
    assert not errors.exists() or not errors.read_text().strip()


def test_bind_hook_ignores_a_printed_entry_when_the_command_is_not_a_mark_call(tmp_path):
    home, proj, ws = _setup(tmp_path)
    payload = _headless_mark_payload(home, proj, ws)
    payload["tool_input"]["command"] = "cat ~/.config/plumb/active_runs.json  # usage marker"
    assert usage.bind_hook(payload, home) is None
    assert _sessions(home, ws) == []
