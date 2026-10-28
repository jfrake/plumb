"""What a run shows the user, and where the rest goes. The chat gets stage headers, findings, stage
results, and one scoreboard at the end; every other step goes to the run log."""
from __future__ import annotations
import datetime
import json
import re
from pathlib import Path

from . import consent, profiles, rundir, stress
from . import depth as _depth

RUN_LOG = "run_log.md"
STAGE_NAMES = ("Intake", "Verify", "Understand", "Theory", "Diagnose", "Synthesize", "Audit", "Output")
ESTIMATES = Path(__file__).with_name("estimates.json")
DEPTH_LABELS = {"quick": "Quick", "standard": "Standard", "deep": "Deep"}


def log_line(ws, line: str, now=None) -> str:
    """Append one timestamped line to `<workspace>/run_log.md` and return it. Whitespace in the
    line, newlines included, collapses to single spaces, so each entry stays on one line."""
    ws = Path(ws)
    text = " ".join(str(line).split())
    if not text:
        raise ValueError("A run-log line needs some text.")
    if not ws.is_dir():
        raise ValueError(f"{ws} is not a run's workspace folder.")
    when = (now or datetime.datetime.now(datetime.timezone.utc)).astimezone(datetime.timezone.utc)
    entry = f"- {when.strftime('%Y-%m-%dT%H:%M:%SZ')} {text}"
    path = ws / RUN_LOG
    head = "" if path.exists() else "# Run log\n\n"
    with path.open("a", encoding="utf-8") as f:
        f.write(head + entry + "\n")
    return entry


def estimates(path=None) -> dict:
    """The time-estimate table: minutes per stage and depth, as [low, high]."""
    return json.loads(Path(path or ESTIMATES).read_text(encoding="utf-8"))


def _minutes(depth_name: str, stage: int, table=None, packs: int = 0) -> tuple:
    """Minutes for a stage at a depth, plus the per-pack increment for each pack the run uses."""
    d = _depth.normalize(str(depth_name).lower())
    if stage not in _depth.STAGES[d]:
        raise ValueError(f"Stage {stage} does not run at {DEPTH_LABELS[d]} depth.")
    table = table or estimates()
    lo, hi = table["minutes"][d][str(stage)]
    plo, phi = (table.get("per_pack") or {}).get(str(stage), (0, 0))
    return int(lo) + packs * int(plo), int(hi) + packs * int(phi)


# Stage 0 starts before the depth is chosen; its header then carries no estimate.
NO_DEPTH = "none"


def _no_depth(depth_name: str, stage: int) -> bool:
    if str(depth_name).lower() != NO_DEPTH:
        return False
    if stage != 0:
        raise ValueError("Only Stage 0 runs before the depth is chosen.")
    return True


def stage_header(depth_name: str, stage: int, table=None, packs: int = 0) -> str:
    """The line the chat shows when a stage starts. At a depth that skips stages it also counts
    the stages that run."""
    if _no_depth(depth_name, stage):
        return f"Stage 0 of {len(STAGE_NAMES)}: {STAGE_NAMES[0]}."
    lo, hi = _minutes(depth_name, stage, table, packs)
    d = _depth.normalize(str(depth_name).lower())
    runs = list(_depth.STAGES[d])
    count = "" if len(runs) == len(STAGE_NAMES) else \
        f" (stage {runs.index(stage) + 1} of {len(runs)} at {DEPTH_LABELS[d]} depth)"
    return (f"Stage {stage} of {len(STAGE_NAMES)}: {STAGE_NAMES[stage]}{count}, "
            f"about {lo} to {hi} minutes (estimate).")


def time_left(depth_name: str, stage: int, table=None, packs: int = 0) -> str:
    """The total for this stage and every later stage that runs at this depth."""
    if _no_depth(depth_name, stage):
        return ""
    _minutes(depth_name, stage, table)
    d = _depth.normalize(str(depth_name).lower())
    spans = [_minutes(d, s, table, packs) for s in _depth.STAGES[d] if s >= stage]
    return f"About {sum(s[0] for s in spans)} to {sum(s[1] for s in spans)} minutes left (estimate)"


_ROW = re.compile(r"^Scoreboard (\d): (.*)$")
FLAG_KINDS = ("cell", "table", "number", "reference")


def _plural(n: int, noun: str) -> str:
    return f"{n} {noun}" + ("" if n == 1 else "s")


def _found_from_files(ws: Path) -> dict:
    """Found for Stage 1 (every record in flags.json, by kind) and Stage 4 (every card in
    questions.json that an earlier answer has not pruned), where those files exist."""
    from . import audit, checkin
    out = {}
    flags = ws / "stage-1" / "flags.json"
    if flags.exists():
        try:
            kinds = [str(r.get("kind")) for r in json.loads(flags.read_text(encoding="utf-8"))]
        except (ValueError, AttributeError, TypeError):
            kinds = None
        if kinds is not None:
            order = list(FLAG_KINDS) + sorted(set(kinds) - set(FLAG_KINDS))
            out[1] = ", ".join(_plural(kinds.count(k), f"{k} flag") for k in order if k in kinds) or "No flags"
    qs = ws / "stage-4" / "questions.json"
    if qs.exists():
        try:
            cards = json.loads(qs.read_text(encoding="utf-8"))
            given = {e["item"]: checkin.letter(e["answer"]) for e in audit.read_events(ws)
                     if e["kind"] == "checkin"}
            out[4] = _plural(sum(1 for q in cards if not checkin.is_pruned(q, given)), "major issue")
        except (ValueError, AttributeError, TypeError, KeyError):
            pass
    return out


