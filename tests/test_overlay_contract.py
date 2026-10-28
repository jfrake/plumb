from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/review"
STAGES = {n: SKILL / "stages" / name for n, name in enumerate([
    "stage-0-intake.md", "stage-1-verify.md", "stage-2-understand.md", "stage-3-theory.md",
    "stage-4-diagnose.md", "stage-5-synthesize.md", "stage-6-audit.md", "stage-7-output.md"])}


def test_fingerprint_records_overlays_and_generated_variables():
    text = (SKILL / "agents/manuscript-audit.md").read_text()
    template = text.split("# Fingerprint", 1)[1].split("```", 1)[0]
    assert "Overlays:" in template and "Generated variables:" in template
    for method in ("LLM", "classifier", "dictionary", "topic model", "embedding", "image", "silicon sample"):
        assert method in text, method
    for role in ("main treatment", "main outcome", "moderator or mechanism", "control"):
        assert role in text, role
    assert "A pack is built for archival only" not in text


def test_pack_number_flags_reach_the_numbers_checkin():
    s1 = STAGES[1].read_text()
    assert "stage-1/<pack>_numbers.md" in s1 and "## Flags" in s1
    assert "numbers:pack:<pack>:<n>" in s1


def test_read_checkin_shows_generated_variable_roles():
    step3 = STAGES[2].read_text().split("\n3. ", 1)[1].split("\n4. ", 1)[0]
    assert "Generated variables:" in step3 and "role" in step3


def test_overlay_severity_override_in_stage_4():
    s4 = STAGES[4].read_text()
    cap = "Second-pack findings are capped at \"Weakens a claim\" unless they undermine the main claim."
    assert cap in s4
    after = s4.split(cap, 1)[1][:600]
    assert "`run.json` `overlays`" in after and "main treatment or main outcome" in after
    assert "severity rules" in after


def test_resume_drops_pack_flags_answered_b_again():
    s1 = STAGES[1].read_text()
    assert "`numbers:arith:*`, `numbers:text:*`, or `numbers:pack:*` flag answered B" in s1


def test_stage_4_compiler_applies_joint_rules():
    s4 = STAGES[4].read_text()
    assert "`## Joint rule` sections" in s4 and "applies the pack's severity rules" in s4


def test_fingerprint_lists_nonlinear_terms_with_roles():
    text = (SKILL / "agents/manuscript-audit.md").read_text()
    template = text.split("# Fingerprint", 1)[1].split("```", 1)[0]
    assert "Nonlinear terms:" in template and "<kind>; model: <model>; role: <role>" in template
    for kind in ("squared term", "three-way interaction", "log-like outcome with zeros", "subsample comparison"):
        assert kind in text, kind
    for model in ("logit or probit", "count", "hazard"):
        assert model in text, model
    assert "main hypothesis" in text and "other hypothesis" in text and "at most two terms have this role" in text
    assert "Do not list a term with neither role" in text
    assert "List the nonlinear overlay under `Overlays:` only when `Nonlinear terms:` is not \"none\"." in text


def test_pack_scripts_run_inside_their_verify_agent():
    step4 = STAGES[1].read_text().split("\n4. ", 1)[1].split("\n", 1)[0]
    assert "and scripts, if any" not in step4
    assert "A pack's scripts are run by its own verify agent; the orchestrator runs none." in step4


def test_filled_cells_redispatch_pack_verify_agents():
    line = next(l for l in STAGES[1].read_text().splitlines() if "re-run `verify_arithmetic.py` from step 2" in l)
    assert "`## Not computed`" in line and "`run.json` `packs`" in line and "before round 2" in line


def test_pack_flag_table_and_cells_reach_flags_json():
    s1 = STAGES[1].read_text()
    assert "When a pack flag's line ends with `Table:` and `Cells:`, copy them into the record's `table` and `cells`." in s1


def test_stage_1_writes_dropped_flags():
    s1 = STAGES[1].read_text()
    step5 = s1.split("\n5. ", 1)[1].split("\n6. ", 1)[0]
    resume = s1.split("\nResume.", 1)[1]
    assert "{WORKSPACE}/stage-1/dropped_flags.md" in step5 and '"None."' in step5
    assert "`dropped_flags.md` from the round 2 items answered B" in resume


def test_read_checkin_shows_every_overlay_line():
    step3 = STAGES[2].read_text().split("\n3. ", 1)[1].split("\n4. ", 1)[0]
    assert "`Nonlinear terms:` for nonlinear" in step3 and "`Generated variables:` for computational" in step3
    assert "the pack lines do not count toward that cap" in step3 and "`core_adjust` `read_lines`" in step3


def test_stage_4_cap_names_nonlinear_main_hypothesis():
    s4 = STAGES[4].read_text()
    assert "generated variable or nonlinear term whose role" in s4
    assert "or main hypothesis (a nonlinear term)" in s4


def test_stage_4_compiler_merges_duplicate_issues():
    s4 = STAGES[4].read_text()
    assert ("When two source files raise the same problem about the same variable, term, table, or hypothesis, "
            "write one issue "
            "that carries the evidence from both and the severity that the owning pack's rules set, or, when no pack owns it, "
            "the better-evidenced of the two.") in s4


