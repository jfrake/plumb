from __future__ import annotations
import re
from pathlib import Path
from plumb import checkin, depth

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/review"
STAGES = {n: SKILL / "stages" / name for n, name in enumerate([
    "stage-0-intake.md", "stage-1-verify.md", "stage-2-understand.md", "stage-3-theory.md",
    "stage-4-diagnose.md", "stage-5-synthesize.md", "stage-6-audit.md", "stage-7-output.md"])}

def _built():
    return {n: p for n, p in STAGES.items() if p.exists()}

def test_skill_lists_stages_in_order():
    text = (SKILL / "SKILL.md").read_text()
    positions = [text.find(f"stages/{p.name}") for p in STAGES.values()]
    assert all(pos >= 0 for pos in positions) and positions == sorted(positions)

def test_all_eight_stage_files_exist():
    missing = [p.name for p in STAGES.values() if not p.exists()]
    assert not missing, missing

def test_every_agent_reference_exists():
    missing = []
    for p in list(_built().values()) + [SKILL / "SKILL.md"] + sorted((SKILL / "agents").glob("*.md")):
        for ref in re.findall(r"agents/[a-z0-9_-]+\.md", p.read_text()):
            if not (SKILL / ref).exists():
                missing.append(f"{p.name} -> {ref}")
    assert not missing, missing

def test_checkin_markers_sit_in_the_right_stage():
    for stop, stage in checkin.STOP_STAGE.items():
        p = STAGES[stage]
        if p.exists():
            assert f"<!-- CHECKIN: {stop} -->" in p.read_text(), f"{p.name} lacks CHECKIN {stop}"

def test_every_checkin_marker_is_a_valid_stop():
    # Stage 5 also escalates under the majors stop (Ruling 31), so a stop may appear after its own stage.
    bad = []
    for n, p in STAGES.items():
        for stop in re.findall(r"<!-- CHECKIN: ([^ ]+) -->", p.read_text()):
            if stop not in checkin.STOP_STAGE:
                bad.append(f"{p.name}: unknown stop {stop}")
            elif checkin.STOP_STAGE[stop] > n:
                bad.append(f"{p.name}: stop {stop} is not reached until stage {checkin.STOP_STAGE[stop]}")
    assert not bad, bad

ACTIONS = ["ASK", "DISPATCH", "PARALLEL", "TASKLIST", "WEB", "RUN"]

def test_every_platform_reference_defines_every_action():
    for plat in ("claude-code", "claude-desktop", "codex"):
        text = (SKILL / "references" / f"{plat}.md").read_text()
        for act in ACTIONS:
            assert f"## {act}" in text, f"{plat}.md lacks {act}"

def test_stage_files_name_no_platform_tools():
    for p in _built().values():
        text = p.read_text()
        for tool in ("AskUserQuestion", "spawn_agent", "Task tool", "TodoWrite", "TaskCreate"):
            assert tool not in text, f"{p.name} names platform tool {tool}"

def test_check_numbers_alias_routes_to_review():
    text = (ROOT / "skills/check-numbers/SKILL.md").read_text()
    assert "review" in text and "Quick" in text

def test_checkins_only_in_orchestrator_files():
    for p in (SKILL / "agents").glob("*.md"):
        assert "AskUserQuestion" not in p.read_text(), f"{p.name}: agents cannot ask the user"

def test_no_recommendation_language_in_output_prompts():
    for p in list((SKILL / "agents").glob("*.md")) + list(_built().values()):
        text = p.read_text()
        assert not re.search(r"(one-word|bare) recommendation|Reject, Major R&R|base rates", text, re.I), p.name

