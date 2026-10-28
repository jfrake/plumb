"""Tokens and time a run used. While a run is active, plugin hooks record where each session's
and each agent's transcript is; Stage 7 reads the transcripts then and totals them.

Binding: a session is added to a run's bound sessions only by `bind_hook`,
fired from PostToolUse on the Bash tool when that session's own `plumb usage mark <ws>` call runs.
`record_hook` (SubagentStop/Stop) records only for sessions already in some run's list. This
replaces first-hook-wins binding, which let an unrelated session sharing the marked folder capture
the run, or a bound session get stolen by a newer run in the same folder (Task 4 review, Important
1 and 2).

Windows (final ruling I1): a run keeps every session it has bound, and each bind is also logged in
the run's own `usage/binds.jsonl`. At Stage 7 a session counts only inside its windows: from its
bind to the next bind by another session, and the last window to the report. A session that keeps
working after the run was resumed elsewhere adds nothing after that resume."""
from __future__ import annotations
import datetime
import json
import os
import re
import shlex
import tempfile
from pathlib import Path

USAGE_DIR = "usage"
HOOK_LOG = "hook_events.jsonl"
BIND_LOG = "binds.jsonl"
UNBOUND_TTL = datetime.timedelta(hours=24)
BOUND_TTL = datetime.timedelta(days=7)
ACTIVITY_REFRESH = datetime.timedelta(hours=1)


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds")


def _parse(ts: str):
    try:
        return datetime.datetime.fromisoformat(ts)
    except (TypeError, ValueError):
        return None


def active_path(home) -> Path:
    """Runs in progress that the usage hooks record for. Paths and ids only."""
    return Path(home) / ".config" / "plumb" / "active_runs.json"


def error_log(home) -> Path:
    return Path(home) / ".config" / "plumb" / "hook_errors.log"


def _log_error(home, line: str) -> None:
    log = error_log(home)
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as fh:
        fh.write(f"{_now()} record_usage: {line}\n")


def _quarantine(home, path: Path) -> None:
    """A corrupt active_runs.json is renamed once and never trusted again; the rename itself makes
    this happen only once, since the next read finds no file at `path`."""
    try:
        path.rename(path.with_name("active_runs.corrupt"))
    except OSError:
        pass
    _log_error(home, "active_runs.json was not valid JSON; quarantined to active_runs.corrupt")


def _expired(entry: dict, now_dt) -> bool:
    ts = _parse(entry.get("last_activity") or entry.get("marked") or "")
    if ts is None:
        return False
    ttl = BOUND_TTL if entry.get("sessions") else UNBOUND_TTL
    return (now_dt - ts) > ttl


def _valid_entry(e) -> bool:
    """A well-shaped active-run entry: this is what mark_active/bind_hook/record_hook write and
    assume, so anything else (a hand edit, disk damage, or the pre-fix f91ed38 `session_id` shape)
    is treated as corrupt rather than risking a crash on a missing key or the wrong type."""
    if not isinstance(e, dict):
        return False
    if not isinstance(e.get("workspace"), str) or not e["workspace"]:
        return False
    if e.get("cwd") is not None and not isinstance(e.get("cwd"), str):
        return False
    sessions = e.get("sessions")
    if not isinstance(sessions, list) or not all(isinstance(s, str) for s in sessions):
        return False
    for key in ("marked", "last_activity"):
        ts = e.get(key)
        if not isinstance(ts, str):
            return False
        dt = _parse(ts)
        if dt is None or dt.tzinfo is None:
            return False
    return True


def _read_active(home, now: str = "") -> list:
    """The active runs: a corrupt file (bad JSON, non-UTF-8 bytes, or a schema-invalid entry) is
    quarantined once and treated as empty; entries whose run folder is gone or whose expiry window
    has passed are pruned, and the prune is persisted so the fast path (no active-run file) comes
    back once nothing is left."""
    path = active_path(home)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    except UnicodeDecodeError:
        _quarantine(home, path)
        return []
    try:
        entries = json.loads(raw)
        if not isinstance(entries, list) or not all(_valid_entry(e) for e in entries):
            raise ValueError(f"{path} is not a valid active-runs list")
    except ValueError:
        _quarantine(home, path)
        return []
    now_dt = _parse(now) or datetime.datetime.now(datetime.timezone.utc)
    kept = [e for e in entries if Path(e["workspace"]).is_dir() and not _expired(e, now_dt)]
    if len(kept) != len(entries):
        _write_active(home, kept)
    return kept


