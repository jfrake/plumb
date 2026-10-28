"""Fixes from the V2 pilot runs. Every input is a small fake file written by the test; no text
comes from a real paper or review."""
from __future__ import annotations
import importlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from plumb import audit, checkin, outputs, validated

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/review/scripts"
sys.path.insert(0, str(SCRIPTS))


def _cli(*args, home=None):
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    if home is not None:
        env["HOME"] = str(home)
    return subprocess.run([sys.executable, "-m", "plumb", *args], capture_output=True, text=True, cwd=ROOT, env=env)


def _flat(rel: str) -> str:
    return " ".join((ROOT / rel).read_text(encoding="utf-8").split())


# ---- A: kept minors reach the Stage 5 draft ----

def _minor(n, text):
    return {"id": f"m{n}", "kind": "minor", "title": f"Fake minor {n}", "severity": "Minor",
            "adjudication": "paper", "solvability": "quick fix", "summary": text,
            "excerpt": "A fake sentence.", "ms_page": 2, "checkin": f"minors:{n}", "sources": []}


FAKE_MINORS = [_minor(n, f"Fake minor point number {n} about a label.") for n in range(1, 6)]


def _stage5(root, minors, draft_lines):
    ws = root / "ws"
    (ws / "stage-5").mkdir(parents=True)
    (ws / "run.json").write_text(json.dumps({"depth": "standard"}))
    (ws / "stage-5" / "issues.json").write_text(json.dumps(minors))
    body = "\n".join(f"- {line}" for line in draft_lines)
    (ws / "stage-5" / "draft.md").write_text(
        f"## Issues\n\n## Minor issues\n\n{body}\n\n## What I left out\n\nNothing.\n")
    return ws


def test_kept_minors_missing_from_the_stage_5_draft_are_listed(tmp_path):
    ws = _stage5(tmp_path, FAKE_MINORS, [f"{m['summary']} (p. 2)" for m in FAKE_MINORS[:3]])
    checkin.record(ws, "minors", "minors:list", "A. Keep all (Recommended)", "A. Keep all (Recommended)", "auto")
    assert [i["id"] for i in validated.minors_missing_from_draft(ws)] == ["m4", "m5"]


def test_minors_the_user_dropped_need_not_be_in_the_draft(tmp_path):
    ws = _stage5(tmp_path, FAKE_MINORS, [f"{m['summary']} (p. 2)" for m in FAKE_MINORS[:3]])
    checkin.record(ws, "minors", "minors:list", "A. Keep all (Recommended)", "B. Keep only the first three")
    assert validated.minors_missing_from_draft(ws) == []


def test_check_minors_ignores_emphasis_and_page_cites(tmp_path):
    lines = [f"*{m['summary']}* (ms p. 2, PDF p. 4)" for m in FAKE_MINORS]
    ws = _stage5(tmp_path, FAKE_MINORS, lines)
    assert validated.minors_missing_from_draft(ws) == []


def test_check_minors_cli(tmp_path):
    ws = _stage5(tmp_path / "a", FAKE_MINORS, [f"{m['summary']} (p. 2)" for m in FAKE_MINORS[:3]])
    r = _cli("check-minors", str(ws))
    assert r.returncode == 1 and "Minor m4" in r.stdout and "Minor m5" in r.stdout
    ws2 = _stage5(tmp_path / "b", FAKE_MINORS, [f"{m['summary']} (p. 2)" for m in FAKE_MINORS])
    r = _cli("check-minors", str(ws2))
    assert r.returncode == 0 and r.stdout.strip() == "OK"
    (ws2 / "stage-5" / "draft.md").unlink()
    r = _cli("check-minors", str(ws2))
    assert r.returncode == 2 and "draft.md" in r.stdout


def test_minor_count_is_the_users_call_not_a_cap():
    text = _flat("skills/review/shared/proportion-and-concision.md")
    assert "four or five items" not in text
    assert "How many minors reach the review is the user's call at the minors check-in" in text


def test_synthesis_writes_each_minor_line_from_its_summary():
    text = _flat("skills/review/agents/synthesis.md")
    assert "a minor's line under `## Minor issues` in the draft starts with its `summary`, word for word" in text
    assert "- <One line per minor issue: its `summary` from issues.json, word for word, then its page reference.>" in text


def test_stage_5_checks_the_kept_minors_are_in_the_draft():
    text = _flat("skills/review/stages/stage-5-synthesize.md")
    assert "Then run `plumb check-minors {WORKSPACE}`." in text
    assert text.index("plumb check-issues {WORKSPACE}/stage-5/issues.json") < text.index("plumb check-minors {WORKSPACE}")