def test_advocate_pages_file_wired_from_stage_3_to_stage_6():
    theory = (SKILL / "stages/stage-3-theory.md").read_text()
    diagnose = (SKILL / "stages/stage-4-diagnose.md").read_text()
    audit = (SKILL / "stages/stage-6-audit.md").read_text()
    advocate = (SKILL / "agents/papers-advocate.md").read_text()
    assert "stage-6/advocate_pages.md" in theory, "stage 3 does not append to advocate_pages.md"
    assert "against:<n>:" in theory
    assert "stage-6/advocate_pages.md" in diagnose, "stage 4 does not append to advocate_pages.md"
    assert "majors:<n>:" in diagnose
    assert "stage-6/advocate_pages.md" in audit, "stage 6 does not pass advocate_pages.md to the advocate"
    assert "stage-6/advocate_pages.md" in advocate, "papers-advocate.md does not read advocate_pages.md"
    # Blinding: the file that reaches the blinded advocate never holds discovery output.
    assert "never" in advocate or "not a discovery" in advocate

def test_pack_agents_run_only_for_packs_in_run_json():
    # Architecture review I-4: slot agents run only for the packs Stage 0 recorded.
    pack_agents = {p.name for p in (ROOT / "packs").glob("*/agents/*.md")}
    slot_line = re.compile(r"`(verify|context|theory|diagnose)` slot")
    bad = []
    for p in _built().values():
        for i, line in enumerate(p.read_text().splitlines(), 1):
            if slot_line.search(line) and "`run.json` `packs`" not in line:
                bad.append(f"{p.name}:{i} dispatches slot agents without restricting to run.json packs")
            for name in pack_agents:
                if name in line:
                    bad.append(f"{p.name}:{i} names pack agent {name} directly")
    assert not bad, bad
    intake = STAGES[0].read_text()
    assert '"packs"' in intake and '"types_without_pack"' in intake


def test_mechanical_dispatches_are_marked():
    mech_agents = [f"agents/{m}.md" for m in depth.MECHANICAL if m != "compiler"]
    bad = []
    for p in (SKILL / "stages").glob("*.md"):
        for i, line in enumerate(p.read_text().splitlines(), 1):
            low = line.lower()
            names_mech = any(a in line for a in mech_agents) or ("compiler" in low and "dispatch" in low and "(judgment)" not in line)
            if names_mech and "(mechanical)" not in line:
                bad.append(f"{p.name}:{i} dispatches a mechanical agent without (mechanical)")
            if "(mechanical)" in line and not names_mech:
                bad.append(f"{p.name}:{i} marks a non-mechanical line (mechanical)")
    assert not bad, bad


def test_every_platform_reference_says_how_to_pass_the_model():
    for plat in ("claude-code", "claude-desktop", "codex"):
        text = (SKILL / "references" / f"{plat}.md").read_text()
        dispatch = text.split("## DISPATCH", 1)[1].split("\n## ", 1)[0]
        assert "model" in dispatch and "inherit" in dispatch, plat
        assert "turn" in dispatch, plat


def test_skill_md_routes_models_and_deep_guidance():
    text = (SKILL / "SKILL.md").read_text()
    assert "plumb models <depth>" in text and "(mechanical)" in text
    assert "Deep depth: you may take up to" in text


def test_quick_depth_wiring():
    stage1 = (SKILL / "stages/stage-1-verify.md").read_text()
    stage2 = (SKILL / "stages/stage-2-understand.md").read_text()
    stage7 = (SKILL / "stages/stage-7-output.md").read_text()
    assert "scripts/check_reference_list.py" in stage1
    assert "At depth `quick`, run steps 1, 3, and 4 only" in stage2
    assert "stage-1/reference_list.md" in stage7 and "summary_for_user.md" in stage7
    assert "Stages 0, 1, 2, and 7 run" in (SKILL / "SKILL.md").read_text()


def test_check_numbers_describes_quick():
    text = (ROOT / "skills/check-numbers/SKILL.md").read_text()
    for phrase in ("reference list", "read the paper", "arithmetic", "Deep"):
        assert phrase in text, phrase


