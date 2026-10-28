"""The stage, agent, and reference files agree with the output design: several outputs, the
run folder, validated issues, and working PDFs at the check-ins."""
from __future__ import annotations
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/review"
STAGES = SKILL / "stages"
AGENTS = SKILL / "agents"


def _stage(n: int) -> str:
    return next(STAGES.glob(f"stage-{n}-*.md")).read_text(encoding="utf-8")


def test_no_agent_reads_a_report_draft():
    hits = [p.name for p in AGENTS.glob("*.md")
            if "draft.txt" in p.read_text(encoding="utf-8") or "draft.<md|txt>" in p.read_text(encoding="utf-8")]
    assert not hits, hits


def test_synthesis_always_writes_draft_md_with_the_fields_validated_reads():
    text = (AGENTS / "synthesis.md").read_text(encoding="utf-8")
    assert "If `run.json` says `report`" not in text
    for field in ('"kind"', '"summary"', '"ms_page"', '"checkin"', "`numbers:text:3`"):
        assert field in text, field
    assert "always in issues-list format" in _stage(5)


def test_adjudicator_writes_the_surviving_issues():
    text = (AGENTS / "adjudicator.md").read_text(encoding="utf-8")
    assert "{WORKSPACE}/stage-6/issues.json" in text and "Leave out an issue you cut" in text
    assert "majors and minors" in text and "with its original `id` and `checkin`" in text
    assert "`{WORKSPACE}/stage-6/issues.json`, the issues that survived the audit" in _stage(6)


def test_working_pdfs_at_the_numbers_and_majors_checkins():
    for n, name, source in ((1, "checkin_numbers_annotated.pdf", "stage-1/flags.json"),
                            (4, "checkin_majors_annotated.pdf", "stage-4/majors_cards.json")):
        text = _stage(n)
        assert f"Open {{WORKSPACE}}/{name} to see each flag on its page." in text
        assert "scripts/locate_issues.py" in text and "scripts/annotate_pdf.py" in text and source in text
    assert "- cell `<table>:<row>:<col>`" in _stage(1) and "`lookup_failed`" in _stage(1)
    assert "`Excerpt:`" in _stage(4)


def test_stage_0_asks_for_outputs_and_folder():
    intake = _stage(0)
    for s in ('"A. Issues list (Recommended)"', '"B. Annotated PDF (Recommended)"', '"C. Mock referee report"',
              "Leave out C at Quick depth.", "setup:output_dir",
              "plumb run-dir new <pdf>", "plumb run-dir move {RUN} <folder>", '`"outputs"`',
              '`"issues_list_mode"`', "plumb referee-decision {PLUGIN}/profiles <journal> <outputs>",
              '" + " in A, B, C order'):
        assert s in intake, s
    assert 'Output "Fix list"' not in intake
    assert intake.index("plumb run-dir new") < intake.index("<!-- CHECKIN: setup -->")
    # A resumed run keeps its folder; Quick is facts-only in every path; readme's keys are written.
    assert "When a resumed run reruns Stage 0, `{RUN}` and `{WORKSPACE}` are already set: skip `plumb run-dir new`." in intake
    assert "<outputs> --depth <depth>" in intake
    assert 'Include `"role"`, `"permission"`, `"journal"`, and `"level"`' in intake


def test_start_over_is_a_fresh_run_recorded_as_a_setup_answer():
    """Ruling 21 (#34): a repeat run never resumes an unfinished run, and the choice is on record."""
    skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    resume = skill.split("## Resume", 1)[1].split("## Stages", 1)[0]
    a_label = "A. Continue from where the last run stopped (Recommended)"
    for s in ("Item id `setup:resume`", "no stored default", "ask it at every resume",
              f'plumb checkin {{WORKSPACE}} setup setup:resume "{a_label}" "<chosen label>" --note preference',
              "Never re-ask a check-in, other than `setup:resume`, whose (stop, item) pair is already answered",
              "plumb run-dir new <pdf> --fresh", '`"unfinished_run"`', "the README names it"):
        assert s in resume, s
    # On A, {WORKSPACE} is set only inside the Continue list, so a Continue bullet must record the answer,
    # after the bullet that sets it (and runs adopt for a legacy run).
    bullets = resume.split('On "Continue":', 1)[1].split("\n\n", 1)[1].split("\n- ")
    record = f'plumb checkin {{WORKSPACE}} setup setup:resume "{a_label}" "{a_label}" --note preference'
    assert any(record in b for b in bullets), record
    assert bullets.index(next(b for b in bullets if record in b)) == bullets.index(
        next(b for b in bullets if "plumb run-dir adopt" in b)) + 1
    intake = _stage(0)
    step1 = intake.split("\n1. ", 1)[1].split("\n2. ", 1)[0]
    for s in ("adding `--fresh` after \"Start over\"", "never resumes the unfinished one",
              f'plumb checkin {{WORKSPACE}} setup setup:resume "{a_label}" "B. Start over" --note preference'):
        assert s in step1, s


