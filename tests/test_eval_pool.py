"""plumb.eval_pool and eval/pool.py: the blind rating pool for one paper. Every run folder,
baseline folder, and event log here is a small fake written by the test; the clustering and
rewrite calls are replaced by fakes and never touch the network."""
from __future__ import annotations
import json
from pathlib import Path

import pytest

from plumb import fixture_score

ROOT = Path(__file__).resolve().parents[1]


# --- the shared text-overlap helper the scorer and the pool both use ---

def test_text_covers_when_the_sentence_is_inside_the_text():
    assert fixture_score.text_covers("The twelve never-treated regions serve as the control group",
                                     "Issue: the twelve never-treated regions serve as the control group throughout.")


def test_text_covers_when_most_content_words_are_shared():
    assert fixture_score.text_covers(
        "The joint test of the five leads (p = 0.31) confirms the identifying assumption.",
        "The joint test of the leads, with p = 0.31, is offered as confirmation of the identifying assumption.")


def test_text_covers_fails_on_few_shared_words_or_a_short_sentence():
    assert not fixture_score.text_covers(
        "The joint test of the five leads (p = 0.31) confirms the identifying assumption.",
        "The sample excludes firms with fewer than ten employees.")
    assert not fixture_score.text_covers("Table 2 wrong", "Table 2 disagrees with the text.")


# --- fakes: a Plumb run folder, its check-in log, and a baseline out folder ---

def _issue(id_, summary, excerpt="", ms_page=None, severity="Weakens a claim", adjudication="judgment",
           kind="major", checkin=None, sources=(), title=None, pdf_page=None):
    return {"id": id_, "kind": kind, "title": title or f"Issue {id_}", "severity": severity,
            "adjudication": adjudication, "solvability": "new analysis", "summary": summary,
            "excerpt": excerpt, "ms_page": ms_page, "pdf_page": pdf_page, "checkin": checkin or f"majors:{id_}",
            "sources": list(sources), "why": "", "settle": ""}


def _run(tmp_path, name, issues, packs=("archival",), events=(), files=None):
    """plumb_output/<name>/.workspace with run.json, stage-5/issues.json, the check-in events, and
    any other workspace files given as {relative path: object or text}."""
    ws = tmp_path / name / "plumb_output" / "2026-10-05" / ".workspace"
    (ws / "stage-5").mkdir(parents=True)
    (ws / "run.json").write_text(json.dumps({"depth": "standard", "packs": list(packs)}), encoding="utf-8")
    (ws / "stage-5" / "issues.json").write_text(json.dumps(issues), encoding="utf-8")
    if events:
        (ws / "audit").mkdir()
        (ws / "audit" / "events.jsonl").write_text(
            "".join(json.dumps(dict({"ts": "2026-10-05T00:00:00+00:00", "kind": "checkin"}, **e)) + "\n"
                    for e in events), encoding="utf-8")
    for rel, body in (files or {}).items():
        p = ws / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body if isinstance(body, str) else json.dumps(body), encoding="utf-8")
    return ws.parent


def _answer(stop, item, recommended, answer, note=""):
    return {"stop": stop, "item": item, "recommended": recommended, "answer": answer, "note": note}


BASELINE_TEXT = """Here are the problems I found.

1. **Never-treated regions are treated**
   Severity: Weakens a claim
   Page: 4 (PDF 6)
   What is wrong: the twelve never-treated regions serve as the control group, but Table 1 shows they adopt in 2019.
   Fix: drop them from the control group.

2. Sample size disagrees between text and table
   (2) Minor
   (3) p. 7
   (4) The text says 1,204 firms and Table 2 says 1,240.
   (5) Reconcile the counts.
"""


def _baseline(tmp_path, texts, run_of_record=1):
    """A baseline.py out folder: <out>/<model>/run-<n>/issues.md plus done, and manifest.json.
    texts maps model -> {run number: issues.md text}."""
    out = tmp_path / "baseline"
    runs = []
    for model, by_run in texts.items():
        for n, text in by_run.items():
            folder = out / model / f"run-{n}"
            folder.mkdir(parents=True)
            (folder / "issues.md").write_text(text, encoding="utf-8")
            for name in ("request.json", "response.json"):
                (folder / name).write_text("{}", encoding="utf-8")
            entry = {"model": model, "run": n, "folder": f"{model}/run-{n}", "status": "complete"}
            (folder / "done").write_text(json.dumps(entry), encoding="utf-8")
            runs.append(entry)
    (out / "manifest.json").write_text(json.dumps({"pdf": "paper.pdf", "run_of_record": run_of_record, "runs": runs}),
                                       encoding="utf-8")
    return out


# --- candidates from each source ---

def test_plumb_run_candidates_carry_the_label_severity_page_text_and_pack(tmp_path):
    from plumb import eval_pool
    run = _run(tmp_path, "auto", [_issue("1", "The control regions adopt in 2019.", excerpt="They serve as the control group.",
                                          ms_page=4, severity="Undermines the main claim", adjudication="paper",
                                          sources=["design_checks.md:DD3"])])
    cands = eval_pool.plumb_candidates(run, "plumb-auto")
    assert len(cands) == 1
    c = cands[0]
    assert c["source"] == "plumb-auto" and c["severity"] == "Undermines the main claim"
    assert c["pages"] == ["4"] and c["issue_id"] == "1" and c["adjudication"] == "paper"
    assert c["pack"] == "archival" and c["item"] == "majors:1" and c["overruled"] is None
    assert c["ref"] == "plumb-auto:1" and c["pdf_pages"] == []
    assert "control regions adopt in 2019" in c["text"] and "serve as the control group" in c["text"]


def test_pack_comes_from_a_source_naming_it_else_the_runs_primary_pack(tmp_path):
    from plumb import eval_pool
    run = _run(tmp_path, "auto", [_issue("1", "a", sources=["survey_numbers.md:3"]),
                                  _issue("2", "b", sources=["core:literature"]),
                                  _issue("3", "c", sources=[])], packs=("archival", "survey"))
    assert [c["pack"] for c in eval_pool.plumb_candidates(run, "plumb-auto")] == ["survey", "core", "archival"]


def test_standard_run_tags_a_major_dismissed_at_the_majors_stop_as_overruled(tmp_path):
    from plumb import eval_pool
    run = _run(tmp_path, "std", [_issue("1", "Kept major."), _issue("2", "Dismissed major.")],
               events=[_answer("majors", "majors:1", "A. Keep it as a major issue (Recommended) | Kept major.",
                               "A. Keep it as a major issue (Recommended) | Kept major."),
                       _answer("majors", "majors:2", "A. Keep it as a major issue (Recommended) | Dismissed major.",
                               "C. The paper already addresses this (give the page) | Dismissed major.", note="p.3: it does")])
    cands = eval_pool.standard_candidates(run)
    by = {c["issue_id"]: c for c in cands}
    assert by["1"]["source"] == "plumb-standard" and by["1"]["overruled"] is None
    assert by["2"]["source"] == "plumb-standard"
    assert by["2"]["overruled"]["item"] == "majors:2" and by["2"]["overruled"]["stop"] == "majors"
    assert by["2"]["overruled"]["answer"].startswith("C.")


def test_a_major_demoted_to_minor_or_answered_on_auto_is_not_overruled(tmp_path):
    from plumb import eval_pool
    run = _run(tmp_path, "std", [_issue("1", "Demoted."), _issue("2", "Auto.")],
               events=[_answer("majors", "majors:1", "A. Keep it as a major issue (Recommended)", "B. It is real, but minor"),
                       _answer("majors", "majors:2", "A. Keep it as a major issue (Recommended)",
                               "C. The paper already addresses this", note="auto")])
    assert [c["overruled"] for c in eval_pool.standard_candidates(run)] == [None, None]


def test_a_dropped_minor_is_matched_by_its_recorded_sentence_or_its_item(tmp_path):
    from plumb import eval_pool
    run = _run(tmp_path, "std", [_issue("m1", "Figure 2 lacks axis labels.", kind="minor", severity="Minor", checkin="minors:1"),
                                 _issue("m2", "A citation year is wrong.", kind="minor", severity="Minor", checkin="minors:2"),
                                 _issue("m3", "Table 3 note is missing.", kind="minor", severity="Minor", checkin="minors:3")],
               events=[_answer("minors", "minors:list", "A. Keep all (Recommended)", "C. Let me pick"),
                       _answer("minors", "minors:1", "Keep (Recommended)", "Keep (Recommended)"),
                       _answer("minors", "minors:2", "Keep (Recommended)", "Drop: A citation year is wrong"),
                       _answer("minors", "minors:3", "Keep (Recommended)", "Drop: some text synthesis renumbered")])
    by = {c["issue_id"]: c for c in eval_pool.standard_candidates(run)}
    assert by["m1"]["overruled"] is None
    assert by["m2"]["overruled"]["item"] == "minors:2"
    assert by["m3"]["overruled"]["item"] == "minors:3"


def test_an_alternative_ruled_out_at_against_enters_from_the_stage_3_question(tmp_path):
    from plumb import eval_pool
    run = _run(tmp_path, "std", [_issue("1", "A kept major.")],
               events=[_answer("against", "against:2", "A. Plausible, investigate further (Recommended) | Reverse causality.",
                               "C. Not plausible here | Reverse causality.")],
               files={"stage-3/questions.json": [
                   {"id": "against:2", "stop": "against", "text": "Reverse causality. Firms that grow adopt the policy.",
                    "options": [], "recommended": "A", "depends_on": [], "prune_if": {}}]})
    cands = eval_pool.standard_candidates(run)
    extra = [c for c in cands if c["issue_id"] is None]
    assert len(extra) == 1 and extra[0]["source"] == "plumb-standard"
    assert extra[0]["overruled"]["item"] == "against:2" and extra[0]["overruled"]["stop"] == "against"
    assert "Firms that grow adopt the policy" in extra[0]["text"]


def test_a_numbers_flag_marked_extraction_error_enters_from_flags_json(tmp_path):
    from plumb import eval_pool
    run = _run(tmp_path, "std", [],
               events=[_answer("numbers", "numbers:text:3", "A. Real problem in the paper (Recommended)", "B. Extraction error"),
                       _answer("numbers", "numbers:arith:t2:r1:stars_vs_se",
                               "C. The paper states one-tailed tests or another source for the marks (Recommended)",
                               "C. The paper states one-tailed tests or another source for the marks (Recommended)")],
               files={"stage-1/flags.json": [
                   {"id": "1", "item": "numbers:text:3", "kind": "number", "title": "Text says 1,204, table says 1,240",
                    "severity": None, "summary": "The text reports 1,204 firms; Table 2 reports 1,240.", "excerpt": None,
                    "ms_page": 7, "pdf_page": 9, "table": "Table 2", "cells": []},
                   {"id": "2", "item": "numbers:arith:t2:r1:stars_vs_se", "kind": "number", "title": "Stars",
                    "severity": None, "summary": "x", "excerpt": None, "ms_page": 8, "pdf_page": None, "table": None, "cells": []}]})
    cands = eval_pool.standard_candidates(run)
    assert [c["overruled"]["item"] for c in cands] == ["numbers:text:3"]
    assert cands[0]["pages"] == ["7"] and cands[0]["adjudication"] == "paper" and "1,204" in cands[0]["text"]


def test_numbers_drops_are_only_the_defined_letters_on_flag_items(tmp_path):
    from plumb import eval_pool
    flags = [{"id": str(k), "item": item, "kind": "number", "title": f"Flag {k}", "severity": None, "summary": f"Summary {k}.",
              "excerpt": None, "ms_page": k, "pdf_page": None, "table": None, "cells": []}
             for k, item in enumerate(["numbers:cell:t1:r1:c1", "numbers:table:t1", "numbers:arith:t2:r1:sum",
                                       "numbers:hyp:H2:HL3", "numbers:text:4", "numbers:pack:survey:1"], 1)]
    run = _run(tmp_path, "std", [], files={"stage-1/flags.json": flags},
               events=[_answer("numbers", "numbers:cell:t1:r1:c1", "A. Leave it blank (Recommended)", "B. Reading 1: 0.26"),
                       _answer("numbers", "numbers:table:t1", "A. Leave the table unverified (Recommended)", "C. Use reading 2"),
                       _answer("numbers", "numbers:arith:t2:r1:sum", "A. Real problem in the paper (Recommended)", "B. Extraction error"),
                       _answer("numbers", "numbers:hyp:H2:HL3", "A. Real problem in the paper (Recommended)", "B. The ledger misread the paper"),
                       _answer("numbers", "numbers:text:4", "A. Real problem in the paper (Recommended)", "C. Something else"),
                       _answer("numbers", "numbers:pack:survey:1", "A. Real problem in the paper (Recommended)", "B. Not a problem or misread")])
    items = [c["overruled"]["item"] for c in eval_pool.standard_candidates(run)]
    assert items == ["numbers:arith:t2:r1:sum", "numbers:hyp:H2:HL3", "numbers:pack:survey:1"]
    by = {c["overruled"]["item"]: c for c in eval_pool.standard_candidates(run)}
    assert by["numbers:pack:survey:1"]["pack"] == "survey" and by["numbers:arith:t2:r1:sum"]["pack"] == "core"
    assert all(c["adjudication"] == "paper" for c in by.values())