# ---- C: citation false flags ----

vc = importlib.import_module("verify_citations")


def _rec(title, year, authors):
    return {"title": title, "publication_year": year,
            "authorships": [{"author": {"display_name": a}} for a in authors]}


def test_a_book_review_listed_first_does_not_hide_the_book():
    """Fake records: a review of a fake book, listed before the book itself."""
    ref = {"raw": "Doe, J., Roe, K., and Poe, L. (2000). Feeling and judging in fake politics. Fake Press.",
           "year": 2000, "last_names": ["Doe", "Roe", "Poe"],
           "title_fragment": "Feeling and judging in fake politics"}
    review = _rec("Feeling and Judging in Fake Politics. By Jane Doe, Kim Roe, and Lee Poe", 2001, ["Sam Critic"])
    book = _rec("Feeling and judging in fake politics", 2000, ["Jane Doe", "Kim Roe", "Lee Poe"])
    assert vc.match_reference(ref, [review, book])[0] == "VERIFIED"
    assert vc.match_reference(ref, [review]) == (None, None)


# Two references by the same author in the same year, so both get the heading "Doe, J (2000)".
FAKE_REVIEW = ("1. A fake point (Doe, 2000).\n\nREFERENCES\n\n"
               "Doe, J. (2000). A fake book on fake things. Fake Press.\n\n"
               "Doe, J. (2000). Another fake study of other things. Fake Journal, 1, 1-2.\n")


def _wrong_authors(query, limit=5):
    """Fake lookup: every search finds the cited title under someone else's name. The titles
    repeat the parser's title fragments, so the title match is strong."""
    title = ("A fake book on fake things. Fake Press" if "book" in query
             else "Another fake study of other things. Fake Journal, 1, 1-2")
    return [_rec(title, 2000, ["Other Person"])], "fake", False


def _setup_review(tmp_path, monkeypatch):
    review = tmp_path / "review.txt"
    review.write_text(FAKE_REVIEW)
    monkeypatch.setattr(vc, "search_paper", _wrong_authors)
    monkeypatch.setattr(vc.time, "sleep", lambda s: None)
    return review, vc.extract_references_from_text(review)


def test_an_accepted_false_flag_counts_as_checked(tmp_path, monkeypatch):
    review, refs = _setup_review(tmp_path, monkeypatch)
    out = tmp_path / "citations.md"
    assert vc.verify_references(review, out) == 1
    ws = tmp_path / "ws"
    for ref in refs:
        audit.log_event(ws, "verification", check="accepted_flag", step="verify_citations", ref=ref["raw"])
    assert vc.verify_references(review, out, vc.accepted_refs(ws)) == 0
    assert "ACCEPTED" in out.read_text()


def test_accepting_one_reference_does_not_accept_its_namesake(tmp_path, monkeypatch):
    review, refs = _setup_review(tmp_path, monkeypatch)
    ws = tmp_path / "ws"
    audit.log_event(ws, "verification", check="accepted_flag", step="verify_citations", ref=refs[0]["raw"])
    out = tmp_path / "citations.md"
    assert vc.verify_references(review, out, vc.accepted_refs(ws)) == 1
    text = out.read_text()
    assert "ACCEPTED" in text and "AUTHOR_MISMATCH" in text
    assert f"- **Entry:** {refs[1]['raw']}" in text


