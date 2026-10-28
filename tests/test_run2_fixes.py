"""Fixes from the second pilot run: one page number when the printed page is the PDF page, and no
working folder whose name other plugins' file guards block. Every path is under tmp_path."""
from __future__ import annotations
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "review" / "scripts"))

import locate_issues  # noqa: E402
from plumb import outputs  # noqa: E402


def test_label_is_one_number_when_the_printed_page_is_the_pdf_page():
    assert locate_issues.page_label("16", 16, "page_only") == "p. 16"
    assert locate_issues.page_label("16", 16, "exact") == "p. 16"
    assert locate_issues.page_label("30", 32, "page_only") == "ms p. 30 (PDF p. 32)"
    assert locate_issues.page_label("2", 2, "approximate") == "ms p. 2 (PDF p. 2, approximate)"
    assert locate_issues.page_label("", 4, "exact") == "PDF p. 4"


def test_one_page_number_passes_only_when_pages_coincide():
    text = "1. The dropout counts are missing (p. 20).\n"
    assert outputs.page_citation_errors(text)
    assert outputs.page_citation_errors(text, same_pages=True) == []


def _cli(home, *args):
    env = dict(os.environ, PYTHONPATH=str(ROOT), HOME=str(home), PLUMB_CONFIG=str(home / "no-config.json"))
    return subprocess.run([sys.executable, "-m", "plumb", *args], capture_output=True, text=True, cwd=ROOT, env=env)


def test_validate_output_reads_page_offset_from_run_json(tmp_path):
    memo = tmp_path / "editor_memo.md"
    memo.write_text("Summary.\n\n1. Dropout counts are missing (p. 20).\n", encoding="utf-8")
    same = tmp_path / "same.json"
    same.write_text(json.dumps({"page_offset": 0}))
    shifted = tmp_path / "shifted.json"
    shifted.write_text(json.dumps({"page_offset": 2}))
    one = _cli(tmp_path, "validate-output", "editor_memo", str(memo), "--run", str(same))
    two = _cli(tmp_path, "validate-output", "editor_memo", str(memo), "--run", str(shifted))
    assert "both numbers" not in one.stdout
    assert "both numbers" in two.stdout


def test_writers_use_one_number_when_page_offset_is_0():
    for name in ("issues-list-writer.md", "report-writer.md", "editor-memo-writer.md"):
        text = " ".join((ROOT / "skills/review/agents" / name).read_text(encoding="utf-8").split())
        assert "When `page_offset` in `{WORKSPACE}/run.json` is 0" in text, name
        assert 'never "ms p." or "PDF p."' in text, name
    report = " ".join((ROOT / "skills/review/agents/report-writer.md").read_text(encoding="utf-8").split())
    assert '"(ms p. 30, PDF p. 32)", not "(ms p. 30 (PDF p. 32))"' in report


# Other plugins on a user's machine guard folders named like these, and deny any Bash command whose
# text contains one. A working path with such a folder breaks the run's own commands.
GUARDED = re.compile(r"/(?:final|submitted|published|archived)/")


def test_no_working_path_uses_a_guarded_folder_name():
    hits = []
    for base in ("skills", "packs"):
        for f in (ROOT / base).rglob("*.md"):
            for line in f.read_text(encoding="utf-8").splitlines():
                for m in re.finditer(r"\{(?:WORKSPACE|RUN)\}[^\s`'\"]*", line):
                    if GUARDED.search(m.group(0) + "/"):
                        hits.append(f"{f.relative_to(ROOT)}: {m.group(0)}")
    assert hits == []
    stage7 = (ROOT / "skills/review/stages/stage-7-output.md").read_text(encoding="utf-8")
    assert stage7.count("{WORKSPACE}/stage-7/last_check/") == 2
