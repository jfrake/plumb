"""eval/cocitation_eval.py: recall of referee-named works in the citation gap lists. Every case,
list, and name here is fake."""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("cocitation_eval", ROOT / "eval" / "cocitation_eval.py")
ev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ev)


@pytest.mark.parametrize("text,want", [
    ("Fakeman, P. E.", "fakeman"), ("Paul E. Fakeman, Robyn M. Fakely", "fakeman"),
    ("Fakevorst, Simmonsfake, & Masseyfake", "fakevorst"), ("van Fakenberg, D.", "fakenberg"),
    ("Daan van Fakenberg", "fakenberg"), ("Ştefan Fakeü", "fakeu"), ("", ""),
    ("Fakeman et al.", "fakeman"), ("Fakeman, P. E., et al.", "fakeman"), ("Fakeman et al", "fakeman"),
    ("Fakeman, P. E., ET AL.", "fakeman"),
    ("Robert E. Lucas Jr.", "lucas"), ("Lucas, R. E., Jr.", "lucas"), ("Pat Fakeman III", "fakeman"),
    ("Fakesen Sørensen", "sorensen"), ("Łukasz Fakeski", "fakeski"), ("Fakeß", "fakess")])
def test_first_surname(text, want):
    assert ev.first_surname(text) == want


def test_matches_on_surname_and_close_year_or_on_title():
    m = {"authors": "Fakeman, A.", "year": 1979, "title": "A fake classic of judgment"}
    assert ev.matches(m, {"authors": "Alan Fakeman", "year": 1980, "title": "Fake judgment studies"})
    assert not ev.matches(m, {"authors": "Alan Fakeman", "year": 1985, "title": "Fake judgment studies"})
    assert ev.matches(m, {"authors": "Wrong Person", "year": 2001, "title": "A fake classic of judgment"})
    assert not ev.matches(m, {"authors": "Wrong Person", "year": 1979, "title": "Nothing alike here"})


def test_a_surname_and_year_match_needs_a_shared_content_word():
    m = {"authors": "Wang, L.", "year": 2015, "title": "Status and careers"}
    assert not ev.matches(m, {"authors": "Li Wang", "year": 2016, "title": "Deep learning for images"})
    assert ev.matches(m, {"authors": "Li Wang", "year": 2016, "title": "Careers in fake firms"})
    # No title on one side: the surname and year decide.
    assert ev.matches({"authors": "Wang, L.", "year": 2015}, {"authors": "Li Wang", "year": 2016, "title": "Deep"})


def test_matches_with_year_suffixes_and_foreign_letters():
    assert ev.matches({"authors": "Sørensen, A.", "year": "1954a", "title": "Fake mobility"},
                      {"authors": "Aage Sorensen", "year": 1955, "title": "Fake mobility"})
    assert ev.matches({"authors": "Fakeman, A.", "year": "1979b"},
                      {"authors": "Alan Fakeman", "year": "1979", "title": "Anything"})


def test_match_row_names_the_listed_work():
    data = {"classics": [{"authors": "Alan Fakeman", "year": 1979, "title": "Fake judgment", "id": "W1"}],
            "recent": []}
    row = ev.match_row({"authors": "Fakeman et al.", "year": 1979, "title": "Fake judgment"}, data)
    assert row["id"] == "W1"
    assert ev.match_row({"authors": "Nobody, C.", "year": 1999}, data) is None


def test_found_checks_both_lists():
    data = {"classics": [{"authors": "Alan Fakeman", "year": 1979, "title": "x"}],
            "recent": [{"authors": "Bea Fakerson", "year": 2015, "title": "y"}]}
    missing = [{"authors": "Fakeman, A.", "year": 1979}, {"authors": "Fakerson, B.", "year": 2015},
               {"authors": "Nobody, C.", "year": 2000}]
    assert ev.found(missing, data) == [True, True, False]