def _write_active(home, entries: list) -> None:
    """Writes through a uniquely named temp file in the same directory (tempfile.mkstemp, not a
    fixed name), so concurrent writers never collide on `os.replace` and lose an update."""
    path = active_path(home)
    if not entries:
        if path.exists():
            path.unlink()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".active_runs.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(entries, indent=2))
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def mark_active(ws, cwd, home, now: str = "") -> dict:
    """Stage 0 and Resume: this run is (or remains) active. This only ensures the entry exists; a
    session is bound to it separately, by `bind_hook`, when this same call's `plumb usage mark`
    Bash command fires PostToolUse. A resume re-marks the same workspace and keeps its sessions
    already bound; marking always refreshes `marked` and `last_activity`, so resuming a run past
    its expiry window revives it before the next hook can prune it."""
    ws = str(Path(ws).resolve())
    now = now or _now()
    entries = _read_active(home, now=now)
    existing = next((e for e in entries if e["workspace"] == ws), None)
    sessions = list(existing["sessions"]) if existing else []
    entry = {"workspace": ws, "cwd": str(Path(cwd).resolve()) if cwd else None,
             "marked": now, "sessions": sessions, "last_activity": now}
    entries = [e for e in entries if e["workspace"] != ws]
    _write_active(home, entries + [entry])
    (Path(ws) / USAGE_DIR).mkdir(parents=True, exist_ok=True)
    return entry


def clear_active(ws, home, now: str = "") -> bool:
    """The run finished: the hooks stop recording for it."""
    entries = _read_active(home, now=now)
    ws = str(Path(ws).resolve())
    keep = [e for e in entries if e["workspace"] != ws]
    if len(keep) == len(entries):
        return False
    _write_active(home, keep)
    return True


def find_active(entries: list, session_id: str):
    """The run this session is bound to: the most recently marked entry whose bound sessions
    include it, or None. A session binds to at most one run in normal use; if a start-over left it
    bound to more than one, the newer run wins."""
    hits = [e for e in entries if session_id in (e.get("sessions") or [])]
    return max(hits, key=lambda e: e.get("marked") or "") if hits else None


def agent_transcript(transcript_path: str, session_id: str, agent_id: str) -> Path:
    """Where Claude Code writes a subagent's transcript, given the parent session's transcript."""
    return Path(transcript_path).parent / session_id / "subagents" / f"agent-{agent_id}.jsonl"


def description(transcript: Path) -> str:
    """The dispatch description from the subagent's meta file; empty until it is written."""
    meta = Path(transcript).with_name(Path(transcript).name[:-len(".jsonl")] + ".meta.json")
    try:
        d = json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    return str(d.get("description") or "") if isinstance(d, dict) else ""


_SEPARATOR_CHARS = set("();<>|&")


