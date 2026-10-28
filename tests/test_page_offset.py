"""The printed-to-PDF page offset: locate_issues.py --page-offset prints it, `plumb page-offset`
writes it into run.json as `page_offset`, Stage 1 runs both, and the eval pool reads it. Every
PDF and run folder is a small fake written under tmp_path."""
from __future__ import annotations
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from plumb import eval_pool, rundir

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/review/scripts/locate_issues.py"
STAGE_1 = ROOT / "skills/review/stages/stage-1-verify.md"


def _make_pdf(path: Path, pages: list) -> Path:
    import pymupdf
    doc = pymupdf.open()
    for lines in pages:
        page = doc.new_page()
        y = 72
        for line in lines:
            page.insert_text((72, y), line)
            y += 14
    doc.save(str(path))
    return path


def _offset(pdf: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), "--page-offset", str(pdf)], capture_output=True, text=True)


def _ws(tmp_path) -> Path:
    ws = tmp_path / "plumb_output" / "2026-10-06" / ".workspace"
    ws.mkdir(parents=True)
    (ws / "run.json").write_text(json.dumps({"depth": "standard", "packs": ["archival"]}), encoding="utf-8")
    return ws


def _cli(tmp_path, *args):
    env = dict(os.environ, PYTHONPATH=str(ROOT), HOME=str(tmp_path), PLUMB_CONFIG=str(tmp_path / "no-config.json"))
    return subprocess.run([sys.executable, "-m", "plumb", *args], capture_output=True, text=True, cwd=ROOT, env=env)


def test_locate_issues_prints_the_fitted_offset(tmp_path):
    pdf = _make_pdf(tmp_path / "p.pdf", [["Fake title page."], ["Fake abstract."], ["1", "Fake body."],
                                         ["2", "More fake."], ["3", "End."]])
    r = _offset(pdf)
    assert r.returncode == 0, r.stdout + r.stderr
    assert json.loads(r.stdout) == 2


def test_locate_issues_prints_null_when_no_offset_fits(tmp_path):
    pdf = _make_pdf(tmp_path / "p.pdf", [["Fake page one."], ["Fake page two."]])
    r = _offset(pdf)
    assert r.returncode == 0 and json.loads(r.stdout) is None


def test_locate_issues_offset_exit_2_on_an_unreadable_pdf(tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_text("not a pdf")
    assert _offset(bad).returncode == 2


def test_set_page_offset_writes_an_integer_and_keeps_the_other_keys(tmp_path):
    ws = _ws(tmp_path)
    assert rundir.set_page_offset(ws, "2") == 2
    run = json.loads((ws / "run.json").read_text())
    assert run["page_offset"] == 2 and run["depth"] == "standard"


@pytest.mark.parametrize("bad", ["null", "two", "1.5", ""])
def test_set_page_offset_refuses_anything_but_an_integer(tmp_path, bad):
    ws = _ws(tmp_path)
    with pytest.raises(ValueError):
        rundir.set_page_offset(ws, bad)
    assert "page_offset" not in json.loads((ws / "run.json").read_text())


def test_cli_writes_page_offset_and_the_pool_reads_it(tmp_path):
    ws = _ws(tmp_path)
    r = _cli(tmp_path, "page-offset", str(ws), "-2")
    assert r.returncode == 0, r.stdout + r.stderr
    run = json.loads((ws / "run.json").read_text())
    assert run["page_offset"] == -2
    assert eval_pool.page_offset(ws, run) == -2
    assert _cli(tmp_path, "page-offset", str(tmp_path / "nowhere"), "1").returncode == 1


def test_stage_1_runs_the_offset_step_at_every_level():
    text = STAGE_1.read_text(encoding="utf-8")
    step = text.split("\n5. ", 1)[1].split("\n6. ", 1)[0]
    bullet = [b for b in step.split("\n   - ") if b.startswith("Page offset")]
    assert len(bullet) == 1
    for phrase in ("at every level",
                   "RUN `python3 {PLUGIN}/skills/review/scripts/locate_issues.py --page-offset <pdf>`",
                   "the PDF page minus the page the paper prints",
                   "run `plumb page-offset {WORKSPACE} <n>`", "writes `page_offset` into `run.json`",
                   "When it prints `null`, write nothing"):
        assert phrase in bullet[0], phrase
