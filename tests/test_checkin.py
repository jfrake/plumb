from __future__ import annotations
import pytest
from plumb import audit, checkin

def test_standard_deep_has_all_seven_in_stage_order():
    assert checkin.stops_for("standard", "deep") == ["setup", "numbers", "read", "against", "majors", "minors", "draft"]

def test_light():
    assert checkin.stops_for("light", "standard") == ["setup", "majors", "draft"]

def test_auto_only_setup():
    assert checkin.stops_for("auto", "deep") == ["setup"]

def test_quick_asks_numbers_and_the_read_check():
    assert checkin.stops_for("standard", "quick") == ["setup", "numbers", "read", "draft"]
    assert checkin.stops_for("light", "quick") == ["setup", "draft"]

def test_bad_level():
    with pytest.raises(ValueError):
        checkin.stops_for("sometimes", "deep")

def test_minors_mode():
    assert checkin.minors_mode("standard") == "list"
    assert checkin.minors_mode("handson") == "each"
    assert checkin.minors_mode("light") is None

def test_override_logged_when_answer_differs(tmp_path):
    checkin.record(tmp_path, "majors", "issue-2", "keep", "downgrade")
    kinds = [e["kind"] for e in audit.read_events(tmp_path)]
    assert kinds == ["checkin", "override"]

def test_no_override_when_answer_matches(tmp_path):
    checkin.record(tmp_path, "majors", "issue-2", "keep", "keep")
    assert [e["kind"] for e in audit.read_events(tmp_path)] == ["checkin"]

def test_no_override_when_no_recommendation(tmp_path):
    checkin.record(tmp_path, "setup", "setup:level_change", "", "light")
    assert [e["kind"] for e in audit.read_events(tmp_path)] == ["checkin"]

def test_frontier_rounds_and_pruning(tmp_path):
    qs = [
        {"id": "alt-1", "stop": "against", "depends_on": [], "prune_if": {}},
        {"id": "maj-1", "stop": "majors", "depends_on": ["alt-1"], "prune_if": {"alt-1": "C"}},
        {"id": "maj-2", "stop": "majors", "depends_on": [], "prune_if": {}},
    ]
    assert [q["id"] for q in checkin.frontier(qs, tmp_path)] == ["alt-1", "maj-2"]
    checkin.record(tmp_path, "against", "alt-1", "A. Plausible, investigate further (Recommended)", "C. Not plausible here")
    assert [q["id"] for q in checkin.frontier(qs, tmp_path)] == ["maj-2"]

def test_frontier_unblocks_dependents(tmp_path):
    qs = [{"id": "a", "stop": "against", "depends_on": [], "prune_if": {}},
          {"id": "b", "stop": "majors", "depends_on": ["a"], "prune_if": {"a": "C"}}]
    checkin.record(tmp_path, "against", "a", "A. Yes (Recommended)", "A. Yes (Recommended)")
    assert [q["id"] for q in checkin.frontier(qs, tmp_path)] == ["b"]

def test_resume_knows_what_was_answered(tmp_path):
    checkin.record(tmp_path, "setup", "level", "standard", "standard")
    checkin.record(tmp_path, "majors", "issue-1", "keep", "keep")
    assert checkin.answered(tmp_path) == {("setup", "level"), ("majors", "issue-1")}


def test_frontier_cli_prunes_majors_built_on_a_dropped_alternative(tmp_path):
    """Shape the Stage 3 and Stage 4 questions.json files use: majors cards resting on an alternative."""
    import json, os, subprocess, sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ, PYTHONPATH=str(root))
    sr = lambda *a: subprocess.run([sys.executable, "-m", "plumb", *map(str, a)],
                                   capture_output=True, text=True, env=env, cwd=root)
    opts = ["A. Keep it as a major issue (Recommended)", "B. It is real, but minor",
            "C. The paper already addresses this (give the page)", "D. Dig deeper before deciding"]
    majors = [
        {"id": "majors:1", "stop": "majors", "text": "x", "options": opts, "recommended": opts[0],
         "depends_on": ["against:1"], "prune_if": {"against:1": "C"}},
        {"id": "majors:2", "stop": "majors", "text": "y", "options": opts, "recommended": opts[0],
         "depends_on": ["against:2"], "prune_if": {"against:2": "C"}},
        {"id": "majors:3", "stop": "majors", "text": "z", "options": opts, "recommended": opts[0],
         "depends_on": [], "prune_if": {}},
    ]
    qfile = tmp_path / "questions.json"
    qfile.write_text(json.dumps(majors))
    sr("checkin", tmp_path, "against", "against:1", "A. Plausible, investigate further (Recommended)", "C. Not plausible here")
    sr("checkin", tmp_path, "against", "against:2", "A. Plausible, investigate further (Recommended)", "A. Plausible, investigate further (Recommended)")
    r = sr("frontier", qfile, tmp_path)
    assert r.returncode == 0, r.stderr
    assert [q["id"] for q in json.loads(r.stdout)] == ["majors:2", "majors:3"]
    sr("checkin", tmp_path, "majors", "majors:2", opts[0], opts[0])
    sr("checkin", tmp_path, "majors", "majors:3", opts[0], opts[1])
    r = sr("frontier", qfile, tmp_path)
    assert json.loads(r.stdout) == []