def _shell_tokens(command: str) -> list:
    """The command's words, with shell separators and redirections (`;`, `&&`, `||`, `|`, `>`)
    split off as their own tokens even when written without spaces (`mark /w; next`)."""
    lex = shlex.shlex(command, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    return list(lex)


def _mark_target(command: str):
    """The workspace argument of a `... usage mark <ws> [--cwd DIR]` shell command, wherever the
    positional falls among the options (argparse accepts either order), with `~` and `$VAR`
    expanded; or None if this command isn't a `plumb usage mark` call, or has no workspace before
    the next shell separator."""
    try:
        tokens = _shell_tokens(command)
    except ValueError:
        return None
    for i in range(len(tokens) - 1):
        if tokens[i] == "usage" and tokens[i + 1] == "mark":
            rest = tokens[i + 2:]
            j = 0
            while j < len(rest):
                tok = rest[j]
                if set(tok) <= _SEPARATOR_CHARS:
                    return None  # the mark command ended before any workspace
                if tok == "--cwd":
                    j += 2  # the option and its value
                    continue
                if tok.startswith("--cwd="):
                    j += 1
                    continue
                return os.path.expanduser(os.path.expandvars(tok))
            return None
    return None


_ENTRY_KEYS = {"workspace", "cwd", "marked", "sessions", "last_activity"}


def _is_mark_call(command: str) -> bool:
    """Whether the shell command contains a `usage mark` call at all, with or without a workspace
    the hook can read from the command text."""
    try:
        tokens = _shell_tokens(command)
    except ValueError:
        return False
    return any(a == "usage" and b == "mark" for a, b in zip(tokens, tokens[1:]))


def _printed_workspaces(payload: dict) -> list:
    """The workspaces `plumb usage mark` printed in this Bash call's output: each stdout line that
    is exactly the entry `mark_active` returns. The shell expanded these, so they cover a workspace
    the command names only through a variable set earlier in the same line (`W=... && plumb usage
    mark "$W"`), which the hook's own environment cannot expand."""
    resp = payload.get("tool_response")
    stdout = resp.get("stdout") if isinstance(resp, dict) else None
    out = []
    for line in str(stdout or "").splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if isinstance(d, dict) and set(d) == _ENTRY_KEYS and isinstance(d["workspace"], str):
            out.append(d["workspace"])
    return out


def bind_hook(payload: dict, home, now: str = ""):
    """PostToolUse on the Bash tool: when the command just run is this session's own
    `plumb usage mark <ws>`, add this session to that run's bound sessions and log the bind, with
    its time, in the run's `usage/binds.jsonl`. This is the only way a session is ever bound, so a
    run is never captured by an unrelated session that merely shares its folder, and a bound
    session is never stolen by a later run there. The workspace comes from the command text, or,
    when that names it through a variable the hook cannot expand, from the entry the mark call
    printed (see `_printed_workspaces`). Returns the updated
    entry, or None when this command didn't mark a run, or names a run that isn't active."""
    command = str((payload.get("tool_input") or {}).get("command") or "")
    if not _is_mark_call(command):
        return None
    session_id = str(payload.get("session_id") or "")
    if not session_id:
        return None
    now = now or _now()
    cwd = str(payload.get("cwd") or "")
    candidates = []
    target = _mark_target(command)
    if target is not None:
        target_path = Path(target)
        if not target_path.is_absolute() and cwd:
            target_path = Path(cwd) / target_path
        candidates.append(str(target_path.resolve()))
    candidates += [str(Path(w).resolve()) for w in _printed_workspaces(payload)]
    entries = _read_active(home, now=now)
    entry = next((e for ws in candidates for e in entries if e["workspace"] == ws), None)
    if entry is None:
        return None
    ws = entry["workspace"]
    if session_id not in entry["sessions"]:
        entry["sessions"].append(session_id)
    entry["last_activity"] = now
    _write_active(home, entries)
    out = Path(ws) / USAGE_DIR
    out.mkdir(exist_ok=True)
    rec = {"ts": now, "session_id": session_id, "transcript_path": str(payload.get("transcript_path") or ""),
           "cwd": cwd}
    with (out / BIND_LOG).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")
    return entry


def _refresh_activity(home, entries: list, entry: dict, now: str) -> None:
    """Best-effort: only rewrite active_runs.json when `last_activity` is more than an hour stale.
    record_hook must append the pointer unconditionally first (see below); this write is a courtesy
    for expiry tracking, not something a lost pointer should ever wait on or be lost to."""
    last = _parse(entry.get("last_activity") or "")
    now_dt = _parse(now)
    if last is not None and now_dt is not None and (now_dt - last) <= ACTIVITY_REFRESH:
        return
    entry["last_activity"] = now
    _write_active(home, entries)


def record_hook(payload: dict, home, now: str = ""):
    """SubagentStop and Stop: append a pointer to the active run's usage/hook_events.jsonl, for a
    session `bind_hook` already bound to that run. It records paths and ids only, because a
    transcript can lag the hook; Stage 7 reads them. The pointer is appended before
    active_runs.json is ever touched, and that refresh is best-effort (see `_refresh_activity`), so
    parallel SubagentStops for the same run never lose a pointer to a write race on the shared
    active-run file. Returns the pointer, or None when this session isn't bound to any active run."""
    if not active_path(home).exists():
        return None
    session_id = str(payload.get("session_id") or "")
    if not session_id:
        return None
    now = now or _now()
    entries = _read_active(home, now=now)
    entry = find_active(entries, session_id)
    if entry is None or not Path(entry["workspace"]).is_dir():
        return None
    parent = str(payload.get("transcript_path") or "")
    ptr = {"ts": now, "event": str(payload.get("hook_event_name") or ""), "session_id": session_id,
           "transcript_path": parent, "cwd": str(payload.get("cwd") or ""), "run_marked": entry.get("marked") or ""}
    if payload.get("agent_id"):
        agent_id = str(payload["agent_id"])
        path = agent_transcript(parent, session_id, agent_id) if parent else None
        ptr.update({"agent_id": agent_id, "agent_type": str(payload.get("agent_type") or ""),
                    "agent_transcript": str(path) if path else "",
                    "description": description(path) if path else ""})
    out = Path(entry["workspace"]) / USAGE_DIR
    out.mkdir(exist_ok=True)
    with (out / HOOK_LOG).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(ptr, sort_keys=True) + "\n")
    _refresh_activity(home, entries, entry, now)
    return ptr


# Reading the transcripts at Stage 7 and totaling them.

STAGE_LOG = "stages.jsonl"
REPORT = "usage.json"
PRICES = Path(__file__).with_name("prices.json")
NOT_MEASURED = "Usage not measured in this app."
NOT_RECORDED = "not recorded"
CODEX_MODEL = "codex (stress test)"
TOKENS = ("input", "output", "cache_write", "cache_read")
METHOD = ("Each API message is counted once, by its id, taking the largest value of each token field across the "
          "transcript lines that carry it. Each session counts inside its windows: from when it marked the run "
          "active to when another session marked it, and the last window to the report. Main-session messages "
          "and hook events count only inside the session's windows. A message belongs "
          "to the stage whose end, recorded by `plumb usage stage-end`, is the first at or after the message's "
          "time; a message after the last recorded end belongs to the next stage the run's depth runs. Stage time "
          "counts only while a session was working on the run: a window that another session closed ends at "
          "its session's last hook or message in it.")


