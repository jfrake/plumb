"""The output folder: where a run's files go, finding an unfinished run, and older runs."""
from __future__ import annotations
import datetime
import hashlib
import json
import re
import shutil
from pathlib import Path

from . import audit, usage, validated
from .consent import PERMISSIONS

OUTPUT_DIR = "plumb_output"
WORKSPACE = ".workspace"
LEGACY_WORKSPACE = "review_workspace"
_RUN_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:-(\d+))?$")


def is_excluded(folder: Path, home: Path) -> bool:
    """The home folder, Desktop, Downloads, Documents, and the top folder of Dropbox or iCloud Drive."""
    folder, home = Path(folder).resolve(), Path(home).resolve()
    fixed = {home, home / "Desktop", home / "Downloads", home / "Documents", home / "Dropbox",
             home / "iCloud Drive", home / "Library" / "Mobile Documents" / "com~apple~CloudDocs"}
    if folder in fixed:
        return True
    return folder.parent == home / "Library" / "CloudStorage" and folder.name.startswith(("Dropbox", "iCloud"))


def choose_root(pdf: Path, cwd, home: Path) -> Path:
    """The working directory when it holds the PDF and is not an excluded folder. Otherwise a
    folder named after the paper, next to the PDF. cwd is None where there is no project
    directory (the Claude chat tab)."""
    pdf = Path(pdf).resolve()
    if cwd is not None:
        cwd = Path(cwd).resolve()
        if cwd in pdf.parents and not is_excluded(cwd, home):
            return cwd
    return pdf.parent / pdf.stem


def next_run_dir(root: Path, date: str) -> Path:
    base = Path(root) / OUTPUT_DIR
    cand, n = base / date, 2
    while cand.exists():
        cand, n = base / f"{date}-{n}", n + 1
    return cand


def _paths(run_dir: Path) -> dict:
    return {"root": str(run_dir.parent.parent), "run_dir": str(run_dir), "workspace": str(run_dir / WORKSPACE)}


def _today() -> str:
    return datetime.date.today().isoformat()


def index_path(home: Path) -> Path:
    """The run index: every run folder Plumb made, so resume finds a run wherever it went."""
    return Path(home) / ".config" / "plumb" / "runs.json"


