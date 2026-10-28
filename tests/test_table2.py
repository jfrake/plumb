"""eval/table2.py: recall by error kind and severity as a LaTeX table. Every scorecard here is a
small fake written by the test; the planted-1 key is read only to check its fields."""
from __future__ import annotations
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "eval" / "table2.py"
_spec = importlib.util.spec_from_file_location("table2", SCRIPT)
table2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(table2)


def _row(kind, severity, caught, strategy="signature"):
    return {"check": "X1", "page": 1, "severity": severity, "kind": kind, "signed": True,
            "result": "caught" if caught else "missed", "issue": "1" if caught else None,
            "strategy": strategy if caught else None, "survived": None}


FAKE = [_row("text_table", "Minor", True), _row("text_table", "Minor", False),
        _row("star", "Weakens a claim", True), _row("design", "Undermines the main claim", True, "locator")]


def _write(tmp_path, rows):
    f = tmp_path / "score.json"
    f.write_text(json.dumps({"fixture": "fake", "must_catch": rows}), encoding="utf-8")
    return f


def test_table_counts_recall_by_kind_and_severity(tmp_path):
    out = tmp_path / "tables" / "table_2.tex"
    proc = subprocess.run([sys.executable, str(SCRIPT), str(_write(tmp_path, FAKE)), "--out", str(out)],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    tex = out.read_text(encoding="utf-8")
    for rule in (r"\toprule", r"\midrule", r"\bottomrule"):
        assert rule in tex
    assert "Text number does not match its table & 2 & 1 & 0.500" in tex
    assert "Significance star not supported & 1 & 1 & 1.000" in tex
    assert "Archival design error & 1 & 1 & 1.000" in tex
    assert "Minor & 2 & 1 & 0.500" in tex
    assert "All planted errors & 4 & 3 & 0.750" in tex
    # Kinds with no planted errors get no row.
    assert "Citation to a nonexistent work" not in tex
    assert "2 of 3 catches were matched by signature" in tex


def test_row_without_a_kind_is_a_clear_error(tmp_path):
    rows = [dict(FAKE[0])]
    rows[0].pop("kind")
    proc = subprocess.run([sys.executable, str(SCRIPT), str(_write(tmp_path, rows)), "--out",
                           str(tmp_path / "t.tex")], capture_output=True, text=True)
    assert proc.returncode == 2 and "kind" in proc.stderr
    assert not (tmp_path / "t.tex").exists()


def test_planted_1_key_gives_every_must_catch_a_kind_and_a_signature():
    key = yaml.safe_load((ROOT / "packs" / "archival" / "fixtures" / "planted-1" / "expected.yaml")
                         .read_text(encoding="utf-8"))
    kinds = {k for k, _ in table2.KINDS}
    rows = key["must_catch"]
    assert len(rows) == 12
    for r in rows:
        assert r["kind"] in kinds, r["check"]
        assert r["signature"] and all(re.compile(s) for s in r["signature"]), r["check"]
    # The README's counts: 2, 2, 2, 2, 4.
    assert [sum(r["kind"] == k for r in rows) for k, _ in table2.KINDS] == [2, 2, 2, 2, 4]