def stage_end(ws, stage: int, now: str = "") -> dict:
    """After each stage's brief line: when the stage ended, so Stage 7 can total usage by stage."""
    rec = {"ts": now or _now(), "stage": int(stage)}
    out = Path(ws) / USAGE_DIR
    out.mkdir(parents=True, exist_ok=True)
    with (out / STAGE_LOG).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")
    return rec


def _ts(s):
    """An ISO timestamp as an aware UTC datetime, or None."""
    if not isinstance(s, str) or not s:
        return None
    s = s.replace("Z", "+00:00")
    for text in (s, re.sub(r"\.\d+", "", s)):
        try:
            d = datetime.datetime.fromisoformat(text)
        except ValueError:
            continue
        return d if d.tzinfo else d.replace(tzinfo=datetime.timezone.utc)
    return None


def _jsonl(path) -> list:
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def _read_transcript_safe(path, main_only: bool = False):
    """read_transcript, or None if the file cannot be decoded or opened: a transcript can be
    unreadable (permissions) or caught mid-write (a truncated multi-byte character at the end),
    since Stage 7 can read a live session's file while Claude Code is still appending to it. The
    report counts this as a missing transcript rather than crashing; it must never stop a run."""
    try:
        return read_transcript(path, main_only=main_only)
    except (OSError, UnicodeDecodeError):
        return None


def read_transcript(path, main_only: bool = False) -> tuple:
    """(messages, span). messages: {message id: {"model", "ts", "input", "output", "cache_write",
    "cache_write_1h", "cache_read"}}. One API message spans several lines that share its id; each
    field is the largest value across them, since early lines can hold streaming placeholders.
    main_only leaves out sidechain lines. span is (first, last) timestamp in the file, or None."""
    msgs, stamps = {}, []
    for row in _jsonl(path):
        t = _ts(row.get("timestamp"))
        if t:
            stamps.append(t)
        msg = row.get("message")
        if row.get("type") != "assistant" or not isinstance(msg, dict) or (main_only and row.get("isSidechain")):
            continue
        u, mid, model = msg.get("usage"), msg.get("id"), str(msg.get("model") or "")
        if not isinstance(u, dict) or not mid or model == "<synthetic>":
            continue
        cc = u.get("cache_creation") if isinstance(u.get("cache_creation"), dict) else {}
        vals = {"input": u.get("input_tokens"), "output": u.get("output_tokens"),
                "cache_write": u.get("cache_creation_input_tokens"), "cache_read": u.get("cache_read_input_tokens"),
                "cache_write_1h": cc.get("ephemeral_1h_input_tokens")}
        rec = msgs.setdefault(mid, {"model": model, "ts": row.get("timestamp") or "", "input": 0, "output": 0,
                                    "cache_write": 0, "cache_write_1h": 0, "cache_read": 0})
        for k, v in vals.items():
            if isinstance(v, int) and v > rec[k]:
                rec[k] = v
        if t and (not _ts(rec["ts"]) or t < _ts(rec["ts"])):
            rec["ts"] = row["timestamp"]
    return msgs, ((min(stamps), max(stamps)) if stamps else None)


def load_prices(path=None) -> dict:
    return json.loads(Path(path or PRICES).read_text(encoding="utf-8"))


_MODEL_ID = re.compile(r"^claude-([a-z]+)-(\d+)(?:-(\d{1,2}))?(?:-\d{8})?$")


def price_for(model: str, prices: dict):
    """The price-table entry for a model id (family and version), or None."""
    m = _MODEL_ID.match(model or "")
    if not m:
        return None
    version = m.group(2) + (f".{m.group(3)}" if m.group(3) else "")
    for p in prices.get("models", []):
        if p.get("family") == m.group(1) and str(p.get("version")) == version:
            return p
    return None


def cost(rec: dict, price):
    """API-equivalent dollars for one message at the table's per-million prices."""
    if price is None:
        return None
    w1h = min(rec.get("cache_write_1h", 0), rec["cache_write"])
    return (rec["input"] * price["input"] + rec["output"] * price["output"]
            + (rec["cache_write"] - w1h) * price["cache_write_5m"] + w1h * price["cache_write_1h"]
            + rec["cache_read"] * price["cache_read"]) / 1_000_000


def _stage_order(ws) -> list:
    try:
        run = json.loads((Path(ws) / "run.json").read_text(encoding="utf-8"))
        return [int(s) for s in run["limits"]["stages"]]
    except (OSError, ValueError, KeyError, TypeError):
        return list(range(8))


def _stage_ends(ws) -> list:
    p = Path(ws) / USAGE_DIR / STAGE_LOG
    ends = [(_ts(r.get("ts")), r.get("stage")) for r in (_jsonl(p) if p.exists() else [])]
    return sorted((t, int(s)) for t, s in ends if t is not None and isinstance(s, int))