def test_minors_list_b_drops_every_held_minor_after_the_third(tmp_path):
    from plumb import eval_pool
    minors = [_issue(f"m{n}", f"Minor point number {n} about figure {n}.", kind="minor", severity="Minor", checkin=f"minors:{n}")
              for n in range(1, 6)]
    run = _run(tmp_path, "std", [_issue("1", "A major.")] + minors,
               events=[_answer("minors", "minors:list", "A. Keep all (Recommended)", "B. Keep only the first three")])
    cands = eval_pool.standard_candidates(run)
    over = {c["issue_id"]: c["overruled"] for c in cands if c["overruled"]}
    assert sorted(over) == ["m4", "m5"]
    assert over["m4"]["item"] == "minors:list" and over["m4"]["stop"] == "minors"


def test_minors_list_b_builds_the_dropped_minors_from_held_minors_md_when_issues_json_lacks_them(tmp_path):
    from plumb import eval_pool
    held = "# Held minors\n\n1. Figure 2 lacks axis labels (p. 9).\n2. A citation year is wrong (p. 12).\n3. Table 3 note missing (p. 7).\n4. The appendix repeats a paragraph (p. 20).\n5. Typo in H2 (p. 3).\n"
    run = _run(tmp_path, "std", [_issue("1", "A major.")], files={"stage-5/held_minors.md": held},
               events=[_answer("minors", "minors:list", "A. Keep all (Recommended)", "B. Keep only the first three")])
    extra = [c for c in eval_pool.standard_candidates(run) if c["overruled"]]
    assert [c["overruled"]["item"] for c in extra] == ["minors:list", "minors:list"]
    assert [c["text"] for c in extra] == ["The appendix repeats a paragraph (p. 20).", "Typo in H2 (p. 3)."]
    assert [c["pages"] for c in extra] == [["20"], ["3"]] and all(c["severity"] == "Minor" for c in extra)
    assert [c["ref"] for c in extra] == ["plumb-standard:minors:4", "plumb-standard:minors:5"]


def test_demotions_against_b_and_draft_rulings_are_not_drops(tmp_path):
    from plumb import eval_pool
    run = _run(tmp_path, "std", [_issue("1", "Demoted."), _issue("2", "Ruled on.")],
               events=[_answer("majors", "majors:1", "A. Keep it as a major issue (Recommended)", "B. It is real, but minor"),
                       _answer("against", "against:1", "A. Plausible, investigate further (Recommended) | Alt.",
                               "B. Plausible, but the paper handles it | Alt.", note="p.3: handled"),
                       _answer("draft", "draft:ruling:2", "A. Accept the ruling (Recommended)", "B. Overturn it")])
    cands = eval_pool.standard_candidates(run)
    assert [c["overruled"] for c in cands] == [None, None] and len(cands) == 2


def test_a_citation_answer_at_the_majors_stop_is_not_a_drop():
    """Fake answers: the Stage 6 citation check-in reuses the majors stop, but its C stops the
    review and drops no issue."""
    from plumb import eval_pool
    stop = _answer("majors", "majors:citation:1", "A. Keep going, and list it as not verified (Recommended) | Fake entry.",
                   "C. Stop the review | Fake entry.")
    assert eval_pool._drops(stop) is False
    assert eval_pool._drops(_answer("majors", "majors:1", "A. Keep (Recommended)", "C. Addressed")) is True


def test_a_major_dismissed_but_absent_from_issues_json_enters_from_the_majors_card(tmp_path):
    from plumb import eval_pool
    run = _run(tmp_path, "std", [_issue("1", "The kept one.")],
               events=[_answer("majors", "majors:2", "A. Keep it as a major issue (Recommended) | Gone one.",
                               "C. The paper already addresses this | Gone one.")],
               files={"stage-4/majors_cards.json": [
                   {"id": "2", "item": "majors:2", "title": "Gone one", "severity": "Weakens a claim",
                    "summary": "Gone one. The problem is the gap.", "excerpt": "The gap sentence.", "ms_page": 5, "pdf_page": None}]})
    extra = [c for c in eval_pool.standard_candidates(run) if c["issue_id"] is None]
    assert len(extra) == 1 and extra[0]["pages"] == ["5"] and extra[0]["severity"] == "Weakens a claim"
    assert "The gap sentence" in extra[0]["text"]
    # The card carries no adjudication type or pack, and no majors_draft.md exists: both are unknown.
    assert extra[0]["adjudication"] == "unknown" and extra[0]["pack"] == "unknown"


MAJORS_DRAFT = """# Major issues

## 1. The kept one.

Severity: Weakens a claim. Adjudication: paper.

## 2. Gone one.

Severity: Weakens a claim. Adjudication: external.
Pack: survey

What the paper claims: something.
"""


def test_an_orphaned_major_takes_its_type_and_pack_from_majors_draft(tmp_path):
    from plumb import eval_pool
    run = _run(tmp_path, "std", [_issue("1", "The kept one.")],
               events=[_answer("majors", "majors:2", "A. Keep it as a major issue (Recommended) | Gone one.",
                               "C. The paper already addresses this | Gone one.")],
               files={"stage-4/majors_cards.json": [
                   {"id": "2", "item": "majors:2", "title": "Gone one", "severity": "Weakens a claim",
                    "summary": "Gone one. The problem is the gap.", "excerpt": "The gap sentence.", "ms_page": 5, "pdf_page": None}],
                   "stage-4/majors_draft.md": MAJORS_DRAFT})
    extra = [c for c in eval_pool.standard_candidates(run) if c["issue_id"] is None]
    assert extra[0]["adjudication"] == "external" and extra[0]["pack"] == "survey"
    # A draft block with no Pack line leaves the pack unknown; the type still comes from the draft.
    run2 = _run(tmp_path, "std2", [_issue("1", "The kept one.")],
                events=[_answer("majors", "majors:2", "A. Keep it (Recommended) | Gone one.", "C. Addressed | Gone one.")],
                files={"stage-4/majors_draft.md": MAJORS_DRAFT.replace("Pack: survey\n", "")})
    extra = [c for c in eval_pool.standard_candidates(run2) if c["issue_id"] is None]
    assert extra[0]["adjudication"] == "external" and extra[0]["pack"] == "unknown"
    assert "Gone one" in extra[0]["text"]


def test_an_alternative_ruled_out_has_unknown_type_and_pack(tmp_path):
    from plumb import eval_pool
    run = _run(tmp_path, "std", [], events=[_answer("against", "against:1", "A. Plausible (Recommended) | Reverse causality.",
                                                     "C. Not plausible here | Reverse causality.")])
    c = eval_pool.standard_candidates(run)[0]
    assert c["adjudication"] == "unknown" and c["pack"] == "unknown" and "Reverse causality" in c["text"]


def test_an_item_dropped_at_the_draft_review_is_matched_by_issue_id(tmp_path):
    from plumb import eval_pool
    run = _run(tmp_path, "std", [_issue("1", "Dropped at the draft."), _issue("2", "Kept.")],
               events=[_answer("draft", "draft:drop:1", "Keep (Recommended)", "Drop: Issue 1")])
    by = {c["issue_id"]: c for c in eval_pool.standard_candidates(run)}
    assert by["1"]["overruled"]["stop"] == "draft" and by["2"]["overruled"] is None


def test_baseline_candidates_come_from_the_run_of_record_with_severity_page_and_raw_block(tmp_path):
    from plumb import eval_pool
    out = _baseline(tmp_path, {"gpt-6-astra": {1: BASELINE_TEXT, 2: "1. Other run.\n"},
                               "claude-fable-5-1": {1: "1. **Only one** Severity: Minor. Page 2. Something small.\n"}})
    cands, missing = eval_pool.baseline_candidates(out)
    assert missing == []
    gpt = [c for c in cands if c["source"] == "gpt-6-astra"]
    assert [c["severity"] for c in gpt] == ["Weakens a claim", "Minor"]
    assert [c["pages"] for c in gpt] == [["4"], ["7"]]
    assert gpt[0]["title"] == "Never-treated regions are treated"
    assert gpt[0]["pdf_pages"] == ["6"] and gpt[0]["ref"] == "gpt-6-astra:1" and gpt[1]["ref"] == "gpt-6-astra:2"
    assert "adopt in 2019" in gpt[0]["text"] and "adopt in 2019" in gpt[0]["raw"]
    assert gpt[0]["issue_id"] is None and gpt[0]["overruled"] is None
    assert [c["source"] for c in cands if c["source"] == "claude-fable-5-1"] == ["claude-fable-5-1"]


def test_a_baseline_model_without_a_complete_run_of_record_is_reported_missing(tmp_path):
    from plumb import eval_pool
    out = _baseline(tmp_path, {"gpt-6-astra": {1: BASELINE_TEXT}})
    (out / "claude-fable-5-1" / "run-1").mkdir(parents=True)
    (out / "claude-fable-5-1" / "run-1" / "issues.md").write_text("1. Half written", encoding="utf-8")
    cands, missing = eval_pool.baseline_candidates(out)
    assert missing == ["claude-fable-5-1"] and {c["source"] for c in cands} == {"gpt-6-astra"}


# --- deduplication across sources: the word-overlap rule, which only the dry run (--no-rewrite) uses ---

def _cand(source, text, pages=(), severity="Weakens a claim", **extra):
    from plumb import eval_pool
    extra.setdefault("ref", f"{source}:{extra.get('issue_id') or extra.get('item') or 'x'}")
    return eval_pool._candidate(source, text, severity=severity, pages=pages, **extra)


def test_candidates_with_overlapping_text_merge_into_one_claim_keeping_every_label(tmp_path):
    from plumb import eval_pool
    cands = [_cand("plumb-auto", "The twelve never-treated regions serve as the control group but adopt in 2019.", ["4"],
                   severity="Undermines the main claim"),
             _cand("gpt-6-astra", "Never-treated regions are treated: the twelve never-treated regions serve as the "
                                  "control group, but Table 1 shows they adopt in 2019.", ["4"]),
             _cand("claude-fable-5-1", "The sample excludes firms with fewer than ten employees.", ["5"], severity="Minor")]
    claims = eval_pool.merge(cands)
    assert [c["sources"] for c in claims] == [["plumb-auto", "gpt-6-astra"], ["claude-fable-5-1"]]
    assert claims[0]["source_severities"] == {"plumb-auto": "Undermines the main claim", "gpt-6-astra": "Weakens a claim"}
    assert claims[0]["pages"] == ["4"] and [c["id"] for c in claims] == ["c01", "c02"]


def test_a_claim_takes_at_most_one_candidate_per_source():
    from plumb import eval_pool
    same = "The joint test of the five leads confirms the identifying assumption."
    claims = eval_pool.merge([_cand("plumb-auto", same, ["5"]), _cand("gpt-6-astra", same, ["5"]),
                              _cand("gpt-6-astra", same + " Stated again.", ["5"])])
    assert [c["sources"] for c in claims] == [["plumb-auto", "gpt-6-astra"], ["gpt-6-astra"]]


def test_overlap_share_is_the_shorter_texts_content_words_found_in_the_longer():
    from plumb import eval_pool
    assert eval_pool.overlap_share("The joint test of the five leads", "The joint test of the leads confirms the identifying assumption.") == 0.75
    assert eval_pool.overlap_share("alpha beta gamma delta", "alpha beta omega") == pytest.approx(2 / 3)
    assert eval_pool.overlap_share("alpha beta gamma delta", "alpha beta omega psi") == 0.5
    assert eval_pool.overlap_share("", "alpha") == 0.0


def test_a_pdf_page_is_never_compared_with_a_printed_page():
    from plumb import eval_pool
    same = "The joint test of the five leads confirms the identifying assumption."
    claims = eval_pool.merge([_cand("plumb-auto", same, [], pdf_pages=["6"]), _cand("gpt-6-astra", same, ["4"])])
    assert len(claims) == 1 and claims[0]["pages"] == ["4"]


def test_a_page_range_keeps_every_page_in_it():
    from plumb import eval_pool
    assert eval_pool.parse_issues_md("1. Title\nSeverity: Minor\nPages: pp. 4-6\nBody.\n")[0]["pages"] == ["4", "5", "6"]
    same = "The joint test of the five leads confirms the identifying assumption."
    claims = eval_pool.merge([_cand("plumb-auto", same, ["5"]), _cand("gpt-6-astra", same, ["4", "5", "6"])])
    assert len(claims) == 1


def test_the_same_text_on_different_pages_stays_apart_but_a_missing_page_does_not_block():
    from plumb import eval_pool
    same = "The joint test of the five leads confirms the identifying assumption."
    claims = eval_pool.merge([_cand("plumb-auto", same, ["5"]), _cand("gpt-6-astra", same, ["9"]),
                              _cand("claude-fable-5-1", same, [])])
    assert [c["sources"] for c in claims] == [["plumb-auto", "claude-fable-5-1"], ["gpt-6-astra"]]


def test_near_misses_list_pairs_above_a_third_and_same_text_on_other_pages():
    from plumb import eval_pool
    same = "The joint test of the five leads confirms the identifying assumption."
    cands = [_cand("plumb-auto", same, ["5"], issue_id="1"), _cand("gpt-6-astra", same, ["9"], ref="gpt-6-astra:1"),
             _cand("claude-fable-5-1", "The joint test of the leads has little power to detect a pre-trend.", ["5"],
                   ref="claude-fable-5-1:2"),
             _cand("claude-fable-5-1", "The sample excludes firms with fewer than ten employees.", ["5"], ref="claude-fable-5-1:3")]
    claims = eval_pool.merge(cands)
    near = eval_pool.near_misses(claims)
    pairs = {(n["a"], n["b"]): n for n in near}
    assert ("plumb-auto:1", "gpt-6-astra:1") in pairs and pairs[("plumb-auto:1", "gpt-6-astra:1")]["reason"] == "pages"
    assert ("plumb-auto:1", "claude-fable-5-1:2") in pairs
    assert 0.3 < pairs[("plumb-auto:1", "claude-fable-5-1:2")]["share"] <= 0.5
    assert not any("claude-fable-5-1:3" in k for k in pairs)


