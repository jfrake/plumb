"""plumb.eval_rate and eval/rate_analysis.py: the preregistered numbers from two filled rating
sheets and the sealed mapping. Every sheet and mapping here is a small fake written by the test."""
from __future__ import annotations
import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

from plumb import eval_rate

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "eval" / "rate_analysis.py"
U, W, M = "Undermines the main claim", "Weakens a claim", "Minor"


def _sheet(path, rows):
    """rows: [(claim_id, correct, reason, importance, recognized)]."""
    with Path(path).open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(eval_rate.SHEET_COLUMNS)
        for cid, correct, reason, importance, recognized in rows:
            w.writerow([cid, f"Claim {cid} (p. 1).", "1", correct, reason, importance, recognized])
    return Path(path)


def _mapping(path, claims, missing=(), paper="p", raters=("r1", "r2"), author=None, nonauthor=None, joint=None,
             adjudication=None):
    """claims: {id: (sources, overruled rows)}. adjudication maps id to type; untyped otherwise."""
    adjudication = adjudication or {}
    data = {"paper": paper, "missing": list(missing), "raters": list(raters), "author": author, "nonauthor": nonauthor,
            "joint": joint,
            "claims": {cid: {"sources": list(srcs), "source_severities": {s: W for s in srcs}, "pages": ["1"],
                             "adjudication": adjudication.get(cid, "untyped"), "overruled": list(over)}
                       for cid, (srcs, over) in claims.items()}}
    Path(path).write_text(json.dumps(data), encoding="utf-8")
    return Path(path)


OVER = {"item": "majors:2", "stop": "majors", "pack": "archival", "adjudication": "judgment", "issue_id": "2", "answer": "C."}

# Six claims: c01 only Plumb Auto, c02 only gpt, c03 shared by three, c04 only claude, c05 raised by
# Auto and dropped by the Standard reviewer (so Auto alone gets credit), c06 only Plumb Standard.
CLAIMS = {"c01": (["plumb-auto"], []), "c02": (["gpt-6-astra"], []),
          "c03": (["plumb-auto", "plumb-standard", "gpt-6-astra"], []), "c04": (["claude-fable-5-1"], []),
          "c05": (["plumb-auto"], [OVER]), "c06": (["plumb-standard"], [])}
# r2 is the author (validity), r1 the non-author (importance).
R2 = [("c01", "yes", "", U, "no"), ("c02", "no", "Table 2 says otherwise", W, "no"), ("c03", "yes", "", W, "yes"),
      ("c04", "yes", "", M, "no"), ("c05", "yes", "", U, "yes"), ("c06", "yes", "", M, "no")]
R1 = [("c01", "yes", "", W, "no"), ("c02", "yes", "", U, "no"), ("c03", "yes", "", U, "no"),
      ("c04", "yes", "", W, "no"), ("c05", "yes", "", W, "no"), ("c06", "no", "Not what the paper says", M, "yes")]


ADJ = {"c01": "paper", "c03": "judgment", "c05": "external", "c06": "judgment"}


@pytest.fixture
def filled(tmp_path):
    return {"r2": _sheet(tmp_path / "sheet-r2.csv", R2), "r1": _sheet(tmp_path / "sheet-r1.csv", R1),
            "mapping": _mapping(tmp_path / "mapping.sealed.json", CLAIMS, adjudication=ADJ)}


# --- reading a sheet ---

def test_read_sheet_returns_one_record_per_claim(tmp_path):
    ratings = eval_rate.read_sheet(_sheet(tmp_path / "s.csv", R2))
    assert ratings["c02"] == {"correct": False, "reason": "Table 2 says otherwise", "importance": W, "recognized": False}
    assert ratings["c01"]["correct"] is True and ratings["c01"]["importance"] == U


@pytest.mark.parametrize("row, message", [
    (("c01", "", "", U, "no"), "correct"),
    (("c01", "yes", "", "", "no"), "importance"),
    (("c01", "yes", "", U, ""), "recognized"),
    (("c01", "no", "", U, "no"), "reason"),
    (("c01", "maybe", "", U, "no"), "yes or no"),
    (("c01", "yes", "", "Serious", "no"), "importance"),
])
def test_a_blank_or_bad_cell_is_an_error_naming_the_claim(tmp_path, row, message):
    with pytest.raises(eval_rate.RateError, match=message) as exc:
        eval_rate.read_sheet(_sheet(tmp_path / "s.csv", [row]))
    assert "c01" in str(exc.value)