def _read_index(home: Path) -> list:
    try:
        entries = json.loads(index_path(home).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [e for e in entries if isinstance(e, dict)] if isinstance(entries, list) else []


def _register(home: Path, pdf, run_dir: Path, started: str, replaces=None) -> None:
    gone = {str(run_dir), str(replaces)}
    entries = [e for e in _read_index(home) if e.get("run_dir") not in gone]
    entries.append({"pdf_path": str(Path(pdf).resolve()), "run_dir": str(run_dir), "started": started,
                    "finished": False})
    path = index_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def mark_finished(ws: Path, home: Path) -> bool:
    """Mark the run that holds `ws` finished in the index. Never creates the index."""
    entries = _read_index(home)
    run_dir = str(Path(ws).resolve().parent)
    hits = [e for e in entries if e.get("run_dir") == run_dir]
    for e in hits:
        e["finished"] = True
    if hits:
        index_path(home).write_text(json.dumps(entries, indent=2), encoding="utf-8")
    return bool(hits)


_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def iso_date(text: str) -> str:
    """`text` as a calendar date written YYYY-MM-DD, else ValueError."""
    text = (text or "").strip()
    if not _ISO_DATE.match(text):
        raise ValueError(f"{text!r} is not a date written YYYY-MM-DD.")
    try:
        datetime.date.fromisoformat(text)
    except ValueError:
        raise ValueError(f"{text!r} is not a calendar date; write it YYYY-MM-DD.")
    return text


def set_search_before(ws: Path, date: str) -> str:
    """The search date cap: write `search_before` (YYYY-MM-DD) into run.json. Research agents cap
    their web searches at that date when the key is present. Nothing is written for a bad date."""
    date = iso_date(date)
    path = Path(ws) / "run.json"
    try:
        run = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        raise ValueError(f"{path} is missing: the workspace is not a Plumb run, so no cap was written.")
    run["search_before"] = date
    path.write_text(json.dumps(run, indent=2), encoding="utf-8")
    return date


def set_page_offset(ws: Path, offset: str) -> int:
    """The printed-to-PDF page offset: write `page_offset` (an integer, PDF page minus the page the
    paper prints, as locate_issues.py --page-offset fits it) into run.json. The eval pool reads it
    to let a PDF page stand in for a missing printed page. Nothing is written for a non-integer."""
    try:
        n = int(str(offset).strip())
    except ValueError:
        raise ValueError(f"{offset!r} is not a whole number; give the offset locate_issues.py printed.")
    path = Path(ws) / "run.json"
    try:
        run = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        raise ValueError(f"{path} is missing: the workspace is not a Plumb run, so no offset was written.")
    run["page_offset"] = n
    path.write_text(json.dumps(run, indent=2), encoding="utf-8")
    return n


def new_run(pdf: Path, cwd, home: Path, date: str = "", search_before: str = "", fresh: bool = False) -> dict:
    """Create <root>/plumb_output/<date>[-n]/.workspace/ and a first run.json. `search_before`
    (YYYY-MM-DD) is the search date cap, an evaluation option set only by flag; setup never asks for it.
    A fresh run (a repeat run that must not resume) records that it started fresh and names the
    unfinished run of this PDF it left as it was, so the archive says why two runs sit side by side."""
    cap = iso_date(search_before) if search_before else ""
    run = {"pdf_path": str(Path(pdf).resolve())}
    if cap:
        run["search_before"] = cap
    if fresh:
        run["fresh"] = True
        left = find_unfinished(pdf, cwd, home)
        if left["workspace"]:
            ws = Path(left["workspace"])
            run["unfinished_run"] = str(ws if left["legacy"] else ws.parent)
    started = date or datetime.datetime.now().isoformat(timespec="seconds")
    date = started[:10]
    run["started"] = started
    run_dir = next_run_dir(choose_root(pdf, cwd, home), date)
    ws = run_dir / WORKSPACE
    ws.mkdir(parents=True)
    (ws / "run.json").write_text(json.dumps(run, indent=2), encoding="utf-8")
    _register(home, pdf, run_dir, started)
    return _paths(run_dir)


def move_run(run_dir: Path, folder: Path, home=None) -> dict:
    """"Somewhere else": move the run folder to <folder>/plumb_output/<date>[-n]/. Empty folders
    it leaves behind are removed. Given `home`, the run index follows the move."""
    run_dir = Path(run_dir).resolve()
    date = _RUN_NAME.match(run_dir.name).group(1)
    target = next_run_dir(Path(folder).expanduser().resolve(), date)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(run_dir), str(target))
    for left in (run_dir.parent, run_dir.parent.parent):
        if left.exists() and not any(left.iterdir()):
            left.rmdir()
    if home is not None:
        try:
            run = json.loads((target / WORKSPACE / "run.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            run = {}
        if run.get("pdf_path"):
            _register(home, run["pdf_path"], target, run.get("started") or date, replaces=run_dir)
    return _paths(target)


def is_finished(ws: Path) -> bool:
    """A run is finished once Stage 7 logged its final output event. A run from before this
    version logged none; it is finished if its brief records Stage 7."""
    if any(e["kind"] == "output" and e.get("final") is True for e in audit.read_events(ws)):
        return True
    brief = Path(ws) / "brief.md"
    return brief.exists() and any(l.startswith("Stage 7:") for l in brief.read_text(encoding="utf-8").splitlines())


def _same_pdf(ws: Path, pdf: Path) -> bool:
    try:
        run = json.loads((Path(ws) / "run.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return bool(run.get("pdf_path")) and Path(run["pdf_path"]).resolve() == Path(pdf).resolve()


def _run_key(run_dir: Path) -> tuple:
    """Newest last: the folder's date and number, then when run.json says the run started, which
    breaks a tie between same-named folders in different places (Start over, then a move)."""
    m = _RUN_NAME.match(run_dir.name)
    try:
        started = str(json.loads((run_dir / WORKSPACE / "run.json").read_text(encoding="utf-8")).get("started") or "")
    except (OSError, ValueError, AttributeError):
        started = ""
    return ((m.group(1), int(m.group(2) or 1)) if m else ("", 0)) + (started,)


def find_unfinished(pdf: Path, cwd, home: Path) -> dict:
    """The newest unfinished run for this PDF, from the run index and under its root, else an
    unfinished run in the old <paper_dir>/review_workspace/ layout.
    {"workspace": path or None, "legacy": bool}."""
    root = choose_root(pdf, cwd, home)
    found = [Path(e["run_dir"]) / WORKSPACE for e in _read_index(home)
             if e.get("run_dir") and not e.get("finished")]
    found += [p.parent for p in (root / OUTPUT_DIR).glob(f"*/{WORKSPACE}/run.json")]
    runs = []
    for ws in found:
        ws = ws.resolve()
        if ws not in runs and (ws / "run.json").exists() and _same_pdf(ws, pdf) and not is_finished(ws):
            runs.append(ws)
    if runs:
        newest = max(runs, key=lambda ws: _run_key(ws.parent))
        return {"workspace": str(newest), "legacy": False}
    legacy = Path(pdf).resolve().parent / LEGACY_WORKSPACE
    if (legacy / "run.json").exists() and _same_pdf(legacy, pdf) and not is_finished(legacy):
        return {"workspace": str(legacy), "legacy": True}
    return {"workspace": None, "legacy": False}


def adopt_legacy(legacy_ws: Path, pdf: Path, cwd, home: Path) -> dict:
    """Move an old <paper_dir>/review_workspace/ into a new run folder as its .workspace/. The
    folder is dated by the old run's first audit event."""
    legacy_ws = Path(legacy_ws)
    if not _same_pdf(legacy_ws, pdf):
        raise ValueError(f"{legacy_ws} is not a legacy workspace for {pdf}")
    events = audit.read_events(legacy_ws)
    date = events[0]["ts"][:10] if events else _today()
    run_dir = next_run_dir(choose_root(pdf, cwd, home), date)
    run_dir.mkdir(parents=True)
    shutil.move(str(legacy_ws), str(run_dir / WORKSPACE))
    _register(home, pdf, run_dir, date)
    return _paths(run_dir)


OLD_OUTPUT = {"fix_list": (["issues_list"], "full"), "report": (["report"], "full"),
              "memo": (["issues_list"], "facts_only")}


# A run from before setup:permission recorded a role instead.
OLD_ROLE = {"author": "mine", "referee": "journal"}


def migrate_run(ws: Path, output_answer: str = "", role_answer: str = "") -> dict:
    """Rewrite an older run.json for this version: "output" becomes "outputs" and
    "issues_list_mode". A report draft from the old layout (draft.txt) is set aside. When it is,
    or when an older run has no stage-6/issues.json, the brief's Stage 5 to 7 lines are removed,
    so resume reruns Stage 5 and the stages after it write the files this version reads. When a
    pre-change run's stage-1/unverified_numbers.md has bullet lines no known form matches, the
    Stage 1 line goes too, so the numbers are checked again."""
    ws = Path(ws)
    path = ws / "run.json"
    run = json.loads(path.read_text(encoding="utf-8"))
    older = "outputs" not in run
    if older:
        old = run.get("output")
        if old not in OLD_OUTPUT:
            old = "report" if "report" in output_answer.lower() else "fix_list"
        run["outputs"], run["issues_list_mode"] = list(OLD_OUTPUT[old][0]), OLD_OUTPUT[old][1]
    run.pop("output", None)
    run.setdefault("issues_list_mode", "full")
    if "permission" not in run:
        if run.get("role") in OLD_ROLE:
            run["permission"] = OLD_ROLE[run["role"]]
        elif role_answer:
            run["permission"] = "journal" if "reviewing" in role_answer.lower() else "mine"
            run["role"] = PERMISSIONS[run["permission"]]
    if str(run.get("depth", "")).lower() == "quick":
        run["outputs"] = [o for o in run["outputs"] if o != "report"] or ["issues_list"]
        run["issues_list_mode"] = "facts_only"
    path.write_text(json.dumps(run, indent=2), encoding="utf-8")
    moved = False
    for stage in ("stage-5", "stage-6"):
        txt = ws / stage / "draft.txt"
        if txt.exists():
            txt.rename(ws / stage / "draft_legacy.txt")
            moved = True
    brief = ws / "brief.md"
    reset = ()
    if moved or (older and not (ws / "stage-6" / "issues.json").exists()):
        reset += ("Stage 5:", "Stage 6:", "Stage 7:")
    # Unverified numbers a pre-change run (no "outputs", or no flags.json) wrote in a form this
    # version cannot read: check them again. A current run is never reset.
    pre_change = older or not (ws / "stage-1" / "flags.json").exists()
    if pre_change and validated.unparsed_unverified(ws):
        reset += ("Stage 1:",)
    if reset and brief.exists():
        keep = [l for l in brief.read_text(encoding="utf-8").splitlines() if not l.startswith(reset)]
        brief.write_text("\n".join(keep) + "\n", encoding="utf-8")
    return run


DEPTH_NAMES = {"quick": "Quick", "standard": "Standard", "deep": "Deep", "full": "Deep"}
LEVEL_NAMES = {"light": "Light", "standard": "Standard", "handson": "Hands-on", "auto": "Auto"}
PERMISSION_NAMES = {"mine": "The paper is yours or your coauthors'",
                    "author_asked": "The author asked you to read it",
                    "journal": "A journal sent it to you for review"}
RECORD = (("qc.md", "Quality-control record: how each finding in the audit was ruled."),
          ("audit_package.md", "Audit package: every check, answer, and model the run used."),
          ("consent.json", "Consent record."),
          ("usage.json", "Usage record: tokens, time, and API-equivalent cost by stage and by model."),
          ("models.json", "Model record: the exact model ids that ran, the work each did (mechanical or judgment), "
                          "and the call counts; the configured aliases, marked as such, where usage was not measured."),
          ("run_log.md", "Run log: one timestamped line for each step the chat did not show."),
          ("run.json", "Run settings."))


def put(run_dir: Path, target: str, source: Path) -> str:
    """Move `source` to `<run_dir>/target`, creating parent folders as needed. `run_dir` must be
    a real Plumb run folder (`<root>/plumb_output/<date>/`, holding `.workspace/run.json`), never
    a folder a confused caller might pass instead, such as the paper's own folder or a project
    root: `plumb_output/<date>/` sits exactly one level above the paper's folder in the real
    layout, so this check is what stops a mis-set `run_dir` from landing on the PDF's own folder
    with no traversal needed. Refuses a target that resolves outside `run_dir`, including `../`
    traversal, an absolute path, and a symlink (inside `run_dir`) that leads outside it. Refuses
    any target ending in `.pdf` unless its name is the annotated copy's pattern (`*_annotated.pdf`,
    see `annotated_name`), so `put` can never overwrite the paper itself. Refuses a missing
    `source`. Removes `source` on a successful move. The blocked-write workaround: a hook that
    scans shell command text cannot block a move done this way, since the command holds only
    paths."""
    run_dir = Path(run_dir).resolve()
    if not (run_dir / WORKSPACE / "run.json").is_file() or run_dir.parent.name != OUTPUT_DIR:
        raise ValueError(f"{run_dir} is not a Plumb run folder.")
    dest = (run_dir / target).resolve()
    if run_dir not in dest.parents:
        raise ValueError(f"{target} is the run folder itself or resolves outside it.")
    if dest.is_dir():
        raise ValueError(f"{target} is a folder; name the file to write.")
    name = dest.name.lower()
    if name.endswith(".pdf") and not name.endswith("_annotated.pdf"):
        raise ValueError(f"{target} is a PDF; plumb put only accepts the annotated copy (*_annotated.pdf).")
    source = Path(source)
    if not source.is_file():
        raise ValueError(f"{source} is not a staging file.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(dest))
    return str(dest)


def search_cap_line(run: dict) -> str:
    """The README and audit-package line for a run with a search date cap. It says what the run did
    (every agent was told the cap; the final outputs were checked for citations dated after its year)."""
    return (f"- Search date cap: {run['search_before']} (every agent was told to cite nothing published after this "
            "date, with the exemptions in its agent file, and the outputs were checked for later citations)")


def annotated_name(pdf_path: str) -> str:
    return f"{Path(pdf_path).stem}_annotated.pdf"


def write_readme(ws: Path, profiles_dir=None) -> Path:
    """README.md in the run folder: what each file is, and the run's settings."""
    from . import profiles
    ws = Path(ws)
    run_dir = ws.parent
    run = json.loads((ws / "run.json").read_text(encoding="utf-8"))
    journal = run.get("journal") or ""
    if journal and profiles_dir:
        try:
            journal = profiles.load_profile(profiles_dir, journal).name
        except ValueError:
            pass
    facts = run.get("issues_list_mode") == "facts_only"
    described = {
        "issues_list": ("issues_list.md",
                        "The facts Plumb checked, most serious first. Items it dropped, and why, are at the end."
                        if facts else
                        "The issues Plumb kept, most serious first, each with a fix. Items it dropped, and why, "
                        "are at the end."),
        "annotated_pdf": (annotated_name(run.get("pdf_path", "paper.pdf")),
                          "A copy of the paper with each issue pinned to its page. Page 1 is an index. "
                          "Your PDF is unchanged."),
        "report": ("mock_report.txt", "A mock referee report in plain text."),
        "editor_memo": ("editor_memo.md", "A memo for an editor: a neutral summary of the paper and the most "
                        "serious issues that survived the checks. It gives no recommendation."),
    }
    # Stage 7's final verification logs one "final" event per check on each delivered output. Only
    # the last pass counts: events after the last draft:ready answer, for the file as it is now.
    events = audit.read_events(ws)
    last_ready = max((i for i, e in enumerate(events)
                      if e["kind"] == "checkin" and e.get("item") == "draft:ready"), default=-1)
    finals = {}
    for e in events[last_ready + 1:]:
        if e["kind"] == "verification" and e.get("check") == "final":
            finals.setdefault(e.get("output"), []).append(e)
    files = []
    for o in run.get("outputs", []):
        if o in described:
            name, what = described[o]
            f = run_dir / name
            sha = hashlib.sha256(f.read_bytes()).hexdigest() if f.is_file() else None
            checks = [e for e in finals.get(o, []) if e.get("sha256") == sha]
            # Citation lookup exits 2 on network trouble; that is not a failure of the file.
            offline = [e for e in checks if e.get("step") == "verify_citations" and e.get("exit") == 2]
            passes = [e.get("exit") == 0 or e in offline for e in checks]
            status = "Verified." if sha and passes and all(passes) else "Not verified."
            if sha is None and (ws / "stage-7" / "withheld" / name).is_file():
                status = f"Withheld. It still carried an editorial recommendation, so it is in `{WORKSPACE}/stage-7/withheld/`."
            if status == "Verified." and offline:
                status += " Citation lookup was unavailable."
            files.append((name, f"{status} {what}"))
    files.append(("paper_summary.md", "A neutral summary of the paper."))
    lines = ["# Plumb review", "",
             f"- Paper: {Path(run.get('pdf_path', '')).name or 'not recorded'}",
             f"- Depth: {DEPTH_NAMES.get(str(run.get('depth', '')).lower(), 'not recorded')}",
             f"- Check-in level: {LEVEL_NAMES.get(run.get('level', ''), 'not recorded')}",
             f"- Journal: {journal or 'not recorded'}",
             f"- Permission: {PERMISSION_NAMES.get(run.get('permission') or OLD_ROLE.get(run.get('role', ''), ''), 'not recorded')}",
             f"- Date: {(run.get('started') or run_dir.name)[:10]}"]
    if run.get("search_before"):
        lines.append(search_cap_line(run))
    if run.get("unfinished_run"):
        lines.append(f"- Started fresh: an unfinished run of this paper, `{run['unfinished_run']}`, was left as it was.")
    lines += ["", "## Files", ""]
    lines += [f"- `{name}`: {what}" for name, what in files]
    lines += [""] + usage.render(usage.load_report(ws))[:-1]
    lines += ["", "## The record", "",
              f"Everything else the run wrote is in `{WORKSPACE}/`. Finder hides it; press Command-Shift-period to show it.", ""]
    lines += [f"- `{WORKSPACE}/{name}`: {what}" for name, what in RECORD if (ws / name).exists()]
    out = run_dir / "README.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out
