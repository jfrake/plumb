"""Usage totals from small fake transcripts. Model ids and prices here are fake."""
from __future__ import annotations
import datetime
import json
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest

from plumb import usage

ROOT = Path(__file__).resolve().parents[1]
FAKE_PRICES = {"as_of": "2000-01-01", "source": "Fake prices for tests.", "models": [
    {"family": "fakeopus", "version": "1", "input": 10.0, "output": 50.0, "cache_write_5m": 12.5,
     "cache_write_1h": 20.0, "cache_read": 1.0},
    {"family": "fakesonnet", "version": "1", "input": 2.0, "output": 10.0, "cache_write_5m": 2.5,
     "cache_write_1h": 4.0, "cache_read": 0.2}]}
OPUS, SONNET = "claude-fakeopus-1", "claude-fakesonnet-1"


def T(hms):
    return f"2026-09-27T{hms}.000Z"


def _msg(mid, ts, model=OPUS, inp=0, out=0, cw=0, cw1h=0, cr=0, side=False):
    return {"type": "assistant", "timestamp": T(ts), "isSidechain": side,
            "message": {"id": mid, "model": model, "usage": {
                "input_tokens": inp, "output_tokens": out, "cache_creation_input_tokens": cw,
                "cache_read_input_tokens": cr,
                "cache_creation": {"ephemeral_5m_input_tokens": cw - cw1h, "ephemeral_1h_input_tokens": cw1h}}}}


def _write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return path


def _ws(tmp_path, stages=list(range(8))):
    ws = tmp_path / "run" / ".workspace"
    (ws / "usage").mkdir(parents=True)
    (ws / "run.json").write_text(json.dumps({"limits": {"stages": stages}}))
    return ws


def _pointers(ws, rows):
    _write(ws / "usage" / "hook_events.jsonl", rows)


def _ends(ws, pairs):
    _write(ws / "usage" / "stages.jsonl", [{"ts": T(ts), "stage": s} for ts, s in pairs])


def test_read_transcript_counts_each_message_once_with_the_largest_values(tmp_path):
    p = _write(tmp_path / "t.jsonl", [
        _msg("m1", "10:00:00", inp=3, out=5), _msg("m1", "10:00:01", inp=3, out=120, cw=40),
        _msg("m1", "10:00:02", inp=3, out=120), _msg("m2", "10:01:00", inp=7, out=9),
        {"type": "user", "timestamp": T("10:02:00")}, "not json"])
    msgs, span = usage.read_transcript(p)
    assert set(msgs) == {"m1", "m2"}
    assert (msgs["m1"]["input"], msgs["m1"]["output"], msgs["m1"]["cache_write"]) == (3, 120, 40)
    assert msgs["m1"]["ts"] == T("10:00:00")
    assert (span[1] - span[0]).total_seconds() == 120


def test_read_transcript_main_only_skips_sidechain_and_synthetic_lines(tmp_path):
    p = _write(tmp_path / "t.jsonl", [_msg("m1", "10:00:00", inp=1), _msg("m2", "10:00:01", inp=5000, side=True),
                                      _msg("m3", "10:00:02", model="<synthetic>")])
    assert set(usage.read_transcript(p, main_only=True)[0]) == {"m1"}


def test_price_for_matches_family_and_version():
    assert usage.price_for(OPUS, FAKE_PRICES)["family"] == "fakeopus"
    assert usage.price_for("claude-fakeopus-1-20000101", FAKE_PRICES)["family"] == "fakeopus"
    for model in ("claude-fakeopus-2", "fakeopus", "", "codex (stress test)"):
        assert usage.price_for(model, FAKE_PRICES) is None


def test_cost_prices_5_minute_and_1_hour_cache_writes_apart():
    rec = {"input": 1_000_000, "output": 1_000_000, "cache_write": 3_000_000, "cache_write_1h": 1_000_000,
           "cache_read": 1_000_000}
    assert usage.cost(rec, usage.price_for(OPUS, FAKE_PRICES)) == pytest.approx(10 + 50 + 2 * 12.5 + 20 + 1)
    assert usage.cost(rec, None) is None