def test_hand_merges_join_two_claims_by_candidate_ref_and_are_recorded(tmp_path):
    from plumb import eval_pool
    same = "The joint test of the five leads confirms the identifying assumption."
    cands = [_cand("plumb-auto", same, ["5"], issue_id="1"), _cand("gpt-6-astra", same, ["9"], ref="gpt-6-astra:1"),
             _cand("claude-fable-5-1", "Unrelated point about the sample window.", ["2"], ref="claude-fable-5-1:2")]
    claims = eval_pool.merge(cands)
    assert len(claims) == 3
    record = eval_pool.apply_hand_merges(claims, [["plumb-auto:1", "gpt-6-astra:1"]])
    assert len(claims) == 2 and claims[0]["sources"] == ["plumb-auto", "gpt-6-astra"] and claims[0]["pages"] == ["5", "9"]
    assert record == {"pairs": [["plumb-auto:1", "gpt-6-astra:1"]], "merged": 1, "by_source": {"plumb-auto": 1, "gpt-6-astra": 1}}
    with pytest.raises(eval_pool.PoolError, match="nope:9"):
        eval_pool.apply_hand_merges(claims, [["plumb-auto:1", "nope:9"]])


def test_build_writes_near_misses_and_applies_a_hand_merge_file(tmp_path):
    from plumb import eval_pool
    auto = _run(tmp_path, "auto", [_issue("1", "The joint test of the five leads confirms the identifying assumption.", ms_page=5)])
    base = _baseline(tmp_path, {"gpt-6-astra": {1: "1. Joint test\nSeverity: Minor\nPage 9\nThe joint test of the five leads confirms the identifying assumption.\n"}})
    first = eval_pool.build(paper="p", auto=auto, standard=None, baseline=base, out=tmp_path / "a", raters=("r1", "r2"),
                            seed=1, rewrite_claims=False)
    assert len(first["claims"]) == 2
    near = json.loads((tmp_path / "a" / "sealed" / "near_misses.json").read_text())
    assert [(n["a"], n["b"], n["reason"]) for n in near] == [("plumb-auto:1", "gpt-6-astra:1", "pages")]
    merges = tmp_path / "merges.json"
    merges.write_text(json.dumps([["plumb-auto:1", "gpt-6-astra:1"]]), encoding="utf-8")
    second = eval_pool.build(paper="p", auto=auto, standard=None, baseline=base, out=tmp_path / "b", raters=("r1", "r2"),
                             seed=1, rewrite_claims=False, hand_merges=merges)
    assert len(second["claims"]) == 1 and second["claims"][0]["sources"] == ["plumb-auto", "gpt-6-astra"]
    assert second["hand_merges"]["merged"] == 1 and second["hand_merges"]["by_source"] == {"plumb-auto": 1, "gpt-6-astra": 1}
    assert json.loads((tmp_path / "b" / "sealed" / "pool.json").read_text())["hand_merges"]["file"] == str(merges)


def test_pool_script_takes_hand_merges(tmp_path):
    import subprocess
    import sys
    auto, std, base = _sources(tmp_path)
    merges = tmp_path / "merges.json"
    merges.write_text("[]", encoding="utf-8")
    proc = subprocess.run([sys.executable, str(ROOT / "eval" / "pool.py"), "--paper", "p", "--auto", str(auto),
                           "--out", str(tmp_path / "pool"), "--raters", "r1,r2", "--no-rewrite", "--hand-merges", str(merges)],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert "hand merges" in proc.stdout


def test_an_overruled_candidate_keeps_its_item_stop_pack_and_adjudication_on_the_claim():
    from plumb import eval_pool
    over = {"item": "majors:2", "stop": "majors", "recommended": "A.", "answer": "C.", "note": ""}
    claims = eval_pool.merge([_cand("plumb-standard", "The mediator is measured after the outcome.", ["7"],
                                    issue_id="2", item="majors:2", pack="experiments", adjudication="judgment", overruled=over),
                              _cand("gpt-6-astra", "The mediator is measured after the outcome, so the indirect effect is moot.", ["7"])])
    assert len(claims) == 1
    assert claims[0]["overruled"] == [{"item": "majors:2", "stop": "majors", "pack": "experiments",
                                       "adjudication": "judgment", "issue_id": "2", "answer": "C."}]
    # Standard dropped the point, so it is not in Standard's output and Standard gets no credit.
    assert claims[0]["sources"] == ["gpt-6-astra"]
    assert claims[0]["source_severities"] == {"gpt-6-astra": "Weakens a claim"}


def test_a_claim_held_only_by_an_overruled_point_has_no_source():
    from plumb import eval_pool
    over = {"item": "minors:4", "stop": "minors", "recommended": "Keep (Recommended)", "answer": "Drop: x", "note": ""}
    claims = eval_pool.merge([_cand("plumb-standard", "Figure 2 lacks axis labels on both panels.", ["9"], overruled=over)])
    assert claims[0]["sources"] == [] and claims[0]["overruled"][0]["stop"] == "minors"


# --- the rewrite: a pinned prompt, a pinned model, mocked here, skipped with --no-rewrite ---

PROMPT_FILE = ROOT / "eval" / "pool_rewrite_prompt.txt"


def _reply(text, model="claude-fable-5-1-20260901", request_id="req_1"):
    """What call_rewrite returns: the line plus the call's record."""
    return {"text": text, "model": model, "usage": {"input_tokens": 100, "output_tokens": 20}, "request_id": request_id}


def _fake_cluster(monkeypatch, groups_for=None):
    """Replace call_cluster. By default the fake returns the groups the overlap rule would form, so
    a real-path test keeps the claims it had; `groups_for(candidates)` overrides that. Returns the
    list of calls (the candidate count of each)."""
    from plumb import eval_pool
    calls = []

    def overlap_groups(candidates):
        index = {id(c): n for n, c in enumerate(candidates, 1)}
        return [[index[id(c)] for c in claim["candidates"]] for claim in eval_pool.merge(candidates)]

    def fake(candidates):
        calls.append(len(candidates))
        return {"groups": (groups_for or overlap_groups)(candidates), "model": "claude-fable-5-1-20260901",
                "request_id": "req_cl", "usage": {"input_tokens": 900, "output_tokens": 40}}

    monkeypatch.setattr(eval_pool, "call_cluster", fake)
    return calls


def test_the_rewrite_prompt_file_matches_its_pinned_hash():
    import hashlib
    from plumb import eval_pool
    assert hashlib.sha256(PROMPT_FILE.read_bytes()).hexdigest() == eval_pool.REWRITE_PROMPT_SHA256
    assert eval_pool.REWRITE_PROMPT_SHA256 == "5f56eda83df1400e62968fe2515a2e453e500c743e21ec0eb5ed92b3f07d6cc2"
    assert "{" not in eval_pool.load_rewrite_prompt()


CLUSTER_PROMPT_FILE = ROOT / "eval" / "pool_cluster_prompt.txt"
CLUSTER_SHA = "e09ab796ed8d317aceb7f5c98b8a9621aeeb4fd67fb451a0bf48871cc649b75e"


def test_the_cluster_prompt_file_matches_its_pinned_hash():
    import hashlib
    from plumb import eval_pool
    assert hashlib.sha256(CLUSTER_PROMPT_FILE.read_bytes()).hexdigest() == eval_pool.CLUSTER_PROMPT_SHA256
    assert eval_pool.CLUSTER_PROMPT_SHA256 == CLUSTER_SHA
    text = eval_pool.load_cluster_prompt()
    assert "{" not in text and "doubt" in text and "exactly once" in text


STANDARD = ("the de-duplication standard Plumb's synthesis step applies before it clusters, which is stricter than "
            "its construct-level clustering")


def test_the_cluster_prompt_header_names_its_standard_and_is_not_sent():
    from plumb import eval_pool
    raw = CLUSTER_PROMPT_FILE.read_text(encoding="utf-8")
    header = [line for line in raw.splitlines() if line.startswith("#")]
    assert header and STANDARD in " ".join(line.lstrip("# ") for line in header)
    sent = eval_pool.load_cluster_prompt()
    assert "Plumb" not in sent and not any(line.startswith("#") for line in sent.splitlines())
    assert sent.startswith("You group review comments")


def test_readme_names_the_clustering_standard():
    readme = " ".join((ROOT / "README.md").read_text(encoding="utf-8").split())
    assert STANDARD in readme


def test_a_changed_cluster_prompt_file_is_refused(monkeypatch):
    from plumb import eval_pool
    monkeypatch.setattr(eval_pool, "CLUSTER_PROMPT_SHA256", "0" * 64)
    with pytest.raises(eval_pool.PoolError, match="sha256"):
        eval_pool.load_cluster_prompt()


def test_a_changed_prompt_file_is_refused(monkeypatch):
    from plumb import eval_pool
    monkeypatch.setattr(eval_pool, "REWRITE_PROMPT_SHA256", "0" * 64)
    with pytest.raises(eval_pool.PoolError, match="sha256"):
        eval_pool.load_rewrite_prompt()


def test_rewrite_sends_each_claims_candidates_without_source_labels_and_takes_the_line(monkeypatch):
    from plumb import eval_pool
    sent = []

    def fake(prompt, payload):
        sent.append((prompt, payload))
        return _reply(f"  Rewritten {len(sent)} (p. 4).\n")

    monkeypatch.setattr(eval_pool, "call_rewrite", fake)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-FAKE-0001")
    claims = eval_pool.merge([_cand("plumb-auto", "The never-treated regions adopt in 2019.", ["4"]),
                              _cand("gpt-6-astra", "The twelve never-treated regions serve as the control group but adopt in 2019.", ["4"]),
                              _cand("claude-fable-5-1", "Something else entirely about the sample.", ["9"])])
    eval_pool.rewrite(claims)
    assert [c["text"] for c in claims] == ["Rewritten 1 (p. 4).", "Rewritten 2 (p. 4)."]
    assert all(c["rewritten"] for c in claims)
    assert sent[0][0] == eval_pool.load_rewrite_prompt()
    assert "never-treated" in sent[0][1] and "(p. 4)" in sent[0][1]
    for label in ("plumb-auto", "gpt-6-astra", "claude-fable-5-1", "plumb", "Plumb"):
        assert label not in sent[0][1] and label not in sent[1][1]


def test_an_empty_or_multi_line_rewrite_is_refused(monkeypatch):
    from plumb import eval_pool
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-FAKE-0001")
    monkeypatch.setattr(eval_pool, "call_rewrite", lambda prompt, payload: _reply("Two\nlines"))
    with pytest.raises(eval_pool.PoolError, match="one line"):
        eval_pool.rewrite(eval_pool.merge([_cand("plumb-auto", "A claim about the paper.", ["4"])]))
    monkeypatch.setattr(eval_pool, "call_rewrite", lambda prompt, payload: _reply("   "))
    with pytest.raises(eval_pool.PoolError, match="empty"):
        eval_pool.rewrite(eval_pool.merge([_cand("plumb-auto", "A claim about the paper.", ["4"])]))


def test_rewrite_refuses_to_start_without_a_key(monkeypatch):
    from plumb import eval_pool
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(eval_pool.PoolError, match="ANTHROPIC_API_KEY"):
        eval_pool.rewrite(eval_pool.merge([_cand("plumb-auto", "A claim about the paper.", ["4"])]))


def test_rewrite_call_uses_the_pinned_model_at_high_effort_with_no_tools(monkeypatch):
    """The one real API call, with a fake SDK module in its place: the request must name the
    pinned model, effort high, the prompt as the system text, and no tools or fallbacks."""
    import sys
    import types
    from plumb import eval_pool
    calls = []

    class Message:
        stop_reason = "end_turn"
        model = "claude-fable-5-1-20260901"
        _request_id = "req_abc"
        usage = types.SimpleNamespace(input_tokens=120, output_tokens=18)
        content = [types.SimpleNamespace(type="thinking", thinking=""), types.SimpleNamespace(type="text", text="One line (p. 2).")]

    class Messages:
        def create(self, **kw):
            calls.append(kw)
            return Message()

    class Client:
        def __init__(self, **kw):
            self.messages = Messages()

    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=Client))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-FAKE-0001")
    out = eval_pool.call_rewrite("the prompt", "the payload")
    assert out == {"text": "One line (p. 2).", "model": "claude-fable-5-1-20260901", "request_id": "req_abc",
                   "usage": {"input_tokens": 120, "output_tokens": 18}}
    kw = calls[0]
    assert kw["model"] == "claude-fable-5-1" and kw["output_config"] == {"effort": "high"} and kw["max_tokens"] == 16000
    assert kw["system"] == "the prompt" and kw["messages"] == [{"role": "user", "content": "the payload"}]
    assert "tools" not in kw and "fallbacks" not in kw and "temperature" not in kw


