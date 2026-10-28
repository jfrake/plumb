"""plumb.eval_override and eval/override_rate.py: the override rate of one Standard run from
audit/events.jsonl, with denominators, by stage, pack, and adjudication type. Every run folder
here is a small fake written by the test."""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

from plumb import eval_override

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "eval" / "override_rate.py"


def _issue(id_, summary, kind="major", adjudication="judgment", checkin=None, sources=(), severity="Weakens a claim"):
    return {"id": id_, "kind": kind, "title": f"Issue {id_}", "severity": severity, "adjudication": adjudication,
            "solvability": "new analysis", "summary": summary, "excerpt": "", "ms_page": 1,
            "checkin": checkin or f"majors:{id_}", "sources": list(sources), "why": "", "settle": ""}


def _answer(stop, item, recommended, answer, note=""):
    return {"ts": "2026-10-05T00:00:00+00:00", "kind": "checkin", "stop": stop, "item": item,
            "recommended": recommended, "answer": answer, "note": note}


def _run(tmp_path, issues, events, files=None, packs=("archival", "survey")):
    ws = tmp_path / "plumb_output" / "2026-10-05" / ".workspace"
    (ws / "stage-5").mkdir(parents=True)
    (ws / "audit").mkdir()
    (ws / "run.json").write_text(json.dumps({"depth": "standard", "packs": list(packs)}), encoding="utf-8")
    (ws / "stage-5" / "issues.json").write_text(json.dumps(issues), encoding="utf-8")
    (ws / "audit" / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    for rel, body in (files or {}).items():
        p = ws / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body if isinstance(body, str) else json.dumps(body), encoding="utf-8")
    return ws.parent


MAJORS_DRAFT = "# Majors\n\n## 1. One.\n\nSeverity: Weakens a claim. Adjudication: paper.\nPack: survey\n\n## 2. Two.\n\nSeverity: Minor. Adjudication: judgment.\n"


def _standard(tmp_path):
    issues = [_issue("1", "One.", adjudication="paper", sources=["survey_checks.md:S1"]),
              _issue("2", "Two.", adjudication="judgment"),
              _issue("m1", "A minor.", kind="minor", adjudication="paper", checkin="minors:1")]
    events = [
        _answer("setup", "setup:depth", "A. Standard (Recommended)", "B. Quick", note="preference"),
        _answer("numbers", "numbers:text:3", "A. Real problem in the paper (Recommended)", "B. Extraction error"),
        _answer("numbers", "numbers:cell:t1:r1:c1", "A. Leave it blank (Recommended)", "B. Reading 1: 0.26"),
        _answer("numbers", "numbers:arith:t2:r1:sum", "A. Real problem in the paper (Recommended)",
                "A. Real problem in the paper (Recommended)"),
        _answer("read", "read:summary", "A. Yes, continue (Recommended)", "B. Correct something", note="the DV is wages"),
        _answer("against", "against:1", "A. Plausible, investigate further (Recommended) | Alt one.",
                "B. Plausible, but the paper handles it | Alt one.", note="p.3: handled"),
        _answer("against", "against:2", "A. Plausible, investigate further (Recommended) | Alt two.",
                "A. Plausible, investigate further (Recommended) | Alt two."),
        _answer("majors", "majors:1", "A. Keep it as a major issue (Recommended) | One.", "B. It is real, but minor | One."),
        _answer("majors", "majors:2", "A. Keep it as a major issue (Recommended) | Two.",
                "A. Keep it as a major issue (Recommended) | Two.", note="auto"),
        _answer("minors", "minors:list", "A. Keep all (Recommended)", "C. Let me pick"),
        _answer("minors", "minors:1", "Keep (Recommended)", "Drop: A minor"),
        _answer("draft", "draft:ruling:2", "A. Accept the ruling (Recommended)", "B. Overturn it"),
        _answer("draft", "draft:ready", "A. The outputs are ready (Recommended)", "A. The outputs are ready (Recommended)"),
    ]
    flags = [{"id": "1", "item": "numbers:text:3", "kind": "number", "title": "t", "severity": None, "summary": "s",
              "excerpt": None, "ms_page": 7, "pdf_page": None, "table": None, "cells": []},
             {"id": "2", "item": "numbers:arith:t2:r1:sum", "kind": "number", "title": "t", "severity": None, "summary": "s",
              "excerpt": None, "ms_page": 8, "pdf_page": None, "table": None, "cells": []}]
    return _run(tmp_path, issues, events, files={"stage-1/flags.json": flags, "stage-4/majors_draft.md": MAJORS_DRAFT})


