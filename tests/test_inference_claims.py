from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "review" / "scripts" / "verify_arithmetic.py"
sys.path.insert(0, str(SCRIPT.parent))
import verify_arithmetic as va  # noqa: E402


def _claim(**kw):
    rec = {"id": "c1", "claim": {"op": "<", "level": "0.10"}}
    rec.update(kw)
    return va.check_claim(rec)


def test_an_over_claim_is_flagged_with_both_readings():
    r = _claim(b="0.061", se="0.052", directional=True, tails="unstated")
    assert r["flag"] is True and r["status"] == "ok"
    two = r["values"]["two-sided"]
    one = r["values"]["one-tailed, which the paper does not state"]
    assert two == [pytest.approx(0.2324, abs=1e-4), pytest.approx(0.2492, abs=1e-4)]
    assert one == [pytest.approx(0.1162, abs=1e-4), pytest.approx(0.1246, abs=1e-4)]
    assert "the text claims p < 0.10" in r["detail"]


def test_claim_true_one_tailed_on_a_directional_hypothesis_is_not_flagged():
    # 0.061 (0.039): two-sided p 0.110 to 0.126, one-tailed 0.055 to 0.063.
    assert _claim(b="0.061", se="0.039", directional=True, tails="unstated")["flag"] is False
    assert _claim(b="0.061", se="0.039", directional=False, tails="unstated")["flag"] is True
    assert _claim(b="0.061", se="0.039", directional=True, tails="two")["flag"] is True
    assert _claim(b="0.061", se="0.052", directional=True, tails="one")["flag"] is True


def test_rounding_keeps_a_claim_the_printed_digits_allow():
    # 0.048 / 0.025 is 1.92 (p 0.055), but the digits allow p down to 0.0477.
    assert _claim(b="0.048", se="0.025", claim={"op": "<", "level": "0.05"})["flag"] is False


def test_a_printed_p_is_read_as_printed():
    assert _claim(b="0.2", p="0.03", claim={"op": "<", "level": "0.05"})["flag"] is False
    assert _claim(b="0.2", p="0.12")["flag"] is True
    assert _claim(b="0.2", p="< .001", claim={"op": "<", "level": "0.01"})["flag"] is False


def test_a_stated_p_smaller_than_the_digits_allow_is_flagged():
    assert _claim(b="0.084", se="0.047", claim={"op": "=", "p": "0.01"})["flag"] is True
    assert _claim(b="0.084", se="0.047", claim={"op": "=", "p": "0.07"})["flag"] is False


def test_a_t_statistic_is_read():
    assert _claim(t="1.50", claim={"op": "<", "level": "0.05"})["flag"] is True
    assert _claim(t="2.10", claim={"op": "<", "level": "0.05"})["flag"] is False


def test_claims_of_non_significance_and_unreadable_records_are_not_computable():
    r = _claim(b="0.50", se="0.10", claim={"op": ">=", "level": "0.05"})
    assert r["status"] == "not_computable" and r["flag"] is False
    assert _claim(b="0.50")["status"] == "not_computable"
    assert _claim(b="0.50", se="0.0")["status"] == "not_computable"


def _run(tmp_path, payload):
    claims = tmp_path / "claims.json"
    if payload is not None:
        claims.write_text(payload)
    out, js = tmp_path / "out.md", tmp_path / "out.json"
    r = subprocess.run([sys.executable, str(SCRIPT), "--claims", str(claims), str(out), "--json", str(js)],
                       capture_output=True, text=True)
    return r, out, js


def test_claims_cli_writes_the_report_and_json(tmp_path):
    recs = [{"id": "h4", "b": "0.061", "se": "0.052", "directional": True, "tails": "unstated",
             "claim": {"op": "<", "level": "0.10"}},
            {"id": "h1", "b": "0.046", "se": "0.020", "claim": {"op": "<", "level": "0.05"}}]
    r, out, js = _run(tmp_path, json.dumps(recs))
    assert r.returncode == 0, r.stderr
    text = out.read_text()
    assert text.startswith("VERDICT: ERRORS_FOUND") and "- [ERROR] claim_vs_se text (h4):" in text
    assert "(h1)" not in text
    assert [x["flag"] for x in json.loads(js.read_text())] == [True, False]


