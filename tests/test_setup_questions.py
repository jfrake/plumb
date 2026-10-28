"""Fewer setup questions: saved provider answers, the consent screen's fixed question list, the
recap as the agreement to send, and round 2 by check-in level. Every path is under tmp_path."""
from __future__ import annotations
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from plumb import config, progress

ROOT = Path(__file__).resolve().parents[1]
INTAKE = ROOT / "skills/review/stages/stage-0-intake.md"


def _step(n):
    return INTAKE.read_text(encoding="utf-8").split(f"\n{n}. ", 1)[1].split(f"\n{n + 1}. ", 1)[0]


def _cli(tmp_path, *args):
    env = dict(os.environ, PYTHONPATH=str(ROOT), HOME=str(tmp_path), PLUMB_CONFIG=str(tmp_path / "c.json"))
    return subprocess.run([sys.executable, "-m", "plumb", *args], capture_output=True, text=True, cwd=ROOT, env=env)


# --- Saved provider answers ---

def test_nothing_saved_is_not_fresh(tmp_path):
    status = config.facts_status(config.load(tmp_path / "none.json"))
    assert status == {"anthropic": {"saved": False, "fresh": False}, "openai": {"saved": False, "fresh": False}}


def test_saved_answers_are_fresh_for_90_days(tmp_path):
    path = tmp_path / "c.json"
    config.set_facts("anthropic", False, 30, today=date(2026, 6, 1), path=path)
    cfg = config.load(path)
    assert config.facts_status(cfg, date(2026, 8, 30))["anthropic"]["fresh"] is True
    stale = config.facts_status(cfg, date(2026, 8, 31))["anthropic"]
    assert stale["fresh"] is False and stale["saved"] is True and stale["given"] == "2026-06-01"
    assert config.facts_status(cfg, date(2026, 8, 30))["openai"] == {"saved": False, "fresh": False}


def test_saving_keeps_the_rest_of_the_config(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"contact_email": "x@example.org", "codex_enabled": True}))
    config.set_facts("openai", None, None, today=date(2026, 10, 8), path=path)
    raw = json.loads(path.read_text())
    assert raw["contact_email"] == "x@example.org" and raw["codex_enabled"] is True
    assert raw["provider_facts"]["openai"] == {"trains_on_inputs": None, "retention_days": None, "given": "2026-10-08"}


@pytest.mark.parametrize("bad", [
    {"mistral": {"trains_on_inputs": False, "retention_days": 0, "given": "2026-10-08"}},
    {"anthropic": {"trains_on_inputs": "no", "retention_days": 0, "given": "2026-10-08"}},
    {"anthropic": {"trains_on_inputs": False, "retention_days": -1, "given": "2026-10-08"}},
    {"anthropic": {"trains_on_inputs": False, "retention_days": 0, "given": "last week"}},
])
def test_a_bad_saved_answer_fails_loudly(tmp_path, bad):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"provider_facts": bad}))
    with pytest.raises(ValueError):
        config.load(path)


def test_zero_retention_is_never_saved():
    assert "zero_retention_confirmed" not in config._clean_facts(
        {"anthropic": {"trains_on_inputs": False, "retention_days": 0, "given": "2026-10-08",
                       "zero_retention_confirmed": True}})["anthropic"]


def test_cli_shows_and_sets(tmp_path):
    shown = _cli(tmp_path, "provider-facts")
    assert shown.returncode == 0 and json.loads(shown.stdout)["anthropic"]["saved"] is False
    made = _cli(tmp_path, "provider-facts", "set", "anthropic", "--trains", "no", "--retention-days", "30",
                "--today", "2026-10-01")
    assert made.returncode == 0, made.stdout
    now = json.loads(_cli(tmp_path, "provider-facts", "--today", "2026-10-08").stdout)["anthropic"]
    assert now == {"saved": True, "fresh": True, "trains_on_inputs": False, "retention_days": 30, "given": "2026-10-01"}
    unsure = _cli(tmp_path, "provider-facts", "set", "openai", "--trains", "unsure", "--retention-days", "unsure")
    assert unsure.returncode == 0 and json.loads(unsure.stdout)["retention_days"] is None
    bad = _cli(tmp_path, "provider-facts", "set", "openai", "--trains", "no", "--retention-days", "a month")
    assert bad.returncode == 1 and "Traceback" not in bad.stderr