def test_a_stop_reason_other_than_end_turn_is_an_error_naming_the_claim(monkeypatch):
    import sys
    import types
    from plumb import eval_pool

    class Message:
        stop_reason = "max_tokens"
        stop_details = None
        model = "claude-fable-5-1"
        _request_id = "req_x"
        usage = types.SimpleNamespace(input_tokens=1, output_tokens=16000)
        content = [types.SimpleNamespace(type="text", text="A line that ran on and on")]

    client = types.SimpleNamespace(messages=types.SimpleNamespace(create=lambda **kw: Message()))
    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=lambda **kw: client))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-FAKE-0001")
    claims = eval_pool.merge([_cand("plumb-auto", "A claim about the paper.", ["4"])])
    eval_pool.assign_ids(claims, 1)
    with pytest.raises(eval_pool.PoolError, match="max_tokens") as exc:
        eval_pool.rewrite(claims)
    assert claims[0]["id"] in str(exc.value)


def test_build_records_each_claims_rewrite_model_usage_and_request_id(tmp_path, monkeypatch):
    from plumb import eval_pool
    _fake_cluster(monkeypatch)
    monkeypatch.setattr(eval_pool, "call_rewrite", lambda prompt, payload: _reply("A neutral line (p. 4).", request_id="req_7"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-FAKE-0001")
    auto, std, base = _sources(tmp_path)
    pool = eval_pool.build(paper="p", auto=auto, standard=std, baseline=base, out=tmp_path / "pool", raters=("r1", "r2"),
                           seed=1, rewrite_claims=True)
    for c in pool["claims"]:
        assert c["rewrite"] == {"model": "claude-fable-5-1-20260901", "request_id": "req_7", "cached": False,
                                "usage": {"input_tokens": 100, "output_tokens": 20}}
    cache = json.loads((tmp_path / "pool" / "sealed" / "rewrites.json").read_text())
    assert len(cache) == len(pool["claims"]) and all(len(k) == 64 for k in cache)


def test_the_rewrite_resumes_from_rewrites_json_and_does_not_pay_twice(tmp_path, monkeypatch):
    from plumb import eval_pool
    clustered = _fake_cluster(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-FAKE-0001")
    auto, std, base = _sources(tmp_path)
    calls = []

    def failing(prompt, payload):
        calls.append(payload)
        if len(calls) == 2:
            raise RuntimeError("network gone")
        return _reply("Line one (p. 4).")

    monkeypatch.setattr(eval_pool, "call_rewrite", failing)
    with pytest.raises(RuntimeError):
        eval_pool.build(paper="p", auto=auto, standard=std, baseline=base, out=tmp_path / "pool", raters=("r1", "r2"),
                        seed=1, rewrite_claims=True)
    cache = json.loads((tmp_path / "pool" / "sealed" / "rewrites.json").read_text())
    assert len(cache) == 1 and not (tmp_path / "pool" / "sealed" / "pool.json").exists()
    again = []
    monkeypatch.setattr(eval_pool, "call_rewrite", lambda prompt, payload: again.append(payload) or _reply("Line two (p. 4)."))
    pool = eval_pool.build(paper="p", auto=auto, standard=std, baseline=base, out=tmp_path / "pool", raters=("r1", "r2"),
                           seed=1, rewrite_claims=True)
    assert len(again) == len(pool["claims"]) - 1
    assert sorted(c["rewrite"]["cached"] for c in pool["claims"]) == [False] * (len(pool["claims"]) - 1) + [True]
    assert {c["text"] for c in pool["claims"]} == {"Line one (p. 4).", "Line two (p. 4)."}
    # The clustering was paid for once, on the first run, and taken from sealed/clusters.json after.
    assert clustered == [7] and pool["cluster"]["call"]["cached"] is True


def test_a_refusal_from_the_rewrite_model_is_an_error(monkeypatch):
    import sys
    import types
    from plumb import eval_pool

    class Message:
        stop_reason = "refusal"
        stop_details = types.SimpleNamespace(category="other", explanation="no")
        content = []

    client = types.SimpleNamespace(messages=types.SimpleNamespace(create=lambda **kw: Message()))
    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=lambda **kw: client))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-FAKE-0001")
    with pytest.raises(eval_pool.PoolError, match="refusal"):
        eval_pool.call_rewrite("p", "q")


# --- the clustering call: one request per paper, groups validated, cached under sealed/ ---

def _fake_sdk(monkeypatch, text, stop_reason="end_turn", model="claude-fable-5-1-20260901", request_id="req_c1"):
    """Put a fake anthropic module in place; returns the list of request kwargs it received, each
    with `_method` naming create or stream. A streamed message carries no _request_id; the stream
    holds it, as the SDK's MessageStream does."""
    import sys
    import types
    calls = []

    class Message:
        pass

    def create(**kw):
        calls.append(kw)
        m = Message()
        m.stop_reason, m.stop_details, m.model, m._request_id = stop_reason, None, model, request_id
        m.usage = types.SimpleNamespace(input_tokens=900, output_tokens=40)
        m.content = [types.SimpleNamespace(type="thinking", thinking=""), types.SimpleNamespace(type="text", text=text)]
        return m

    class Stream:
        def __init__(self, kw):
            self.kw, self.request_id = kw, request_id

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get_final_message(self):
            m = create(**self.kw)
            calls[-1]["_method"] = "stream"
            del m._request_id
            return m

    def create_call(**kw):
        m = create(**kw)
        calls[-1]["_method"] = "create"
        return m

    client = types.SimpleNamespace(messages=types.SimpleNamespace(create=create_call, stream=lambda **kw: Stream(kw)))
    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=lambda **kw: client))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-FAKE-0001")
    return calls


def _three():
    return [_cand("plumb-auto", "The twelve never-treated regions adopt the policy in 2019.", ["4"], severity="Minor", issue_id="1"),
            _cand("gpt-6-astra", "Errors are not clustered by school.", ["12"], ref="gpt-6-astra:1"),
            _cand("claude-fable-5-1", "Controls are contaminated: Table 1 shows the comparison units get treated later.", ["4"],
                  ref="claude-fable-5-1:1")]


def test_call_cluster_sends_one_request_on_the_pinned_model_and_returns_the_groups(monkeypatch):
    from plumb import eval_pool
    calls = _fake_sdk(monkeypatch, "1, 3\n2\n")
    out = eval_pool.call_cluster(_three())
    assert out == {"groups": [[1, 3], [2]], "model": "claude-fable-5-1-20260901", "request_id": "req_c1",
                   "usage": {"input_tokens": 900, "output_tokens": 40}}
    assert len(calls) == 1
    kw = calls[0]
    assert kw["model"] == eval_pool.REWRITE_MODEL == eval_pool.CLUSTER_MODEL == "claude-fable-5-1"
    # Its own ceiling, streamed so a long reply does not hit the HTTP timeout.
    assert kw["output_config"] == {"effort": "high"} and kw["max_tokens"] == eval_pool.CLUSTER_MAX_TOKENS == 64000
    assert kw["_method"] == "stream"
    assert kw["system"] == eval_pool.load_cluster_prompt()
    assert "tools" not in kw and "fallbacks" not in kw and "temperature" not in kw
    [turn] = kw["messages"]
    assert turn["role"] == "user"
    assert "Candidate 1 (p. 4): The twelve never-treated" in turn["content"] and "Candidate 3 (p. 4)" in turn["content"]
    for word in ("plumb", "gpt", "astra", "claude", "fable", "Minor", "Weakens", "severity"):
        assert word not in turn["content"], word


@pytest.mark.parametrize("reply, problem", [
    ("1, 3\n", "candidate 2 is in no group"),
    ("1, 3\n2\n4\n", "candidate 4, but there are only 3"),
    ("1, 3\n2, 3\n", "candidate 3 is in more than one group"),
    ("1, 1, 3\n2\n", "candidate 1 is in more than one group"),
    ("Groups:\n1, 3\n2\n", "not a list of candidate numbers"),
    ("\n", "no groups"),
])
def test_a_clustering_reply_that_misses_repeats_or_invents_a_candidate_is_refused(monkeypatch, reply, problem):
    from plumb import eval_pool
    _fake_sdk(monkeypatch, reply)
    with pytest.raises(eval_pool.PoolError, match=problem):
        eval_pool.call_cluster(_three())


def test_a_clustering_stop_at_max_tokens_is_an_error(monkeypatch):
    from plumb import eval_pool
    _fake_sdk(monkeypatch, "1, 3\n2", stop_reason="max_tokens")
    with pytest.raises(eval_pool.PoolError, match="clustering model stopped with max_tokens"):
        eval_pool.call_cluster(_three())


def test_clustering_refuses_to_start_without_a_key(monkeypatch):
    from plumb import eval_pool
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(eval_pool.PoolError, match="ANTHROPIC_API_KEY"):
        eval_pool.cluster(_three())


def _by_ref(*ref_groups):
    """A groups_for for _fake_cluster: the groups named by candidate ref, numbered as the payload
    numbers them, so a test does not depend on the hashed order."""
    def groups_for(candidates):
        number = {c["ref"]: n for n, c in enumerate(candidates, 1)}
        return [[number[r] for r in g] for g in ref_groups]
    return groups_for


def test_the_payload_numbers_candidates_in_a_hashed_order_and_groups_map_back(monkeypatch):
    from plumb import eval_pool
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-FAKE-0001")
    cands = _three() + [_cand("gpt-6-astra", "Point four about the sample window.", ["2"], ref="gpt-6-astra:2"),
                        _cand("plumb-auto", "Point five about the outcome coding.", ["3"], issue_id="5")]
    order = eval_pool.cluster_order(cands)
    assert sorted(order) == list(range(5)) and order != list(range(5))
    assert eval_pool.cluster_order([dict(c) for c in cands]) == order
    seen = []
    calls = _fake_cluster(monkeypatch, _by_ref(["plumb-auto:1", "claude-fable-5-1:1"], ["gpt-6-astra:1"],
                                               ["gpt-6-astra:2"], ["plumb-auto:5"]))
    real = eval_pool.call_cluster
    monkeypatch.setattr(eval_pool, "call_cluster", lambda c: seen.append([x["ref"] for x in c]) or real(c))
    out = eval_pool.cluster(cands)
    assert seen == [[cands[i]["ref"] for i in order]] and calls == [5]
    assert out["order"] == [cands[i]["ref"] for i in order]
    assert out["groups"] == [[1, 3], [2], [4], [5]]


def test_the_clustering_is_cached_with_a_stable_key_and_a_rerun_does_not_pay_twice(tmp_path, monkeypatch):
    import hashlib
    from plumb import eval_pool
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-FAKE-0001")
    calls = _fake_cluster(monkeypatch, _by_ref(["plumb-auto:1", "claude-fable-5-1:1"], ["gpt-6-astra:1"]))
    cache = tmp_path / "sealed" / "clusters.json"
    first = eval_pool.cluster(_three(), cache_file=cache)
    assert first["groups"] == [[1, 3], [2]] and first["call"]["cached"] is False and calls == [3]
    [key] = json.loads(cache.read_text())
    ordered = [_three()[i] for i in eval_pool.cluster_order(_three())]
    prompt = eval_pool.load_cluster_prompt()
    assert key == eval_pool.cluster_key(prompt, eval_pool.cluster_payload(ordered))
    assert key == hashlib.sha256(("claude-fable-5-1\nhigh\n" + prompt + "\n\n" + eval_pool.cluster_payload(ordered))
                                 .encode("utf-8")).hexdigest()
    second = eval_pool.cluster(_three(), cache_file=cache)
    assert second["groups"] == [[1, 3], [2]] and second["call"]["cached"] is True and calls == [3]
    assert second["call"]["request_id"] == "req_cl" and second["order"] == first["order"]
    assert [*json.loads(cache.read_text())] == [key]


def test_the_cache_key_changes_with_the_model_or_the_effort(monkeypatch):
    from plumb import eval_pool
    base = eval_pool.cluster_key("p", "q")
    monkeypatch.setattr(eval_pool, "CLUSTER_EFFORT", "max")
    assert eval_pool.cluster_key("p", "q") != base
    monkeypatch.setattr(eval_pool, "CLUSTER_EFFORT", "high")
    monkeypatch.setattr(eval_pool, "CLUSTER_MODEL", "another-model")
    assert eval_pool.cluster_key("p", "q") != base


@pytest.mark.parametrize("entry", ["not a dict", {"model": "m"}, {"groups": "1, 2, 3"}, {"groups": [[1, "x"], [2, 3]]},
                                   {"groups": [[1, 2]]}])
def test_a_malformed_cache_entry_is_an_error(tmp_path, monkeypatch, entry):
    from plumb import eval_pool
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-FAKE-0001")
    _fake_cluster(monkeypatch)
    ordered = [_three()[i] for i in eval_pool.cluster_order(_three())]
    cache = tmp_path / "clusters.json"
    cache.write_text(json.dumps({eval_pool.cluster_key(eval_pool.load_cluster_prompt(), eval_pool.cluster_payload(ordered)): entry}))
    with pytest.raises(eval_pool.PoolError, match="clusters.json"):
        eval_pool.cluster(_three(), cache_file=cache)


def test_one_candidate_needs_no_clustering_call(monkeypatch):
    from plumb import eval_pool
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    calls = _fake_cluster(monkeypatch)
    [c] = _three()[:1]
    assert eval_pool.cluster([c]) == {"groups": [[1]], "order": [c["ref"]], "call": None}
    assert eval_pool.cluster([]) == {"groups": [], "order": [], "call": None}
    assert calls == []


@pytest.mark.parametrize("reply, groups", [("1, 3\n\n\n2\n", [[1, 3], [2]]), ("  3,1 \n2", [[3, 1], [2]])])
def test_the_parser_takes_blank_lines_between_groups(reply, groups):
    from plumb import eval_pool
    assert eval_pool.parse_groups(reply, 3) == groups


