"""The model record: models.json next to usage.json, listing the exact model ids that ran, the
roles that used each, and the call counts, as the version record an evaluation can cite. Model ids
here are fake."""
from __future__ import annotations
import json
import os
import subprocess
import sys
from pathlib import Path

from plumb import audit, rundir, usage
from tests.test_usage import FAKE_PRICES, OPUS, SONNET, T, _one_session_run

ROOT = Path(__file__).resolve().parents[1]


def _row(model: str, calls: int) -> dict:
    return {"model": model, "input": 100, "output": 20, "cache_write": 0, "cache_read": 0, "seconds": 1.0,
            "cost_usd": 0.1, "cost_complete": True, "calls": calls}


def _usage_json(ws: Path, rows: list) -> None:
    rep = {"measured": True, "method": "", "price_table": {"as_of": "2000-01-01", "source": "Fake."},
           "sessions": 1, "agents": 2, "missing_transcripts": 0, "codex": None, "unpriced_models": [],
           "by_stage": [], "by_model": rows, "total": {k: v for k, v in _row("", 0).items() if k != "model"}}
    (ws / "usage.json").write_text(json.dumps(rep))


def _run_json(ws: Path, models) -> None:
    ws.mkdir(parents=True, exist_ok=True)
    run = {"pdf_path": "/fake/fakepaper.pdf", "depth": "standard", "started": "2026-09-26"}
    if models is not None:
        run["models"] = models
    (ws / "run.json").write_text(json.dumps(run))


def test_report_counts_calls_by_model(tmp_path):
    rep = usage.report(_one_session_run(tmp_path), now=T("10:30:00"), prices=FAKE_PRICES)
    models = {r["model"]: r for r in rep["by_model"]}
    assert models[OPUS]["calls"] == 3 and models[SONNET]["calls"] == 1


def test_record_from_usage_names_ids_roles_and_calls(tmp_path):
    _run_json(tmp_path, {"mechanical": "fakesonnet", "judgment": "fakeopus"})
    _usage_json(tmp_path, [_row(OPUS, 12), _row(SONNET, 30)])
    rec = usage.model_record(tmp_path)
    assert rec["observed"] is True and rec["source"] == "usage.json"
    assert rec["configured"] == {"mechanical": "fakesonnet", "judgment": "fakeopus"}
    assert rec["models"] == [{"id": OPUS, "roles": ["judgment"], "calls": 12},
                             {"id": SONNET, "roles": ["mechanical"], "calls": 30}]
    assert rec["unresolved_roles"] == []


def test_record_matches_a_full_id_in_the_settings_and_leaves_an_unknown_model_without_a_role(tmp_path):
    _run_json(tmp_path, {"mechanical": OPUS, "judgment": OPUS})
    _usage_json(tmp_path, [_row(OPUS, 5), _row("claude-fakehaiku-1", 2)])
    rec = usage.model_record(tmp_path)
    assert rec["models"][0] == {"id": OPUS, "roles": ["mechanical", "judgment"], "calls": 5}
    assert rec["models"][1] == {"id": "claude-fakehaiku-1", "roles": [], "calls": 2}


def test_record_assigns_inherit_roles_when_one_model_ran(tmp_path):
    _run_json(tmp_path, {"mechanical": "inherit", "judgment": "inherit"})
    _usage_json(tmp_path, [_row(OPUS, 7), _row(usage.CODEX_MODEL, 0)])
    rec = usage.model_record(tmp_path)
    assert rec["models"][0] == {"id": OPUS, "roles": ["mechanical", "judgment"], "calls": 7}
    assert rec["models"][1] == {"id": usage.CODEX_MODEL, "roles": ["stress_test"], "calls": None}
    assert rec["unresolved_roles"] == []


def test_record_leaves_inherit_roles_unresolved_when_several_models_ran(tmp_path):
    _run_json(tmp_path, {"mechanical": "inherit", "judgment": "inherit"})
    _usage_json(tmp_path, [_row(OPUS, 7), _row(SONNET, 2)])
    rec = usage.model_record(tmp_path)
    assert [m["roles"] for m in rec["models"]] == [[], []]
    assert rec["unresolved_roles"] == ["mechanical", "judgment"]
    assert rec["candidates"] == {"mechanical": [OPUS, SONNET], "judgment": [OPUS, SONNET]}