def test_stage_0_asks_whose_permission_never_the_role():
    intake = _stage(0)
    for s in ('"A. It\'s mine or my coauthors\'"', '"B. The author asked me to read it"',
              '"C. A journal sent it to me for review"', "Item id `setup:permission`",
              '`"author_permission"`', "setup setup:permission"):
        assert s in intake, s
    assert "Whose paper is this" not in intake and "Reviewing it" not in intake and "setup:role" not in intake
    question = next(l for l in intake.splitlines() if "Item id `setup:permission`" in l)
    assert "role" not in question.lower()
    skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "a `setup:role` answer in place of `setup:permission`" in skill


def test_skill_md_run_folder_and_resume():
    skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    resume = skill.split("## Resume", 1)[1].split("## Stages", 1)[0]
    for s in ("plumb run-dir find <pdf>", "plumb run-dir adopt", "plumb migrate-run {WORKSPACE}",
              "leave that run folder as it is", "`~/.config/plumb/runs.json`", "and `--depth <depth>`",
              "(at Quick depth the mode is always `facts_only`)"):
        assert s in resume, s
    assert "`{RUN}/.workspace/`" in skill


def test_platform_references_cover_the_run_folder_and_multi_select():
    for plat in ("claude-code", "claude-desktop", "codex"):
        text = (SKILL / "references" / f"{plat}.md").read_text(encoding="utf-8")
        assert "## Run folder" in text and "--cwd" in text, plat
        assert "several answers" in text, plat
    assert "leave `--cwd` out" in (SKILL / "references/claude-desktop.md").read_text(encoding="utf-8")


def test_no_stage_names_the_old_layout():
    stale = ("review_workspace", "draft.txt", "fix_list.md", "memo.md")
    # "editor_memo.md" is the current editor memo, not the old "memo.md".
    hits = [f"{p.name}: {s}" for p in sorted(STAGES.glob("*.md")) for s in stale
            if re.search(r"(?<!\w)" + re.escape(s), p.read_text(encoding="utf-8"))]
    assert not hits, hits
    # SKILL.md names the old folder only to resume a run from before the output folder.
    assert "= `<paper_dir>/review_workspace/`" not in (SKILL / "SKILL.md").read_text(encoding="utf-8")


def test_writers_renamed_and_memo_writer_retired():
    assert not (AGENTS / "memo-writer.md").exists() and not (AGENTS / "fix-list-writer.md").exists()
    writer = (AGENTS / "issues-list-writer.md").read_text(encoding="utf-8")
    for s in ("MODE=full", "MODE=facts_only", "## Checked facts", "## Dropped items", "validated.json",
              "locations.json", "word for word", "{RUN}/issues_list.md"):
        assert s in writer, s
    report = (AGENTS / "report-writer.md").read_text(encoding="utf-8")
    for s in ("validated.json", "do not add a finding", "report_trace.json", "{RUN}/mock_report.txt"):
        assert s in report, s


def test_stage_7_runs_in_the_spec_order():
    out = _stage(7)
    order = ["plumb validated {WORKSPACE}", "scripts/locate_issues.py", "agents/issues-list-writer.md",
             "agents/report-writer.md", "scripts/annotate_pdf.py", "plumb validate-output issues_list",
             "plumb validate-output report", "scripts/verify_quotes.py", "scripts/verify_citations.py",
             "<!-- CHECKIN: draft -->", "plumb render-audit {WORKSPACE}", "plumb readme {WORKSPACE}",
             "`{RUN}/paper_summary.md`",
             "plumb log {WORKSPACE} output"]
    pos = [out.index(s) for s in order]
    assert pos == sorted(pos), order
    assert "--allow-missing-excerpt" in out and "report_trace.json" in out
    assert "asked once about all the chosen outputs together" in out
    assert "draft:drop:<source>" in out and "list each entry as not verified" not in out