def _next_stage(last: int, order: list) -> str:
    later = [s for s in order if s > last]
    return str(later[0]) if later else str(last)


def stage_of(t, ends: list, order: list) -> str:
    """The stage a message at time t belongs to: the first recorded end at or after t, else the
    stage after the last recorded end. "not recorded" when no stage end was recorded."""
    if not ends:
        return NOT_RECORDED
    for end, stage in ends:
        if t <= end:
            return str(stage)
    return _next_stage(ends[-1][1], order)


def _union(windows: list) -> list:
    out = []
    for a, b in sorted(windows):
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def _stage_seconds(ends: list, order: list, windows: list) -> dict:
    """Seconds each stage was worked on: its interval between recorded ends, within the sessions' windows."""
    if not ends:
        intervals = [(float("-inf"), float("inf"), NOT_RECORDED)]
    else:
        intervals, prev = [], float("-inf")
        for end, stage in ends:
            intervals.append((prev, end.timestamp(), str(stage)))
            prev = end.timestamp()
        intervals.append((prev, float("inf"), _next_stage(ends[-1][1], order)))
    out = {}
    for lo, hi, stage in intervals:
        for a, b in windows:
            overlap = min(hi, b.timestamp()) - max(lo, a.timestamp())
            if overlap > 0:
                out[stage] = out.get(stage, 0.0) + overlap
    return out


def _row() -> dict:
    return {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0, "seconds": 0.0,
            "cost_usd": 0.0, "cost_complete": True, "calls": 0}


def _add(table: dict, key: str, rec: dict, c, calls: int = 1) -> None:
    """Add one API message to a row. `calls` is 0 for the Codex total, which is not one message."""
    row = table.setdefault(key, _row())
    for k in TOKENS:
        row[k] += rec[k]
    row["calls"] += calls
    if c is None:
        row["cost_complete"] = False
    else:
        row["cost_usd"] += c


def _merge(into: dict, msgs: dict) -> None:
    for mid, rec in msgs.items():
        if mid not in into:
            into[mid] = rec
            continue
        for k in TOKENS + ("cache_write_1h",):
            into[mid][k] = max(into[mid][k], rec[k])


def _dominant(msgs) -> str:
    """The model that wrote most of an agent's output."""
    by = {}
    for rec in msgs:
        by[rec["model"]] = by.get(rec["model"], 0) + rec["output"] + 1
    return max(by, key=by.get) if by else ""


def _session_windows(binds: list, ptrs: list, now_t) -> tuple:
    """({session: [(start, end, open), ...]}, {session: transcript path}). Each bind opens a window
    for its session and closes the window of the session bound before it; the last window stays
    open to the report (`open` is True for it alone). A session with pointers but no logged bind
    (a run recorded before binds were logged) is treated as bound at the earliest `run_marked` of
    its pointers."""
    events, transcripts = [], {}
    for b in binds:
        t, sid = _ts(b.get("ts")), b.get("session_id")
        if isinstance(sid, str) and sid and t is not None:
            events.append((t, sid))
            transcripts[sid] = transcripts.get(sid) or str(b.get("transcript_path") or "")
    bound = {sid for _, sid in events}
    first = {}
    for p in ptrs:
        sid = p.get("session_id")
        t = _ts(p.get("run_marked")) or _ts(p.get("ts"))
        if isinstance(sid, str) and sid and sid not in bound and t is not None:
            first[sid] = min(first.get(sid, t), t)
    events += [(t, sid) for sid, t in first.items()]
    wins, owner = {}, None
    for t, sid in sorted(events):
        if sid == owner:
            continue
        if owner is not None:
            wins[owner][-1][1] = t
        wins.setdefault(sid, []).append([t, None, False])
        owner = sid
    if owner is not None:
        wins[owner][-1][1:] = [max(now_t, wins[owner][-1][0]), True]
    return {sid: [tuple(w) for w in ws_list] for sid, ws_list in wins.items()}, transcripts


def _inside(t, windows: list) -> bool:
    """Whether t falls in one of a session's windows. A window includes its start and excludes its
    end, where the next session's bind begins; the open window includes the report time."""
    if t is None:
        return False
    return any(a <= t < b or (is_open and t == b) for a, b, is_open in windows)


def _note(last: dict, sid: str, wins: dict, t) -> None:
    """Record t as activity in whichever of the session's windows holds it."""
    for i, (a, b, is_open) in enumerate(wins.get(sid) or []):
        if t is not None and (a <= t < b or (is_open and t == b)):
            last[(sid, i)] = max(last.get((sid, i), t), t)
            return


