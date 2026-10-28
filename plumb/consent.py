"""Consent record: who agreed, what leaves the machine, under what terms. A hard gate."""
from __future__ import annotations
from dataclasses import dataclass, field, fields
from typing import List, Optional

ALLOWED_EGRESS = {"manuscript_text", "search_queries", "code_summary_output", "codex_stress_test"}
# Who receives each egress item, when it is not the model provider.
EGRESS_RECIPIENTS = {
    "search_queries": ("web search and page fetches through the agent's tools; "
                       "OpenAlex, Crossref, and Semantic Scholar from this machine"),
    "codex_stress_test": "OpenAI, through the Codex CLI (stress test)",
}
# Every run sends these, so the record must declare them.
REQUIRED_EGRESS = ("manuscript_text", "search_queries")
# Logged when the item is actually sent, not at the consent check, because the run may skip it.
LOGGED_AT_USE = ("codex_stress_test",)
_STRESS_KEYS = {"provider", "trains_on_inputs", "retention_days", "zero_retention_confirmed"}
# Whose permission covers the manuscript (setup:permission), and the run it makes.
PERMISSIONS = {"mine": "author", "author_asked": "author", "journal": "referee"}


class ConsentError(Exception):
    pass


@dataclass
class ConsentRecord:
    role: str
    provider: str
    provider_trains_on_inputs: Optional[bool]
    retention_days: Optional[int]
    egress: List[str] = field(default_factory=list)
    coauthors_agree: Optional[bool] = None
    journal_allows: Optional[bool] = None
    author_consented_at_submission: Optional[bool] = None
    data_agreement_allows: Optional[bool] = None
    irb_allows_excerpts: Optional[bool] = None
    zero_retention_confirmed: Optional[bool] = None
    journal_allows_self_confirmed: Optional[bool] = None
    stress_test_provider: Optional[dict] = None
    permission: Optional[str] = None
    author_permission: Optional[bool] = None


def from_dict(d: dict) -> ConsentRecord:
    # Check required fields are present
    required = {"role", "provider", "provider_trains_on_inputs", "retention_days"}
    missing = required - set(d.keys())
    if missing:
        raise ConsentError(f"Missing required fields: {', '.join(sorted(missing))}.")

    # Type validation
    errors = []

    if not isinstance(d.get("role"), str):
        errors.append("role must be a string")

    if not isinstance(d.get("provider"), str):
        errors.append("provider must be a string")

    # provider_trains_on_inputs must be bool or None
    pti = d.get("provider_trains_on_inputs")
    if pti is not None and not isinstance(pti, bool):
        errors.append("provider_trains_on_inputs must be true, false, or null")

    # retention_days must be int or None (but not bool, which is a subclass of int)
    rd = d.get("retention_days")
    if rd is not None and (isinstance(rd, bool) or not isinstance(rd, int)):
        errors.append("retention_days must be an integer or null")

    # Optional bool fields must be bool or None
    optional_bools = {"coauthors_agree", "journal_allows", "author_consented_at_submission",
                      "data_agreement_allows", "irb_allows_excerpts", "zero_retention_confirmed",
                      "journal_allows_self_confirmed", "author_permission"}
    for field_name in optional_bools:
        val = d.get(field_name)
        if val is not None and not isinstance(val, bool):
            errors.append(f"{field_name} must be true, false, or null")

    perm = d.get("permission")
    if perm is not None and perm not in PERMISSIONS:
        errors.append("permission must be mine, author_asked, journal, or null")

    # egress must be a list of str
    egress = d.get("egress", [])
    if not isinstance(egress, list):
        errors.append("egress must be a list")
    elif not all(isinstance(e, str) for e in egress):
        errors.append("egress must contain only strings")

    stp = d.get("stress_test_provider")
    if stp is not None:
        if not isinstance(stp, dict):
            errors.append("stress_test_provider must be an object or null")
        else:
            unknown = sorted(set(stp) - _STRESS_KEYS)
            if unknown:
                errors.append(f"stress_test_provider has unknown keys: {', '.join(unknown)}")
            if not isinstance(stp.get("provider"), str):
                errors.append("stress_test_provider.provider must be a string")
            for key in ("trains_on_inputs", "zero_retention_confirmed"):
                val = stp.get(key)
                if val is not None and not isinstance(val, bool):
                    errors.append(f"stress_test_provider.{key} must be true, false, or null")
            srd = stp.get("retention_days")
            if srd is not None and (isinstance(srd, bool) or not isinstance(srd, int)):
                errors.append("stress_test_provider.retention_days must be an integer or null")

    if errors:
        raise ConsentError("; ".join(errors) + ".")

    # Extract only valid field names
    names = {f.name for f in fields(ConsentRecord)}
    return ConsentRecord(**{k: v for k, v in d.items() if k in names})


# Profile upload policies under which a listed journal allows AI tools in review.
PROFILE_ALLOWS_UPLOAD = ("allowed", "conditional")


def apply_journal_profile(r: ConsentRecord, upload: str) -> ConsentRecord:
    """A referee at a listed journal whose profile allows upload takes journal_allows from the
    profile when the record leaves it unset. An explicit answer is never overridden, a banned
    journal is refused before this, and an unlisted journal (upload unknown) still needs the
    referee's own confirmation."""
    if r.role == "referee" and r.journal_allows is None and upload in PROFILE_ALLOWS_UPLOAD:
        r.journal_allows = True
    return r


