"""The hypothesis ledger gate: verify_hypothesis_ledger.py. All ledgers are small fake files written by the tests."""
from __future__ import annotations
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "review" / "scripts" / "verify_hypothesis_ledger.py"


def _test(test_id="H1-t1", **over):
    t = {"test_id": test_id, "study": "", "table": "Table 2", "column": "Model 4", "term": "Alliance experience",
         "term_kind": "main effect", "expected_sign": "positive",
         "variables": {"outcome": "New products", "predictor": "Alliance experience", "moderator": ""},
         "sample": "full", "designated": "yes", "model_includes_product": False, "model_family": "count",
         "estimate": {"b": "0.142", "se": "0.041", "t": "", "p": "", "ci": [], "ci_level": "", "marks": "***",
                      "scale": "coefficient", "se_of": "printed estimate"},
         "note_levels": ["0.10", "0.05", "0.01"], "tails": "unstated",
         "cells": ["table_02.csv:3:4", "table_02.csv:4:4"], "evidence_kind": "n/a", "verdict": ""}
    t.update(over)
    return t


def _row(rid="H1", tests=None, **over):
    r = {"id": rid, "statement": "Alliance experience increases new product introductions.", "page": "7",
         "first_stated": {"section": "theory", "page": "7"}, "post_hoc_label": False, "carries_main_result": True,
         "type": "directional", "sign_note": "", "shape": "n/a", "base_sign": "n/a", "moderator_note": "",
         "independent": "n/a",
         "constructs": {"predictor": "alliance experience", "outcome": "innovation", "moderator": "", "mediator": ""},
         "restatements": [{"where": "results", "page": "15", "text": "Hypothesis 1 predicted ..."}],
         "tests": [_test()] if tests is None else tests, "search_note": "", "verdict": "supported",
         "verdict_text": "Hypothesis 1 is supported.", "verdict_page": "15", "verdict_cites": ["H1-t1"],
         "verdict_scope": "cited tests", "claimed_level": "", "partial_parts": ""}
    r.update(over)
    return r


def _interaction():
    product = _test("H7-t1", table="Table 4", column="Model 3", term="Slack x Competition",
                    term_kind="product term", expected_sign="positive", model_includes_product=True,
                    model_family="linear", cells=["table_04.csv:9:3", "table_04.csv:10:3"])
    product["estimate"] = dict(product["estimate"], b="-0.090", se="0.030")
    main = _test("H7-t2", table="Table 4", column="Model 3", term="Competition", term_kind="main effect",
                 expected_sign="none", model_includes_product=True, model_family="linear",
                 cells=["table_04.csv:3:3", "table_04.csv:4:3"])
    return _row("H7", [product, main], type="interaction", shape="weakens", base_sign="negative",
                carries_main_result=False, verdict_cites=["H7-t1", "H7-t2"],
                statement="Slack weakens the negative effect of competition on innovation.")


def ledger(**over):
    d = {"verified": True, "checker_signoff": "checker: 2 rows re-derived", "mode": "hypotheses",
         "no_entries_reason": "",
         "criterion": {"level": "0.05", "tails": "two", "page": "11", "text": "All tests are two-tailed."},
         "preregistration": "none stated", "hypotheses": [_row(), _interaction()],
         "unhypothesized_tests": [{"table": "Table 4", "column": "Model 5", "term": "Firm age x Alliance experience",
                                   "page": "18", "excerpt": "providing further support", "label": "none",
                                   "in_abstract": True}]}
    d.update(over)
    return d


def _run(tmp_path, data, *extra):
    ws = tmp_path / "ws"
    (ws / "stage-1").mkdir(parents=True, exist_ok=True)
    path = ws / "stage-1" / "hypothesis_ledger.json"
    if data is not None:
        path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
    report = ws / "stage-1" / "hypothesis_ledger_gate.md"
    r = subprocess.run([sys.executable, str(SCRIPT), str(path), str(report), *extra], capture_output=True, text=True)
    return r, (report.read_text(encoding="utf-8") if report.exists() else "")


def test_valid_ledger_passes(tmp_path):
    r, report = _run(tmp_path, ledger())
    assert r.returncode == 0, report
    assert report.startswith("PASS: hypothesis_ledger.json holds 2 hypotheses, signed off.")
    assert "Traceback" not in r.stderr