def report(ws, now: str = "", prices=None) -> dict:
    """Totals by stage and by model from the transcripts the hook pointed to."""
    ws = Path(ws)
    hook_log, bind_log = ws / USAGE_DIR / HOOK_LOG, ws / USAGE_DIR / BIND_LOG
    if not hook_log.exists() and not bind_log.exists():
        return {"measured": False, "reason": NOT_MEASURED}
    prices = load_prices() if prices is None else prices
    now_t = _ts(now) or datetime.datetime.now(datetime.timezone.utc)
    ptrs = _jsonl(hook_log) if hook_log.exists() else []
    binds = _jsonl(bind_log) if bind_log.exists() else []
    wins, transcripts = _session_windows(binds, ptrs, now_t)
    ptrs = [p for p in ptrs if _inside(_ts(p.get("ts")), wins.get(p.get("session_id")) or [])]
    for p in ptrs:
        transcripts[p["session_id"]] = p.get("transcript_path") or transcripts.get(p["session_id"], "")
    last = {}  # (session, window index) -> its last activity inside that window
    for p in ptrs:
        _note(last, p["session_id"], wins, _ts(p.get("ts")))
    messages, agent_time, missing, main_msgs = {}, [], 0, {}
    for sid in wins:
        path = Path(transcripts[sid]) if transcripts.get(sid) else None
        if path is None or not path.is_file():
            missing += 1
            continue
        got = _read_transcript_safe(path, main_only=True)
        if got is None:
            missing += 1
            continue
        msgs, _ = got
        inside = {mid: r for mid, r in msgs.items() if _inside(_ts(r["ts"]), wins[sid])}
        for r in inside.values():
            _note(last, sid, wins, _ts(r["ts"]))
        _merge(messages, inside)
        main_msgs[sid] = inside
    active = []  # (session, start, end): the time each session worked on the run
    for sid, ws_list in wins.items():
        for i, (a, b, is_open) in enumerate(ws_list):
            end = b if is_open else max(a, min(b, last.get((sid, i), a)))
            active.append((sid, a, end))
    for sid, inside in main_msgs.items():
        if inside:
            secs = sum((b - a).total_seconds() for s2, a, b in active if s2 == sid)
            agent_time.append((secs, _dominant(inside.values())))
    seen = set()
    for p in ptrs:
        aid = p.get("agent_id")
        if not aid or aid in seen:
            continue
        path = Path(p.get("agent_transcript") or agent_transcript(p.get("transcript_path") or "",
                                                                  p.get("session_id") or "", aid))
        # Claude Code's own background helpers stop with no agent type and leave no transcript.
        # They are not the run's agents, so they count neither as agents nor as missing.
        if not p.get("agent_type") and not path.is_file():
            continue
        seen.add(aid)
        if not path.is_file():
            missing += 1
            continue
        got = _read_transcript_safe(path)
        if got is None:
            missing += 1
            continue
        msgs, span = got
        _merge(messages, msgs)
        if span and msgs:
            agent_time.append(((span[1] - span[0]).total_seconds(), _dominant(msgs.values())))
    ends, order = _stage_ends(ws), _stage_order(ws)
    by_stage, by_model, unpriced = {}, {}, set()
    for rec in messages.values():
        t = _ts(rec["ts"])
        stage = stage_of(t, ends, order) if t else NOT_RECORDED
        price = price_for(rec["model"], prices)
        if price is None:
            unpriced.add(rec["model"] or "unknown")
        c = cost(rec, price)
        _add(by_stage, stage, rec, c)
        _add(by_model, rec["model"] or "unknown", rec, c)
    codex = None
    cpath = ws / "stage-6" / "stress_test" / "usage.json"
    if cpath.is_file():
        try:
            cu = json.loads(cpath.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError):
            cu = {}
        available = bool(isinstance(cu, dict) and cu.get("available"))
        rec = None
        if available:
            tot = cu.get("total")
            if isinstance(tot, dict):
                try:
                    cached = int(tot.get("cached_input_tokens") or 0)
                    rec = {"input": max(int(tot.get("input_tokens") or 0) - cached, 0),
                           "output": int(tot.get("output_tokens") or 0), "cache_write": 0, "cache_read": cached}
                except (TypeError, ValueError):
                    rec = None
        codex = {"available": available and rec is not None}
        if codex["available"]:
            _add(by_stage, "6", rec, None, calls=0)
            _add(by_model, CODEX_MODEL, rec, None, calls=0)
            unpriced.add(CODEX_MODEL)
            try:
                secs = float(cu.get("elapsed_seconds") or 0)
            except (TypeError, ValueError):
                secs = 0.0
            agent_time.append((secs, CODEX_MODEL))
    windows = _union([(a, b) for _, a, b in active])
    for stage, secs in _stage_seconds(ends, order, windows).items():
        by_stage.setdefault(stage, _row())["seconds"] = secs
    for secs, model in agent_time:
        if model in by_model:
            by_model[model]["seconds"] += secs
    total = _row()
    for row in by_model.values():
        for k in TOKENS + ("calls",):
            total[k] += row[k]
        total["cost_usd"] += row["cost_usd"]
        total["cost_complete"] = total["cost_complete"] and row["cost_complete"]
    total["seconds"] = sum((b - a).total_seconds() for a, b in windows)
    return {"measured": True, "method": METHOD,
            "price_table": {"as_of": prices.get("as_of", ""), "source": prices.get("source", "")},
            "sessions": len(wins), "agents": len(seen), "missing_transcripts": missing, "codex": codex,
            "unpriced_models": sorted(unpriced),
            "by_stage": [dict(stage=k, **by_stage[k]) for k in sorted(by_stage, key=_stage_key)],
            "by_model": [dict(model=k, **by_model[k]) for k in sorted(by_model)],
            "total": total}