def test_record_without_usage_lists_the_aliases_and_says_they_are_not_observed(tmp_path):
    _run_json(tmp_path, {"mechanical": "fakesonnet", "judgment": "fakeopus"})
    rec = usage.model_record(tmp_path)
    assert rec["observed"] is False and rec["source"] == "run.json"
    assert rec["models"] == [{"id": "fakeopus", "roles": ["judgment"], "calls": None},
                             {"id": "fakesonnet", "roles": ["mechanical"], "calls": None}]
    assert "aliases" in rec["note"] and "not observed ids" in rec["note"] and "not measured" in rec["note"]
    usage.write_report(tmp_path)  # a not-measured report (the chat tab) gives the same answer
    assert usage.model_record(tmp_path)["observed"] is False
    _run_json(tmp_path, None)
    bare = usage.model_record(tmp_path)
    assert bare["models"] == [] and bare["observed"] is False and "not recorded" in bare["note"]


def test_write_model_record_and_the_usage_report_cli_write_models_json(tmp_path):
    _run_json(tmp_path, {"mechanical": "fakesonnet", "judgment": "fakeopus"})
    _usage_json(tmp_path, [_row(OPUS, 12)])
    assert usage.write_model_record(tmp_path)["models"][0]["id"] == OPUS
    assert json.loads((tmp_path / usage.MODELS).read_text())["observed"] is True
    (tmp_path / "models.json").unlink()
    env = dict(os.environ, PYTHONPATH=str(ROOT), HOME=str(tmp_path), PLUMB_CONFIG=str(tmp_path / "none.json"))
    r = subprocess.run([sys.executable, "-m", "plumb", "usage", "report", str(tmp_path)],
                       capture_output=True, text=True, env=env, cwd=ROOT)
    assert r.returncode == 0
    rec = json.loads((tmp_path / "models.json").read_text())
    assert rec["observed"] is False and rec["models"][0]["id"] == "fakeopus"


def test_audit_package_has_a_models_line(tmp_path):
    _run_json(tmp_path, {"mechanical": "fakesonnet", "judgment": "fakeopus"})
    _usage_json(tmp_path, [_row(OPUS, 12), _row(SONNET, 30)])
    audit.log_event(tmp_path, "model", role="judgment", name="fakeopus")
    text = audit.render_package(tmp_path).read_text()
    section = text[text.index("## Models and settings"):text.index("## Dependencies and warnings")]
    assert (f"- Models that ran (ids observed in the transcripts): {OPUS}: judgment, 12 calls; {SONNET}: mechanical, "
            "30 calls. Call counts are per id over every transcript, the main session included. The work each did "
            "was configured by name, mostly by tier alias; the same settings can resolve to a different id on "
            "another day.") in section
    assert "pinned" not in section
    (tmp_path / "usage.json").unlink()
    text = audit.render_package(tmp_path).read_text()
    assert ("- Models: fakeopus: judgment; fakesonnet: mechanical. These are the configured names from the run's "
            "settings, mostly tier aliases, not observed ids; usage was not measured in this app, so the ids that "
            "ran are not recorded.") in text
    assert "\u2014" not in text


def test_readme_lists_the_model_record(tmp_path):
    ws = tmp_path / "plumb_output" / "2026-09-26" / ".workspace"
    _run_json(ws, {"mechanical": "fakesonnet", "judgment": "fakeopus"})
    assert "models.json" not in rundir.write_readme(ws).read_text()
    usage.write_model_record(ws)
    text = rundir.write_readme(ws).read_text()
    assert "- `.workspace/models.json`: Model record: the exact model ids that ran" in text


def test_stage_7_readme_and_spec_name_the_model_record():
    seven = " ".join((ROOT / "skills/review/stages/stage-7-output.md").read_text(encoding="utf-8").split())
    step = seven[seven.index("7. Finish the run folder"):seven.index("8. Ask:")]
    assert "`{WORKSPACE}/models.json`" in step and "exact model ids" in step and "aliases" in step
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "`.workspace/models.json`" in readme and "exact model ids" in readme
    spec = (ROOT / "docs/spec.md").read_text(encoding="utf-8")
    ten = spec[spec.index("## 10. Audit package"):spec.index("## 11.")]
    assert "models.json" in ten and "exact model ids" in ten


