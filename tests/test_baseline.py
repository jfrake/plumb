"""eval/baseline.py: one fixed prompt, one PDF, two models over their APIs. Both API calls are
replaced by fakes here; no test touches the network."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "eval" / "baseline.py"
PROMPT_FILE = ROOT / "eval" / "baseline_prompt.txt"


def _load():
    spec = importlib.util.spec_from_file_location("baseline", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def baseline():
    return _load()


@pytest.fixture
def pdf(tmp_path):
    p = tmp_path / "paper.pdf"
    p.write_bytes(b"%PDF-1.4 fake paper body")
    return p


@pytest.fixture
def keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-FAKE-SECRET-0001")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-FAKE-SECRET-0002")
    return {"OPENAI_API_KEY": "sk-openai-FAKE-SECRET-0001", "ANTHROPIC_API_KEY": "sk-ant-FAKE-SECRET-0002"}


def openai_response(text="1. A problem (OpenAI)", status="completed", **extra):
    """The shape responses.create returns after model_dump, reduced to what the script reads."""
    return dict({"id": "resp_1", "model": "gpt-6-astra-2026-09-01", "status": status,
                 "output": [{"type": "reasoning", "id": "rs_1", "summary": []},
                            {"type": "message", "id": "msg_1", "role": "assistant", "status": "completed",
                             "content": [{"type": "output_text", "text": text, "annotations": []}]}],
                 "incomplete_details": None, "error": None,
                 "usage": {"input_tokens": 10, "output_tokens": 5}}, **extra)


def anthropic_response(text="1. A problem (Anthropic)", stop_reason="end_turn", **extra):
    """The shape messages.create returns after to_dict, reduced to what the script reads."""
    return dict({"id": "msg_1", "model": "claude-fable-5-1", "role": "assistant", "stop_reason": stop_reason,
                 "stop_details": None,
                 "content": [{"type": "thinking", "thinking": "", "signature": "x"},
                             {"type": "text", "text": text}],
                 "usage": {"input_tokens": 10, "output_tokens": 5}}, **extra)


def _fake_calls(baseline, monkeypatch, log=None, openai_reply=None, anthropic_reply=None):
    """Replace both call functions with fakes that record each call and return a canned response dict."""
    log = [] if log is None else log
    openai_reply = openai_response() if openai_reply is None else openai_reply
    anthropic_reply = anthropic_response() if anthropic_reply is None else anthropic_reply

    def fake_openai(pdf_bytes, filename, prompt):
        log.append(("gpt-6-astra", filename, prompt))
        return json.loads(json.dumps(openai_reply))

    def fake_anthropic(pdf_bytes, filename, prompt):
        log.append(("claude-fable-5-1", filename, prompt))
        return json.loads(json.dumps(anthropic_reply))

    monkeypatch.setattr(baseline, "call_openai", fake_openai)
    monkeypatch.setattr(baseline, "call_anthropic", fake_anthropic)
    return log


class _StubSDK:
    """Stands in for the openai or anthropic package: records the create/stream kwargs, returns a reply."""

    def __init__(self, reply):
        self.reply = reply
        self.client_kwargs = None
        self.call_kwargs = None

    def install(self, monkeypatch, name):
        import types
        sdk = self
        mod = types.ModuleType(name)

        class _Reply:
            def model_dump(self, mode="python"):
                return sdk.reply

            def to_dict(self):
                return sdk.reply

        class _Stream:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def get_final_message(self):
                return _Reply()

        class _Responses:
            def create(self, **kw):
                sdk.call_kwargs = kw
                return _Reply()

        class _Messages:
            def stream(self, **kw):
                sdk.call_kwargs = kw
                return _Stream()

        class _Client:
            def __init__(self, **kw):
                sdk.client_kwargs = kw
                self.responses = _Responses()
                self.messages = _Messages()

        mod.OpenAI = _Client
        mod.Anthropic = _Client
        monkeypatch.setitem(sys.modules, name, mod)
        return self


def _run(baseline, pdf, out, *extra):
    return baseline.main([str(pdf), "--journal", "Organization Science", "--out", str(out), *extra])


# --- the prompt and its hash ---

def test_prompt_file_hash_matches_the_pinned_constant(baseline):
    assert hashlib.sha256(PROMPT_FILE.read_bytes()).hexdigest() == baseline.PROMPT_SHA256
    assert "{journal}" in PROMPT_FILE.read_text(encoding="utf-8")


def test_show_prompt_hash_prints_the_hash(baseline, capsys):
    assert baseline.main(["--show-prompt-hash"]) == 0
    assert capsys.readouterr().out.strip() == baseline.PROMPT_SHA256


def test_refuses_to_run_when_the_prompt_hash_does_not_match(baseline, monkeypatch, pdf, tmp_path, keys, capsys):
    _fake_calls(baseline, monkeypatch)
    monkeypatch.setattr(baseline, "PROMPT_SHA256", "0" * 64)
    assert _run(baseline, pdf, tmp_path / "out") != 0
    assert "baseline_prompt.txt" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


# --- the folder layout ---

def test_a_run_writes_one_folder_per_model_and_run(baseline, monkeypatch, pdf, tmp_path, keys):
    log = _fake_calls(baseline, monkeypatch)
    out = tmp_path / "out"
    assert _run(baseline, pdf, out) == 0
    assert len(log) == 6
    for model in ("gpt-6-astra", "claude-fable-5-1"):
        for n in (1, 2, 3):
            folder = out / model / f"run-{n}"
            assert sorted(p.name for p in folder.iterdir()) == ["done", "issues.md", "request.json", "response.json"]
    req = json.loads((out / "gpt-6-astra" / "run-1" / "request.json").read_text())
    assert req["pdf_sha256"] == hashlib.sha256(pdf.read_bytes()).hexdigest()
    assert req["prompt_sha256"] == baseline.PROMPT_SHA256
    assert "Organization Science" in req["prompt_text"] and "{journal}" not in req["prompt_text"]
    assert req["journal"] == "Organization Science"
    assert req["model_requested"] == "gpt-6-astra" and req["effort"] == "high"
    assert req["timestamp_utc"].endswith("+00:00")
    assert req["python_version"].startswith(sys.version.split()[0])
    assert set(req["library_versions"]) == {"openai", "anthropic"}
    assert req["run"] == 1
    resp = json.loads((out / "gpt-6-astra" / "run-1" / "response.json").read_text())
    assert resp["model"] == "gpt-6-astra-2026-09-01" and resp["usage"]["output_tokens"] == 5
    assert (out / "claude-fable-5-1" / "run-2" / "issues.md").read_text() == "1. A problem (Anthropic)"
    sent = log[0][2]
    assert sent == req["prompt_text"] and sent.startswith("I am an author of the attached manuscript")


def test_manifest_lists_every_run_with_its_status(baseline, monkeypatch, pdf, tmp_path, keys):
    _fake_calls(baseline, monkeypatch)
    out = tmp_path / "out"
    assert _run(baseline, pdf, out) == 0
    m = json.loads((out / "manifest.json").read_text())
    assert m["pdf_sha256"] == hashlib.sha256(pdf.read_bytes()).hexdigest()
    assert m["prompt_sha256"] == baseline.PROMPT_SHA256
    assert m["journal"] == "Organization Science" and m["run_of_record"] == 1
    assert [(r["model"], r["run"], r["status"]) for r in m["runs"]] == [
        ("gpt-6-astra", 1, "complete"), ("gpt-6-astra", 2, "complete"), ("gpt-6-astra", 3, "complete"),
        ("claude-fable-5-1", 1, "complete"), ("claude-fable-5-1", 2, "complete"),
        ("claude-fable-5-1", 3, "complete")]
    assert m["runs"][0]["folder"] == "gpt-6-astra/run-1"
    assert m["runs"][0]["model_returned"] == "gpt-6-astra-2026-09-01"


def test_models_and_runs_can_be_narrowed(baseline, monkeypatch, pdf, tmp_path, keys):
    log = _fake_calls(baseline, monkeypatch)
    out = tmp_path / "out"
    assert _run(baseline, pdf, out, "--models", "claude-fable-5-1", "--runs", "1") == 0
    assert [m for m, _, _ in log] == ["claude-fable-5-1"]
    assert not (out / "gpt-6-astra").exists()


# --- idempotence ---

def test_a_second_invocation_skips_complete_runs(baseline, monkeypatch, pdf, tmp_path, keys):
    log = _fake_calls(baseline, monkeypatch)
    out = tmp_path / "out"
    assert _run(baseline, pdf, out) == 0
    before = (out / "gpt-6-astra" / "run-1" / "request.json").read_text()
    assert _run(baseline, pdf, out) == 0
    assert len(log) == 6
    assert (out / "gpt-6-astra" / "run-1" / "request.json").read_text() == before
    m = json.loads((out / "manifest.json").read_text())
    assert {r["status"] for r in m["runs"]} == {"complete"} and len(m["runs"]) == 6


def test_an_incomplete_run_folder_is_redone(baseline, monkeypatch, pdf, tmp_path, keys):
    log = _fake_calls(baseline, monkeypatch)
    out = tmp_path / "out"
    assert _run(baseline, pdf, out, "--models", "gpt-6-astra", "--runs", "1") == 0
    (out / "gpt-6-astra" / "run-1" / "response.json").unlink()
    assert _run(baseline, pdf, out, "--models", "gpt-6-astra", "--runs", "1") == 0
    assert len(log) == 2
    assert (out / "gpt-6-astra" / "run-1" / "response.json").exists()


def test_an_out_folder_holding_another_paper_is_refused(baseline, monkeypatch, pdf, tmp_path, keys, capsys):
    _fake_calls(baseline, monkeypatch)
    out = tmp_path / "out"
    assert _run(baseline, pdf, out, "--runs", "1") == 0
    other = tmp_path / "other.pdf"
    other.write_bytes(b"%PDF-1.4 a different paper")
    assert _run(baseline, other, out, "--runs", "1") != 0
    assert "another PDF" in capsys.readouterr().err


def test_the_manifest_lists_every_run_folder_on_disk_not_only_this_invocations(baseline, monkeypatch, pdf, tmp_path, keys):
    _fake_calls(baseline, monkeypatch)
    out = tmp_path / "out"
    assert _run(baseline, pdf, out, "--runs", "3") == 0
    assert _run(baseline, pdf, out, "--runs", "1", "--models", "claude-fable-5-1") == 0
    m = json.loads((out / "manifest.json").read_text())
    assert [(r["model"], r["run"]) for r in m["runs"]] == [
        ("gpt-6-astra", 1), ("gpt-6-astra", 2), ("gpt-6-astra", 3),
        ("claude-fable-5-1", 1), ("claude-fable-5-1", 2), ("claude-fable-5-1", 3)]
    assert all(r["status"] == "complete" and r["model_returned"] for r in m["runs"])


def test_a_stray_incomplete_folder_is_listed_as_incomplete(baseline, monkeypatch, pdf, tmp_path, keys):
    _fake_calls(baseline, monkeypatch)
    out = tmp_path / "out"
    stray = out / "gpt-6-astra" / "run-5"
    stray.mkdir(parents=True)
    (stray / "request.json").write_text("{}")
    assert _run(baseline, pdf, out, "--runs", "1", "--models", "claude-fable-5-1") == 0
    m = json.loads((out / "manifest.json").read_text())
    assert [(r["model"], r["run"], r["status"]) for r in m["runs"]] == [
        ("gpt-6-astra", 5, "incomplete"), ("claude-fable-5-1", 1, "complete")]


def test_a_zero_byte_issues_file_without_the_done_marker_is_redone(baseline, monkeypatch, pdf, tmp_path, keys):
    log = _fake_calls(baseline, monkeypatch)
    out = tmp_path / "out"
    folder = out / "gpt-6-astra" / "run-1"
    folder.mkdir(parents=True)
    for name in ("request.json", "response.json"):
        (folder / name).write_text("{}")
    (folder / "issues.md").write_bytes(b"")
    assert _run(baseline, pdf, out, "--runs", "1", "--models", "gpt-6-astra") == 0
    assert len(log) == 1
    assert (folder / "done").is_file() and (folder / "issues.md").read_text() == "1. A problem (OpenAI)"


def test_every_output_file_is_written_through_a_rename(baseline, monkeypatch, pdf, tmp_path, keys):
    _fake_calls(baseline, monkeypatch)
    replaced = []
    real = os.replace

    def spy(src, dst):
        replaced.append(Path(dst).name)
        return real(src, dst)

    monkeypatch.setattr(baseline.os, "replace", spy)
    out = tmp_path / "out"
    assert _run(baseline, pdf, out, "--runs", "1", "--models", "gpt-6-astra") == 0
    assert {"request.json", "response.json", "issues.md", "done", "manifest.json"} <= set(replaced)
    assert not [p for p in out.rglob("*") if p.is_file() and p.name not in
                ("request.json", "response.json", "issues.md", "done", "manifest.json")]


def test_an_unreadable_manifest_is_named_and_stops_the_run(baseline, monkeypatch, pdf, tmp_path, keys, capsys):
    log = _fake_calls(baseline, monkeypatch)
    out = tmp_path / "out"
    out.mkdir()
    (out / "manifest.json").write_text("{not json")
    assert _run(baseline, pdf, out, "--runs", "1") != 0
    assert "manifest.json" in capsys.readouterr().err and log == []


@pytest.mark.parametrize("flag, value, word", [
    ("--journal", "Management Science", "journal"),
    ("--run-of-record", "2", "run_of_record"),
])
def test_a_manifest_from_a_different_setting_is_refused(baseline, monkeypatch, pdf, tmp_path, keys, capsys,
                                                         flag, value, word):
    log = _fake_calls(baseline, monkeypatch)
    out = tmp_path / "out"
    assert _run(baseline, pdf, out, "--runs", "2") == 0
    args = [str(pdf), "--journal", "Organization Science", "--out", str(out), "--runs", "2", flag, value]
    assert baseline.main(args) != 0
    assert word in capsys.readouterr().err and len(log) == 4


def test_a_manifest_from_a_different_prompt_or_effort_is_refused(baseline, monkeypatch, pdf, tmp_path, keys, capsys):
    log = _fake_calls(baseline, monkeypatch)
    out = tmp_path / "out"
    assert _run(baseline, pdf, out, "--runs", "1") == 0
    m = json.loads((out / "manifest.json").read_text())
    for field in ("prompt_sha256", "effort"):
        changed = dict(m, **{field: "something else"})
        (out / "manifest.json").write_text(json.dumps(changed))
        assert _run(baseline, pdf, out, "--runs", "1") != 0
        assert field in capsys.readouterr().err
    assert len(log) == 2


# --- refusals ---

def test_refuses_an_out_folder_inside_the_repo(baseline, monkeypatch, pdf, keys, capsys):
    _fake_calls(baseline, monkeypatch)
    out = ROOT / "eval" / "baseline_out_should_not_exist"
    assert _run(baseline, pdf, out) != 0
    assert "inside the repo" in capsys.readouterr().err
    assert not out.exists()


def test_refuses_a_symlink_that_resolves_into_the_repo(baseline, monkeypatch, pdf, tmp_path, keys, capsys):
    _fake_calls(baseline, monkeypatch)
    link = tmp_path / "link"
    link.symlink_to(ROOT / "eval", target_is_directory=True)
    out = link / "baseline_out_should_not_exist"
    assert _run(baseline, pdf, out) != 0
    assert "inside the repo" in capsys.readouterr().err
    assert not (ROOT / "eval" / "baseline_out_should_not_exist").exists()


def test_refuses_a_path_with_spaces_inside_the_repo(baseline, monkeypatch, pdf, keys, capsys):
    _fake_calls(baseline, monkeypatch)
    out = ROOT / "eval" / "out with spaces" / "should not exist"
    assert _run(baseline, pdf, out) != 0
    assert "inside the repo" in capsys.readouterr().err
    assert not (ROOT / "eval" / "out with spaces").exists()


def test_a_tilde_in_out_means_the_home_folder(baseline, monkeypatch, pdf, tmp_path, keys):
    _fake_calls(baseline, monkeypatch)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert baseline.main([str(pdf), "--journal", "J", "--out", "~/base/paper", "--runs", "1"]) == 0
    assert (tmp_path / "base" / "paper" / "manifest.json").is_file()


@pytest.mark.parametrize("limit, provider", [("ANTHROPIC_REQUEST_LIMIT", "Anthropic"), ("OPENAI_FILE_LIMIT", "OpenAI")])
def test_a_pdf_over_a_providers_size_limit_is_refused_before_any_call(baseline, monkeypatch, pdf, tmp_path, keys,
                                                                       capsys, limit, provider):
    log = _fake_calls(baseline, monkeypatch)
    monkeypatch.setattr(baseline, limit, 16)
    out = tmp_path / "out"
    assert _run(baseline, pdf, out) != 0
    err = capsys.readouterr().err
    assert provider in err and "MB" in err and err.count("\n") == 1
    assert log == [] and not out.exists()


def test_a_size_limit_applies_only_to_the_requested_model(baseline, monkeypatch, pdf, tmp_path, keys):
    _fake_calls(baseline, monkeypatch)
    monkeypatch.setattr(baseline, "OPENAI_FILE_LIMIT", 16)
    assert _run(baseline, pdf, tmp_path / "out", "--models", "claude-fable-5-1", "--runs", "1") == 0


def test_a_missing_key_is_named_before_anything_is_written(baseline, monkeypatch, pdf, tmp_path, keys, capsys):
    _fake_calls(baseline, monkeypatch)
    monkeypatch.delenv("OPENAI_API_KEY")
    out = tmp_path / "out"
    assert _run(baseline, pdf, out) != 0
    assert "OPENAI_API_KEY" in capsys.readouterr().err
    assert not out.exists()


def test_a_missing_key_for_an_unrequested_model_does_not_matter(baseline, monkeypatch, pdf, tmp_path, keys):
    _fake_calls(baseline, monkeypatch)
    monkeypatch.delenv("OPENAI_API_KEY")
    assert _run(baseline, pdf, tmp_path / "out", "--models", "claude-fable-5-1", "--runs", "1") == 0


def test_a_pdf_that_is_not_a_pdf_is_refused(baseline, monkeypatch, tmp_path, keys, capsys):
    _fake_calls(baseline, monkeypatch)
    p = tmp_path / "paper.pdf"
    p.write_bytes(b"not a pdf")
    assert _run(baseline, p, tmp_path / "out") != 0
    assert "PDF" in capsys.readouterr().err


# --- failure ---

def test_a_failed_call_exits_nonzero_and_names_the_run(baseline, monkeypatch, pdf, tmp_path, keys, capsys):
    log = _fake_calls(baseline, monkeypatch)
    good = baseline.call_openai
    attempts = []

    def flaky(pdf_bytes, filename, prompt):
        attempts.append(filename)
        if len(attempts) == 2:
            raise RuntimeError("503 from the fake server")
        return good(pdf_bytes, filename, prompt)

    monkeypatch.setattr(baseline, "call_openai", flaky)
    out = tmp_path / "out"
    assert _run(baseline, pdf, out) != 0
    err = capsys.readouterr().err
    assert "gpt-6-astra run-2" in err and "503 from the fake server" in err
    m = json.loads((out / "manifest.json").read_text())
    assert [(r["run"], r["status"]) for r in m["runs"] if r["model"] == "gpt-6-astra"] == [
        (1, "complete"), (2, "failed")]
    assert len(attempts) == 2 and len(log) == 1, "no silent retry and nothing after the failure"
    assert not (out / "gpt-6-astra" / "run-2" / "response.json").exists()


# --- what each SDK is asked to send ---

def test_openai_call_sends_the_pdf_and_prompt_with_store_off_and_nothing_else(baseline, monkeypatch, keys):
    sdk = _StubSDK(openai_response("found it")).install(monkeypatch, "openai")
    reply = baseline.call_openai(b"%PDF-1.4 body", "paper.pdf", "PROMPT")
    kw = sdk.call_kwargs
    assert kw["model"] == "gpt-6-astra" and kw["reasoning"] == {"effort": "high"} and kw["store"] is False
    assert set(kw) == {"model", "reasoning", "store", "input"}
    turn = kw["input"][0]
    assert turn["role"] == "user" and [c["type"] for c in turn["content"]] == ["input_file", "input_text"]
    assert turn["content"][0]["filename"] == "paper.pdf"
    assert turn["content"][0]["file_data"] == "data:application/pdf;base64,JVBERi0xLjQgYm9keQ=="
    assert turn["content"][1]["text"] == "PROMPT"
    assert sdk.client_kwargs["max_retries"] == 0
    assert reply["model"] == "gpt-6-astra-2026-09-01"


def test_anthropic_call_sends_the_pdf_and_prompt_with_effort_and_nothing_else(baseline, monkeypatch, keys):
    sdk = _StubSDK(anthropic_response("found it")).install(monkeypatch, "anthropic")
    reply = baseline.call_anthropic(b"%PDF-1.4 body", "paper.pdf", "PROMPT")
    kw = sdk.call_kwargs
    assert kw["model"] == "claude-fable-5-1" and kw["output_config"] == {"effort": "high"}
    assert set(kw) == {"model", "max_tokens", "output_config", "messages"}
    turn = kw["messages"][0]
    assert turn["role"] == "user" and [c["type"] for c in turn["content"]] == ["document", "text"]
    assert turn["content"][0]["source"] == {"type": "base64", "media_type": "application/pdf",
                                            "data": "JVBERi0xLjQgYm9keQ=="}
    assert turn["content"][1]["text"] == "PROMPT"
    assert sdk.client_kwargs["max_retries"] == 0
    assert reply["model"] == "claude-fable-5-1"


def test_request_json_records_that_openai_storage_is_off(baseline, monkeypatch, pdf, tmp_path, keys):
    _fake_calls(baseline, monkeypatch)
    out = tmp_path / "out"
    assert _run(baseline, pdf, out, "--runs", "1") == 0
    assert json.loads((out / "gpt-6-astra" / "run-1" / "request.json").read_text())["store"] is False
    assert json.loads((out / "claude-fable-5-1" / "run-1" / "request.json").read_text())["store"] is None


RETENTION = "The PDF is sent to OpenAI and Anthropic; Anthropic retains it for up to 30 days."


def test_help_and_readme_say_where_the_pdf_goes(tmp_path):
    env = dict(os.environ, HOME=str(tmp_path))
    r = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True,
                       cwd=str(tmp_path), env=env)
    assert RETENTION in " ".join(r.stdout.split())
    readme = (ROOT / "README.md").read_text(encoding="utf-8").split("## Evaluation", 1)[1]
    assert RETENTION in readme and "consent record" in readme


def test_the_anthropic_call_has_no_fallback_so_no_other_model_serves_a_run(baseline):
    src = SCRIPT.read_text(encoding="utf-8")
    assert "fallbacks=" not in src and "fallbacks" in src.split("def call_anthropic", 1)[1].split("def ", 1)[0]


# --- refusals and truncations stay archived but are loud ---

def _refusal_output(text):
    return [{"type": "message", "id": "msg_1", "role": "assistant", "status": "completed",
             "content": [{"type": "refusal", "refusal": text}]}]


def test_an_openai_refusal_part_is_archived_flagged_and_not_redone(baseline, monkeypatch, pdf, tmp_path, keys, capsys):
    log = _fake_calls(baseline, monkeypatch, openai_reply=openai_response(output=_refusal_output("I cannot review this.")))
    out = tmp_path / "out"
    assert _run(baseline, pdf, out, "--runs", "1", "--models", "gpt-6-astra") == 0
    err = capsys.readouterr().err
    assert "gpt-6-astra run-1" in err and "refusal" in err and "I cannot review this." in err
    m = json.loads((out / "manifest.json").read_text())
    assert m["runs"][0]["status"] == "complete (refusal)" and m["runs"][0]["finish"] == "refusal"
    assert m["runs"][0]["refusal"] == "I cannot review this."
    assert (out / "gpt-6-astra" / "run-1" / "done").is_file()
    assert _run(baseline, pdf, out, "--runs", "1", "--models", "gpt-6-astra") == 0 and len(log) == 1


def test_an_openai_incomplete_response_names_the_reason(baseline, monkeypatch, pdf, tmp_path, keys, capsys):
    _fake_calls(baseline, monkeypatch, openai_reply=openai_response(
        status="incomplete", incomplete_details={"reason": "max_output_tokens"}))
    out = tmp_path / "out"
    assert _run(baseline, pdf, out, "--runs", "1", "--models", "gpt-6-astra") == 0
    assert "max_output_tokens" in capsys.readouterr().err
    m = json.loads((out / "manifest.json").read_text())
    assert m["runs"][0]["status"] == "complete (incomplete: max_output_tokens)"


def test_an_openai_error_object_is_surfaced(baseline, monkeypatch, pdf, tmp_path, keys, capsys):
    _fake_calls(baseline, monkeypatch, openai_reply=openai_response(
        status="failed", error={"code": "server_error", "message": "upstream fell over"}))
    out = tmp_path / "out"
    assert _run(baseline, pdf, out, "--runs", "1", "--models", "gpt-6-astra") == 0
    assert "upstream fell over" in capsys.readouterr().err
    m = json.loads((out / "manifest.json").read_text())
    assert m["runs"][0]["status"] == "complete (failed: server_error)"


def test_an_anthropic_refusal_stop_reason_is_archived_and_flagged(baseline, monkeypatch, pdf, tmp_path, keys, capsys):
    log = _fake_calls(baseline, monkeypatch, anthropic_reply=anthropic_response(
        "", stop_reason="refusal", stop_details={"type": "refusal", "category": "cyber", "explanation": None}))
    out = tmp_path / "out"
    assert _run(baseline, pdf, out, "--runs", "1", "--models", "claude-fable-5-1") == 0
    err = capsys.readouterr().err
    assert "claude-fable-5-1 run-1" in err and "refusal: cyber" in err
    m = json.loads((out / "manifest.json").read_text())
    assert m["runs"][0]["status"] == "complete (refusal: cyber)" and m["runs"][0]["finish"] == "refusal: cyber"
    assert _run(baseline, pdf, out, "--runs", "1", "--models", "claude-fable-5-1") == 0 and len(log) == 1


def test_an_anthropic_max_tokens_stop_is_flagged(baseline, monkeypatch, pdf, tmp_path, keys, capsys):
    _fake_calls(baseline, monkeypatch, anthropic_reply=anthropic_response("cut off", stop_reason="max_tokens"))
    out = tmp_path / "out"
    assert _run(baseline, pdf, out, "--runs", "1", "--models", "claude-fable-5-1") == 0
    assert "max_tokens" in capsys.readouterr().err
    m = json.loads((out / "manifest.json").read_text())
    assert m["runs"][0]["status"] == "complete (max_tokens)"


def test_a_clean_run_writes_nothing_to_stderr(baseline, monkeypatch, pdf, tmp_path, keys, capsys):
    _fake_calls(baseline, monkeypatch)
    assert _run(baseline, pdf, tmp_path / "out", "--runs", "1") == 0
    assert capsys.readouterr().err == ""


# --- keys never reach disk; the SDKs load only when called ---

def test_no_key_string_appears_in_any_written_file(baseline, monkeypatch, pdf, tmp_path, keys):
    _fake_calls(baseline, monkeypatch)
    out = tmp_path / "out"
    assert _run(baseline, pdf, out) == 0
    for p in out.rglob("*"):
        if p.is_file():
            text = p.read_bytes()
            for key in keys.values():
                assert key.encode() not in text, p


def test_importing_the_script_does_not_import_either_sdk(tmp_path):
    code = ("import importlib.util, sys\n"
            f"spec = importlib.util.spec_from_file_location('baseline', {str(SCRIPT)!r})\n"
            "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
            "print('openai' in sys.modules, 'anthropic' in sys.modules)\n")
    env = dict(os.environ, HOME=str(tmp_path))
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=str(tmp_path), env=env)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "False False"


def test_cli_help_runs_from_a_subprocess(tmp_path):
    env = dict(os.environ, HOME=str(tmp_path))
    r = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True,
                       cwd=str(tmp_path), env=env)
    assert r.returncode == 0 and "--show-prompt-hash" in r.stdout and "--run-of-record" in r.stdout