def _stage_key(k: str) -> tuple:
    return (k == NOT_RECORDED, int(k) if k.isdigit() else 0)


def write_report(ws, now: str = "", prices=None) -> dict:
    rep = report(ws, now, prices)
    (Path(ws) / REPORT).write_text(json.dumps(rep, indent=2), encoding="utf-8")
    return rep


def load_report(ws) -> dict:
    """The report Stage 7 wrote, or a not-measured report for a run that has none."""
    try:
        rep = json.loads((Path(ws) / REPORT).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"measured": False, "reason": "Usage was not recorded for this run."}
    return rep if isinstance(rep, dict) else {"measured": False, "reason": "Usage was not recorded for this run."}


# The model record: the version record an evaluation can cite.

MODELS = "models.json"
ROLE_ORDER = ("mechanical", "judgment")
STRESS_ROLE = "stress_test"
CALLS_NOTE = "Call counts are per id over every transcript, the main session included."
NO_TRANSCRIPTS = "Usage was measured but no transcript could be read"


def _configured_models(ws) -> dict:
    """The `models` block Stage 0 wrote into run.json: each role's configured name (a tier alias,
    a full model id, or inherit), in role order."""
    try:
        run = json.loads((Path(ws) / "run.json").read_text(encoding="utf-8"))
        raw = run.get("models") if isinstance(run, dict) else None
    except (OSError, ValueError):
        raw = None
    if not isinstance(raw, dict):
        return {}
    out = {r: str(raw[r]) for r in ROLE_ORDER if isinstance(raw.get(r), str) and raw[r]}
    out.update({r: str(v) for r, v in raw.items() if r not in out and isinstance(v, str) and v})
    return out


def _family(model_id: str) -> str:
    m = _MODEL_ID.match(model_id or "")
    return m.group(1) if m else ""


def model_record(ws) -> dict:
    """Which models ran, from usage.json's `by_model` when the platform measured usage: each model
    id observed in the transcripts, the roles whose configured name is that id or its tier alias,
    and its call count. A name that matches more than one id (two versions of one family, or
    `inherit` with several models) leaves its role unresolved, with the ids under `candidates`.
    Without measured usage (the Claude chat tab, Codex) the record lists the configured names and
    says they are aliases, not observed ids."""
    ws = Path(ws)
    configured = _configured_models(ws)
    rep = load_report(ws)
    rows = [r for r in (rep.get("by_model") or []) if isinstance(r, dict) and r.get("model")] \
        if rep.get("measured") else []
    if rows:
        ids = [str(r["model"]) for r in rows]
        ran = [i for i in ids if i != CODEX_MODEL]
        roles_of = {i: [] for i in ids}
        unresolved, candidates = [], {}
        for role, name in configured.items():
            # Every id the configured name could mean: the id itself, every id of that family for a
            # tier alias, or every id that ran for inherit (the session's model). One match resolves
            # the role; more than one is ambiguous and is recorded as such, never picked silently.
            hits = [i for i in ran if name == i or name == _family(i)]
            if not hits and name == "inherit":
                hits = list(ran)
            if len(hits) == 1:
                roles_of[hits[0]].append(role)
            else:
                unresolved.append(role)
                if hits:
                    candidates[role] = hits
        if CODEX_MODEL in roles_of:
            roles_of[CODEX_MODEL].append(STRESS_ROLE)
        models = []
        for r in rows:
            i = str(r["model"])
            calls = r.get("calls")
            models.append({"id": i, "roles": roles_of[i],
                           "calls": None if i == CODEX_MODEL or not isinstance(calls, int) else calls})
        note = (f"Model ids observed in the transcripts after the run. {CALLS_NOTE} The work each did was "
                "configured by name (see configured), mostly by tier alias, so the same settings can resolve "
                "to a different id on another day.")
        if candidates:
            note += (" A name under unresolved_roles matched more than one id that ran, listed under "
                     "candidates, so the record cannot say which id did that work.")
        if [r for r in unresolved if r not in candidates]:
            note += " A name under unresolved_roles with no candidates matched no id that ran."
        return {"observed": True, "source": REPORT, "configured": configured, "models": models,
                "unresolved_roles": unresolved, "candidates": candidates, "note": note}
    by_name = {}
    for role, name in configured.items():
        by_name.setdefault(name, []).append(role)
    models = [{"id": name, "roles": roles, "calls": None} for name, roles in sorted(by_name.items())]
    why = NO_TRANSCRIPTS if rep.get("measured") else "Usage was not measured in this app"
    if configured:
        note = f"These are the configured names, mostly tier aliases, not observed ids. {why}, so the model ids that ran are not recorded."
    else:
        note = f"No models were configured for this run. {why}, so the models are not recorded."
    return {"observed": False, "source": "run.json", "configured": configured, "models": models,
            "unresolved_roles": [], "candidates": {}, "note": note}


