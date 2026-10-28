"""Tests for verify_construction_ledger.py -- deterministic construction-ledger gate.

Covers:
  - test_passes_when_complete: valid ledger, verified true -> exit 0
  - test_fails_missing_field: a variable missing construction_formula -> exit 1
  - test_fails_bad_level_enum: level_of_measurement not in enum -> exit 1
  - test_fails_not_verified: verified=false -> exit 1
  - test_fails_empty_variables: variables=[] -> exit 1
  - test_critical_missing_file: ledger path does not exist -> exit 2
  - test_critical_bad_json: ledger is not valid JSON -> exit 2
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/review/scripts/verify_construction_ledger.py"
sys.path.insert(0, str(SCRIPT.parent))
from verify_construction_ledger import verify_construction_ledger


def _entry(**over):
    e = {
        "name": "prior experience",
        "role": "moderator",
        "level_of_measurement": "individual",
        "source_data": "employment records",
        "construction_formula": "years in prior role",
        "time_variation": "time-varying",
        "methods_anchor": "p.10",
        "construction_caveats": "missing coded as 0",
    }
    e.update(over)
    return e


def _write(tmp_path, obj):
    p = tmp_path / "construction_ledger.json"
    p.write_text(json.dumps(obj), encoding="utf-8")
    return p


def test_passes_when_complete(tmp_path):
    p = _write(tmp_path, {"verified": True, "checker_signoff": "ok", "variables": [_entry()]})
    code, report = verify_construction_ledger(p)
    assert code == 0, report
    assert "PASS" in report


def test_fails_missing_field(tmp_path):
    bad = _entry()
    del bad["construction_formula"]
    p = _write(tmp_path, {"verified": True, "variables": [bad]})
    code, report = verify_construction_ledger(p)
    assert code == 1, report


def test_fails_bad_level_enum(tmp_path):
    p = _write(tmp_path, {"verified": True, "variables": [_entry(level_of_measurement="planet")]})
    code, report = verify_construction_ledger(p)
    assert code == 1, report


def test_fails_not_verified(tmp_path):
    p = _write(tmp_path, {"verified": False, "variables": [_entry()]})
    code, report = verify_construction_ledger(p)
    assert code == 1, report


def test_fails_empty_variables(tmp_path):
    p = _write(tmp_path, {"verified": True, "variables": []})
    code, report = verify_construction_ledger(p)
    assert code == 1, report


def test_critical_missing_file(tmp_path):
    code, report = verify_construction_ledger(tmp_path / "nope.json")
    assert code == 2, report


def test_critical_bad_json(tmp_path):
    p = tmp_path / "construction_ledger.json"
    p.write_text("{not json", encoding="utf-8")
    code, report = verify_construction_ledger(p)
    assert code == 2, report



def _construct(**over):
    c = {
        "name": "relational buffering",
        "role": "aggregate dimension",
        "level_of_measurement": "organization",
        "source_data": "42 interviews with managers; board minutes",
        "construction_formula": "Groups the first-order codes 'shielding staff' and 'absorbing blame'.",
        "methods_anchor": "pp.9-11",
        "construction_caveats": "none",
        "evidence_anchor": "none shown",
    }
    c.update(over)
    return c


def test_constructs_only_ledger_passes_with_none_shown(tmp_path):
    p = _write(tmp_path, {"verified": True, "checker_signoff": "ok", "constructs": [_construct()]})
    code, report = verify_construction_ledger(p)
    assert code == 0, report
    assert "0 variables, 1 constructs" in report


def test_ledger_with_both_lists_checks_each(tmp_path):
    good = {"verified": True, "variables": [_entry()], "constructs": [_construct()]}
    assert verify_construction_ledger(_write(tmp_path, good))[0] == 0
    bad = {"verified": True, "variables": [_entry()], "constructs": [_construct(role="treatment")]}
    code, report = verify_construction_ledger(_write(tmp_path, bad))
    assert code == 1 and "Construct relational buffering: role 'treatment'" in report
    bad = {"verified": True, "variables": [_entry(role="theme")], "constructs": [_construct()]}
    code, report = verify_construction_ledger(_write(tmp_path, bad))
    assert code == 1 and "Variable prior experience: role 'theme'" in report


def test_construct_needs_evidence_anchor_but_not_time_variation(tmp_path):
    c = _construct()
    del c["evidence_anchor"]
    code, report = verify_construction_ledger(_write(tmp_path, {"verified": True, "constructs": [c]}))
    assert code == 1 and "evidence_anchor" in report
    assert "time_variation" not in _construct()


def test_fails_when_neither_list_has_entries(tmp_path):
    code, report = verify_construction_ledger(_write(tmp_path, {"verified": True, "variables": [], "constructs": []}))
    assert code == 1 and "ledger is empty" in report


def test_fails_when_constructs_is_not_a_list(tmp_path):
    code, report = verify_construction_ledger(
        _write(tmp_path, {"verified": True, "variables": [_entry()], "constructs": "none"}))
    assert code == 1 and "'constructs' must be a list" in report


def test_empty_ledger_passes_only_with_a_reason(tmp_path):
    reason = "The paper reports no measured variables and no coded constructs (searched pp. 1-30)."
    code, report = verify_construction_ledger(
        _write(tmp_path, {"verified": True, "variables": [], "constructs": [], "no_entries_reason": reason}))
    assert code == 0 and "verified empty" in report and reason in report
    code, _ = verify_construction_ledger(
        _write(tmp_path, {"verified": True, "variables": [], "no_entries_reason": "  "}))
    assert code == 1
    code, _ = verify_construction_ledger(
        _write(tmp_path, {"verified": False, "variables": [], "no_entries_reason": reason}))
    assert code == 1
