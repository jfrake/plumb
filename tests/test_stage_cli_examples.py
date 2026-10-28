"""Every `plumb log` and `plumb checkin` example in the stage and shared files runs through the real CLI."""
from __future__ import annotations
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/review"
FILES = sorted((SKILL / "stages").glob("*.md")) + sorted((SKILL / "shared").glob("*.md"))
CMD = re.compile(r"`(plumb (?:log|checkin|limits|models|counts|stress-test-decision|usage|runlog|scoreboard) [^`]+)`")


def _examples():
    out = []
    for p in FILES:
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            for cmd in CMD.findall(line):
                out.append(pytest.param(cmd, id=f"{p.name}:{i}:{cmd.split()[1]}"))
    return out


def _fill(cmd: str, workspace: Path) -> list:
    cmd = cmd.replace("<depth>", "deep")
    cmd = cmd.replace("'<json>'", "'{}'")
    cmd = cmd.replace("<stop>", "draft").replace("<item>", "draft:ready")
    cmd = re.sub(r'"<[^">]*>"', '"A"', cmd)
    cmd = re.sub(r"<[^>]*>", "1", cmd)
    cmd = cmd.replace("{WORKSPACE}", str(workspace))
    return shlex.split(cmd)[1:]


EXAMPLES = _examples()


def test_examples_were_found():
    assert len(EXAMPLES) >= 10


@pytest.mark.parametrize("cmd", EXAMPLES)
def test_example_runs_through_cli(cmd, tmp_path):
    args = _fill(cmd, tmp_path)
    if args[0] == "stress-test-decision":
        (tmp_path / "run.json").write_text('{"depth": "deep", "needs_zero_retention": false}')
    # HOME is the test's folder, so the Stage 7 `plumb log ... output` example never reads or
    # marks the real ~/.config/plumb/runs.json.
    env = dict(os.environ, PYTHONPATH=str(ROOT), PLUMB_CONFIG=str(tmp_path / "no-config.json"),
               HOME=str(tmp_path))
    r = subprocess.run([sys.executable, "-m", "plumb", *args],
                       capture_output=True, text=True, env=env, cwd=ROOT)
    assert r.returncode == 0, f"{cmd}\n-> {args}\n{r.stderr[-800:]}"