def test_shipped_price_table_is_dated_and_prices_every_entry():
    prices = usage.load_prices()
    assert prices["as_of"] == "2026-09-27" and prices["currency"] == "USD"
    assert {"opus", "sonnet", "haiku"} <= {p["family"] for p in prices["models"]}
    for p in prices["models"]:
        for k in ("input", "output", "cache_write_5m", "cache_write_1h", "cache_read"):
            assert isinstance(p[k], float) and p[k] > 0, (p, k)
        model_id = "claude-" + p["family"] + "-" + p["version"].replace(".", "-")
        assert usage.price_for(model_id, prices) is p


def test_stage_of_uses_the_first_end_at_or_after_the_message():
    t = lambda hms: usage._ts(T(hms))
    ends = [(t("10:10:00"), 0), (t("10:20:00"), 1), (t("10:40:00"), 5)]
    order = list(range(8))
    assert usage.stage_of(t("10:10:00"), ends, order) == "0"
    assert usage.stage_of(t("10:30:00"), ends, order) == "5"
    assert usage.stage_of(t("10:50:00"), ends, order) == "6"
    assert usage.stage_of(t("10:50:00"), [(t("10:10:00"), 2)], [0, 1, 2, 7]) == "7"
    assert usage.stage_of(t("10:50:00"), [], order) == "not recorded"


def test_no_hook_events_means_not_measured(tmp_path):
    ws = _ws(tmp_path)
    rep = usage.write_report(ws)
    assert rep == {"measured": False, "reason": "Usage not measured in this app."}
    assert json.loads((ws / "usage.json").read_text()) == rep
    assert usage.render(rep) == ["## Usage", "", "Usage not measured in this app.", ""]
    assert usage.load_report(tmp_path)["measured"] is False


def _one_session_run(tmp_path):
    ws = _ws(tmp_path)
    main = _write(tmp_path / "t" / "sess-1.jsonl", [
        _msg("m0", "09:00:00", inp=999, out=999),
        _msg("m1", "10:05:00", inp=100, out=5), _msg("m1", "10:05:01", inp=100, out=200, cw=1000),
        _msg("m9", "10:06:00", inp=5000, side=True),
        _msg("m2", "10:15:00", inp=50, out=100, cr=2000),
        _msg("m3", "10:25:00", inp=10, out=10, cw=400, cw1h=400)])
    sub = _write(tmp_path / "t" / "sess-1" / "subagents" / "agent-a1.jsonl", [
        {"type": "user", "timestamp": T("10:11:00")},
        _msg("s1", "10:12:00", model=SONNET, inp=1000, out=300),
        _msg("s1", "10:13:00", model=SONNET, inp=1000, out=300)])
    _pointers(ws, [
        {"ts": T("10:13:30"), "event": "SubagentStop", "session_id": "sess-1", "transcript_path": str(main),
         "run_marked": T("10:00:00"), "agent_id": "a1", "agent_transcript": str(sub), "description": "Fake"},
        {"ts": T("10:26:00"), "event": "Stop", "session_id": "sess-1", "transcript_path": str(main),
         "run_marked": T("10:00:00")}])
    _ends(ws, [("10:10:00", 0), ("10:20:00", 1)])
    return ws


