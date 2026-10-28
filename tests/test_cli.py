from __future__ import annotations
import json, os, re, subprocess, sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

def run(*args):
    return subprocess.run([sys.executable, "-m", "plumb", *args], capture_output=True, text=True, cwd=ROOT)

def test_sha256(tmp_path):
    import hashlib
    f = tmp_path / "x.txt"
    f.write_bytes(b"fake")
    r = run("sha256", str(f))
    assert r.returncode == 0 and r.stdout.strip() == hashlib.sha256(b"fake").hexdigest()


def test_stops():
    r = run("stops", "light", "standard")
    assert r.returncode == 0 and json.loads(r.stdout) == ["setup", "majors", "draft"]

def test_limits_cli():
    r = run("limits", "deep")
    assert r.returncode == 0 and json.loads(r.stdout)["revisions"] == 4

def test_limits_cli_maps_full_to_deep():
    assert json.loads(run("limits", "full").stdout)["depth"] == "deep"

def test_limits_cli_bad_depth_exit_1():
    r = run("limits", "huge")
    assert r.returncode == 1 and "depth must be one of" in r.stdout

def test_stops_accepts_full_alias():
    assert json.loads(run("stops", "standard", "full").stdout) == json.loads(run("stops", "standard", "deep").stdout)

def test_referee_blocked_exit_code():
    r = run("referee-decision", "profiles", "smj", "report")
    assert r.returncode == 3 and json.loads(r.stdout)["allowed"] is False

def test_consent_failure_exit_code(tmp_path):
    rec = tmp_path / "c.json"
    rec.write_text(json.dumps({"role": "author", "provider": "x", "provider_trains_on_inputs": None,
                               "retention_days": 30, "egress": ["manuscript_text"]}))
    r = run("consent-check", str(rec), str(tmp_path / "ws"))
    assert r.returncode == 1 and "coauthors" in r.stdout

def test_consent_success_logs_event(tmp_path):
    rec = tmp_path / "c.json"
    rec.write_text(json.dumps({"role": "author", "provider": "x", "provider_trains_on_inputs": False,
                               "retention_days": 30, "egress": ["manuscript_text", "search_queries"],
                               "coauthors_agree": True}))
    r = run("consent-check", str(rec), str(tmp_path / "ws"))
    assert r.returncode == 0
    assert "consent" in (tmp_path / "ws" / "audit" / "events.jsonl").read_text()

def test_consent_check_accepts_the_authors_permission(tmp_path):
    rec = tmp_path / "c.json"
    rec.write_text(json.dumps({"role": "author", "permission": "author_asked", "author_permission": True,
                               "provider": "x", "provider_trains_on_inputs": False, "retention_days": 30,
                               "egress": ["manuscript_text", "search_queries"]}))
    r = run("consent-check", str(rec), str(tmp_path / "ws"))
    assert r.returncode == 0, r.stdout
    events = [json.loads(l) for l in (tmp_path / "ws" / "audit" / "events.jsonl").read_text().splitlines()]
    logged = next(e for e in events if e["kind"] == "consent")
    assert logged["permission"] == "author_asked" and logged["author_permission"] is True


def test_consent_egress_events_render_under_what_left_this_machine(tmp_path):
    (tmp_path / "ws").mkdir()
    rec = tmp_path / "ws" / "consent.json"
    rec.write_text(json.dumps({"role": "author", "provider": "x", "provider_trains_on_inputs": False,
                               "retention_days": 30, "egress": ["manuscript_text", "search_queries"],
                               "coauthors_agree": True}))
    assert run("consent-check", str(rec), str(tmp_path / "ws")).returncode == 0
    assert run("egress", str(tmp_path / "ws")).returncode == 0
    assert run("render-audit", str(tmp_path / "ws")).returncode == 0
    pkg = (tmp_path / "ws" / "audit_package.md").read_text()
    section = pkg.split("## What left this machine", 1)[1].split("\n## ", 1)[0]
    assert "item: manuscript_text" in section and "item: search_queries" in section
    assert "to: x" in section
    assert "OpenAlex, Crossref, and Semantic Scholar" in section
    assert "None recorded." not in section

