"""
TDD for FIX 1: verify_claim_attribution.verify() returns real exit codes.

Exit code contract:
    0  PASS         -- all citations documented, no REFUTED entries.
    1  FAIL         -- structural or content (REFUTED) failure.
    2  REVIEW_NEEDED -- at least one UNVERIFIABLE entry, no other failures.

Tests construct minimal claim_attribution.jsonl + review.txt fixtures and call
verify() directly; they also confirm the CLI exits with the same code.
"""
from __future__ import annotations

import json
import subprocess
import sys
import pathlib
import tempfile
import textwrap

SD = pathlib.Path(__file__).resolve().parents[1] / "skills/review/scripts"
sys.path.insert(0, str(SD))

import importlib
vca = importlib.import_module("verify_claim_attribution")

SCRIPT = SD / "verify_claim_attribution.py"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_review(path, citations):
    """Write a minimal review.txt with body citations so coverage check passes."""
    body = " ".join(f"({a} {y})" for a, y in citations)
    path.write_text(f"The review says {body}.\n\nREFERENCES\n\nSmith (2020). A paper.\n")


def _write_ledger(path, records):
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")


def _confirmed_record(surname="Smith", year=2020):
    return {
        "citation": f"{surname} et al. ({year})",
        "review_claim": "the paper finds X",
        "claim_type": "finding",
        "source_url": "https://example.com/smith2020",
        "evidence_quote": "We find X in Table 2.",
        "verdict": "CONFIRMED",
    }


def _refuted_record(surname="Jones", year=2021):
    return {
        "citation": f"{surname} ({year})",
        "review_claim": "the paper finds Y",
        "claim_type": "finding",
        "source_url": "https://example.com/jones2021",
        "evidence_quote": "We find Z, not Y.",
        "verdict": "REFUTED",
    }


def _unverifiable_record(surname="Chen", year=2019):
    return {
        "citation": f"{surname} ({year})",
        "review_claim": "the paper finds Z",
        "claim_type": "existence-only",
        "source_url": "",
        "evidence_quote": "",
        "verdict": "UNVERIFIABLE",
        "note": "paper not publicly accessible",
    }


# ---------------------------------------------------------------------------
# Direct verify() return-value tests
# ---------------------------------------------------------------------------

def test_verify_returns_0_for_pass(tmp_path):
    review = tmp_path / "review.txt"
    ledger = tmp_path / "ledger.jsonl"
    out = tmp_path / "out.md"

    _write_review(review, [("Smith", 2020)])
    _write_ledger(ledger, [_confirmed_record("Smith", 2020)])

    code = vca.verify(str(review), str(ledger), str(out))
    assert code == 0, f"Expected exit 0 for PASS, got {code}"
    assert "PASS" in out.read_text()


def test_verify_returns_1_for_refuted_content(tmp_path):
    review = tmp_path / "review.txt"
    ledger = tmp_path / "ledger.jsonl"
    out = tmp_path / "out.md"

    _write_review(review, [("Jones", 2021)])
    _write_ledger(ledger, [_refuted_record("Jones", 2021)])

    code = vca.verify(str(review), str(ledger), str(out))
    assert code == 1, f"Expected exit 1 for REFUTED, got {code}"
    assert "REFUTED" in out.read_text() or "FAIL" in out.read_text()


def test_verify_returns_1_for_structural_fail_no_ledger(tmp_path):
    review = tmp_path / "review.txt"
    ledger = tmp_path / "missing_ledger.jsonl"
    out = tmp_path / "out.md"

    _write_review(review, [("Smith", 2020)])
    # ledger file does not exist

    code = vca.verify(str(review), str(ledger), str(out))
    assert code == 1, f"Expected exit 1 for missing ledger, got {code}"


def test_verify_returns_2_for_review_needed(tmp_path):
    review = tmp_path / "review.txt"
    ledger = tmp_path / "ledger.jsonl"
    out = tmp_path / "out.md"

    _write_review(review, [("Chen", 2019)])
    _write_ledger(ledger, [_unverifiable_record("Chen", 2019)])

    code = vca.verify(str(review), str(ledger), str(out))
    assert code == 2, f"Expected exit 2 for REVIEW_NEEDED, got {code}"
    assert "REVIEW_NEEDED" in out.read_text()


def test_verify_returns_1_when_refuted_and_unverifiable_present(tmp_path):
    """FAIL (exit 1) takes priority over REVIEW_NEEDED when both conditions present."""
    review = tmp_path / "review.txt"
    ledger = tmp_path / "ledger.jsonl"
    out = tmp_path / "out.md"

    _write_review(review, [("Jones", 2021), ("Chen", 2019)])
    _write_ledger(ledger, [
        _refuted_record("Jones", 2021),
        _unverifiable_record("Chen", 2019),
    ])

    code = vca.verify(str(review), str(ledger), str(out))
    assert code == 1, f"Expected exit 1 (REFUTED takes priority), got {code}"


# ---------------------------------------------------------------------------
# CLI exit-code tests (confirm sys.exit() propagates the right value)
# ---------------------------------------------------------------------------

def _run_cli(args, tmp_path):
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        capture_output=True,
        text=True,
    )


def test_cli_exits_0_for_pass(tmp_path):
    review = tmp_path / "review.txt"
    ledger = tmp_path / "ledger.jsonl"
    out = tmp_path / "out.md"
    _write_review(review, [("Smith", 2020)])
    _write_ledger(ledger, [_confirmed_record("Smith", 2020)])

    r = _run_cli([str(review), str(ledger), str(out)], tmp_path)
    assert r.returncode == 0, f"CLI exit {r.returncode}; stdout={r.stdout!r}"


def test_cli_exits_1_for_fail(tmp_path):
    review = tmp_path / "review.txt"
    ledger = tmp_path / "ledger.jsonl"
    out = tmp_path / "out.md"
    _write_review(review, [("Jones", 2021)])
    _write_ledger(ledger, [_refuted_record("Jones", 2021)])

    r = _run_cli([str(review), str(ledger), str(out)], tmp_path)
    assert r.returncode == 1, f"CLI exit {r.returncode}; stdout={r.stdout!r}"


def test_cli_exits_2_for_review_needed(tmp_path):
    review = tmp_path / "review.txt"
    ledger = tmp_path / "ledger.jsonl"
    out = tmp_path / "out.md"
    _write_review(review, [("Chen", 2019)])
    _write_ledger(ledger, [_unverifiable_record("Chen", 2019)])

    r = _run_cli([str(review), str(ledger), str(out)], tmp_path)
    assert r.returncode == 2, f"CLI exit {r.returncode}; stdout={r.stdout!r}"


def test_cli_uncited_mode_always_exits_0(tmp_path):
    """--uncited mode must always exit 0 regardless of findings."""
    review = tmp_path / "review.txt"
    out = tmp_path / "uncited.md"
    review.write_text(
        "The FDA requires all vendors to report. NAICS mandates disclosure.\n"
    )
    r = _run_cli(["--uncited", str(review), str(out)], tmp_path)
    assert r.returncode == 0, (
        f"--uncited mode must always exit 0, got {r.returncode}; stdout={r.stdout!r}"
    )
