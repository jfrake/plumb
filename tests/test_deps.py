from __future__ import annotations
from plumb import config, deps

def test_missing_required_reports_pip_names(monkeypatch):
    import importlib.util
    real = importlib.util.find_spec
    monkeypatch.setattr(importlib.util, "find_spec", lambda m: None if m == "pdfplumber" else real(m))
    assert "pdfplumber" in deps.missing_required()

def test_codex_detection(monkeypatch):
    monkeypatch.setattr(deps.shutil, "which", lambda n: "/usr/local/bin/codex" if n == "codex" else None)
    assert deps.codex_available() is True

def test_report_shape(monkeypatch):
    monkeypatch.setattr(deps, "codex_available", lambda: False)
    r = deps.report(config.Config())
    assert set(r) == {"missing_required", "codex"}
    assert r["codex"] is False


def test_deps_cli_reports_missing_yaml_instead_of_crashing():
    import json, subprocess, sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    code = ("import sys, runpy; sys.modules['yaml'] = None; sys.argv = ['plumb', 'deps']; "
            "runpy.run_module('plumb', run_name='__main__')")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=root)
    assert r.returncode == 0, r.stderr
    assert "pyyaml" in json.loads(r.stdout)["missing_required"]