def _cases(tmp_path):
    d = tmp_path / "cases"
    for f in ("c1", "c2"):
        (d / f).mkdir(parents=True)
        (d / f / "reference_list_input.txt").write_text("REFERENCES\n\nFake, A. (2001). Fake. J, 1, 1.\n")
    cases = [{"folder": "c1", "search_before": "2015-01-01",
              "missing_specific": [{"authors": "Fakeman, A.", "year": 1979, "title": "A fake classic"}]},
             {"folder": "c2", "search_before": "2016-01-01",
              "missing_specific": [{"authors": "Nobody, C.", "year": 1990, "title": "Absent"}]}]
    (d / "cases.json").write_text(json.dumps(cases))
    (d / "split.json").write_text(json.dumps({"dev": ["c1"], "test": ["c2"]}))
    return d


def _fake_main(monkeypatch, seen):
    """A fake cocitation.main that records what it was given and writes fake lists."""
    def main(argv):
        ws = Path(argv[0])
        seen.append({"argv": argv, "run": json.loads((ws / "run.json").read_text()),
                     "TOP": ev.cc.TOP, "cache": os.environ.get("PLUMB_COCITATION_CACHE")})
        (ws / "stage-2").mkdir()
        (ws / "stage-2" / "cocitation.json").write_text(json.dumps({
            "seeds": 5, "openalex_cost_usd": 0.001, "recent": [],
            "classics": [{"authors": "Alan Fakeman", "year": 1979, "title": "A fake classic"}]}))
        return 0
    monkeypatch.setattr(ev.cc, "main", main)


def test_macro_recall_weights_cases_equally_and_splits_by_kind():
    """Fake per-case results: one heavy case and one light case."""
    per_case = [
        {"folder": "fake-a", "student": False, "unaided": True,
         "by_kind": {"substantive": {"missing": 10, "found": 1}, "methods": {"missing": 2, "found": 2}}},
        {"folder": "Fake Dissertation", "student": True, "unaided": False,
         "by_kind": {"substantive": {"missing": 2, "found": 2}}},
    ]
    assert ev._macro(per_case, "substantive") == round((0.1 + 1.0) / 2, 4)
    assert ev._macro(per_case, "substantive", lambda c: not c["student"]) == 0.1
    assert ev._macro(per_case, "substantive", lambda c: c["unaided"]) == 0.1
    assert ev._macro(per_case, "methods") == 1.0
    assert ev._macro(per_case, "data") is None
    assert ev._student({"folder": "Kyle Dissertation"}) and not ev._student({"folder": "OS-MS-1"})
    assert ev._student({"folder": "kyle dissertation"}) and ev._student({"folder": "fake PROPOSAL"})


def test_evaluate_runs_each_case_in_scratch_and_counts_recall(tmp_path, monkeypatch):
    d, seen, before = _cases(tmp_path), [], ev.cc.TOP
    _fake_main(monkeypatch, seen)
    out = tmp_path / "res.json"
    assert ev.main([str(d), "--split", "all", "--set", "TOP=25", "--out", str(out)]) == 0
    res = json.loads(out.read_text())
    assert res["found"] == 1 and res["missing"] == 2 and res["recall"] == 0.5
    assert [s["run"]["search_before"] for s in seen] == ["2015-01-01", "2016-01-01"]
    assert not any(a.startswith("--ranking") for s in seen for a in s["argv"]) and all(s["TOP"] == 25 for s in seen)
    assert "ranking" not in res
    assert all(s["cache"] == str(d / "_cache") for s in seen)
    assert ev.cc.TOP == before and "PLUMB_COCITATION_CACHE" not in os.environ
    assert sorted(p.name for p in d.iterdir()) == ["c1", "c2", "cases.json", "split.json"]


def test_split_selects_dev_only(tmp_path, monkeypatch):
    d, seen = _cases(tmp_path), []
    _fake_main(monkeypatch, seen)
    ev.main([str(d), "--split", "dev", "--out", str(tmp_path / "r.json")])
    assert [s["run"]["search_before"] for s in seen] == ["2015-01-01"]


def test_unknown_setting_and_output_inside_the_repository_are_refused(tmp_path, monkeypatch):
    d = _cases(tmp_path)
    _fake_main(monkeypatch, [])
    with pytest.raises(SystemExit):
        ev.main([str(d), "--split", "all", "--set", "API_KEY=x",
                 "--out", str(tmp_path / "r.json")])
    with pytest.raises(SystemExit):
        ev.main([str(d), "--split", "all", "--out", str(ROOT / "eval" / "r.json")])


