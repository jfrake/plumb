from __future__ import annotations
import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pymupdf
import pytest

from plumb import consent, stress

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "skills/review/scripts/codex_stress_test.py"
PROMPT = ROOT / "skills/review/shared/stress-test-prompt.md"


def _runner():
    spec = importlib.util.spec_from_file_location("codex_stress_test", RUNNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


FIX = ("## Issues\n\n### 1. The sample is selected\n\nSeverity: Weakens a claim\nFix: new analysis\n\nText one.\n\n"
       "### 2. Stars do not match\n\nSeverity: Minor\nFix: quick fix\n\nText two.\n\n## What I left out\n\nNothing.\n")
REPORT = "1. First comment text.\n\n2. Second comment text.\n\nREFERENCES\n\nSmith, J. (2020). T. J, 1, 1.\n"
OLD = "MAJOR COMMENTS\n\n1. Old style point.\n\nMINOR COMMENTS\n\n1. Old minor.\n"


def test_parse_fix_list_items():
    pts = _runner().parse_draft(FIX)
    assert [p["point_id"] for p in pts] == ["issue-1", "issue-2"]
    assert "What I left out" not in pts[-1]["text"]


def test_parse_report_comments_stop_at_references():
    pts = _runner().parse_draft(REPORT)
    assert [p["point_id"] for p in pts] == ["comment-1", "comment-2"]
    assert "Smith" not in pts[-1]["text"]


def test_old_format_still_parses():
    assert [p["point_id"] for p in _runner().parse_review(OLD)] == ["major-1", "minor-1"]


def test_prompt_uses_the_generic_example():
    text = PROMPT.read_text()
    assert "Column 2 of Table 3 reports" in text


FAKE_CODEX = """#!/usr/bin/env python3
import json, sys
args = sys.argv[1:]
out = args[args.index("-o") + 1]
sys.stdin.read()
json.dump({"point_id": "x", "verdict": "confirmed", "already_addressed": {"status": "no"},
           "recommendation": "keep_as_is"}, open(out, "w"))
"""


def _fake_codex_dir(tmp_path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    exe = bindir / "codex"
    exe.write_text(FAKE_CODEX)
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    return bindir


def _pdf(tmp_path):
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "A short paper with enough words to extract. " * 5)
    p = tmp_path / "paper.pdf"
    doc.save(p)
    return p


def test_runner_writes_one_file_per_point_and_a_summary(tmp_path):
    draft = tmp_path / "draft.md"
    draft.write_text(FIX)
    out = tmp_path / "stress_test"
    env = dict(os.environ, PATH=f"{_fake_codex_dir(tmp_path)}{os.pathsep}{os.environ['PATH']}")
    r = subprocess.run([sys.executable, str(RUNNER), str(_pdf(tmp_path)), str(draft), str(PROMPT), str(out),
                        "--parallel", "2"], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    assert (out / "issue-1.json").exists() and (out / "issue-2.json").exists()
    assert json.loads((out / "summary.json").read_text())["n_points"] == 2


def test_runner_without_codex_exits_1(tmp_path):
    draft = tmp_path / "draft.md"
    draft.write_text(FIX)
    env = dict(os.environ, PATH=str(tmp_path / "empty"))
    r = subprocess.run([sys.executable, str(RUNNER), str(_pdf(tmp_path)), str(draft), str(PROMPT),
                        str(tmp_path / "o")], capture_output=True, text=True, env=env)
    assert r.returncode == 1 and "not on PATH" in r.stderr


OPENAI_OK = {"provider": "OpenAI", "trains_on_inputs": False, "retention_days": 30, "zero_retention_confirmed": None}
BASE = dict(role="author", provider="anthropic-api", provider_trains_on_inputs=False, retention_days=30,
            egress=["manuscript_text", "search_queries", "codex_stress_test"], coauthors_agree=True,
            stress_test_provider=OPENAI_OK)


def rec(**kw):
    d = dict(BASE)
    d.update(kw)
    return consent.from_dict(d)


@pytest.mark.parametrize("d", ["standard", "deep", "full"])
def test_codex_runs_at_standard_and_deep_when_everything_is_in_place(d):
    assert stress.decide(d, True, True, rec()) == ("codex", "")


def test_quick_has_no_stress_test():
    assert stress.decide("quick", True, True, rec()) == ("", "Quick depth has no stress test.")


@pytest.mark.parametrize("d", ["standard", "deep"])
def test_claude_runs_when_codex_is_not_enabled_or_missing(d):
    assert stress.decide(d, False, True, rec()) == ("claude", "Codex is not enabled in the Plumb config.")
    assert stress.decide(d, True, False, rec()) == ("claude", "The codex command is not on PATH.")
    assert stress.decide(d, True, True, None) == ("claude", "No consent record was found.")


def test_claude_runs_when_consent_does_not_name_openai():
    engine, reason = stress.decide("standard", True, True, rec(stress_test_provider=None))
    assert engine == "claude" and "OpenAI" in reason
    assert stress.decide("deep", True, True, rec(egress=["manuscript_text", "search_queries"]))[0] == "claude"


@pytest.mark.parametrize("trains", [None, True])
def test_claude_runs_when_openai_training_unknown_or_on(trains):
    assert stress.decide("deep", True, True, rec(stress_test_provider=dict(OPENAI_OK, trains_on_inputs=trains)))[0] == "claude"


def test_zero_retention_journal_needs_openai_zero_retention():
    engine, reason = stress.decide("standard", True, True, rec(), needs_zero_retention=True)
    assert engine == "claude" and "zero data retention" in reason
    zdr = rec(stress_test_provider=dict(OPENAI_OK, zero_retention_confirmed=True))
    assert stress.decide("standard", True, True, zdr, needs_zero_retention=True) == ("codex", "")


def test_codex_problem_is_empty_only_when_codex_can_run():
    assert stress.codex_problem(True, True, rec()) == ""
    assert stress.codex_problem(False, True, rec()) == "Codex is not enabled in the Plumb config."


def test_openai_answers_never_block_the_run():
    bad = rec(stress_test_provider=dict(OPENAI_OK, trains_on_inputs=True))
    assert consent.missing_consents(bad) == []


@pytest.mark.parametrize("bad", [dict(OPENAI_OK, trains_on_inputs="no"), dict(OPENAI_OK, extra=1),
                                 dict(OPENAI_OK, retention_days=True), "OpenAI"])
def test_openai_entry_types_are_validated(bad):
    with pytest.raises(consent.ConsentError):
        rec(stress_test_provider=bad)


CWD_CODEX = """#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
out = args[args.index("-o") + 1]
sys.stdin.read()
json.dump({"cwd": os.getcwd(), "listing": os.listdir(".")}, open(out, "w"))
"""


def test_codex_exec_runs_in_an_empty_temp_directory(tmp_path, monkeypatch):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    exe = bindir / "codex"
    exe.write_text(CWD_CODEX)
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.chdir(tmp_path)
    got = json.loads(_runner().call_codex("sys", "user", "paper", None, 30))
    assert os.path.realpath(got["cwd"]) != os.path.realpath(str(tmp_path))
    assert got["listing"] == [] and not os.path.exists(got["cwd"])


USAGE_CODEX = """#!/usr/bin/env python3
import json, sys
args = sys.argv[1:]
assert "--json" in args
out = args[args.index("-o") + 1]
sys.stdin.read()
print(json.dumps({"type": "thread.started"}))
print("not json")
print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 1000, "cached_input_tokens": 400,
                                                      "output_tokens": 50}}))
json.dump({"point_id": "x", "verdict": "confirmed", "recommendation": "keep_as_is"}, open(out, "w"))
"""


def _run(tmp_path, *extra, codex=None, path=None):
    draft = tmp_path / "draft.md"
    draft.write_text(FIX)
    env = dict(os.environ)
    if codex is not None:
        bindir = tmp_path / "bin"
        bindir.mkdir(exist_ok=True)
        (bindir / "codex").write_text(codex)
        (bindir / "codex").chmod(0o755)
        env["PATH"] = f"{bindir}{os.pathsep}{os.environ['PATH']}"
    if path is not None:
        env["PATH"] = path
    return subprocess.run([sys.executable, str(RUNNER), str(_pdf(tmp_path)), str(draft), str(PROMPT),
                           str(tmp_path / "stress_test"), *extra], capture_output=True, text=True, env=env)


def test_parse_usage_takes_the_last_usage_object():
    out = "\n".join([json.dumps({"usage": {"input_tokens": 1, "output_tokens": 1}}), "noise",
                     json.dumps({"msg": {"info": {"input_tokens": 7, "cached_input_tokens": 2,
                                                  "output_tokens": 3, "reasoning_output_tokens": 1}}})])
    assert _runner().parse_usage(out) == {"input_tokens": 7, "cached_input_tokens": 2,
                                          "output_tokens": 3, "reasoning_output_tokens": 1}
    assert _runner().parse_usage("no json here") == {}


def test_parse_usage_prefers_total_token_usage_in_a_token_count_event():
    # codex-cli 0.157.0's `--json` session log carries a "token_count" event whose
    # info holds both a cumulative total_token_usage and a per-turn last_token_usage;
    # the cumulative total is what usage.json should report.
    line = json.dumps({"type": "token_count", "info": {
        "total_token_usage": {"input_tokens": 500, "cached_input_tokens": 100, "output_tokens": 20,
                              "reasoning_output_tokens": 5, "total_tokens": 625},
        "last_token_usage": {"input_tokens": 50, "cached_input_tokens": 10, "output_tokens": 5,
                             "reasoning_output_tokens": 1, "total_tokens": 66}}})
    assert _runner().parse_usage(line) == {"input_tokens": 500, "cached_input_tokens": 100,
                                           "output_tokens": 20, "reasoning_output_tokens": 5}


def test_codex_run_records_usage(tmp_path):
    r = _run(tmp_path, "--parallel", "2", codex=USAGE_CODEX)
    assert r.returncode == 0, r.stderr
    u = json.loads((tmp_path / "stress_test" / "usage.json").read_text())
    assert u["available"] is True and u["points_with_usage"] == 2
    assert u["total"] == {"input_tokens": 2000, "cached_input_tokens": 800, "output_tokens": 100,
                          "reasoning_output_tokens": 0}
    assert u["elapsed_seconds"] >= 0
    s = json.loads((tmp_path / "stress_test" / "summary.json").read_text())
    assert s["engine"] == "codex" and s["n_points"] == 2


def test_codex_run_without_printed_usage_says_unavailable(tmp_path):
    r = _run(tmp_path, codex=FAKE_CODEX)
    assert r.returncode == 0, r.stderr
    u = json.loads((tmp_path / "stress_test" / "usage.json").read_text())
    assert u["available"] is False and u["points"] == {"issue-1": None, "issue-2": None}


def test_prepare_writes_the_inputs_without_codex(tmp_path):
    out = tmp_path / "stress_test"
    out.mkdir()
    (out / "issue-9.json").write_text("{}")
    (out / "summary.json").write_text("{}")
    r = _run(tmp_path, "--mode", "prepare", "--engine", "claude", path=str(tmp_path / "empty"))
    assert r.returncode == 0, r.stderr
    points = json.loads((out / "input" / "points.json").read_text())
    assert [p["point_id"] for p in points] == ["issue-1", "issue-2"]
    assert "POINT ID: issue-1" in (out / "input" / "issue-1.txt").read_text()
    assert "[page 1]" in (out / "input" / "paper.txt").read_text()
    assert json.loads((out / "run_manifest.json").read_text()) == {"point_ids": ["issue-1", "issue-2"]}
    assert not (out / "issue-9.json").exists() and not (out / "summary.json").exists()


def test_summarize_writes_the_claude_summary(tmp_path):
    out = tmp_path / "stress_test"
    assert _run(tmp_path, "--mode", "prepare", "--engine", "claude").returncode == 0
    (out / "issue-1.json").write_text('```json\n{"point_id": "issue-1", "verdict": "wrong", '
                                      '"recommendation": "drop"}\n```')
    (out / "issue-2.json").write_text('{"point_id": "issue-2", "verdict": "confirmed", '
                                      '"recommendation": "keep_as_is"}')
    r = _run(tmp_path, "--mode", "summarize", "--engine", "claude", path=str(tmp_path / "empty"))
    assert r.returncode == 0, r.stderr
    s = json.loads((out / "summary.json").read_text())
    assert s["engine"] == "claude" and s["n_points"] == 2 and s["recommendations"] == {"drop": 1, "keep_as_is": 1}
    assert json.loads((out / "issue-1.json").read_text())["_point_text"].startswith("The sample is selected")


def test_summarize_exits_1_when_a_point_is_missing(tmp_path):
    out = tmp_path / "stress_test"
    assert _run(tmp_path, "--mode", "prepare", "--engine", "claude").returncode == 0
    (out / "issue-1.json").write_text('{"point_id": "issue-1", "verdict": "confirmed"}')
    (out / "issue-2.json").write_text("not json at all")
    r = _run(tmp_path, "--mode", "summarize", "--engine", "claude")
    assert r.returncode == 1 and "issue-2" in r.stderr
    assert json.loads((out / "summary.json").read_text())["n_points"] == 1
