"""The override rate of one Standard run, from audit/events.jsonl and the stage files: every
final answer that overrules the tool (checkin.is_override), with its stage, pack, and
adjudication type, over the answers that could have been overrides (checkin.counts_as_user_answer),
by stage, stop, pack, and adjudication type. Demotions, alternatives marked handled, and audit
rulings overturned count here; they are not drops, so they never enter the rating pool.
`eval/override_rate.py` wraps `override_rate` and prints JSON then markdown."""
from __future__ import annotations
import re

from . import audit, checkin, fixture_score
from .eval_pool import ADJUDICATIONS, CITATION, PoolError, UNKNOWN, _drops, _records, majors_draft, pack_of


class OverrideError(Exception):
    """The run folder is missing or malformed."""


def _issues(ws) -> list:
    out = {}
    for rel in ("stage-5/issues.json", "stage-6/issues.json"):
        for i in _records(ws, rel):
            if "id" in i:
                out.setdefault(str(i["id"]), i)
    return list(out.values())


def _typed(issue: dict, run: dict) -> tuple:
    adj = issue.get("adjudication")
    return pack_of(issue, run) or UNKNOWN, adj if adj in ADJUDICATIONS else UNKNOWN


def attribute(item: str, stop: str, answer: str, issues: list, draft: dict, run: dict) -> tuple:
    """(pack, adjudication type) for a check-in item: the issue it names in stage-5 or stage-6
    issues.json (by check-in item, or for an alternative by a source naming it, as the pool
    matches them), else majors_draft.md for a major, else a numbers flag's pack (paper by
    nature), else unknown."""
    if stop == "numbers":
        m = re.match(r"numbers:pack:([^:]+):", item)
        return (m.group(1) if m else "core"), "paper"
    if stop in ("majors", "minors"):
        for i in issues:
            if i.get("checkin") == item:
                return _typed(i, run)
        if stop == "minors" and answer.startswith("Drop:"):
            sentence = fixture_score._norm(answer[len("Drop:"):])
            for i in issues:
                if i.get("kind") == "minor" and sentence and (
                        fixture_score._norm(i.get("summary")).startswith(sentence)
                        or fixture_score._norm(i.get("title")).startswith(sentence)):
                    return _typed(i, run)
        if stop == "majors" and item in draft:
            return draft[item]["pack"], draft[item]["adjudication"]
        return UNKNOWN, UNKNOWN
    if stop == "against":
        for i in issues:
            if i.get("checkin") == item or item in (i.get("sources") or []):
                return _typed(i, run)
        return UNKNOWN, UNKNOWN
    if stop == "draft":
        m = re.match(r"draft:(?:ruling|drop):(.+)$", item)
        if m:
            src = m.group(1)
            for i in issues:
                if str(i["id"]) == src or src in (i.get("sources") or []):
                    return _typed(i, run)
    return UNKNOWN, UNKNOWN


def kind_of(ev: dict) -> str:
    """What the override did: citation (the Stage 6 citation check-in), drop, demotion, handled
    (against B), correction (read), reading (a numbers cell or table), ruling overturned, edits
    (draft:ready), or other."""
    stop, item, answer = ev["stop"], str(ev["item"]), str(ev.get("answer", ""))
    letter = checkin._choice(answer)
    if item.startswith(CITATION):
        return "citation"
    if _drops(ev):
        return "drop"
    if stop == "majors" and letter == "B":
        return "demotion"
    if stop == "against" and letter == "B":
        return "handled"
    if stop == "read":
        return "correction"
    if stop == "numbers" and item.startswith(("numbers:cell:", "numbers:table:")):
        return "reading"
    if stop == "draft" and item.startswith("draft:ruling:"):
        return "ruling overturned"
    if stop == "draft" and item == "draft:ready":
        return "edits"
    return "other"


def _cell(rows: dict, key, is_override: bool) -> None:
    cell = rows.setdefault(str(key), {"overrides": 0, "answers": 0})
    cell["answers"] += 1
    cell["overrides"] += is_override


