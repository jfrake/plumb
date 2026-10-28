from __future__ import annotations
import pytest
from plumb import checkin, depth


def test_three_depths():
    assert depth.DEPTHS == ("quick", "standard", "deep")


def test_full_is_an_alias_for_deep():
    assert depth.normalize("full") == "deep"
    assert depth.limits("full") == depth.limits("deep")


def test_unknown_depth_rejected():
    with pytest.raises(ValueError):
        depth.normalize("thorough")


def test_revisions_per_depth():
    assert [depth.limits(d)["revisions"] for d in depth.DEPTHS] == [1, 2, 4]


def test_stages_per_depth():
    assert depth.limits("quick")["stages"] == [0, 1, 2, 7]
    assert depth.limits("standard")["stages"] == list(range(8))
    assert depth.limits("deep")["stages"] == list(range(8))


def test_deep_doubles_turns_and_notes_and_standard_and_deep_stress_test():
    s, d = depth.limits("standard"), depth.limits("deep")
    assert (s["turn_factor"], s["notes_factor"], s["stress_test"]) == (1, 1, True)
    assert (d["turn_factor"], d["notes_factor"], d["stress_test"]) == (2, 2, True)
    assert depth.limits("quick")["stress_test"] is False


def test_search_budgets():
    std, deep = depth.limits("standard")["searches"], depth.limits("deep")["searches"]
    assert std["setting-research"] == "about 15" and deep["setting-research"] == "70-100"
    for agent in ("timeline-research", "contribution-research", "adjacent-literature", "boundary-conditions"):
        assert std[agent] == "about 15" and deep[agent] == "25-35"
    assert std["editor-reader"] == "about 10" and deep["editor-reader"] == "about 20"
    assert depth.limits("quick")["searches"] == {}


def test_stops_for_accepts_full_as_deep():
    assert checkin.stops_for("standard", "full") == checkin.stops_for("standard", "deep")


def test_standard_splits_roles_and_deep_uses_judgment_everywhere():
    cfg = {"mechanical": "mid", "judgment": "top"}
    assert depth.models("quick", cfg) == {"mechanical": "mid", "judgment": "top"}
    assert depth.models("standard", cfg) == {"mechanical": "mid", "judgment": "top"}
    assert depth.models("deep", cfg) == {"mechanical": "top", "judgment": "top"}
    assert depth.models("full", cfg)["mechanical"] == "top"


# Final review m1: old run.json files.
@pytest.mark.parametrize("cfg, answer, want", [
    ({"depth": "full"}, "", "deep"),
    ({"tier": "full"}, "", "deep"),
    ({"tier": "quick"}, "", "quick"),
    ({}, "C. Full", "deep"),
    ({}, "B. Quick", "quick"),
    ({}, "", "standard"),
    ({"depth": "Standard"}, "", "standard"),
])
def test_from_run_handles_old_run_files(cfg, answer, want):
    assert depth.from_run(cfg, answer) == want


# Final review m4: Codex never receives a Claude model.
def test_codex_platform_never_gets_claude_aliases():
    cfg = {"mechanical": "sonnet", "judgment": "opus"}
    assert depth.models("standard", cfg, "codex") == {"mechanical": "inherit", "judgment": "inherit"}
    assert depth.models("deep", {"judgment": "claude-top"}, "codex")["judgment"] == "inherit"
    assert depth.models("standard", {"mechanical": "codex-small", "judgment": "codex-big"}, "codex") == \
        {"mechanical": "codex-small", "judgment": "codex-big"}
    assert depth.models("standard", cfg) == {"mechanical": "sonnet", "judgment": "opus"}
    with pytest.raises(ValueError):
        depth.models("standard", cfg, "other")
