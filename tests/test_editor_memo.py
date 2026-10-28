"""The checked-facts memo for an editor: when it is offered, the top-five selection, and its
validator. Every paper detail below is made up (Fakeland, widgets)."""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

import pytest

from plumb import outputs, profiles, rundir

ROOT = Path(__file__).resolve().parents[1]
PDIR = ROOT / "profiles"


def _v(n: int, severity: str = "Weakens a claim") -> dict:
    return {"id": str(n), "severity": severity, "title": f"Fake issue {n}",
            "summary": f"The fake widget count in issue {n} does not add up."}


def _memo(items, extra: str = "", sentence: str = "", mode: str = "full") -> str:
    lines = ["# Checked-facts memo", "", "## The paper", "",
             "The paper claims that widget subsidies in Fakeland raise widget output. It uses a made-up "
             "panel of 400 fake firms and compares firms before and after the subsidy.", "",
             "## Most serious issues", ""]
    if sentence:
        lines += [sentence, ""]
    for k, v in enumerate(items, 1):
        lines += [f"### {k}. {v['title']}", "",
                  f"Severity: {v['severity']}",
                  f"Where: ms p. {k + 1}, PDF p. {k + 3}",
                  "What the paper claims: The subsidy doubles fake output.",
                  f"The problem: {v['summary']} The totals in the fake table differ by 12."]
        if mode != "facts_only":
            lines += ["Why it matters: The main estimate uses these totals.",
                      "What would settle it: A recount of the fake table's rows."]
        lines += [""]
    return "\n".join(lines) + extra + "\n"


# --- when the memo is offered ---

@pytest.mark.parametrize("permission,depth_name,pid,offered", [
    ("journal", "standard", "orgsci", True),
    ("journal", "deep", "mansci", True),
    ("journal", "full", "generic", True),
    ("journal", "quick", "orgsci", False),
    ("mine", "standard", "orgsci", False),
    ("author_asked", "deep", "orgsci", False),
    ("journal", "standard", "smj", False),
])
def test_memo_offered_only_to_a_referee_at_standard_or_deep_where_ai_review_is_allowed(
        permission, depth_name, pid, offered):
    assert profiles.editor_memo_offered(permission, depth_name, profiles.load_profile(PDIR, pid)) is offered


def test_referee_decision_keeps_the_memo_and_drops_it_at_quick():
    orgsci = profiles.load_profile(PDIR, "orgsci")
    d = profiles.referee_decision(orgsci, "issues_list,editor_memo", depth="standard")
    assert d.allowed and d.outputs == ["issues_list", "editor_memo"]
    d = profiles.referee_decision(orgsci, ["editor_memo"], depth="quick")
    assert d.outputs == ["issues_list"] and d.issues_list_mode == "facts_only"
    d = profiles.referee_decision(profiles.load_profile(PDIR, "mansci"), ["report", "editor_memo"], depth="deep")
    assert d.outputs == ["report", "editor_memo"] and d.issues_list_mode == "full"
    # A facts-only memo drops the two judgment fields, and the validator, told the mode, accepts that shape.
    kept = [_v(n) for n in range(1, 6)]
    facts_memo = _memo(outputs.memo_issues(kept), mode="facts_only")
    assert outputs.validate_editor_memo(facts_memo, validated=kept, mode="facts_only") == []
    assert profiles.parse_outputs("editor_memo,report,issues_list") == ["issues_list", "report", "editor_memo"]


# --- editor_memo_offered is enforced in code, not only in prose ---


def test_filter_outputs_drops_the_memo_for_an_author():
    # An author's outputs list never carries editor_memo, even if the caller wrongly included it:
    # editor_memo_offered requires a journal referee, so no profile is even needed here.
    kept = profiles.filter_outputs_for_role(["issues_list", "editor_memo"], "mine", "standard")
    assert kept == ["issues_list"]
    kept = profiles.filter_outputs_for_role(["issues_list", "editor_memo"], "author_asked", "deep")
    assert kept == ["issues_list"]


def test_filter_outputs_drops_the_memo_for_an_unconfirmed_unlisted_journal_referee():
    generic = profiles.load_profile(PDIR, "generic")
    d = profiles.referee_decision(generic, "issues_list,editor_memo", self_confirmed=False, depth="standard")
    assert not d.allowed and "editor_memo" not in d.outputs


