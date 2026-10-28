# tests/test_audit_coverage_hardening.py
from __future__ import annotations

import sys, pathlib
SD = pathlib.Path(__file__).resolve().parents[1] / "skills/review/scripts"
sys.path.insert(0, str(SD))
import importlib; ac = importlib.import_module("audit_coverage")

def test_duplicate_of_ignores_parenthetical():
    entries = [
        {"finding_id":"a","disposition":"INCLUDED_MAJOR","rationale":"x","target":"","severity":"","source_file":""},
        {"finding_id":"b","disposition":"MERGED","rationale":"duplicate_of: a (same root cause)","target":"","severity":"","source_file":""},
    ]
    assert ac.check_duplicate_of_targets(entries) == []

def test_source_excerpt_column_tolerated():
    md = ("| finding_id | source_file | severity | disposition | target | rationale | source_excerpt |\n"
          "|---|---|---|---|---|---|---|\n"
          "| a | f.md | Serious | INCLUDED_MAJOR | - | r | \"some excerpt text here\" |\n")
    entries = ac.extract_coverage_entries(md)
    assert len(entries) == 1  # header row was skipped, not parsed as data
    assert entries[0]["finding_id"] == "a"
    assert entries[0]["disposition"] == "INCLUDED_MAJOR"


def test_malformed_duplicate_of_target():
    # "duplicate_of: (no id here)" has no leading id token; fallback must be "" not the raw string
    entries = [
        {"finding_id": "good", "disposition": "INCLUDED_MAJOR", "rationale": "r", "target": "", "severity": "Serious", "source_file": ""},
        {"finding_id": "bad",  "disposition": "MERGED",         "rationale": "duplicate_of: (no id here)", "target": "", "severity": "Serious", "source_file": ""},
    ]
    errors = ac.check_duplicate_of_targets(entries)
    assert len(errors) > 0  # malformed/empty target is not an included id
    # must not crash; the error message should mention the empty target
    assert any("bad" in e for e in errors)