def test_recap_dates_the_saved_answers(tmp_path):
    ws = tmp_path / "plumb_output" / "2026-10-08" / ".workspace"
    ws.mkdir(parents=True)
    (ws / "run.json").write_text(json.dumps({"pdf_path": "/fake/p.pdf", "depth": "standard", "permission": "mine",
                                             "role": "author", "journal": "orgsci", "level": "auto",
                                             "outputs": ["issues_list"]}))
    (ws / "consent.json").write_text(json.dumps({"role": "author", "permission": "mine", "provider": "Anthropic",
                                                 "provider_trains_on_inputs": False, "retention_days": 30,
                                                 "egress": ["manuscript_text", "search_queries"]}))
    facts = {"anthropic": {"trains_on_inputs": False, "retention_days": 30, "given": "2026-09-01"}}
    assert "keeps inputs 30 days (your answer of 2026-09-01) |" in progress.recap(ws, facts=facts)
    assert "your answer of" not in progress.recap(ws)


# --- The consent screen and the recap ---

def test_consent_screen_names_its_questions_and_drops_the_data_agreement():
    seven = _step(7)
    assert "Ask only the questions this step names for the run's permission, and no others" in seven
    assert "from `plumb/consent.py` fields" not in seven and "Not applicable" not in seven
    assert "Do not ask about a data agreement" in seven and "leave `data_agreement_allows` null" in seven


def test_consent_screen_asks_provider_terms_only_when_not_fresh():
    seven = _step(7)
    assert "Run `plumb provider-facts`" in seven
    assert "When `anthropic` is fresh, use its saved values and ask nothing about it." in seven
    assert "plumb provider-facts set anthropic --trains <yes|no|unsure> --retention-days <days|unsure>" in seven
    assert "plumb provider-facts set openai --trains <yes|no|unsure> --retention-days <days|unsure>" in seven
    assert "Zero data retention is never saved" in seven
    assert "ask on every run whether that account has zero data retention" in seven


def test_sending_is_a_notice_and_the_recap_is_the_agreement():
    seven, eight = _step(7), _step(8)
    assert "as a notice and not a question" in seven
    assert '"Starting the review at the recap is your agreement to send both."' in seven
    assert '"A. Start the review and send the paper (Recommended)" / "B. Change something"' in eight
    assert "A is the user's agreement to send what step 7's notice named." in eight
    assert "including the provider questions even when a fresh answer is saved" in eight


# --- Round 2 by level ---

def test_round_2_by_level():
    eleven = _step(11)
    auto = eleven.split("At Auto, ASK nothing.", 1)[1].split("At Light and Standard", 1)[0]
    assert "otherwise take the recommended answer" in auto
    light = eleven.split("At Light and Standard, ASK one screen.", 1)[1].split("At Hands-on", 1)[0]
    assert '"Change the second type or contribution"' in light and "--note shown" in light
    hands_on = eleven.split("At Hands-on, ASK one screen with every item as its own question", 1)[1]
    assert "the second type and the contribution" in hands_on
    for item in ("`setup:type`", "`setup:second_type`", "`setup:contribution`", "`setup:overlay:<pack>`",
                 "`setup:journal_confirm`"):
        assert item in eleven, item


def test_runner_answers_round_2_for_auto_and_never_saves_provider_terms():
    runner = (ROOT / "eval/run_fixture.sh").read_text(encoding="utf-8")
    assert "Setup, round 2 (Auto: use these answers, ask nothing)" in runner
    assert "never run plumb provider-facts set" in runner
    assert "data-agreement" not in runner
