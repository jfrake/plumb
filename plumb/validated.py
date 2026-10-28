"""Which findings reach the outputs. An issue is validated when it survived the audit, the user
kept it, and its facts are confirmed. `plumb validated` writes stage-7/validated.json (the kept
issues, most serious first) and stage-7/dropped.json (every dropped item, once, with its reason)."""
from __future__ import annotations
import json
import re
from pathlib import Path

from . import checkin
from . import depth as _depth
from .outputs import _match_key, metaphor_errors

SEVERITIES = ("Undermines the main claim", "Weakens a claim", "Minor")
AUDIT = "overruled in the audit"
DISMISSED = "you dismissed it"
EXTRACTION = "you marked it an extraction error"
EXPLAINED = "the paper states one-tailed tests or another source for the marks"
NOT_A_PROBLEM = "you marked it not a problem or misread"
NOT_VERIFIED = "numbers not verified"
LOOKUP = "lookup failed"
CUT_PART = "cut from a kept issue in the audit"
MERGED = "merged into a kept issue in the audit"
# Stage 5 exclusions, by rationale. A `duplicate_of` finding is still in the review, so it is not dropped.
LEFT_OUT = {
    "addressed_by_paper_appendix": "left out because the paper already does it",
    "low_confidence_minor_only": "left out as a low-confidence minor point",
    "user_ruled_out": "you ruled out the alternative it rests on",
}
FACT_KINDS = ("number", "reference")
NEEDS_EXCERPT = ("judgment", "paper")
SETTLED = ("paper", "external")
DRAFT_DROP = "draft:drop:"


class InputError(Exception):
    """A required input is missing, is not valid JSON, or has the wrong shape."""


class MissingExcerpt(Exception):
    def __init__(self, issues: list):
        self.issues = issues
        super().__init__("\n".join(f"Issue {i['id']} ({i.get('title', '')}) has no excerpt from the paper."
                                   for i in issues))


class UnauditedSummary(Exception):
    """A kept issue's summary is not in the audited draft, stage-6/draft.md."""
    def __init__(self, issues: list):
        self.issues = issues
        super().__init__("\n".join(
            f"Issue {i['id']} ({i.get('title', '')}): its summary is not in stage-6/draft.md word for word."
            for i in issues))


def minors_missing_from_draft(ws) -> list:
    """The minors in stage-5/issues.json that the user kept (no answer dismissed them) whose
    summary is not in stage-5/draft.md. The draft carries every kept minor; Stage 5 checks it so a
    skipped regeneration fails there, not in Stage 7."""
    ws = Path(ws)
    issues = records(ws / "stage-5" / "issues.json", ISSUE_FIELDS)
    draft = ws / "stage-5" / "draft.md"
    if not draft.exists():
        raise InputError(f"{draft} is missing.")
    text = _plain_key(draft.read_text(encoding="utf-8"))
    answers = checkin.answers(ws)
    gone = dismissed(ws, answers)
    first_three = checkin.letter(answers.get("minors:list", "")) == "B"
    minors = [i for i in issues if i.get("kind") == "minor"]
    drops = _resolve_minor_drops(minors, gone)
    return [i for i in minors if _dismissal(i, gone, first_three, drops) is None
            and _plain_key(i.get("summary") or "") not in text]


def _load(path: Path, default=None):
    if not path.exists():
        if default is not None:
            return default
        raise InputError(f"{path} is missing.")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise InputError(f"{path} is not valid JSON: {exc}")


ISSUE_FIELDS = ("id", "kind", "summary", "checkin")
# Fields the writers copy word for word; Stage 5 writes `why`, validated.json calls it `why_it_matters`.
COPIED_FIELDS = ("title", "summary", "why", "why_it_matters", "settle")


