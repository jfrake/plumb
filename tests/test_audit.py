from __future__ import annotations
import pytest
from plumb import audit, checkin

def test_log_and_read(tmp_path):
    audit.log_event(tmp_path, "verification", check="quotes", result="pass")
    audit.log_event(tmp_path, "checkin", stop="setup", item="level", recommended="standard", answer="light")
    ev = audit.read_events(tmp_path)
    assert [e["kind"] for e in ev] == ["verification", "checkin"]
    assert all("ts" in e for e in ev)

def test_unknown_kind_rejected(tmp_path):
    with pytest.raises(ValueError):
        audit.log_event(tmp_path, "gossip", x=1)

def test_render_has_every_section_even_when_empty(tmp_path):
    audit.log_event(tmp_path, "model", role="reasoning", name="inherit")
    text = audit.render_package(tmp_path).read_text()
    for title in audit.TITLES.values():
        assert f"## {title}" in text
    assert "None recorded." in text

def test_dependency_warning_is_logged_and_visible(tmp_path):
    audit.warn_dependency(tmp_path, "codex", "Codex not installed; a Claude agent ran the stress test.")
    text = audit.render_package(tmp_path).read_text()
    assert "a Claude agent ran the stress test" in text

def test_reserved_keys_rejected(tmp_path):
    with pytest.raises(ValueError):
        audit.log_event(tmp_path, "verification", ts="x")
    assert audit.read_events(tmp_path) == []


def test_dig_deeper_is_its_own_kind_and_renders(tmp_path):
    audit.log_event(tmp_path, "dig_deeper", item="majors:2", text="The sample is selected.")
    text = audit.render_package(tmp_path).read_text()
    section = text.split(f"## {audit.TITLES['dig_deeper']}", 1)[1].split("\n## ", 1)[0]
    assert "item: majors:2" in section


def test_counts_separate_overrides_and_dig_deeper(tmp_path):
    checkin.record(tmp_path, "majors", "majors:1", "A. Keep it (Recommended)", "B. Minor")
    audit.log_event(tmp_path, "dig_deeper", item="majors:1", text="x")
    audit.log_event(tmp_path, "dig_deeper", item="majors:2", text="y")
    c = audit.counts(tmp_path)
    assert c["override"] == 1 and c["dig_deeper"] == 2 and c["checkin"] == 1
    assert set(c) == set(audit.KINDS) | {"auto_answers", "user_answers", "delegations"}


# Final review I1: override counts come from the last answer recorded for each (stop, item).
def _reviewer_case(ws):
    rec_m = "A. Keep it as a major issue (Recommended) | The sample is selected."
    checkin.record(ws, "majors", "majors:1", rec_m, "D. Dig deeper before deciding | The sample is selected.")
    checkin.record(ws, "majors", "majors:1", rec_m, rec_m.replace(" (Recommended)", ""))
    rec_a = "A. Plausible, investigate further (Recommended) | Demand rises."
    ans_a = "B. Plausible, but the paper handles it (give the page) | Demand rises."
    checkin.record(ws, "against", "against:2", rec_a, ans_a)
    checkin.record(ws, "against", "against:2", rec_a, ans_a, note="p.4: handled")


def test_rerecorded_answers_count_one_override(tmp_path):
    _reviewer_case(tmp_path)
    c = audit.counts(tmp_path)
    assert c["override"] == 1
    assert c["user_answers"] == 2 and c["auto_answers"] == 0 and c["checkin"] == 4


def test_audit_package_lists_each_override_once(tmp_path):
    _reviewer_case(tmp_path)
    text = audit.render_package(tmp_path).read_text()
    section = text.split(f"## {audit.TITLES['override']}", 1)[1].split("\n## ", 1)[0]
    rows = [ln for ln in section.splitlines() if ln.startswith("- ")]
    assert len(rows) == 1 and "item: against:2" in rows[0] and "note: p.4: handled" in rows[0]
    assert "Each item is listed once, from its final answer." in section


