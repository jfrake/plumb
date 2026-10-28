from __future__ import annotations
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "packs" / "network" / "scripts" / "check_network_numbers.py"
POOLED = dict(same_network=True, actors=412, ties=1030, directed=False)


def _mod():
    spec = importlib.util.spec_from_file_location("check_network_numbers", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _rec(kind, **fields):
    base = {"id": "r1", "kind": kind, "page": 9, "location": "Table 1"}
    base.update(fields)
    return base


def _run(*records):
    return _mod().run(list(records))["results"]


def _by(results, quantity):
    found = [r for r in results if r["quantity"] == quantity]
    assert len(found) == 1, (quantity, results)
    return found[0]


def test_summary_flags_the_fixture_density_and_passes_mean_degree():
    res = _run(_rec("summary", density="0.12", mean_degree="5.00", **POOLED))
    d = _by(res, "density")
    assert d["flag"] == "density_mismatch" and d["status"] == "computed"
    assert abs(d["computed"] - 1030 / 84666) < 1e-12
    m = _by(res, "mean_degree")
    assert m["flag"] is None and m["computed"] == 5.0


def test_summary_skips_different_networks():
    res = _run(_rec("summary", same_network=False, actors=412, ties=1030, directed=False, density="0.12"))
    assert len(res) == 1 and res[0]["status"] == "not_checked" and res[0]["flag"] is None
    assert "different_networks" in res[0]["note"]


def test_directed_formulas():
    res = _run(_rec("summary", same_network=True, actors=10, ties=18, directed=True, density="0.20",
                    mean_degree="1.8", degree_kind="out"))
    assert _by(res, "density")["computed"] == pytest.approx(0.2) and _by(res, "density")["flag"] is None
    assert _by(res, "mean_degree")["computed"] == pytest.approx(1.8) and _by(res, "mean_degree")["flag"] is None
    total = _run(_rec("summary", same_network=True, actors=10, ties=18, directed=True,
                      mean_degree="3.6", degree_kind="total"))
    assert _by(total, "mean_degree")["flag"] is None
    no_kind = _run(_rec("summary", same_network=True, actors=10, ties=18, directed=True, mean_degree="1.8"))
    assert no_kind[0]["status"] == "input_error"
    either = _run(_rec("summary", same_network=True, actors=10, ties=18, directed=True,
                       mean_degree="3.6", degree_kind="unstated"))
    assert _by(either, "mean_degree")["flag"] is None and _by(either, "mean_degree")["computed"] == pytest.approx(3.6)
    neither = _run(_rec("summary", same_network=True, actors=10, ties=18, directed=True,
                        mean_degree="2.5", degree_kind="unstated"))
    assert _by(neither, "mean_degree")["flag"] == "mean_degree_mismatch"
    over = _run(_rec("summary", same_network=True, actors=4, ties=7, directed=False))
    assert _by(over, "density")["flag"] == "density_out_of_range"


@pytest.mark.parametrize("shown,flag", [("0.012", None), ("0.0122", None), ("0.12", "density_mismatch"),
                                        ("1.2%", None), ("12%", "density_mismatch")])
def test_tolerance_reads_the_printed_decimals(shown, flag):
    assert _by(_run(_rec("summary", density=shown, **POOLED)), "density")["flag"] == flag


def test_dyad_maximum_depends_on_pair_ordering_and_sides():
    ordered = _by(_run(_rec("dyads", actors=412, periods=10, reported_dyads=900000, sampling="full")), "dyads")
    assert ordered["computed"] == 1693320 and ordered["flag"] is None
    once = _by(_run(_rec("dyads", actors=412, periods=10, each_pair_once=True, reported_dyads=900000,
                         sampling="full")), "dyads")
    assert once["computed"] == 846660 and once["flag"] == "dyads_exceed_risk_set"
    two = _by(_run(_rec("dyads", actors=50, actors_other_side=300, periods=5, reported_dyads=80000,
                        sampling="unclear")), "dyads")
    assert two["computed"] == 75000 and two["flag"] == "dyads_exceed_risk_set"


def test_sampled_count_flags_only_an_excess():
    base = dict(actors=412, periods=10, sampling="sampled", ties=800, sampled_nonties=200000)
    assert all(r["flag"] is None for r in _run(_rec("dyads", reported_dyads=200800, **base)))
    over = _by(_run(_rec("dyads", reported_dyads=201000, **base)), "sampled_count")
    assert over["flag"] == "sampled_count_exceeded"
    short = _by(_run(_rec("dyads", reported_dyads=199500, **base)), "sampled_count")
    assert short["flag"] is None and "1300" in short["note"]


def test_response_shares_without_a_coding_rule():
    r = _by(_run(_rec("response", actors=120, respondents=78, directed=False)), "response")
    c = r["computed"]
    assert (c["pairs"], c["both_pairs"], c["any_pairs"]) == (7140, 3003, 6279)
    assert c["both_share"] == pytest.approx(0.42059, abs=1e-5) and c["any_share"] == pytest.approx(0.87941, abs=1e-5)
    assert "sender_share" not in c and r["flag"] is None
    d = _by(_run(_rec("response", actors=120, respondents=78, directed=True)), "response")["computed"]
    assert d["sender_share"] == pytest.approx(0.65) and (d["sender_pairs"], d["ordered_pairs"]) == (9282, 14280)


def test_respondents_exceed_actors():
    r = _by(_run(_rec("response", actors=50, respondents=60, directed=False)), "response")
    assert r["flag"] == "respondents_exceed_actors"


def test_range_kind():
    assert _by(_run(_rec("range", measure="clustering", value="1.3")), "clustering")["flag"] == "out_of_range"
    assert _by(_run(_rec("range", measure="density", value="0.45")), "density")["flag"] is None
    assert _run(_rec("range", measure="constraint", value="1.3"))[0]["status"] == "input_error"


def test_bad_values_are_input_errors_not_crashes():
    res = _run(_rec("summary", same_network=True, actors="many", ties=10, directed=False),
               _rec("summary", density="n/a", **POOLED),
               _rec("summary", density="0,0122", **POOLED))
    assert [r["status"] for r in res] == ["input_error", "input_error", "input_error"]
    mod = _mod()
    with pytest.raises(mod.InputError):
        mod.printed("1,030")
    comma = _run(_rec("summary", same_network=True, actors=100, ties=206, directed=False, mean_degree="4,120"))
    assert [r["status"] for r in comma] == ["input_error"] and comma[0]["flag"] is None


def test_out_of_range_density_never_echoes_nan():
    out = _mod().run([_rec("summary", same_network=True, actors=10, ties=100, directed=False,
                           density=float("nan"))])
    text = json.dumps(out, allow_nan=False)
    assert json.loads(text)["results"][0]["flag"] == "density_out_of_range"


def test_huge_values_are_input_errors_not_crashes():
    res = _run(_rec("summary", same_network=True, actors=5, ties=10**400, directed=False, density="0.1"),
               _rec("dyads", actors=10**400, periods=10**400, reported_dyads=1, sampling="full"),
               _rec("response", actors=10**400, respondents=3, directed=False),
               _rec("range", measure="density", value="1e400"))
    assert [r["status"] for r in res] == ["input_error"] * 4


def _cli(tmp_path, payload):
    f = tmp_path / "in.json"
    f.write_text(payload if isinstance(payload, str) else json.dumps(payload))
    return subprocess.run([sys.executable, str(SCRIPT), str(f)], capture_output=True, text=True)


@pytest.mark.parametrize("payload,message", [
    ([{"id": "a", "kind": "summary", "page": 1, "location": "T1", "actors": 5, "ties": 4, "directed": False}],
     "same_network"),
    ([{"id": "a", "kind": "ego", "page": 1, "location": "T1"}], "unknown kind"),
    ([{"id": "a", "kind": ["summary"], "page": 1, "location": "T1"}], "unknown kind"),
    ({"id": "a"}, "list"),
    ("{not json", "JSON"),
])
def test_cli_exits_2_on_bad_input(tmp_path, payload, message):
    r = _cli(tmp_path, payload)
    assert r.returncode == 2 and message in r.stderr and r.stdout == ""


def test_cli_prints_assumptions_and_results(tmp_path):
    r = _cli(tmp_path, [_rec("summary", density="0.12", **POOLED)])
    out = json.loads(r.stdout)
    assert r.returncode == 0 and out["assumptions"] and out["results"][0]["flag"] == "density_mismatch"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["in.json"]