def test_filter_outputs_drops_the_memo_at_quick_depth():
    orgsci = profiles.load_profile(PDIR, "orgsci")
    kept = profiles.filter_outputs_for_role(["issues_list", "editor_memo"], "journal", "quick", orgsci)
    assert kept == ["issues_list"]


def test_filter_outputs_keeps_the_memo_for_an_organization_science_referee_at_standard():
    orgsci = profiles.load_profile(PDIR, "orgsci")
    kept = profiles.filter_outputs_for_role(["issues_list", "editor_memo"], "journal", "standard", orgsci)
    assert kept == ["issues_list", "editor_memo"]
    d = profiles.referee_decision(orgsci, "issues_list,editor_memo", depth="standard")
    assert d.outputs == ["issues_list", "editor_memo"]


def test_filter_outputs_keeps_the_memo_for_a_management_science_referee_at_deep():
    mansci = profiles.load_profile(PDIR, "mansci")
    kept = profiles.filter_outputs_for_role(["report", "editor_memo"], "journal", "deep", mansci)
    assert kept == ["report", "editor_memo"]
    d = profiles.referee_decision(mansci, "report,editor_memo", depth="deep")
    assert d.outputs == ["report", "editor_memo"] and d.issues_list_mode == "full"


def test_filter_outputs_cli_matches_the_python_function(tmp_path):
    r = subprocess.run([sys.executable, "-m", "plumb", "filter-outputs", "mine", "standard",
                        "issues_list,editor_memo"], capture_output=True, text=True, cwd=ROOT,
                       env=_cli_env(tmp_path))
    assert r.returncode == 0 and json.loads(r.stdout) == ["issues_list"]
    r = subprocess.run([sys.executable, "-m", "plumb", "filter-outputs", "journal", "standard",
                        "issues_list,editor_memo", "--profiles", "profiles", "--journal", "orgsci"],
                       capture_output=True, text=True, cwd=ROOT, env=_cli_env(tmp_path))
    assert r.returncode == 0 and json.loads(r.stdout) == ["issues_list", "editor_memo"]


# --- top five and "fewer than five" ---

def test_memo_takes_the_first_five_validated_issues_in_order():
    kept = [_v(n) for n in range(1, 8)]
    assert [v["id"] for v in outputs.memo_issues(kept)] == ["1", "2", "3", "4", "5"]
    assert outputs.memo_issues(kept[:2]) == kept[:2]


def test_fewer_than_five_sentence():
    assert outputs.fewer_than_five(5) == "" and outputs.fewer_than_five(9) == ""
    assert outputs.fewer_than_five(0) == "No issues survived the checks."
    assert outputs.fewer_than_five(1) == "Only 1 issue survived the checks, so this memo lists it."
    assert outputs.fewer_than_five(3) == "Only 3 issues survived the checks, so this memo lists all of them."


# --- the validator ---

def test_a_good_memo_passes():
    kept = [_v(1, "Undermines the main claim")] + [_v(n) for n in range(2, 8)]
    assert outputs.validate_editor_memo(_memo(outputs.memo_issues(kept)), validated=kept) == []


def test_memo_with_fewer_than_five_needs_the_sentence():
    kept = [_v(1), _v(2)]
    good = _memo(kept, sentence=outputs.fewer_than_five(2))
    assert outputs.validate_editor_memo(good, validated=kept) == []
    errs = outputs.validate_editor_memo(_memo(kept), validated=kept)
    assert any("Only 2 issues survived the checks" in e for e in errs)
    empty = _memo([], sentence="No issues survived the checks.")
    assert outputs.validate_editor_memo(empty, validated=[]) == []


def test_memo_must_follow_validated_json():
    kept = [_v(n) for n in range(1, 7)]
    six = _memo(kept)
    errs = outputs.validate_editor_memo(six, validated=kept)
    assert any("at most 5" in e for e in errs)
    swapped = [kept[1], kept[0]] + kept[2:5]
    errs = outputs.validate_editor_memo(_memo(swapped), validated=kept)
    assert any("Item 1 must include its summary" in e for e in errs)
    wrong = dict(kept[0], severity="Minor")
    errs = outputs.validate_editor_memo(_memo([wrong] + kept[1:5]), validated=kept)
    assert any("Item 1 has Severity 'Minor'" in e for e in errs)