def test_consent_check_rejects_undeclared_egress(tmp_path):
    rec = tmp_path / "c.json"
    rec.write_text(json.dumps({"role": "author", "provider": "x", "provider_trains_on_inputs": False,
                               "retention_days": 30, "egress": [], "coauthors_agree": True}))
    r = run("consent-check", str(rec), str(tmp_path / "ws"))
    assert r.returncode == 1 and "manuscript_text" in r.stdout and "search_queries" in r.stdout

def test_validate_packs():
    assert run("validate-packs", "packs").returncode == 0

def test_validate_output(tmp_path):
    f = tmp_path / "r.txt"; f.write_text("1. Only comment. Text.\n\nReject\n")
    r = run("validate-output", "report", str(f))
    assert r.returncode == 1 and "recommendation" in r.stdout

def test_consent_check_malformed_types_exit_1(tmp_path):
    rec = tmp_path / "c.json"
    rec.write_text(json.dumps({"role": "author", "provider": "x", "provider_trains_on_inputs": "no",
                               "retention_days": "thirty", "egress": ["manuscript_text"]}))
    r = run("consent-check", str(rec), str(tmp_path / "ws"))
    assert r.returncode == 1
    assert "provider_trains_on_inputs" in r.stdout

def test_referee_decision_bad_journal_id_exit_3(tmp_path):
    r = run("referee-decision", "profiles", "../x", "report")
    assert r.returncode == 3
    assert "journal id" in r.stdout

def test_validate_packs_broken_pack_dir_exit_1(tmp_path):
    broken = tmp_path / "packs" / "broken"
    broken.mkdir(parents=True)
    (broken / "pack.yaml").write_text("name: broken\n")
    r = run("validate-packs", str(tmp_path / "packs"))
    assert r.returncode == 1
    assert "pack.yaml" in r.stdout


def test_answered_labels_prints_chosen_label(tmp_path):
    ws = tmp_path / "ws"
    assert run("checkin", str(ws), "minors", "minors:2", "Keep", "Drop").returncode == 0
    r = run("answered", str(ws), "--labels")
    assert r.returncode == 0 and json.loads(r.stdout) == {"minors:2": "Drop"}
    assert json.loads(run("answered", str(ws)).stdout) == [["minors", "minors:2"]]


def test_consent_check_applies_journal_author_consent_rule(tmp_path):
    pdir = tmp_path / "profiles"; pdir.mkdir()
    (pdir / "j.yaml").write_text("id: j\nname: J\nupload: allowed\ndrafting: allowed\n"
                                 "requires_zero_retention: false\nrequires_author_consent: true\n")
    rec = tmp_path / "c.json"
    rec.write_text(json.dumps({"role": "referee", "provider": "x", "provider_trains_on_inputs": False,
                               "retention_days": 0, "egress": ["manuscript_text", "search_queries"],
                               "journal_allows": True, "author_consented_at_submission": None,
                               "zero_retention_confirmed": True}))
    r = run("consent-check", str(rec), str(tmp_path / "ws"), "--profiles", str(pdir), "--journal", "j")
    assert r.returncode == 1 and "requires the author's consent" in r.stdout
    r = run("consent-check", str(rec), str(tmp_path / "ws2"), "--profiles", "profiles", "--journal", "orgsci")
    assert r.returncode == 0, r.stdout


def test_consent_check_author_with_unlisted_journal_passes(tmp_path):
    rec = tmp_path / "c.json"
    rec.write_text(json.dumps({"role": "author", "provider": "x", "provider_trains_on_inputs": False,
                               "retention_days": 30, "egress": ["manuscript_text", "search_queries"],
                               "coauthors_agree": True}))
    r = run("consent-check", str(rec), str(tmp_path / "ws"), "--profiles", "profiles", "--journal", "Other")
    assert r.returncode == 0, r.stdout