def test_a_sheet_with_the_wrong_columns_or_a_repeated_claim_is_an_error(tmp_path):
    p = tmp_path / "s.csv"
    p.write_text("id,claim\nc01,x\n", encoding="utf-8")
    with pytest.raises(eval_rate.RateError, match="columns"):
        eval_rate.read_sheet(p)
    with pytest.raises(eval_rate.RateError, match="twice"):
        eval_rate.read_sheet(_sheet(p, [("c01", "yes", "", U, "no"), ("c01", "yes", "", U, "no")]))


def test_the_two_sheets_and_the_mapping_must_name_the_same_claims(tmp_path):
    a = eval_rate.read_sheet(_sheet(tmp_path / "a.csv", R2))
    b = eval_rate.read_sheet(_sheet(tmp_path / "b.csv", R1[:5]))
    mapping = json.loads(_mapping(tmp_path / "m.json", CLAIMS).read_text())
    with pytest.raises(eval_rate.RateError, match="c06"):
        eval_rate.analyse({"r2": a, "r1": b}, mapping, author="r2", nonauthor="r1")


# --- the headline rules ---

def _result(filled, **kw):
    sheets = {r: eval_rate.read_sheet(filled[r]) for r in ("r2", "r1")}
    return eval_rate.analyse(sheets, json.loads(filled["mapping"].read_text()), **dict({"author": "r2", "nonauthor": "r1"}, **kw))


def test_primary_rule_author_validity_and_nonauthor_importance(filled):
    r = _result(filled)
    # r2 says correct: c01, c03, c04, c05, c06; r1 top-two: c01, c02, c03, c04, c05 -> valid+important: c01, c03, c04, c05
    primary = r["rules"]["primary"]
    assert primary["valid_important"] == ["c01", "c03", "c04", "c05"]
    assert primary["only_source"] == {"plumb-auto": ["c01", "c05"], "claude-fable-5-1": ["c04"]}
    assert primary["by_source"]["plumb-auto"]["any"] == 3 and primary["by_source"]["plumb-auto"]["only"] == 2
    assert primary["by_source"]["gpt-6-astra"]["any"] == 1 and primary["by_source"]["gpt-6-astra"]["only"] == 0
    assert primary["by_source"]["plumb-standard"]["any"] == 1 and primary["by_source"]["plumb-standard"]["only"] == 0
    assert list(primary["by_source"]) == ["plumb-auto", "plumb-standard", "gpt-6-astra", "claude-fable-5-1"]


def test_an_auto_issue_dropped_at_standard_is_found_by_only_auto_and_still_in_the_override_table(filled):
    r = _result(filled)
    assert "c05" in r["rules"]["primary"]["only_source"]["plumb-auto"]
    assert [o["id"] for o in r["overrides"]["claims"]] == ["c05"]


def test_a_claim_with_no_source_counts_for_nobody_but_is_still_rated(tmp_path):
    claims = {"c01": ([], [OVER])}
    m = json.loads(_mapping(tmp_path / "m.json", claims).read_text())
    r2 = eval_rate.read_sheet(_sheet(tmp_path / "r2.csv", [("c01", "yes", "", W, "no")]))
    r1 = eval_rate.read_sheet(_sheet(tmp_path / "r1.csv", [("c01", "yes", "", W, "no")]))
    r = eval_rate.analyse({"r2": r2, "r1": r1}, m, author="r2", nonauthor="r1")
    assert r["rules"]["primary"]["valid_important"] == ["c01"] and r["rules"]["primary"]["only_source"] == {}
    assert r["rules"]["primary"]["no_source"] == ["c01"]
    assert r["overrides"]["claims"][0]["sided_with"] == "tool"


def test_both_agree_rule_needs_both_correct_and_both_important(filled):
    r = _result(filled)
    # both correct: c01, c03, c04, c05; both top-two: c01, c03, c05 -> c01, c03, c05
    both = r["rules"]["both_agree"]
    assert both["valid_important"] == ["c01", "c03", "c05"]
    assert both["only_source"] == {"plumb-auto": ["c01", "c05"]}


def test_joint_makes_the_primary_rule_the_both_agree_rule(filled):
    r = _result(filled, joint=True)
    assert r["rules"]["primary"] == r["rules"]["both_agree"]
    assert r["joint"] is True


