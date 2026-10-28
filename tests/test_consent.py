from __future__ import annotations
import pytest
from plumb import consent

BASE = dict(role="author", provider="anthropic-api", provider_trains_on_inputs=False,
            retention_days=30, egress=["manuscript_text", "search_queries"], coauthors_agree=True)

def rec(**kw):
    d = dict(BASE); d.update(kw); return consent.from_dict(d)

def test_complete_author_record_passes():
    consent.gate(rec())

def test_author_needs_coauthors():
    assert any("coauthors" in p for p in consent.missing_consents(rec(coauthors_agree=None)))

def test_referee_needs_journal_permission():
    probs = consent.missing_consents(rec(role="referee", coauthors_agree=None, journal_allows=False))
    assert any("journal" in p for p in probs)

def test_unknown_training_blocks():
    assert consent.missing_consents(rec(provider_trains_on_inputs=None))

def test_training_on_blocks():
    assert consent.missing_consents(rec(provider_trains_on_inputs=True))

def test_raw_data_never_allowed():
    with pytest.raises(consent.ConsentError):
        consent.gate(rec(egress=["manuscript_text", "raw_data"]))

def test_data_agreement_false_blocks_but_none_means_no_data():
    assert consent.missing_consents(rec(data_agreement_allows=False))
    assert not consent.missing_consents(rec(data_agreement_allows=None))

def test_irb_false_blocks():
    assert consent.missing_consents(rec(irb_allows_excerpts=False))

def test_bad_role():
    assert consent.missing_consents(rec(role="editor"))


def test_author_asked_records_the_authors_permission_not_coauthors():
    assert consent.missing_consents(rec(permission="author_asked", coauthors_agree=None, author_permission=True)) == []
    probs = consent.missing_consents(rec(permission="author_asked", coauthors_agree=True))
    assert any("The author must have asked you" in p for p in probs)
    assert not any("coauthors" in p for p in probs)


def test_mine_still_needs_coauthors():
    assert any("coauthors" in p for p in consent.missing_consents(rec(permission="mine", coauthors_agree=None)))


def test_permission_must_match_the_record_and_be_known():
    assert any("does not match" in p for p in consent.missing_consents(rec(permission="journal")))
    with pytest.raises(consent.ConsentError):
        consent.from_dict(dict(BASE, permission="friend"))
    with pytest.raises(consent.ConsentError):
        consent.from_dict(dict(BASE, author_permission="yes"))


def test_no_consent_message_says_role():
    probs = consent.missing_consents(rec(role="editor"))
    assert probs and not any("role" in p.lower() for p in probs)

# Fix round 1: type validation tests
def test_string_false_for_irb_rejected():
    with pytest.raises(consent.ConsentError):
        consent.from_dict(dict(role="author", provider="anthropic-api",
                              provider_trains_on_inputs=False, retention_days=30,
                              egress=["manuscript_text"], coauthors_agree=True,
                              irb_allows_excerpts="false"))

def test_string_false_for_data_agreement_rejected():
    with pytest.raises(consent.ConsentError):
        consent.from_dict(dict(role="author", provider="anthropic-api",
                              provider_trains_on_inputs=False, retention_days=30,
                              egress=["manuscript_text"], coauthors_agree=True,
                              data_agreement_allows="false"))

def test_empty_string_for_provider_trains_rejected():
    with pytest.raises(consent.ConsentError):
        consent.from_dict(dict(role="author", provider="anthropic-api",
                              provider_trains_on_inputs="", retention_days=30,
                              egress=["manuscript_text"], coauthors_agree=True))

def test_zero_for_provider_trains_rejected():
    with pytest.raises(consent.ConsentError):
        consent.from_dict(dict(role="author", provider="anthropic-api",
                              provider_trains_on_inputs=0, retention_days=30,
                              egress=["manuscript_text"], coauthors_agree=True))

def test_retention_days_bool_rejected():
    with pytest.raises(consent.ConsentError):
        consent.from_dict(dict(role="author", provider="anthropic-api",
                              provider_trains_on_inputs=False, retention_days=True,
                              egress=["manuscript_text"], coauthors_agree=True))

def test_missing_role_raises():
    with pytest.raises(consent.ConsentError):
        consent.from_dict(dict(provider="anthropic-api",
                              provider_trains_on_inputs=False, retention_days=30,
                              egress=["manuscript_text"]))

def test_missing_provider_raises():
    with pytest.raises(consent.ConsentError):
        consent.from_dict(dict(role="author",
                              provider_trains_on_inputs=False, retention_days=30,
                              egress=["manuscript_text"]))

def test_missing_provider_trains_on_inputs_raises():
    with pytest.raises(consent.ConsentError):
        consent.from_dict(dict(role="author", provider="anthropic-api",
                              retention_days=30, egress=["manuscript_text"]))