# Review fixes: an alias that matches two ids of one family is ambiguous; a measured run with no
# model rows is not "not measured"; call counts are per id over every transcript.

def test_an_alias_matching_two_ids_of_one_family_leaves_the_role_unresolved_with_both_candidates(tmp_path):
    _run_json(tmp_path, {"mechanical": "fakesonnet", "judgment": "fakeopus"})
    _usage_json(tmp_path, [_row("claude-fakeopus-1", 4), _row("claude-fakeopus-2", 9), _row(SONNET, 3)])
    rec = usage.model_record(tmp_path)
    assert rec["unresolved_roles"] == ["judgment"]
    assert rec["candidates"] == {"judgment": ["claude-fakeopus-1", "claude-fakeopus-2"]}
    assert [m["roles"] for m in rec["models"]] == [[], [], ["mechanical"]]
    assert "more than one id" in rec["note"] and "candidates" in rec["note"]
    line = usage.render_models(rec)
    assert "judgment: claude-fakeopus-1 or claude-fakeopus-2" in line
    assert "configured inherit" not in line


def test_inherit_with_several_models_is_unresolved_with_every_id_as_a_candidate(tmp_path):
    _run_json(tmp_path, {"mechanical": "inherit", "judgment": "inherit"})
    _usage_json(tmp_path, [_row(OPUS, 7), _row(SONNET, 2), _row(usage.CODEX_MODEL, 0)])
    rec = usage.model_record(tmp_path)
    assert rec["unresolved_roles"] == ["mechanical", "judgment"]
    assert rec["candidates"] == {"mechanical": [OPUS, SONNET], "judgment": [OPUS, SONNET]}
    assert rec["models"][2]["roles"] == ["stress_test"]
    assert "candidates" in usage.render_models(rec) or f"mechanical: {OPUS} or {SONNET}" in usage.render_models(rec)


def test_resolved_roles_have_no_candidates_entry(tmp_path):
    _run_json(tmp_path, {"mechanical": "fakesonnet", "judgment": "fakeopus"})
    _usage_json(tmp_path, [_row(OPUS, 12), _row(SONNET, 30)])
    rec = usage.model_record(tmp_path)
    assert rec["candidates"] == {} and rec["unresolved_roles"] == []


def test_a_measured_run_with_no_model_rows_does_not_say_usage_was_not_measured(tmp_path):
    _run_json(tmp_path, {"mechanical": "fakesonnet", "judgment": "fakeopus"})
    _usage_json(tmp_path, [])
    rec = usage.model_record(tmp_path)
    assert rec["source"] == "run.json" and rec["models"][0]["id"] == "fakeopus"
    assert "not measured" not in rec["note"] and "no transcript" in rec["note"]
    assert "not measured" not in usage.render_models(rec) and "no transcript" in usage.render_models(rec)
    (tmp_path / "usage.json").unlink()
    assert "not measured" in usage.model_record(tmp_path)["note"]


def test_call_counts_are_per_id_over_every_transcript(tmp_path):
    _run_json(tmp_path, {"mechanical": "fakesonnet", "judgment": "fakeopus"})
    _usage_json(tmp_path, [_row(OPUS, 12)])
    rec = usage.model_record(tmp_path)
    for text in (rec["note"], usage.render_models(rec)):
        assert "every transcript" in text and "main session" in text


def test_readme_and_spec_say_observed_not_pinned():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "observed in the transcripts" in readme and "pinned" not in readme
    spec = (ROOT / "docs/spec.md").read_text(encoding="utf-8")
    assert "the model versions reported are the observed ids in `models.json`" in spec
    assert "the pinned model versions are the ids in `models.json`" not in spec
    ten = spec[spec.index("## 10. Audit package"):spec.index("## 11.")]
    assert "observed" in ten and "unpinned" not in ten