# Architecture review I-6: resume replays the chosen labels, not just which items were answered.
def test_answers_returns_last_chosen_label(tmp_path):
    checkin.record(tmp_path, "numbers", "numbers:cell:3:2:1", "A. Leave it blank (Recommended)", "B. Reading 1: 0.26**")
    checkin.record(tmp_path, "minors", "minors:list", "A. Keep all (Recommended)", "A. Keep all (Recommended)")
    checkin.record(tmp_path, "minors", "minors:list", "A. Keep all (Recommended)", "B. Keep only the first three")
    assert checkin.answers(tmp_path) == {"numbers:cell:3:2:1": "B. Reading 1: 0.26**",
                                         "minors:list": "B. Keep only the first three"}


# Ruling 40 (4): against/majors answers carry " | <first sentence>"; pruning reads the letter before it.
def test_frontier_prunes_on_label_with_sentence_suffix(tmp_path):
    qs = [{"id": "against:1", "stop": "against", "depends_on": [], "prune_if": {}},
          {"id": "majors:1", "stop": "majors", "depends_on": ["against:1"], "prune_if": {"against:1": "C"}},
          {"id": "majors:2", "stop": "majors", "depends_on": ["against:2"], "prune_if": {"against:2": "C"}},
          {"id": "against:2", "stop": "against", "depends_on": [], "prune_if": {}}]
    rec = "A. Plausible, investigate further (Recommended) | Firms self-select into treatment."
    checkin.record(tmp_path, "against", "against:1", rec,
                   "C. Not plausible here | Firms self-select into treatment.")
    checkin.record(tmp_path, "against", "against:2", "A. Plausible, investigate further (Recommended) | Demand. C. rises.",
                   "D. Let the tool decide | Demand. C. rises.")
    assert [q["id"] for q in checkin.frontier(qs, tmp_path)] == ["majors:2"]

def test_letter_ignores_sentence_after_bar():
    assert checkin._letter("B. Plausible, but the paper handles it (give the page) | A. Smith argues X.") == "B"

def test_delegated_answer_logs_no_override(tmp_path):
    # Ruling 40 follow-up: "D. Let the tool decide" is recorded as the recommended label with a note.
    label = "A. Plausible, investigate further (Recommended) | Firms self-select into treatment."
    checkin.record(tmp_path, "against", "against:1", label, label, note="delegated to the tool")
    kinds = [e["kind"] for e in audit.read_events(tmp_path)]
    assert "override" not in kinds
    ev = [e for e in audit.read_events(tmp_path) if e["kind"] == "checkin"][0]
    assert ev["note"] == "delegated to the tool"

def test_stage_3_records_d_as_delegated():
    from pathlib import Path
    text = (Path(__file__).resolve().parents[1] / "skills/review/stages/stage-3-theory.md").read_text()
    assert '--note "delegated to the tool"' in text


def test_setup_items_never_log_overrides(tmp_path):
    checkin.record(tmp_path, "setup", "setup:type", "A. Archival (Recommended)", "B. Experiments")
    assert [e["kind"] for e in audit.read_events(tmp_path)] == ["checkin"]


def test_letter_differs_logs_override_even_with_text_suffix(tmp_path):
    checkin.record(tmp_path, "against", "against:1",
                   "A. Plausible, investigate further (Recommended) | Selection explains it.",
                   "C. Not plausible here | Selection explains it.")
    assert [e["kind"] for e in audit.read_events(tmp_path)] == ["checkin", "override"]