def test_memo_needs_its_sections_fields_and_both_page_numbers():
    kept = [_v(n) for n in range(1, 6)]
    text = _memo(kept).replace("Why it matters: ", "Why: ", 1).replace("ms p. 2, PDF p. 4", "p. 2", 1)
    errs = outputs.validate_editor_memo(text.replace("## The paper", "## Paper"), validated=kept)
    assert any("'## The paper'" in e for e in errs)
    assert any("Item 1 needs a 'Why it matters:' line" in e for e in errs)
    assert any("both numbers" in e for e in errs)


@pytest.mark.parametrize("phrase", [
    "This is a clear desk reject.",
    "Score: 3 out of 10",
    "Decision: reject",
    "Recommendation: major revision",
    "I recommend rejecting the paper.",
    "The editor should accept the paper.",
    "The paper should be rejected.",
    "**Decision:** reject",
    "- Score: 4/10",
])
def test_memo_rejects_every_verdict_and_desk_reject_signal(phrase):
    kept = [_v(n) for n in range(1, 6)]
    errs = outputs.validate_editor_memo(_memo(kept, extra="\n" + phrase), validated=kept)
    assert any("editorial recommendation" in e or "desk-reject" in e for e in errs), phrase


def test_memo_rejects_a_section_other_than_the_two_allowed():
    kept = [_v(n) for n in range(1, 6)]
    text = _memo(kept) + "\n## Overall assessment\n\nA closing note the memo must not carry.\n"
    errs = outputs.validate_editor_memo(text, validated=kept)
    assert any("allowed as sections" in e for e in errs)


def test_memo_allows_plain_statistical_wording():
    kept = [_v(n) for n in range(1, 6)]
    text = _memo(kept, extra="\nThe fake test cannot reject the null at the 5% level. Readers may reject "
                             "the paper's claim that the effect is causal, and some reject the paper’s "
                             "framing. The fake survey was sent out in 1999.")
    assert outputs.validate_editor_memo(text, validated=kept) == []


@pytest.mark.parametrize("phrase", [
    "The paper is not suitable for this journal.",
    "It is unsuitable for Fakeland Review.",
    "The manuscript should not be sent out for review.",
    "I would send it out to referees.",
    "The contribution falls below the bar for this journal.",
    "It does not meet the journal's bar.",
    "The paper is not ready for review.",
    "It is a poor fit for the journal.",
    "The paper is not publishable as it stands.",
    "Firms below the threshold receive no fake subsidy.",
    "Firms under the threshold are excluded from the fake panel.",
    "Only firms below the eligibility bar qualify for the fake subsidy.",
    "Firms that clear the bar get the fake subsidy.",
])
def test_memo_allows_ordinary_design_and_journal_language(phrase):
    """These read like verdicts on their words alone but describe the paper's own design (a
    regression-discontinuity or eligibility cutoff) or a mundane editorial fact; the validator no
    longer flags them (Task 6 fix round 1, Important #1)."""
    kept = [_v(n) for n in range(1, 6)]
    text = _memo(kept, extra="\n" + phrase)
    assert outputs.validate_editor_memo(text, validated=kept) == []


def test_memo_in_facts_only_mode_keeps_only_the_checked_facts():
    """In facts-only mode the memo drops 'Why it matters' and 'What would settle it' and keeps the rest."""
    kept = [_v(n) for n in range(1, 6)]
    facts_memo = _memo(kept, mode="facts_only")
    assert outputs.validate_editor_memo(facts_memo, validated=kept, mode="facts_only") == []
    errs = outputs.validate_editor_memo(facts_memo, validated=kept, mode="full")
    assert any("Item 1 needs a 'Why it matters:' line" in e for e in errs)
    assert any("Item 1 needs a 'What would settle it:' line" in e for e in errs)
    errs = outputs.validate_editor_memo(_memo(kept), validated=kept, mode="facts_only")
    assert any("Item 1 must drop the 'Why it matters:' line" in e for e in errs)
    assert any("Item 1 must drop the 'What would settle it:' line" in e for e in errs)