def test_final_verification_runs_on_the_delivered_files():
    out = _stage(7)
    final = out.index("6. Final verification")
    assert out.index("`draft:ready`") < final and out.rindex("redo steps 1 to 4") < final
    tail = out[final:out.index("7. Finish the run folder")]
    for s in ("plumb validate-output issues_list", "plumb validate-output report", "--trace",
              "scripts/verify_quotes.py", "scripts/verify_citations.py", "plumb sha256",
              '"check":"final"', "Not verified:", "rebuild nothing after this step"):
        assert s in tail, s
    assert final < out.index("plumb render-audit {WORKSPACE}") < out.index("plumb readme {WORKSPACE}")
    assert "role" not in out.lower()


def test_minor_issue_lines_print_a_flat_label():
    writer = (AGENTS / "issues-list-writer.md").read_text(encoding="utf-8")
    assert "ms p. 4, PDF p. 4" in writer and "(<the issue's label>)" not in writer


def test_report_writer_lists_no_unverified_numbers():
    report = (AGENTS / "report-writer.md").read_text(encoding="utf-8")
    writer = (AGENTS / "issues-list-writer.md").read_text(encoding="utf-8")
    assert "unverified" not in report and "unverified_numbers" not in writer


def test_no_em_dash_in_new_user_facing_files():
    files = [STAGES / "stage-7-output.md", AGENTS / "report-writer.md", AGENTS / "issues-list-writer.md",
             SKILL / "scripts/locate_issues.py",
             SKILL / "scripts/annotate_pdf.py", ROOT / "plumb/rundir.py", ROOT / "plumb/validated.py"]
    hits = [p.name for p in files if "—" in p.read_text(encoding="utf-8")]
    assert not hits, hits


def test_report_leaves_out_minor_comments_when_no_minor_issue_survives():
    report = (AGENTS / "report-writer.md").read_text(encoding="utf-8")
    assert 'When no issue in `validated.json` has severity "Minor", leave out the `MINOR COMMENTS` section' in report


def test_final_check_of_the_annotated_pdf_logs_its_real_result():
    out = _stage(7)
    tail = out[out.index("6. Final verification"):out.index("7. Finish the run folder")]
    assert "annotate_pdf.py --check {RUN}/<paper-stem>_annotated.pdf" in tail
    assert '"step":"check"' in tail and '"step":"built"' not in tail


def test_readme_and_spec_describe_the_outputs():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for s in ("## Outputs", "## Where the files go", "**Issues list**", "**Annotated PDF**",
              "**Mock referee report**", "plumb_output/<date>/", "ms p. 30 (PDF p. 32)"):
        assert s in readme, s
    assert "verification memo" not in readme and "—" not in readme
    assert "role" not in readme.lower() and "sent you the paper for review" in readme
    spec = (ROOT / "docs/spec.md").read_text(encoding="utf-8")
    for old in ("the output is a **verification memo**", "or verification memo. Audit package",
                "the output is a verification memo, not a report", "memo writer", "At setup the user picks the output:"):
        assert old not in spec, old
    assert "checked facts only" in spec and "highlights each issue on its page" in spec
    # The original section 3 lines from 101615f stay as they are.
    assert "The tool NEVER asks the user's role." in spec and "**Annotated PDF.**" in spec


def test_issue_records_are_rederived_from_the_audited_draft():
    six = _stage(6)
    step = six.split("\n6. ", 1)[1]
    assert "after step 5" in step and "`agents/adjudicator.md`" in step
    for field in ("`summary`", "`excerpt`", "`ms_page`", "{WORKSPACE}/stage-6/draft.md"):
        assert field in step, field
    adj = (AGENTS / "adjudicator.md").read_text(encoding="utf-8")
    assert "Re-derive every issue's record from the audited draft" in adj
    assert "first sentence of its item in `{WORKSPACE}/stage-6/draft.md`, word for word" in adj
    seven = _stage(7)
    assert "Exit 3 lists issues whose summary is not in `stage-6/draft.md` word for word" in seven


def test_issues_list_writer_handles_no_major_and_no_issue():
    from plumb import outputs
    text = (AGENTS / "issues-list-writer.md").read_text(encoding="utf-8")
    assert f'When `validated.json` is empty, write the one line "{outputs.NO_ISSUES}" under `## Issues`' in text
    assert "When every issue is Minor, `## Issues` has no `###` item" in text