@pytest.mark.parametrize("reply", ["1-3\n", "1, 3\n2\nThese are the groups.", "1, 3\n2 (alone)", "1 3\n2"])
def test_the_parser_refuses_a_range_trailing_prose_or_a_missing_comma(reply):
    from plumb import eval_pool
    with pytest.raises(eval_pool.PoolError, match="not a list of candidate numbers"):
        eval_pool.parse_groups(reply, 3)


# --- the clustered merge: claims follow the clusterer's groups, not the word overlap ---

PARAPHRASE_A = "The comparison regions are themselves treated later, so the control group is contaminated."
PARAPHRASE_B = "Never-treated provinces adopt the reform in 2019 according to Table 1."


def _probe_and_paraphrase():
    from plumb import eval_pool
    a = eval_pool.parse_issues_md(ATTRITION)[0]
    b = eval_pool.parse_issues_md(CLUSTERING)[0]
    return [eval_pool._candidate("gpt-6-astra", a["text"], pages=a["pages"], raw=a["body"], ref="gpt-6-astra:1"),
            eval_pool._candidate("claude-fable-5-1", b["text"], pages=b["pages"], raw=b["body"], ref="claude-fable-5-1:1"),
            _cand("plumb-auto", PARAPHRASE_A, ["4"], issue_id="1", severity="Undermines the main claim"),
            _cand("gpt-6-astra", PARAPHRASE_B, ["4"], ref="gpt-6-astra:2")]


def test_the_clustered_merge_joins_a_paraphrase_with_few_shared_words_and_keeps_the_probe_pair_apart():
    from plumb import eval_pool
    cands = _probe_and_paraphrase()
    # The overlap rule cannot see the paraphrase; the clusterer's groups decide.
    assert eval_pool.overlap_share(PARAPHRASE_A, PARAPHRASE_B) < eval_pool.NEAR_SHARE
    assert len(eval_pool.merge(cands)) == 4
    claims = eval_pool.merge(cands, groups=[[1], [2], [3, 4]])
    assert [c["sources"] for c in claims] == [["gpt-6-astra"], ["claude-fable-5-1"], ["plumb-auto", "gpt-6-astra"]]
    assert claims[2]["source_severities"] == {"plumb-auto": "Undermines the main claim", "gpt-6-astra": "Weakens a claim"}
    assert claims[2]["pages"] == ["4"] and [c["ref"] for c in claims[2]["candidates"]] == ["plumb-auto:1", "gpt-6-astra:2"]


def test_the_clustered_merge_lets_one_source_hold_two_candidates_in_a_claim():
    from plumb import eval_pool
    cands = [_cand("gpt-6-astra", "Attrition differs by arm.", ["12"], ref="gpt-6-astra:1", severity="Minor"),
             _cand("gpt-6-astra", "Dropout is higher in the treatment arm.", ["13"], ref="gpt-6-astra:2"),
             _cand("plumb-standard", "Treatment-arm dropout is higher.", ["12"], issue_id="3",
                   overruled={"item": "majors:3", "stop": "majors", "recommended": "A.", "answer": "C.", "note": ""})]
    [claim] = eval_pool.merge(cands, groups=[[1, 2, 3]])
    # The source's severity on the claim is the highest of its candidates in it, whatever the order.
    assert claim["sources"] == ["gpt-6-astra"] and claim["source_severities"] == {"gpt-6-astra": "Weakens a claim"}
    assert claim["pages"] == ["12", "13"] and len(claim["candidates"]) == 3
    assert [o["item"] for o in claim["overruled"]] == ["majors:3"]


def test_a_source_with_two_candidates_in_a_claim_takes_its_highest_severity():
    from plumb import eval_pool
    cands = [_cand("gpt-6-astra", "Attrition differs by arm.", ["12"], ref="gpt-6-astra:1", severity=None),
             _cand("gpt-6-astra", "Dropout is higher in the treatment arm.", ["12"], ref="gpt-6-astra:2",
                   severity="Undermines the main claim"),
             _cand("gpt-6-astra", "Treated units drop out more.", ["12"], ref="gpt-6-astra:3", severity="Minor")]
    [claim] = eval_pool.merge(cands, groups=[[1, 2, 3]])
    assert claim["source_severities"] == {"gpt-6-astra": "Undermines the main claim"}
    [claim] = eval_pool.merge(cands[::-1], groups=[[1, 2, 3]])
    assert claim["source_severities"] == {"gpt-6-astra": "Undermines the main claim"}


def test_clustered_near_misses_list_both_directions_for_the_hand_pass():
    from plumb import eval_pool
    same = "The joint test of the five leads confirms the identifying assumption."
    cands = [_cand("plumb-auto", same, ["5"], issue_id="1"),
             _cand("gpt-6-astra", same, ["5"], ref="gpt-6-astra:1"),
             _cand("plumb-auto", PARAPHRASE_A, ["4"], issue_id="2"),
             _cand("gpt-6-astra", PARAPHRASE_B, ["4"], ref="gpt-6-astra:2")]
    claims = eval_pool.merge(cands, groups=[[1], [2], [3, 4]])
    near = eval_pool.near_misses(claims, clustered=True)
    by = {(n["a"], n["b"]): n for n in near}
    apart = by[("plumb-auto:1", "gpt-6-astra:1")]
    assert apart["direction"] == "kept_apart" and apart["overlap_would_merge"] is True and apart["share"] == 1.0
    merged = by[("plumb-auto:2", "gpt-6-astra:2")]
    assert merged["direction"] == "merged" and merged["share"] < eval_pool.NEAR_SHARE
    assert len(near) == 2


def test_overlap_near_misses_are_all_kept_apart_pairs():
    from plumb import eval_pool
    same = "The joint test of the five leads confirms the identifying assumption."
    claims = eval_pool.merge([_cand("plumb-auto", same, ["5"], issue_id="1"), _cand("gpt-6-astra", same, ["9"], ref="gpt-6-astra:1")])
    [n] = eval_pool.near_misses(claims)
    assert n["direction"] == "kept_apart" and n["overlap_would_merge"] is False and n["reason"] == "pages"


# --- the pool on disk: pool.json, two sheets, the sealed mapping ---

def _sources(tmp_path):
    auto = _run(tmp_path, "auto", [
        _issue("1", "The twelve never-treated regions serve as the control group but adopt in 2019.", ms_page=4,
               severity="Undermines the main claim", adjudication="paper", sources=["design_checks.md:DD3"]),
        _issue("2", "The mediator is measured after the outcome.", ms_page=7, adjudication="judgment")])
    std = _run(tmp_path, "std", [
        _issue("1", "The twelve never-treated regions serve as the control group but adopt in 2019.", ms_page=4,
               severity="Undermines the main claim", adjudication="paper"),
        _issue("2", "The mediator is measured after the outcome.", ms_page=7, adjudication="judgment")],
        events=[_answer("majors", "majors:2", "A. Keep it as a major issue (Recommended) | The mediator is measured after the outcome.",
                        "C. The paper already addresses this | The mediator is measured after the outcome.")])
    base = _baseline(tmp_path, {"gpt-6-astra": {1: BASELINE_TEXT},
                                "claude-fable-5-1": {1: "1. **Mediator timing** Severity: Weakens a claim. Page 7. "
                                                        "The mediator is measured after the outcome, so the indirect effect "
                                                        "cannot carry the mechanism.\n"}})
    return auto, std, base


def test_build_writes_pool_sheets_and_sealed_mapping_without_the_rewrite(tmp_path):
    import csv
    from plumb import eval_pool
    auto, std, base = _sources(tmp_path)
    out = tmp_path / "pool"
    pool = eval_pool.build(paper="pilot-exp", auto=auto, standard=std, baseline=base, out=out,
                           raters=("r1", "r2"), seed=7, rewrite_claims=False)
    assert pool["paper"] == "pilot-exp" and pool["seed"] == 7 and pool["rewrite"]["done"] is False
    assert pool["missing"] == []
    by = {tuple(c["sources"]): c for c in pool["claims"]}
    assert ("plumb-auto", "plumb-standard", "gpt-6-astra") in by
    assert ("plumb-auto", "claude-fable-5-1") in by
    assert ("gpt-6-astra",) in by
    assert len(pool["claims"]) == 3
    assert all(c["text"] and not c["rewritten"] for c in pool["claims"])
    assert pool["dry_run"] is True
    assert json.loads((out / "sealed" / "pool.json").read_text())["claims"][0]["id"] == pool["claims"][0]["id"]
    sealed = json.loads((out / "sealed" / "mapping.sealed.json").read_text())
    assert sealed["paper"] == "pilot-exp"
    over = [v for v in sealed["claims"].values() if v["overruled"]]
    assert len(over) == 1 and over[0]["overruled"][0]["item"] == "majors:2"
    assert over[0]["overruled"][0]["adjudication"] == "judgment" and over[0]["overruled"][0]["pack"] == "archival"
    for rater in ("r1", "r2"):
        with (out / "raters" / f"sheet-{rater}.DRYRUN.csv").open(encoding="utf-8", newline="") as fh:
            banner = fh.readline()
            rows = list(csv.DictReader(fh))
        assert banner.startswith("DRY RUN")
        assert list(rows[0].keys()) == ["claim_id", "claim", "pages", "correct", "reason_if_incorrect", "importance", "recognized"]
        assert sorted(r["claim_id"] for r in rows) == ["c01", "c02", "c03"]
        assert all(r["correct"] == "" and r["importance"] == "" and r["recognized"] == "" for r in rows)
        assert [r["claim_id"] for r in rows] == pool["sheet_order"][rater]
    assert not (out / "raters" / "sheet-r1.csv").exists()
    assert (out / "raters" / "instructions.txt").is_file()
    text = (out / "raters" / "instructions.txt").read_text()
    assert all(level in text for level in ("Undermines the main claim", "Weakens a claim", "Minor"))


def test_sheets_carry_no_source_label_or_severity(tmp_path):
    from plumb import eval_pool
    auto, std, base = _sources(tmp_path)
    out = tmp_path / "pool"
    eval_pool.build(paper="p", auto=auto, standard=std, baseline=base, out=out, raters=("r1", "r2"), seed=1,
                    rewrite_claims=False)
    for rater in ("r1", "r2"):
        text = (out / "raters" / f"sheet-{rater}.DRYRUN.csv").read_text(encoding="utf-8").casefold()
        for word in ("plumb", "gpt", "astra", "claude", "fable", "overruled", "auto", "standard", "majors:",
                     "sealed", "condition",
                     "undermines the main claim", "weakens a claim", "severity"):
            assert word not in text, word


def test_the_shuffle_is_fixed_by_the_seed_and_differs_between_raters(tmp_path):
    from plumb import eval_pool
    issues = [_issue(str(n), f"Distinct problem number {n} about variable v{n} in table t{n}.", ms_page=n) for n in range(1, 13)]
    auto = _run(tmp_path, "auto", issues)
    a = eval_pool.build(paper="p", auto=auto, standard=None, baseline=None, out=tmp_path / "a", raters=("r1", "r2"),
                        seed=3, rewrite_claims=False)
    b = eval_pool.build(paper="p", auto=auto, standard=None, baseline=None, out=tmp_path / "b", raters=("r1", "r2"),
                        seed=3, rewrite_claims=False)
    c = eval_pool.build(paper="p", auto=auto, standard=None, baseline=None, out=tmp_path / "c", raters=("r1", "r2"),
                        seed=4, rewrite_claims=False)
    assert a["sheet_order"] == b["sheet_order"]
    assert a["sheet_order"]["r1"] != a["sheet_order"]["r2"]
    assert a["sheet_order"]["r1"] != c["sheet_order"]["r1"]
    assert sorted(a["sheet_order"]["r1"]) == [f"c{n:02d}" for n in range(1, 13)]
    assert a["missing"] == ["plumb-standard", "gpt-6-astra", "claude-fable-5-1"]


def test_build_runs_the_rewrite_through_the_mocked_call_and_records_it(tmp_path, monkeypatch):
    from plumb import eval_pool
    _fake_cluster(monkeypatch)
    monkeypatch.setattr(eval_pool, "call_rewrite", lambda prompt, payload: _reply("A neutral line (p. 4)."))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-FAKE-0001")
    auto, std, base = _sources(tmp_path)
    pool = eval_pool.build(paper="p", auto=auto, standard=std, baseline=base, out=tmp_path / "pool", raters=("r1", "r2"),
                           seed=1, rewrite_claims=True)
    assert pool["rewrite"] == {"done": True, "model": "claude-fable-5-1", "effort": "high",
                               "prompt_file": "pool_rewrite_prompt.txt", "prompt_sha256": eval_pool.REWRITE_PROMPT_SHA256}
    assert all(c["text"] == "A neutral line (p. 4)." and c["rewritten"] for c in pool["claims"])
    assert pool["dry_run"] is False
    assert "A neutral line (p. 4)." in (tmp_path / "pool" / "raters" / "sheet-r1.csv").read_text()
    assert not (tmp_path / "pool" / "raters" / "sheet-r1.DRYRUN.csv").exists()