def write_model_record(ws) -> dict:
    rec = model_record(ws)
    (Path(ws) / MODELS).write_text(json.dumps(rec, indent=2), encoding="utf-8")
    return rec


def render_models(rec: dict) -> str:
    """The audit package's "Models" line."""
    def item(m):
        roles = ", ".join(m["roles"]) or "no configured name matched"
        return f"{m['id']}: {roles}" + (f", {m['calls']} calls" if isinstance(m["calls"], int) else "")
    if rec["observed"]:
        line = ("- Models that ran (ids observed in the transcripts): " + "; ".join(item(m) for m in rec["models"])
                + f". {CALLS_NOTE} The work each did was configured by name, mostly by tier alias; the same "
                "settings can resolve to a different id on another day.")
        for role in rec["unresolved_roles"]:
            hits = rec.get("candidates", {}).get(role)
            line += (f" Could not say which id did the {role} work: {role}: {' or '.join(hits)}." if hits
                     else f" No id that ran matched the configured name for the {role} work.")
        return line
    if not rec["models"]:
        return "- Models: not recorded. " + rec["note"]
    why = NO_TRANSCRIPTS if NO_TRANSCRIPTS in rec["note"] else "Usage was not measured in this app"
    return ("- Models: " + "; ".join(item(m) for m in rec["models"]) + ". These are the configured names from the "
            f"run's settings, mostly tier aliases, not observed ids; {why[0].lower() + why[1:]}, so the ids that "
            "ran are not recorded.")


def _duration(seconds: float) -> str:
    s = int(round(seconds))
    h, rest = divmod(s, 3600)
    m, sec = divmod(rest, 60)
    if h:
        return f"{h}h {m:02d}m {sec:02d}s"
    return f"{m}m {sec:02d}s" if m else f"{sec}s"


def _money(row: dict) -> str:
    if not row["cost_complete"] and row["cost_usd"] == 0:
        return "not priced"
    text = f"${row['cost_usd']:,.2f}"
    return text if row["cost_complete"] else f"{text} (partial)"


def _cells(row: dict) -> str:
    return " | ".join([f"{row[k]:,}" for k in TOKENS] + [_duration(row["seconds"]), _money(row)])


def render(rep: dict) -> list:
    """The "## Usage" section of the audit package and the run folder's README, as lines."""
    lines = ["## Usage", ""]
    if not rep.get("measured"):
        return lines + [rep.get("reason") or NOT_MEASURED, ""]
    head = "| Input | Output | Cache write | Cache read | {} | API-equivalent cost |"
    rule = "|---|---:|---:|---:|---:|---:|---:|"
    lines += [f"Tokens and time this run used. The cost is API-equivalent: what these tokens would cost at the "
              f"list prices in Plumb's price table dated {rep['price_table']['as_of']}. On a subscription plan "
              "it is not what you pay.", "",
              "### By stage", "", "| Stage " + head.format("Time"), rule]
    for row in rep["by_stage"]:
        label = "Not recorded" if row["stage"] == NOT_RECORDED else f"Stage {row['stage']}"
        lines.append(f"| {label} | {_cells(row)} |")
    lines += [f"| Total | {_cells(rep['total'])} |", "", "### By model", "", "| Model " + head.format("Agent time"), rule]
    lines += [f"| {row['model']} | {_cells(row)} |" for row in rep["by_model"]]
    lines += ["", f"Counted from {rep['sessions']} main session(s) and {rep['agents']} agent(s). Stage time counts "
              "only while a session was working on the run, check-ins included. Agent time adds up each agent's "
              "own time, so agents that ran at once each count in full.",
              "This does not measure usage in the Claude chat tab. It only counts sessions and agents run "
              "through this tool.",
              "If a resumed session keeps its old session id, the time above can include the idle gap between "
              "when you stopped and when you resumed."]
    if rep["missing_transcripts"]:
        lines.append(f"{rep['missing_transcripts']} transcript(s) could not be read, so their tokens are not counted.")
    if rep.get("codex") and not rep["codex"]["available"]:
        lines.append("Codex ran the stress test but reported no token counts, so its tokens are not counted.")
    if rep["unpriced_models"]:
        lines.append(f"No price in the table for: {', '.join(rep['unpriced_models'])}. "
                     "Their tokens are counted but not priced.")
    return lines + [""]