def _referee_record(tmp_path, **extra):
    d = {"role": "referee", "provider": "x", "provider_trains_on_inputs": False, "retention_days": 0,
         "egress": ["manuscript_text", "search_queries"], "journal_allows": True}
    d.update(extra)
    rec = tmp_path / "c.json"
    rec.write_text(json.dumps(d))
    return rec


def _open_journal(tmp_path):
    """A made-up journal that allows uploads and needs no zero retention, for the flag's own tests."""
    pdir = tmp_path / "open_profiles"
    pdir.mkdir(exist_ok=True)
    (pdir / "openj.yaml").write_text("id: openj\nname: Open J\nupload: allowed\ndrafting: allowed\n"
                                     "requires_zero_retention: false\n")
    return ["--profiles", str(pdir), "--journal", "openj"]

def test_consent_check_needs_zero_retention_blocks_unconfirmed(tmp_path):
    rec = _referee_record(tmp_path)
    r = run("consent-check", str(rec), str(tmp_path / "ws"), "--needs-zero-retention", *_open_journal(tmp_path))
    assert r.returncode == 1 and "zero data retention" in r.stdout

def test_consent_check_needs_zero_retention_passes_when_confirmed(tmp_path):
    rec = _referee_record(tmp_path, zero_retention_confirmed=True)
    r = run("consent-check", str(rec), str(tmp_path / "ws"), "--needs-zero-retention", *_open_journal(tmp_path))
    assert r.returncode == 0, r.stdout
    assert '"zero_retention_confirmed": true' in (tmp_path / "ws" / "audit" / "events.jsonl").read_text()

def test_consent_check_without_flag_ignores_zero_retention(tmp_path):
    rec = _referee_record(tmp_path)
    assert run("consent-check", str(rec), str(tmp_path / "ws"), *_open_journal(tmp_path)).returncode == 0

def test_consent_check_no_log_checks_without_logging(tmp_path):
    rec = _referee_record(tmp_path)
    ws = tmp_path / "ws"
    r = run("consent-check", str(rec), str(ws), "--no-log", *_open_journal(tmp_path))
    assert r.returncode == 0 and "OK" in r.stdout
    assert not (ws / "audit" / "events.jsonl").exists()
    bad = _referee_record(tmp_path)
    r = run("consent-check", str(bad), str(ws), "--no-log", "--needs-zero-retention", *_open_journal(tmp_path))
    assert r.returncode == 1 and "zero data retention" in r.stdout


def _run_with_config(tmp_path, cfg: dict, *args):
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg))
    env = dict(os.environ, PLUMB_CONFIG=str(p))
    return subprocess.run([sys.executable, "-m", "plumb", *args],
                          capture_output=True, text=True, cwd=ROOT, env=env)


def test_models_cli_reads_config_and_applies_depth(tmp_path):
    cfg = {"models": {"mechanical": "mid", "judgment": "top"}}
    r = _run_with_config(tmp_path, cfg, "models", "standard")
    assert r.returncode == 0 and json.loads(r.stdout) == {"mechanical": "mid", "judgment": "top"}
    r = _run_with_config(tmp_path, cfg, "models", "deep")
    assert json.loads(r.stdout) == {"mechanical": "top", "judgment": "top"}


def test_models_cli_bad_config_exit_1(tmp_path):
    r = _run_with_config(tmp_path, {"models": {"judgment": 3}}, "models", "deep")
    assert r.returncode == 1 and "models" in r.stdout


def test_counts_cli(tmp_path):
    ws = tmp_path / "ws"
    assert run("log", str(ws), "dig_deeper", '{"item":"majors:1","text":"x"}').returncode == 0
    r = run("counts", str(ws))
    assert r.returncode == 0 and json.loads(r.stdout)["dig_deeper"] == 1


def test_referee_decision_self_confirmed_unlisted(tmp_path):
    r = run("referee-decision", "profiles", "generic", "report", "--self-confirmed")
    d = json.loads(r.stdout)
    assert r.returncode == 0 and d["allowed"] and d["outputs"] == ["report"] and d["needs_zero_retention"]
    assert run("referee-decision", "profiles", "generic", "report").returncode == 3