def test_report_totals_by_stage_and_by_model(tmp_path):
    ws = _one_session_run(tmp_path)
    rep = usage.write_report(ws, now=T("10:30:00"), prices=FAKE_PRICES)
    stages = {r["stage"]: r for r in rep["by_stage"]}
    assert list(stages) == ["0", "1", "2"]
    assert [stages["0"][k] for k in ("input", "output", "cache_write", "cache_read")] == [100, 200, 1000, 0]
    assert [stages["1"][k] for k in ("input", "output", "cache_write", "cache_read")] == [1050, 400, 0, 2000]
    assert [stages["2"][k] for k in ("input", "output", "cache_write", "cache_read")] == [10, 10, 400, 0]
    assert stages["0"]["cost_usd"] == pytest.approx(0.0235) and stages["1"]["cost_usd"] == pytest.approx(0.0125)
    assert stages["2"]["cost_usd"] == pytest.approx(0.0086)
    assert [stages[s]["seconds"] for s in ("0", "1", "2")] == [600, 600, 600]
    models = {r["model"]: r for r in rep["by_model"]}
    assert models[OPUS]["input"] == 160 and models[OPUS]["seconds"] == 1800
    assert models[SONNET]["output"] == 300 and models[SONNET]["seconds"] == 120
    assert models[SONNET]["cost_usd"] == pytest.approx(0.005)
    total = rep["total"]
    assert [total[k] for k in ("input", "output", "cache_write", "cache_read", "seconds")] == [1160, 610, 1400, 2000, 1800]
    assert total["cost_usd"] == pytest.approx(0.0446) and total["cost_complete"] is True
    assert (rep["sessions"], rep["agents"], rep["missing_transcripts"]) == (1, 1, 0)
    assert json.loads((ws / "usage.json").read_text())["total"]["input"] == 1160


def test_render_labels_the_cost_api_equivalent(tmp_path):
    rep = usage.report(_one_session_run(tmp_path), now=T("10:30:00"), prices=FAKE_PRICES)
    text = "\n".join(usage.render(rep))
    assert "API-equivalent" in text and "it is not what you pay" in text and "dated 2000-01-01" in text
    assert "| Stage 2 | 10 | 10 | 400 | 0 | 10m 00s | $0.01 |" in text
    assert "| Total | 1,160 | 610 | 1,400 | 2,000 | 30m 00s | $0.04 |" in text
    assert "### By model" in text and "| claude-fakesonnet-1 |" in text
    assert "—" not in text


def test_a_resumed_run_counts_each_session_in_its_own_window(tmp_path):
    # Final ruling I1: A's window runs from its mark (10:00) to B's mark (12:00), so a2, after A's
    # last hook but before the resume, counts. Time in A's window ends at A's last activity
    # (a2 at 10:15), so the overnight gap is not counted as time.
    ws = _ws(tmp_path)
    a = _write(tmp_path / "t" / "a.jsonl", [_msg("a1", "10:05:00", inp=1), _msg("a2", "10:15:00", inp=100)])
    b = _write(tmp_path / "t" / "b.jsonl", [_msg("b0", "11:00:00", inp=1000), _msg("b1", "12:05:00", inp=10)])
    _pointers(ws, [
        {"ts": T("10:10:00"), "event": "Stop", "session_id": "A", "transcript_path": str(a), "run_marked": T("10:00:00")},
        {"ts": T("12:10:00"), "event": "Stop", "session_id": "B", "transcript_path": str(b), "run_marked": T("12:00:00")}])
    rep = usage.report(ws, now=T("12:30:00"), prices=FAKE_PRICES)
    assert rep["total"]["input"] == 111 and rep["total"]["seconds"] == 900 + 1800
    assert [r["stage"] for r in rep["by_stage"]] == ["not recorded"]
    assert rep["by_stage"][0]["seconds"] == 2700 and rep["sessions"] == 2


def _binds(ws, rows):
    _write(ws / "usage" / "binds.jsonl", [{"ts": T(ts), "session_id": sid, "transcript_path": str(tr)}
                                          for ts, sid, tr in rows])