def test_dig_deeper_logged_and_counted_separately():
    diagnose = (SKILL / "stages/stage-4-diagnose.md").read_text()
    output = (SKILL / "stages/stage-7-output.md").read_text()
    template = (SKILL / "shared/checkin-template.md").read_text()
    assert "dig_deeper" in diagnose
    # Stage 7's closing sentence reports this count in plain words, not the raw field name
    # (run voice fix round 1, item 1): the field itself is never spoken to the user.
    assert "plumb counts {WORKSPACE}" in output and "look deeper" in output
    assert '--note "free text"' in template


def test_stage_6_wires_the_stress_test():
    audit_stage = (SKILL / "stages/stage-6-audit.md").read_text()
    assert "runner not ported" not in audit_stage
    assert "plumb stress-test-decision {WORKSPACE}" in audit_stage
    assert "scripts/codex_stress_test.py" in audit_stage and "shared/stress-test-prompt.md" in audit_stage
    assert "stage-6/stress_test/summary.json" in audit_stage
    intake = (SKILL / "stages/stage-0-intake.md").read_text()
    assert "OpenAI" in intake and '"stress_test_provider"' in intake and '"needs_zero_retention"' in intake


# Final review I2: models and limits are set before the first dispatch in Stage 0.
def test_stage_0_sets_models_and_limits_before_any_dispatch():
    intake = STAGES[0].read_text()
    first_dispatch = intake.index("9. Only now do the PDF checks and dispatch agents")
    assert intake.index("plumb models <depth>") < first_dispatch
    assert intake.index("plumb limits <depth>") < first_dispatch
    assert intake.index("<!-- CHECKIN: setup -->") < intake.index("plumb models <depth>")
    assert "plumb models <depth>" not in intake[first_dispatch:]


# Final review I1: one record per final answer; follow-ups go in its note.
def test_follow_ups_are_recorded_in_the_single_record():
    skill = (SKILL / "SKILL.md").read_text()
    assert "After every answer" not in skill and "final answer once" in skill
    theory = STAGES[3].read_text()
    diagnose = STAGES[4].read_text()
    assert "add the reply to the" not in theory + diagnose
    assert "before recording it" in theory and "before recording it" in diagnose
    assert '--note "p.<page>: <one-line claim>"`' in theory and '--note "p.<page>: <one-line claim>"`' in diagnose


# Final review m3: every level fallback records with --note auto.
def test_every_level_fallback_uses_the_auto_note():
    for n, p in _built().items():
        text = p.read_text()
        for m in re.finditer(r"record it the same way", text):
            assert text[m.end():m.end() + 20].startswith(" with `--note auto`"), (p.name, m.start())
    template = (SKILL / "shared/checkin-template.md").read_text()
    assert "--note auto" in template and "auto_answers" in (SKILL / "SKILL.md").read_text()


# Final review m2, m4, m6.
def test_resume_rebuilds_stops_limits_and_models():
    skill = (SKILL / "SKILL.md").read_text()
    resume = skill.split("## Resume", 1)[1].split("## Stages", 1)[0]
    for cmd in ("plumb stops <level> <depth>", "plumb limits <depth>", "plumb models <depth>", '"tier"'):
        assert cmd in resume, cmd


def test_codex_reference_never_passes_claude_models():
    text = (SKILL / "references/codex.md").read_text()
    assert "--platform codex" in text and "Never pass a Claude model" in text


def test_quick_memo_handles_a_missing_summary():
    stage7 = STAGES[7].read_text()
    assert "If `summary_for_user.md` does not exist" in stage7

def test_alternatives_carry_full_context():
    devil = (SKILL / "agents/theory-devil.md").read_text()
    for heading in ("## The paper's explanation", "How it would produce the results:",
                    "Which results it could explain:", "What would tell them apart:"):
        assert heading in devil, heading
    stage3 = STAGES[3].read_text()
    assert "the paper's explanation" in stage3 and "in full" in stage3

def test_major_issue_cards_carry_full_context():
    stage4 = STAGES[4].read_text()
    for heading in ("What the paper claims:", "The problem:", "Why it matters:",
                    "What would settle it:"):
        assert heading in stage4, heading
    assert "compiler (judgment)" in stage4
    assert "Before each card's question, paste that issue in full" in stage4