def _drop(d, path):
    obj = d
    for key in path[:-1]:
        obj = obj[key]
    del obj[path[-1]]
    return d


def _set(d, path, value):
    obj = d
    for key in path[:-1]:
        obj = obj[key]
    obj[path[-1]] = value
    return d


FAILS = [
    ("missing-row-field", lambda d: _drop(d, ["hypotheses", 0, "verdict_scope"]), "missing field 'verdict_scope'"),
    ("missing-test-field", lambda d: _drop(d, ["hypotheses", 0, "tests", 0, "term_kind"]), "missing field 'term_kind'"),
    ("missing-top-field", lambda d: _drop(d, ["criterion"]), "Missing top-level field 'criterion'"),
    ("bad-type", lambda d: _set(d, ["hypotheses", 0, "type"], "moderation"), "type 'moderation' not in"),
    ("bad-verdict", lambda d: _set(d, ["hypotheses", 0, "verdict"], "confirmed"), "verdict 'confirmed' not in"),
    ("bad-term-kind", lambda d: _set(d, ["hypotheses", 0, "tests", 0, "term_kind"], "slope"), "term_kind 'slope'"),
    ("bad-shape-for-type", lambda d: _set(d, ["hypotheses", 1, "shape"], "inverted U"), "shape 'inverted U' not in"),
    ("shape-on-directional", lambda d: _set(d, ["hypotheses", 0, "shape"], "weakens"), "shape must be 'n/a'"),
    ("base-sign-on-directional", lambda d: _set(d, ["hypotheses", 0, "base_sign"], "negative"),
     "base_sign must be 'n/a'"),
    ("independent-on-directional", lambda d: _set(d, ["hypotheses", 0, "independent"], "yes"),
     "independent must be 'n/a'"),
    ("bad-scale", lambda d: _set(d, ["hypotheses", 0, "tests", 0, "estimate", "scale"], "log"), "scale 'log'"),
    ("bad-mode", lambda d: _set(d, ["mode"], "main results"), "mode 'main results' not in"),
    ("unverified", lambda d: _set(d, ["verified"], False), "'verified' is not true"),
    ("empty-signoff", lambda d: _set(d, ["checker_signoff"], ""), "'checker_signoff' is empty"),
    ("empty-without-reason", lambda d: _set(_set(d, ["hypotheses"], []), ["mode"], "none"), "The ledger is empty"),
    ("number-for-string", lambda d: _set(d, ["hypotheses", 0, "tests", 0, "estimate", "b"], 0.142),
     "estimate 'b' must be a string as printed"),
    ("number-in-interval", lambda d: _set(d, ["hypotheses", 0, "tests", 0, "estimate", "ci"], [0.01, 0.2]),
     "'ci' must be an empty list or two strings"),
    ("non-focal-signed", lambda d: _set(d, ["hypotheses", 1, "tests", 1, "expected_sign"], "negative"),
     "does not fit the focal-test table for a non-focal main effect"),
    ("wrong-product-sign", lambda d: _set(d, ["hypotheses", 1, "tests", 0, "expected_sign"], "negative"),
     "does not fit the focal-test table for a focal product term"),
    ("dangling-cite", lambda d: _set(d, ["hypotheses", 0, "verdict_cites"], ["H1-t9"]), "verdict_cites names 'H1-t9'"),
    ("dangling-scope", lambda d: _set(d, ["hypotheses", 0, "verdict_scope"], ["H1-t9"]), "verdict_scope names 'H1-t9'"),
    ("bad-cell", lambda d: _set(d, ["hypotheses", 0, "tests", 0, "cells"], ["Table 2, row 3"]), "is not of the form"),
    ("no-test-no-search", lambda d: _set(_set(d, ["hypotheses", 0, "tests"], []), ["hypotheses", 0, "verdict_cites"], []),
     "no tests and an empty search_note"),
    ("duplicate-id", lambda d: _set(d, ["hypotheses", 1, "id"], "H1"), "id is not unique"),
    ("label-with-space", lambda d: _set(d, ["hypotheses", 0, "id"], "Hypothesis 1"), "no spaces or colons"),
    ("evidence-kind-off-mediation", lambda d: _set(d, ["hypotheses", 0, "tests", 0, "evidence_kind"],
                                                   "causal steps only"), "evidence_kind must be 'n/a'"),
    ("reason-with-rows", lambda d: _set(d, ["no_entries_reason"], "none"), "'no_entries_reason' is set"),
    ("level-as-text", lambda d: _set(d, ["hypotheses", 0, "claimed_level"], "p < .01"),
     "claimed_level 'p < .01' must be a plain number"),
    ("criterion-percent", lambda d: _set(d, ["criterion", "level"], "5%"), "criterion.level '5%' must be a plain number"),
    ("note-level-text", lambda d: _set(d, ["hypotheses", 0, "tests", 0, "note_levels"], ["0.10", "*"]),
     "note_levels '*' must be a plain number"),
    ("starred-estimate", lambda d: _set(d, ["hypotheses", 0, "tests", 0, "estimate", "b"], "0.142***"),
     "estimate 'b' '0.142***' is not a plain number"),
    ("bracketed-error", lambda d: _set(d, ["hypotheses", 0, "tests", 0, "estimate", "se"], "(0.041)"),
     "estimate 'se' '(0.041)' is not a plain number"),
]