def test_final_citation_check_logs_the_step_the_readme_reads():
    seven = _stage(7)
    assert '`"step":"verify_citations"`' in seven
    assert "README reads it as verified, with a note that citation lookup was unavailable" in seven


def test_stages_5_and_6_end_by_checking_their_issue_files():
    for n in (5, 6):
        text = _stage(n)
        assert f"plumb check-issues {{WORKSPACE}}/stage-{n}/issues.json" in text
    seven = _stage(7)
    assert "never as issues with no excerpt" in seven and "names the file" in seven


def test_stage_0_keeps_the_resolved_pdf_path_and_never_names_the_role_to_the_user():
    intake = _stage(0)
    assert '`"pdf_path"` and `"page_count"` from step 2' not in intake
    assert "keep the `pdf_path` step 1 wrote" in intake
    assert "no question or message the user sees names it" in intake
    assert "no question, screen, or file the user sees names it" not in intake


def test_report_writer_handles_no_surviving_issue():
    from plumb import outputs
    text = (AGENTS / "report-writer.md").read_text(encoding="utf-8")
    assert f'When `validated.json` is empty, write the title line and then the one sentence "{outputs.REPORT_NO_ISSUES}"' in text


def test_setup_asks_the_level_first_groups_consent_and_ends_with_a_recap():
    intake = _stage(0)
    round1 = intake.split("\n5. ", 1)[1].split("If the journal answer is C", 1)[0]
    assert "setup:depth" in round1 and "setup:level" in round1 and "setup:output_dir" not in round1
    round2 = intake.split("\n11. ", 1)[1].split("\n12. ", 1)[0]
    assert "setup:level" not in round2
    assert "At Auto, ASK nothing" in round2 and "At Light and Standard, ASK one screen" in round2
    assert "At Hands-on, ASK one screen with every item as its own question" in round2
    outputs = intake.split("Then ASK a second screen", 1)[1].split("\n6. ", 1)[0]
    assert "setup:output" in outputs and "setup:output_dir" in outputs
    assert outputs.index("setup:output_dir") < outputs.index("plumb run-dir move {RUN} <folder>")
    consent_step = intake.split("\n7. ", 1)[1].split("\n8. ", 1)[0]
    assert '"Data and consent: what leaves this machine"' in consent_step
    recap = intake.split("\n8. ", 1)[1].split("\n9. ", 1)[0]
    assert intake.index("\n7. ") < intake.index("<!-- CHECKIN: setup -->", intake.index("\n7. ")) < intake.index("\n8. ")
    for s in ("plumb recap {WORKSPACE} --profiles {PLUGIN}/profiles", '"A. Start the review and send the paper (Recommended)"',
              '"B. Change something"', "at every level, Auto included", "never counts as an override",
              'setup:recap "A. Start the review and send the paper (Recommended)" "<chosen label>" --note preference'):
        assert s in recap, s
    assert "—" not in recap


def test_setup_recap_redo_rules_keep_stops_and_consent_current():
    intake = _stage(0)
    recap = intake.split("\n8. ", 1)[1].split("\n9. ", 1)[0]
    depth_row = recap.split("Depth: ", 1)[1].split("\n", 1)[0]
    assert "rerun steps 6 and 7" in depth_row
    # `plumb stops` runs after the recap, in step 13, so a changed depth or level is picked up there.
    assert intake.index("\n8. ") < intake.index("plumb stops <level> <depth>", intake.index("\n13. "))
    level_row = recap.split("Check-in level: ", 1)[1].split("\n", 1)[0]
    assert "step 13" in level_row
    stress_row = recap.split("Stress test or provider and retention: ", 1)[1]
    assert "rerun step 7" in stress_row
    assert "rewrite `consent.json`" in stress_row and "`egress`" in stress_row
    assert "plumb consent-check" in stress_row
    assert "drop `codex_stress_test` from `egress`" in stress_row
    assert "—" not in recap


def test_recap_comes_after_consent_and_before_the_paper_is_read():
    # Ruling, 2026-09-29: permission, journal, and consent are confirmed before anything reads the paper.
    intake = _stage(0)
    consent_check = intake.index("plumb consent-check {WORKSPACE}/consent.json")
    recap_step = intake.index("plumb recap {WORKSPACE} --profiles {PLUGIN}/profiles")
    first_read = intake.index("agents/paper-summary.md")
    assert consent_check < recap_step < first_read
    assert recap_step < intake.index("agents/manuscript-audit.md")
    recap = intake.split("\n8. ", 1)[1].split("\n9. ", 1)[0]
    assert "Nothing has left this machine yet" in recap
    assert "before step 9" in recap and "plumb consent-check" in recap
    assert "paper_summary" not in recap and "wait" not in recap.lower()