def test_validity_is_reported_for_both_raters_to_size_self_defense(filled):
    r = _result(filled)
    assert r["validity_by_rater"] == {"r2": {"correct": 5, "of": 6}, "r1": {"correct": 5, "of": 6}}


# --- agreement ---

def test_kappa_on_a_known_two_by_two_table():
    # 20 yes/yes, 5 yes/no, 10 no/yes, 15 no/no: po 0.70, pe 0.50, kappa 0.40.
    a = ["yes"] * 25 + ["no"] * 25
    b = ["yes"] * 20 + ["no"] * 5 + ["yes"] * 10 + ["no"] * 15
    assert eval_rate.agreement(a, b) == {"percent": 70.0, "kappa": 0.4, "n": 50}


def test_kappa_with_no_chance_disagreement_is_one_when_they_agree_and_zero_otherwise():
    assert eval_rate.agreement(["a", "a"], ["a", "a"]) == {"percent": 100.0, "kappa": 1.0, "n": 2}
    assert eval_rate.agreement(["a", "a"], ["b", "b"]) == {"percent": 0.0, "kappa": 0.0, "n": 2}


def test_agreement_is_reported_for_correctness_and_importance(filled):
    r = _result(filled)
    # correctness: agree on c01, c03, c04, c05 (4 of 6).
    assert r["agreement"]["correctness"]["percent"] == pytest.approx(66.67, abs=0.01)
    assert r["agreement"]["correctness"]["n"] == 6
    # three-level importance: agree on c06 only (1 of 6); binarized top-two: all but c04 (5 of 6).
    assert r["agreement"]["importance"]["percent"] == pytest.approx(16.67, abs=0.01)
    assert set(r["agreement"]) == {"correctness", "importance"}


# --- recognition ---

def test_recognition_share_per_rater_and_the_headline_on_unrecognized_claims(filled):
    r = _result(filled)
    assert r["recognized"] == {"r2": {"count": 2, "of": 6}, "r1": {"count": 1, "of": 6}}
    assert r["unrecognized"]["claims"] == ["c01", "c02", "c04"]
    assert r["unrecognized"]["primary"]["valid_important"] == ["c01", "c04"]
    assert r["unrecognized"]["primary"]["only_source"] == {"plumb-auto": ["c01"], "claude-fable-5-1": ["c04"]}
    assert r["unrecognized"]["both_agree"]["valid_important"] == ["c01"]


# --- the headline by adjudication type, shares, and missing sources ---

def test_headline_is_split_by_adjudication_type_with_external_apart(filled):
    r = _result(filled)
    by = r["rules"]["primary"]["by_adjudication"]
    # valid+important: c01 paper, c03 judgment, c04 untyped, c05 external.
    assert by["paper"]["valid_important"] == ["c01"] and by["paper"]["only_source"] == {"plumb-auto": ["c01"]}
    assert by["judgment"]["valid_important"] == ["c03"] and by["judgment"]["only_source"] == {}
    assert by["untyped"]["valid_important"] == ["c04"] and by["untyped"]["only_source"] == {"claude-fable-5-1": ["c04"]}
    assert by["external"]["valid_important"] == ["c05"] and by["external"]["only_source"] == {"plumb-auto": ["c05"]}
    assert r["rules"]["primary"]["external_apart"]["valid_important"] == ["c01", "c03", "c04"]
    assert r["rules"]["primary"]["external_apart"]["by_source"]["plumb-auto"]["only"] == 1
    assert list(by) == ["paper", "external", "judgment", "unknown", "untyped"]


def test_the_share_found_by_only_one_source_sits_next_to_the_count(filled):
    r = _result(filled)
    primary = r["rules"]["primary"]
    # 4 valid and important; only-source: plumb-auto 2, claude 1 -> 50% and 25%.
    assert primary["by_source"]["plumb-auto"]["only_share"] == 50.0
    assert primary["by_source"]["claude-fable-5-1"]["only_share"] == 25.0
    assert primary["by_source"]["gpt-6-astra"]["only_share"] == 0.0
    assert primary["only_any_source"] == {"count": 3, "share": 75.0}
    text = eval_rate.markdown(r)
    assert "| plumb-auto | 3 | 2 (50%) |" in text


