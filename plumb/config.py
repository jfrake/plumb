"""User configuration, stored as JSON outside the repository."""
from __future__ import annotations
import json
import os
from datetime import date
from dataclasses import asdict, dataclass, field
from pathlib import Path


def default_path() -> Path:
    env = os.environ.get("PLUMB_CONFIG")
    return Path(env) if env else Path.home() / ".config" / "plumb" / "config.json"


MODEL_ROLES = ("mechanical", "judgment")
# Older config files used these role names.
_LEGACY_ROLES = {"reasoning": "judgment", "compiler": "mechanical"}


def _default_models() -> dict:
    return {role: "inherit" for role in MODEL_ROLES}


@dataclass
class Config:
    contact_email: str = ""
    codex_enabled: bool = False
    models: dict = field(default_factory=_default_models)
    # The user's answers about each model provider's terms, with the date given. Never zero retention.
    provider_facts: dict = field(default_factory=dict)
    # Optional free OpenAlex key for the Stage 2 citation gap lists. Never printed or logged.
    openalex_api_key: str = ""


def _clean_models(raw) -> dict:
    if not isinstance(raw, dict) or not all(
            isinstance(k, str) and isinstance(v, str) and v.strip() for k, v in raw.items()):
        raise ValueError("config 'models' must map each role (mechanical, judgment) to a model name")
    out = _default_models()
    for old, new in _LEGACY_ROLES.items():
        if old in raw and new not in raw:
            out[new] = raw[old]
    for role in MODEL_ROLES:
        if role in raw:
            out[role] = raw[role]
    return out


PROVIDERS = {"anthropic": "Anthropic", "openai": "OpenAI"}
# A saved answer about a provider's terms is asked again once it is older than this.
FACTS_MAX_AGE_DAYS = 90


def _clean_facts(raw) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("config 'provider_facts' must map a provider to its saved answers")
    out = {}
    for name, f in raw.items():
        if name not in PROVIDERS or not isinstance(f, dict):
            raise ValueError(f"config 'provider_facts' has an unknown provider or a bad entry: {name!r}")
        trains, days, given = f.get("trains_on_inputs"), f.get("retention_days"), f.get("given")
        if trains is not None and not isinstance(trains, bool):
            raise ValueError(f"provider_facts.{name}.trains_on_inputs must be true, false, or null")
        if days is not None and (isinstance(days, bool) or not isinstance(days, int) or days < 0):
            raise ValueError(f"provider_facts.{name}.retention_days must be a whole number of days or null")
        try:
            date.fromisoformat(str(given))
        except ValueError:
            raise ValueError(f"provider_facts.{name}.given must be a YYYY-MM-DD date") from None
        out[name] = {"trains_on_inputs": trains, "retention_days": days, "given": str(given)}
    return out


def facts_status(cfg: "Config", today: date | None = None) -> dict:
    """Each provider's saved answers, with `fresh` true when given within FACTS_MAX_AGE_DAYS."""
    today = today or date.today()
    out = {}
    for name in PROVIDERS:
        f = cfg.provider_facts.get(name)
        if not f:
            out[name] = {"saved": False, "fresh": False}
            continue
        age = (today - date.fromisoformat(f["given"])).days
        out[name] = {"saved": True, "fresh": 0 <= age <= FACTS_MAX_AGE_DAYS, **f}
    return out


def set_facts(name: str, trains, days, today: date | None = None, path: Path | None = None) -> dict:
    """Save a provider's answers, dated today. `trains` is True, False, or None; `days` an int or None."""
    if name not in PROVIDERS:
        raise ValueError(f"Unknown provider {name!r}: use one of {', '.join(PROVIDERS)}.")
    cfg = load(path)
    cfg.provider_facts[name] = _clean_facts({name: {
        "trains_on_inputs": trains, "retention_days": days,
        "given": (today or date.today()).isoformat()}})[name]
    save(cfg, path)
    return cfg.provider_facts[name]


def load(path: Path | None = None) -> Config:
    p = path or default_path()
    if not p.exists():
        return Config()
    raw = json.loads(p.read_text())
    known = {k: raw[k] for k in Config.__dataclass_fields__ if k in raw}
    if "models" in known:
        known["models"] = _clean_models(known["models"])
    if "provider_facts" in known:
        known["provider_facts"] = _clean_facts(known["provider_facts"])
    return Config(**known)


def save(cfg: Config, path: Path | None = None) -> Path:
    """Write `cfg`, owner-only (0o600), since the file can hold an API key. A config with no
    openalex_api_key keeps the key already in the file, so a setup rewrite never erases it."""
    p = path or default_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    data = asdict(cfg)
    if not data.get("openalex_api_key") and p.exists():
        try:
            old = json.loads(p.read_text())
        except ValueError:
            old = {}
        if isinstance(old, dict) and isinstance(old.get("openalex_api_key"), str):
            data["openalex_api_key"] = old["openalex_api_key"]
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.chmod(p, 0o600)  # an existing file keeps its old mode through os.open; tighten it
    with os.fdopen(fd, "w") as f:
        f.write(json.dumps(data, indent=2) + "\n")
    return p
