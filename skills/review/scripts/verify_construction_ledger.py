#!/usr/bin/env python3
"""Deterministic gate: verify the Variable Construction Ledger is complete and signed off.

The ledger holds measured variables under "variables", constructs built from qualitative
evidence under "constructs", or both. Each list is checked against its own fields. At least
one list must have an entry, unless both are empty and "no_entries_reason" says why (a paper
with no measured variables and no coded constructs, which the checker confirms).

Exit codes:
    0  All checks passed. Pipeline may proceed to world-building.
    1  One or more content checks failed (missing field, bad enum, not verified, empty).
    2  Critical input missing or unparseable (ledger absent / invalid JSON).

No LLM, no randomness.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

REQUIRED_FIELDS = [
    "name", "role", "level_of_measurement", "source_data",
    "construction_formula", "time_variation", "methods_anchor",
    "construction_caveats",
]
ROLE_ENUM = {"treatment", "DV", "moderator", "control"}
LEVEL_ENUM = {"firm", "industry", "CEO", "state", "firm-year", "individual", "other"}

# A construct reuses the variable fields, drops time_variation, and adds evidence_anchor
# (the pages or tables where the paper shows evidence for it, or "none shown").
CONSTRUCT_FIELDS = [
    "name", "role", "level_of_measurement", "source_data",
    "construction_formula", "methods_anchor", "construction_caveats",
    "evidence_anchor",
]
CONSTRUCT_ROLE_ENUM = {"aggregate dimension", "theme", "concept", "process phase", "mechanism", "other"}
CONSTRUCT_LEVEL_ENUM = {"individual", "group", "organization", "field", "event", "other"}


def _check_entries(entries, kind, fields, roles, levels, errors):
    for i, v in enumerate(entries):
        label = v.get("name", f"<index {i}>") if isinstance(v, dict) else f"<index {i}>"
        if not isinstance(v, dict):
            errors.append(f"{kind} {label}: not an object.")
            continue
        for f in fields:
            if not str(v.get(f, "")).strip():
                errors.append(f"{kind} {label}: missing/empty field '{f}'.")
        if v.get("role") not in roles:
            errors.append(f"{kind} {label}: role '{v.get('role')}' not in {sorted(roles)}.")
        if v.get("level_of_measurement") not in levels:
            errors.append(
                f"{kind} {label}: level_of_measurement '{v.get('level_of_measurement')}' "
                f"not in {sorted(levels)}."
            )


def verify_construction_ledger(ledger_path):
    """Return (exit_code, markdown_report)."""
    ledger_path = pathlib.Path(ledger_path)
    if not ledger_path.exists():
        return 2, f"CRITICAL: construction ledger not found at {ledger_path}"
    try:
        data = json.loads(ledger_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError) as exc:
        return 2, f"CRITICAL: ledger is not valid JSON: {exc}"

    errors = []
    if data.get("verified") is not True:
        errors.append("Top-level 'verified' is not true (checker has not signed off).")

    lists = {}
    for key in ("variables", "constructs"):
        value = data.get(key)
        if value is None:
            lists[key] = []
        elif not isinstance(value, list):
            errors.append(f"'{key}' must be a list.")
            lists[key] = []
        else:
            lists[key] = value
    reason = data.get("no_entries_reason")
    empty = not lists["variables"] and not lists["constructs"]
    if empty and not (isinstance(reason, str) and reason.strip()):
        errors.append("The ledger is empty: 'variables' or 'constructs' must be a non-empty list, "
                      "or 'no_entries_reason' must say why the paper has none.")

    _check_entries(lists["variables"], "Variable", REQUIRED_FIELDS, ROLE_ENUM, LEVEL_ENUM, errors)
    _check_entries(lists["constructs"], "Construct", CONSTRUCT_FIELDS,
                   CONSTRUCT_ROLE_ENUM, CONSTRUCT_LEVEL_ENUM, errors)

    if errors:
        body = "\n".join(f"  - {e}" for e in errors)
        return 1, f"CONSTRUCTION LEDGER GATE FAILED ({len(errors)} issue(s)):\n{body}"
    if empty:
        return 0, f"PASS: construction_ledger.json verified empty, signed off: {reason.strip()}"
    return 0, (f"PASS: construction_ledger.json verified ({len(lists['variables'])} variables, "
               f"{len(lists['constructs'])} constructs, signed off).")


def main():
    ap = argparse.ArgumentParser(description="Verify the Variable Construction Ledger.")
    ap.add_argument("ledger", help="path to construction_ledger.json")
    ap.add_argument("report", help="path to write the markdown report")
    args = ap.parse_args()
    code, report = verify_construction_ledger(args.ledger)
    pathlib.Path(args.report).write_text(report + "\n", encoding="utf-8")
    print(report)
    sys.exit(code)


if __name__ == "__main__":
    main()