def test_build_clusters_by_meaning_and_records_the_call(tmp_path, monkeypatch):
    from plumb import eval_pool
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-FAKE-0001")
    monkeypatch.setattr(eval_pool, "call_rewrite", lambda prompt, payload: _reply("A neutral line (p. 4)."))
    auto = _run(tmp_path, "auto", [_issue("1", PARAPHRASE_A, ms_page=4),
                                   _issue("2", "The joint test of the five leads confirms the identifying assumption.", ms_page=5)])
    base = _baseline(tmp_path, {"gpt-6-astra": {1: "1. Reform timing\nSeverity: Minor\nPage 4\n" + PARAPHRASE_B + "\n\n"
                                                    "2. Leads\nSeverity: Minor\nPage 5\n"
                                                    "The joint test of the five leads confirms the identifying assumption.\n"}})
    # The clusterer joins the paraphrase and keeps the leads pair apart.
    calls = _fake_cluster(monkeypatch, _by_ref(["plumb-auto:1", "gpt-6-astra:1"], ["plumb-auto:2"], ["gpt-6-astra:2"]))
    pool = eval_pool.build(paper="p", auto=auto, standard=None, baseline=base, out=tmp_path / "pool", raters=("r1", "r2"),
                           seed=1, rewrite_claims=True)
    assert calls == [4] and pool["merge"] == "cluster"
    assert sorted(tuple(c["sources"]) for c in pool["claims"]) == [("gpt-6-astra",), ("plumb-auto",), ("plumb-auto", "gpt-6-astra")]
    order = pool["cluster"].pop("order")
    assert pool["cluster"].pop("max_tokens") == 64000
    assert sorted(order) == sorted(["plumb-auto:1", "plumb-auto:2", "gpt-6-astra:1", "gpt-6-astra:2"])
    assert pool["cluster"] == {"done": True, "model": "claude-fable-5-1", "effort": "high",
                               "prompt_file": "pool_cluster_prompt.txt", "prompt_sha256": eval_pool.CLUSTER_PROMPT_SHA256,
                               "groups": 3, "from": None,
                               "call": {"model": "claude-fable-5-1-20260901", "request_id": "req_cl", "cached": False,
                                        "usage": {"input_tokens": 900, "output_tokens": 40}}}
    on_disk = json.loads((tmp_path / "pool" / "sealed" / "pool.json").read_text())
    assert on_disk["merge"] == "cluster" and on_disk["cluster"]["call"]["request_id"] == "req_cl"
    assert len(json.loads((tmp_path / "pool" / "sealed" / "clusters.json").read_text())) == 1
    near = json.loads((tmp_path / "pool" / "sealed" / "near_misses.json").read_text())
    assert {(n["a"], n["b"], n["direction"]) for n in near} == {("plumb-auto:2", "gpt-6-astra:2", "kept_apart"),
                                                              ("plumb-auto:1", "gpt-6-astra:1", "merged")}
    assert next(n for n in near if n["direction"] == "kept_apart")["overlap_would_merge"] is True


def test_a_paper_with_no_candidates_builds_an_empty_pool_without_a_clustering_call(tmp_path, monkeypatch):
    from plumb import eval_pool
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-FAKE-0001")
    calls = _fake_cluster(monkeypatch)
    pool = eval_pool.build(paper="p", auto=_run(tmp_path, "auto", []), standard=None, baseline=None, out=tmp_path / "pool",
                           raters=("r1", "r2"), seed=1, rewrite_claims=True)
    assert calls == [] and pool["claims"] == [] and pool["merge"] == "cluster"
    assert pool["cluster"]["call"] is None and pool["cluster"]["groups"] == 0 and pool["cluster"]["order"] == []


def test_a_hand_merge_applies_after_the_clustering_and_is_recorded(tmp_path, monkeypatch):
    from plumb import eval_pool
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-FAKE-0001")
    monkeypatch.setattr(eval_pool, "call_rewrite", lambda prompt, payload: _reply("A neutral line (p. 5)."))
    _fake_cluster(monkeypatch, lambda cands: [[1], [2]])
    same = "The joint test of the five leads confirms the identifying assumption."
    auto = _run(tmp_path, "auto", [_issue("1", same, ms_page=5)])
    base = _baseline(tmp_path, {"gpt-6-astra": {1: "1. Leads\nSeverity: Minor\nPage 5\n" + same + "\n"}})
    merges = tmp_path / "merges.json"
    merges.write_text(json.dumps([["plumb-auto:1", "gpt-6-astra:1"]]), encoding="utf-8")
    pool = eval_pool.build(paper="p", auto=auto, standard=None, baseline=base, out=tmp_path / "pool", raters=("r1", "r2"),
                           seed=1, rewrite_claims=True, hand_merges=merges)
    assert pool["merge"] == "cluster" and len(pool["claims"]) == 1
    assert pool["hand_merges"]["merged"] == 1 and pool["hand_merges"]["file"] == str(merges)
    # The near misses describe the clusterer's grouping, before the hand pass joined the pair.
    near = json.loads((tmp_path / "pool" / "sealed" / "near_misses.json").read_text())
    assert [(n["a"], n["b"], n["direction"]) for n in near] == [("plumb-auto:1", "gpt-6-astra:1", "kept_apart")]


# --- the hand pass checks the grouping that ships: a clusters-only run, then --clusters-from ---

def _leads_pair(tmp_path, name="auto", text="The joint test of the five leads confirms the identifying assumption."):
    auto = _run(tmp_path, name, [_issue("1", text, ms_page=5), _issue("2", PARAPHRASE_A, ms_page=4)])
    base = _baseline(tmp_path, {"gpt-6-astra": {1: "1. Leads\nSeverity: Minor\nPage 5\n"
                                                    "The joint test of the five leads confirms the identifying assumption.\n\n"
                                                    "2. Reform timing\nSeverity: Minor\nPage 4\n" + PARAPHRASE_B + "\n"}})
    return auto, base


def _no_rewrite_call(monkeypatch):
    from plumb import eval_pool

    def no_call(prompt, payload):
        raise AssertionError("this run must not rewrite")

    monkeypatch.setattr(eval_pool, "call_rewrite", no_call)


def test_a_clusters_only_run_writes_the_groups_and_near_misses_and_stops(tmp_path, monkeypatch):
    from plumb import eval_pool
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-FAKE-0001")
    _no_rewrite_call(monkeypatch)
    calls = _fake_cluster(monkeypatch, _by_ref(["plumb-auto:2", "gpt-6-astra:2"], ["plumb-auto:1"], ["gpt-6-astra:1"]))
    auto, base = _leads_pair(tmp_path)
    out = tmp_path / "clusters"
    result = eval_pool.build(paper="p", auto=auto, standard=None, baseline=base, out=out, raters=("r1", "r2"),
                             seed=1, stop_after_clusters=True)
    assert calls == [4] and result["clusters_only"] is True and result["claims"] == 3 and result["near_misses"] == 2
    assert (out / "sealed" / "clusters.json").is_file()
    near = json.loads((out / "sealed" / "near_misses.json").read_text())
    assert {(n["a"], n["b"], n["direction"]) for n in near} == {("plumb-auto:1", "gpt-6-astra:1", "kept_apart"),
                                                              ("plumb-auto:2", "gpt-6-astra:2", "merged")}
    assert not (out / "sealed" / "pool.json").exists() and not (out / "raters").exists()
    assert sorted(p.name for p in (out / "sealed").iterdir()) == ["clusters.json", "near_misses.json"]


def test_the_real_run_reuses_the_checked_groups_applies_hand_merges_and_records_the_file(tmp_path, monkeypatch):
    import hashlib
    from plumb import eval_pool
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-FAKE-0001")
    _no_rewrite_call(monkeypatch)
    _fake_cluster(monkeypatch, _by_ref(["plumb-auto:2", "gpt-6-astra:2"], ["plumb-auto:1"], ["gpt-6-astra:1"]))
    auto, base = _leads_pair(tmp_path)
    eval_pool.build(paper="p", auto=auto, standard=None, baseline=base, out=tmp_path / "clusters", raters=("r1", "r2"),
                    seed=1, stop_after_clusters=True)
    groups_file = tmp_path / "clusters" / "sealed" / "clusters.json"

    def no_call(candidates):
        raise AssertionError("the real run must reuse the checked groups")

    monkeypatch.setattr(eval_pool, "call_cluster", no_call)
    monkeypatch.setattr(eval_pool, "call_rewrite", lambda prompt, payload: _reply("A neutral line (p. 5)."))
    merges = tmp_path / "merges.json"
    merges.write_text(json.dumps([["plumb-auto:1", "gpt-6-astra:1"]]), encoding="utf-8")
    pool = eval_pool.build(paper="p", auto=auto, standard=None, baseline=base, out=tmp_path / "pool", raters=("r1", "r2"),
                           seed=1, clusters_from=groups_file, hand_merges=merges)
    assert sorted(tuple(c["sources"]) for c in pool["claims"]) == [("plumb-auto", "gpt-6-astra")] * 2
    assert pool["hand_merges"]["merged"] == 1 and pool["merge"] == "cluster"
    assert pool["cluster"]["from"] == {"file": str(groups_file), "sha256": hashlib.sha256(groups_file.read_bytes()).hexdigest()}
    assert pool["cluster"]["call"]["cached"] is True and pool["cluster"]["call"]["request_id"] == "req_cl"
    assert json.loads((tmp_path / "pool" / "sealed" / "pool.json").read_text())["cluster"]["from"]["file"] == str(groups_file)
    assert (tmp_path / "pool" / "raters" / "sheet-r1.csv").is_file()
    near = json.loads((tmp_path / "pool" / "sealed" / "near_misses.json").read_text())
    assert near == json.loads((tmp_path / "clusters" / "sealed" / "near_misses.json").read_text())


def test_clusters_from_refuses_groups_made_for_other_candidates_or_another_prompt(tmp_path, monkeypatch):
    from plumb import eval_pool
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-FAKE-0001")
    _no_rewrite_call(monkeypatch)
    _fake_cluster(monkeypatch)
    auto, base = _leads_pair(tmp_path)
    eval_pool.build(paper="p", auto=auto, standard=None, baseline=base, out=tmp_path / "clusters", raters=("r1", "r2"),
                    seed=1, stop_after_clusters=True)
    groups_file = tmp_path / "clusters" / "sealed" / "clusters.json"
    other, _ = _leads_pair(tmp_path / "x", text="A different first issue about the leads.")
    with pytest.raises(eval_pool.PoolError, match="the candidates differ"):
        eval_pool.build(paper="p", auto=other, standard=None, baseline=base, out=tmp_path / "a", raters=("r1", "r2"),
                        seed=1, clusters_from=groups_file)
    real = eval_pool.load_cluster_prompt()
    monkeypatch.setattr(eval_pool, "load_cluster_prompt", lambda: real + " Changed.")
    monkeypatch.setattr(eval_pool, "CLUSTER_PROMPT_SHA256", "f" * 64)
    with pytest.raises(eval_pool.PoolError, match="the clustering prompt differs"):
        eval_pool.build(paper="p", auto=auto, standard=None, baseline=base, out=tmp_path / "b", raters=("r1", "r2"),
                        seed=1, clusters_from=groups_file)
    with pytest.raises(eval_pool.PoolError, match="missing"):
        eval_pool.build(paper="p", auto=auto, standard=None, baseline=base, out=tmp_path / "c", raters=("r1", "r2"),
                        seed=1, clusters_from=tmp_path / "nope.json")


@pytest.mark.parametrize("flags, problem", [
    ({"stop_after_clusters": True, "rewrite_claims": False}, "--no-rewrite"),
    ({"stop_after_clusters": True, "hand_merges": "m.json"}, "--hand-merges"),
    ({"stop_after_clusters": True, "clusters_from": "c.json"}, "--clusters-from"),
    ({"clusters_from": "c.json", "rewrite_claims": False}, "--no-rewrite"),
])
def test_clusters_only_and_clusters_from_refuse_flags_that_do_not_fit(tmp_path, flags, problem):
    from plumb import eval_pool
    with pytest.raises(eval_pool.PoolError, match=problem):
        eval_pool.build(paper="p", auto=_run(tmp_path, "auto", []), standard=None, baseline=None, out=tmp_path / "o",
                        raters=("r1", "r2"), seed=1, **flags)


def test_pool_script_takes_the_clusters_flags_and_lists_them_in_its_usage(tmp_path):
    import subprocess
    import sys
    auto, std, base = _sources(tmp_path)
    proc = subprocess.run([sys.executable, str(ROOT / "eval" / "pool.py"), "--paper", "p", "--auto", str(auto),
                           "--out", str(tmp_path / "pool"), "--no-rewrite", "--stop-after-clusters"],
                          capture_output=True, text=True)
    assert proc.returncode == 2 and "--no-rewrite" in proc.stderr
    usage = (ROOT / "eval" / "pool.py").read_text(encoding="utf-8").split('"""')[1].split("Output")[0]
    for flag in ("--hand-merges", "--stop-after-clusters", "--clusters-from"):
        assert flag in usage, flag


def test_the_dry_run_uses_the_overlap_merge_and_says_so(tmp_path, monkeypatch):
    from plumb import eval_pool

    def no_call(candidates):
        raise AssertionError("a dry run must not call the clusterer")

    monkeypatch.setattr(eval_pool, "call_cluster", no_call)
    auto, std, base = _sources(tmp_path)
    pool = eval_pool.build(paper="p", auto=auto, standard=std, baseline=base, out=tmp_path / "pool", raters=("r1", "r2"),
                           seed=1, rewrite_claims=False)
    assert pool["merge"] == "overlap" and pool["cluster"]["done"] is False and pool["cluster"]["call"] is None
    assert json.loads((tmp_path / "pool" / "sealed" / "pool.json").read_text())["merge"] == "overlap"
    assert not (tmp_path / "pool" / "sealed" / "clusters.json").exists()