def test_same_letter_is_not_an_override(tmp_path):
    checkin.record(tmp_path, "numbers", "numbers:cell:t1:2:3",
                   "A. Leave it blank and list it as unverified (Recommended)",
                   "A. Leave it blank and list it as unverified")
    assert [e["kind"] for e in audit.read_events(tmp_path)] == ["checkin"]


def test_delegation_replay_and_free_text_never_override(tmp_path):
    rec = "A. Keep it as a major issue (Recommended) | The sample is selected."
    checkin.record(tmp_path, "majors", "majors:1", rec, rec, note="delegated to the tool")
    checkin.record(tmp_path, "majors", "majors:2", rec, "B. It is real, but minor | The sample is selected.",
                   note="replayed; ")
    checkin.record(tmp_path, "draft", "draft:ready", "A. The output is ready (Recommended)",
                   "Please shorten comment 3", note="free text")
    assert [e["kind"] for e in audit.read_events(tmp_path)] == ["checkin"] * 3


def test_minor_drop_counts_and_keep_does_not(tmp_path):
    checkin.record(tmp_path, "minors", "minors:3", "Keep (Recommended)", "Keep")
    checkin.record(tmp_path, "minors", "minors:2", "Keep (Recommended)", "Drop: The sample period is short.")
    assert [e["kind"] for e in audit.read_events(tmp_path)] == ["checkin", "checkin", "override"]


@pytest.mark.parametrize("stop", checkin.OVERRIDE_STOPS)
def test_every_judgment_stop_can_log_an_override(tmp_path, stop):
    checkin.record(tmp_path, stop, f"{stop}:x", "A. Yes (Recommended)", "B. No")
    assert [e["kind"] for e in audit.read_events(tmp_path)] == ["checkin", "override"]


def _overrides(ws):
    return sum(1 for e in audit.read_events(ws) if e["kind"] == "override")


def test_minors_list_let_me_pick_without_drops_is_not_an_override(tmp_path):
    checkin.record(tmp_path, "minors", "minors:list", "A. Keep all (Recommended)", "C. Let me pick")
    assert _overrides(tmp_path) == 0


def test_minors_list_let_me_pick_counts_each_drop(tmp_path):
    checkin.record(tmp_path, "minors", "minors:list", "A. Keep all (Recommended)", "C. Let me pick")
    checkin.record(tmp_path, "minors", "minors:2", "Keep (Recommended)", "Drop: The sample period is short.")
    checkin.record(tmp_path, "minors", "minors:5", "Keep (Recommended)", "Drop: Table 3 lacks units.")
    assert _overrides(tmp_path) == 2


def test_minors_list_keep_first_three_is_one_override(tmp_path):
    checkin.record(tmp_path, "minors", "minors:list", "A. Keep all (Recommended)", "B. Keep only the first three")
    assert _overrides(tmp_path) == 1


def test_author_mode_reask_compares_by_text(tmp_path):
    checkin.record(tmp_path, "majors", "majors:1", "Keep it (Recommended)", "Drop it")
    assert _overrides(tmp_path) == 1
    checkin.record(tmp_path, "majors", "majors:2", "Keep it (Recommended)", "Keep it")
    assert _overrides(tmp_path) == 1


def test_collision_copy_is_marked_replayed_and_counts_once(tmp_path):
    rec = "A. Keep it as a major issue (Recommended) | The sample is selected."
    ans = "B. It is real, but minor | The sample is selected."
    checkin.record(tmp_path, "majors", "majors:3:r", rec, ans)
    checkin.record(tmp_path, "majors", "majors:3", rec, ans, note="replayed; ")
    assert _overrides(tmp_path) == 1
    assert checkin.answers(tmp_path)["majors:3"] == ans


def test_author_mode_keep_it_records_original_recommended_label(tmp_path):
    rec = "A. Keep it as a major issue (Recommended) | The sample is selected."
    checkin.record(tmp_path, "majors", "majors:1", rec, rec)
    checkin.record(tmp_path, "minors", "minors:4", "Keep (Recommended)", "Keep (Recommended)")
    assert _overrides(tmp_path) == 0


def test_author_mode_drop_it_records_the_dropping_option(tmp_path):
    checkin.record(tmp_path, "minors", "minors:4", "Keep (Recommended)", "Drop: Table 3 lacks units.")
    assert _overrides(tmp_path) == 1