def test_a_case_without_a_search_cap_is_reported_not_run(tmp_path, monkeypatch):
    d, seen = _cases(tmp_path), []
    cases = json.loads((d / "cases.json").read_text())
    cases[0]["search_before"] = ""
    (d / "cases.json").write_text(json.dumps(cases))
    _fake_main(monkeypatch, seen)
    rc = ev.main([str(d), "--split", "dev", "--out", str(tmp_path / "r.json")])
    res = json.loads((tmp_path / "r.json").read_text())
    assert seen == [] and res["per_case"][0]["error"] == "no search cap"
    assert rc == 1 and res["errors"] == ["c1"]


def test_a_failed_case_exits_1_but_still_writes_the_result(tmp_path, monkeypatch, capsys):
    d = _cases(tmp_path)
    monkeypatch.setattr(ev.cc, "main", lambda argv: 2)
    rc = ev.main([str(d), "--split", "all", "--out", str(tmp_path / "r.json")])
    res = json.loads((tmp_path / "r.json").read_text())
    assert rc == 1 and res["errors"] == ["c1", "c2"]
    assert "2 errors" in capsys.readouterr().out


def test_a_clean_run_has_no_errors_and_exits_0(tmp_path, monkeypatch):
    d = _cases(tmp_path)
    _fake_main(monkeypatch, [])
    assert ev.main([str(d), "--split", "all", "--out", str(tmp_path / "r.json")]) == 0
    assert json.loads((tmp_path / "r.json").read_text())["errors"] == []


def test_hits_record_the_listed_work(tmp_path, monkeypatch):
    d = _cases(tmp_path)
    _fake_main(monkeypatch, [])
    ev.main([str(d), "--split", "dev", "--out", str(tmp_path / "r.json")])
    hit = json.loads((tmp_path / "r.json").read_text())["per_case"][0]["hits"][0]
    assert hit["referee"] == "Fakeman, A. 1979" and hit["authors"] == "Alan Fakeman"
    assert hit["year"] == 1979 and hit["title"] == "A fake classic" and "id" in hit


def test_output_inside_any_git_work_tree_is_refused(tmp_path, monkeypatch):
    d = _cases(tmp_path)
    _fake_main(monkeypatch, [])
    (tmp_path / "other" / ".git").mkdir(parents=True)
    with pytest.raises(SystemExit):
        ev.main([str(d), "--split", "all", "--out", str(tmp_path / "other" / "sub" / "r.json")])


def test_output_refused_by_relative_path_and_by_symlink(tmp_path, monkeypatch):
    d = _cases(tmp_path)
    _fake_main(monkeypatch, [])
    monkeypatch.chdir(ROOT / "eval")
    with pytest.raises(SystemExit):
        ev.main([str(d), "--split", "all", "--out", "r.json"])
    (tmp_path / "link").symlink_to(ROOT / "eval")
    with pytest.raises(SystemExit):
        ev.main([str(d), "--split", "all", "--out", str(tmp_path / "link" / "r.json")])
    with pytest.raises(SystemExit):
        ev.main([str(d), "--split", "all", "--out", str(str(ROOT).upper() + "/r.json")])


def test_the_ranking_option_is_gone(tmp_path):
    with pytest.raises(SystemExit) as e:
        ev.main([str(_cases(tmp_path)), "--split", "all", "--ranking", "count", "--out", str(tmp_path / "r.json")])
    assert e.value.code == 2


def test_cases_dir_inside_the_repository_is_refused(tmp_path):
    with pytest.raises(SystemExit):
        ev.main([str(ROOT / "eval" / "no_such_cases"), "--split", "all",
                 "--out", str(tmp_path / "r.json")])


def test_a_bad_setting_value_is_a_parser_error_not_a_traceback(tmp_path):
    d = _cases(tmp_path)
    with pytest.raises(SystemExit) as e:
        ev.main([str(d), "--split", "all", "--set", "TOP=abc",
                 "--out", str(tmp_path / "r.json")])
    assert e.value.code == 2


