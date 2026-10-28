"""The stored planted-1 run reproduces Table 2 exactly, with no model call."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "eval" / "runs" / "planted-1-2026-10-19"
EXPECTED = ROOT / "eval" / "runs" / "planted-1-2026-10-19.table_2.tex"
FIXTURE = ROOT / "packs" / "archival" / "fixtures" / "planted-1"


def test_stored_run_reproduces_table_2(tmp_path):
    score = tmp_path / "score.json"
    r = subprocess.run([sys.executable, str(ROOT / "eval/score_fixture.py"), str(FIXTURE), str(RUN), "--out", str(score)],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stderr
    card = json.loads(score.read_text())
    caught = [row for row in card["must_catch"] if row["result"] == "caught"]
    assert len(card["must_catch"]) == 12 and len(caught) == 11
    out = tmp_path / "table_2.tex"
    r = subprocess.run([sys.executable, str(ROOT / "eval/table2.py"), str(score), "--out", str(out)],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 0, r.stderr
    assert out.read_text() == EXPECTED.read_text()


def test_stored_run_holds_only_what_the_grader_reads():
    files = sorted(str(p.relative_to(RUN)) for p in RUN.rglob("*") if p.is_file())
    assert all(f in ("run.json", "README.md") or f.startswith(
        ("stage-4/", "stage-5/issues.json", "stage-7/validated.json", "stage-7/dropped.json")) for f in files)
    run = json.loads((RUN / "run.json").read_text())
    assert not Path(run["pdf_path"]).is_absolute()