def metaphor_problems(path, draft=None) -> list:
    """One line per copied field of an issues.json file that uses a metaphor, naming the issue id, the
    field, and the phrases, then the draft's metaphors if `draft` is given. A minor the minors
    check-in dropped is skipped: rewording it would break the match that drops it. A copied field
    that is not text raises InputError."""
    path = Path(path)
    issues = records(path, ISSUE_FIELDS)
    # Type-check first: the dismissal matching below reads summaries and titles as text.
    for i in issues:
        for field in COPIED_FIELDS:
            value = i.get(field)
            if value is not None and not isinstance(value, str):
                raise InputError(f"{path}: issue {i['id']} `{field}` must be text, not {type(value).__name__}.")
    ws = path.parent.parent
    answers = checkin.answers(ws)
    gone = dismissed(ws, answers)
    first_three = checkin.letter(answers.get("minors:list", "")) == "B"
    drops = _resolve_minor_drops([i for i in issues if i.get("kind") == "minor"], gone)
    out = []
    for i in issues:
        if i.get("kind") == "minor" and _dismissal(i, gone, first_three, drops) is not None:
            continue
        for field in COPIED_FIELDS:
            errs = metaphor_errors(i.get(field) or "")
            if errs:
                out.append(f"Issue {i['id']} `{field}`: {errs[0]}")
    if draft is not None:
        draft = Path(draft)
        if not draft.exists():
            raise InputError(f"{draft} is missing.")
        out += [f"{draft.name}: {e}" for e in metaphor_errors(draft.read_text(encoding="utf-8"))]
    return out


def _run(path: Path) -> dict:
    run = _load(path)
    if not isinstance(run, dict):
        raise InputError(f"{path} must be a JSON object.")
    return run


def records(path: Path, fields: tuple, default=None) -> list:
    """A JSON list of objects, each with `fields`. Raises InputError naming the file and record."""
    rows = _load(path, default)
    if not isinstance(rows, list):
        raise InputError(f"{path} must be a JSON list of records, not a {type(rows).__name__}.")
    for n, r in enumerate(rows, 1):
        if not isinstance(r, dict):
            raise InputError(f"{path}: record {n} is not a JSON object.")
        for f in fields:
            if f not in r:
                raise InputError(f"{path}: record {n} has no '{f}'.")
        if not isinstance(r.get("sources") or [], list):
            raise InputError(f"{path}: record {n} has 'sources' that is not a list.")
        if not isinstance(r.get("merged_from") or [], list):
            raise InputError(f"{path}: record {n} has 'merged_from' that is not a list.")
    return rows


def synthesis_exclusions(ws) -> list:
    """(finding_id, source_file, reason) for each EXCLUDED row of synthesis_coverage.md that left
    its point out of the review: every exclusion except `duplicate_of`."""
    path = Path(ws) / "synthesis_coverage.md"
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [c.strip().replace("\x00", "|")
                 for c in line.strip().replace(r"\|", "\x00").split("|")[1:-1]]
        if len(cells) < 6 or cells[3] != "EXCLUDED":
            continue
        code = cells[5].split(":", 1)[0].strip()
        if code in LEFT_OUT:
            out.append((cells[0], cells[1], LEFT_OUT[code]))
    return out


def cut_points(ws) -> list:
    """stage-6/cut_points.json: distinct points the audit cut from issues it kept."""
    rows = _load(Path(ws) / "stage-6" / "cut_points.json", default=[])
    if not isinstance(rows, list) or any(not isinstance(r, dict) or not r.get("point") for r in rows):
        raise InputError(f"{Path(ws) / 'stage-6' / 'cut_points.json'} must be a JSON list of records, "
                         "each with 'issue' and 'point'.")
    return rows


def _plain_key(text: str) -> str:
    """The summary match key with markdown emphasis (*, _, backticks) removed."""
    return _match_key(re.sub(r"[*_`]", "", text))


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip().rstrip(".").casefold()


def _first_sentence(text: str) -> str:
    return re.split(r"(?<=[.!?])\s+", (text or "").strip(), maxsplit=1)[0]


# Runs from before flags.json wrote each line in free form "with the page". These read the
# forms those runs used: a check-in item id, a backticked <table>:<row>:<col>, or prose.
_LEGACY = (
    ("cell", re.compile(r"numbers:cell:([^`,()]+?:[^:`,()\s]+:[^:`,()\s]+)")),
    ("table", re.compile(r"numbers:table:([^`,()]+?)\s*(?:[`,(]|$)")),
    ("cell", re.compile(r"`([^`:]+:[^`:]+:[^`:]+)`")),
    ("cell", re.compile(r"^(?P<t>[^,()]+?),? row (?P<r>[^,\s]+),? col(?:umn)? (?P<c>[^,\s()]+)")),
    ("table", re.compile(r"^`?([^`,()]+?)`?,? \(?(?:the )?(?:whole|entire) table")),
)


