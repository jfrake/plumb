#!/usr/bin/env python3
"""Soft gate: verify the hypothesis ledger is complete, well typed, and signed off.

Usage:
    verify_hypothesis_ledger.py <ledger.json> <report.md> [--allow-unverified]
    verify_hypothesis_ledger.py --skip <ledger.json> "<reason>"

Exit codes:
    0  All checks passed (advisory lines never fail the gate). --skip also exits 0.
    1  One or more content checks failed (missing field, bad enum, not verified, empty).
    2  The ledger is missing or not valid JSON, or the arguments are wrong.

The report's "## Advisory" section lists interaction, curvilinear, and difference rows whose
terms are not under `Nonlinear terms:` in the fingerprint, which is read from
<workspace>/stage-0/fingerprint.md when the ledger sits in <workspace>/stage-1/.

check_hypotheses.py imports the enums, the focal-test table, and the sign rules from this file,
so the gate and the checks read one definition. Standard library only. Mirrors
verify_construction_ledger.py.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

MODES = ("hypotheses", "none")
TYPES = ("directional", "null", "difference", "interaction", "curvilinear", "mediation",
         "moderated mediation", "research question", "other")
SIGNS = ("positive", "negative", "not negative", "not positive", "none")
SHAPES = {
    "interaction": ("strengthens", "weakens", "reverses", "substitutes", "complements", "other"),
    "curvilinear": ("inverted U", "U", "diminishing returns", "increasing returns", "other"),
    "mediation": ("full", "partial", "unspecified"),
}
BASE_SIGNS = ("positive", "negative", "from estimate")
INDEPENDENT = ("yes", "no", "unknown")
TERM_KINDS = ("main effect", "moderator main effect", "product term", "squared term", "linear term of curve",
              "indirect effect", "direct effect", "index of moderated mediation", "difference test",
              "subsample estimate", "pooled estimate", "meta-regression coefficient", "figure", "other")
DESIGNATED = ("yes", "no", "unspecified")
FAMILIES = ("linear", "logit or probit", "count", "hazard", "other")
EVIDENCE = ("indirect effect with interval", "Sobel test", "causal steps only", "index of moderated mediation",
            "other")
SCALES = ("coefficient", "ratio", "correlation", "standardized")
SE_OF = ("printed estimate", "another number", "unstated")
VERDICTS = ("supported", "marginally supported", "partially supported", "not supported", "mixed", "none stated")
SECTIONS = ("abstract", "introduction", "theory", "methods", "results", "discussion", "appendix")
TAILS = ("one", "two", "unstated")
LABELS = ("none", "exploratory", "post hoc")
MEDIATION_TYPES = ("mediation", "moderated mediation")

# The focal term_kind for each hypothesis type (spec section 4.2). Every other test has expected_sign none.
FOCAL = {
    "directional": ("main effect", "pooled estimate", "meta-regression coefficient"),
    "interaction": ("product term",),
    "curvilinear": ("squared term",),
    "mediation": ("indirect effect",),
    "moderated mediation": ("index of moderated mediation",),
    "difference": ("difference test",),
    "null": ("main effect",),
}
CURVE_SIGN = {"inverted U": "negative", "diminishing returns": "negative", "U": "positive",
              "increasing returns": "positive"}

ROW_FIELDS = {
    "id": str, "statement": str, "page": str, "first_stated": dict, "post_hoc_label": bool,
    "carries_main_result": bool, "type": str, "sign_note": str, "shape": str, "base_sign": str,
    "moderator_note": str, "independent": str, "constructs": dict, "restatements": list, "tests": list,
    "search_note": str, "verdict": str, "verdict_text": str, "verdict_page": str, "verdict_cites": list,
    "verdict_scope": (str, list), "claimed_level": str, "partial_parts": str,
}
TEST_FIELDS = {
    "test_id": str, "study": str, "table": str, "column": str, "term": str, "term_kind": str,
    "expected_sign": str, "variables": dict, "sample": str, "designated": str, "model_includes_product": bool,
    "model_family": str, "estimate": dict, "note_levels": list, "tails": str, "cells": list,
    "evidence_kind": str, "verdict": str,
}
ESTIMATE_STRINGS = ("b", "se", "t", "p", "ci_level", "marks")
CELL = re.compile(r"^[^:\s]+:\d+:\d+$")
LABEL = re.compile(r"^[^\s:]+$")
NUMBER = re.compile(r"^[-+]?(\d+\.?\d*|\.\d+)$")


def _list(value):
    return value if isinstance(value, list) else []


PRINTED_P = re.compile(r"^(p\s*)?(<=|>=|<|>|=)?\s*[-+]?(\d+\.?\d*|\.\d+)$", re.I)


def _num(text):
    """The value of a plain printed number (commas and a Unicode minus allowed), or None."""
    s = str(text).strip().replace("\u2212", "-").replace(",", "")
    return float(s) if NUMBER.match(s) else None


def _level_text(value, where, name, errors):
    if isinstance(value, str) and value.strip():
        v = _num(value)
        if v is None or not 0 < v <= 1:
            errors.append(f"{where}: {name} '{value}' must be a plain number in (0, 1], or empty.")


def is_focal(row_type, term_kind) -> bool:
    if not isinstance(row_type, str) or not isinstance(term_kind, str):
        return False
    return term_kind in FOCAL.get(row_type, ())


def printed_sign(text, ratio=False):
    """'positive', 'negative', or None for a printed number (a ratio is read against 1); None when the
    text is not a plain number or prints as the null value."""
    s = str(text if text is not None else "").strip().replace("\u2212", "-").replace(",", "")
    if not NUMBER.match(s):
        return None
    v = float(s)
    if ratio:
        v -= 1.0
    if v == 0:
        return None
    return "positive" if v > 0 else "negative"


def _flip(sign):
    return {"positive": "negative", "negative": "positive"}.get(sign)


def product_sign(row):
    """The sign a product term must show for an interaction row, or (None, reason) when it cannot be
    derived. The required sign is base_sign for strengthens and the opposite for weakens and reverses,
    flipped once more when moderator_note is not empty (the moderator is coded against the
    hypothesis's wording). With base_sign 'from estimate', the base comes from the row's main effect in a
    model without the product term."""
    shape = row.get("shape")
    if shape not in ("strengthens", "weakens", "reverses"):
        return None, f"shape '{shape}' fixes no sign for the product term"
    base = row.get("base_sign")
    if base == "from estimate":
        base = None
        for t in _list(row.get("tests")):
            if isinstance(t, dict) and t.get("term_kind") == "main effect" and t.get("model_includes_product") is False:
                est = t.get("estimate") if isinstance(t.get("estimate"), dict) else {}
                base = printed_sign(est.get("b"), ratio=est.get("scale") == "ratio")
                if base:
                    break
        if base is None:
            return None, "base_sign is 'from estimate' and no model without the product term gives a signed main effect"
    if base not in ("positive", "negative"):
        return None, f"base_sign '{row.get('base_sign')}' fixes no sign"
    sign = base if shape == "strengthens" else _flip(base)
    if str(row.get("moderator_note") or "").strip():
        sign = _flip(sign)
    return sign, ""


def allowed_signs(row, test):
    """The expected_sign values the focal-test table allows for this test, or None when any is allowed."""
    rtype, kind = row.get("type"), test.get("term_kind")
    if not is_focal(rtype, kind) or rtype == "null":
        return {"none"}
    if rtype == "directional":
        return {"positive", "negative", "not negative", "not positive"}
    if rtype == "interaction":
        sign, _ = product_sign(row)
        return {sign} if sign else {"positive", "negative", "none"}
    if rtype == "curvilinear":
        sign = CURVE_SIGN.get(row.get("shape")) if isinstance(row.get("shape"), str) else None
        return {sign} if sign else {"positive", "negative", "none"}
    return {"positive", "negative", "none"}


def _typed(obj, fields, where, errors):
    for name, kind in fields.items():
        if name not in obj:
            errors.append(f"{where}: missing field '{name}'.")
        elif not isinstance(obj[name], kind):
            errors.append(f"{where}: field '{name}' must be {_kind_name(kind)}.")


def _kind_name(kind):
    names = {str: "a string", bool: "true or false", dict: "an object", list: "a list"}
    if isinstance(kind, tuple):
        return " or ".join(names[k] for k in kind)
    return names[kind]


def _enum(value, allowed, where, name, errors):
    if isinstance(value, str) and value not in allowed:
        errors.append(f"{where}: {name} '{value}' not in {sorted(allowed)}.")


def _check_test(row, test, where, errors):
    _typed(test, TEST_FIELDS, where, errors)
    for name in ("table", "term", "term_kind"):
        if isinstance(test.get(name), str) and not test[name].strip():
            errors.append(f"{where}: '{name}' is empty.")
    _enum(test.get("term_kind"), TERM_KINDS, where, "term_kind", errors)
    _enum(test.get("expected_sign"), SIGNS, where, "expected_sign", errors)
    _enum(test.get("designated"), DESIGNATED, where, "designated", errors)
    _enum(test.get("model_family"), FAMILIES, where, "model_family", errors)
    _enum(test.get("tails"), TAILS, where, "tails", errors)
    if isinstance(test.get("verdict"), str) and test["verdict"]:
        _enum(test["verdict"], VERDICTS, where, "verdict", errors)
    if row.get("type") in MEDIATION_TYPES:
        _enum(test.get("evidence_kind"), EVIDENCE, where, "evidence_kind", errors)
    elif isinstance(test.get("evidence_kind"), str) and test["evidence_kind"] != "n/a":
        errors.append(f"{where}: evidence_kind must be 'n/a' for a {row.get('type')} row.")
    est = test.get("estimate")
    if isinstance(est, dict):
        for name in ESTIMATE_STRINGS:
            if name not in est:
                errors.append(f"{where}: estimate is missing '{name}'.")
            elif not isinstance(est[name], str):
                errors.append(f"{where}: estimate '{name}' must be a string as printed.")
        ci = est.get("ci")
        if not isinstance(ci, list) or not all(isinstance(x, str) for x in ci) or len(ci) not in (0, 2):
            errors.append(f"{where}: estimate 'ci' must be an empty list or two strings as printed.")
        for name in ("b", "se", "t"):
            v = est.get(name)
            if isinstance(v, str) and v.strip() and _num(v) is None:
                errors.append(f"{where}: estimate '{name}' '{v}' is not a plain number as printed (no marks, "
                              f"brackets, or words).")
        p = est.get("p")
        if isinstance(p, str) and p.strip() and not PRINTED_P.match(p.strip().replace("\u2212", "-")):
            errors.append(f"{where}: estimate 'p' '{p}' is not a printed p-value.")
        for x in ci if isinstance(ci, list) else []:
            if isinstance(x, str) and x.strip() and _num(x) is None:
                errors.append(f"{where}: estimate 'ci' end '{x}' is not a plain number as printed.")
        if "df" in est:  # optional: the degrees of freedom the paper prints for the test
            df = est["df"]
            if not isinstance(df, str) or (df.strip() and not (_num(df) or 0) > 0):
                errors.append(f"{where}: estimate 'df' {df!r} must be the printed degrees of freedom, a positive "
                              f"number as a string, or empty.")
        for name, allowed in (("scale", SCALES), ("se_of", SE_OF)):
            if name not in est:
                errors.append(f"{where}: estimate is missing '{name}'.")
            else:
                _enum(est[name], allowed, where, name, errors)
                if not isinstance(est[name], str):
                    errors.append(f"{where}: estimate '{name}' must be a string.")
    levels = test.get("note_levels")
    if isinstance(levels, list) and not all(isinstance(x, str) for x in levels):
        errors.append(f"{where}: note_levels must be strings as printed.")
    for x in levels if isinstance(levels, list) else []:
        if isinstance(x, str) and x.strip():
            v = _num(x.strip().lstrip("<").strip())
            if v is None or not 0 < v <= 1:
                errors.append(f"{where}: note_levels '{x}' must be a plain number in (0, 1].")
    cells = test.get("cells")
    if isinstance(cells, list):
        for c in cells:
            if not isinstance(c, str) or not CELL.match(c):
                errors.append(f"{where}: cell {c!r} is not of the form <file>:<row>:<col>.")
    sign = test.get("expected_sign")
    if isinstance(sign, str) and sign in SIGNS and isinstance(row.get("type"), str):
        allowed = allowed_signs(row, test)
        if sign not in allowed:
            focal = "focal" if is_focal(row.get("type"), test.get("term_kind")) else "non-focal"
            errors.append(f"{where}: expected_sign '{sign}' does not fit the focal-test table for a {focal} "
                          f"{test.get('term_kind')} in a {row.get('type')} row (allowed: {sorted(allowed)}).")


def _check_row(row, where, errors):
    _typed(row, ROW_FIELDS, where, errors)
    rid = row.get("id")
    if isinstance(rid, str) and not LABEL.match(rid):
        errors.append(f"{where}: id must be the paper's label with no spaces or colons (for example 'H3a').")
    for name in ("statement", "verdict"):
        if isinstance(row.get(name), str) and not row[name].strip():
            errors.append(f"{where}: '{name}' is empty.")
    _level_text(row.get("claimed_level"), where, "claimed_level", errors)
    rtype = row.get("type")
    _enum(rtype, TYPES, where, "type", errors)
    _enum(row.get("verdict"), VERDICTS, where, "verdict", errors)
    shape = row.get("shape")
    if isinstance(shape, str) and isinstance(rtype, str):
        if rtype in SHAPES:
            _enum(shape, SHAPES[rtype], where, "shape", errors)
        elif rtype == "difference":
            if not (shape.startswith("larger in:") and shape[len("larger in:"):].strip()):
                errors.append(f"{where}: shape for a difference row must be 'larger in: <group>'.")
        elif shape != "n/a":
            errors.append(f"{where}: shape must be 'n/a' for a {rtype} row.")
    base = row.get("base_sign")
    if isinstance(base, str) and isinstance(rtype, str):
        if rtype == "interaction":
            _enum(base, BASE_SIGNS, where, "base_sign", errors)
        elif base != "n/a":
            errors.append(f"{where}: base_sign must be 'n/a' for a {rtype} row.")
    ind = row.get("independent")
    if isinstance(ind, str) and isinstance(rtype, str):
        if rtype == "difference":
            _enum(ind, INDEPENDENT, where, "independent", errors)
        elif ind != "n/a":
            errors.append(f"{where}: independent must be 'n/a' for a {rtype} row.")
    first = row.get("first_stated")
    if isinstance(first, dict):
        if "section" not in first or "page" not in first:
            errors.append(f"{where}: first_stated needs 'section' and 'page'.")
        else:
            _enum(first["section"], SECTIONS, where, "first_stated.section", errors)
    cons = row.get("constructs")
    if isinstance(cons, dict):
        for name in ("predictor", "outcome", "moderator", "mediator"):
            if not isinstance(cons.get(name), str):
                errors.append(f"{where}: constructs.{name} must be a string.")
    for i, r in enumerate(_list(row.get("restatements"))):
        if not isinstance(r, dict) or not all(isinstance(r.get(k), str) for k in ("where", "page", "text")):
            errors.append(f"{where}: restatement {i} needs 'where', 'page', and 'text' as strings.")
    tests = row.get("tests")
    ids = []
    if isinstance(tests, list):
        if not tests and not str(row.get("search_note") or "").strip():
            errors.append(f"{where}: no tests and an empty search_note; name every place searched.")
        for j, test in enumerate(tests):
            twhere = f"{where}, test {test.get('test_id', j) if isinstance(test, dict) else j}"
            if not isinstance(test, dict):
                errors.append(f"{twhere}: not an object.")
                continue
            ids.append(test.get("test_id") if isinstance(test.get("test_id"), str) else None)
            _check_test(row, test, twhere, errors)
    cites = row.get("verdict_cites")
    if isinstance(cites, list):
        for c in cites:
            if c not in ids:
                errors.append(f"{where}: verdict_cites names {c!r}, which is not a test of this row.")
    scope = row.get("verdict_scope")
    if isinstance(scope, str) and scope != "cited tests":
        errors.append(f"{where}: verdict_scope must be 'cited tests' or a list of this row's test ids.")
    elif isinstance(scope, list):
        for c in scope:
            if c not in ids:
                errors.append(f"{where}: verdict_scope names {c!r}, which is not a test of this row.")
    return ids


def verify(data, allow_unverified=False):
    """Return the list of content errors in a parsed ledger."""
    errors = []
    if not isinstance(data, dict):
        return ["The ledger must be a JSON object."]
    if not allow_unverified:
        if data.get("verified") is not True:
            errors.append("Top-level 'verified' is not true (the checker has not signed off).")
        elif not str(data.get("checker_signoff") or "").strip():
            errors.append("'checker_signoff' is empty although 'verified' is true.")
    for name, kind in (("verified", bool), ("checker_signoff", str), ("mode", str), ("no_entries_reason", str),
                       ("criterion", dict), ("preregistration", str), ("hypotheses", list),
                       ("unhypothesized_tests", list)):
        if name not in data:
            errors.append(f"Missing top-level field '{name}'.")
        elif not isinstance(data[name], kind):
            errors.append(f"Top-level '{name}' must be {_kind_name(kind)}.")
    _enum(data.get("mode"), MODES, "Ledger", "mode", errors)
    crit = data.get("criterion")
    if isinstance(crit, dict):
        for name in ("level", "tails", "page", "text"):
            if not isinstance(crit.get(name), str):
                errors.append(f"criterion.{name} must be a string.")
        _enum(crit.get("tails"), TAILS, "Ledger", "criterion.tails", errors)
        _level_text(crit.get("level"), "Ledger", "criterion.level", errors)
    rows = data.get("hypotheses") if isinstance(data.get("hypotheses"), list) else []
    reason = data.get("no_entries_reason")
    has_reason = isinstance(reason, str) and bool(reason.strip())
    if not rows and not has_reason:
        errors.append("The ledger is empty: 'hypotheses' must be non-empty, or 'no_entries_reason' must say why.")
    if rows and has_reason:
        errors.append("'no_entries_reason' is set although 'hypotheses' is not empty.")
    if data.get("mode") == "none" and rows:
        errors.append("mode is 'none' although 'hypotheses' is not empty.")
    if data.get("mode") == "hypotheses" and not rows:
        errors.append("mode is 'hypotheses' although 'hypotheses' is empty.")
    seen_rows, seen_tests, main = set(), set(), 0
    for i, row in enumerate(rows):
        where = f"Hypothesis {row.get('id', f'<index {i}>') if isinstance(row, dict) else f'<index {i}>'}"
        if not isinstance(row, dict):
            errors.append(f"{where}: not an object.")
            continue
        if isinstance(row.get("id"), str) and row.get("id") in seen_rows:
            errors.append(f"{where}: id is not unique.")
        seen_rows.add(row.get("id") if isinstance(row.get("id"), str) else None)
        for tid in _check_row(row, where, errors):
            if tid is not None and tid in seen_tests:
                errors.append(f"{where}: test_id {tid!r} is not unique in the ledger.")
            seen_tests.add(tid if isinstance(tid, str) else None)
        if row.get("carries_main_result") is True:
            main += 1
    if main > 2:
        errors.append(f"carries_main_result is true on {main} rows; at most two rows carry the main result.")
    for i, u in enumerate(data.get("unhypothesized_tests") if isinstance(data.get("unhypothesized_tests"), list) else []):
        where = f"Unhypothesized test {i}"
        if not isinstance(u, dict):
            errors.append(f"{where}: not an object.")
            continue
        for name in ("table", "column", "term", "page", "excerpt", "label"):
            if not isinstance(u.get(name), str):
                errors.append(f"{where}: '{name}' must be a string.")
        _enum(u.get("label"), LABELS, where, "label", errors)
        if not isinstance(u.get("in_abstract"), bool):
            errors.append(f"{where}: 'in_abstract' must be true or false.")
    return errors


def _norm(text):
    return " ".join(str(text).lower().replace("\u00d7", " x ").replace("*", " x ").split())


def advisory(data, fingerprint_text):
    """Rows of type interaction, curvilinear, or difference whose terms are not under `Nonlinear terms:`."""
    if fingerprint_text is None or not isinstance(data, dict):
        return []
    block = ""
    m = re.search(r"^Nonlinear terms:(.*?)(?=^[A-Z][A-Za-z -]*:|\Z)", fingerprint_text, re.M | re.S)
    if m:
        block = _norm(m.group(1))
    out = []
    for row in _list(data.get("hypotheses")):
        if not isinstance(row, dict) or row.get("type") not in ("interaction", "curvilinear", "difference"):
            continue
        terms = [t.get("term") for t in _list(row.get("tests"))
                 if isinstance(t, dict) and isinstance(t.get("term"), str) and t.get("term").strip()]
        if not any(_norm(t) in block for t in terms):
            shown = ", ".join(f"'{t}'" for t in terms) or "no term"
            out.append(f"{row.get('id')}: {row.get('type')} row ({shown}) is not under `Nonlinear terms:` "
                       f"in the fingerprint.")
    return out


def skip(ledger_path, reason):
    ledger_path = Path(ledger_path)
    data = {"verified": True, "checker_signoff": "skipped by the orchestrator", "mode": "none",
            "no_entries_reason": reason.strip(),
            "criterion": {"level": "", "tails": "unstated", "page": "", "text": ""},
            "preregistration": "none stated", "hypotheses": [], "unhypothesized_tests": []}
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    ledger_path.with_suffix(".md").write_text(
        f"# Hypothesis ledger\n\nNo ledger for this paper: {reason.strip()}\n", encoding="utf-8")
    return data


USAGE = ("Usage: verify_hypothesis_ledger.py <ledger.json> <report.md> [--allow-unverified]\n"
         "       verify_hypothesis_ledger.py --skip <ledger.json> \"<reason>\"")


def main(argv):
    if argv[:1] == ["--skip"]:
        if len(argv) != 3 or not argv[2].strip():
            print(USAGE, file=sys.stderr)
            return 2
        skip(argv[1], argv[2])
        print(f"SKIPPED: wrote an empty ledger to {argv[1]}: {argv[2].strip()}")
        return 0
    allow = "--allow-unverified" in argv
    args = [a for a in argv if a != "--allow-unverified"]
    if len(args) != 2 or any(a.startswith("--") for a in args):
        print(USAGE, file=sys.stderr)
        return 2
    ledger_path, report_path = Path(args[0]), Path(args[1])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(ledger_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        report = f"CRITICAL: hypothesis ledger not readable at {ledger_path}: {exc}"
        report_path.write_text(report + "\n", encoding="utf-8")
        print(report)
        return 2
    except (ValueError, RecursionError) as exc:
        report = f"CRITICAL: ledger is not valid JSON: {exc}"
        report_path.write_text(report + "\n", encoding="utf-8")
        print(report)
        return 2
    errors = verify(data, allow_unverified=allow)
    fp = ledger_path.resolve().parent.parent / "stage-0" / "fingerprint.md"
    try:
        fp_text = fp.read_text(encoding="utf-8") if fp.is_file() else None
    except (OSError, UnicodeDecodeError):
        fp_text = None
    notes = advisory(data, fp_text)
    if errors:
        head = f"HYPOTHESIS LEDGER GATE FAILED ({len(errors)} issue(s)):\n" + "\n".join(f"  - {e}" for e in errors)
    else:
        n = len(data.get("hypotheses") or [])
        state = "not yet verified, allowed for this pass" if allow and data.get("verified") is not True else "signed off"
        head = (f"PASS: hypothesis_ledger.json verified empty, {state}: {str(data.get('no_entries_reason')).strip()}"
                if n == 0 else f"PASS: hypothesis_ledger.json holds {n} hypotheses, {state}.")
    tail = "\n".join(f"- {a}" for a in notes) if notes else "None."
    if fp_text is None:
        head += "\nNo fingerprint beside the workspace; the advisory check did not run."
    report = f"{head}\n\n## Advisory\n\n{tail}\n"
    report_path.write_text(report, encoding="utf-8")
    print(head)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
