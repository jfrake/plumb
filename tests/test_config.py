from __future__ import annotations
import json

import pytest

from plumb import config

def test_defaults_when_missing(tmp_path):
    cfg = config.load(tmp_path / "none.json")
    assert cfg.contact_email == "" and cfg.codex_enabled is False
    assert cfg.models == {"mechanical": "inherit", "judgment": "inherit"}


def test_legacy_model_roles_map_to_new_ones(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"models": {"reasoning": "top", "compiler": "mid"}}))
    assert config.load(p).models == {"mechanical": "mid", "judgment": "top"}


def test_partial_models_fill_defaults(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"models": {"judgment": "top"}}))
    assert config.load(p).models == {"mechanical": "inherit", "judgment": "top"}


@pytest.mark.parametrize("bad", [{"judgment": 3}, {"judgment": ""}, ["top"]])
def test_models_must_map_roles_to_names(tmp_path, bad):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"models": bad}))
    with pytest.raises(ValueError):
        config.load(p)

def test_roundtrip_and_unknown_keys_ignored(tmp_path):
    p = tmp_path / "c.json"
    cfg = config.Config(contact_email="a@example.org", codex_enabled=True)
    config.save(cfg, p)
    p.write_text(p.read_text().replace("{", '{"legacy_key": 1, ', 1))
    back = config.load(p)
    assert back.contact_email == "a@example.org" and back.codex_enabled is True

def test_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("PLUMB_CONFIG", str(tmp_path / "x.json"))
    assert config.default_path() == tmp_path / "x.json"