def test_workspace_flag_is_read_in_any_position(tmp_path):
    review = tmp_path / "review.txt"
    review.write_text("1. A fake point with no citations.\n")
    ws = tmp_path / "ws"
    ws.mkdir()
    for args in ([str(review), str(tmp_path / "a.md"), "--workspace", str(ws)],
                 ["--workspace", str(ws), str(review), str(tmp_path / "b.md"), "fake@example.org"]):
        r = subprocess.run([sys.executable, str(SCRIPTS / "verify_citations.py"), *args],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr


def test_stage_6_citation_gate_is_a_check_in_that_auto_answers():
    text = _flat("skills/review/stages/stage-6-audit.md")
    step2 = text.split(" 3. Stress test", 1)[0]
    assert "<!-- CHECKIN: majors -->" in step2
    assert "If only the citation gate still fails, go to the check-in below." in step2
    assert "majors:citation:<k>" in step2 and "--note auto" in step2
    assert '"check":"accepted_flag","step":"verify_citations"' in step2
    assert "There is no check-in in this stage." not in text


def test_stage_6_citation_gate_covers_dangling_body_citations():
    step2 = _flat("skills/review/stages/stage-6-audit.md").split(" 3. Stress test", 1)[0]
    assert "dangling body citations" in step2
    assert "log each one as a `citation_check` dependency event" in step2
    assert "if dangling body citations remain, stop and show the report" in step2


def _smith_ref(last_names):
    return {"raw": "Smith (2010). Fake theory of widgets.", "year": 2010, "last_names": last_names,
            "title_fragment": "Fake theory of widgets"}


@pytest.mark.parametrize("last_names", [["Smith"], ["Smith", "Lee"]])
def test_a_weak_verified_hit_does_not_overturn_a_misattribution(last_names):
    """Fake records: the title under the wrong author, then an unrelated paper by an Al Smith."""
    wrong = _rec("Fake theory of widgets", 2010, ["Pat Jones"])
    unrelated = _rec("An unrelated study of gadgets", 2010, ["Al Smith"])
    assert vc.match_reference(_smith_ref(last_names), [wrong, unrelated])[0] == "AUTHOR_MISMATCH"


def test_a_strong_title_verified_hit_still_wins_after_a_weaker_one():
    ref = _smith_ref(["Smith"])
    wrong = _rec("Fake theory of widgets", 2010, ["Pat Jones"])
    right = _rec("Fake theory of widgets", 2010, ["Al Smith"])
    assert vc.match_reference(ref, [wrong, right])[0] == "VERIFIED"


def test_the_cited_work_is_not_taken_for_a_review():
    ref = {"raw": "Li (2015). Strategy: By Design for public firms.", "year": 2015, "last_names": ["Li"],
           "title_fragment": "Strategy By Design for public firms"}
    work = _rec("Strategy: By Design for public firms", 2015, ["Wei Li"])
    assert not vc._is_review_of(ref, work)
    assert vc.match_reference(ref, [work])[0] == "VERIFIED"
    # Whole words only: "li" inside "public" is not a name.
    other = _rec("Strategy: By Design for public firms", 2015, ["Sam Critic"])
    assert not vc._is_review_of(ref, other)


def test_a_lower_case_by_review_is_detected():
    ref = {"raw": "Doe (2000). Fake book.", "year": 2000, "last_names": ["Doe"], "title_fragment": "Fake book"}
    assert vc._is_review_of(ref, _rec("Book Review: Fake book by Doe", 2001, ["Sam Critic"]))


def test_every_citation_check_reads_the_accepted_flags():
    for rel in ("skills/review/stages/stage-6-audit.md", "skills/review/stages/stage-7-output.md"):
        t = _flat(rel)
        n = t.count("scripts/verify_citations.py")
        assert n and t.count("<config contact_email> --workspace {WORKSPACE}") == n, rel


# ---- F: a heading row one reading keeps ----

ct = importlib.import_module("compare_transcriptions")
FAKE_BODY = [["", "(1)", "(2)"], ["Fake firms", "12", "34"], ["Other fakes", "5", "6"]]


def test_a_spanning_heading_kept_by_one_reading_is_set_aside():
    """Fake table: reading a keeps a heading printed over two columns as its own row."""
    a = [["All fake firms", "", ""]] + [list(r) for r in FAKE_BODY]
    res = ct.compare(a, [list(r) for r in FAKE_BODY])
    assert res["shape_match"] and res["agreed"] == FAKE_BODY
    assert res["disagreements"] == [{"row": None, "col": None, "a": "1 heading row", "b": "0 heading rows",
                                     "reason": "header_rows", "whole_table": False}]


def test_heading_row_and_a_cell_difference_together():
    b = [list(r) for r in FAKE_BODY]
    b[2][2] = "7"
    res = ct.compare([list(r) for r in FAKE_BODY], [["All fake firms", "", ""]] + b)
    assert res["shape_match"]
    assert {"row": 2, "col": 2, "a": "6", "b": "7", "reason": "cell"} in res["disagreements"]
    assert res["agreed"][2][2] == ""


def test_a_missing_data_row_is_still_a_whole_table_disagreement():
    res = ct.compare([list(r) for r in FAKE_BODY], [list(r) for r in FAKE_BODY[:2]])
    assert not res["shape_match"] and res["disagreements"][0]["whole_table"] is True


def test_transcriber_and_stage_1_handle_spanning_headings():
    rules = _flat("skills/review/agents/table-transcriber.md")
    assert "A heading printed above the column headers that spans several columns is its own first row" in rules
    s1 = _flat("skills/review/stages/stage-1-verify.md")
    assert "Entries with reason `header_rows` are not asked either" in s1


# ---- D: merged issues ----
# All issues below are fake.

def _major(id_):
    return {"id": id_, "kind": "major", "title": f"Fake issue {id_}", "severity": "Weakens a claim",
            "adjudication": "judgment", "solvability": "new analysis", "excerpt": "A fake sentence.",
            "ms_page": 3, "summary": f"Fake summary for issue {id_}.", "checkin": f"majors:{id_}", "sources": []}


def _stage6(root, before, after):
    ws = root / "ws"
    for d in ("stage-1", "stage-4", "stage-5", "stage-6"):
        (ws / d).mkdir(parents=True, exist_ok=True)
    (ws / "run.json").write_text(json.dumps({"depth": "standard", "issues_list_mode": "full"}))
    (ws / "stage-5" / "issues.json").write_text(json.dumps(before))
    (ws / "stage-6" / "issues.json").write_text(json.dumps(after))
    (ws / "stage-6" / "draft.md").write_text("## Issues\n\n" + "\n\n".join(i["summary"] for i in after))
    (ws / "stage-1" / "flags.json").write_text("[]")
    (ws / "stage-1" / "unverified_numbers.md").write_text("")
    return ws


def test_a_merged_issue_is_labelled_merged_not_overruled(tmp_path):
    a, b, c = _major("7"), _major("12"), _major("13")
    ws = _stage6(tmp_path, [a, b, c], [dict(a, merged_from=["12"])])
    kept, dropped = validated.build(ws)
    assert [k["item"] for k in kept] == ["majors:7"]
    assert {d["item"]: d["reason"] for d in dropped} == {
        "majors:12": "merged into a kept issue in the audit", "majors:13": "overruled in the audit"}


def test_merged_from_must_be_a_list(tmp_path):
    a, b = _major("7"), _major("12")
    ws = _stage6(tmp_path, [a, b], [dict(a, merged_from="12")])
    with pytest.raises(validated.InputError, match="merged_from"):
        validated.build(ws)


def test_adjudicator_records_merges():
    text = _flat("skills/review/agents/adjudicator.md")
    assert "list its id in the kept issue's `merged_from`" in text


# ---- E: stress test JSON retry ----

def _stress_runner():
    spec = importlib.util.spec_from_file_location("codex_stress_test_v2", SCRIPTS / "codex_stress_test.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Fake Codex replies. The bad one quotes two passages with unescaped double quotes.
BAD_JSON = ('{"point_id": "issue-1", "verdict": "confirmed", "already_addressed": {"status": "yes", '
            '"location": "p. 3", "verbatim_quote": ""A fake quote." (p. 3) "Another fake quote." (p. 9)"}}')
GOOD_JSON = '{"point_id": "issue-1", "verdict": "confirmed", "recommendation": "keep_as_is"}'
FAKE_POINT = {"point_id": "issue-1", "section": "major", "index": 1, "text": "Fake point."}


def _fake_codex(replies, prompts):
    def fake(system_prompt, user_msg, paper_text, model, timeout, max_retries=2, usage_out=None):
        prompts.append(user_msg)
        if usage_out is not None:
            usage_out.update({"input_tokens": 10, "output_tokens": 1})
        return replies.pop(0)
    return fake


def test_stress_point_retries_once_when_the_reply_is_not_valid_json(tmp_path, monkeypatch):
    mod, prompts, usage = _stress_runner(), [], {}
    monkeypatch.setattr(mod, "call_codex", _fake_codex([BAD_JSON, GOOD_JSON], prompts))
    pid, status = mod.process_point(FAKE_POINT, tmp_path, "sys", "paper", None, 30, usage=usage)
    assert (pid, status) == ("issue-1", "ok") and len(prompts) == 2
    assert "not valid JSON" in prompts[1]
    assert json.loads((tmp_path / "issue-1.json").read_text())["verdict"] == "confirmed"
    assert usage["issue-1"] == {"input_tokens": 20, "output_tokens": 2}


def test_stress_point_gives_up_after_one_retry(tmp_path, monkeypatch):
    mod, prompts = _stress_runner(), []
    monkeypatch.setattr(mod, "call_codex", _fake_codex([BAD_JSON, BAD_JSON], prompts))
    pid, status = mod.process_point(FAKE_POINT, tmp_path, "sys", "paper", None, 30)
    assert status == "json_error" and len(prompts) == 2
    assert (tmp_path / "issue-1.raw.txt").read_text() == BAD_JSON


def test_stress_prompt_asks_for_escaped_quotes():
    text = _flat("skills/review/shared/stress-test-prompt.md")
    assert "Inside any JSON string value, escape each double quote" in text


# ---- B: the run log records the end of Stage 7 ----

def _fresh_ws(root):
    ws = root / "run" / ".workspace"
    ws.mkdir(parents=True)
    return ws


def test_final_output_log_writes_the_stage_7_run_log_line(tmp_path):
    ws = _fresh_ws(tmp_path)
    r = _cli("log", str(ws), "output", '{"final":true,"files":["issues_list.md","README.md"]}', home=tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    last = (ws / "run_log.md").read_text().strip().splitlines()[-1]
    assert "Stage 7 done" in last and "issues_list.md, README.md" in last


def test_final_output_log_without_files_still_writes_the_line(tmp_path):
    ws = _fresh_ws(tmp_path)
    assert _cli("log", str(ws), "output", '{"final":true}', home=tmp_path).returncode == 0
    assert "Stage 7 done" in (ws / "run_log.md").read_text()


def test_other_output_events_write_no_run_log_line(tmp_path):
    ws = _fresh_ws(tmp_path)
    assert _cli("log", str(ws), "output", '{"files":["x.md"]}', home=tmp_path).returncode == 0
    assert not (ws / "run_log.md").exists()


def test_stage_7_says_the_final_log_writes_the_run_log_line():
    assert "which marks the run finished and writes the Stage 7 line in the run log" in _flat(
        "skills/review/stages/stage-7-output.md")


# ---- H and G: how agents write files ----

def test_stage_2_compiler_returns_the_summary_and_the_orchestrator_writes_it():
    text = _flat("skills/review/stages/stage-2-understand.md")
    assert "returns the summary for the user as the text of its reply and writes no file" in text
    assert "Write the text it returns to `{WORKSPACE}/stage-2/summary_for_user.md` with your file-writing tool." in text
    assert "with a compiler dispatch (mechanical)" not in text


def test_contracts_count_inline_scripts_as_shell_writes():
    text = _flat("skills/review/shared/contracts.md")
    assert "An inline script typed on the command line" in text
    assert "counts as a shell write" in text


def test_adjudicator_rederive_rewrites_the_whole_file():
    text = _flat("skills/review/agents/adjudicator.md")
    assert "Rewrite the whole file with your file-writing tool; never edit it with a script." in text


# ---- Final review: citation answers stay out of dismissals ----

def test_a_citation_stop_answer_is_not_a_dismissal(tmp_path):
    """Fake answers: C at the Stage 6 citation check-in stops the review; it dismisses no issue."""
    answers = {"majors:citation:1": "C. Stop the review | Fake, A. (2001). Fake title.",
               "majors:citation:1:r": "C. Stop the review | Fake, A. (2001). Fake title.",
               "majors:2": "C. The paper already addresses this | Fake major two."}
    assert validated.dismissed(tmp_path, answers) == {"majors:2": "Fake major two."}


def _stage6_step2():
    return _flat("skills/review/stages/stage-6-audit.md").split(" 3. Stress test", 1)[0]


def test_stage_6_citation_answers_are_tied_to_the_entry_text():
    step2 = _stage6_step2()
    assert '"<recommended label> | <Entry line>" "<chosen label> | <Entry line>"' in step2
    assert "plumb answered {WORKSPACE} --labels" in step2
    assert "has this entry's Entry line as its text after ` | `, reuse that answer" in step2
    assert "across the step 2 pass and the step 5 pass" in step2
    assert "`majors:citation:<k>:r`, or `:r2`, `:r3`, and so on, taking the first with no answer" in step2
    assert ("After the rerun, entries answered A or C no longer block; continue to step 3 when only "
            "A-answered entries and ACCEPTED entries remain.") in step2


def test_stage_6_a_recorded_citation_stop_is_asked_again_on_resume():
    step2 = _stage6_step2()
    assert "A recorded C means the user chose to stop. On a resume, do not reuse it" in step2
    assert "ask that entry again under the first suffixed id with no answer" in step2


def test_stage_6_says_how_to_escape_a_single_quote_in_the_entry():
    step2 = _stage6_step2()
    assert "write each single quote in an entry or heading as `'\\''`" in step2
    assert "O'Brien becomes `O'\\''Brien`" in step2


def test_writers_copy_references_word_for_word_and_the_formats_agree():
    for rel in ("skills/review/agents/report-writer.md", "skills/review/agents/issues-list-writer.md"):
        assert "Copy each REFERENCES entry word for word from the adjudicated draft" in _flat(rel), rel
    synthesis = (ROOT / "skills/review/agents/synthesis.md").read_text(encoding="utf-8")
    plain = synthesis.split("## Fix-List Template", 1)[0].rsplit("REFERENCES", 1)[1]
    draft = synthesis.split("## Fix-List Template", 1)[1].split("REFERENCES", 1)[1]
    form = "Author, A., and Author, B. (Year). Title. Journal, volume(issue), pages."
    assert form in plain and form in draft
    assert "Year. Title of paper" not in synthesis


def test_a_minor_summary_is_one_sentence():
    text = _flat("skills/review/agents/synthesis.md")
    assert "a minor's `summary` is one plain sentence" in text
    assert "`summary` is two or three plain sentences stating the issue" in text


def test_stage_7_does_not_send_a_kept_unverified_reference_back_to_the_writers():
    step4 = _flat("skills/review/stages/stage-7-output.md").split(" 4. Check each prose output.", 1)[1]
    step4 = step4.split("<!-- CHECKIN: draft -->", 1)[0]
    assert "already has a `citation_check` dependency event" in step4
    assert "is not sent back" in step4 and 'goes straight to the "Not verified:" block in step 6' in step4


def test_match_reference_docstring_states_the_strong_title_rule():
    import verify_citations
    doc = " ".join(verify_citations.match_reference.__doc__.split())
    assert "A VERIFIED result anywhere in the list wins" not in doc
    assert "wins only when it also matches the title strongly" in doc


# ---- No metaphors in the outputs. All texts below are fake, written for the test. ----

METAPHORS = [
    ("The fake contribution rests on one coefficient.", "rests on"),
    ("The fake claims rest on a single survey.", "rest on"),
    ("The fake result hinges on the window.", "hinges on"),
    ("The fake dictionary is the load-bearing measure.", "load-bearing"),
    ("The fake instrument does the work here.", "does the work"),
    ("The fake interviews bear on H2.", "bear on"),
    ("The fake interview bears on the question.", "bears on"),
    ("The fake identification rests on the assumption of no spillovers.", "rests on"),
    ("The fake result stands on its own.", "stands on its own"),
    ("Seen through the fake lens of agency, it changes.", "lens"),
    ("The fake instrument was doing the work.", "doing the work"),
    ("This fake result carries the contribution.", "carries the contribution"),
    ("This fake test carries the most weight.", "carries the most weight"),
    ("This fake test carries weight.", "carries weight"),
    ("This fake test carries little weight.", "carries little weight"),
    ("This fake test carries no weight.", "carries no weight"),
    ("In the '90s, the fake estimate rests on the firms' data.", "rests on"),
    ('A 5" fake screen. The fake result rests on one city. See "Table 3".', "rests on"),
    ("The fake trend sits uneasily with the claim.", "sits uneasily"),
    ("The two fake shares are trading weight.", "trading weight"),
    ("The fake theory section unpacks the term.", "unpacks"),
    ("The fake claims outrun their evidence.", "outrun"),
    ("The fake betas move in a see-saw.", "see-saw"),
    ("The fake landscape of studies is thin.", "landscape"),
    ("The fake panel is the backbone of the paper.", "backbone"),
    ("Read through a fake lens, the result changes.", "lens"),
    ("The fake dictionary that carries H2's moderation is narrow.", "carries h2's moderation"),
    ("This fake process carried all three contributions.", "carried all three contributions"),
    ("The fake table carrying the headline has no N.", "carrying the headline"),
]


@pytest.mark.parametrize("sentence,phrase", METAPHORS)
def test_each_metaphor_is_caught(sentence, phrase):
    errs = outputs.metaphor_errors(sentence)
    assert len(errs) == 1 and errs[0].startswith(
        "Use no metaphors: name the variable, test, or assumption and say literally how they relate. "
        "Text quoted from the paper in quotation marks is not checked. Found: ")
    assert repr(phrase) in errs[0], errs


LITERAL = [
    "The fake dictionary used to measure H2's moderator is narrow.",
    "The parallel-trends assumption requires it. Fake firms carry debt and carry inventory.",
    "The fake interaction carries a negative sign.",
    "Fake Model 3 carries the same sign.",
    "Each fake observation carries a weight equal to its inverse probability.",
    "The fake variable carries the effect of tenure.",
    "Fake treated firms bear on average 3 percent more cost.",
    "Fake workers do the work in teams.",
    "Fake managers lean on peers for advice.",
    "Fake respondents stand on the factory floor.",
]


@pytest.mark.parametrize("sentence", LITERAL)
def test_literal_sentences_pass_the_metaphor_check(sentence):
    assert outputs.metaphor_errors(sentence) == []


QUOTED = [
    'The authors write "this carries weight" on the fake page.',
    "The authors write “this rests on trust” on the fake page.",
    'The authors write "the result\nrests on trust" across a line break.',
    "The authors write “the result\nrests on trust” across a line break.",
    "The authors write ‘this rests on trust’ on the fake page.",
    "The authors write 'this rests on trust' on the fake page.",
    "The fake firms' managers write 'the landscape changed' in the fake memo.",
]


@pytest.mark.parametrize("sentence", QUOTED)
def test_quoted_text_is_not_checked(sentence):
    assert outputs.metaphor_errors(sentence) == []


def test_quote_pairing_does_not_hide_text_between_two_quotes():
    text = 'They write "the effect\nvanishes" but the result hinges on "Table 3".'
    errs = outputs.metaphor_errors(text)
    assert errs and "'hinges on'" in errs[0]


def test_exempt_lines_and_sections():
    assert outputs.metaphor_errors(outputs.DISCLOSURE_LINE) == []
    title = "Referee Report on Unpacking the Landscape of Gig Work\n\nThis fake paper studies fake gig workers.\n"
    assert outputs.metaphor_errors(title) == []
    assert outputs.metaphor_errors(title + "\n1. Your fake estimate rests on one city.\n")
    for heading in ("REFERENCES", "References", "REFERENCES  "):
        refs = f"1. A fake point.\r\n\r\n{heading}\r\n\r\nAuthor, A. 2020. A fake landscape of firms. J, 1: 1-2.\r\n"
        assert outputs.metaphor_errors(refs) == [], heading


def test_the_message_names_at_most_five_phrases():
    text = " ".join(s for s, _ in METAPHORS)
    errs = outputs.metaphor_errors(text)
    assert len(errs) == 1 and errs[0].count("'") == 10


def test_a_summary_copied_word_for_word_is_exempt_once():
    summary = "The fake result rests on one window."
    assert outputs.metaphor_errors(f"### 1. {summary}\n", [summary]) == []
    assert outputs.metaphor_errors(f"### 1. {summary}\n\nIt also rests on one firm.\n", [summary])


def test_validate_report_and_issues_list_surface_metaphors():
    report = ("Referee Report on A Fake Paper\n\nThis fake paper studies fake firms.\n\n"
              "1. The fake estimate hinges on one firm. Report it without that firm.\n")
    assert not any("metaphor" in e for e in outputs.validate_report(report.replace("hinges on", "depends on")))
    assert any("'hinges on'" in e for e in outputs.validate_report(report))
    issues = ("## Issues\n\n### 1. The fake instrument may fail\n\nSeverity: Undermines the main claim\n"
              "Fix: new analysis\nWhere: ms p. 12 (PDF p. 14)\n\nThe fake identification rests on the "
              "instrument. Report the first stage.\n\n## What I left out\n\nNothing.\n")
    assert any("'rests on'" in e for e in outputs.validate_issues_list(issues, "full"))
    clean = issues.replace("rests on", "requires")
    assert not any("metaphor" in e for e in outputs.validate_issues_list(clean, "full"))


def test_a_copied_title_is_exempt_in_the_issues_list():
    issues = ("## Issues\n\n### 1. The fake result rests on one window\n\nSeverity: Undermines the main claim\n"
              "Fix: new analysis\nWhere: ms p. 12 (PDF p. 14)\n\nReport the other windows.\n\n"
              "## What I left out\n\nNothing.\n")
    kept = [{"id": "1", "severity": "Undermines the main claim", "title": "The fake result rests on one window",
             "summary": "Report the other windows."}]
    assert not any("metaphor" in e for e in outputs.validate_issues_list(issues, "full", kept))


def test_validate_fix_list_checks_the_draft_for_metaphors():
    draft = ("## Issues\n\n### 1. Fake issue\n\nSeverity: Weakens a claim\nFix: new analysis\n\n"
             "The fake estimate hinges on one firm.\n\n## What I left out\n\nNothing.\n")
    assert any("'hinges on'" in e for e in outputs.validate_fix_list(draft))
    assert outputs.validate_fix_list(draft.replace("hinges on", "depends on")) == []
    assert not any("metaphor" in e for e in outputs.validate_fix_list(draft, metaphors=False))


def _stage5_issue(summary, why="The fake estimate uses this share.", settle="Recount the fake share.",
                  id="1", kind="major", checkin="majors:1"):
    return {"id": id, "kind": kind, "title": "Fake share", "severity": "Weakens a claim",
            "summary": summary, "why": why, "settle": settle, "checkin": checkin}


def _issues_file(root, issues):
    path = root / "ws" / "stage-5" / "issues.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(issues))
    return path


def test_check_issues_fails_on_a_metaphor_in_a_copied_field(tmp_path):
    """Fake Stage 5 issues: a metaphor in summary, why, or settle exits 1 naming the id and phrase."""
    path = _issues_file(tmp_path, [_stage5_issue("The fake share that carries every result is unvalidated.")])
    r = _cli("check-issues", str(path))
    assert r.returncode == 1, r.stdout
    assert "Issue 1 `summary`" in r.stdout and "'carries every result'" in r.stdout and "OK" not in r.stdout
    path.write_text(json.dumps([_stage5_issue("The fake share is unvalidated.", why="H2 rests on it.")]))
    r = _cli("check-issues", str(path))
    assert r.returncode == 1 and "Issue 1 `why`" in r.stdout and "'rests on'" in r.stdout


def test_check_issues_passes_a_literal_stage_5_issue(tmp_path):
    path = _issues_file(tmp_path, [_stage5_issue("The fake share used in every result is unvalidated.")])
    r = _cli("check-issues", str(path))
    assert r.returncode == 0 and r.stdout.strip() == "OK"


def test_check_issues_checks_the_draft(tmp_path):
    path = _issues_file(tmp_path, [_stage5_issue("The fake share used in every result is unvalidated.")])
    draft = path.parent / "draft.md"
    draft.write_text("## Issues\n\n### 1. Fake share\n\nThe fake estimate hinges on one firm.\n")
    r = _cli("check-issues", str(path), "--draft", str(draft))
    assert r.returncode == 1 and "draft.md" in r.stdout and "'hinges on'" in r.stdout
    draft.write_text("## Issues\n\n### 1. Fake share\n\nThe fake estimate depends on one firm.\n")
    assert _cli("check-issues", str(path), "--draft", str(draft)).returncode == 0


def test_check_issues_skips_a_minor_the_user_dropped(tmp_path):
    minor = _stage5_issue("The fake label rests on a typo.", id="m1", kind="minor", checkin="minors:1")
    path = _issues_file(tmp_path, [minor])
    assert _cli("check-issues", str(path)).returncode == 1
    checkin.record(path.parent.parent, "minors", "minors:1", "Keep", "Drop: The fake label rests on a typo.")
    r = _cli("check-issues", str(path))
    assert r.returncode == 0 and r.stdout.strip() == "OK"


def test_check_issues_rejects_a_copied_field_that_is_not_text(tmp_path):
    path = _issues_file(tmp_path, [_stage5_issue(["The fake share."])])
    r = _cli("check-issues", str(path))
    assert r.returncode == 2 and "must be text" in r.stdout and "Traceback" not in r.stderr


def test_check_issues_type_checks_before_matching_a_dropped_minor(tmp_path):
    minor = _stage5_issue(["The fake label."], id="m1", kind="minor", checkin="minors:1")
    path = _issues_file(tmp_path, [minor])
    checkin.record(path.parent.parent, "minors", "minors:1", "Keep", "Drop: The fake label.")
    r = _cli("check-issues", str(path))
    assert r.returncode == 2 and "must be text" in r.stdout and "Traceback" not in r.stderr


def test_a_long_or_unbalanced_double_quote_exempts_nothing():
    long_quote = '"' + "fake words " * 40 + '" and the fake result rests on one city "x".'
    assert outputs.metaphor_errors(long_quote)
    assert outputs.metaphor_errors('The authors write "the fake result rests on trust".') == []


def test_the_memo_writer_quotes_the_paper_title():
    assert "When you name the paper's title, put it in double quotes" in _flat(
        "skills/review/agents/editor-memo-writer.md")


def test_stage_5_and_6_route_a_metaphor_failure_back_to_the_writer():
    for rel, agent, stage in (("skills/review/stages/stage-5-synthesize.md", "agents/synthesis.md", 5),
                              ("skills/review/stages/stage-6-audit.md", "agents/adjudicator.md", 6)):
        text = _flat(rel)
        assert f"--draft {{WORKSPACE}}/stage-{stage}/draft.md" in text, rel
        key = "Reword each listed field or draft passage without metaphors"
        assert "On exit 1, " in text and key in text, rel
        assert agent in text.split(key, 1)[0][-400:], rel
        assert "Change no fact, number, or page; replace only the metaphor." in text, rel