def test_old_session_is_counted_only_until_another_session_marks_the_run(tmp_path):
    # Reviewer's "oldsession": after B resumes at 12:00, A keeps working on something else, and
    # A's last hook (13:00) is later than B's (12:10). A's later work and its later subagent are
    # not counted, and B, not A, is the session extended to the report, so B's main-session
    # message after its last hook (12:20) still counts.
    ws = _ws(tmp_path)
    a = _write(tmp_path / "t" / "a.jsonl", [_msg("a0", "09:00:00", inp=9000), _msg("a1", "10:05:00", inp=1),
                                            _msg("a9", "12:30:00", inp=500000, out=51000)])
    b = _write(tmp_path / "t" / "b.jsonl", [_msg("b1", "12:05:00", inp=10), _msg("b7", "12:20:00", inp=5)])
    late = _write(tmp_path / "t" / "a" / "subagents" / "agent-late.jsonl", [_msg("l1", "12:40:00", inp=7000, side=True)])
    ok = _write(tmp_path / "t" / "a" / "subagents" / "agent-ok.jsonl", [_msg("k1", "10:06:00", inp=20, side=True)])
    _binds(ws, [("10:00:00", "A", a), ("12:00:00", "B", b)])
    _pointers(ws, [
        {"ts": T("10:07:00"), "event": "SubagentStop", "session_id": "A", "transcript_path": str(a),
         "run_marked": T("10:00:00"), "agent_id": "ok", "agent_transcript": str(ok)},
        {"ts": T("10:10:00"), "event": "Stop", "session_id": "A", "transcript_path": str(a), "run_marked": T("10:00:00")},
        {"ts": T("12:10:00"), "event": "Stop", "session_id": "B", "transcript_path": str(b), "run_marked": T("12:00:00")},
        {"ts": T("12:45:00"), "event": "SubagentStop", "session_id": "A", "transcript_path": str(a),
         "run_marked": T("12:00:00"), "agent_id": "late", "agent_transcript": str(late)},
        {"ts": T("13:00:00"), "event": "Stop", "session_id": "A", "transcript_path": str(a), "run_marked": T("12:00:00")}])
    rep = usage.report(ws, now=T("12:30:00"), prices=FAKE_PRICES)
    assert rep["total"]["input"] == 1 + 20 + 10 + 5 and rep["total"]["output"] == 0
    assert rep["agents"] == 1 and rep["sessions"] == 2
    assert rep["total"]["seconds"] == 600 + 1800  # A 10:00-10:10, B 12:00 to the report


def test_a_session_bound_again_after_another_gets_a_second_window(tmp_path):
    # A, then B, then A again: A counts in [10:00, 11:00) and from 12:00; B in [11:00, 12:00).
    ws = _ws(tmp_path)
    a = _write(tmp_path / "t" / "a.jsonl", [_msg("a1", "10:30:00", inp=1), _msg("a2", "11:30:00", inp=1000),
                                            _msg("a3", "12:30:00", inp=100)])
    b = _write(tmp_path / "t" / "b.jsonl", [_msg("b1", "11:30:00", inp=10), _msg("b2", "12:30:00", inp=10000)])
    _binds(ws, [("10:00:00", "A", a), ("11:00:00", "B", b), ("12:00:00", "A", a)])
    rep = usage.report(ws, now=T("13:00:00"), prices=FAKE_PRICES)
    assert rep["measured"] is True and rep["total"]["input"] == 111
    assert rep["sessions"] == 2 and rep["total"]["seconds"] == 1800 + 1800 + 3600