def test_referee_to_author_change_at_the_recap_rewrites_the_step_5_keys():
    intake = _stage(0)
    recap = intake.split("\n8. ", 1)[1].split("\n9. ", 1)[0]
    row = recap.split("Permission or journal: ", 1)[1].split("\n", 1)[0]
    assert "rerun the end of step 5" in row and "plumb filter-outputs" in row
    assert "`issues_list_mode`" in row and "`\"needs_zero_retention\"`" in row


def test_editor_memo_is_offered_written_checked_and_verified():
    from plumb import outputs
    intake = _stage(0)
    assert '"D. Checked-facts memo for an editor"' in intake
    assert "List D only when the permission answer is C and the depth is Standard or Deep" in intake
    assert '"Checked-facts memo for an editor" -> `editor_memo`' in intake
    out = _stage(7)
    step3 = out.split("\n3. ", 1)[1].split("\n4. ", 1)[0]
    assert "agents/editor-memo-writer.md" in step3 and "{RUN}/editor_memo.md" in step3
    for f in ("{WORKSPACE}/stage-7/validated.json", "{WORKSPACE}/stage-7/locations.json",
              "{WORKSPACE}/paper_summary.md", "do not pass `PDF_PATH`, `PAGE_COUNT`, or `shared/contracts.md`"):
        assert f in step3, f
    cmd = "plumb validate-output editor_memo {RUN}/editor_memo.md --validated {WORKSPACE}/stage-7/validated.json"
    step4 = out.split("\n4. ", 1)[1].split("\n5. ", 1)[0]
    final = out.split("\n6. ", 1)[1].split("\n7. ", 1)[0]
    assert cmd in step4 and cmd in final and "`editor_memo`" in final
    skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "The editor-memo writer dispatched in Stage 7 step 3 receives none of this either" in skill
    writer = (AGENTS / "editor-memo-writer.md").read_text(encoding="utf-8")
    for s in ("Read only these three files", "{WORKSPACE}/stage-7/validated.json",
              "{WORKSPACE}/stage-7/locations.json", "{WORKSPACE}/paper_summary.md", outputs.MEMO_SUMMARY,
              outputs.MEMO_ISSUES, *outputs.MEMO_FIELDS, outputs.fewer_than_five(1), outputs.NO_ISSUES,
              "Only N issues survived the checks, so this memo lists all of them.", "ms p. 30, PDF p. 32",
              '"not suitable"', '"should not be sent out"', '"below the bar"', "{RUN}/editor_memo.md",
              "(no heredoc, no `echo >`, no `cat >`, no `tee`)", "tools: [Read, Write]"):
        assert s in writer, s
    assert "—" not in writer and "—" not in step3


def test_unlisted_journal_confirmation_precedes_the_outputs_question():
    intake = _stage(0)
    # A referee at an unlisted journal confirms the journal's AI policy right after round 1,
    # before ever reaching the outputs screen that lists option D. A decline stops the run there,
    # so option D is never offered to an unconfirmed referee.
    assert intake.index("setup:journal_policy") < intake.index("Then ASK a second screen")
    assert intake.index("setup:journal_policy") < intake.index('"D. Checked-facts memo for an editor"')
    recap = intake.split("\n8. ", 1)[1].split("\n9. ", 1)[0]
    row = recap.split("Permission or journal: ", 1)[1].split("\n", 1)[0]
    assert row.index("setup:journal_policy") < row.index("ask the outputs question again")


# The original section 3 lines in docs/spec.md (from 101615f), with the dated attributions removed for the
# public repo (Plan 1e wave B1).
ORIGINAL_SPEC_LINES = (
    "- **Audiences.** Primary: authors and friendly reviewers (a colleague running it on "
    "the author's draft with the author's permission). Secondary: journal referees and editors. Journal-level "
    "use at intake is future potential only. The tool NEVER asks the user's role. Setup asks what output they "
    "want and whose permission covers the manuscript; the journal profile gates what may be produced. Editor "
    "output = checked-facts memo + neutral summary, no recommendation.",
    "- **Author mode** runs on the author's own paper (or a colleague runs it on the author's behalf) before "
    "submission. It always runs, subject to the consent record in section 9.",
    "- **Referee mode** runs only where the journal profile allows it (section 8).",
    "  - **Annotated PDF.** With the fix list, a copy of the manuscript annotated where "
    "each problem occurs. The proposal describes this as an author output.",
)