def test_every_override_is_listed_with_its_stage_pack_and_type(tmp_path):
    r = eval_override.override_rate(_standard(tmp_path))
    rows = {o["item"]: o for o in r["overrides"]}
    # Overrides per checkin.is_override: the numbers B answers, read B, against B, majors B, the
    # dropped minor, and the overturned ruling. majors:2 was auto, draft:ready matched, arith matched.
    assert sorted(rows) == ["against:1", "draft:ruling:2", "majors:1", "minors:1", "numbers:cell:t1:r1:c1", "numbers:text:3", "read:summary"]
    assert rows["majors:1"] == {"item": "majors:1", "stop": "majors", "stage": 4, "pack": "survey", "adjudication": "paper",
                                "kind": "demotion", "answer": "B. It is real, but minor | One."}
    assert rows["against:1"]["kind"] == "handled" and rows["against:1"]["pack"] == "unknown"
    assert rows["draft:ruling:2"]["kind"] == "ruling overturned" and rows["draft:ruling:2"]["adjudication"] == "judgment"
    assert rows["minors:1"]["kind"] == "drop" and rows["minors:1"]["adjudication"] == "paper"
    assert rows["numbers:text:3"]["kind"] == "drop" and rows["numbers:text:3"]["adjudication"] == "paper"
    assert rows["numbers:cell:t1:r1:c1"]["kind"] == "reading" and rows["numbers:cell:t1:r1:c1"]["pack"] == "core"
    assert rows["read:summary"]["kind"] == "correction" and rows["read:summary"]["stage"] == 2


def test_denominators_are_the_user_answers_at_the_judgment_stops(tmp_path):
    r = eval_override.override_rate(_standard(tmp_path))
    # User answers: numbers 3, read 1, against 2, majors 1 (majors:2 was auto), minors 1 (the
    # list choice C is a mode choice), draft 2 = 10; overrides 7.
    assert r["totals"] == {"overrides": 7, "answers": 10, "rate": 70.0}
    assert r["by_stage"]["1"] == {"overrides": 2, "answers": 3, "rate": pytest_approx(66.67)}
    assert r["by_stage"]["4"] == {"overrides": 1, "answers": 1, "rate": 100.0}
    assert r["by_stop"]["draft"] == {"overrides": 1, "answers": 2, "rate": 50.0}
    assert r["by_pack"]["survey"] == {"overrides": 1, "answers": 1, "rate": 100.0}
    assert r["by_adjudication"]["paper"]["overrides"] == 4
    assert r["auto_answers"] == 1 and r["dig_deeper"] == 0


def pytest_approx(x):
    import pytest
    return pytest.approx(x, abs=0.01)


def test_an_orphaned_major_takes_its_pack_and_type_from_majors_draft_else_unknown(tmp_path):
    run = _run(tmp_path, [], [_answer("majors", "majors:1", "A. Keep (Recommended) | One.", "C. Addressed | One.")],
               files={"stage-4/majors_draft.md": MAJORS_DRAFT})
    r = eval_override.override_rate(run)
    assert r["overrides"][0]["pack"] == "survey" and r["overrides"][0]["adjudication"] == "paper"
    run2 = _run(tmp_path / "two", [], [_answer("majors", "majors:9", "A. Keep (Recommended) | Nine.", "C. Addressed | Nine.")])
    r2 = eval_override.override_rate(run2)
    assert r2["overrides"][0]["pack"] == "unknown" and r2["overrides"][0]["adjudication"] == "unknown"