def test_unreadable_transcripts_and_unknown_models_are_reported(tmp_path):
    ws = _ws(tmp_path)
    main = _write(tmp_path / "t" / "s.jsonl", [_msg("m1", "10:05:00", model="claude-fakeopus-9", inp=5),
                                               _msg("m2", "10:06:00", inp=1)])
    _pointers(ws, [
        {"ts": T("10:10:00"), "event": "SubagentStop", "session_id": "s", "transcript_path": str(main),
         "run_marked": T("10:00:00"), "agent_id": "gone", "agent_type": "general-purpose",
         "agent_transcript": str(tmp_path / "missing.jsonl")},
        # x resumed the run at 10:10:30, after s's hooks, so s keeps its own window (final ruling I1).
        {"ts": T("10:11:00"), "event": "Stop", "session_id": "x", "transcript_path": str(tmp_path / "nope.jsonl"),
         "run_marked": T("10:10:30")}])
    rep = usage.report(ws, now=T("10:30:00"), prices=FAKE_PRICES)
    assert rep["missing_transcripts"] == 2 and rep["unpriced_models"] == ["claude-fakeopus-9"]
    assert rep["by_stage"][0]["cost_complete"] is False
    text = "\n".join(usage.render(rep))
    assert "2 transcript(s) could not be read" in text and "No price in the table for: claude-fakeopus-9." in text
    assert "(partial)" in text


def test_codex_stress_test_usage_is_counted_in_stage_6_when_available(tmp_path):
    ws = _ws(tmp_path)
    main = _write(tmp_path / "t" / "s.jsonl", [_msg("m1", "10:05:00", inp=1)])
    _pointers(ws, [{"ts": T("10:10:00"), "event": "Stop", "session_id": "s", "transcript_path": str(main),
                    "run_marked": T("10:00:00")}])
    _ends(ws, [("10:01:00", 5)])
    _write(ws / "stage-6" / "stress_test" / "usage.json", [{"engine": "codex", "available": True,
           "total": {"input_tokens": 1000, "cached_input_tokens": 400, "output_tokens": 50}, "elapsed_seconds": 90}])
    rep = usage.report(ws, now=T("10:30:00"), prices=FAKE_PRICES)
    six = {r["stage"]: r for r in rep["by_stage"]}["6"]
    assert (six["input"], six["cache_read"], six["output"]) == (601, 400, 50)
    codex = {r["model"]: r for r in rep["by_model"]}["codex (stress test)"]
    assert codex["seconds"] == 90 and codex["cost_complete"] is False and codex["cost_usd"] == 0
    assert "| codex (stress test) | 600 | 50 | 0 | 400 | 1m 30s | not priced |" in "\n".join(usage.render(rep))


def test_codex_without_counts_is_noted(tmp_path):
    ws = _ws(tmp_path)
    main = _write(tmp_path / "t" / "s.jsonl", [_msg("m1", "10:05:00", inp=1)])
    _pointers(ws, [{"ts": T("10:10:00"), "event": "Stop", "session_id": "s", "transcript_path": str(main),
                    "run_marked": T("10:00:00")}])
    _write(ws / "stage-6" / "stress_test" / "usage.json", [{"engine": "codex", "available": False}])
    rep = usage.report(ws, now=T("10:30:00"), prices=FAKE_PRICES)
    assert rep["codex"] == {"available": False}
    assert "Codex ran the stress test but reported no token counts" in "\n".join(usage.render(rep))


def test_cli_stage_end_and_report(tmp_path):
    ws = _ws(tmp_path)
    env = dict(os.environ, PYTHONPATH=str(ROOT), HOME=str(tmp_path), PLUMB_CONFIG=str(tmp_path / "none.json"))
    run = lambda *a: subprocess.run([sys.executable, "-m", "plumb", *a], capture_output=True, text=True, env=env, cwd=ROOT)
    r = run("usage", "stage-end", str(ws), "3")
    assert r.returncode == 0 and json.loads(r.stdout)["stage"] == 3
    assert json.loads((ws / "usage" / "stages.jsonl").read_text())["stage"] == 3
    r = run("usage", "report", str(ws))
    assert r.returncode == 0 and json.loads(r.stdout)["measured"] is False
    assert json.loads((ws / "usage.json").read_text())["reason"] == "Usage not measured in this app."


# Fix round 1: a transcript or Codex usage file the report cannot read must never crash it.