def test_stage_6_runs_the_stress_test_with_codex_or_claude():
    from plumb import consent
    step = STAGES[6].read_text().split("\n3. ", 1)[1].split("\n4. ", 1)[0]
    assert "Standard and Deep" in step and "never a gate" in step
    assert '"engine":"codex"' in step and '"engine":"claude"' in step
    assert "--mode prepare --engine claude" in step and "--mode summarize --engine claude" in step
    assert "agents/stress-tester.md" in step and "never the mechanical model" in step
    assert '"check":"claude_stress_test"' in step and '"check":"codex_stress_test"' in step
    tester = (SKILL / "agents/stress-tester.md").read_text()
    assert "shared/stress-test-prompt.md" in tester and "input/points.json" in tester
    assert "—" not in tester and "—" not in step
    intake = STAGES[0].read_text()
    assert "If the depth is `standard` or `deep`" in intake
    assert "At Standard and Deep depth, an optional Codex stress test" in intake
    setup = (ROOT / "skills/setup/SKILL.md").read_text()
    assert "stress test at Standard and Deep depth" in setup and "stress test at Deep depth" not in setup
    assert consent.EGRESS_RECIPIENTS["codex_stress_test"] == "OpenAI, through the Codex CLI (stress test)"

def test_stress_tester_dispatch_is_exempt_from_default_dispatch_contents():
    step = STAGES[6].read_text().split("\n3. ", 1)[1].split("\n4. ", 1)[0]
    assert "one exception to SKILL.md's rules" in step
    assert "do not pass `PDF_PATH`, `PAGE_COUNT`, or `shared/contracts.md`" in step
    skill = (SKILL / "SKILL.md").read_text()
    assert "stress tester" in skill and "Stage 6 step 3" in skill
    assert "receives none of this" in skill
    tester = (SKILL / "agents/stress-tester.md").read_text()
    assert "Do not open the PDF or any file outside" in tester
    assert "stage-6/stress_test/input/" in tester and "other than the prompt file" in tester

def test_usage_is_marked_recorded_and_reported():
    skill = (SKILL / "SKILL.md").read_text()
    assert "plumb usage stage-end {WORKSPACE} <N>" in skill
    resume = skill.split("## Resume", 1)[1].split("## Stages", 1)[0]
    assert resume.index("plumb usage mark {WORKSPACE}") < resume.index("plumb migrate-run {WORKSPACE}")
    intake = STAGES[0].read_text()
    step1 = intake.split("\n1. ", 1)[1].split("\n2. ", 1)[0]
    assert "plumb usage mark {WORKSPACE} --cwd <project dir>" in step1
    assert intake.count("plumb usage mark {WORKSPACE}") == 2
    output = STAGES[7].read_text()
    assert output.index("plumb usage report {WORKSPACE}") < output.index("plumb render-audit {WORKSPACE}")
    assert "Usage not measured in this app." in output and "API-equivalent" in output
    for plat in ("claude-code", "claude-desktop", "codex"):
        assert "## Usage" in (SKILL / "references" / f"{plat}.md").read_text(), plat
    assert "Usage not measured in this app." in (SKILL / "references/claude-desktop.md").read_text()

def test_readme_and_spec_describe_the_stress_test_and_usage():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "## Tokens, time, and cost" in readme and "Usage not measured in this app." in readme
    assert "API-equivalent" in readme and "not what you pay" in readme and "plumb/prices.json" in readme
    assert "At Standard and Deep depth, Plumb can use Codex" in readme and "a fresh Claude agent" in readme
    assert "Deep also runs the Codex stress test" not in readme and "—" not in readme
    spec = (ROOT / "docs/spec.md").read_text(encoding="utf-8")
    assert "(Deep only)" not in spec and "It runs only as a stress test at Deep depth." not in spec
    assert "Deep also runs the optional Codex stress test." not in spec
    assert "API-equivalent cost by stage and by model" in spec and "SubagentStop and Stop" in spec

