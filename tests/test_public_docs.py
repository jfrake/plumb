"""The README and the repo spec read as public documents: no internal notes, and claims that match
the code and the profiles."""
from __future__ import annotations
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _spec() -> str:
    return (ROOT / "docs" / "spec.md").read_text(encoding="utf-8")


def _readme() -> str:
    return (ROOT / "README.md").read_text(encoding="utf-8")


def test_spec_carries_no_internal_notes():
    spec = _spec()
    for s in ("claude.ai/artifact", "working name", "Your plugin's private", "Plan 2", "Task 1 tests",
              "OS_reviewer/plumb", "Author A's old plugin", "private scrub checklist"):
        assert s not in spec, s
    assert not re.search(r"\((?:Author A|Author B), 20\d\d-\d\d-\d\d", spec)
    assert not re.search(r"\(ruled 20\d\d-\d\d-\d\d", spec)
    assert not re.search(r"\(20\d\d-\d\d-\d\d\)", spec)
    assert "**Author B:**" in spec and "**Author A:**" in spec


def test_spec_matches_the_management_science_ruling():
    spec = _spec()
    assert "requires the conclusions to be the reviewer's own, the issues list holds" not in spec
    assert "or requires the conclusions to be the reviewer's own" not in spec
    assert "memo only" not in spec
    assert "verification memo" not in spec


def test_spec_and_readme_say_the_memo_rule_once():
    for text in (_spec(), _readme()):
        assert "The memo never gives a verdict" not in text


def test_spec_lists_the_overlays_and_the_real_dependencies():
    spec = _spec()
    overlays = spec.split("## 5. Packs", 1)[1].split("\n\n", 2)[1]
    for name in ("computational", "nonlinear", "inference", "market-event", "network", "configurational", "framing"):
        assert name in overlays, name
    assert "is the first overlay" not in spec and "is another overlay" not in spec
    deps = spec.split("## 13.", 1)[1].split("\n- **Optional", 1)[0]
    assert "pyyaml" in deps and "Python 3.9" in deps


def test_spec_milestones_reflect_the_state_on_october_3():
    table = _spec().split("| Week ending |", 1)[1].split("\n\n", 1)[0]
    assert "Done" in table and "no IRB" in table and "Repo public" in table


def test_spec_names_only_journals_with_profiles_as_off():
    rules = _spec().split("Referee mode rules:", 1)[1].split("\n\n", 1)[0]
    for j in ("AMR", "JAP", "JOM", "OBHDP"):
        assert j not in rules, j
    assert "SMJ" in rules and "must confirm" in rules


def test_spec_says_the_pilot_used_only_the_authors_own_referee_reports():
    spec = _spec()
    consent = spec.split("## 9. Consent", 1)[1].split("\n## 10.", 1)[0]
    assert "never go to a model provider" not in consent and "by hand" not in consent
    assert "the only referee reports used are the first-round referee reports the authors received on their own manuscripts" in consent
    assert "A Claude model, run through Claude Code, read them" in consent
    assert "Results are reported only as counts, and no report is quoted." in consent
    sources = spec.split("## 14. Evaluation", 1)[1].split("\n## 15.", 1)[0]
    assert "the real referee reports, if consent allows" not in sources
    assert ("referee reports on other people's manuscripts, per paper, with the authors' consent and as the "
            "journal's policy allows") in sources
    assert "editor-in-chief" not in spec and "preregistered on OSF" not in sources
    assert "Plumb on Standard, run by an author" in sources
    assert "the blind raters, and referee reports on other people's manuscripts move to Stage 2" in sources
    stage1 = sources.split("**Stage 2", 1)[0]
    assert "12 planted errors" in stage1 and "factual, substantive judgment, or preference" in stage1
    for later in ("three runs per paper", "outside expert", "ChatGPT"):
        assert later not in stage1, later
    open_items = spec.split("## 18. Open items", 1)[1]
    assert "Consent for using real referee reports as a blinded source." not in open_items
    assert "**Resolved October 5, 2026:** referee reports on other people's manuscripts enter the evaluation in Stage 2" in open_items


def test_readme_uses_setup_only_for_the_install_skill():
    readme = _readme()
    run_part = readme.split("## Depths", 1)[1]
    assert not re.search(r"\b[Ss]etup\b", run_part), re.findall(r".{30}\b[Ss]etup\b.{30}", run_part)
    assert "at the start of each run" in readme.lower()


def test_readme_discloses_pending_fixtures_and_the_python_floor():
    readme = _readme()
    assert "pending_planting" in readme and "plumb validate-packs" in readme
    assert "Python 3.9 or later" in readme


def test_setup_offers_a_venv_when_pip_user_is_refused():
    step2 = (ROOT / "skills/setup/SKILL.md").read_text(encoding="utf-8").split("\n2. ", 1)[1].split("\n3. ", 1)[0]
    assert "externally-managed-environment" in step2
    assert "python3 -m venv ~/.config/plumb/venv" in step2 and "activate" in step2


def test_no_internal_plan_or_person_in_shipped_notes():
    sim = (ROOT / "packs/simulation/pack.yaml").read_text(encoding="utf-8")
    seven = (ROOT / "skills/review/stages/stage-7-output.md").read_text(encoding="utf-8")
    assert not re.search(r"after Author [AB] reads", sim) and "Wibbens and Kretschmer (2026)" in sim
    assert "Plan 2" not in seven and "feedback.md" in seven


def test_readme_names_the_codex_skill_names():
    codex = _readme().split("### Codex", 1)[1].split("### After installing", 1)[0]
    for d in sorted(p.name for p in (ROOT / "skills").iterdir() if p.is_dir()):
        assert f"`plumb-{d}`" in codex, d