def test_referee_decision_takes_a_set_of_outputs():
    r = run("referee-decision", "profiles", "mansci", "report,annotated_pdf")
    d = json.loads(r.stdout)
    assert r.returncode == 0 and d["outputs"] == ["annotated_pdf", "report"] and d["issues_list_mode"] == "full"


def test_referee_decision_bad_outputs_exit_1():
    r = run("referee-decision", "profiles", "orgsci", "fix_list")
    assert r.returncode == 1 and "requested outputs must be" in r.stdout


def test_referee_decision_quick_depth_is_facts_only():
    r = run("referee-decision", "profiles", "orgsci", "issues_list,report", "--depth", "quick")
    d = json.loads(r.stdout)
    assert r.returncode == 0 and d["outputs"] == ["issues_list"] and d["issues_list_mode"] == "facts_only"


def test_referee_decision_self_confirmed_banned_still_exit_3():
    assert run("referee-decision", "profiles", "smj", "report", "--self-confirmed").returncode == 3


def test_consent_check_unlisted_journal_requires_self_confirmation(tmp_path):
    rec = _referee_record(tmp_path, zero_retention_confirmed=True)
    r = run("consent-check", str(rec), str(tmp_path / "ws"), "--profiles", "profiles", "--journal", "generic",
            "--needs-zero-retention")
    assert r.returncode == 1 and "not recorded" in r.stdout
    rec = _referee_record(tmp_path, zero_retention_confirmed=True, journal_allows_self_confirmed=True)
    ws = tmp_path / "ws2"
    r = run("consent-check", str(rec), str(ws), "--profiles", "profiles", "--journal", "generic",
            "--needs-zero-retention")
    assert r.returncode == 0, r.stdout
    assert run("render-audit", str(ws)).returncode == 0
    section = (ws / "audit_package.md").read_text().split("## Consent record", 1)[1].split("\n## ", 1)[0]
    assert "journal_allows_self_confirmed: True" in section


def test_consent_check_defers_the_openai_egress_event(tmp_path):
    rec = tmp_path / "c.json"
    rec.write_text(json.dumps({"role": "author", "provider": "x", "provider_trains_on_inputs": False,
                               "retention_days": 30, "coauthors_agree": True,
                               "egress": ["manuscript_text", "search_queries", "codex_stress_test"],
                               "stress_test_provider": {"provider": "OpenAI", "trains_on_inputs": False,
                                                        "retention_days": 30, "zero_retention_confirmed": None}}))
    ws = tmp_path / "ws"
    assert run("consent-check", str(rec), str(ws)).returncode == 0
    (ws / "consent.json").write_text(rec.read_text())
    assert run("egress", str(ws)).returncode == 0
    egress = [json.loads(l)["item"] for l in (ws / "audit" / "events.jsonl").read_text().splitlines()
              if json.loads(l)["kind"] == "egress"]
    assert egress == ["manuscript_text", "search_queries"]


def _stress_ws(tmp_path, depth_name, with_openai, journal=""):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "run.json").write_text(json.dumps({"depth": depth_name, "needs_zero_retention": False,
                                             "journal": journal}))
    rec = {"role": "author", "provider": "x", "provider_trains_on_inputs": False, "retention_days": 30,
           "coauthors_agree": True, "egress": ["manuscript_text", "search_queries"]}
    if journal:
        rec = {"role": "referee", "provider": "x", "provider_trains_on_inputs": False, "retention_days": 0,
               "journal_allows": True, "zero_retention_confirmed": True,
               "egress": ["manuscript_text", "search_queries"]}
    if with_openai:
        rec["egress"].append("codex_stress_test")
        rec["stress_test_provider"] = {"provider": "OpenAI", "trains_on_inputs": False,
                                       "retention_days": 30, "zero_retention_confirmed": None}
    (ws / "consent.json").write_text(json.dumps(rec))
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"codex_enabled": True}))
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "codex").write_text("#!/bin/sh\nexit 0\n")
    (bindir / "codex").chmod(0o755)
    env = dict(os.environ, PLUMB_CONFIG=str(cfg), PATH=f"{bindir}{os.pathsep}{os.environ['PATH']}")
    r = subprocess.run([sys.executable, "-m", "plumb", "stress-test-decision", str(ws)],
                       capture_output=True, text=True, cwd=ROOT, env=env)
    events = ws / "audit" / "events.jsonl"
    return r, (events.read_text() if events.exists() else "")


