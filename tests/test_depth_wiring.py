from __future__ import annotations
import re
from pathlib import Path
from plumb import depth

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/review"
STAGES = SKILL / "stages"


def test_research_agents_state_the_depth_budgets():
    for agent, budget in depth.SEARCH_BUDGET.items():
        text = (SKILL / "agents" / f"{agent}.md").read_text()
        lines = [l for l in text.splitlines() if l.startswith("Search budget:")]
        assert len(lines) == 1, f"{agent}: expected one 'Search budget:' line, found {len(lines)}"
        line = lines[0]
        assert f"{budget['standard']} searches at Standard depth" in line, agent
        assert f"{budget['deep']} at Deep" in line, agent
        assert "Read `depth` from `run.json`" in line, agent


def test_old_budget_lines_are_gone():
    assert "20-30 searches." not in (SKILL / "agents/timeline-research.md").read_text()
    assert "15-20 searches." not in (SKILL / "agents/contribution-research.md").read_text()
    assert "Read `tier`" not in (SKILL / "agents/setting-research.md").read_text()


def test_no_hard_coded_loop_caps_in_stage_files():
    banned = ["Max 2 devil cycles", "Max 1 correction cycle", "Max 2 critic cycles",
              "after two cycles", "on the second cycle", "back to `agents/synthesis.md` once",
              "`agents/accuracy-audit.md` once", "the same single retry", "back to the writer once"]
    for p in STAGES.glob("*.md"):
        text = p.read_text()
        for b in banned:
            assert b not in text, f"{p.name}: {b}"
    for name in ("stage-3-theory.md", "stage-5-synthesize.md", "stage-6-audit.md", "stage-7-output.md"):
        assert "`revisions`" in (STAGES / name).read_text(), name


def test_ported_agents_defer_cycle_caps_to_the_orchestrator():
    devil = (SKILL / "agents/theory-devil.md").read_text()
    critic = (SKILL / "agents/synthesis-critic.md").read_text()
    assert "Max 1 revision cycle" not in devil and "One revision cycle only" not in devil
    assert "REVISIONS" in devil and "REVIEW" in devil
    assert "Max 2 critic cycles" not in critic
    assert "REVISIONS" in (STAGES / "stage-3-theory.md").read_text()


FULL_WORDING = [re.compile(p) for p in (
    r"\bat Full\b", r"C\. Full\b", r"\bFull depth\b", r"\bFull runs\b", r"`full`", r"\bat full depth\b")]


def test_no_full_depth_wording_left():
    files = sorted(SKILL.rglob("*.md")) + sorted((ROOT / "skills").glob("*/SKILL.md")) + [
        ROOT / "README.md", ROOT / "docs/spec.md"]
    hits = [f"{p.relative_to(ROOT)}: {rx.pattern}" for p in files for rx in FULL_WORDING if rx.search(p.read_text())]
    assert not hits, hits


def test_stage_0_offers_three_depths_and_writes_limits():
    intake = (STAGES / "stage-0-intake.md").read_text()
    assert "Depth (A. Standard (Recommended) / B. Quick / C. Deep)" in intake
    assert "`quick`/`standard`/`deep`" in intake
    assert "plumb limits <depth>" in intake and '"limits"' in intake


def test_resume_maps_full_to_deep_and_restores_limits():
    skill = (SKILL / "SKILL.md").read_text()
    assert '"full"' in skill and "plumb limits <depth>" in skill


def test_readme_names_the_three_depths():
    readme = (ROOT / "README.md").read_text()
    assert "## Depths" in readme
    for word in ("**Quick**", "**Standard**", "**Deep**"):
        assert word in readme