def test_a_missing_source_is_told_apart_from_one_with_no_valid_claim(tmp_path):
    claims = {"c01": (["plumb-auto"], []), "c02": (["gpt-6-astra"], [])}
    m = json.loads(_mapping(tmp_path / "m.json", claims, missing=["claude-fable-5-1"]).read_text())
    r2 = eval_rate.read_sheet(_sheet(tmp_path / "r2.csv", [("c01", "yes", "", U, "no"), ("c02", "no", "wrong", U, "no")]))
    r1 = eval_rate.read_sheet(_sheet(tmp_path / "r1.csv", [("c01", "yes", "", U, "no"), ("c02", "yes", "", U, "no")]))
    r = eval_rate.analyse({"r2": r2, "r1": r1}, m, author="r2", nonauthor="r1")
    by = r["rules"]["primary"]["by_source"]
    assert by["claude-fable-5-1"]["status"] == "missing" and by["gpt-6-astra"]["status"] == "present"
    assert by["plumb-standard"]["status"] == "present" and by["plumb-standard"]["any"] == 0
    assert r["missing"] == ["claude-fable-5-1"]
    text = eval_rate.markdown(r)
    assert "missing for this paper" in text and "| claude-fable-5-1 | missing for this paper |" in text


# --- the override analysis ---

def test_each_overruled_claim_is_sided_with_the_tool_or_the_reviewer(filled):
    r = _result(filled)
    assert r["overrides"]["claims"] == [{"id": "c05", "paper": "p", "item": "majors:2", "stop": "majors", "pack": "archival",
                                         "adjudication": "judgment", "valid": True, "important": True, "sided_with": "tool"}]
    assert r["overrides"]["by_stop"] == {"majors": {"tool": 1, "reviewer": 0, "partial": 0}}
    assert r["overrides"]["by_pack"] == {"archival": {"tool": 1, "reviewer": 0, "partial": 0}}
    assert r["overrides"]["by_adjudication"] == {"judgment": {"tool": 1, "reviewer": 0, "partial": 0}}


def test_an_overruled_claim_rated_incorrect_sides_with_the_reviewer_and_unimportant_is_partial(tmp_path):
    claims = {"c01": (["plumb-standard-overruled"], [dict(OVER, item="minors:1", stop="minors", adjudication="paper")]),
              "c02": (["plumb-standard-overruled"], [dict(OVER, item="against:1", stop="against", pack="core")])}
    m = json.loads(_mapping(tmp_path / "m.json", claims).read_text())
    r2 = eval_rate.read_sheet(_sheet(tmp_path / "r2.csv", [("c01", "no", "wrong", W, "no"), ("c02", "yes", "", W, "no")]))
    r1 = eval_rate.read_sheet(_sheet(tmp_path / "r1.csv", [("c01", "yes", "", W, "no"), ("c02", "yes", "", M, "no")]))
    r = eval_rate.analyse({"r2": r2, "r1": r1}, m, author="r2", nonauthor="r1")
    assert [c["sided_with"] for c in r["overrides"]["claims"]] == ["reviewer", "partial"]
    assert r["overrides"]["by_stop"] == {"minors": {"tool": 0, "reviewer": 1, "partial": 0},
                                         "against": {"tool": 0, "reviewer": 0, "partial": 1}}
    assert r["overrides"]["by_adjudication"]["paper"] == {"tool": 0, "reviewer": 1, "partial": 0}


# --- output ---

def test_markdown_lists_the_headline_agreement_recognition_and_overrides(filled):
    r = _result(filled)
    text = eval_rate.markdown(r)
    assert "| plumb-auto | 3 | 2 (50%) |" in text
    assert "kappa" in text and "recognized" in text and "majors" in text
    assert chr(0x2014) not in text


def test_markdown_defines_the_three_override_sides(filled):
    text = eval_rate.markdown(_result(filled))
    assert "reviewer: the claim was rated not valid" in text
    assert "tool: valid and rated Undermines the main claim or Weakens a claim" in text
    assert "partial: valid and rated Minor" in text


# --- the mapping's raters and roles must match the flags ---

def test_sheet_rater_names_must_match_the_pools_raters(tmp_path):
    claims = {"c01": (["plumb-auto"], [])}
    m = json.loads(_mapping(tmp_path / "m.json", claims, raters=("r1", "r2")).read_text())
    a = eval_rate.read_sheet(_sheet(tmp_path / "a.csv", [("c01", "yes", "", U, "no")]))
    b = eval_rate.read_sheet(_sheet(tmp_path / "b.csv", [("c01", "yes", "", U, "no")]))
    with pytest.raises(eval_rate.RateError, match="raters"):
        eval_rate.analyse({"r1": a, "xx": b}, m, author="r1", nonauthor="xx")