def test_markdown_has_the_four_tables(tmp_path):
    text = eval_override.markdown(eval_override.override_rate(_standard(tmp_path)))
    for head in ("by stage", "by stop", "by pack", "by adjudication"):
        assert head in text
    assert "| majors:1 | majors | 4 | survey | paper | demotion |" in text
    assert chr(0x2014) not in text


def test_script_prints_json_then_markdown(tmp_path):
    proc = subprocess.run([sys.executable, str(SCRIPT), str(_standard(tmp_path))], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    head, sep, tail = proc.stdout.partition("\n## ")
    assert json.loads(head)["totals"]["overrides"] == 7 and sep and "by stage" in tail


def test_script_rejects_a_folder_that_is_no_run(tmp_path):
    proc = subprocess.run([sys.executable, str(SCRIPT), str(tmp_path)], capture_output=True, text=True)
    assert proc.returncode == 2 and "run folder" in proc.stderr


def test_an_against_item_is_typed_from_the_issue_that_names_it_as_the_pool_does(tmp_path):
    issues = [_issue("1", "Rests on alternative one.", adjudication="paper", sources=["against:1", "survey_checks.md:S2"]),
              _issue("2", "Built at the against stop.", adjudication="external", checkin="against:2")]
    run = _run(tmp_path, issues, [
        _answer("against", "against:1", "A. Plausible (Recommended) | Alt one.", "B. Handles it | Alt one.", note="p.2"),
        _answer("against", "against:2", "A. Plausible (Recommended) | Alt two.", "C. Not plausible here | Alt two."),
        _answer("against", "against:3", "A. Plausible (Recommended) | Alt three.", "C. Not plausible here | Alt three.")])
    rows = {o["item"]: o for o in eval_override.override_rate(run)["overrides"]}
    assert (rows["against:1"]["pack"], rows["against:1"]["adjudication"]) == ("survey", "paper")
    assert (rows["against:2"]["pack"], rows["against:2"]["adjudication"]) == ("archival", "external")
    assert (rows["against:3"]["pack"], rows["against:3"]["adjudication"]) == ("unknown", "unknown")


def test_the_stage_4_block_format_pack_line_reaches_the_override_table(tmp_path):
    """A majors_draft.md block written to the stage text's own template carries its Pack line into
    eval_pool.majors_draft and the override attribution."""
    from plumb import eval_pool
    text = (ROOT / "skills/review/stages/stage-4-diagnose.md").read_text(encoding="utf-8")
    template = text.split("Write each issue as:", 1)[1].split("```", 2)[1]
    block = "\n".join(line[3:] for line in template.strip("\n").splitlines())
    block = (block.replace("<n>", "1").replace("<One sentence naming the problem.>", "One.")
             .replace("<label>", "Weakens a claim").replace("<paper | external | judgment>", "external")
             .replace("<pack name | core>", "survey"))
    run = _run(tmp_path, [], [_answer("majors", "majors:1", "A. Keep (Recommended) | One.", "C. Addressed | One.")],
               files={"stage-4/majors_draft.md": "# Majors\n\n" + block + "\n"})
    draft = eval_pool.majors_draft(run / ".workspace")
    assert draft["majors:1"]["pack"] == "survey" and draft["majors:1"]["adjudication"] == "external"
    r = eval_override.override_rate(run)
    assert r["overrides"][0]["pack"] == "survey" and r["overrides"][0]["adjudication"] == "external"


def test_a_citation_answer_at_the_majors_stop_has_its_own_kind():
    """Fake answers: a B or C at the Stage 6 citation check-in is neither a demotion nor a drop."""
    rec = "A. Keep going, and list it as not verified (Recommended) | Fake entry."
    for chosen in ("B. It is a false flag: count it as checked | Fake entry.", "C. Stop the review | Fake entry."):
        assert eval_override.kind_of(_answer("majors", "majors:citation:2", rec, chosen)) == "citation"
    assert eval_override.kind_of(_answer("majors", "majors:1", "A. Keep (Recommended)", "B. Minor")) == "demotion"