@pytest.mark.parametrize("payload", [None, "not json", '{"id": "x"}'])
def test_claims_cli_exits_2_on_bad_input(tmp_path, payload):
    r, out, _ = _run(tmp_path, payload)
    assert r.returncode == 2 and not out.exists()


# Fix round 1
def test_printed_p_honors_one_tailed_reading():
    base = {"b": "0.061", "p": "0.08", "directional": True, "claim": {"op": "<", "level": "0.05"}}
    assert _claim(tails="unstated", **base)["flag"] is False
    assert _claim(tails="one", **base)["flag"] is False
    assert _claim(tails="two", **base)["flag"] is True
    r = _claim(tails="unstated", **{**base, "p": "0.2"})
    assert r["flag"] is True and "(normal)" not in r["detail"]
    assert "one-tailed (printed p halved)" in r["values"]


def test_malformed_records_are_invalid_not_exceptions(tmp_path):
    r = _claim(b="0.1", se="0.07", claim="p<0.05")
    assert r["status"] == "invalid" and r["flag"] is False
    recs = [{"id": "a", "b": "0.1", "se": "0.07", "claim": "p<0.05"},
            {"id": "b", "b": "0.061", "se": "0.052", "directional": True, "tails": "unstated",
             "claim": {"op": "<", "level": "0.10"}}]
    res, out, js = _run(tmp_path, json.dumps(recs))
    assert res.returncode == 0, res.stderr
    got = json.loads(js.read_text())
    assert [x["status"] for x in got] == ["invalid", "ok"] and got[1]["flag"] is True
    assert _claim(b=["x"], se="0.1")["status"] == "invalid"


@pytest.mark.parametrize("tails", ["one-tailed", "One tailed", " 1 "])
def test_tails_spellings_normalize(tails):
    r = _claim(b="0.061", se="0.039", directional=False, tails=tails)
    assert r["flag"] is False


def test_unknown_tails_is_the_lenient_reading():
    assert _claim(b="0.061", se="0.039", directional=True, tails="banana")["flag"] is False


def test_touching_rounding_boxes_do_not_flag():
    assert _claim(b="0.2", p="0.04", claim={"op": "=", "p": "0.03"})["flag"] is False
    assert _claim(b="0.2", p="0.05", claim={"op": "=", "p": "0.04"})["flag"] is False


def test_json_parent_directory_is_created(tmp_path):
    claims = tmp_path / "c.json"
    claims.write_text("[]")
    js = tmp_path / "deep" / "er" / "o.json"
    r = subprocess.run([sys.executable, str(SCRIPT), "--claims", str(claims), str(tmp_path / "o.md"),
                        "--json", str(js)], capture_output=True, text=True)
    assert r.returncode == 0 and js.exists()


@pytest.mark.parametrize("level", ["0", "1.5", "-0.1"])
def test_level_outside_unit_interval_is_not_computable(level):
    r = _claim(b="0.5", se="0.1", claim={"op": "<", "level": level})
    assert r["status"] == "not_computable" and r["flag"] is False


def test_report_wording_and_counts(tmp_path):
    assert _claim(b="0.5", se="0.1", claim=None)["detail"] == "no significance claim given"
    recs = [{"id": "z", "b": "0.5"}]
    r, out, _ = _run(tmp_path, json.dumps(recs))
    text = out.read_text()
    assert text.startswith("VERDICT: NOTHING_CHECKED")
    assert "flagged: 0 | ok: 0 | not_computable: 1 | invalid: 0" in text


# --- Final fix wave, section B ---

def test_detail_has_no_stray_space_before_semicolon():
    r = _claim(b="0.061", p="0.2", tails="two", directional=True, claim={"op": "<", "level": "0.05"})
    assert r["flag"] is True and " ;" not in r["detail"] and "; the text claims" in r["detail"]
    n = _claim(b="0.061", se="0.052", directional=True, tails="unstated")
    assert n["flag"] is True and " ;" not in n["detail"] and "(normal); the text claims" in n["detail"]


def test_empty_claims_list_is_nothing_checked(tmp_path):
    r, out, _ = _run(tmp_path, "[]")
    assert r.returncode == 0
    assert out.read_text().startswith("VERDICT: NOTHING_CHECKED")