def test_run_case_restores_the_mailto_settings(tmp_path, monkeypatch):
    d = _cases(tmp_path)

    def main(argv):
        ev.cc.MAILTO = ev.cc.vc.MAILTO = argv[1]
        return 2
    monkeypatch.setattr(ev.cc, "main", main)
    monkeypatch.setattr(ev.cc, "MAILTO", "")
    monkeypatch.setattr(ev.cc.vc, "MAILTO", "")
    ev.run_case(json.loads((d / "cases.json").read_text())[0], d, {}, "fake@example.org")
    assert ev.cc.MAILTO == "" and ev.cc.vc.MAILTO == ""


def test_a_failed_case_keeps_the_last_five_lines_without_the_key(tmp_path, monkeypatch):
    d = _cases(tmp_path)

    def main(argv):
        ev.cc.API_KEY = "fake-key-777"
        for k in range(6):
            print(f"fake line {k}")
        print("Citation lookup unreachable: fake error with fake-key-777; nothing written.")
        return 2
    monkeypatch.setattr(ev.cc, "main", main)
    monkeypatch.setattr(ev.cc, "API_KEY", "")
    out = ev.run_case(json.loads((d / "cases.json").read_text())[0], d, {})
    err = out["error"]
    assert err.startswith("exit 2") and "fake line 1" not in err
    assert all(f"fake line {k}" in err for k in (2, 3, 4, 5))
    assert "Citation lookup unreachable" in err and "fake-key-777" not in err and "[key]" in err


# ---- reach (every pool, id, and title here is fake) ----

def _reach_cases(tmp_path):
    d = tmp_path / "cases"
    (d / "c1").mkdir(parents=True)
    (d / "c1" / "reference_list_input.txt").write_text("REFERENCES\n\nFake, A. (2001). Fake. J, 1, 1.\n")
    named = [{"authors": "Fakeman, A.", "year": 1979, "title": "A fake classic of careers"},
             {"authors": "Fakerson, B.", "year": 2015, "title": "Fake forward paper on ladders"},
             {"authors": "Fakeworth, C.", "year": 1990, "title": "Fake unreachable study of firms"},
             {"authors": "Ghostly, D.", "year": 2000, "title": "Ghost fake title nobody has"},
             {"authors": "Methodist, E.", "year": 1995, "title": "Fake methods for panels", "kind": "methods"}]
    (d / "cases.json").write_text(json.dumps([{"folder": "c1", "search_before": "2018-01-01",
                                               "missing_specific": named}]))
    (d / "split.json").write_text(json.dumps({"dev": ["c1"], "test": []}))
    return d


_TITLES = {"A fake classic of careers": ("W1", "A Fake Classic of Careers", 1979),
           "Fake forward paper on ladders": ("W2", "Fake forward paper on ladders", 2016),
           "Fake unreachable study of firms": ("W3", "Fake unreachable study of firms", 1990),
           "Ghost fake title nobody has": ("W9", "Something else altogether", 2000),
           "Fake methods for panels": ("W4", "Fake methods for panels", 1995)}


def _reach_fakes(monkeypatch, seen, lookups):
    def main(argv):
        ws = Path(argv[0])
        seen.append(argv)
        (ws / "stage-2").mkdir()
        (ws / "stage-2" / "cocitation.json").write_text(json.dumps({
            "seeds": 5, "openalex_cost_usd": 0.0, "recent": [],
            "classics": [{"authors": "Alan Fakeman", "year": 1979, "title": "A fake classic of careers", "id": "W1"}],
            "pools": {"backward": {"W1": 5, "W4": 2, "W7": 9}, "forward": {"W2": 3}}}))
        return 0

    def get(params):
        lookups.append({"params": params, "cache": ev.cc.CACHE_DIR})
        wid, title, year = _TITLES[params["search"]]
        return {"results": [{"id": f"https://openalex.org/{wid}", "title": title, "display_name": title,
                             "publication_year": year}]}
    monkeypatch.setattr(ev.cc, "main", main)
    monkeypatch.setattr(ev.cc, "_get", get)


