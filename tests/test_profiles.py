from __future__ import annotations
from pathlib import Path
import pytest
from plumb import profiles

PDIR = Path(__file__).resolve().parents[1] / "profiles"

@pytest.mark.parametrize("pid", ["orgsci", "mansci", "smj", "asq", "amj", "generic"])
def test_shipped_profiles_load_and_cite_sources(pid):
    p = profiles.load_profile(PDIR, pid)
    assert p.upload in profiles.UPLOAD and p.drafting in profiles.DRAFTING
    if pid != "generic":
        assert p.sources and all({"quote", "url", "retrieved"} <= set(s) for s in p.sources)

def _decide(pid, requested, **kw):
    return profiles.referee_decision(profiles.load_profile(PDIR, pid), requested, **kw)


ALL = ["issues_list", "annotated_pdf", "report"]


@pytest.mark.parametrize("pid", ["smj", "amj", "asq"])
def test_banned_upload_blocks_referee(pid):
    d = _decide(pid, ALL)
    assert not d.allowed and d.outputs == [] and "bans uploading" in d.reasons[0]


def test_orgsci_allows_all_three_with_zdr_and_disclosure():
    d = _decide("orgsci", ["report", "annotated_pdf", "issues_list"])
    assert d.allowed and d.outputs == ALL and d.issues_list_mode == "full" and d.needs_zero_retention
    assert any("disclosing" in r for r in d.reasons)


def test_orgsci_without_report_has_no_disclosure_reason():
    d = _decide("orgsci", ["issues_list", "annotated_pdf"])
    assert d.outputs == ["issues_list", "annotated_pdf"] and d.reasons == []


def test_mansci_is_treated_like_orgsci():
    # Ruling, 2026-09-29: Management Science's drafting rule does not narrow the outputs.
    d = _decide("mansci", ALL)
    assert d.allowed and d.outputs == ALL and d.issues_list_mode == "full" and d.needs_zero_retention
    assert any("disclosing" in r for r in d.reasons)
    d = _decide("mansci", ["annotated_pdf"])
    assert d.outputs == ["annotated_pdf"] and d.issues_list_mode == "full" and d.reasons == []


def test_requested_outputs_parse_from_a_comma_list_in_a_b_c_order():
    assert profiles.parse_outputs("report,issues_list") == ["issues_list", "report"]


@pytest.mark.parametrize("bad", [[], "", "fix_list", ["issues_list", "memo"]])
def test_bad_requested_outputs(bad):
    with pytest.raises(ValueError):
        profiles.parse_outputs(bad)


def test_quick_depth_drops_the_report_and_is_facts_only():
    d = _decide("orgsci", ALL, depth="quick")
    assert d.allowed and d.outputs == ["issues_list", "annotated_pdf"] and d.issues_list_mode == "facts_only"
    assert not any("disclosing" in r for r in d.reasons)
    d = _decide("generic", ["report"], self_confirmed=True, depth="quick")
    assert d.outputs == ["issues_list"] and d.issues_list_mode == "facts_only"


def test_unknown_or_misspelled_journal_is_off():
    d = profiles.referee_decision(profiles.load_profile(PDIR, "org-sci-typo"), "report")
    assert not d.allowed and "not recorded" in d.reasons[0]

def test_bad_request():
    with pytest.raises(ValueError):
        profiles.referee_decision(profiles.load_profile(PDIR, "orgsci"), "decision")

def test_invalid_value_rejected(tmp_path):
    (tmp_path / "x.yaml").write_text("id: x\nname: X\nupload: sometimes\ndrafting: silent\nrequires_zero_retention: false\n")
    with pytest.raises(ValueError):
        profiles.load_profile(tmp_path, "x")

@pytest.mark.parametrize("bad_pid", ["../x", "a/b", "ORGSCI", ""])
def test_path_traversal_blocked(tmp_path, bad_pid):
    with pytest.raises(ValueError, match="journal id must use lowercase letters"):
        profiles.load_profile(tmp_path, bad_pid)

def test_id_mismatch_rejected(tmp_path):
    (tmp_path / "x.yaml").write_text("id: y\nname: X\nupload: allowed\ndrafting: allowed\nrequires_zero_retention: false\n")
    with pytest.raises(ValueError):
        profiles.load_profile(tmp_path, "x")

def test_requires_zero_retention_must_be_bool(tmp_path):
    (tmp_path / "x.yaml").write_text("id: x\nname: X\nupload: allowed\ndrafting: allowed\nrequires_zero_retention: \"false\"\n")
    with pytest.raises(ValueError):
        profiles.load_profile(tmp_path, "x")


def test_requires_author_consent_defaults_false_in_shipped_profiles():
    for pid in ["orgsci", "mansci", "smj", "asq", "amj", "generic"]:
        assert profiles.load_profile(PDIR, pid).requires_author_consent is False

def test_requires_author_consent_read_and_must_be_bool(tmp_path):
    base = "id: x\nname: X\nupload: allowed\ndrafting: allowed\nrequires_zero_retention: false\n"
    (tmp_path / "x.yaml").write_text(base + "requires_author_consent: true\n")
    assert profiles.load_profile(tmp_path, "x").requires_author_consent is True
    (tmp_path / "x.yaml").write_text(base + "requires_author_consent: \"yes\"\n")
    with pytest.raises(ValueError):
        profiles.load_profile(tmp_path, "x")


def test_unlisted_journal_self_confirmed_is_treated_as_orgsci():
    d = _decide("generic", ALL, self_confirmed=True)
    assert d.allowed and d.outputs == ALL and d.issues_list_mode == "full" and d.needs_zero_retention
    assert any("disclosing" in r for r in d.reasons)
    assert any("You confirmed" in r for r in d.reasons)


def test_unlisted_journal_self_confirmed_issues_list_only():
    d = _decide("generic", ["issues_list"], self_confirmed=True)
    assert d.allowed and d.outputs == ["issues_list"] and d.needs_zero_retention


def test_unlisted_journal_without_confirmation_still_off():
    d = _decide("generic", ["report"])
    assert not d.allowed and "not recorded" in d.reasons[0]


@pytest.mark.parametrize("pid", ["smj", "amj", "asq"])
def test_self_confirmation_never_unlocks_a_banned_journal(pid):
    d = _decide(pid, ["report"], self_confirmed=True)
    assert not d.allowed and d.outputs == []


@pytest.mark.parametrize("pid", ["smj", "amj", "asq"])
def test_banned_upload_is_reported_even_with_no_outputs(pid):
    # The outputs screen is skipped for these referees, so the list can arrive empty.
    d = _decide(pid, "")
    assert d.allowed is False and "bans uploading" in d.reasons[0]