def test_memo_accepts_an_issue_with_no_printed_page_or_no_location():
    kept = [_v(n) for n in range(1, 6)]
    text = _memo(kept).replace("Where: ms p. 2, PDF p. 4", "Where: PDF p. 4", 1)
    text = text.replace("Where: ms p. 3, PDF p. 5", "Where: location not found", 1)
    assert outputs.validate_editor_memo(text, validated=kept) == []


def test_validate_output_cli_takes_the_memo(tmp_path):
    kept = [_v(n) for n in range(1, 6)]
    (tmp_path / "validated.json").write_text(json.dumps(kept))
    memo = tmp_path / "editor_memo.md"

    def run():
        return subprocess.run([sys.executable, "-m", "plumb", "validate-output", "editor_memo", str(memo),
                               "--validated", str(tmp_path / "validated.json")],
                              capture_output=True, text=True, cwd=ROOT, env=_cli_env(tmp_path))

    memo.write_text(_memo(kept))
    r = run()
    assert r.returncode == 0 and r.stdout.strip() == "OK"
    memo.write_text(_memo(kept, extra="\nThe paper should be rejected."))
    r = run()
    assert r.returncode == 1 and "desk-reject" in r.stdout


def test_readme_marks_the_memo(tmp_path):
    import hashlib
    from plumb import audit
    home = tmp_path / "home"
    proj = home / "proj"
    proj.mkdir(parents=True)
    pdf = proj / "fakepaper.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    ws = Path(rundir.new_run(pdf, proj, home.resolve(), "2026-09-26")["workspace"])
    run = json.loads((ws / "run.json").read_text())
    run.update({"outputs": ["issues_list", "editor_memo"], "issues_list_mode": "full"})
    (ws / "run.json").write_text(json.dumps(run))
    (ws.parent / "editor_memo.md").write_text("Fake memo.\n")
    sha = hashlib.sha256(b"Fake memo.\n").hexdigest()
    audit.log_event(ws, "verification", check="final", output="editor_memo", file="editor_memo.md",
                    sha256=sha, step="validate-output", exit=0)
    text = rundir.write_readme(ws).read_text()
    assert "- `editor_memo.md`: Verified. A memo for an editor" in text
    assert "It gives no recommendation." in text


def _cli_env(tmp_path):
    import os
    return dict(os.environ, HOME=str(tmp_path), PLUMB_CONFIG=str(tmp_path / "no-config.json"))


def test_every_cli_call_in_this_file_sets_home_and_plumb_config():
    # Global constraint: a test that runs the CLI points HOME and PLUMB_CONFIG under tmp_path.
    import re
    text = Path(__file__).read_text(encoding="utf-8")
    calls = [m.start() for m in re.finditer(r'subprocess\.run\(\[sys\.executable, "-m", "plumb"', text)]
    assert calls
    for start in calls:
        depth = 0
        for end in range(start, len(text)):
            depth += {"(": 1, ")": -1}.get(text[end], 0)
            if text[end] == ")" and depth == 0:
                break
        assert "env=_cli_env(tmp_path)" in text[start:end], text[start:start + 120]


# Plan 1e wave C12: the memo's judgment fields have a source in validated.json.

def test_validated_records_carry_why_it_matters_and_what_would_settle_it():
    from plumb import validated
    rec = validated._record({"id": "1", "title": "Fake", "severity": "Minor", "summary": "S.",
                             "why": "The fake estimate rests on it.", "settle": "A recount of the fake rows."},
                            "major")
    assert rec["why_it_matters"] == "The fake estimate rests on it."
    assert rec["settle"] == "A recount of the fake rows."
    assert validated._record({"id": "2", "summary": "S."}, "major")["why_it_matters"] is None


def test_the_writers_fill_and_the_memo_reads_the_judgment_fields():
    agents = ROOT / "skills/review/agents"
    synthesis = (agents / "synthesis.md").read_text(encoding="utf-8")
    assert '"checkin", "sources", "why", "settle"}' in synthesis
    adjudicator = (agents / "adjudicator.md").read_text(encoding="utf-8")
    assert "`why` and `settle`" in adjudicator
    writer = (agents / "editor-memo-writer.md").read_text(encoding="utf-8")
    assert "`why_it_matters`" in writer and "`settle`" in writer