@pytest.mark.parametrize("recorded, flags, message", [
    ({"author": "r2", "nonauthor": "r1", "joint": False}, {"author": "r1", "nonauthor": "r2"}, "--author"),
    ({"author": "r2", "nonauthor": "r1", "joint": False}, {"author": "r2", "nonauthor": "r1", "joint": True}, "--joint"),
    ({"author": "r2", "nonauthor": "r1", "joint": True}, {"author": "r2", "nonauthor": "r1"}, "--joint"),
])
def test_roles_recorded_at_build_time_refuse_a_mismatch(tmp_path, recorded, flags, message):
    claims = {"c01": (["plumb-auto"], [])}
    m = json.loads(_mapping(tmp_path / "m.json", claims, **recorded).read_text())
    a = eval_rate.read_sheet(_sheet(tmp_path / "a.csv", [("c01", "yes", "", U, "no")]))
    b = eval_rate.read_sheet(_sheet(tmp_path / "b.csv", [("c01", "yes", "", U, "no")]))
    with pytest.raises(eval_rate.RateError, match=message):
        eval_rate.analyse({"r1": a, "r2": b}, m, **flags)


def test_roles_not_recorded_at_build_time_are_not_checked(tmp_path):
    claims = {"c01": (["plumb-auto"], [])}
    m = json.loads(_mapping(tmp_path / "m.json", claims).read_text())
    a = eval_rate.read_sheet(_sheet(tmp_path / "a.csv", [("c01", "yes", "", U, "no")]))
    b = eval_rate.read_sheet(_sheet(tmp_path / "b.csv", [("c01", "yes", "", U, "no")]))
    assert eval_rate.analyse({"r1": a, "r2": b}, m, author="r1", nonauthor="r2")["claims"] == 1


# --- pooled across papers ---

def _second_paper(tmp_path):
    claims = {"c01": (["plumb-auto"], []), "c02": (["gpt-6-astra"], [dict(OVER, item="minors:2", stop="minors")])}
    m = json.loads(_mapping(tmp_path / "m2.json", claims, paper="q", missing=["claude-fable-5-1"],
                            adjudication={"c01": "paper"}).read_text())
    r2 = eval_rate.read_sheet(_sheet(tmp_path / "dh2.csv", [("c01", "yes", "", U, "no"), ("c02", "no", "wrong", W, "yes")]))
    r1 = eval_rate.read_sheet(_sheet(tmp_path / "jf2.csv", [("c01", "yes", "", W, "no"), ("c02", "yes", "", W, "no")]))
    return eval_rate.analyse({"r2": r2, "r1": r1}, m, author="r2", nonauthor="r1")


def test_pooled_numbers_sum_counts_and_recompute_agreement_from_the_claim_ratings(filled, tmp_path):
    first = _result(filled)
    second = _second_paper(tmp_path)
    pooled = eval_rate.pooled([first, second])
    assert pooled["papers"] == ["p", "q"] and pooled["claims"] == 8
    primary = pooled["rules"]["primary"]
    assert len(primary["valid_important"]) == 5
    assert primary["by_source"]["plumb-auto"] == {"any": 4, "only": 3, "only_share": 60.0, "papers_missing": []}
    assert primary["by_source"]["claude-fable-5-1"]["papers_missing"] == ["q"]
    assert pooled["agreement"]["correctness"]["n"] == 8
    assert pooled["recognized"] == {"author": {"count": 3, "of": 8}, "nonauthor": {"count": 1, "of": 8}}
    assert pooled["overrides"]["by_stop"] == {"majors": {"tool": 1, "reviewer": 0, "partial": 0},
                                              "minors": {"tool": 0, "reviewer": 1, "partial": 0}}
    text = eval_rate.pooled_markdown(pooled)
    assert "| p |" in text and "| q |" in text and "pooled" in text