def test_readme_and_spec_describe_the_run_voice_and_the_editor_memo():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for s in ("**Checked-facts memo for an editor** (`editor_memo.md`)", "## During a run",
              "plumb/estimates.json", "`.workspace/run_log.md`", "never gives a recommendation",
              "it has a fixed two-part layout, a check blocks explicit verdict wording, and you "
              "read the memo before using it"):
        assert s in readme, s
    assert "—" not in readme and "verification memo" not in readme and "role" not in readme.lower()
    spec = (ROOT / "docs/spec.md").read_text(encoding="utf-8")
    for s in ("**Checked-facts memo for an editor.**", "desk-reject", "run log",
              "(estimate)", "recap",
              "it has a fixed two-part layout, a check blocks explicit verdict wording, and the "
              "user reads the memo before using it"):
        assert s in spec, s
    lines = spec.splitlines()
    for line in ORIGINAL_SPEC_LINES:
        assert line in lines, line[:60]
    section3 = spec.split("## 3. Users, modes, and outputs", 1)[1].split("\n## 4.", 1)[0]
    assert "—" not in section3


def test_the_memo_puts_the_skipped_check_sentence_last_in_the_paper_section():
    """Stage 7 tells every writer to add the skipped-checks sentence; the memo allows only two sections,
    so the sentence goes last under '## The paper', and the validator accepts it there."""
    import json
    from plumb import outputs
    writer = (AGENTS / "editor-memo-writer.md").read_text(encoding="utf-8")
    assert "last sentence of `## The paper`" in writer
    assert "last sentence of `## The paper`" in _stage(7)
    kept = [{"id": str(n), "severity": "Minor", "title": f"Fake issue {n}",
             "summary": f"The fake count in issue {n} does not add up."} for n in range(1, 6)]
    items = "".join(f"### {n}. Fake issue {n}\n\nSeverity: Minor\nWhere: ms p. {n}, PDF p. {n + 2}\n"
                    f"What the paper claims: Fake output doubles.\nThe problem: The fake count in issue {n} "
                    f"does not add up.\nWhy it matters: The estimate uses it.\n"
                    f"What would settle it: A recount.\n\n" for n in range(1, 6))
    memo = ("# Checked-facts memo\n\n## The paper\n\nThe paper claims fake subsidies raise widget output. "
            "Setting research was skipped by design for this paper because it uses no field site.\n\n"
            "## Most serious issues\n\n" + items)
    assert outputs.validate_editor_memo(memo, validated=kept) == []


def test_a_verdict_failure_never_ships_under_a_not_verified_block():
    out = _stage(7)
    tail = out[out.index("6. Final verification"):out.index("7. Finish the run folder")]
    assert "remove the sentence the failure names" in tail.lower() and "stage-7/withheld/" in tail
    assert tail.index("never ships") < tail.index('a line "Not verified:"')


def test_a_resume_in_the_middle_of_a_recap_change_reasks_what_rests_on_it():
    """Plan 1e wave C7."""
    intake = _stage(0)
    recap = intake.split("\n8. ", 1)[1].split("\n9. ", 1)[0]
    assert 'setup:recap_pending "" "<the setting to change>" --note preference' in recap
    assert 'setup:recap_pending "" "Done" --note preference' in recap
    skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "`setup:recap_pending`" in skill and '"Done"' in skill.split("`setup:recap_pending`", 1)[1][:600]
    step7 = intake.split("\n7. ", 1)[1].split("<!-- CHECKIN", 1)[0]
    assert "`consent.json` unchanged" in step7 and "--no-log" in step7


def test_stage_wording_for_what_runs_before_consent_and_the_coverage_audit():
    """Plan 1e wave C13."""
    intake = _stage(0)
    assert intake.split("\n", 3)[2].startswith("Nothing from the manuscript enters this conversation, and no agent reads it, before")
    five = _stage(5)
    step3 = five.split("\n3. ", 1)[1].split("\n4. ", 1)[0]
    assert "`<paper_dir>` is the folder that holds the PDF" in step3