def test_a_rerun_into_a_folder_holding_the_clustering_cache_is_allowed(tmp_path, monkeypatch):
    from plumb import eval_pool
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-FAKE-0001")
    _fake_cluster(monkeypatch)

    def failing(prompt, payload):
        raise RuntimeError("network gone")

    monkeypatch.setattr(eval_pool, "call_rewrite", failing)
    auto, std, base = _sources(tmp_path)
    with pytest.raises(RuntimeError):
        eval_pool.build(paper="p", auto=auto, standard=std, baseline=base, out=tmp_path / "pool", raters=("r1", "r2"),
                        seed=1, rewrite_claims=True)
    assert (tmp_path / "pool" / "sealed" / "clusters.json").is_file()
    eval_pool.check_out(tmp_path / "pool")


def test_build_refuses_to_overwrite_an_existing_pool(tmp_path):
    from plumb import eval_pool
    auto, std, base = _sources(tmp_path)
    out = tmp_path / "pool"
    eval_pool.build(paper="p", auto=auto, standard=std, baseline=base, out=out, raters=("r1", "r2"), seed=1,
                    rewrite_claims=False)
    with pytest.raises(eval_pool.PoolError, match="already"):
        eval_pool.build(paper="p", auto=auto, standard=std, baseline=base, out=out, raters=("r1", "r2"), seed=1,
                        rewrite_claims=False)