def test_rerecording_the_same_choice_logs_no_second_override_event(tmp_path):
    rec = "A. Plausible, investigate further (Recommended) | Demand rises."
    ans = "B. Plausible, but the paper handles it (give the page) | Demand rises."
    checkin.record(tmp_path, "against", "against:2", rec, ans)
    checkin.record(tmp_path, "against", "against:2", rec, ans, note="p.4: handled")
    assert _overrides(tmp_path) == 1


def test_changed_choice_still_logs_its_own_event(tmp_path):
    checkin.record(tmp_path, "majors", "majors:1", "A. Keep it (Recommended)", "B. Minor")
    checkin.record(tmp_path, "majors", "majors:1", "A. Keep it (Recommended)", "C. Addressed")
    assert _overrides(tmp_path) == 2
    assert len(checkin.final_overrides(audit.read_events(tmp_path))) == 1


def test_auto_note_is_never_an_override(tmp_path):
    assert not checkin.is_override("majors", "A. Keep it (Recommended)", "B. Minor", note="auto")
    checkin.record(tmp_path, "numbers", "numbers:cell:t1:2:3", "A. Leave it blank (Recommended)",
                   "A. Leave it blank (Recommended)", note="auto")
    assert _overrides(tmp_path) == 0


def test_final_answers_skip_replays_and_keep_last():
    evs = [{"kind": "checkin", "stop": "majors", "item": "majors:1", "answer": "B", "note": ""},
           {"kind": "checkin", "stop": "majors", "item": "majors:1", "answer": "A", "note": ""},
           {"kind": "checkin", "stop": "majors", "item": "majors:1", "answer": "C", "note": "replayed; "},
           {"kind": "checkin", "stop": "majors", "item": "majors:2", "answer": "C", "note": "replayed; "}]
    finals = checkin.final_answers(evs)
    assert list(finals) == [("majors", "majors:1")] and finals[("majors", "majors:1")]["answer"] == "A"


def test_second_collision_uses_r2_and_keeps_both_overrides(tmp_path):
    rec = "A. Keep it as a major issue (Recommended)"
    checkin.record(tmp_path, "majors", "majors:1", f"{rec} | X.", "B. It is real, but minor | X.")
    # Rerun 1: a new item Y at number 1 goes to majors:1:r, then is copied under majors:1.
    checkin.record(tmp_path, "majors", "majors:1:r", f"{rec} | Y.", "C. The paper already addresses this | Y.")
    checkin.record(tmp_path, "majors", "majors:1", f"{rec} | Y.", "C. The paper already addresses this | Y.",
                   note="replayed; ")
    qs = [{"id": "majors:1:r", "stop": "majors"}, {"id": "majors:1:r2", "stop": "majors"}]
    # Rerun 2: majors:1:r is taken, so a new item Z goes to the first free suffix, majors:1:r2.
    assert [q["id"] for q in checkin.frontier(qs, tmp_path)] == ["majors:1:r2"]
    checkin.record(tmp_path, "majors", "majors:1:r2", f"{rec} | Z.", f"{rec} | Z.")
    checkin.record(tmp_path, "majors", "majors:1", f"{rec} | Z.", f"{rec} | Z.", note="replayed; ")
    assert len(checkin.final_overrides(audit.read_events(tmp_path))) == 2


def test_collision_suffix_rule_is_written_down():
    from pathlib import Path
    skill = Path(__file__).resolve().parents[1] / "skills/review"
    assert "`<id>:r2`, `<id>:r3`" in (skill / "shared/checkin-template.md").read_text()
    assert "`minors:<n>:r2`, `minors:<n>:r3`" in (skill / "stages/stage-5-synthesize.md").read_text()


def test_level_change_records_a_setup_level_label_and_resume_maps_it():
    """setup:level_change records a label in setup:level's form, and resume maps either through
    its level id before running plumb stops (Plan 1e wave C8)."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "skills/review"
    template = (root / "shared/checkin-template.md").read_text(encoding="utf-8")
    assert 'setup:level_change "" "<new level label>" --note preference' in template
    assert '"B. Light"' in template.split("fewer questions", 1)[1]
    skill = (root / "SKILL.md").read_text(encoding="utf-8")
    resume = skill.split("A new session holds none of the lists", 1)[1].split("\n", 1)[0]
    assert "map the label to its level id, \"Light\"" in resume