def test_a_transcript_truncated_mid_utf8_character_counts_as_missing_not_a_crash(tmp_path):
    ws = _ws(tmp_path)
    main = tmp_path / "t" / "s.jsonl"
    main.parent.mkdir(parents=True, exist_ok=True)
    good_line = json.dumps(_msg("m1", "10:05:00", inp=5)).encode("utf-8") + b"\n"
    main.write_bytes(good_line + b"\xe2\x82")  # a 3-byte UTF-8 sequence cut short, as a live write can leave
    _pointers(ws, [{"ts": T("10:10:00"), "event": "Stop", "session_id": "s", "transcript_path": str(main),
                    "run_marked": T("10:00:00")}])
    rep = usage.report(ws, now=T("10:30:00"), prices=FAKE_PRICES)
    assert rep["measured"] is True and rep["missing_transcripts"] == 1
    assert rep["total"]["input"] == 0
    assert "1 transcript(s) could not be read" in "\n".join(usage.render(rep))


def test_an_unreadable_transcript_counts_as_missing_not_a_crash(tmp_path):
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("running as root: chmod 000 does not block reads")
    ws = _ws(tmp_path)
    main = _write(tmp_path / "t" / "s.jsonl", [_msg("m1", "10:05:00", inp=5)])
    main.chmod(0o000)
    try:
        _pointers(ws, [{"ts": T("10:10:00"), "event": "Stop", "session_id": "s", "transcript_path": str(main),
                        "run_marked": T("10:00:00")}])
        rep = usage.report(ws, now=T("10:30:00"), prices=FAKE_PRICES)
    finally:
        main.chmod(0o644)
    assert rep["measured"] is True and rep["missing_transcripts"] == 1
    assert rep["total"]["input"] == 0


def test_codex_total_as_a_list_is_treated_as_unavailable_not_a_crash(tmp_path):
    ws = _ws(tmp_path)
    main = _write(tmp_path / "t" / "s.jsonl", [_msg("m1", "10:05:00", inp=1)])
    _pointers(ws, [{"ts": T("10:10:00"), "event": "Stop", "session_id": "s", "transcript_path": str(main),
                    "run_marked": T("10:00:00")}])
    _write(ws / "stage-6" / "stress_test" / "usage.json", [{"engine": "codex", "available": True,
           "total": ["not", "a", "dict"], "elapsed_seconds": 90}])
    rep = usage.report(ws, now=T("10:30:00"), prices=FAKE_PRICES)
    assert rep["codex"] == {"available": False}
    assert "codex (stress test)" not in {r["model"] for r in rep["by_model"]}
    assert "Codex ran the stress test but reported no token counts" in "\n".join(usage.render(rep))


def test_codex_total_with_a_non_numeric_count_is_treated_as_unavailable_not_a_crash(tmp_path):
    ws = _ws(tmp_path)
    main = _write(tmp_path / "t" / "s.jsonl", [_msg("m1", "10:05:00", inp=1)])
    _pointers(ws, [{"ts": T("10:10:00"), "event": "Stop", "session_id": "s", "transcript_path": str(main),
                    "run_marked": T("10:00:00")}])
    _write(ws / "stage-6" / "stress_test" / "usage.json", [{"engine": "codex", "available": True,
           "total": {"input_tokens": "lots", "cached_input_tokens": 0, "output_tokens": 0}, "elapsed_seconds": 90}])
    rep = usage.report(ws, now=T("10:30:00"), prices=FAKE_PRICES)
    assert rep["codex"] == {"available": False}