def test_read_checkin_shows_role_lines_for_every_pack_in_run_json():
    step3 = STAGES[2].read_text().split("\n3. ", 1)[1].split("\n4. ", 1)[0]
    assert "For each pack in `run.json` `packs`, add in plain words" in step3
    assert "When `run.json` `overlays` is not empty" not in step3
    assert "whether the pack runs as the paper's type or as an overlay" in step3


def test_fixture_pending_is_logged_only_for_packs_in_run_json():
    s0 = STAGES[0].read_text()
    step4 = s0.split("\n4. ", 1)[1].split("\n", 1)[0]
    step13 = s0.split("\n13. ", 1)[1]
    assert "fixture pending" not in step4
    assert "fixture pending" in step13 and "`pending_planting`" in step13


def test_pack_flags_offer_not_a_problem_or_misread():
    s1 = STAGES[1].read_text()
    assert 'for a `numbers:pack:*` item, "B. Not a problem or misread"' in s1
    assert '"B. Extraction error"' in s1


def test_resume_builds_dropped_flags_from_round_2():
    resume = STAGES[1].read_text().split("\nResume.", 1)[1]
    assert "`dropped_flags.md` from the round 2 items answered B" in resume


def test_copied_table_redispatches_pack_verify_agents():
    line = next(l for l in STAGES[1].read_text().splitlines() if "re-run `verify_arithmetic.py` from step 2" in l)
    assert "a cell of a table copied in at round 1" in line


def test_stage_4_merge_without_an_owning_pack():
    s4 = STAGES[4].read_text()
    assert "or, when no pack owns it, the better-evidenced of the two." in s4


# --- Post-1e items 1, 3, and 5 (Plans 2a Task 3, 2b Task 2, 2c Task 4), in Plan 1e's step numbers ---

def _step(text, n):
    return text.split(f"\n{n}. ", 1)[1].split(f"\n{n + 1}. ", 1)[0]


def test_overlay_question_is_asked_only_when_detected():
    step11 = _step(STAGES[0].read_text(), 11)
    assert "setup:overlay:<pack>" in step11
    assert "A. Run the <pack> checks (Recommended)" in step11 and "B. Skip them" in step11
    assert "When no overlay is listed, ask none." in step11 and "Overlays:" in step11


def test_overlay_question_is_skipped_when_the_type_already_runs_the_pack():
    step11 = _step(STAGES[0].read_text(), 11)
    assert "already chosen as" in step11


def test_overlay_question_is_a_preference():
    step11 = _step(STAGES[0].read_text(), 11)
    assert "setup:overlay" in step11 and "--note preference" in step11


def test_overlay_question_is_one_question_except_at_hands_on():
    step11 = _step(STAGES[0].read_text(), 11)
    assert "each overlay that `fingerprint.md` lists under `Overlays:`" in step11
    assert "I found computational measures" not in step11
    assert "the nonlinear terms for nonlinear" in step11
    light = step11.split("At Light and Standard, ASK one screen", 1)[1].split("At Hands-on", 1)[0]
    assert '"A. Run all of them (Recommended)" / "B. Skip some"' in light and "`setup:overlays`" in light
    assert "Record every overlay under `setup:overlay:<pack>`" in light
    hands_on = step11.split("At Hands-on", 1)[1]
    assert "one question for each overlay" in hands_on


def test_auto_asks_nothing_in_round_2_and_records_auto_answers():
    step11 = _step(STAGES[0].read_text(), 11)
    auto = step11.split("At Auto, ASK nothing.", 1)[1].split("At Light and Standard", 1)[0]
    assert "a scripted run gives them in its prompt" in auto and "--note auto" in auto


def test_run_json_packs_come_from_run_packs():
    step13 = _step(STAGES[0].read_text(), 13)
    assert "plumb run-packs {PLUGIN}/packs" in step13
    for key in ('"packs"', '"overlays"', '"types_without_pack"', '"primary_pack"'):
        assert key in step13, key


def test_run_json_passes_each_chosen_overlay():
    step13 = _step(STAGES[0].read_text(), 13)
    assert "one `--overlay <pack>` for each `setup:overlay:<pack>` question answered A" in step13
    assert "`--overlay computational` when" not in step13
    assert step13.index("plumb run-packs") < step13.index("plumb core-adjust") < step13.index("plumb stops")


# --- Post-1e items 2 and 7 (Plan 2a Task 11, Plan 2c Task 15): one ## Packs section ---

def test_readme_and_spec_describe_the_computational_overlay():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    spec = (ROOT / "docs" / "spec.md").read_text(encoding="utf-8")
    assert "## Packs and core checks" not in readme and readme.count("\n## Packs\n") == 1
    section = readme.split("\n## Packs\n", 1)[1].split("\n## ", 1)[0]
    assert "- **Archival** runs when you choose an archival paper type" in section
    assert "- **Computational** is an overlay." in section
    order = ["- **Computational** is an overlay.", "Papers of a type with no pack get the core checks only",
             "turn off core checks", "significance star"]
    assert [section.index(s) for s in order] == sorted(section.index(s) for s in order)
    folder = spec.split("A pack is a folder:", 1)[1].split("\n", 1)[0]
    assert "A pack may set `overlay: true`." in folder and "Seven packs are overlays: computational, nonlinear, inference, market-event" in folder
    assert spec.index("If the user overrides the detected contribution type, the output says so.") < spec.index(
        "A pack changes the core only through three `pack.yaml` fields")