@pytest.mark.parametrize("depth_name", ["standard", "deep"])
def test_stress_test_decision_falls_back_to_claude_without_openai_consent(tmp_path, depth_name):
    r, events = _stress_ws(tmp_path, depth_name, with_openai=False)
    out = json.loads(r.stdout)
    assert r.returncode == 0 and out["run"] is True and out["engine"] == "claude" and "OpenAI" in out["reason"]
    # The user never declared the Codex stress test, so there is nothing to warn about (wave C6).
    assert events == ""


def test_stress_test_decision_warns_when_a_declared_codex_test_cannot_run(tmp_path):
    r, events = _stress_ws(tmp_path, "standard", with_openai=True, journal="orgsci")
    assert json.loads(r.stdout)["engine"] == "claude"
    assert '"name": "codex_stress_test"' in events and '"kind": "dependency"' in events
    assert "A Claude agent runs the stress test instead." in events


@pytest.mark.parametrize("depth_name", ["standard", "deep"])
def test_stress_test_decision_uses_codex_when_covered(tmp_path, depth_name):
    r, events = _stress_ws(tmp_path, depth_name, with_openai=True)
    assert json.loads(r.stdout) == {"run": True, "engine": "codex", "reason": ""} and events == ""


def test_stress_test_decision_silent_at_quick(tmp_path):
    r, events = _stress_ws(tmp_path, "quick", with_openai=True)
    assert json.loads(r.stdout) == {"run": False, "engine": "", "reason": "Quick depth has no stress test."}
    assert events == ""


def test_stress_test_decision_logs_nothing_when_codex_is_not_enabled(tmp_path):
    ws = _old_run_ws(tmp_path, {"depth": "standard"})
    r = _run_with_config(tmp_path, {}, "stress-test-decision", str(ws))
    assert json.loads(r.stdout)["engine"] == "claude"
    assert not (ws / "audit" / "events.jsonl").exists()


def test_counts_cli_reviewer_case(tmp_path):
    ws = str(tmp_path / "ws")
    rec_m = "A. Keep it as a major issue (Recommended) | S."
    run("checkin", ws, "majors", "majors:1", rec_m, "D. Dig deeper before deciding | S.")
    run("checkin", ws, "majors", "majors:1", rec_m, "A. Keep it as a major issue | S.")
    rec_a = "A. Plausible, investigate further (Recommended) | D."
    ans_a = "B. Plausible, but the paper handles it (give the page) | D."
    run("checkin", ws, "against", "against:2", rec_a, ans_a)
    run("checkin", ws, "against", "against:2", rec_a, ans_a, "--note", "p.4: handled")
    c = json.loads(run("counts", ws).stdout)
    assert c["override"] == 1 and c["user_answers"] == 2


def _old_run_ws(tmp_path, run_cfg, depth_answer=None):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "run.json").write_text(json.dumps(run_cfg))
    if depth_answer:
        run("checkin", str(ws), "setup", "setup:depth", "A. Standard (Recommended)", depth_answer)
    return ws


@pytest.mark.parametrize("run_cfg, answer, engine", [
    ({"tier": "full"}, None, "claude"),
    ({"depth": "full"}, None, "claude"),
    ({}, "C. Full", "claude"),
    ({}, None, "claude"),
    ({"tier": "quick"}, None, ""),
    ({}, "B. Quick", ""),
])
def test_stress_test_decision_reads_old_run_files(tmp_path, run_cfg, answer, engine):
    ws = _old_run_ws(tmp_path, run_cfg, answer)
    r = _run_with_config(tmp_path, {}, "stress-test-decision", str(ws))
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["engine"] == engine and out["run"] is bool(engine)


