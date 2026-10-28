"""eval/report.py: the planted-error table by depth over fixture and run pairs, and the
reliability step through eval/compare_runs.py."""
from __future__ import annotations
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "eval" / "report.py"


def _load():
    spec = importlib.util.spec_from_file_location("eval_report", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def report():
    return _load()


def _issue(id_, check, severity="Weakens a claim"):
    return {"id": id_, "kind": "major", "title": f"Issue {id_}", "severity": severity, "adjudication": "paper",
            "summary": "x", "excerpt": "", "ms_page": None, "checkin": f"majors:{id_}", "sources": [], "check": check}


def _run(tmp_path, name, depth, issues):
    ws = tmp_path / name / "plumb_output" / "2026-10-05" / ".workspace"
    ws.mkdir(parents=True)
    (ws / "run.json").write_text(json.dumps({"depth": depth, "packs": ["fake"]}), encoding="utf-8")
    if issues is not None:
        (ws / "stage-5").mkdir()
        (ws / "stage-5" / "issues.json").write_text(json.dumps(issues), encoding="utf-8")
    return ws.parent


def _fixture(tmp_path, name, must_catch, must_not_flag=()):
    pack = tmp_path / "packs" / "fake"
    fx = pack / "fixtures" / name
    fx.mkdir(parents=True, exist_ok=True)
    (pack / "checklists").mkdir(exist_ok=True)
    (pack / "checklists" / "fake.yaml").write_text("[]", encoding="utf-8")
    key = {"status": "planted", "module": "did", "paper": "planted.pdf",
           "must_catch": [{"check": c, "page": 1, "locator": "l", "note": "n", "severity": s} for c, s in must_catch],
           "must_not_flag": [{"check": c, "page": 2, "locator": "l", "note": "n"} for c in must_not_flag], "also_fair": []}
    (fx / "expected.yaml").write_text(yaml.safe_dump(key), encoding="utf-8")
    return fx


@pytest.fixture
def pairs(tmp_path):
    fx1 = _fixture(tmp_path, "f-1", [("DD1", "Undermines the main claim"), ("DD3", "Weakens a claim")], ["DD6"])
    fx2 = _fixture(tmp_path, "f-2", [("E2", "Minor")])
    deep = _run(tmp_path, "deep", "deep", [_issue("1", "DD1"), _issue("2", "DD6")])
    std = _run(tmp_path, "std", "standard", [_issue("1", "E2")])
    quick = _run(tmp_path, "quick", "quick", None)
    return [(fx1, deep), (fx2, std), (fx1, quick)]


def test_depth_table_sums_each_part_by_depth(report, pairs):
    cards = report.score_pairs(pairs)
    table = report.by_depth(cards)
    assert table["deep"] == {"runs": 1, "must_catch": {"expected": 2, "caught": 1}, "must_not_flag": {"expected": 1, "flagged": 1},
                             "also_fair": {"expected": 0, "caught": 0},
                             "by_severity": {"Undermines the main claim": {"expected": 1, "caught": 1},
                                             "Weakens a claim": {"expected": 1, "caught": 0}, "Minor": {"expected": 0, "caught": 0}}}
    assert table["standard"]["must_catch"] == {"expected": 1, "caught": 1}
    assert table["quick"]["must_catch"] == {"expected": 2, "caught": 0} and table["quick"]["must_not_flag"]["flagged"] == 0


def test_markdown_lists_each_run_then_the_depth_table(report, pairs):
    cards = report.score_pairs(pairs)
    text = report.markdown(cards, report.by_depth(cards))
    assert "| f-1 | fake | deep | 1 of 2 | 1 of 1 | 0 of 0 |" in text
    assert "| deep | 1 | 1 of 2 (50%) | 1 of 1 (100%) |" in text
    assert "| quick | 1 | 0 of 2 (0%) | 0 of 1 (0%) |" in text
    assert chr(0x2014) not in text


def test_main_takes_pairs_and_a_manifest_and_writes_json(report, pairs, tmp_path, capsys):
    manifest = tmp_path / "pairs.txt"
    manifest.write_text("".join(f"{fx}={run}\n" for fx, run in pairs[1:]) + "\n# a comment\n", encoding="utf-8")
    out = tmp_path / "report.json"
    code = report.main([f"{pairs[0][0]}={pairs[0][1]}", "--manifest", str(manifest), "--json", str(out)])
    assert code == 0
    data = json.loads(out.read_text())
    assert len(data["runs"]) == 3 and set(data["by_depth"]) == {"deep", "standard", "quick"}
    printed = capsys.readouterr().out
    assert "| deep | 1 |" in printed and "compare_runs" in printed


def test_a_bad_pair_is_a_clear_error(report, pairs, capsys):
    assert report.main([f"{pairs[0][0]}"]) == 2
    assert "fixture=run" in capsys.readouterr().err
    assert report.main([f"{pairs[0][0]}={pairs[0][0] / 'nope'}"]) == 2
    assert "run folder" in capsys.readouterr().err


def _auto_runs(tmp_path):
    """Two Auto runs of one PDF, sharing issue 1 by check id, as compare_runs matches them."""
    runs = []
    for name in ("run-a", "run-b"):
        ws = tmp_path / "autos" / name / "plumb_output" / "2026-10-05" / ".workspace"
        (ws / "stage-5").mkdir(parents=True)
        (ws / "run.json").write_text(json.dumps({"depth": "standard", "packs": ["fake"],
                                                 "pdf_path": str(tmp_path / "paper.pdf")}), encoding="utf-8")
        (ws / "stage-5" / "issues.json").write_text(json.dumps([_issue("1", "DD1")]), encoding="utf-8")
        runs.append(ws.parent)
    return runs


def test_compare_runs_is_run_over_the_auto_runs_and_its_card_printed(report, pairs, tmp_path, capsys):
    a, b = _auto_runs(tmp_path)
    assert report.main([f"{pairs[0][0]}={pairs[0][1]}", "--runs", str(a), str(b)]) == 0
    out = capsys.readouterr().out
    assert "reliability" in out and "Jaccard" in out and "compare_runs.py exited 0" in out


def test_hand_matches_are_passed_through_to_compare_runs(report, pairs, tmp_path, capsys):
    a, b = _auto_runs(tmp_path)
    hand = tmp_path / "hand.json"
    hand.write_text(json.dumps([[{"run": str(a), "id": "1"}, {"run": str(b), "id": "1"}]]), encoding="utf-8")
    assert report.main([f"{pairs[0][0]}={pairs[0][1]}", "--runs", str(a), str(b), "--hand-matches", str(hand)]) == 0
    out = capsys.readouterr().out
    assert "hand" in out and "compare_runs.py exited 0" in out
    missing = tmp_path / "nope.json"
    assert report.main([f"{pairs[0][0]}={pairs[0][1]}", "--runs", str(a), str(b), "--hand-matches", str(missing)]) == 0
    assert "compare_runs.py exited 2" in capsys.readouterr().out


def test_without_runs_the_reliability_step_says_so(report, pairs, capsys):
    assert report.main([f"{pairs[0][0]}={pairs[0][1]}"]) == 0
    assert "--runs" in capsys.readouterr().out


def test_script_runs_as_a_subprocess(pairs):
    proc = subprocess.run([sys.executable, str(SCRIPT), f"{pairs[0][0]}={pairs[0][1]}"], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert "| deep | 1 |" in proc.stdout