def test_cli_report_exits_0_when_a_transcript_cannot_be_read(tmp_path):
    ws = _ws(tmp_path)
    main = tmp_path / "t" / "s.jsonl"
    main.parent.mkdir(parents=True, exist_ok=True)
    main.write_bytes(json.dumps(_msg("m1", "10:05:00", inp=1)).encode("utf-8") + b"\n" + b"\xe2\x82")
    _pointers(ws, [{"ts": T("10:10:00"), "event": "Stop", "session_id": "s", "transcript_path": str(main),
                    "run_marked": T("10:00:00")}])
    env = dict(os.environ, PYTHONPATH=str(ROOT), HOME=str(tmp_path), PLUMB_CONFIG=str(tmp_path / "none.json"))
    r = subprocess.run([sys.executable, "-m", "plumb", "usage", "report", str(ws)],
                        capture_output=True, text=True, env=env, cwd=ROOT)
    assert r.returncode == 0
    assert json.loads(r.stdout)["measured"] is True


# Final ruling I2: times written by usage code keep milliseconds.

class _FixedClock(datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime.datetime(2026, 9, 27, 10, 10, 0, 900000, tzinfo=datetime.timezone.utc)


_CLOCK = types.SimpleNamespace(datetime=_FixedClock, timezone=datetime.timezone, timedelta=datetime.timedelta)


def test_a_message_300_ms_before_a_stage_end_belongs_to_that_stage(tmp_path, monkeypatch):
    monkeypatch.setattr(usage, "datetime", _CLOCK)
    ws = _ws(tmp_path)
    main = _write(tmp_path / "t" / "s.jsonl", [
        {**_msg("m1", "10:05:00", inp=1), "timestamp": "2026-09-27T10:10:00.600Z"},
        {**_msg("m2", "10:05:00", inp=10), "timestamp": "2026-09-27T10:10:01.200Z"}])
    rec = usage.stage_end(ws, 0)  # the clock reads 10:10:00.900
    assert rec["ts"] == "2026-09-27T10:10:00.900+00:00"
    _pointers(ws, [{"ts": T("10:10:05"), "event": "Stop", "session_id": "s", "transcript_path": str(main),
                    "run_marked": T("10:00:00")}])
    monkeypatch.undo()
    rep = usage.report(ws, now=T("10:30:00"), prices=FAKE_PRICES)
    stages = {r["stage"]: r["input"] for r in rep["by_stage"]}
    assert stages == {"0": 1, "1": 10}


def test_hook_and_mark_times_keep_milliseconds(tmp_path, monkeypatch):
    monkeypatch.setattr(usage, "datetime", _CLOCK)
    home, ws = tmp_path / "home", _ws(tmp_path)
    entry = usage.mark_active(ws, tmp_path, home)
    assert entry["marked"] == entry["last_activity"] == "2026-09-27T10:10:00.900+00:00"
    cmd = "plumb usage mark " + str(ws)
    usage.bind_hook({"session_id": "s", "cwd": str(tmp_path), "tool_input": {"command": cmd}}, home)
    ptr = usage.record_hook({"session_id": "s", "hook_event_name": "Stop", "transcript_path": "/x/s.jsonl"}, home)
    bind = json.loads((ws / "usage" / "binds.jsonl").read_text())
    assert ptr["ts"] == bind["ts"] == "2026-09-27T10:10:00.900+00:00"
    assert usage._read_active(home, now=usage._now())[0]["sessions"] == ["s"]  # still a valid entry


def test_helper_agents_with_no_type_and_no_transcript_are_not_counted(tmp_path):
    """Fake run: Claude Code's background helpers stop with an empty agent_type and write no transcript."""
    ws = _one_session_run(tmp_path)
    log = ws / "usage" / "hook_events.jsonl"
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    rows.insert(1, {"ts": T("10:14:00"), "event": "SubagentStop", "session_id": "sess-1",
                    "transcript_path": rows[0]["transcript_path"], "run_marked": T("10:00:00"),
                    "agent_id": "helper-1", "agent_type": "", "agent_transcript": str(tmp_path / "none.jsonl"),
                    "description": ""})
    _pointers(ws, rows)
    rep = usage.report(ws, now=T("10:30:00"), prices=FAKE_PRICES)
    assert (rep["agents"], rep["missing_transcripts"]) == (1, 0)