@pytest.mark.parametrize("mutate,match", [f[1:] for f in FAILS], ids=[f[0] for f in FAILS])
def test_content_failures_exit_1(tmp_path, mutate, match):
    r, report = _run(tmp_path, mutate(copy.deepcopy(ledger())))
    assert r.returncode == 1, report
    assert report.startswith("HYPOTHESIS LEDGER GATE FAILED") and match in report, report


def test_printed_forms_that_pass(tmp_path):
    d = ledger()
    d["hypotheses"][0]["tests"][0]["estimate"].update(b="1,204.5", se="", t="-2.31", p="<0.001",
                                                    ci=[".012", "0.31"], ci_level="95")
    d["hypotheses"][0]["claimed_level"] = ".05"
    r, report = _run(tmp_path, d)
    assert r.returncode == 0, report


def test_wrong_derived_sign_on_a_focal_squared_term_fails(tmp_path):
    curve = _row("H12", [_test("H12-t1", term="Supplier concentration squared", term_kind="squared term",
                               expected_sign="positive")], type="curvilinear", shape="inverted U",
                 carries_main_result=False, verdict_cites=["H12-t1"])
    r, report = _run(tmp_path, ledger(hypotheses=[_row(), curve]))
    assert r.returncode == 1 and "allowed: ['negative']" in report, report
    curve["tests"][0]["expected_sign"] = "negative"
    r, report = _run(tmp_path, ledger(hypotheses=[_row(), curve]))
    assert r.returncode == 0, report


def test_three_main_result_rows_fail(tmp_path):
    rows = [_row(f"H{i}", [_test(f"H{i}-t1")], verdict_cites=[f"H{i}-t1"]) for i in (1, 2, 3)]
    r, report = _run(tmp_path, ledger(hypotheses=rows))
    assert r.returncode == 1 and "at most two rows carry the main result" in report


def test_allow_unverified_passes_an_unsigned_ledger(tmp_path):
    r, report = _run(tmp_path, ledger(verified=False, checker_signoff=""), "--allow-unverified")
    assert r.returncode == 0, report
    assert "not yet verified, allowed for this pass" in report


def test_missing_and_unparseable_exit_2(tmp_path):
    r, report = _run(tmp_path, None)
    assert r.returncode == 2 and report.startswith("CRITICAL")
    r, report = _run(tmp_path, "{not json")
    assert r.returncode == 2 and "not valid JSON" in report


def test_top_level_list_fails_without_a_traceback(tmp_path):
    r, report = _run(tmp_path, [ledger()])
    assert r.returncode == 1 and "must be a JSON object" in report
    assert "Traceback" not in r.stderr