def _unverified_lines(ws: Path) -> tuple:
    """(cells, tables, unparsed lines) from stage-1/unverified_numbers.md, in file order."""
    p = Path(ws) / "stage-1" / "unverified_numbers.md"
    text = p.read_text(encoding="utf-8") if p.exists() else ""
    cells, tables, bad = [], [], []
    for line in text.splitlines():
        s = line.strip()
        # Only bullet lines name a cell or table; headings, intro lines, and "None." do not.
        if not re.match(r"^(?:[-*]|\d+\.)\s", s):
            continue
        m = re.match(r"^- (cell|table) `([^`]+)`", s)
        if not m:
            body = re.sub(r"^(?:[-*]|\d+\.)\s+", "", s)
            for kind, rx in _LEGACY:
                hit = rx.search(body)
                if hit:
                    name = ":".join(hit.group(k).strip() for k in ("t", "r", "c")) if "t" in rx.groupindex \
                        else hit.group(1).strip()
                    m = (kind, name)
                    break
            else:
                bad.append(s)
                continue
        else:
            m = (m.group(1), m.group(2))
        (cells if m[0] == "cell" else tables).append(m[1])
    return cells, tables, bad


def unverified(ws: Path) -> tuple:
    """(cells, tables) listed in stage-1/unverified_numbers.md, as "- cell `<table>:<row>:<col>`, ..."
    and "- table `<table>`, ..." lines, or in an older run's forms, in file order."""
    cells, tables, _ = _unverified_lines(ws)
    return cells, tables


def unparsed_unverified(ws: Path) -> list:
    """Lines of stage-1/unverified_numbers.md that name no cell or table this version can read."""
    return _unverified_lines(ws)[2]


SUFFIXED = re.compile(r"^(?:majors|minors):\d+:r\d*$")
# The Stage 6 citation check-in reuses the majors stop; its C stops the review and dismisses nothing.
CITATION = "majors:citation:"


def dismissed(ws: Path, answers: dict) -> dict:
    """Items the user dismissed: {item: title}. A major is dismissed by "C. The paper already
    addresses this" or when its card was pruned by an alternative the user ruled out; a minor, or
    anything at the draft review (`draft:drop:<source>`), by a "Drop: <sentence>" answer. The
    check-in replay protocol re-asks a numbered item under a suffixed id ("majors:1:r") and always
    copies that answer under the base id ("majors:1") too, so a suffixed id is skipped here: its
    dismissal is counted once, under the base id."""
    given = {k: checkin.letter(v) for k, v in answers.items()}
    out = {}
    for q in records(Path(ws) / "stage-4" / "questions.json", ("id",), default=[]):
        if q.get("stop") == "majors" and q["id"] not in answers and checkin.is_pruned(q, given):
            out[q["id"]] = _first_sentence(q.get("text", ""))
    for item, answer in answers.items():
        if SUFFIXED.match(item):
            continue
        if item.startswith(CITATION):
            continue
        if item.startswith("majors:") and given[item] == "C":
            out[item] = answer.split(" | ", 1)[1].strip() if " | " in answer else item
        elif item.startswith(("minors:", DRAFT_DROP)) and answer.startswith("Drop:"):
            out[item] = answer[len("Drop:"):].strip()
    return out


def _resolve_minor_drops(minors: list, gone: dict) -> dict:
    """{issue id: gone key} for minors dismissed by a "minors:<n>" Drop-answer. Synthesis may
    renumber the minors after the check-in records an answer against a number (the numbered-item
    replay protocol), so a minor is matched by its dismissed text first; a key whose text matches
    no minor falls back to naming the minor recorded at that key today."""
    keys = [k for k in gone if re.fullmatch(r"minors:\d+", k)]
    resolved = {}
    for k in keys:
        s = gone[k]
        if not s:
            continue
        for i in minors:
            if i["id"] not in resolved and (_norm(i.get("summary")).startswith(_norm(s))
                                            or _norm(i.get("title")).startswith(_norm(s))):
                resolved[i["id"]] = k
                break
    for k in keys:
        if k in resolved.values():
            continue
        for i in minors:
            if i["id"] not in resolved and i.get("checkin") == k:
                resolved[i["id"]] = k
                break
    return resolved