def test_stress_test_decision_bad_depth_is_a_message(tmp_path):
    ws = _old_run_ws(tmp_path, {"depth": "huge"})
    r = _run_with_config(tmp_path, {}, "stress-test-decision", str(ws))
    assert r.returncode == 1 and "depth must be one of" in r.stdout and "Traceback" not in r.stderr


def test_models_cli_codex_platform(tmp_path):
    r = _run_with_config(tmp_path, {"models": {"mechanical": "sonnet", "judgment": "opus"}},
                         "models", "standard", "--platform", "codex")
    assert r.returncode == 0 and json.loads(r.stdout) == {"mechanical": "inherit", "judgment": "inherit"}

def test_validate_packs_reports_packs_and_overlays():
    r = run("validate-packs", "packs")
    out = json.loads(r.stdout)
    assert r.returncode == 0 and "archival" in out["packs"] and isinstance(out["overlays"], list)

def test_run_packs_cli(tmp_path):
    root = tmp_path / "packs"
    for name, extra in (("archival", ""), ("computational", "overlay: true\n")):
        d = root / name
        (d / "agents").mkdir(parents=True); (d / "checklists").mkdir(); (d / "fixtures" / "f").mkdir(parents=True)
        (d / "agents" / "a.md").write_text("x")
        (d / "pack.yaml").write_text(f"name: {name}\n{extra}detection_cues: [x]\nslots: {{diagnose: [a.md]}}\n")
        (d / "checklists" / "c.yaml").write_text("- {id: c1, text: t, adjudication: paper}\n")
        (d / "fixtures" / "f" / "expected.yaml").write_text("status: pending_planting\n")
    r = run("run-packs", str(root), "--type", "archival", "--second-type", "none", "--overlay", "computational")
    assert r.returncode == 0
    assert json.loads(r.stdout) == {"packs": ["archival", "computational"], "overlays": ["computational"],
                                    "types_without_pack": [], "primary_pack": "archival"}
    bad = run("run-packs", str(root), "--type", "archival", "--overlay", "archival")
    assert bad.returncode == 1 and "overlay" in bad.stdout


def test_validate_packs_lists_design_modules(tmp_path):
    d = tmp_path / "packs" / "archival"
    (d / "agents").mkdir(parents=True); (d / "checklists").mkdir(); (d / "modules").mkdir()
    (d / "agents" / "a.md").write_text("x")
    (d / "pack.yaml").write_text("name: archival\ndetection_cues: [x]\nslots: {diagnose: [a.md]}\n")
    (d / "checklists" / "c.yaml").write_text("- {id: c1, text: t, adjudication: paper}\n")
    (d / "modules" / "did.yaml").write_text(
        "name: did\nlabel: DiD\ndefinition: \"Before and after.\"\ndetection_cues: [parallel trends]\n"
        "checklist:\n  - {id: DD1, text: t, adjudication: paper}\n")
    (d / "modules" / "did.md").write_text("# DiD\n")
    for sub, extra in (("planted-1", ""), ("did-1", "module: did\n")):
        (d / "fixtures" / sub).mkdir(parents=True)
        (d / "fixtures" / sub / "expected.yaml").write_text(f"status: pending_planting\n{extra}")
    r = run("validate-packs", str(tmp_path / "packs"))
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["modules"] == {"archival": [{"name": "did", "label": "DiD", "definition": "Before and after.",
                                            "cues": ["parallel trends"]}]}
    assert out["packs"] == {"archival": "pending_planting"} and out["overlays"] == []


def _subcommand_help(*args):
    """Map each subcommand listed by `--help` to whether it has a help line."""
    out = run(*args, "--help").stdout
    names = re.search(r"\{([^}]+)\}", out).group(1).split(",")
    return {n: bool(re.search(rf"^\s{{4}}{re.escape(n)}\s+\S", out, re.M)) for n in names}


def test_every_subcommand_has_a_help_line():
    for args in ((), ("run-dir",), ("usage",)):
        missing = [n for n, ok in _subcommand_help(*args).items() if not ok]
        assert not missing, (args, missing)


def test_referee_decision_help_names_the_memo():
    assert "editor_memo" in run("referee-decision", "--help").stdout
    assert "editor_memo" in run("filter-outputs", "--help").stdout