def test_counts_do_not_depend_on_override_events(tmp_path):
    # A stray override event (for example from an older version of record) does not change the count.
    checkin.record(tmp_path, "majors", "majors:1", "A. Keep it (Recommended)", "B. Minor")
    audit.log_event(tmp_path, "override", stop="majors", item="majors:1", recommended="A", answer="B")
    assert audit.counts(tmp_path)["override"] == 1


def test_renumbered_replay_keeps_the_original_override(tmp_path):
    rec = "A. Plausible, investigate further (Recommended)"
    checkin.record(tmp_path, "against", "against:1", f"{rec} | X.", "C. Not plausible here | X.")
    checkin.record(tmp_path, "against", "against:2", f"{rec} | Y.", f"{rec} | Y.")
    # The stage reruns and the agent swaps the numbers; both answers are replayed by text.
    checkin.record(tmp_path, "against", "against:1", f"{rec} | Y.", f"{rec} | Y.", note="replayed; ")
    checkin.record(tmp_path, "against", "against:2", f"{rec} | X.", "C. Not plausible here | X.", note="replayed; ")
    assert audit.counts(tmp_path)["override"] == 1


def test_auto_answers_reported_apart_and_never_override(tmp_path):
    checkin.record(tmp_path, "read", "read:summary", "A. Yes, continue (Recommended)",
                   "A. Yes, continue (Recommended)", note="auto")
    checkin.record(tmp_path, "draft", "draft:ready", "A. The output is ready (Recommended)",
                   "A. The output is ready (Recommended)", note="auto")
    checkin.record(tmp_path, "majors", "majors:1", "A. Keep it (Recommended)", "B. Minor")
    checkin.record(tmp_path, "setup", "setup:role", "", "A. Mine", note="preference")
    c = audit.counts(tmp_path)
    assert c["auto_answers"] == 2 and c["user_answers"] == 1 and c["override"] == 1


# Fix round 2: the denominator counts only answers that could be overrides.
def test_let_me_pick_denominator_is_the_minors_shown(tmp_path):
    checkin.record(tmp_path, "minors", "minors:list", "A. Keep all (Recommended)", "C. Let me pick")
    for n in range(1, 11):
        if n in (3, 7):
            checkin.record(tmp_path, "minors", f"minors:{n}", "Keep (Recommended)", f"Drop: Minor {n}.")
        else:
            checkin.record(tmp_path, "minors", f"minors:{n}", "Keep (Recommended)", "Keep (Recommended)")
    checkin.record(tmp_path, "draft", "draft:ready", "A. The output is ready (Recommended)",
                   "Please shorten comment 3", note="free text")
    rec = "A. Plausible, investigate further (Recommended) | Demand rises."
    checkin.record(tmp_path, "against", "against:1", rec, rec, note="delegated to the tool")
    c = audit.counts(tmp_path)
    assert c["override"] == 2 and c["user_answers"] == 10 and c["delegations"] == 1 and c["auto_answers"] == 0


def _measured_report():
    row = {"input": 100, "output": 20, "cache_write": 5, "cache_read": 1000, "seconds": 65.0,
           "cost_usd": 0.5, "cost_complete": True}
    return {"measured": True, "method": "", "price_table": {"as_of": "2000-01-01", "source": "Fake."},
            "sessions": 1, "agents": 2, "missing_transcripts": 0, "codex": None, "unpriced_models": [],
            "by_stage": [dict(stage="0", **row)], "by_model": [dict(model="claude-fakeopus-1", **row)],
            "total": dict(row)}


def test_audit_package_ends_with_usage(tmp_path):
    import json
    from plumb import usage
    audit.log_event(tmp_path, "model", role="judgment", name="inherit")
    text = audit.render_package(tmp_path).read_text()
    assert text.rstrip().endswith("## Usage\n\nUsage was not recorded for this run.")
    usage.write_report(tmp_path)
    assert "Usage not measured in this app." in audit.render_package(tmp_path).read_text()
    (tmp_path / "usage.json").write_text(json.dumps(_measured_report()))
    text = audit.render_package(tmp_path).read_text()
    assert "| Stage 0 | 100 | 20 | 5 | 1,000 | 1m 05s | $0.50 |" in text and "API-equivalent" in text