def _dismissal(issue: dict, gone: dict, first_three: bool, minor_drops: dict):
    """The dismissal that covers this issue, or None. "minors:list" stands for "keep only the
    first three minors"."""
    draft_key = f"{DRAFT_DROP}{issue['id']}"
    if draft_key in gone:
        return draft_key
    if issue.get("kind") == "minor":
        hit = minor_drops.get(issue["id"])
        if hit:
            return hit
        n = re.fullmatch(r"minors:(\d+)", issue.get("checkin") or "")
        if first_three and n and int(n.group(1)) > 3:
            return "minors:list"
        return None
    key = issue.get("checkin")
    return key if key and key in gone else None


def _rank(severity) -> int:
    return SEVERITIES.index(severity) if severity in SEVERITIES else len(SEVERITIES) - 1


def _record(src: dict, kind: str) -> dict:
    return {
        "source": str(src["item"]) if kind in FACT_KINDS else str(src.get("id")),
        "item": src.get("item") or src.get("checkin"),
        "kind": kind,
        "title": src.get("title", ""),
        "severity": src.get("severity") if src.get("severity") in SEVERITIES else "Minor",
        "summary": src.get("summary", ""),
        "excerpt": (src.get("excerpt") or "").strip() or None,
        "ms_page": src.get("ms_page"),
        "pdf_page": src.get("pdf_page"),
        "adjudication": src.get("adjudication") or ("paper" if kind == "number" else "external"),
        "fix": src.get("solvability"),
        "sources": list(src.get("sources") or []),
        # The memo's "Why it matters" and "What would settle it" read these; a checked fact has neither.
        "why_it_matters": src.get("why") or None,
        "settle": src.get("settle") or None,
    }


def _cell_title(name: str) -> str:
    parts = name.rsplit(":", 2)
    return f"{parts[0]}, row {parts[1]}, column {parts[2]}" if len(parts) == 3 else name


