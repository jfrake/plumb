"""Which check-ins run for a level and tier, and a record of every answer."""
from __future__ import annotations
import re
from . import audit
from . import depth as _depth

LEVELS = ("light", "standard", "handson", "auto")
TIERS = _depth.DEPTHS
STOP_STAGE = {"setup": 0, "numbers": 1, "read": 2, "against": 3, "majors": 4, "minors": 5, "draft": 7}
_LEVEL_STOPS = {
    "light": {"setup", "majors", "draft"},
    "standard": set(STOP_STAGE),
    "handson": set(STOP_STAGE),
    "auto": {"setup"},
}


def stops_for(level: str, tier: str) -> list:
    if level not in LEVELS:
        raise ValueError(f"level must be one of {LEVELS}")
    stages = set(_depth.STAGES[_depth.normalize(tier)])
    ordered = sorted(STOP_STAGE.items(), key=lambda kv: kv[1])
    return [s for s, stage in ordered if s in _LEVEL_STOPS[level] and stage in stages]


def minors_mode(level: str):
    return {"standard": "list", "handson": "each"}.get(level)


# Stops whose answers can overrule the tool. Setup answers are preferences and never count.
OVERRIDE_STOPS = ("numbers", "read", "against", "majors", "minors", "draft")
# Notes marking an answer that is not the user disagreeing with the tool. "auto" marks an answer
# the tool took at a stop the level does not ask.
NO_OVERRIDE_NOTES = ("preference", "delegated to the tool", "free text", "replayed", "auto")
AUTO_NOTE = "auto"
DELEGATED_NOTE = "delegated to the tool"
# Answers that choose how to answer, not what to decide. Each later choice is judged on its own.
MODE_CHOICES = {"minors:list": ("C",)}


def _choice(label: str) -> str:
    """The option an answer picked: its letter ("B. ..."), or for letterless options
    ("Keep", "Drop: <sentence>") the text before any colon. "(Recommended)" is ignored."""
    head = label.split(" | ", 1)[0].strip()
    head = re.sub(r"\s*\(Recommended\)\s*$", "", head)
    m = re.match(r"^([A-Z])\.(?:\s|$)", head)
    if m:
        return m.group(1)
    return head.split(":", 1)[0].strip().lower()


def is_override(stop: str, recommended: str, answer: str, note: str = "", item: str = "") -> bool:
    if stop not in OVERRIDE_STOPS or not recommended:
        return False
    if note.startswith(NO_OVERRIDE_NOTES):
        return False
    if _choice(answer) in MODE_CHOICES.get(item, ()):
        return False
    return _choice(answer) != _choice(recommended)


def record(workspace, stop: str, item: str, recommended: str, answer: str, note: str = "") -> dict:
    if stop not in STOP_STAGE:
        raise ValueError(f"unknown stop: {stop}")
    prior = [e for e in audit.read_events(workspace)
             if e["kind"] == "override" and e.get("stop") == stop and e.get("item") == item]
    ev = audit.log_event(workspace, "checkin", stop=stop, item=item, recommended=recommended, answer=answer, note=note)
    # Override events are the audit trail only; counts come from final_answers. A re-record of the
    # same choice adds no second event.
    if is_override(stop, recommended, answer, note, item) and not (
            prior and _choice(prior[-1]["answer"]) == _choice(answer)):
        audit.log_event(workspace, "override", stop=stop, item=item, recommended=recommended, answer=answer)
    return ev


def final_answers(events: list) -> dict:
    """The last recorded answer for each (stop, item), ignoring replayed copies. An item recorded
    more than once (a re-ask, a note added later) counts once, by its final answer. An item that
    only holds replayed copies has no entry: its answer is counted where it was first given."""
    out = {}
    for e in events:
        if e["kind"] == "checkin" and not str(e.get("note", "")).startswith("replayed"):
            out[(e["stop"], e["item"])] = e
    return out


def counts_as_user_answer(ev: dict) -> bool:
    """Whether a final answer belongs in the override-rate denominator: a judgment-stop answer the
    user gave that could have been an override. See `audit.counts`."""
    note = str(ev.get("note", ""))
    if ev["stop"] not in OVERRIDE_STOPS or note in (AUTO_NOTE, DELEGATED_NOTE):
        return False
    if note.startswith("free text"):
        return False
    return _choice(ev["answer"]) not in MODE_CHOICES.get(ev["item"], ())


def final_overrides(events: list) -> list:
    """The final answers that overrule the tool, one per (stop, item)."""
    return [e for e in final_answers(events).values()
            if is_override(e["stop"], e.get("recommended", ""), e["answer"], e.get("note", ""), e["item"])]


def answered(workspace) -> set:
    return {(e["stop"], e["item"]) for e in audit.read_events(workspace) if e["kind"] == "checkin"}


def answers(workspace) -> dict:
    """The chosen label for each answered item; the last answer wins."""
    return {e["item"]: e["answer"] for e in audit.read_events(workspace) if e["kind"] == "checkin"}


def letter(label: str) -> str:
    """The option letter an answer starts with: "B. ..." -> "B"."""
    return label.split(".", 1)[0].strip().upper()


_letter = letter


def is_pruned(question: dict, given: dict) -> bool:
    """Whether an earlier answer prunes this question. `given` maps each answered item to its letter."""
    return any(given.get(k) == str(v).upper() for k, v in (question.get("prune_if") or {}).items())


def frontier(questions: list, workspace) -> list:
    """Questions to ask this round: unanswered, prerequisites answered, not pruned by an earlier answer."""
    given = {e["item"]: _letter(e["answer"]) for e in audit.read_events(workspace) if e["kind"] == "checkin"}
    out = []
    for q in questions:
        if q["id"] in given:
            continue
        if any(d not in given for d in q.get("depends_on") or []):
            continue
        if is_pruned(q, given):
            continue
        out.append(q)
    return out