# consent-check derives a referee's rules from the journal profile (Plan 1e wave C1).

def test_consent_check_needs_the_journal_for_a_referee_record(tmp_path):
    rec = _referee_record(tmp_path, zero_retention_confirmed=True)
    r = run("consent-check", str(rec), str(tmp_path / "ws"))
    assert r.returncode == 1 and "--journal" in r.stdout
    assert not (tmp_path / "ws" / "audit" / "events.jsonl").exists()


def test_consent_check_refuses_a_referee_at_a_journal_that_bans_uploads(tmp_path):
    rec = _referee_record(tmp_path, zero_retention_confirmed=True)
    r = run("consent-check", str(rec), str(tmp_path / "ws"), "--profiles", "profiles", "--journal", "smj")
    assert r.returncode == 1 and "bans uploading" in r.stdout


def _referee_record_without_journal_answer(tmp_path, **extra):
    d = {"role": "referee", "provider": "x", "provider_trains_on_inputs": False, "retention_days": 0,
         "egress": ["manuscript_text", "search_queries"], "zero_retention_confirmed": True}
    d.update(extra)
    rec = tmp_path / "c.json"
    rec.write_text(json.dumps(d))
    return rec


@pytest.mark.parametrize("journal", ["orgsci", "mansci"])
def test_consent_check_takes_journal_allows_from_a_profile_that_allows_upload(tmp_path, journal):
    # Stage 0 sets journal_allows only for a self-confirmed unlisted journal, so a referee at a
    # listed journal whose profile allows upload reaches the gate with it unset.
    rec = _referee_record_without_journal_answer(tmp_path)
    ws = tmp_path / "ws"
    r = run("consent-check", str(rec), str(ws), "--profiles", "profiles", "--journal", journal)
    assert r.returncode == 0, r.stdout
    logged = [json.loads(l) for l in (ws / "audit" / "events.jsonl").read_text().splitlines()]
    consent_event = [e for e in logged if e["kind"] == "consent"][-1]
    assert consent_event["journal_allows"] is True


def test_consent_check_profile_never_overrides_a_no(tmp_path):
    rec = _referee_record_without_journal_answer(tmp_path, journal_allows=False)
    r = run("consent-check", str(rec), str(tmp_path / "ws"), "--profiles", "profiles", "--journal", "orgsci")
    assert r.returncode == 1 and "must allow AI tools" in r.stdout


def test_consent_check_refuses_an_smj_referee_without_a_journal_answer(tmp_path):
    rec = _referee_record_without_journal_answer(tmp_path)
    r = run("consent-check", str(rec), str(tmp_path / "ws"), "--profiles", "profiles", "--journal", "smj")
    assert r.returncode == 1 and "bans uploading" in r.stdout


def test_consent_check_unlisted_journal_still_needs_the_referee_to_confirm(tmp_path):
    rec = _referee_record_without_journal_answer(tmp_path)
    r = run("consent-check", str(rec), str(tmp_path / "ws"), "--profiles", "profiles", "--journal", "generic",
            "--needs-zero-retention")
    assert r.returncode == 1 and "not recorded" in r.stdout and "must allow AI tools" in r.stdout
    rec = _referee_record_without_journal_answer(tmp_path, journal_allows=True, journal_allows_self_confirmed=True)
    r = run("consent-check", str(rec), str(tmp_path / "ws2"), "--profiles", "profiles", "--journal", "generic",
            "--needs-zero-retention")
    assert r.returncode == 0, r.stdout


def test_consent_check_takes_zero_retention_from_the_profile(tmp_path):
    rec = _referee_record(tmp_path)
    for journal, extra in (("orgsci", {}), ("generic", {"journal_allows_self_confirmed": True})):
        rec = _referee_record(tmp_path, **extra)
        r = run("consent-check", str(rec), str(tmp_path / journal), "--profiles", "profiles", "--journal", journal)
        assert r.returncode == 1 and "zero data retention" in r.stdout, (journal, r.stdout)
        rec = _referee_record(tmp_path, zero_retention_confirmed=True, **extra)
        r = run("consent-check", str(rec), str(tmp_path / (journal + "2")), "--profiles", "profiles",
                "--journal", journal)
        assert r.returncode == 0, (journal, r.stdout)