def test_stress_test_is_never_described_as_skipped_and_the_adjudicator_gets_only_its_results():
    # Final ruling: when consent does not cover OpenAI, the Claude agent runs the stress test; and
    # the adjudicator reads the stress test's results, never its inputs or usage counts.
    intake = STAGES[0].read_text()
    assert "Stage 6 skips it" not in intake
    assert "if they do not cover OpenAI, a fresh Claude agent runs the stress test in Stage 6 instead" in intake
    spec = (ROOT / "docs/spec.md").read_text(encoding="utf-8")
    assert "or the stress test is skipped" not in spec
    assert "or a fresh Claude agent runs the stress test instead; the run continues." in spec
    step4 = STAGES[6].read_text().split("\n4. ", 1)[1].split("\n5. ", 1)[0]
    assert "with every stage-6 file," not in step4
    assert "`stage-6/stress_test/summary.json` and the per-point `<point_id>.json` files" in step4
    assert "never `stage-6/stress_test/input/` or `stage-6/stress_test/usage.json`" in step4
    assert "—" not in step4

def test_consent_screen_asks_author_consent_only_when_the_journal_requires_it():
    stage0 = STAGES[0].read_text()
    assert "Do not ask whether the author consented at submission" in stage0
    assert "requires_author_consent" in stage0


# Run voice (spec 2026-09-28): what the chat shows, in the first person and in plain words.
INTERNAL_TERMS = (
    "theory devil", "summary compiler", "compiler", "adjudicator", "orchestrator", "subagent",
    "synthesis critic", "advocate", "standards auditor", "missed criticisms", "stress tester",
    "table transcriber", "numeric fidelity", "ledger checker", "ledger producer", "contribution auditor",
    "manuscript audit", "skeptical reviewer", "developmental advisor", "issues-list writer",
    "report writer", "memo writer", "hard gate", "advisory", "verdict", "frontier", "dispatch",
    "validated.json", "brief.md", "run.json", "issues.json", "run_log", "questions.json",
)
PLUMB_AS_SUBJECT = re.compile(
    r"\bPlumb (?:can(?:not)?|could|will|would|does|did|is|was|has|had|may|might|should|[a-z]+s)\b")


def _chat_strings():
    """What the orchestrator says or asks: double-quoted text outside backtick spans in SKILL.md,
    the check-in template, and the stage files. Text inside backticks is a command, a file, or a
    message to an agent."""
    out = []
    for p in [SKILL / "SKILL.md", SKILL / "shared/checkin-template.md"] + list(STAGES.values()):
        text = re.sub(r"`[^`\n]*`", "", p.read_text(encoding="utf-8"))
        out += [(p.name, s) for s in re.findall(r'"([^"\n]+)"', text)]
    return out


def test_chat_text_names_no_agent_file_gate_or_verdict():
    hits = [f"{name}: {term!r} in {s!r}" for name, s in _chat_strings()
            for term in INTERNAL_TERMS if term in s.lower()]
    assert not hits, hits


def test_plumb_is_never_the_subject_of_chat_text():
    from plumb import profiles
    files = [SKILL / "SKILL.md", SKILL / "shared/checkin-template.md", ROOT / "skills/setup/SKILL.md"]
    hits = [f"{p.name}: {m.group(0)}" for p in files + list(STAGES.values())
            for m in PLUMB_AS_SUBJECT.finditer(p.read_text(encoding="utf-8"))]
    for pid in ("orgsci", "mansci", "generic"):
        prof = profiles.load_profile(ROOT / "profiles", pid)
        for wanted in (["report"], ["issues_list", "report"], ["issues_list"]):
            d = profiles.referee_decision(prof, wanted, self_confirmed=True)
            hits += [f"{pid} reason: {r}" for r in d.reasons if PLUMB_AS_SUBJECT.search(r)]
    assert not hits, hits


