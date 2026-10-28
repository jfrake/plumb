"""Journal profiles: policy fields (from Harmon's dataset) plus hand-written norms."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import re

import yaml

UPLOAD = {"banned", "conditional", "allowed", "unknown"}
DRAFTING = {"banned", "reviewer_own", "silent", "allowed", "unknown"}


@dataclass
class Profile:
    id: str
    name: str
    upload: str
    drafting: str
    requires_zero_retention: bool
    sources: list = field(default_factory=list)
    requires_author_consent: bool = False
    norms: dict = field(default_factory=dict)


OUTPUTS = ("issues_list", "annotated_pdf", "report", "editor_memo")
PROFILES_DIR = Path(__file__).resolve().parents[1] / "profiles"


def needs_zero_retention(profile: Profile) -> bool:
    """A referee needs an API account with zero data retention where the journal allows tools on
    that condition, or where its policy is not recorded."""
    return (profile.upload == "conditional" and profile.requires_zero_retention) or profile.upload == "unknown"


def run_needs_zero_retention(run: dict, record, profiles_dir=None) -> bool:
    """Whether the run needs zero retention: run.json says so, or the consent record is a referee's
    and the journal in run.json needs it. A referee with no readable journal counts as needing it."""
    if run.get("needs_zero_retention"):
        return True
    if record is None or record.role != "referee":
        return False
    try:
        return needs_zero_retention(load_profile(profiles_dir or PROFILES_DIR, run.get("journal") or "generic"))
    except ValueError:
        return True
DISCLOSURE_REASON = "The report carries a line disclosing that the tool was used."


@dataclass
class RefereeDecision:
    allowed: bool
    outputs: list
    issues_list_mode: str
    needs_zero_retention: bool
    reasons: list


def load_profile(profiles_dir, pid: str) -> Profile:
    # Validate pid against path traversal
    if not re.match(r"^[a-z0-9][a-z0-9_-]*$", pid):
        raise ValueError("journal id must use lowercase letters, digits, '-' or '_'")

    p = Path(profiles_dir) / f"{pid}.yaml"
    if not p.exists():
        return Profile(id=pid, name=pid, upload="unknown", drafting="unknown", requires_zero_retention=True)
    d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if d.get("upload") not in UPLOAD:
        raise ValueError(f"{p.name}: upload must be one of {sorted(UPLOAD)}")
    if d.get("drafting") not in DRAFTING:
        raise ValueError(f"{p.name}: drafting must be one of {sorted(DRAFTING)}")

    # Check if id field differs from pid
    file_id = d.get("id")
    if file_id is not None and file_id != pid:
        raise ValueError(f"id mismatch in {p.name}: file has id={file_id!r} but pid={pid!r}")

    # Validate requires_zero_retention is a real boolean
    zdr_value = d.get("requires_zero_retention", True)
    if not isinstance(zdr_value, bool):
        raise ValueError(f"{p.name}: requires_zero_retention must be a boolean, not {type(zdr_value).__name__}")

    # Optional: the journal requires the author's consent at submission before a referee uses AI tools.
    author_consent = d.get("requires_author_consent", False)
    if not isinstance(author_consent, bool):
        raise ValueError(f"{p.name}: requires_author_consent must be a boolean, not {type(author_consent).__name__}")

    return Profile(id=d.get("id", pid), name=d.get("name", pid), upload=d["upload"], drafting=d["drafting"],
                   requires_zero_retention=zdr_value, requires_author_consent=author_consent,
                   sources=d.get("sources") or [], norms=d.get("norms") or {})


def parse_outputs(requested) -> list:
    """The requested outputs in A, B, C order. Accepts a list or a comma-separated string."""
    items = requested.split(",") if isinstance(requested, str) else list(requested)
    items = [i.strip() for i in items if i.strip()]
    bad = [i for i in items if i not in OUTPUTS]
    if not items or bad:
        raise ValueError("requested outputs must be one or more of: " + ", ".join(OUTPUTS))
    return [o for o in OUTPUTS if o in items]


def referee_decision(profile: Profile, requested, self_confirmed: bool = False, depth: str = "") -> RefereeDecision:
    """Which of the requested outputs a referee may have at this journal, and the issues list's mode.
    self_confirmed: a referee at a journal whose policy is not recorded confirmed that the
    journal allows AI tools in review. It never overrides a recorded ban. depth: at Quick depth
    no report is written and the issues list holds checked facts only, whatever the journal allows.
    A recorded ban is reported before the outputs are parsed, since its referee is never asked for any."""
    if profile.upload == "banned":
        return _journal_decision(profile, [], self_confirmed)
    d = _journal_decision(profile, parse_outputs(requested), self_confirmed)
    if d.allowed and str(depth).lower() == "quick":
        d.outputs = [o for o in d.outputs if o not in ("report", "editor_memo")] or ["issues_list"]
        d.issues_list_mode = "facts_only"
        d.reasons = [r for r in d.reasons if r != DISCLOSURE_REASON]
    if d.allowed:
        d.outputs = filter_outputs_for_role(d.outputs, "journal", depth, profile) or ["issues_list"]
    return d


def editor_memo_offered(permission: str, depth: str, profile: Profile) -> bool:
    """The checked-facts memo for an editor is offered only when a journal sent the paper for
    review, the journal allows AI tools in review (an unlisted journal's referee confirms that at
    setup, or the run stops), and the depth is Standard or Deep."""
    return (permission == "journal" and str(depth).lower() in ("standard", "deep", "full")
            and profile.upload != "banned")


def filter_outputs_for_role(outputs_list: list, permission: str, depth: str, profile: Profile = None) -> list:
    """Drop `editor_memo` from `outputs_list` unless `editor_memo_offered` allows it for this
    permission, depth, and journal profile. Every other requested output passes through
    unchanged. `profile` may be omitted when `permission` is not `journal`: `editor_memo_offered`
    never returns true for an author or a friendly reader regardless of the journal, so no
    profile lookup is needed to know the memo must go. This runs on every path that can end up
    writing `outputs` to `run.json`, not only a referee's."""
    if "editor_memo" not in outputs_list:
        return list(outputs_list)
    if profile is not None and editor_memo_offered(permission, depth, profile):
        return list(outputs_list)
    return [o for o in outputs_list if o != "editor_memo"]