def test_missing_retention_days_raises():
    with pytest.raises(consent.ConsentError):
        consent.from_dict(dict(role="author", provider="anthropic-api",
                              provider_trains_on_inputs=False,
                              egress=["manuscript_text"]))

def test_raw_data_and_other_unknown_both_reported():
    probs = consent.missing_consents(rec(egress=["manuscript_text", "raw_data", "weird"]))
    has_raw_data = any("Raw data may never leave" in p for p in probs)
    has_unknown = any("Unknown egress items" in p for p in probs)
    assert has_raw_data and has_unknown

def test_direct_construct_with_string_false_fails_gate():
    r = consent.ConsentRecord(role="author", provider="anthropic-api",
                             provider_trains_on_inputs=False, retention_days=30,
                             egress=["manuscript_text"], coauthors_agree=True,
                             irb_allows_excerpts="false")
    with pytest.raises(consent.ConsentError):
        consent.gate(r)


# Architecture review I-7: the record must declare what every run sends.
def test_empty_egress_blocks():
    probs = consent.missing_consents(rec(egress=[]))
    assert any("manuscript_text" in p and "search_queries" in p for p in probs)

def test_missing_search_queries_blocks():
    probs = consent.missing_consents(rec(egress=["manuscript_text"]))
    assert any("missing: search_queries" in p for p in probs)

def test_missing_manuscript_text_blocks():
    with pytest.raises(consent.ConsentError, match="manuscript_text"):
        consent.gate(rec(egress=["search_queries"]))


# Ruling 39: author consent at submission, in referee mode.
REF = dict(role="referee", coauthors_agree=None, journal_allows=True)

def test_referee_blocked_when_author_did_not_consent():
    probs = consent.missing_consents(rec(author_consented_at_submission=False, **REF))
    assert any("did not consent" in p for p in probs)

def test_referee_unknown_author_consent_passes_when_profile_does_not_require_it():
    assert consent.missing_consents(rec(author_consented_at_submission=None, **REF)) == []

def test_referee_unknown_author_consent_blocks_when_profile_requires_it():
    probs = consent.missing_consents(rec(author_consented_at_submission=None, **REF), requires_author_consent=True)
    assert any("requires the author's consent" in p for p in probs)

def test_referee_author_consent_true_passes_when_required():
    consent.gate(rec(author_consented_at_submission=True, **REF), requires_author_consent=True)

def test_author_mode_ignores_author_consent_rule():
    assert consent.missing_consents(rec(author_consented_at_submission=None), requires_author_consent=True) == []


# Ruling 40 (5): the zero-retention confirmation is part of the record and the gate enforces it.
def test_zero_retention_needed_but_unconfirmed_blocks():
    probs = consent.missing_consents(rec(**REF), needs_zero_retention=True)
    assert any("zero data retention" in p for p in probs)

def test_zero_retention_needed_and_false_blocks():
    with pytest.raises(consent.ConsentError):
        consent.gate(rec(zero_retention_confirmed=False, **REF), needs_zero_retention=True)

def test_zero_retention_confirmed_passes_when_needed():
    consent.gate(rec(zero_retention_confirmed=True, **REF), needs_zero_retention=True)

def test_zero_retention_not_needed_ignores_field():
    assert consent.missing_consents(rec(**REF)) == []

def test_zero_retention_must_be_bool():
    with pytest.raises(consent.ConsentError):
        rec(zero_retention_confirmed="yes")


def _referee(**kw):
    d = dict(role="referee", provider="anthropic-api", provider_trains_on_inputs=False, retention_days=0,
             egress=["manuscript_text", "search_queries"], journal_allows=True)
    d.update(kw)
    return consent.from_dict(d)


def test_unrecorded_policy_needs_self_confirmation():
    probs = consent.missing_consents(_referee(), journal_policy_recorded=False)
    assert any("not recorded" in p for p in probs)
    assert not consent.missing_consents(_referee(journal_allows_self_confirmed=True), journal_policy_recorded=False)


def test_self_confirmation_must_be_bool():
    with pytest.raises(consent.ConsentError):
        _referee(journal_allows_self_confirmed="yes")


def test_recorded_policy_ignores_self_confirmation_field():
    assert not consent.missing_consents(_referee())


def test_irb_attestation_not_sure_does_not_block():
    assert not consent.missing_consents(rec(irb_allows_excerpts=None))
    assert not consent.missing_consents(rec(irb_allows_excerpts=True))


def test_irb_attestation_no_blocks_with_a_plain_message():
    problems = consent.missing_consents(rec(irb_allows_excerpts=False))
    assert any("ethics approval or a site agreement" in p for p in problems)