def test_skill_md_gives_the_chat_formats_and_voice():
    skill = (SKILL / "SKILL.md").read_text()
    chat = skill.split("## What the chat shows", 1)[1].split("\n## ", 1)[0]
    for s in ("plumb stage-header <depth> <N>", "Stage 3 of 8: Theory, about 10 to 15 minutes (estimate).",
              "Provisional: <what I found> (<source>). <why it may matter>.", "Stage 1 done. Two things matter most:",
              "plumb scoreboard {WORKSPACE}", "| Stage | Status | Found | Needs you |",
              'plumb runlog {WORKSPACE} "<what happened>"', "I checked the tables", "Never make \"Plumb\" the subject",
              "I'm waiting on <what>, about <N> minutes.", "(round 2 of 2)", "shared/checkin-template.md"):
        assert s in chat, s
    assert "Scoreboard <N>: <status> | <found> | <needs you>" in skill
    assert "voice rules in SKILL.md" in (SKILL / "shared/checkin-template.md").read_text()
    output = STAGES[7].read_text()
    assert output.index("plumb scoreboard {WORKSPACE}") > output.index("plumb counts {WORKSPACE}")
    assert "—" not in chat


# Run voice fix round 1 (task-3-review.md Important 1-3): three leak points a real run would
# still hit past the original brief's edit list.
VERDICT_POINTER = ('Report the result in chat by the voice rules in SKILL.md, never the verdict '
                    'word or the agent name.')
COUNTS_SENTENCE_BANNED = ("upheld", "overruled", "reframed", "override", "delegations",
                           "auto_answers", "the tool")


def test_stage_3_and_5_verdict_points_point_to_the_voice_rules():
    theory = STAGES[3].read_text()
    synthesize = STAGES[5].read_text()
    assert VERDICT_POINTER in theory
    assert VERDICT_POINTER in synthesize


def _stage_7_counts_sentence() -> str:
    output = STAGES[7].read_text()
    return output.split("Run `plumb counts {WORKSPACE}`.", 1)[1].split("Then append this stage's", 1)[0]


def test_stage_7_counts_sentence_has_no_verdict_labels_or_field_names_in_what_is_spoken():
    sentence = _stage_7_counts_sentence()
    # Parenthetical read-pointers are instructions to the model, not spoken text (fix round 2):
    # strip them before checking what the user actually hears.
    spoken = re.sub(r"\([^)]*\)", "", sentence).lower()
    hits = [t for t in COUNTS_SENTENCE_BANNED if t in spoken]
    assert not hits, hits
    assert "kept, dropped, or reworded" in sentence
    assert "look deeper" in sentence
    assert "as a separate number" in sentence


def test_stage_7_counts_sentence_names_its_read_pointers():
    # Fix round 2 (task-3-rereview-1.md): the sentence must still tell the model which
    # `plumb counts` key backs each spoken clause, and where the qc.md-derived counts come
    # from, clearly marked as read, never spoken.
    sentence = _stage_7_counts_sentence()
    for key in ("override", "user_answers", "delegations", "auto_answers", "dig_deeper"):
        assert f"`{key}`" in sentence, key
    assert "qc.md" in sentence
    assert "do not say" in sentence


def test_skill_md_resolves_the_revision_cycle_contradiction():
    skill = (SKILL / "SKILL.md").read_text()
    # The old wording put "revision cycles" in the same breath as "never to the chat", which
    # contradicted the Voice section's own revision-cycle chat line just below it.
    assert "page-span fixes, and revision cycles" not in skill
    chat = skill.split("## What the chat shows", 1)[1].split("\n## ", 1)[0]
    assert "only when it adds time" in chat
    rules = skill.split("## Rules that apply everywhere", 1)[1]
    assert 'Log every dispatch, command, retry, and revision cycle with `plumb runlog {WORKSPACE} "<line>"`' in rules


