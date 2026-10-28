from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_plugin_manifest():
    m = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
    assert m["name"] == "plumb"
    assert m["license"] == "MIT"

def test_marketplace_lists_plugin():
    m = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
    assert any(p["name"] == "plumb" for p in m["plugins"])

def test_requirements_exact():
    reqs = {l.split("=")[0].split(">")[0].strip().lower()
            for l in (ROOT / "requirements.txt").read_text().splitlines() if l.strip() and not l.startswith("#")}
    assert reqs == {"pymupdf", "pdfplumber", "requests", "pyyaml", "openai", "anthropic"}


def test_requirements_mark_the_sdks_as_evaluation_only():
    lines = (ROOT / "requirements.txt").read_text().splitlines()
    marker = next(i for i, l in enumerate(lines) if l.startswith("# evaluation only"))
    assert {l.split(">")[0] for l in lines[marker + 1:] if l.strip()} == {"openai", "anthropic"}
    assert not any(l.startswith(("openai", "anthropic")) for l in lines[:marker])