def test_script_pools_several_result_files(filled, tmp_path):
    first = tmp_path / "r1.json"
    proc = subprocess.run([sys.executable, str(SCRIPT), "--sheet", f"r2={filled['r2']}", "--sheet", f"r1={filled['r1']}",
                           "--mapping", str(filled["mapping"]), "--author", "r2", "--nonauthor", "r1", "--json", str(first)],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    second = tmp_path / "r2.json"
    second.write_text(json.dumps(_second_paper(tmp_path)), encoding="utf-8")
    proc = subprocess.run([sys.executable, str(SCRIPT), "--pool", str(first), str(second)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    head, sep, tail = proc.stdout.partition("\n## ")
    assert json.loads(head)["papers"] == ["p", "q"] and "pooled" in tail


def test_script_prints_json_then_markdown_and_writes_the_json(filled, tmp_path):
    out = tmp_path / "result.json"
    proc = subprocess.run([sys.executable, str(SCRIPT), "--sheet", f"r2={filled['r2']}", "--sheet", f"r1={filled['r1']}",
                           "--mapping", str(filled["mapping"]), "--author", "r2", "--nonauthor", "r1", "--json", str(out)],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    head, sep, tail = proc.stdout.partition("\n## ")
    assert json.loads(head)["rules"]["primary"]["valid_important"] == ["c01", "c03", "c04", "c05"]
    assert sep and "plumb-auto" in tail
    assert json.loads(out.read_text())["paper"] == "p"


def test_script_never_finds_the_mapping_on_its_own(filled):
    """The sheets sit next to mapping.sealed.json; without --mapping the script stops."""
    proc = subprocess.run([sys.executable, str(SCRIPT), "--sheet", f"r2={filled['r2']}", "--sheet", f"r1={filled['r1']}",
                           "--author", "r2", "--nonauthor", "r1"], capture_output=True, text=True)
    assert proc.returncode == 2 and "--mapping" in proc.stderr
    source = (ROOT / "plumb" / "eval_rate.py").read_text(encoding="utf-8")
    assert "mapping.sealed" not in source and "glob" not in source


def test_script_rejects_an_author_who_has_no_sheet(filled):
    proc = subprocess.run([sys.executable, str(SCRIPT), "--sheet", f"r2={filled['r2']}", "--sheet", f"r1={filled['r1']}",
                           "--mapping", str(filled["mapping"]), "--author", "xx", "--nonauthor", "r1"],
                          capture_output=True, text=True)
    assert proc.returncode == 2 and "xx" in proc.stderr


# --- second review: no-source claims out of the only-share denominator; pooled rows full width ---

def test_no_source_claims_are_out_of_the_only_share_denominator_and_counted_apart(tmp_path):
    claims = {"c01": (["plumb-auto"], []), "c02": ([], [OVER]), "c03": (["plumb-auto", "gpt-6-astra"], [])}
    m = json.loads(_mapping(tmp_path / "m.json", claims).read_text())
    rows = [("c01", "yes", "", U, "no"), ("c02", "yes", "", U, "no"), ("c03", "yes", "", U, "no")]
    r2 = eval_rate.read_sheet(_sheet(tmp_path / "r2.csv", rows))
    r1 = eval_rate.read_sheet(_sheet(tmp_path / "r1.csv", rows))
    r = eval_rate.analyse({"r2": r2, "r1": r1}, m, author="r2", nonauthor="r1")
    primary = r["rules"]["primary"]
    # Three valid and important; one credited to no source leaves a denominator of two.
    assert primary["valid_important"] == ["c01", "c02", "c03"] and primary["no_source"] == ["c02"]
    assert primary["sourced"] == 2
    assert primary["by_source"]["plumb-auto"]["only_share"] == 50.0
    assert primary["only_any_source"] == {"count": 1, "share": 50.0}
    text = eval_rate.markdown(r)
    assert "1 held only by a point the Standard reviewer dropped" in text
    assert "shares are over the 2 claims credited to a source" in text


def test_pooled_source_rows_have_the_full_column_count(filled, tmp_path):
    pooled = eval_rate.pooled([_result(filled), _second_paper(tmp_path)])
    text = eval_rate.pooled_markdown(pooled)
    block = text.split("### pooled headline, primary rule", 1)[1].split("By adjudication type", 1)[0]
    rows = [line for line in block.splitlines() if line.startswith("| ")]
    widths = {line.count(" | ") + 1 for line in rows}
    assert widths == {4}, rows
    assert any(line.startswith("| claude-fable-5-1 |") and line.rstrip().endswith("| q |") for line in rows)
    assert any(line.startswith("| plumb-auto |") and line.rstrip().endswith("|  |") for line in rows)