# Errors and guards (spec 2026-09-28, section 5).
NO_SHELL_WRITES = "(no heredoc, no `echo >`, no `cat >`, no `tee`)"
SHELL_WRITE = re.compile(r"\bcat\s*>|\bcat\s*<<|<<-?\s*['\"]?[A-Z][A-Z_]*['\"]?|\becho\b[^\n`]*\s>>?\s*\S"
                         r"|\bprintf\b[^\n`]*\s>>?\s*\S|\|\s*tee\b|\btee\s+-?a?\s*\S")


def test_no_stage_or_agent_file_writes_a_file_through_the_shell():
    files = sorted(ROOT.glob("skills/**/*.md")) + sorted(ROOT.glob("packs/**/*.md"))
    hits = [f"{p.relative_to(ROOT)}: {m.group(0)!r}" for p in files
            for m in SHELL_WRITE.finditer(p.read_text(encoding="utf-8").replace(NO_SHELL_WRITES, ""))]
    assert not hits, hits


def test_the_file_writing_rule_reaches_the_orchestrator_and_every_agent():
    skill = (SKILL / "SKILL.md").read_text()
    assert NO_SHELL_WRITES in skill and "file-writing tool" in skill
    contracts = (SKILL / "shared/contracts.md").read_text()
    assert NO_SHELL_WRITES in contracts and "Contracts in [shared/contracts.md](shared/contracts.md) bind every agent" in skill
    # The stress tester gets no contracts.md, so it carries the rule itself.
    assert "file-writing tool, never through a shell command" in (SKILL / "agents/stress-tester.md").read_text()


def test_warnings_blocked_writes_and_the_one_workaround():
    rules = (SKILL / "SKILL.md").read_text().split("## Rules that apply everywhere", 1)[1]
    for s in ("never as \"failed\"", "Text quality: fair. Continuing.",
              "This is the only allowed workaround", '"name":"write_blocked"', 'plumb runlog {WORKSPACE} "',
              "outside `{RUN}`", "never work around it"):
        assert s in rules, s
    step9 = STAGES[0].read_text().split("\n9. ", 1)[1].split("\n10. ", 1)[0]
    assert "Exit 1 is a warning, never a failure" in step9 and '"Text quality: fair. Continuing."' in step9
    assert "A warning is never a reason to read the paper yourself" in rules


def test_the_blocked_write_workaround_is_plumb_put_not_a_shell_command():
    # Fix round 1 (task-4-review.md): the workaround must not tell the model to fall back to a
    # shell command, the exact technique the hooks this rule exists for are described as blocking.
    rules = (SKILL / "SKILL.md").read_text().split("## Rules that apply everywhere", 1)[1]
    assert "plumb put" in rules
    assert "a shell command, if the file-writing tool was blocked" not in rules


# Final review I4 and I5 (2026-09-29).
def test_stage_7_draft_review_says_each_ruling_in_plain_words():
    step5 = STAGES[7].read_text().split("\n5. ", 1)[1].split("\n6. ", 1)[0]
    ruling = step5.split("one question per major-issue ruling", 1)[1].split("Options:", 1)[0]
    assert "in plain words" in ruling and "never its tag or its section name" in ruling


def test_skill_md_carves_out_setup_stops_and_check_ins_from_nothing_else():
    skill = (SKILL / "SKILL.md").read_text()
    first = skill.split("## What the chat shows", 1)[1].split("\n\n", 2)[1]
    for s in ("setup questions", "the recap", "stop messages", "check-in screens", "a stage file tells you to say"):
        assert s in first, s


# Ruling 21 (#34): every answer the tool takes at a skipped stop names its item id, so Judgment
# calls can be matched across Auto runs. The minors stop has no mode at light or auto, so its
# fallback must say which item id it records under.
def test_minors_fallback_names_its_item_id():
    text = STAGES[5].read_text()
    assert ("At levels where the `minors` stop is not asked, take A under `minors:list` and record it the "
            "same way with `--note auto`.") in text