def scoreboard(ws) -> str:
    """The end-of-run table, one row per stage, from the `Scoreboard <N>: <status> | <found> |
    <needs you>` lines in brief.md. The last line for a stage wins, so a rerun stage shows its
    rerun. A stage the depth skips says so; a stage with no line is "Not recorded"."""
    ws = Path(ws)
    run_path = ws / "run.json"
    run = json.loads(run_path.read_text(encoding="utf-8")) if run_path.exists() else {}
    try:
        d = _depth.from_run(run)
    except ValueError:
        d = "standard"
    rows = {}
    brief = ws / "brief.md"
    for line in (brief.read_text(encoding="utf-8").splitlines() if brief.exists() else []):
        m = _ROW.match(line.strip())
        if m:
            cells = [c.strip() for c in m.group(2).split("|")]
            cells = cells[:2] + [" ".join(cells[2:])] if len(cells) > 3 else (cells + ["", ""])[:3]
            rows[int(m.group(1))] = cells
    found = _found_from_files(ws)
    out = ["| Stage | Status | Found | Needs you |", "|---|---|---|---|"]
    for n, name in enumerate(STAGE_NAMES):
        if n not in _depth.STAGES[d]:
            cells = [f"Not run at {DEPTH_LABELS[d]} depth", "", ""]
        else:
            cells = list(rows.get(n, ["Not recorded", "", ""]))
            if n in found and n in rows:
                cells[1] = found[n]
        out.append(f"| {n} {name} | " + " | ".join(cells) + " |")
    return "\n".join(out)


OUTPUT_NAMES = {"issues_list": "Issues list", "annotated_pdf": "Annotated PDF", "report": "Mock referee report",
                "editor_memo": "Checked-facts memo for an editor"}
STRESS_NAMES = {"codex": "Codex, which sends the paper to OpenAI", "claude": "A fresh Claude agent",
                "": "None at Quick depth"}
NOT_SET = "Not recorded yet"


def _provider_terms(name: str, trains, days) -> str:
    t = {True: "trains on inputs", False: "does not train on inputs"}.get(trains, "training not recorded")
    if days is None:
        k = "retention not recorded"
    elif days == 0:
        k = "keeps nothing"
    else:
        k = f"keeps inputs {days} day{'' if days == 1 else 's'}"
    return f"{name}, {t}, {k}"


def _given(facts, name: str) -> str:
    f = (facts or {}).get(name) or {}
    return f" (your answer of {f['given']})" if f.get("given") else ""


def _terms(rec, facts=None) -> str:
    """`facts` is the config's saved provider answers; their dates show, so a stale answer is visible."""
    if rec is None:
        return NOT_SET
    out = [_provider_terms(rec.provider, rec.provider_trains_on_inputs, rec.retention_days) + _given(facts, "anthropic")]
    extra = rec.stress_test_provider or {}
    if extra:
        out.append(_provider_terms(extra.get("provider") or "OpenAI", extra.get("trains_on_inputs"),
                                   extra.get("retention_days")) + " (stress test)" + _given(facts, "openai"))
    return "; ".join(out)


def recap(ws, profiles_dir=None, codex_enabled: bool = False, codex_on_path: bool = False,
          facts=None) -> str:
    """The table shown after the consent check, before anything reads the paper: permission, journal, depth, check-in level,
    outputs, stress test, provider and retention, and output folder. The stress test is the one
    `stress.decide` would pick now; Stage 6 decides again when it runs. Logs nothing."""
    ws = Path(ws)
    run_path = ws / "run.json"
    if not run_path.exists():
        raise ValueError(f"{run_path} is missing.")
    run = json.loads(run_path.read_text(encoding="utf-8"))
    d = _depth.from_run(run)
    journal = run.get("journal") or ""
    if journal and profiles_dir:
        try:
            journal = profiles.load_profile(profiles_dir, journal).name
        except ValueError:
            pass
    rec = None
    cpath = ws / "consent.json"
    if cpath.exists():
        try:
            rec = consent.from_dict(json.loads(cpath.read_text(encoding="utf-8")))
        except (consent.ConsentError, ValueError, AttributeError):
            rec = None
    engine, _ = stress.decide(d, codex_enabled, codex_on_path, rec,
                              profiles.run_needs_zero_retention(run, rec, profiles_dir))
    outputs = ", ".join(OUTPUT_NAMES.get(o, o) for o in run.get("outputs") or []) or NOT_SET
    if outputs != NOT_SET and run.get("issues_list_mode") == "facts_only":
        outputs += " (checked facts only)"
    rows = [
        ("Permission", rundir.PERMISSION_NAMES.get(run.get("permission") or "", NOT_SET)),
        ("Journal", journal or NOT_SET),
        ("Depth", DEPTH_LABELS[d]),
        ("Check-in level", rundir.LEVEL_NAMES.get(run.get("level") or "", NOT_SET)),
        ("Outputs", outputs),
        ("Stress test", STRESS_NAMES[engine]),
        ("Provider and retention", _terms(rec, facts)),
        ("Output folder", str(ws.parent)),
    ]
    rows.append(("Search date cap", str(run["search_before"]) if run.get("search_before") else "None"))
    return "\n".join(["| Setting | Your answer |", "|---|---|"] + [f"| {k} | {v} |" for k, v in rows])