def build(ws, allow_missing_excerpt: bool = False) -> tuple:
    """(kept, dropped) for the run in `ws`. Raises InputError, UnauditedSummary, or MissingExcerpt. Each dropped item
    appears once, with the most specific reason: the user's answer, then the audit, then the facts."""
    ws = Path(ws)
    run = _run(ws / "run.json")
    answers = checkin.answers(ws)
    try:
        d = _depth.from_run(run, answers.get("setup:depth", ""))
    except ValueError as exc:
        raise InputError(f"run.json: {exc}")
    mode = "facts_only" if d == "quick" else run.get("issues_list_mode", "full")
    if mode not in ("full", "facts_only"):
        raise InputError(f"run.json: issues_list_mode must be 'full' or 'facts_only', not {mode!r}")
    dropped = []

    def drop(item, title, reason):
        dropped.append({"item": item, "title": title, "reason": reason})

    gone = dismissed(ws, answers)

    # Stage 1 facts: the user's answer first, then rule 3.
    cells, tables = unverified(ws)
    facts, fact_reason = [], {}
    for f in records(ws / "stage-1" / "flags.json", ("item", "kind"), default=[]):
        if f.get("kind") not in FACT_KINDS:
            continue
        reason = None
        if f"{DRAFT_DROP}{f['item']}" in gone:
            reason = DISMISSED
            gone.pop(f"{DRAFT_DROP}{f['item']}")
        elif f["kind"] == "number":
            letter = checkin.letter(answers.get(f["item"], ""))
            if letter == "B":
                reason = NOT_A_PROBLEM if f["item"].startswith(("numbers:pack:", "numbers:hyp:")) else EXTRACTION
            elif letter == "C" and f["item"].endswith(":stars_vs_se"):
                reason = EXPLAINED
            elif set(f.get("cells") or []) & set(cells) or (f.get("table") and f["table"] in tables):
                reason = NOT_VERIFIED
        elif f.get("lookup_failed"):
            reason = LOOKUP
        if reason:
            fact_reason[f["item"]] = reason
            drop(f["item"], f.get("title", ""), reason)
        else:
            facts.append(f)

    issues = []
    if 6 in _depth.STAGES[d]:
        before = records(ws / "stage-5" / "issues.json", ISSUE_FIELDS)
        after = records(ws / "stage-6" / "issues.json", ISSUE_FIELDS)
        survived = {str(i["id"]): i for i in after}
        merged = {str(m) for i in after for m in (i.get("merged_from") or [])}
        known = {str(i["id"]) for i in before}
        first_three = checkin.letter(answers.get("minors:list", "")) == "B"
        combined = before + [a for a in after if str(a["id"]) not in known]
        minor_drops = _resolve_minor_drops([i for i in combined if i.get("kind") == "minor"], gone)
        for i in combined:
            iid = str(i["id"])
            label = i.get("checkin") or f"issue {iid}"
            # Rule 2: the user kept it.
            hit = _dismissal(i, gone, first_three, minor_drops)
            if hit is not None:
                gone.pop(hit, None)
                drop(label, i.get("title", ""), DISMISSED)
                continue
            # Rule 1: an issue the adjudicator left out of stage-6/issues.json did not survive the
            # audit, unless a kept issue names it in `merged_from`.
            if iid not in survived:
                drop(label, i.get("title", ""), MERGED if iid in merged else AUDIT)
                continue
            issue = survived[iid]
            # Rule 3: an issue built on a Stage 1 fact that was dropped goes with it.
            bad = [s for s in issue.get("sources") or [] if s in fact_reason]
            if bad:
                drop(label, issue.get("title", ""), fact_reason[bad[0]])
                continue
            issues.append(issue)
        # Points lost inside the pipeline: left out at synthesis, or cut from an issue the audit kept.
        for fid, source, reason in synthesis_exclusions(ws):
            dropped.append({"item": f"finding {fid}", "title": fid, "reason": reason, "source": source})
        for c in cut_points(ws):
            drop(f"issue {c.get('issue', '')}".strip(), c["point"], CUT_PART)
        pool = [i for i in issues if mode == "full" or i.get("adjudication") in SETTLED]
        # The outputs quote each summary, so it must be text the accuracy audit checked.
        draft = ws / "stage-6" / "draft.md"
        if not draft.exists():
            raise InputError(f"{draft} is missing.")
        audited = _plain_key(draft.read_text(encoding="utf-8"))
        unaudited = [i for i in pool if not _plain_key(i.get("summary") or "")
                     or _plain_key(i["summary"]) not in audited]
        if unaudited:
            raise UnauditedSummary(unaudited)
        missing = [i for i in pool if i.get("adjudication") in NEEDS_EXCERPT
                   and not (i.get("excerpt") or "").strip()]
        if missing and not allow_missing_excerpt:
            raise MissingExcerpt(missing)
    for item, title in gone.items():
        drop(item, title, DISMISSED)
    # Unverified numbers appear only here, in the dropped-items appendix.
    for c in cells:
        drop(f"cell:{c}", _cell_title(c), NOT_VERIFIED)
    for t in tables:
        drop(f"table:{t}", f"{t}, the whole table", NOT_VERIFIED)

    kept = [_record(i, i.get("kind") or "major") for i in issues]
    if mode == "facts_only":
        kept = [k for k in kept if k["adjudication"] in SETTLED]
        folded = {s for k in kept for s in k["sources"]}
        kept += [_record(f, f["kind"]) for f in facts if f["item"] not in folded]
    kept.sort(key=lambda k: _rank(k["severity"]))
    return [dict(id=str(n), **k) for n, k in enumerate(kept, 1)], dropped


def write(ws, allow_missing_excerpt: bool = False) -> dict:
    kept, dropped = build(ws, allow_missing_excerpt)
    out = Path(ws) / "stage-7"
    out.mkdir(parents=True, exist_ok=True)
    (out / "validated.json").write_text(json.dumps(kept, indent=2), encoding="utf-8")
    (out / "dropped.json").write_text(json.dumps(dropped, indent=2), encoding="utf-8")
    return {"kept": len(kept), "dropped": len(dropped)}
