from __future__ import annotations
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_install_copies_skill_and_records_root(tmp_path):
    dest = tmp_path / "skills"; cfg = tmp_path / "cfg"
    r = subprocess.run(["bash", str(ROOT / "adapters/codex/install.sh"), "--dest", str(dest)],
                       capture_output=True, text=True, env={"HOME": str(tmp_path), "PLUMB_CONFIG_DIR": str(cfg), "PATH": "/usr/bin:/bin"})
    assert r.returncode == 0, r.stderr
    assert (dest / "plumb-review" / "SKILL.md").exists()
    assert (dest / "plumb-check-numbers" / "SKILL.md").exists()
    assert (cfg / "plugin_root").read_text().strip() == str(ROOT)

def test_agents_md_repeats_subagent_instruction():
    text = (ROOT / "adapters/codex/AGENTS.md").read_text()
    assert "subagent" in text.lower() and "plumb" in text