def test_pool_script_builds_a_pool_with_no_rewrite(tmp_path):
    import subprocess
    import sys
    auto, std, base = _sources(tmp_path)
    out = tmp_path / "pool"
    proc = subprocess.run([sys.executable, str(ROOT / "eval" / "pool.py"), "--paper", "p", "--auto", str(auto),
                           "--standard", str(std), "--baseline", str(base), "--out", str(out), "--raters", "r1,r2",
                           "--seed", "5", "--no-rewrite"], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert (out / "sealed" / "pool.json").is_file() and (out / "sealed" / "mapping.sealed.json").is_file()
    assert (out / "raters" / "sheet-r1.DRYRUN.csv").is_file() and (out / "raters" / "sheet-r2.DRYRUN.csv").is_file()
    assert "3 claims" in proc.stdout and "no rewrite" in proc.stdout
    assert "merged by word overlap (dry run)" in proc.stdout


def test_pool_script_needs_exactly_two_raters(tmp_path):
    import subprocess
    import sys
    auto, std, base = _sources(tmp_path)
    proc = subprocess.run([sys.executable, str(ROOT / "eval" / "pool.py"), "--paper", "p", "--auto", str(auto),
                           "--out", str(tmp_path / "pool"), "--raters", "r1", "--no-rewrite"], capture_output=True, text=True)
    assert proc.returncode == 2 and "two raters" in proc.stderr


# --- claim ids are random, the layout splits raters from sealed, and the repo is refused ---

def _twelve(tmp_path):
    issues = [_issue(str(n), f"Distinct problem number {n} about variable v{n} in table t{n}.", ms_page=n) for n in range(1, 13)]
    return _run(tmp_path, "auto", issues)


def test_claim_ids_are_a_seeded_permutation_independent_of_merge_order(tmp_path):
    from plumb import eval_pool
    pool = eval_pool.build(paper="p", auto=_twelve(tmp_path), standard=None, baseline=None, out=tmp_path / "a",
                           raters=("r1", "r2"), seed=3, rewrite_claims=False)
    in_merge_order = [c["id"] for c in pool["merge_order"]]
    assert sorted(in_merge_order) == [f"c{n:02d}" for n in range(1, 13)]
    assert in_merge_order != sorted(in_merge_order)
    # pool.json and the mapping list claims by id, not by the order the sources came in.
    assert [c["id"] for c in pool["claims"]] == sorted(in_merge_order)
    sealed = json.loads((tmp_path / "a" / "sealed" / "mapping.sealed.json").read_text())
    assert list(sealed["claims"]) == sorted(in_merge_order)
    again = eval_pool.build(paper="p", auto=_twelve(tmp_path / "x"), standard=None, baseline=None, out=tmp_path / "b",
                            raters=("r1", "r2"), seed=3, rewrite_claims=False)
    assert [c["id"] for c in again["merge_order"]] == in_merge_order


def test_the_first_claim_merged_does_not_get_the_first_id(tmp_path):
    """Auto's issues merge first; with ids random, the issue numbered 1 is not c01 for most seeds."""
    from plumb import eval_pool
    firsts = set()
    for seed in range(6):
        pool = eval_pool.build(paper="p", auto=_twelve(tmp_path / str(seed)), standard=None, baseline=None,
                               out=tmp_path / f"out{seed}", raters=("r1", "r2"), seed=seed, rewrite_claims=False)
        firsts.add(pool["merge_order"][0]["id"])
    assert firsts != {"c01"}


def test_an_out_folder_inside_the_repo_is_refused(tmp_path):
    from plumb import eval_pool
    with pytest.raises(eval_pool.PoolError, match="inside the repo"):
        eval_pool.build(paper="p", auto=_twelve(tmp_path), standard=None, baseline=None, out=ROOT / "eval" / "pool-out",
                        raters=("r1", "r2"), seed=1, rewrite_claims=False)
    assert not (ROOT / "eval" / "pool-out").exists()


# --- the baseline parser: headings, bold titles, printed and PDF pages, and a count check ---

def test_parser_accepts_issue_and_problem_headings_and_bold_numbered_titles():
    from plumb import eval_pool
    text = """## Issue 1: Never-treated regions are treated
Severity: Weakens a claim
Page: printed 12, PDF 14
The control group adopts in 2019.

### Problem 2 - Sample counts disagree
Severity: Minor
Page 7
The text says 1,204 and the table 1,240.

**3. Mediator timing**
Severity: Undermines the main claim
p. 9
The mediator is measured after the outcome. The paper lists:
1. the mediator
2. the outcome
and treats them as ordered.
"""
    entries = eval_pool.parse_issues_md(text)
    assert [e["title"] for e in entries] == ["Never-treated regions are treated", "Sample counts disagree", "Mediator timing"]
    assert [e["pages"] for e in entries] == [["12"], ["7"], ["9"]]
    assert entries[0]["pdf_pages"] == ["14"]
    assert [e["severity"] for e in entries] == ["Weakens a claim", "Minor", "Undermines the main claim"]
    assert "2. the outcome" in entries[2]["body"] and len(entries) == 3


def test_parser_does_not_split_an_entry_on_a_numbered_list_inside_a_field():
    from plumb import eval_pool
    text = "1. First\nSeverity: Minor\nPage 2\n(4) Two things are wrong:\n1. the count\n2. the year\n(5) Fix both.\n\n2. Second\nSeverity: Minor\nPage 3\nBody.\n"
    entries = eval_pool.parse_issues_md(text)
    assert [e["title"] for e in entries] == ["First", "Second"]
    assert "2. the year" in entries[0]["body"]


def test_a_run_of_record_that_parses_to_no_entry_or_a_label_count_mismatch_is_an_error(tmp_path):
    from plumb import eval_pool
    out = _baseline(tmp_path, {"gpt-6-astra": {1: "I found no numbered problems, only Severity: Minor remarks.\n"}})
    with pytest.raises(eval_pool.PoolError, match="no entries"):
        eval_pool.baseline_candidates(out)
    out2 = _baseline(tmp_path / "two", {"gpt-6-astra": {1: "1. One\nSeverity: Minor\nPage 2\nx\n\n2. Two\nPage 3\nno label here\n"}})
    with pytest.raises(eval_pool.PoolError, match="2 entries but 1 severity label"):
        eval_pool.baseline_candidates(out2)


def test_baseline_candidates_report_the_parsed_count_per_model(tmp_path):
    from plumb import eval_pool
    out = _baseline(tmp_path, {"gpt-6-astra": {1: BASELINE_TEXT},
                               "claude-fable-5-1": {1: "1. **Only one** Severity: Minor. Page 2. Something small.\n"}})
    cands, missing, counts = eval_pool.baseline_candidates(out, with_counts=True)
    assert counts == {"gpt-6-astra": 2, "claude-fable-5-1": 1}
    pool = eval_pool.build(paper="p", auto=None, standard=None, baseline=out, out=tmp_path / "pool", raters=("r1", "r2"),
                           seed=1, rewrite_claims=False)
    assert pool["baseline_counts"] == {"gpt-6-astra": 2, "claude-fable-5-1": 1}


# --- what the sealed mapping carries for the rating step ---

def test_mapping_carries_adjudication_missing_sources_raters_and_the_rating_roles(tmp_path):
    from plumb import eval_pool
    auto, std, base = _sources(tmp_path)
    pool = eval_pool.build(paper="p", auto=auto, standard=None, baseline=base, out=tmp_path / "pool", raters=("r1", "r2"),
                           seed=1, rewrite_claims=False, author="r2", nonauthor="r1", joint=False)
    sealed = json.loads((tmp_path / "pool" / "sealed" / "mapping.sealed.json").read_text())
    assert sealed["missing"] == ["plumb-standard"] and sealed["raters"] == ["r1", "r2"]
    assert sealed["author"] == "r2" and sealed["nonauthor"] == "r1" and sealed["joint"] is False
    by = {tuple(v["sources"]): v for v in sealed["claims"].values()}
    # A Plumb candidate types the claim; a baseline-only claim is untyped.
    assert by[("plumb-auto", "gpt-6-astra")]["adjudication"] == "paper"
    assert by[("plumb-auto", "claude-fable-5-1")]["adjudication"] == "judgment"
    assert by[("gpt-6-astra",)]["adjudication"] == "untyped"
    assert pool["author"] == "r2" and pool["joint"] is False


def test_author_and_nonauthor_must_be_the_two_raters(tmp_path):
    from plumb import eval_pool
    auto = _twelve(tmp_path)
    with pytest.raises(eval_pool.PoolError, match="--author"):
        eval_pool.build(paper="p", auto=auto, standard=None, baseline=None, out=tmp_path / "a", raters=("r1", "r2"),
                        seed=1, rewrite_claims=False, author="xx", nonauthor="r1")
    with pytest.raises(eval_pool.PoolError, match="different"):
        eval_pool.build(paper="p", auto=auto, standard=None, baseline=None, out=tmp_path / "b", raters=("r1", "r2"),
                        seed=1, rewrite_claims=False, author="r1", nonauthor="r1")


def test_pool_script_records_the_rating_roles(tmp_path):
    import subprocess
    import sys
    auto, std, base = _sources(tmp_path)
    out = tmp_path / "pool"
    proc = subprocess.run([sys.executable, str(ROOT / "eval" / "pool.py"), "--paper", "p", "--auto", str(auto),
                           "--out", str(out), "--raters", "r1,r2", "--author", "r2", "--nonauthor", "r1", "--joint",
                           "--no-rewrite"], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    sealed = json.loads((out / "sealed" / "mapping.sealed.json").read_text())
    assert sealed["author"] == "r2" and sealed["joint"] is True


# --- second review: the baseline merge text, severity by field, page forms (reviewer's probes) ---

ATTRITION = "1. **Attrition by arm**\n   Severity: Weakens a claim\n   Page: 12\n   What is wrong: attrition differs by arm.\n   Fix: report Lee bounds.\n"
CLUSTERING = "1. **Clustering**\n   Severity: Weakens a claim\n   Page: 12\n   What is wrong: errors not clustered by school.\n   Fix: cluster by school.\n"


def test_baseline_merge_text_is_the_title_and_what_is_wrong_without_boilerplate():
    from plumb import eval_pool
    a = eval_pool.parse_issues_md(ATTRITION)[0]
    assert a["text"] == "Attrition by arm attrition differs by arm."
    for word in ("Severity", "Weakens", "Page", "Fix", "Lee bounds", "What is wrong"):
        assert word not in a["text"], word
    assert "Fix: report Lee bounds." in a["body"]
    fields = eval_pool.parse_issues_md("1. Treated controls\n(2) Minor\n(3) 4\n(4) The regions adopt in 2019.\n(5) Drop them.\n")[0]
    assert fields["text"] == "Treated controls The regions adopt in 2019."


def test_two_unrelated_baseline_items_on_one_page_do_not_merge():
    from plumb import eval_pool
    a = eval_pool.parse_issues_md(ATTRITION)[0]
    b = eval_pool.parse_issues_md(CLUSTERING)[0]
    ca = eval_pool._candidate("gpt-6-astra", a["text"], pages=a["pages"], raw=a["body"])
    cb = eval_pool._candidate("claude-fable-5-1", b["text"], pages=b["pages"], raw=b["body"])
    assert eval_pool.overlap_share(ca["text"], cb["text"]) < 0.5
    assert len(eval_pool.merge([ca, cb])) == 2


def test_a_baseline_item_and_a_plumb_issue_merge_once_the_boilerplate_is_gone(tmp_path):
    from plumb import eval_pool
    plumb = ("The twelve never-treated regions serve as the control group but Table 1 shows they adopt the policy in "
             "2019, so the control group is contaminated by treated units and the event-study estimates lean on them.")
    base_text = ("1. **Control regions adopt**\n   Severity: Weakens a claim\n   Page: 4 (PDF 6)\n"
                 "   What is wrong: the never-treated regions adopt in 2019, contaminating the control group.\n"
                 "   Fix: drop them.\n")
    entry = eval_pool.parse_issues_md(base_text)[0]
    # The whole body is the shorter text, and its field labels dilute the share below the merge line.
    assert eval_pool.overlap_share(entry["body"], plumb) < 0.5
    assert eval_pool.overlap_share(entry["text"], plumb) > 0.5
    cands = [_cand("plumb-auto", plumb, ["4"], issue_id="1"),
             eval_pool._candidate("gpt-6-astra", entry["text"], pages=entry["pages"], raw=entry["body"], ref="gpt-6-astra:1")]
    assert len(eval_pool.merge(cands)) == 1
    out = _baseline(tmp_path, {"gpt-6-astra": {1: base_text}})
    cands, missing = eval_pool.baseline_candidates(out)
    assert cands[0]["text"] == entry["text"] and cands[0]["raw"] == entry["body"]


def test_severity_is_read_only_from_the_severity_field_with_word_boundaries():
    from plumb import eval_pool
    t = "1. Minority-owned firms misclassified\nSeverity: Undermines the main claim\nPage: 4\nThe coding is wrong.\n"
    e = eval_pool.parse_issues_md(t)
    assert e[0]["severity"] == "Undermines the main claim"
    eval_pool.check_parse("m", t, e)
    t2 = "1. Treated controls\nSeverity: Weakens a claim\nPage: 4\nThis is a minor point in the text but weakens a claim about wages.\n"
    e2 = eval_pool.parse_issues_md(t2)
    assert e2[0]["severity"] == "Weakens a claim"
    eval_pool.check_parse("f", t2, e2)
    assert eval_pool.count_severity_labels(t2) == 1
    fields = eval_pool.parse_issues_md("1. **Sample counts**\n(2) Minor\n(3) 7\n(4) Counts differ.\n")[0]
    assert fields["severity"] == "Minor"
    assert eval_pool.parse_issues_md("1. **Only one** Severity: Minor. Page 2. Something small.\n")[0]["severity"] == "Minor"


def test_a_checked_parse_count_mismatch_can_be_accepted_and_is_recorded(tmp_path):
    from plumb import eval_pool
    text = "1. One\nSeverity: Minor\nPage 2\nx\n\n2. Two\nPage 3\nno label here\n"
    out = _baseline(tmp_path, {"gpt-6-astra": {1: text}})
    with pytest.raises(eval_pool.PoolError, match="2 entries but 1 severity label"):
        eval_pool.baseline_candidates(out)
    cands, missing, counts = eval_pool.baseline_candidates(out, with_counts=True, accept_parse_count=True)
    assert counts == {"gpt-6-astra": 2} and len(cands) == 2
    pool = eval_pool.build(paper="p", auto=None, standard=None, baseline=out, out=tmp_path / "pool", raters=("r1", "r2"),
                           seed=1, rewrite_claims=False, accept_parse_count=True)
    assert pool["departures"] == [{"model": "gpt-6-astra", "entries": 2, "severity_labels": 1,
                                   "note": "parse count accepted by --accept-parse-count after a human check"}]
    assert pool["accept_parse_count"] is True


def test_pool_script_takes_accept_parse_count(tmp_path):
    import subprocess
    import sys
    out = _baseline(tmp_path, {"gpt-6-astra": {1: "1. One\nSeverity: Minor\nPage 2\nx\n\n2. Two\nPage 3\nno label\n"}})
    args = [sys.executable, str(ROOT / "eval" / "pool.py"), "--paper", "p", "--baseline", str(out), "--out", str(tmp_path / "pool"),
            "--raters", "r1,r2", "--no-rewrite"]
    proc = subprocess.run(args, capture_output=True, text=True)
    assert proc.returncode == 2 and "severity label" in proc.stderr
    proc = subprocess.run(args + ["--accept-parse-count"], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert "departure" in proc.stdout


def test_printed_page_in_the_third_field_and_before_a_pdf_page():
    from plumb import eval_pool
    text = ("1. **Treated controls**\n(2) Weakens a claim\n(3) 12 (PDF 14)\n(4) The never-treated regions adopt in 2019.\n\n"
            "2. **Sample counts**\n(2) Minor\n(3) Printed page 7; PDF page 9\n(4) Counts differ.\n\n"
            "3. **Third**\n(2) Minor\n(3) 21\n(4) Something.\n")
    e = eval_pool.parse_issues_md(text)
    assert [(x["pages"], x["pdf_pages"]) for x in e] == [(["12"], ["14"]), (["7"], ["9"]), (["21"], [])]
    assert eval_pool.parse_issues_md("1. T\nSeverity: Minor\nPage: printed 3-5, PDF 5-7\nx\n")[0]["pages"] == ["3", "4", "5"]


# --- the id seed is secret unless given, and never printed ---

def test_without_a_seed_the_ids_come_from_a_secret_seed_stored_only_under_sealed(tmp_path):
    from plumb import eval_pool
    a = eval_pool.build(paper="p", auto=_twelve(tmp_path), standard=None, baseline=None, out=tmp_path / "a",
                        raters=("r1", "r2"), seed=None, rewrite_claims=False)
    b = eval_pool.build(paper="p", auto=_twelve(tmp_path / "x"), standard=None, baseline=None, out=tmp_path / "b",
                        raters=("r1", "r2"), seed=None, rewrite_claims=False)
    assert isinstance(a["seed"], int) and a["seed"] != b["seed"]
    assert a["seed"] == json.loads((tmp_path / "a" / "sealed" / "pool.json").read_text())["seed"]
    for name in ("sealed/mapping.sealed.json", "raters/sheet-r1.DRYRUN.csv", "raters/instructions.txt"):
        assert str(a["seed"]) not in (tmp_path / "a" / name).read_text()
    assert "seed" not in (tmp_path / "a" / "sealed" / "mapping.sealed.json").read_text()


def test_a_given_seed_is_honored_and_stored_only_under_sealed(tmp_path):
    from plumb import eval_pool
    a = eval_pool.build(paper="p", auto=_twelve(tmp_path), standard=None, baseline=None, out=tmp_path / "a",
                        raters=("r1", "r2"), seed=424242, rewrite_claims=False)
    b = eval_pool.build(paper="p", auto=_twelve(tmp_path / "x"), standard=None, baseline=None, out=tmp_path / "b",
                        raters=("r1", "r2"), seed=424242, rewrite_claims=False)
    assert a["sheet_order"] == b["sheet_order"] and [c["id"] for c in a["merge_order"]] == [c["id"] for c in b["merge_order"]]
    assert "424242" not in (tmp_path / "a" / "raters" / "sheet-r1.DRYRUN.csv").read_text()
    assert "424242" not in (tmp_path / "a" / "sealed" / "mapping.sealed.json").read_text()


def test_pool_script_prints_no_seed(tmp_path):
    import re
    import subprocess
    import sys
    auto, std, base = _sources(tmp_path)
    for extra in ([], ["--seed", "987654321"]):
        out = tmp_path / ("pool" + str(len(extra)))
        proc = subprocess.run([sys.executable, str(ROOT / "eval" / "pool.py"), "--paper", "p", "--auto", str(auto),
                               "--out", str(out), "--raters", "r1,r2", "--no-rewrite"] + extra, capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        assert "seed" not in proc.stdout.lower() and "987654321" not in proc.stdout
        seed = json.loads((out / "sealed" / "pool.json").read_text())["seed"]
        assert str(seed) not in proc.stdout and not re.search(r"\b\d{6,}\b", proc.stdout)


# --- hand-merge counts by source; same-source pairs are no near miss ---

def test_hand_merge_counts_by_the_candidates_source_not_the_ref_prefix():
    from plumb import eval_pool
    same = "The joint test of the five leads confirms the identifying assumption."
    cands = [_cand("plumb-standard", same, ["5"], item="minors:4", ref="plumb-standard:minors:4"),
             _cand("gpt-6-astra", same, ["9"], ref="gpt-6-astra:1")]
    claims = eval_pool.merge(cands)
    record = eval_pool.apply_hand_merges(claims, [["plumb-standard:minors:4", "gpt-6-astra:1"]])
    assert record["by_source"] == {"plumb-standard": 1, "gpt-6-astra": 1}


def test_near_misses_skip_pairs_from_one_source():
    from plumb import eval_pool
    cands = [_cand("gpt-6-astra", "The joint test of the five leads confirms the identifying assumption.", ["5"], ref="gpt-6-astra:1"),
             _cand("gpt-6-astra", "The joint test of the leads has little power against a pre-trend.", ["5"], ref="gpt-6-astra:2"),
             _cand("plumb-auto", "The joint test of the leads has little power against a pre-trend.", ["7"], issue_id="1")]
    claims = eval_pool.merge(cands)
    near = eval_pool.near_misses(claims)
    assert [(n["a"], n["b"]) for n in near] == [("gpt-6-astra:1", "plumb-auto:1"), ("gpt-6-astra:2", "plumb-auto:1")]


# --- blinding: one page form on every claim, whatever the source wrote ---

def test_page_label_is_one_form_for_a_page_a_range_and_nothing():
    from plumb import eval_pool
    assert eval_pool.page_label(["4"]) == "p. 4"
    assert eval_pool.page_label(["4", "5", "6"]) == "pp. 4-6"
    assert eval_pool.page_label(["4", "9"]) == "pp. 4, 9"
    assert eval_pool.page_label(["9", "4", "5"]) == "pp. 4-5, 9"
    assert eval_pool.page_label([]) == "p. ?"


def test_the_rewrite_prompt_fixes_the_page_form_and_forbids_repeating_the_input_list():
    from plumb import eval_pool
    prompt = eval_pool.load_rewrite_prompt()
    assert '"p. N"' in prompt and '"pp. N-M"' in prompt
    assert "never repeat" in prompt.casefold() or "do not repeat" in prompt.casefold()


def test_sheets_print_pages_in_one_form_for_a_baseline_range_and_a_plumb_page(tmp_path):
    import csv
    from plumb import eval_pool
    auto = _run(tmp_path, "auto", [_issue("1", "A plumb point about the control group adoption year.", ms_page=4)])
    base = _baseline(tmp_path, {"claude-fable-5-1": {1: "1. A baseline point\nSeverity: Minor\nPages 9-11\nThe clustering ignores state-level variation.\n"}})
    eval_pool.build(paper="p", auto=auto, standard=None, baseline=base, out=tmp_path / "pool", raters=("r1", "r2"),
                    seed=1, rewrite_claims=False)
    with (tmp_path / "pool" / "raters" / "sheet-r1.DRYRUN.csv").open(encoding="utf-8", newline="") as fh:
        fh.readline()
        rows = list(csv.DictReader(fh))
    assert sorted(r["pages"] for r in rows) == ["p. 4", "pp. 9-11"]
    assert all(r["claim"].endswith((" (p. 4)", " (pp. 9-11)")) for r in rows)
    payloads = [eval_pool.rewrite_payload(c) for c in eval_pool.merge(eval_pool.plumb_candidates(auto, "plumb-auto"))]
    assert payloads[0].endswith("(p. 4): A plumb point about the control group adoption year.") or "p. 4" in payloads[0]


def test_a_plumb_issue_without_a_printed_page_takes_its_pdf_page_only_when_the_run_says_they_coincide(tmp_path):
    from plumb import eval_pool
    run = _run(tmp_path, "auto", [_issue("1", "No printed page here.", ms_page=None, pdf_page=6)])
    assert eval_pool.plumb_candidates(run, "plumb-auto")[0]["pages"] == []
    ws = run / ".workspace"
    ws_run = json.loads((ws / "run.json").read_text())
    (ws / "run.json").write_text(json.dumps(dict(ws_run, page_offset=0)), encoding="utf-8")
    assert eval_pool.plumb_candidates(run, "plumb-auto")[0]["pages"] == ["6"]
    (ws / "run.json").write_text(json.dumps(dict(ws_run, page_offset=2)), encoding="utf-8")
    assert eval_pool.plumb_candidates(run, "plumb-auto")[0]["pages"] == []
    (ws / "run.json").write_text(json.dumps(ws_run), encoding="utf-8")
    (ws / "table_pages").mkdir()
    (ws / "table_pages" / "index.json").write_text(json.dumps([{"table": "Table 1", "page": 3, "ms_page": 3},
                                                               {"table": "Table 2", "page": 5, "ms_page": 5}]), encoding="utf-8")
    assert eval_pool.plumb_candidates(run, "plumb-auto")[0]["pages"] == ["6"]


def test_an_against_drop_with_no_page_prints_p_question_mark(tmp_path):
    from plumb import eval_pool
    std = _run(tmp_path, "std", [], events=[_answer("against", "against:1", "A. Plausible (Recommended) | Reverse causality drives the result.",
                                                     "C. Not plausible here | Reverse causality drives the result.")])
    pool = eval_pool.build(paper="p", auto=None, standard=std, baseline=None, out=tmp_path / "pool", raters=("r1", "r2"),
                           seed=1, rewrite_claims=False)
    assert pool["claims"][0]["text"].endswith(" (p. ?)")
    assert "p. ?" in (tmp_path / "pool" / "raters" / "sheet-r1.DRYRUN.csv").read_text()


def test_readme_says_the_pool_clusters_by_meaning_and_cites_the_prompt_hash():
    from plumb import eval_pool
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "eval/pool_cluster_prompt.txt" in readme and eval_pool.CLUSTER_PROMPT_SHA256 in readme
    assert "by meaning" in readme and "dry run" in readme and "sealed/clusters.json" in readme
    assert "merged across sources when more than half" not in readme
    flat = " ".join(readme.split())
    assert "--stop-after-clusters" in flat and "--clusters-from" in flat and "there are no hand splits" in flat
    assert "they are never used to carry results between folders" not in flat