def missing_consents(r: ConsentRecord, requires_author_consent: bool = False,
                     needs_zero_retention: bool = False, journal_policy_recorded: bool = True) -> list:
    """requires_author_consent comes from the journal profile (referee mode);
    needs_zero_retention comes from the referee decision; journal_policy_recorded is False
    when the referee's journal profile has no recorded upload policy."""
    problems = []

    # Type checking for bool fields: must be bool or None
    bool_fields = {
        "coauthors_agree": r.coauthors_agree,
        "journal_allows": r.journal_allows,
        "author_consented_at_submission": r.author_consented_at_submission,
        "data_agreement_allows": r.data_agreement_allows,
        "irb_allows_excerpts": r.irb_allows_excerpts,
        "zero_retention_confirmed": r.zero_retention_confirmed,
        "journal_allows_self_confirmed": r.journal_allows_self_confirmed,
        "author_permission": r.author_permission,
    }
    for field_name, val in bool_fields.items():
        if val is not None and not isinstance(val, bool):
            problems.append(f"{field_name} must be true, false, or unknown.")

    # Type checking for provider_trains_on_inputs
    if r.provider_trains_on_inputs is not None and not isinstance(r.provider_trains_on_inputs, bool):
        problems.append("provider_trains_on_inputs must be true, false, or unknown.")

    if r.role not in ("author", "referee"):
        problems.append("The record does not say whose permission covers the paper.")
    if r.permission is not None and PERMISSIONS.get(r.permission) != r.role:
        problems.append("The record's permission answer does not match the run it describes.")
    if r.role == "author" and r.permission == "author_asked":
        if r.author_permission is not True:
            problems.append("The author must have asked you to read the paper and agreed that it may be "
                            "sent to a model provider.")
    elif r.role == "author" and r.coauthors_agree is not True:
        problems.append("All coauthors must agree before the paper is sent to a model provider.")
    if r.role == "referee" and r.journal_allows is not True:
        problems.append("The journal's policy must allow AI tools in review.")
    if r.role == "referee" and not journal_policy_recorded and r.journal_allows_self_confirmed is not True:
        problems.append("Your journal's AI policy is not recorded. "
                        "Confirm that your journal allows AI tools in review.")
    if r.role == "referee" and r.author_consented_at_submission is False:
        problems.append("The author did not consent at submission to reviewers using AI tools.")
    if r.role == "referee" and requires_author_consent and r.author_consented_at_submission is None:
        problems.append("This journal requires the author's consent at submission to AI tools in review. "
                        "Confirm the author gave it.")
    # data_agreement_allows: None means "not applicable" (no code and data path yet); only False blocks.
    # irb_allows_excerpts is the author's attestation for quoted interviews, field notes, or
    # open-ended answers: Yes is True, No is False and blocks, Not sure is None and continues.
    if r.data_agreement_allows is False:
        problems.append("The data agreement does not allow this processing.")
    if r.irb_allows_excerpts is False:
        problems.append("Your ethics approval or a site agreement does not allow sending the manuscript "
                        "to a model provider.")
    if needs_zero_retention and r.zero_retention_confirmed is not True:
        problems.append("This journal requires an API account with zero data retention. "
                        "Confirm the account has it.")
    if r.provider_trains_on_inputs is None:
        problems.append("Confirm whether the model provider trains on your inputs.")
    elif r.provider_trains_on_inputs is True:
        problems.append("The model provider trains on inputs. Turn training off or use an API account.")

    # Handle egress validation: report both raw_data and other unknown items
    bad = [e for e in r.egress if e not in ALLOWED_EGRESS]
    if "raw_data" in bad:
        problems.append("Raw data may never leave the machine.")
        other_bad = [e for e in bad if e != "raw_data"]
        if other_bad:
            problems.append(f"Unknown egress items: {', '.join(other_bad)}.")
    elif bad:
        problems.append(f"Unknown egress items: {', '.join(bad)}.")

    undeclared = [e for e in REQUIRED_EGRESS if e not in r.egress]
    if undeclared:
        problems.append(
            "Every run sends the manuscript text to the model provider and search queries "
            "drawn from the paper to search engines and citation databases. Declare both in "
            f"egress (missing: {', '.join(undeclared)}).")

    return problems


def gate(r: ConsentRecord, requires_author_consent: bool = False,
         needs_zero_retention: bool = False, journal_policy_recorded: bool = True) -> None:
    problems = missing_consents(r, requires_author_consent, needs_zero_retention, journal_policy_recorded)
    if problems:
        raise ConsentError(" ".join(problems))


def stress_test_problems(r: ConsentRecord, needs_zero_retention: bool = False) -> list:
    """Why the record does not cover the Codex stress test; empty means covered.
    These never stop the run. Without Codex, a fresh Claude agent runs the stress test instead."""
    p = r.stress_test_provider
    if "codex_stress_test" not in r.egress or p is None:
        return ["The consent record does not cover sending the paper to OpenAI for the Codex stress test."]
    problems = []
    if p.get("trains_on_inputs") is None:
        problems.append("Confirm whether OpenAI trains on inputs for the account Codex uses.")
    elif p.get("trains_on_inputs") is True:
        problems.append("OpenAI trains on inputs for the account Codex uses. Turn training off to use Codex for the stress test.")
    if needs_zero_retention and p.get("zero_retention_confirmed") is not True:
        problems.append("This journal requires zero data retention. "
                        "Confirm the OpenAI account Codex uses has zero data retention.")
    return problems