def test_skip_writes_a_ledger_that_passes(tmp_path):
    path = tmp_path / "ws" / "stage-1" / "hypothesis_ledger.json"
    r = subprocess.run([sys.executable, str(SCRIPT), "--skip", str(path), "the fingerprint lists no hypotheses"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["mode"] == "none" and data["hypotheses"] == [] and data["verified"] is True
    assert data["checker_signoff"] == "skipped by the orchestrator"
    assert "the fingerprint lists no hypotheses" in path.with_suffix(".md").read_text(encoding="utf-8")
    r2, report = _run(tmp_path, data)
    assert r2.returncode == 0 and report.startswith("PASS: hypothesis_ledger.json verified empty")


def test_skip_needs_a_reason(tmp_path):
    r = subprocess.run([sys.executable, str(SCRIPT), "--skip", str(tmp_path / "l.json"), " "],
                       capture_output=True, text=True)
    assert r.returncode == 2 and r.stderr.startswith("Usage: verify_hypothesis_ledger.py")


def test_advisory_lists_terms_missing_from_the_fingerprint_and_does_not_fail(tmp_path):
    ws = tmp_path / "ws"
    (ws / "stage-0").mkdir(parents=True)
    (ws / "stage-0" / "fingerprint.md").write_text(
        "# Fingerprint\n\nNonlinear terms:\n- Firm age x Alliance experience: interaction; model: count; "
        "role: other hypothesis\nDesigns:\n- none\n", encoding="utf-8")
    r, report = _run(tmp_path, ledger())
    assert r.returncode == 0, report
    advisory = report.split("## Advisory", 1)[1]
    assert "- H7: interaction row ('Slack x Competition', 'Competition') is not under `Nonlinear terms:`" in advisory
    (ws / "stage-0" / "fingerprint.md").write_text(
        "# Fingerprint\n\nNonlinear terms:\n- Slack \u00d7 Competition: interaction; model: linear; "
        "role: main hypothesis\n", encoding="utf-8")
    r, report = _run(tmp_path, ledger())
    assert r.returncode == 0 and report.split("## Advisory", 1)[1].strip() == "None."


JUNK = [
    ("list-id", ["hypotheses", 0, "id"], ["H1"]),
    ("dict-type", ["hypotheses", 0, "type"], {"x": 1}),
    ("list-test-id", ["hypotheses", 0, "tests", 0, "test_id"], ["H1-t1"]),
    ("float-tests", ["hypotheses", 0, "tests"], 1e308),
    ("null-row", ["hypotheses", 1], None),
    ("string-restatements", ["hypotheses", 0, "restatements"], "p. 15"),
    ("list-shape", ["hypotheses", 1, "shape"], ["weakens"]),
]


@pytest.mark.parametrize("path,value", [j[1:] for j in JUNK], ids=[j[0] for j in JUNK])
def test_malformed_values_fail_without_a_traceback(tmp_path, path, value):
    r, report = _run(tmp_path, _set(copy.deepcopy(ledger()), path, value))
    assert r.returncode == 1 and "Traceback" not in r.stderr, r.stderr


# --- Fix round (2026-09-30 rulings): the optional printed degrees of freedom ---

@pytest.mark.parametrize("df,ok", [(None, True), ("", True), ("10", True), ("1,204", True), ("38.6", True),
                                   ("ten", False), ("0", False), ("-3", False), (10, False)])
def test_optional_df_is_a_printed_positive_number(tmp_path, df, ok):
    d = ledger()
    if df is not None:
        d["hypotheses"][0]["tests"][0]["estimate"]["df"] = df
    r, report = _run(tmp_path, d)
    assert r.returncode == (0 if ok else 1), report
    if not ok:
        assert "estimate 'df'" in report


def test_deep_nesting_exits_2(tmp_path, monkeypatch):
    r, report = _run(tmp_path, "[" * 100000 + "]" * 100000)
    assert r.returncode in (1, 2) and "Traceback" not in r.stderr
    import importlib.util
    spec = importlib.util.spec_from_file_location("verify_hypothesis_ledger", SCRIPT)
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)

    def deep(_text):
        raise RecursionError("maximum recursion depth exceeded")  # what Python 3.9's json raises
    monkeypatch.setattr(gate.json, "loads", deep)
    path = tmp_path / "ws" / "stage-1" / "hypothesis_ledger.json"
    assert gate.main([str(path), str(tmp_path / "gate.md")]) == 2
