"""Append-only audit log for a run, and the audit package rendered from it."""
from __future__ import annotations
import datetime
import json
from pathlib import Path

from . import usage as _usage

KINDS = ("verification", "accuracy_change", "qc_ruling", "checkin", "override", "dig_deeper",
         "consent", "egress", "model", "dependency", "output")
TITLES = {
    "verification": "Verifications and results",
    "accuracy_change": "Changes made by the accuracy audit",
    "qc_ruling": "Quality-control rulings",
    "checkin": "Check-ins",
    "override": "Where you overruled the tool",
    "dig_deeper": "Requests to dig deeper",
    "consent": "Consent record",
    "egress": "What left this machine",
    "model": "Models and settings",
    "dependency": "Dependencies and warnings",
    "output": "Files written",
}


def _path(workspace) -> Path:
    return Path(workspace) / "audit" / "events.jsonl"


def log_event(workspace, kind: str, **data) -> dict:
    if kind not in KINDS:
        raise ValueError(f"unknown audit event kind: {kind}")
    reserved = {"ts", "kind"}
    offending = sorted(reserved & set(data.keys()))
    if offending:
        raise ValueError(f"audit event data may not use reserved key(s): {', '.join(offending)}")
    ev = {"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "kind": kind}
    ev.update(data)
    p = _path(workspace)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(ev, sort_keys=True) + "\n")
    return ev


def read_events(workspace) -> list:
    p = _path(workspace)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def warn_dependency(workspace, name: str, message: str) -> dict:
    return log_event(workspace, "dependency", name=name, message=message)


def _row(e: dict) -> str:
    return f"- {e['ts']} " + "; ".join(f"{k}: {v}" for k, v in sorted(e.items()) if k not in ("ts", "kind"))


def _run(workspace) -> dict:
    try:
        run = json.loads((Path(workspace) / "run.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return run if isinstance(run, dict) else {}


def _settings(workspace) -> list:
    """Lines after the model events: the settings run.json carries that the events do not."""
    from . import rundir
    run = _run(workspace)
    lines = [_usage.render_models(_usage.model_record(workspace)), ""]
    if run.get("search_before"):
        lines += [rundir.search_cap_line(run), ""]
    return lines


def render_package(workspace) -> Path:
    events = read_events(workspace)
    lines = ["# Audit package", ""]
    for kind in KINDS:
        lines += [f"## {TITLES[kind]}", ""]
        if kind == "override":
            rows = _checkin.final_overrides(events)
        else:
            rows = [e for e in events if e["kind"] == kind]
        if not rows:
            lines += ["None recorded.", ""]
        elif kind == "consent":
            # The recap can rewrite consent.json; the last record checked is the one the run used.
            lines += ["Final record:", _row(rows[-1]), ""]
            if rows[:-1]:
                lines += ["Earlier records:"] + [_row(e) for e in rows[:-1]] + [""]
        else:
            for e in rows:
                detail = "; ".join(f"{k}: {v}" for k, v in sorted(e.items()) if k not in ("ts", "kind"))
                lines.append(f"- {e['ts']} {detail}")
            lines.append("")
        if kind == "override":
            logged = sum(1 for e in events if e["kind"] == "override")
            lines += [f"Each item is listed once, from its final answer. Override events logged (every "
                      f"recorded answer, re-records included): {logged}.", ""]
        if kind == "model":
            lines += _settings(workspace)
    lines += _usage.render(_usage.load_report(workspace))
    out = Path(workspace) / "audit_package.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def counts(workspace) -> dict:
    """Counts for the run. Every kind in KINDS is a raw event count, except `override`.

    The counts below read final answers: for each (stop, item), the last `checkin` whose note does
    not start with "replayed". An item recorded twice therefore counts once.
    - `override`: final answers at the judgment stops that overrule the tool (`checkin.is_override`).
    - `user_answers`: final answers at the judgment stops (numbers, read, against, majors, minors,
      draft) that could be overrides. It leaves out answers the tool took at a skipped stop (note
      "auto"), mode choices (such as "C. Let me pick" at `minors:list`), typed answers (note starts
      "free text"), and delegations (note "delegated to the tool"). This is the override-rate
      denominator.
    - `auto_answers`: final answers with note "auto", which the tool took at stops the level skips.
    - `delegations`: final answers with note "delegated to the tool". Add them to `user_answers` if
      delegations belong in the denominator.
    Overrides and dig-deeper requests (`dig_deeper`) stay apart."""
    events = read_events(workspace)
    out = {kind: sum(1 for e in events if e["kind"] == kind) for kind in KINDS}
    finals = list(_checkin.final_answers(events).values())
    out["override"] = len(_checkin.final_overrides(events))
    out["auto_answers"] = sum(1 for e in finals if e.get("note") == _checkin.AUTO_NOTE)
    out["delegations"] = sum(1 for e in finals if e.get("note") == _checkin.DELEGATED_NOTE)
    out["user_answers"] = sum(1 for e in finals if _checkin.counts_as_user_answer(e))
    return out


from . import checkin as _checkin  # noqa: E402  (checkin imports this module)