def test_stress_test_decision_takes_zero_retention_from_the_referee_and_profile(tmp_path):
    """run.json says no zero retention, but a referee at Organization Science needs it (wave C3)."""
    r, _ = _stress_ws(tmp_path, "standard", with_openai=True, journal="orgsci")
    out = json.loads(r.stdout)
    assert out["engine"] == "claude" and "zero data retention" in out["reason"], out


def test_filter_outputs_fails_when_nothing_is_left():
    r = run("filter-outputs", "mine", "standard", "editor_memo")
    assert r.returncode == 1 and "no output" in r.stdout.lower()


def test_stage_0_step_5_filters_with_the_journal():
    text = (ROOT / "skills/review/stages/stage-0-intake.md").read_text(encoding="utf-8")
    step5 = text.split("\n5. ", 1)[1].split("\n6. ", 1)[0]
    assert "plumb filter-outputs <permission> <depth> <mapped list joined by commas> --profiles {PLUGIN}/profiles --journal <journal>" in step5


# Egress is logged when the paper is first sent, and the audit package marks the final consent (wave C5).

def _author_consent(ws, provider="x"):
    ws.mkdir(parents=True, exist_ok=True)
    rec = ws / "consent.json"
    rec.write_text(json.dumps({"role": "author", "provider": provider, "provider_trains_on_inputs": False,
                               "retention_days": 30, "egress": ["manuscript_text", "search_queries"],
                               "coauthors_agree": True}))
    return rec


def _kinds(ws):
    return [json.loads(l)["kind"] for l in (ws / "audit" / "events.jsonl").read_text().splitlines()]


def test_consent_check_logs_no_egress_and_the_egress_command_logs_it_once(tmp_path):
    ws = tmp_path / "ws"
    rec = _author_consent(ws)
    assert run("consent-check", str(rec), str(ws)).returncode == 0
    assert "egress" not in _kinds(ws)
    assert run("egress", str(ws)).returncode == 0
    assert run("egress", str(ws)).returncode == 0
    assert _kinds(ws).count("egress") == 2



def test_egress_to_a_new_provider_is_logged_again(tmp_path):
    ws = tmp_path / "ws"
    rec = _author_consent(ws, "FirstProvider")
    assert run("consent-check", str(rec), str(ws)).returncode == 0
    assert run("egress", str(ws)).returncode == 0
    rec = _author_consent(ws, "SecondProvider")
    assert run("consent-check", str(rec), str(ws)).returncode == 0
    assert run("egress", str(ws)).returncode == 0
    assert _kinds(ws).count("egress") == 3

def test_audit_package_marks_the_last_consent_record_final(tmp_path):
    ws = tmp_path / "ws"
    rec = _author_consent(ws, "FirstProvider")
    assert run("consent-check", str(rec), str(ws)).returncode == 0
    rec = _author_consent(ws, "SecondProvider")
    assert run("consent-check", str(rec), str(ws)).returncode == 0
    assert run("render-audit", str(ws)).returncode == 0
    section = (ws / "audit_package.md").read_text().split("## Consent record", 1)[1].split("\n## ", 1)[0]
    final = section.split("Final record:", 1)[1].split("Earlier records", 1)[0]
    assert "SecondProvider" in final and "FirstProvider" not in final
    assert "FirstProvider" in section.split("Earlier records", 1)[1]


def test_stage_0_logs_egress_at_the_first_dispatch():
    text = (ROOT / "skills/review/stages/stage-0-intake.md").read_text(encoding="utf-8")
    step9 = text.split("\n9. ", 1)[1].split("\n10. ", 1)[0]
    assert "plumb egress {WORKSPACE}" in step9
    step7 = text.split("\n7. ", 1)[1].split("<!-- CHECKIN", 1)[0]
    assert "one `egress` event per declared item" not in step7