def test_reach_marks_each_named_work_and_counts_recall_among_reachable(tmp_path, monkeypatch, capsys):
    d, seen, lookups = _reach_cases(tmp_path), [], []
    _reach_fakes(monkeypatch, seen, lookups)
    before = ev.cc.CACHE_DIR
    out = tmp_path / "r.json"
    assert ev.main([str(d), "--split", "all", "--reach", "--out", str(out)]) == 0
    res = json.loads(out.read_text())
    assert all("--emit-pools" in a for a in seen)
    assert res["reachable"] == 3 and res["found_among_reachable"] == 1 and res["recall_reachable"] == 0.3333
    assert res["substantive_reachable"] == 2 and res["substantive_found_among_reachable"] == 1
    assert res["substantive_recall_reachable"] == 0.5
    reach = {m["referee"]: m["reach"] for m in res["per_case"][0]["misses"]}
    assert reach == {"Fakerson, B. 2015": "forward:3", "Fakeworth, C. 1990": "none",
                     "Ghostly, D. 2000": "unresolved", "Methodist, E. 1995": "backward:2"}
    p = lookups[0]["params"]
    assert p["search"] == "A fake classic of careers" and p["filter"] == "publication_year:1978-1980"
    assert all(x["cache"] == str(d / "_cache") for x in lookups) and ev.cc.CACHE_DIR == before
    line = capsys.readouterr().out
    assert "substantive macro 0.25" in line and "reachable substantive 2" in line
    assert "found among reachable 1" in line


def test_without_reach_no_pools_are_asked_for(tmp_path, monkeypatch):
    d, seen, lookups = _reach_cases(tmp_path), [], []
    _reach_fakes(monkeypatch, seen, lookups)
    out = tmp_path / "r.json"
    ev.main([str(d), "--split", "all", "--out", str(out)])
    res = json.loads(out.read_text())
    assert all("--emit-pools" not in a for a in seen) and lookups == []
    assert "reachable" not in res and "misses" not in res["per_case"][0]


def test_reach_lookups_stop_at_the_first_budget_refusal(tmp_path, monkeypatch, capsys):
    d, seen, lookups = _reach_cases(tmp_path), [], []
    _reach_fakes(monkeypatch, seen, lookups)
    real = ev.cc._get

    def get(params):
        if params["search"] == "Fake forward paper on ladders":
            lookups.append({"params": params, "cache": ev.cc.CACHE_DIR})
            raise ev.cc.BudgetUsedUp(3600)
        return real(params)
    monkeypatch.setattr(ev.cc, "_get", get)
    out = tmp_path / "r.json"
    ev.main([str(d), "--split", "all", "--reach", "--out", str(out)])
    res = json.loads(out.read_text())
    reach = {m["referee"]: m["reach"] for m in res["per_case"][0]["misses"]}
    assert reach == {"Fakerson, B. 2015": "unresolved (budget)", "Fakeworth, C. 1990": "unresolved (budget)",
                     "Ghostly, D. 2000": "unresolved (budget)", "Methodist, E. 1995": "unresolved (budget)"}
    assert len(lookups) == 2 and res["reach_budget_used_up"] is True
    assert res["reachable"] == 1 and res["substantive_reachable"] == 1
    assert "OpenAlex budget used up" in capsys.readouterr().out


def test_reach_lookup_cost_is_added_and_reported(tmp_path, monkeypatch):
    d, seen, lookups = _reach_cases(tmp_path), [], []
    _reach_fakes(monkeypatch, seen, lookups)
    real = ev.cc._get

    def get(params):
        ev.cc.COST_USD += 0.002
        return real(params)
    monkeypatch.setattr(ev.cc, "_get", get)
    out = tmp_path / "r.json"
    ev.main([str(d), "--split", "all", "--reach", "--out", str(out)])
    res = json.loads(out.read_text())
    assert res["reach_cost_usd"] == pytest.approx(0.01)
    assert res["openalex_cost_usd"] == pytest.approx(0.01)  # the fake run itself cost 0.0
    assert res["reach_budget_used_up"] is False


def test_named_work_lookups_are_reused_within_a_run(tmp_path, monkeypatch):
    lookups = []
    _reach_fakes(monkeypatch, [], lookups)
    memo = {}
    m = {"authors": "Fakeman, A.", "year": 1979, "title": "A fake classic of careers"}
    assert ev.named_id(m, memo) == "W1" and ev.named_id(m, memo) == "W1"
    assert len(lookups) == 1