def _rates(rows: dict) -> dict:
    for cell in rows.values():
        cell["rate"] = round(100 * cell["overrides"] / cell["answers"], 2) if cell["answers"] else 0.0
    return rows


def override_rate(run_dir) -> dict:
    """The override table for a run folder (or its workspace)."""
    try:
        ws = fixture_score.workspace(run_dir)
        run = fixture_score.run_record(ws)
    except fixture_score.ScoreError as exc:
        raise OverrideError(str(exc))
    try:
        issues = _issues(ws)
    except PoolError as exc:
        raise OverrideError(str(exc))
    draft = majors_draft(ws)
    events = audit.read_events(ws)
    finals = sorted(checkin.final_answers(events).values(), key=lambda e: (checkin.STOP_STAGE.get(e["stop"], 9), e["item"]))
    overrides, by_stage, by_stop, by_pack, by_adj = [], {}, {}, {}, {}
    totals = {"overrides": 0, "answers": 0}
    for ev in finals:
        if not checkin.counts_as_user_answer(ev):
            continue
        stop, item, answer = ev["stop"], str(ev["item"]), str(ev.get("answer", ""))
        over = checkin.is_override(stop, str(ev.get("recommended", "")), answer, str(ev.get("note") or ""), item)
        pack, adj = attribute(item, stop, answer, issues, draft, run)
        totals["answers"] += 1
        totals["overrides"] += over
        _cell(by_stage, checkin.STOP_STAGE[stop], over)
        _cell(by_stop, stop, over)
        _cell(by_pack, pack, over)
        _cell(by_adj, adj, over)
        if over:
            overrides.append({"item": item, "stop": stop, "stage": checkin.STOP_STAGE[stop], "pack": pack,
                              "adjudication": adj, "kind": kind_of(ev), "answer": answer})
    counts = audit.counts(ws)
    totals["rate"] = round(100 * totals["overrides"] / totals["answers"], 2) if totals["answers"] else 0.0
    return {"run": str(ws), "packs": list(run.get("packs") or []), "totals": totals, "overrides": overrides,
            "by_stage": _rates(by_stage), "by_stop": _rates(by_stop), "by_pack": _rates(by_pack),
            "by_adjudication": _rates(by_adj), "auto_answers": counts["auto_answers"],
            "delegations": counts["delegations"], "dig_deeper": counts["dig_deeper"]}


def _line(*cells) -> str:
    return "| " + " | ".join(str("" if c is None else c).replace("|", "/") for c in cells) + " |"


def _table(header: tuple, rows: list) -> list:
    return [_line(*header), "|" + "|".join("---" for _ in header) + "|"] + rows


def markdown(r: dict) -> str:
    t = r["totals"]
    lines = [f"## override rate: {r['run']}", "",
             f"{t['overrides']} overrides in {t['answers']} answers at the judgment stops ({t['rate']:g}%); "
             f"{r['auto_answers']} answers the tool took itself, {r['delegations']} delegated, "
             f"{r['dig_deeper']} dig-deeper requests. Packs: {', '.join(r['packs']) or 'none'}.", "",
             "### overrides", ""]
    if r["overrides"]:
        lines += _table(("item", "stop", "stage", "pack", "adjudication", "kind", "answer"), [
            _line(o["item"], o["stop"], o["stage"], o["pack"], o["adjudication"], o["kind"], o["answer"]) for o in r["overrides"]])
    else:
        lines.append("None.")
    for key, title in (("by_stage", "by stage"), ("by_stop", "by stop"), ("by_pack", "by pack"), ("by_adjudication", "by adjudication")):
        lines += ["", f"### {title}", ""] + _table((title[3:], "overrides", "answers", "rate"), [
            _line(k, v["overrides"], v["answers"], f"{v['rate']:g}%") for k, v in r[key].items()])
    return "\n".join(lines) + "\n"