def _journal_decision(profile: Profile, wanted: list, self_confirmed: bool) -> RefereeDecision:
    if profile.upload == "banned":
        return RefereeDecision(False, [], "full", False,
                               [f"Referee mode is off: {profile.name} bans uploading manuscripts to AI tools."])
    if profile.upload == "unknown":
        if not self_confirmed:
            return RefereeDecision(False, [], "full", False,
                                   [f"Referee mode is off: the AI policy for {profile.name} is not recorded."])
        reasons = ["You confirmed that your journal allows AI tools in review. "
                   "The consent record and the audit package record it.",
                   "Your journal's policy is not recorded, so the run needs an API account with zero data retention."]
        if "report" in wanted:
            reasons.append(DISCLOSURE_REASON)
        return RefereeDecision(True, wanted, "full", True, reasons)
    zdr = needs_zero_retention(profile)
    # reviewer_own (Management Science) is treated like any journal that allows drafting.
    if profile.drafting in ("silent", "allowed", "reviewer_own"):
        return RefereeDecision(True, wanted, "full", zdr, [DISCLOSURE_REASON] if "report" in wanted else [])
    kept = [o for o in wanted if o != "report"] or ["issues_list"]
    own = f"{profile.name} requires the review's conclusions to be your own, "
    if wanted == ["report"]:
        reason = own + "so I write a list of checked facts instead of a report."
    elif "report" in wanted:
        reason = own + "so I write no report, and the other outputs hold checked facts only."
    else:
        reason = own + "so the outputs hold checked facts only."
    return RefereeDecision(True, kept, "facts_only", zdr, [reason])
