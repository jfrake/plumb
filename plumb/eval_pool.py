"""The blind rating pool for one pilot paper. Candidates come from Plumb run folders (the issues in
stage-5/issues.json; for the Standard run also every point the reviewer dropped at a check-in,
tagged as overruled with its item id) and from eval/baseline.py out folders (the run of record's
issues.md). Candidates are grouped by meaning by a pinned model on a fixed clustering prompt (the
dry run, which calls no model, uses the scorer's text-overlap rule instead), each group becomes one
claim, each claim is rewritten into one neutral line by the same model on a fixed prompt, and the
claims go out shuffled on rating sheets that carry no source label. `eval/pool.py` wraps this."""
from __future__ import annotations
import json
import re
from pathlib import Path

from . import checkin
from . import fixture_score
from .validated import SEVERITIES


class PoolError(Exception):
    """A required input is missing or has the wrong shape."""


PLUMB_AUTO = "plumb-auto"
PLUMB_STANDARD = "plumb-standard"
BASELINE_MODELS = ("gpt-6-astra", "claude-fable-5-1")
# The four conditions. A point the Standard reviewer dropped keeps plumb-standard as its origin but
# is not in Standard's output, so it carries `overruled` and earns Standard no credit.
CONDITIONS = (PLUMB_AUTO, PLUMB_STANDARD) + BASELINE_MODELS
BASELINE_RUN_FILES = ("request.json", "response.json", "issues.md", "done")


# --- candidates from Plumb runs ---

def _candidate(source, text, title="", severity=None, pages=(), raw=None, issue_id=None, item=None,
               adjudication=None, pack=None, overruled=None, ref=None, pdf_pages=()) -> dict:
    """One candidate. `pages` are printed page numbers and `pdf_pages` PDF page numbers; only
    printed pages are ever compared. `ref` names the candidate for near_misses.json and hand
    merges: <source>:<issue id>, <source>:<item>, or <model>:<entry number>."""
    return {"source": source, "text": re.sub(r"\s+", " ", str(text or "")).strip(), "title": str(title or "").strip(),
            "severity": severity if severity in SEVERITIES else None, "pages": [str(p) for p in pages if p is not None],
            "pdf_pages": [str(p) for p in pdf_pages if p is not None], "raw": raw, "issue_id": issue_id, "item": item,
            "adjudication": adjudication, "pack": pack, "overruled": overruled,
            "ref": ref or f"{source}:{issue_id or item or 'x'}"}


def pack_of(issue: dict, run: dict):
    """The pack an issue belongs to: a pack named in one of its sources (a token or a prefix, as in
    "survey_numbers.md:3"), "core" for a core source, else the run's primary pack."""
    packs = [str(p) for p in run.get("packs") or []]
    for s in issue.get("sources") or []:
        tokens = fixture_score._tokens(s)
        for p in packs:
            if p.casefold() in tokens or str(s).casefold().startswith(p.casefold()):
                return p
        if "core" in tokens:
            return "core"
    return str(run.get("primary_pack") or (packs[0] if packs else "")) or None


def page_label(pages) -> str:
    """One form for every claim, whatever the source wrote: "p. 4", "pp. 4-6" for a run,
    "pp. 4, 9" for separate pages, "p. ?" for none."""
    nums = sorted({int(p) for p in pages if str(p).strip().isdigit()})
    if not nums:
        return "p. ?"
    runs, start, prev = [], nums[0], nums[0]
    for n in nums[1:]:
        if n == prev + 1:
            prev = n
            continue
        runs.append((start, prev))
        start = prev = n
    runs.append((start, prev))
    parts = [str(a) if a == b else f"{a}-{b}" for a, b in runs]
    return ("p. " if len(nums) == 1 else "pp. ") + ", ".join(parts)


def page_offset(ws, run: dict):
    """PDF page minus printed page for the run, when the run says: run.json `page_offset`, else
    table_pages/index.json entries that carry both `page` (PDF) and `ms_page` (printed) and
    agree; None when nothing says."""
    if isinstance(run.get("page_offset"), int):
        return run["page_offset"]
    offsets = set()
    for row in _records(ws, "table_pages/index.json"):
        if isinstance(row.get("page"), int) and isinstance(row.get("ms_page"), int):
            offsets.add(row["page"] - row["ms_page"])
    return offsets.pop() if len(offsets) == 1 else None


def _issue_pages(issue: dict, offset) -> list:
    """The printed page; when there is none, the PDF page stands in only where the run says the
    two numberings coincide (offset 0)."""
    if issue.get("ms_page") is not None:
        return [issue["ms_page"]]
    if offset == 0 and issue.get("pdf_page") is not None:
        return [issue["pdf_page"]]
    return []


def _issue_candidate(issue: dict, run: dict, source: str, overruled=None, offset=None) -> dict:
    return _candidate(source, fixture_score.issue_text(issue), title=issue.get("title"), severity=issue.get("severity"),
                      pages=_issue_pages(issue, offset), pdf_pages=[issue.get("pdf_page")], raw=issue, issue_id=str(issue["id"]),
                      item=issue.get("checkin"), adjudication=issue.get("adjudication"), pack=pack_of(issue, run),
                      overruled=overruled, ref=f"{source}:{issue['id']}")


def _load(run_dir):
    try:
        return fixture_score.load_run(run_dir)
    except fixture_score.ScoreError as exc:
        raise PoolError(str(exc))


def plumb_candidates(run_dir, source: str) -> list:
    """One candidate per issue in the run's stage-5/issues.json, labelled `source`."""
    run = _load(run_dir)
    offset = page_offset(run["workspace"], run["run"])
    return [_issue_candidate(i, run["run"], source, offset=offset) for i in run["issues"]]


# Ruling R4: the answers that drop the item asked about. majors C and against C; numbers B on a
# flag item (arith, text, pack, hyp; stage-1-verify.md defines B as a drop there) and C only on a
# stars_vs_se flag, never on a cell or table reading; minors "Drop:" and minors:list B (every held
# minor after the third); draft:drop. Demotions (majors B), against B, and draft rulings are
# overrides but not drops, so they enter the override-rate table and not the pool.
_NUMBERS_FLAGS = ("numbers:arith:", "numbers:text:", "numbers:pack:", "numbers:hyp:")
MINORS_KEPT_BY_LIST_B = 3
# The Stage 6 citation check-in reuses the majors stop; its answers drop no issue.
CITATION = "majors:citation:"


def _drops(ev: dict) -> bool:
    stop, item, answer = ev["stop"], str(ev["item"]), str(ev.get("answer", ""))
    letter = checkin._choice(answer)
    if item.startswith(CITATION):
        return False
    if stop == "majors" or stop == "against":
        return letter == "C"
    if stop == "numbers":
        if item == "numbers:hyp:mapping" or not item.startswith(_NUMBERS_FLAGS):
            return False
        return letter == "B" or (letter == "C" and item.endswith(":stars_vs_se"))
    if stop == "minors":
        return letter == "B" if item == "minors:list" else answer.startswith("Drop:")
    if stop == "draft":
        return item.startswith("draft:drop:") and answer.startswith("Drop:")
    return False


def overruled_items(ws) -> list:
    """The final answers at the judgment stops that dropped an item against the tool's
    recommendation: {item, stop, recommended, answer, note}. An answer the tool took itself (note
    "auto"), a replay, a delegation, or an answer matching the recommendation never counts."""
    out = []
    for ev in checkin.final_answers(checkin.audit.read_events(ws)).values():
        if ev["stop"] not in checkin.OVERRIDE_STOPS or not _drops(ev):
            continue
        if not checkin.is_override(ev["stop"], str(ev.get("recommended", "")), str(ev["answer"]),
                                   str(ev.get("note") or ""), ev["item"]):
            continue
        out.append({"item": ev["item"], "stop": ev["stop"], "recommended": ev.get("recommended", ""),
                    "answer": ev["answer"], "note": ev.get("note") or ""})
    return out


def _sentence_after_bar(label: str) -> str:
    return label.split(" | ", 1)[1].strip() if " | " in label else ""


def _records(ws, rel: str) -> list:
    f = Path(ws) / rel
    if not f.is_file():
        return []
    try:
        rows = json.loads(f.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise PoolError(f"{f} is not valid JSON: {exc}")
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def _minor_number(issue: dict):
    m = re.fullmatch(r"minors:(\d+)", str(issue.get("checkin") or ""))
    return int(m.group(1)) if m and issue.get("kind") == "minor" else None


def _match_issue(over: dict, issues: list):
    """The stage-5 issue an overruled item names: by check-in item, by issue id (draft:drop), by a
    dropped minor's recorded sentence, or by a numbers flag in the issue's sources."""
    item, stop, answer = over["item"], over["stop"], str(over["answer"])
    if item == "minors:list":
        return None
    if stop == "draft":
        src = item[len("draft:drop:"):]
        for i in issues:
            if str(i["id"]) == src or src in (i.get("sources") or []):
                return i
        return None
    if stop == "minors":
        sentence = fixture_score._norm(answer[len("Drop:"):])
        for i in issues:
            if i.get("kind") == "minor" and sentence and (
                    fixture_score._norm(i.get("summary")).startswith(sentence)
                    or fixture_score._norm(i.get("title")).startswith(sentence)):
                return i
    for i in issues:
        if i.get("checkin") == item or item in (i.get("sources") or []):
            return i
    return None


UNKNOWN = "unknown"
_DRAFT_HEAD = re.compile(r"^##\s+(\d+)\.\s+(.*)$", re.M)
_DRAFT_ADJ = re.compile(r"\bAdjudication:\s*(paper|external|judgment)\b", re.I)
_DRAFT_PACK = re.compile(r"^\s*Pack:\s*([A-Za-z0-9_-]+)", re.M | re.I)
_DRAFT_SEV = re.compile(r"\bSeverity:\s*(" + "|".join(re.escape(x) for x in SEVERITIES) + r")", re.I)


def majors_draft(ws) -> dict:
    """{majors:<n>: {sentence, severity, adjudication, pack}} from stage-4/majors_draft.md, whose
    blocks start "## <n>. <sentence>" and carry "Severity: <label>. Adjudication: <type>."; a
    "Pack: <name>" line is read when present. Absent fields are "unknown"."""
    f = Path(ws) / "stage-4" / "majors_draft.md"
    if not f.is_file():
        return {}
    text = f.read_text(encoding="utf-8")
    heads = list(_DRAFT_HEAD.finditer(text))
    out = {}
    for n, m in enumerate(heads):
        block = text[m.end():heads[n + 1].start() if n + 1 < len(heads) else len(text)]
        adj, pack, sev = _DRAFT_ADJ.search(block), _DRAFT_PACK.search(block), _DRAFT_SEV.search(block)
        out[f"majors:{m.group(1)}"] = {
            "sentence": m.group(2).strip(), "adjudication": adj.group(1).lower() if adj else UNKNOWN,
            "pack": pack.group(1) if pack else UNKNOWN,
            "severity": next((x for x in SEVERITIES if sev and x.casefold() == sev.group(1).casefold()), None)}
    return out


def held_minors(ws) -> list:
    """[(n, line)] from stage-5/held_minors.md, a numbered list, weakest last."""
    f = Path(ws) / "stage-5" / "held_minors.md"
    if not f.is_file():
        return []
    out = []
    for line in f.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^(\d+)[.)]\s+(.+)$", line.strip())
        if m:
            out.append((int(m.group(1)), m.group(2).strip()))
    return out


def _orphan_candidate(over: dict, ws, run: dict):
    """A candidate for an overruled item that names no stage-5 issue, built from the file that
    asked it: stage-4/majors_cards.json (type and pack from majors_draft.md, else unknown),
    stage-3/questions.json (type and pack unknown), or stage-1/flags.json."""
    item, stop = over["item"], over["stop"]
    if stop == "majors":
        draft = majors_draft(ws).get(item) or {}
        adj, pack = draft.get("adjudication", UNKNOWN), draft.get("pack", UNKNOWN)
        for card in _records(ws, "stage-4/majors_cards.json"):
            if card.get("item") == item:
                text = " ".join(str(card.get(k) or "") for k in ("title", "summary", "excerpt"))
                return _candidate(PLUMB_STANDARD, text, title=card.get("title"), severity=card.get("severity"),
                                  pages=[card.get("ms_page")], raw=card, item=item,
                                  adjudication=card.get("adjudication") or adj, pack=card.get("pack") or pack, overruled=over)
        for q in _records(ws, "stage-4/questions.json"):
            if q.get("id") == item:
                return _candidate(PLUMB_STANDARD, q.get("text"), raw=q, item=item, adjudication=adj, pack=pack, overruled=over)
        if draft:
            return _candidate(PLUMB_STANDARD, draft["sentence"], severity=draft["severity"], raw=draft, item=item,
                              adjudication=adj, pack=pack, overruled=over)
    if stop == "against":
        for q in _records(ws, "stage-3/questions.json"):
            if q.get("id") == item:
                return _candidate(PLUMB_STANDARD, q.get("text"), raw=q, item=item, adjudication=UNKNOWN, pack=UNKNOWN,
                                  overruled=over)
    if stop == "numbers":
        for flag in _records(ws, "stage-1/flags.json"):
            if flag.get("item") == item:
                text = " ".join(str(flag.get(k) or "") for k in ("title", "summary", "excerpt"))
                m = re.match(r"numbers:pack:([^:]+):", item)
                return _candidate(PLUMB_STANDARD, text, title=flag.get("title"), pages=[flag.get("ms_page")], raw=flag,
                                  item=item, adjudication="paper", pack=m.group(1) if m else "core", overruled=over)
    sentence = _sentence_after_bar(str(over["answer"]))
    if sentence:
        return _candidate(PLUMB_STANDARD, sentence, raw=over, item=item, adjudication=UNKNOWN, pack=UNKNOWN, overruled=over)
    return None


def _list_b_candidates(over: dict, issues: list, ws) -> tuple:
    """minors:list B keeps the first three held minors: ({issue id: over} for the minors after
    the third in stage-5/issues.json, [candidates] built from held_minors.md when issues.json
    holds no such minor)."""
    by_issue = {str(i["id"]): over for i in issues
                if _minor_number(i) is not None and _minor_number(i) > MINORS_KEPT_BY_LIST_B}
    if by_issue:
        return by_issue, []
    extra = []
    for n, line in held_minors(ws):
        if n > MINORS_KEPT_BY_LIST_B:
            m = re.search(r"\(p+\.?\s*(\d+)", line)
            extra.append(_candidate(PLUMB_STANDARD, line, severity="Minor", pages=[m.group(1)] if m else [],
                                    raw=line, item=f"minors:{n}", adjudication=UNKNOWN, pack=UNKNOWN, overruled=over,
                                    ref=f"{PLUMB_STANDARD}:minors:{n}"))
    return {}, extra


def standard_candidates(run_dir) -> list:
    """The Standard run's issues, tagged plumb-standard, with `overruled` set on each the reviewer
    dropped at a check-in; plus one overruled candidate for each dropped point that names no issue
    in stage-5/issues.json."""
    run = _load(run_dir)
    ws = run["workspace"]
    issues = run["issues"]
    over_by_issue, orphans, extra = {}, [], []
    for over in overruled_items(ws):
        if over["item"] == "minors:list":
            found, built = _list_b_candidates(over, issues, ws)
            for iid, o in found.items():
                over_by_issue.setdefault(iid, o)
            extra += built
            continue
        hit = _match_issue(over, issues)
        if hit is not None:
            over_by_issue.setdefault(str(hit["id"]), over)
        else:
            orphans.append(over)
    out = []
    offset = page_offset(ws, run["run"])
    for i in issues:
        out.append(_issue_candidate(i, run["run"], PLUMB_STANDARD, over_by_issue.get(str(i["id"])), offset=offset))
    for over in orphans:
        c = _orphan_candidate(over, ws, run["run"])
        if c is not None:
            out.append(c)
    return out + extra


# --- candidates from eval/baseline.py out folders ---

# An entry starts at a line beginning with the next number in sequence: "N." or "N)", under
# heading marks or bold, or "Issue N" / "Problem N" with any separator. Sequence matters: a
# numbered list inside an entry restarts at 1, so it does not split the entry.
# An entry starts at a line beginning with the next number in sequence: "N." or "N)", under
# heading marks or bold, or "Issue N" / "Problem N" with any separator. Sequence matters: a
# numbered list inside an entry restarts at 1, so it does not split the entry.
_ENTRY = re.compile(r"^(?:#{1,6}\s*)?(?:\*\*)?(?:(?:Issue|Problem)\s*#?\s*)?(\d{1,3})\s*(?:[.):-]|\s)\s*", re.M | re.I)
_LABELS = "|".join(re.escape(x) for x in SEVERITIES)
# A severity is read only from its field: "Severity: <label>" anywhere, or field (2) / "2." at the
# start of a line, or a line that is the label alone; always on word boundaries, so prose such
# as "Minority-owned" or "weakens a claim about wages" is never a severity.
_SEV_FIELD = re.compile(r"(?:\bseverity\s*[:\-]\s*\**\s*|^\s*(?:\(2\)|2[.)])\s*\**\s*|^\s*\**\s*)(" + _LABELS + r")\b(?=\s*\**\s*[.;,:)]?\s*(?:$|\s))",
                        re.I | re.M)
_PAGE = re.compile(r"(?:\bpages?\b|\bpp?\.)\s*[:*_]*\s*(?:printed\s*)?(\d{1,4})(?:\s*(?:-|to|–)\s*(\d{1,4}))?", re.I)
# The third field holds the page: "(3) 12 (PDF 14)" or "3. 12"; and a number directly before
# "(PDF n)" is the printed page whatever precedes it.
_PAGE_FIELD = re.compile(r"^\s*(?:\(3\)|3[.)])\s*(?:printed\s*(?:page\s*)?)?[:*_]*\s*(\d{1,4})(?:\s*(?:-|to|–)\s*(\d{1,4}))?", re.I | re.M)
_PAGE_BEFORE_PDF = re.compile(r"(\d{1,4})(?:\s*(?:-|to|–)\s*(\d{1,4}))?\s*\(\s*PDF\b", re.I)
_PDF_PAGE = re.compile(r"\bPDF\b\s*(?:page\s*)?[:*_]*\s*(\d{1,4})", re.I)


def _page_list(m) -> list:
    """The printed pages a match names: one page, or every page in a range."""
    first, last = int(m.group(1)), int(m.group(2)) if m.group(2) else None
    if last is None or last < first or last - first > 50:
        return [str(first)]
    return [str(n) for n in range(first, last + 1)]


def _printed_pages(block: str) -> list:
    for rx in (_PAGE, _PAGE_FIELD, _PAGE_BEFORE_PDF):
        m = rx.search(block)
        if m:
            return _page_list(m)
    return []


def _severity(block: str):
    m = _SEV_FIELD.search(block)
    return next((x for x in SEVERITIES if m and x.casefold() == m.group(1).casefold()), None) if m else None


def count_severity_labels(text: str) -> int:
    """How many severity fields the text holds, read the same way parse_issues_md reads one."""
    return len(_SEV_FIELD.findall(text))


_MARK = re.compile(r"^\s*(?:\((\d)\)|(\d)[.)])\s*")
_TITLE_SPLIT = re.compile(r"\s+(?=(?:severity\s*[:\-]|pages?\b|pp?\.))", re.I)
_FIELD_LABEL = re.compile(r"^\s*(?:what is wrong|what the paper claims(?: and what is wrong)?|the problem|problem|issue|description)\s*[:\-]\s*",
                          re.I)
_INLINE_SEV = re.compile(r"\bseverity\s*[:\-]\s*\**\s*(?:" + _LABELS + r")\**\s*[.;,]?", re.I)
_INLINE_PAGE = re.compile(r"(?:\bpages?\b|\bpp?\.)\s*[:*_]*\s*(?:printed\s*(?:page\s*)?)?[:,]?\s*\d{1,4}(?:\s*(?:-|to|–)\s*\d{1,4})?"
                          r"(?:\s*(?:[,;]|and)?\s*\(?\s*PDF\s*(?:page\s*)?\d{1,4}(?:\s*(?:-|to|–)\s*\d{1,4})?\s*\)?)?[.;,]?", re.I)
_INLINE_PDF = re.compile(r"\(?\s*(?:printed\s*)?\bPDF\s*(?:page\s*)?[:*_]*\s*\d{1,4}(?:\s*(?:-|to|–)\s*\d{1,4})?\s*\)?[.;,]?", re.I)
_LONE_LABEL = re.compile(r"^\s*\**\s*(?:" + _LABELS + r")\s*\**\s*[.;,]?\s*$", re.I)
_LONE_PAGE = re.compile(r"^\s*\**\s*(?:printed\s*(?:page\s*)?)?\d{1,4}(?:\s*(?:-|to|–)\s*\d{1,4})?\s*(?:\(\s*PDF[^)]*\))?\s*[.;,]?\s*$", re.I)


def _plain(text: str) -> str:
    text = re.sub(r"[*_`#]+", "", text)
    text = re.sub(r"^\s*(?:\(1\)|title)\s*[:.)-]?\s*", "", text, flags=re.I)
    text = re.sub(r"^\s*[:\-]\s*", "", text)
    return re.sub(r"\s+", " ", text).strip().rstrip(".:")


def merge_text(title: str, body_lines: list) -> str:
    """The title plus the "what is wrong" field: field markers, the title field, the severity and
    page fields, PDF pages, and the fix field (which runs to the end) are dropped, so two items
    on one page share no boilerplate and a baseline item meets a Plumb summary on its substance."""
    kept = []
    for line in body_lines:
        m = _MARK.match(line)
        field = int(m.group(1) or m.group(2)) if m else None
        rest = line[m.end():] if m else line
        head = re.sub(r"[*_`]+", "", rest).strip()
        if field == 5 or re.match(r"^\s*(?:fix|concrete fix|suggested fix|how to fix|remedy)\b", head, re.I):
            break
        if field == 1 or re.match(r"^\s*title\s*[:\-]", head, re.I):
            continue
        if field in (2, 3) and (_LONE_LABEL.match(head) or _LONE_PAGE.match(head) or _INLINE_PAGE.match(head)):
            continue
        if _LONE_LABEL.match(head) or _LONE_PAGE.match(head):
            continue
        head = _INLINE_SEV.sub(" ", head)
        head = _INLINE_PAGE.sub(" ", head)
        head = _INLINE_PDF.sub(" ", head)
        head = _FIELD_LABEL.sub("", head)
        head = re.sub(r"^\s*(?:what is wrong|the problem)\s*[:\-]\s*", "", head, flags=re.I)
        head = re.sub(r"\s+", " ", head).strip()
        if head and head not in ".;,:":
            kept.append(head)
    return re.sub(r"\s+", " ", (title + " " + " ".join(kept))).strip()


_HEADED = re.compile(r"^(?:#|\*\*|Issue\b|Problem\b)", re.I)


def _entry_starts(text: str) -> list:
    """Matches that start entries: the next number in sequence, on the first line, after a blank
    line, or as a heading (marks, bold, "Issue", "Problem"). A list inside a field runs on from
    the line above it, so it does not start an entry."""
    starts, want = [], 1
    for m in _ENTRY.finditer(text):
        if int(m.group(1)) != want:
            continue
        before = text[:m.start()].rstrip(" \t")
        line = text[m.start():text.find("\n", m.start()) if "\n" in text[m.start():] else len(text)]
        if before and not before.endswith("\n\n") and not _HEADED.match(line):
            continue
        starts.append(m)
        want += 1
    return starts


def parse_issues_md(text: str) -> list:
    """The numbered entries of a baseline issues.md: [{title, severity, pages, pdf_pages, text,
    body}]. Entries are found by their sequence number (1, 2, 3, ...) at the start of a line, as
    "N.", a bold "N. Title", "## Issue N: Title", or "Problem N - Title". The severity comes from
    its field only; the printed page from "page", "pp.", "p.", the third field, or a number before
    "(PDF n)", with "printed 12" and a range "4-6" read as such and the PDF page kept apart.
    `text` is the title and the "what is wrong" field (merge_text); `body` the whole block."""
    out = []
    starts = _entry_starts(text)
    for n, m in enumerate(starts):
        end = starts[n + 1].start() if n + 1 < len(starts) else len(text)
        block = text[m.end():end].strip()
        if not block:
            continue
        first, _, rest = block.partition("\n")
        parts = _TITLE_SPLIT.split(first, maxsplit=1)
        title = _plain(parts[0])
        body_lines = ([parts[1]] if len(parts) > 1 else []) + rest.split("\n")
        pdf = _PDF_PAGE.search(block)
        out.append({"title": title, "severity": _severity(block), "pages": _printed_pages(block),
                    "pdf_pages": [pdf.group(1)] if pdf else [], "text": merge_text(title, body_lines),
                    "body": text[m.start():end].strip()})
    return out


def check_parse(model: str, text: str, entries: list, accept: bool = False):
    """A run of record must parse to at least one entry, and to as many entries as severity
    fields; otherwise the parser missed something and the pool would be wrong. With `accept`
    (the --accept-parse-count flag, for a file a human has checked) a count mismatch is
    returned as a departure record instead of raised."""
    if not entries:
        raise PoolError(f"{model}: issues.md parsed to no entries; check the numbering in the file")
    labels = count_severity_labels(text)
    if labels != len(entries):
        if not accept:
            raise PoolError(f"{model}: issues.md parsed to {len(entries)} entries but {labels} severity labels; "
                            "check the file before pooling, or pass --accept-parse-count after checking it")
        return {"model": model, "entries": len(entries), "severity_labels": labels,
                "note": "parse count accepted by --accept-parse-count after a human check"}
    return None


def _run_of_record(out: Path) -> int:
    f = out / "manifest.json"
    if not f.is_file():
        return 1
    try:
        head = json.loads(f.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise PoolError(f"{f} is not valid JSON: {exc}")
    return int(head.get("run_of_record") or 1) if isinstance(head, dict) else 1


def baseline_candidates(out_dir, models=BASELINE_MODELS, with_counts: bool = False, accept_parse_count: bool = False,
                        departures=None) -> tuple:
    """(candidates, missing models[, parsed count per model]) from a baseline out folder: each
    model's run of record, as manifest.json names it, parsed from its issues.md and checked
    (check_parse; an accepted mismatch is appended to `departures`). A model whose run of record
    is not complete (no done marker) is listed as missing and contributes nothing. A candidate's
    merge text is the entry's title and "what is wrong" field; its raw is the whole block."""
    out = Path(out_dir)
    n = _run_of_record(out)
    cands, missing, counts = [], [], {}
    for model in models:
        folder = out / model / f"run-{n}"
        if not all((folder / name).is_file() for name in BASELINE_RUN_FILES):
            missing.append(model)
            continue
        text = (folder / "issues.md").read_text(encoding="utf-8")
        entries = parse_issues_md(text)
        departure = check_parse(model, text, entries, accept=accept_parse_count)
        if departure and departures is not None:
            departures.append(departure)
        counts[model] = len(entries)
        for k, entry in enumerate(entries, 1):
            cands.append(_candidate(model, entry["text"], title=entry["title"], severity=entry["severity"],
                                    pages=entry["pages"], pdf_pages=entry["pdf_pages"], raw=entry["body"],
                                    ref=f"{model}:{k}"))
    return (cands, missing, counts) if with_counts else (cands, missing)


# --- deduplication across sources: the clusterer's groups, or the word-overlap rule in a dry run ---

# Ruling R2: more than half of the shorter text's content words in the longer; near misses from
# a share above 0.3, or the same text on different printed pages.
MERGE_SHARE = 0.5
NEAR_SHARE = 0.3


def overlap_share(a_text, b_text) -> float:
    """The share of the shorter text's content words (the scorer's content_words; shorter means
    fewer of them) found in the longer; 0 when the shorter has none."""
    want, have = sorted((fixture_score.content_words(a_text), fixture_score.content_words(b_text)), key=len)
    if not want:
        return 0.0
    return len(want & have) / len(want)


def _pages_agree(a: dict, b: dict) -> bool:
    """Printed pages are compared only when both candidates have them; PDF pages never count."""
    return not (a["pages"] and b["pages"]) or bool(set(a["pages"]) & set(b["pages"]))


def _same_claim(a: dict, b: dict) -> bool:
    return _pages_agree(a, b) and overlap_share(a["text"], b["text"]) > MERGE_SHARE


def _near_row(a: dict, b: dict, share: float, direction: str, reason: str) -> dict:
    return {"a": a["ref"], "b": b["ref"], "direction": direction, "share": round(share, 3), "reason": reason,
            "overlap_would_merge": a["source"] != b["source"] and _same_claim(a, b),
            "pages_a": a["pages"], "pages_b": b["pages"], "text_a": a["text"], "text_b": b["text"]}


def near_misses(claims: list, clustered: bool = False) -> list:
    """Pairs for the hand pass, judged by the word-overlap rule. Direction kept_apart: candidates
    from different sources in different claims with a share above NEAR_SHARE, or a share above
    MERGE_SHARE held apart by their pages; `overlap_would_merge` marks the pairs the overlap rule
    itself would have joined, which after clustering are the clusterer's splits to check. Two
    items from one source are that source's own two points and are never listed. With
    `clustered`, also direction merged: candidates the clusterer put in one claim whose share is
    below NEAR_SHARE, so the hand pass checks the clusterer's merges too."""
    out = []
    for i, ca in enumerate(claims):
        for cb in claims[i + 1:]:
            for a in ca["candidates"]:
                for b in cb["candidates"]:
                    if a["source"] == b["source"]:
                        continue
                    share = overlap_share(a["text"], b["text"])
                    if share <= NEAR_SHARE:
                        continue
                    reason = "pages" if share > MERGE_SHARE and not _pages_agree(a, b) else "share"
                    out.append(_near_row(a, b, share, "kept_apart", reason))
    if clustered:
        for claim in claims:
            members = claim["candidates"]
            for i, a in enumerate(members):
                for b in members[i + 1:]:
                    share = overlap_share(a["text"], b["text"])
                    if share < NEAR_SHARE:
                        out.append(_near_row(a, b, share, "merged", "share"))
    return out


def _union(home: dict, other: dict) -> None:
    for c in other["candidates"]:
        _add(home, c)


def apply_hand_merges(claims: list, pairs: list) -> dict:
    """Join the claims holding each pair of candidate refs, in place; a pair already in one claim
    is a no-op. Returns {pairs, merged, by_source} for pool.json."""
    by_source, merged = {}, 0
    for pair in pairs:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise PoolError(f"a hand merge is a pair of candidate refs, not {pair!r}")
        where = {}
        for ref in pair:
            for claim in claims:
                if any(c["ref"] == ref for c in claim["candidates"]):
                    where[ref] = claim
                    break
            else:
                raise PoolError(f"hand merge names {ref}, which is no candidate in this pool (see near_misses.json)")
        a, b = (where[ref] for ref in pair)
        if a is b:
            continue
        _union(a, b)
        claims.remove(b)
        merged += 1
        for ref in pair:
            src = next(c["source"] for c in a["candidates"] if c["ref"] == ref)
            by_source[src] = by_source.get(src, 0) + 1
    return {"pairs": [list(p) for p in pairs], "merged": merged, "by_source": by_source}


def load_hand_merges(path) -> list:
    import yaml
    p = Path(path)
    if not p.is_file():
        raise PoolError(f"--hand-merges {p} is missing")
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or []
    except yaml.YAMLError as exc:
        raise PoolError(f"{p} is not valid YAML or JSON: {exc}")
    if not isinstance(data, list):
        raise PoolError(f"{p} must be a list of [ref, ref] pairs")
    return data


UNTYPED = "untyped"
ADJUDICATIONS = ("paper", "external", "judgment")


def claim_adjudication(claim: dict) -> str:
    """The claim's adjudication type: the first Plumb candidate's (paper, external, judgment, or
    unknown for an orphaned overruled point); untyped when only baseline items hold it."""
    for c in claim["candidates"]:
        if c["source"] in (PLUMB_AUTO, PLUMB_STANDARD):
            return c.get("adjudication") if c.get("adjudication") in ADJUDICATIONS else UNKNOWN
    return UNTYPED


def _over_row(c: dict) -> dict:
    o = c["overruled"]
    return {"item": o["item"], "stop": o["stop"], "pack": c.get("pack"), "adjudication": c.get("adjudication"),
            "issue_id": c.get("issue_id"), "answer": o["answer"]}


def _new_claim() -> dict:
    return {"id": None, "sources": [], "source_severities": {}, "pages": [], "candidates": [], "overruled": [],
            "text": None}


def _higher(a, b):
    """The higher of two severities in SEVERITIES order; a missing severity ranks lowest."""
    rank = {s: n for n, s in enumerate(SEVERITIES)}
    return min((a, b), key=lambda s: rank.get(s, len(SEVERITIES)))


def _add(home: dict, c: dict) -> None:
    """Put a candidate in a claim. A source is labeled once, with the highest severity among its
    candidates in the claim (a clustered or hand-merged claim can hold two from one source); an
    overruled candidate adds its row to `overruled` and no label."""
    if c["overruled"]:
        home["overruled"].append(_over_row(c))
    elif c["source"] not in home["sources"]:
        home["sources"].append(c["source"])
        home["source_severities"][c["source"]] = c["severity"]
    else:
        home["source_severities"][c["source"]] = _higher(home["source_severities"][c["source"]], c["severity"])
    home["pages"] = sorted(set(home["pages"]) | set(c["pages"]), key=lambda p: (len(p), p))
    home["candidates"].append(c)


def merge(candidates: list, groups=None) -> list:
    """Claims from candidates. With `groups` (the clusterer's, as lists of candidate numbers from
    1, checked by parse_groups), each group is one claim, in the order given; one source may hold
    two candidates in a claim, as synthesis would merge them too. Without `groups` (the dry run's
    word-overlap rule), each candidate in order joins the first earlier claim that holds no
    candidate from its source and matches it, else starts a new claim. Either way every source
    label stays on the merged claim, with that source's own severity, and the pages are the union.
    An overruled candidate adds its row to `overruled` and no label: the reviewer dropped it, so
    it is not in that source's output."""
    claims = []
    if groups is not None:
        for group in groups:
            home = _new_claim()
            for k in group:
                _add(home, candidates[k - 1])
            claims.append(home)
    else:
        for c in candidates:
            home = None
            for claim in claims:
                if c["source"] in [x["source"] for x in claim["candidates"]]:
                    continue
                if any(_same_claim(c, other) for other in claim["candidates"]):
                    home = claim
                    break
            if home is None:
                home = _new_claim()
                claims.append(home)
            _add(home, c)
    for n, claim in enumerate(claims, 1):
        claim["id"] = f"c{n:02d}"
    return claims


# --- the rewrite: one pinned model, one fixed prompt, one call per claim ---

REWRITE_PROMPT_FILE = Path(__file__).resolve().parents[1] / "eval" / "pool_rewrite_prompt.txt"
# sha256 of eval/pool_rewrite_prompt.txt. The preregistration cites it; a changed file is refused.
REWRITE_PROMPT_SHA256 = "5f56eda83df1400e62968fe2515a2e453e500c743e21ec0eb5ed92b3f07d6cc2"
REWRITE_MODEL = "claude-fable-5-1"
REWRITE_EFFORT = "high"
# A ceiling, not a sampling parameter; a one-line answer never nears it, and a stop at the cap
# is an error.
REWRITE_MAX_TOKENS = 16000
REWRITES_FILE = "rewrites.json"
REWRITE_KEY_VAR = "ANTHROPIC_API_KEY"


def load_rewrite_prompt() -> str:
    import hashlib
    found = hashlib.sha256(REWRITE_PROMPT_FILE.read_bytes()).hexdigest()
    if found != REWRITE_PROMPT_SHA256:
        raise PoolError(f"{REWRITE_PROMPT_FILE.name} has sha256 {found}, not the pinned {REWRITE_PROMPT_SHA256}; the "
                        "rewrite prompt is fixed for the preregistration, so restore the file or update the pin and "
                        "the preregistration together")
    return REWRITE_PROMPT_FILE.read_text(encoding="utf-8").strip()


CLUSTER_PROMPT_FILE = REWRITE_PROMPT_FILE.parent / "pool_cluster_prompt.txt"
# sha256 of eval/pool_cluster_prompt.txt, fixed for the preregistration like the rewrite prompt's.
CLUSTER_PROMPT_SHA256 = "e09ab796ed8d317aceb7f5c98b8a9621aeeb4fd67fb451a0bf48871cc649b75e"


def load_cluster_prompt() -> str:
    import hashlib
    found = hashlib.sha256(CLUSTER_PROMPT_FILE.read_bytes()).hexdigest()
    if found != CLUSTER_PROMPT_SHA256:
        raise PoolError(f"{CLUSTER_PROMPT_FILE.name} has sha256 {found}, not the pinned {CLUSTER_PROMPT_SHA256}; the "
                        "clustering prompt is fixed for the preregistration, so restore the file or update the pin and "
                        "the preregistration together")
    # The header lines ("#") say what the prompt is for; they are hashed with the rest but not sent.
    text = CLUSTER_PROMPT_FILE.read_text(encoding="utf-8")
    return "\n".join(line for line in text.splitlines() if not line.startswith("#")).strip()


def rewrite_payload(claim: dict) -> str:
    """The user turn for one claim: each candidate's text with its pages, numbered, and nothing
    that names its source."""
    lines = []
    for n, c in enumerate(claim["candidates"], 1):
        lines.append(f"Comment {n} ({page_label(c['pages'])}): {c['text']}")
    return "\n\n".join(lines)


def call_rewrite(prompt: str, payload: str) -> dict:
    """claude-fable-5-1 over the Messages API: the prompt as the system text, the payload as the one
    user turn, effort high, no tools, no sampling parameters. The server-side fallbacks parameter is
    deliberately omitted: a pinned model must never be served by another, so a refusal, or any stop
    other than end_turn, is an error. Returns {text, model, usage, request_id}; the SDK loads only
    here, so the rest of Plumb never needs it."""
    return _call_model(prompt, payload, "rewrite")


def _require_key() -> None:
    import os
    if not os.environ.get(REWRITE_KEY_VAR):
        raise PoolError(f"missing {REWRITE_KEY_VAR} in the environment; export it or pass --no-rewrite")


def _call_model(prompt: str, payload: str, what: str, max_tokens: int = None, stream: bool = False) -> dict:
    """The one request shape both pool calls use (see call_rewrite). `what` names the step in
    errors. With `stream`, the request is streamed and the final message taken whole, so a large
    ceiling does not run into the HTTP timeout."""
    _require_key()
    import anthropic

    client = anthropic.Anthropic()
    request = dict(model=REWRITE_MODEL, max_tokens=max_tokens or REWRITE_MAX_TOKENS,
                   output_config={"effort": REWRITE_EFFORT}, system=prompt,
                   messages=[{"role": "user", "content": payload}])
    request_id = None
    if stream:
        with client.messages.stream(**request) as live:
            message = live.get_final_message()
            request_id = getattr(live, "request_id", None)
    else:
        message = client.messages.create(**request)
    if message.stop_reason != "end_turn":
        details = getattr(message, "stop_details", None)
        why = f" ({details.category}: {details.explanation})" if details is not None else ""
        raise PoolError(f"the {what} model stopped with {message.stop_reason}{why}; nothing was retried on another model")
    usage = getattr(message, "usage", None)
    return {"text": "".join(getattr(b, "text", "") for b in message.content if getattr(b, "type", "") == "text"),
            "model": getattr(message, "model", None), "request_id": getattr(message, "_request_id", None) or request_id,
            "usage": {"input_tokens": getattr(usage, "input_tokens", None), "output_tokens": getattr(usage, "output_tokens", None)}}


# --- the clustering: one call per paper groups the candidates by meaning ---

# The clustering runs on the rewrite's model at the same effort.
CLUSTER_MODEL = REWRITE_MODEL
CLUSTER_EFFORT = REWRITE_EFFORT
# A ceiling of its own: one reply lists every candidate of a paper. The call is streamed, and a
# stop at the cap is an error.
CLUSTER_MAX_TOKENS = 64000
CLUSTERS_FILE = "clusters.json"
_GROUP_LINE = re.compile(r"^\d+(?:\s*,\s*\d+)*$")


def cluster_order(candidates: list) -> list:
    """The order the clusterer sees the candidates in, as indexes into `candidates`: sorted by the
    sha256 of each candidate's ref and text, so the numbering follows no source and is the same on
    every rerun."""
    import hashlib

    def digest(n):
        c = candidates[n]
        return hashlib.sha256((str(c["ref"]) + "\n" + c["text"]).encode("utf-8")).hexdigest(), n

    return sorted(range(len(candidates)), key=digest)


def cluster_key(prompt: str, payload: str) -> str:
    """The cache key for one clustering request: the model, the effort, the prompt, and the payload."""
    import hashlib
    return hashlib.sha256(f"{CLUSTER_MODEL}\n{CLUSTER_EFFORT}\n{prompt}\n\n{payload}".encode("utf-8")).hexdigest()


def cluster_payload(candidates: list) -> str:
    """The user turn: each candidate's text and pages, numbered from 1, with no source label and
    no severity."""
    return "\n\n".join(f"Candidate {n} ({page_label(c['pages'])}): {c['text'] or c['title']}"
                       for n, c in enumerate(candidates, 1))


def parse_groups(text: str, n: int) -> list:
    """The groups in a clustering reply, as lists of candidate numbers from 1. Every line must be
    numbers separated by commas, and every number from 1 to n must appear exactly once."""
    groups, seen = [], set()
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        if not _GROUP_LINE.match(line):
            raise PoolError(f"the clustering reply line {line!r} is not a list of candidate numbers")
        group = [int(x) for x in line.split(",")]
        for k in group:
            if k < 1 or k > n:
                raise PoolError(f"the clustering reply names candidate {k}, but there are only {n}")
            if k in seen:
                raise PoolError(f"the clustering reply puts candidate {k} twice: candidate {k} is in more than one group")
            seen.add(k)
        groups.append(group)
    if not groups:
        raise PoolError("the clustering reply holds no groups")
    missing = [k for k in range(1, n + 1) if k not in seen]
    if missing:
        raise PoolError(f"the clustering reply leaves out candidates: candidate {missing[0]} is in no group"
                        + (f" (nor {', '.join(str(k) for k in missing[1:])})" if len(missing) > 1 else ""))
    return groups


def call_cluster(candidates: list) -> dict:
    """claude-fable-5-1 over the Messages API, as call_rewrite: the clustering prompt as the system
    text, the numbered candidates as the one user turn, effort high, a ceiling of
    CLUSTER_MAX_TOKENS, streamed, no tools, no fallbacks; any stop other than end_turn is an error. Returns {groups, model, usage, request_id}, the groups
    checked by parse_groups."""
    reply = _call_model(load_cluster_prompt(), cluster_payload(candidates), "clustering",
                        max_tokens=CLUSTER_MAX_TOKENS, stream=True)
    return {"groups": parse_groups(reply["text"], len(candidates)), "model": reply["model"],
            "usage": reply["usage"], "request_id": reply["request_id"]}


def _cached_groups(entry, n: int, path) -> list:
    """The groups in a cache entry, checked as a fresh reply is; anything else is an error."""
    groups = entry.get("groups") if isinstance(entry, dict) else None
    if not isinstance(groups, list) or not all(isinstance(g, list) and all(isinstance(k, int) for k in g) for g in groups):
        raise PoolError(f"{path} holds a malformed clustering entry; delete the file and run again")
    try:
        return parse_groups("\n".join(", ".join(str(k) for k in g) for g in groups), n)
    except PoolError as exc:
        raise PoolError(f"{path} holds a malformed clustering entry ({exc}); delete the file and run again")


def _mismatch(entries: dict, payload_sha256: str) -> str:
    """Why no entry in a --clusters-from file fits this pool, from the hashes each entry stores."""
    problems = set()
    for e in entries.values():
        if not isinstance(e, dict):
            continue
        if e.get("prompt_sha256") != CLUSTER_PROMPT_SHA256:
            problems.add(f"the clustering prompt differs (the file's sha256 {e.get('prompt_sha256')}, now {CLUSTER_PROMPT_SHA256})")
        if (e.get("request_model"), e.get("effort")) != (CLUSTER_MODEL, CLUSTER_EFFORT):
            problems.add(f"the model or effort differs (the file's {e.get('request_model')} at {e.get('effort')}, "
                         f"now {CLUSTER_MODEL} at {CLUSTER_EFFORT})")
        if e.get("payload_sha256") != payload_sha256:
            problems.add("the candidates differ (a run, the baseline, or a candidate's text or page changed)")
    return "; ".join(sorted(problems)) or "it holds no clustering entry"


def cluster(candidates: list, cache_file=None, from_file=None) -> dict:
    """Group the candidates: {groups, order, call}. The candidates are numbered for the clusterer in
    cluster_order and its groups are mapped back, so `groups` number `candidates` from 1, each group
    sorted and the groups in order of their first member; `order` lists the refs in the order sent.
    No call is made for fewer than two candidates (`call` is None). Otherwise the key is checked
    first and `call` records the returned model, usage, request id, and whether the reply came from
    `cache_file`, where a checked reply is stored under cluster_key so a rerun does not pay again.
    With `from_file` (a clusters-only run's sealed/clusters.json) no call is made: the entry for
    this prompt, model, effort, and payload is taken from it and checked, else the mismatch is
    named; the entry is copied to `cache_file`."""
    import hashlib
    order = cluster_order(candidates)
    refs = [candidates[i]["ref"] for i in order]
    if len(candidates) < 2:
        return {"groups": [[1]] if candidates else [], "order": refs, "call": None}
    _require_key()
    ordered = [candidates[i] for i in order]
    prompt, payload = load_cluster_prompt(), cluster_payload(ordered)
    key = cluster_key(prompt, payload)
    cache = _load_cache(cache_file)
    payload_sha256 = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    if from_file is not None:
        path = Path(from_file)
        if not path.is_file():
            raise PoolError(f"--clusters-from {path} is missing")
        source = _load_cache(path)
        if key not in source:
            raise PoolError(f"--clusters-from {path} holds no clustering for this pool: {_mismatch(source, payload_sha256)}")
        entry, cached = source[key], True
        sent = _cached_groups(entry, len(ordered), path)
        if cache_file is not None:
            cache[key] = entry
            Path(cache_file).parent.mkdir(parents=True, exist_ok=True)
            _json(Path(cache_file), cache)
    elif key in cache:
        entry, cached = cache[key], True
        sent = _cached_groups(entry, len(ordered), cache_file)
    else:
        entry, cached = call_cluster(ordered), False
        sent = entry["groups"]
        if cache_file is not None:
            cache[key] = dict(entry, request_model=CLUSTER_MODEL, effort=CLUSTER_EFFORT,
                              prompt_sha256=CLUSTER_PROMPT_SHA256,
                              payload_sha256=payload_sha256)
            Path(cache_file).parent.mkdir(parents=True, exist_ok=True)
            _json(Path(cache_file), cache)
    groups = sorted((sorted(order[k - 1] + 1 for k in g) for g in sent), key=lambda g: g[0])
    return {"groups": groups, "order": refs,
            "call": {"model": entry.get("model"), "usage": entry.get("usage"), "request_id": entry.get("request_id"),
                     "cached": cached}}


def _load_cache(path) -> dict:
    if path is None or not Path(path).is_file():
        return {}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except ValueError as exc:
        raise PoolError(f"{path} is not valid JSON: {exc}")
    return data if isinstance(data, dict) else {}


def rewrite(claims: list, cache_file=None) -> None:
    """Sets each claim's `text` to the model's one line and `rewrite` to the call's record. The key
    is checked before the first call. With `cache_file`, every finished rewrite is written there
    as it lands, keyed by the sha256 of the payload, and a rerun takes a cached line instead of
    paying for it again."""
    import hashlib
    import os
    if not os.environ.get(REWRITE_KEY_VAR):
        raise PoolError(f"missing {REWRITE_KEY_VAR} in the environment; export it or pass --no-rewrite")
    prompt = load_rewrite_prompt()
    cache = _load_cache(cache_file)
    for claim in claims:
        payload = rewrite_payload(claim)
        key = hashlib.sha256((prompt + "\n\n" + payload).encode("utf-8")).hexdigest()
        cached = key in cache
        if cached:
            reply = cache[key]
        else:
            try:
                reply = call_rewrite(prompt, payload)
            except PoolError as exc:
                raise PoolError(f"claim {claim['id']}: {exc}")
            if cache_file is not None:
                cache[key] = reply
                Path(cache_file).parent.mkdir(parents=True, exist_ok=True)
                _json(Path(cache_file), cache)
        line = str(reply.get("text") or "").strip()
        if not line:
            raise PoolError(f"the rewrite of claim {claim['id']} came back empty")
        if "\n" in line:
            raise PoolError(f"the rewrite of claim {claim['id']} is not one line: {line!r}")
        claim["text"], claim["rewritten"] = line, True
        claim["rewrite"] = {"model": reply.get("model"), "usage": reply.get("usage"), "request_id": reply.get("request_id"),
                            "cached": cached}


def unrewritten_text(claim: dict) -> str:
    """For a dry run: the first candidate's text, with the claim's pages in the one form."""
    c = claim["candidates"][0]
    return f"{c['text'] or c['title']} ({page_label(claim['pages'])})"


# --- the pool on disk ---

SHEET_COLUMNS = ("claim_id", "claim", "pages", "correct", "reason_if_incorrect", "importance", "recognized")
INSTRUCTIONS = """Rating sheet for the Plumb fall pilot.

Rate every claim, on your own, without discussing any claim with the other rater before both
sheets lock. A sheet locks only when every cell is filled.

Columns:
- correct: yes or no. Is the claim a correct statement about the paper?
- reason_if_incorrect: required when correct is no; one sentence.
- importance: one of "Undermines the main claim", "Weakens a claim", "Minor".
- recognized: yes or no. Tick yes when you think you know where this claim came from.

Do not open pool.json or mapping.sealed.json until both sheets lock.
"""


def _claim_record(claim: dict) -> dict:
    return {"id": claim["id"], "text": claim["text"], "rewritten": claim.get("rewritten", False),
            "rewrite": claim.get("rewrite"), "pages": claim["pages"], "adjudication": claim_adjudication(claim),
            "sources": claim["sources"], "source_severities": claim["source_severities"], "overruled": claim["overruled"],
            "candidates": [{k: c[k] for k in ("source", "text", "title", "severity", "pages", "issue_id", "item",
                                               "adjudication", "pack")} for c in claim["candidates"]]}


def shuffled_order(ids: list, seed: int, rater: str) -> list:
    """The claim ids in the order a rater's sheet lists them: a seeded RNG per (seed, rater)."""
    import random
    rng = random.Random(f"{seed}:{rater}")
    order = list(ids)
    rng.shuffle(order)
    return order


def assign_ids(claims: list, seed: int) -> None:
    """Random claim ids: a seeded permutation of zero-padded numbers, so an id says nothing about
    the order the sources came in (merge order puts Auto's issues first)."""
    import random
    ids = [f"c{n:02d}" for n in range(1, len(claims) + 1)]
    random.Random(f"{seed}:ids").shuffle(ids)
    for claim, cid in zip(claims, ids):
        claim["id"] = cid


REPO = Path(__file__).resolve().parents[1]
RATERS_DIR = "raters"
SEALED_DIR = "sealed"
DRY_RUN_BANNER = "DRY RUN: the claims are the sources' own text, not rewritten; do not rate this sheet"


def check_out(out: Path) -> None:
    """Refuse a folder inside the repo (pool outputs hold the pilot papers' issues) and one that
    already holds a finished pool."""
    try:
        out.resolve().relative_to(REPO.resolve())
    except ValueError:
        pass
    else:
        raise PoolError(f"--out {out} is inside the repo; pool outputs go outside it")
    if (out / SEALED_DIR / "pool.json").is_file() or (out / RATERS_DIR).is_dir():
        raise PoolError(f"{out} already holds a pool; a pool is built once per paper, so name another folder")
    stray = [p.name for p in out.iterdir() if p.name != SEALED_DIR] if out.is_dir() else []
    stray += ([p.name for p in (out / SEALED_DIR).iterdir() if p.name not in (REWRITES_FILE, CLUSTERS_FILE)]
              if (out / SEALED_DIR).is_dir() else [])
    if stray:
        raise PoolError(f"{out} holds files other than the clustering and rewrite caches ({', '.join(sorted(stray))}); "
                        "name an empty folder")


def _write_sheet(path: Path, claims_in_order: list, dry_run: bool) -> None:
    import csv
    with path.open("w", encoding="utf-8", newline="") as fh:
        if dry_run:
            fh.write(DRY_RUN_BANNER + "\n")
        w = csv.writer(fh)
        w.writerow(SHEET_COLUMNS)
        for c in claims_in_order:
            w.writerow([c["id"], c["text"], page_label(c["pages"]), "", "", "", ""])


def _json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _from_record(clusters_from):
    if clusters_from is None:
        return None
    import hashlib
    if not Path(clusters_from).is_file():
        raise PoolError(f"--clusters-from {clusters_from} is missing")
    return {"file": str(clusters_from), "sha256": hashlib.sha256(Path(clusters_from).read_bytes()).hexdigest()}


def build(paper: str, auto, standard, baseline, out, raters: tuple, seed=None, rewrite_claims: bool = True,
          hand_merges=None, author=None, nonauthor=None, joint: bool = False, accept_parse_count: bool = False,
          stop_after_clusters: bool = False, clusters_from=None) -> dict:
    """The pool for one paper, written to `out`: sealed/pool.json (everything, sources included),
    sealed/mapping.sealed.json (claim id to sources; the rating step never reads it on its own),
    raters/sheet-<rater>.csv with no source label, and raters/instructions.txt. A dry run names the
    sheets sheet-<rater>.DRYRUN.csv with a banner first row. Returns the pool, plus `merge_order`
    (the claims in the order they were built, not written to disk).

    The hand pass is a two-run workflow, so it checks the grouping that ships. With
    `stop_after_clusters` the run calls the clusterer, writes sealed/clusters.json and
    sealed/near_misses.json, and stops: no rewrite, no pool.json, no sheets. The real run then
    takes `clusters_from` (that sealed/clusters.json), reuses its checked groups without a call,
    applies `hand_merges`, rewrites, and writes the sheets; pool.json records the file and its
    sha256."""
    out = Path(out)
    if stop_after_clusters and not rewrite_claims:
        raise PoolError("--stop-after-clusters calls the clusterer, which --no-rewrite never does")
    if stop_after_clusters and hand_merges is not None:
        raise PoolError("--hand-merges belongs to the real run, after --stop-after-clusters; pass it with --clusters-from")
    if stop_after_clusters and clusters_from is not None:
        raise PoolError("--clusters-from belongs to the real run; a --stop-after-clusters run makes the groups")
    if clusters_from is not None and not rewrite_claims:
        raise PoolError("--clusters-from feeds the real run; a --no-rewrite dry run uses the overlap rule instead")
    check_out(out)
    if seed is None:
        # The id permutation and the shuffles follow from the seed and the claim count, so a seed
        # a rater could know would unblind the ids. Drawn here, stored only in sealed/pool.json.
        import secrets
        seed = secrets.randbits(63)
    for name, role in ((author, "--author"), (nonauthor, "--nonauthor")):
        if name is not None and name not in raters:
            raise PoolError(f"{role} {name!r} is not one of the raters ({', '.join(raters)})")
    if author is not None and author == nonauthor:
        raise PoolError("--author and --nonauthor must be different raters")
    sources, missing, candidates = {}, [], []
    if auto is not None:
        sources[PLUMB_AUTO] = str(auto)
        candidates += plumb_candidates(auto, PLUMB_AUTO)
    else:
        missing.append(PLUMB_AUTO)
    if standard is not None:
        sources[PLUMB_STANDARD] = str(standard)
        candidates += standard_candidates(standard)
    else:
        missing.append(PLUMB_STANDARD)
    counts, departures = {}, []
    if baseline is not None:
        cands, gone, counts = baseline_candidates(baseline, with_counts=True, accept_parse_count=accept_parse_count,
                                                  departures=departures)
        for model in BASELINE_MODELS:
            if model not in gone:
                sources[model] = str(Path(baseline) / model)
        candidates += cands
        missing += gone
    else:
        missing += list(BASELINE_MODELS)
    # The real run groups the candidates by meaning with the clusterer; the dry run, which makes
    # no API call, keeps the word-overlap rule.
    clustering = {"groups": [], "order": [], "call": None}
    if rewrite_claims:
        clustering = cluster(candidates, cache_file=out / SEALED_DIR / CLUSTERS_FILE, from_file=clusters_from)
        claims = merge(candidates, groups=clustering["groups"])
    else:
        claims = merge(candidates)
    # The near misses describe the grouping the hand pass was asked to check, so they are taken
    # before any hand merge. A hand merge can only join claims; it never splits a clusterer merge.
    near = near_misses(claims, clustered=rewrite_claims)
    if stop_after_clusters:
        sealed_dir = out / SEALED_DIR
        sealed_dir.mkdir(parents=True, exist_ok=True)
        if not (sealed_dir / CLUSTERS_FILE).is_file():
            _json(sealed_dir / CLUSTERS_FILE, {})
        _json(sealed_dir / "near_misses.json", near)
        return {"paper": paper, "clusters_only": True, "candidates": len(candidates), "claims": len(claims),
                "near_misses": len(near), "cluster": clustering["call"], "order": clustering["order"]}
    hand = {"file": None, "pairs": [], "merged": 0, "by_source": {}}
    if hand_merges is not None:
        hand = dict(apply_hand_merges(claims, load_hand_merges(hand_merges)), file=str(hand_merges))
    assign_ids(claims, seed)
    if rewrite_claims:
        rewrite(claims, cache_file=out / SEALED_DIR / REWRITES_FILE)
    else:
        for claim in claims:
            claim["text"], claim["rewritten"] = unrewritten_text(claim), False
    by_id = {c["id"]: c for c in claims}
    ids = sorted(by_id)
    order = {rater: shuffled_order(ids, seed, rater) for rater in raters}
    dry_run = not rewrite_claims
    pool = {"paper": paper, "seed": seed, "dry_run": dry_run,
            "merge": "cluster" if rewrite_claims else "overlap",
            "cluster": {"done": rewrite_claims, "model": CLUSTER_MODEL, "effort": CLUSTER_EFFORT,
                        "max_tokens": CLUSTER_MAX_TOKENS,
                        "prompt_file": CLUSTER_PROMPT_FILE.name, "prompt_sha256": CLUSTER_PROMPT_SHA256,
                        "groups": len(clustering["groups"]) if rewrite_claims else None,
                        "order": clustering["order"], "call": clustering["call"], "from": _from_record(clusters_from)},
            "rewrite": {"done": rewrite_claims, "model": REWRITE_MODEL, "effort": REWRITE_EFFORT,
                        "prompt_file": REWRITE_PROMPT_FILE.name, "prompt_sha256": REWRITE_PROMPT_SHA256},
            "sources": sources, "missing": missing, "raters": list(raters), "sheet_order": order,
            "author": author, "nonauthor": nonauthor, "joint": joint,
            "hand_merges": hand, "near_misses": len(near), "baseline_counts": counts,
            "accept_parse_count": accept_parse_count, "departures": departures,
            "claims": [_claim_record(by_id[cid]) for cid in ids]}
    sealed_dir, raters_dir = out / SEALED_DIR, out / RATERS_DIR
    sealed_dir.mkdir(parents=True, exist_ok=True)
    raters_dir.mkdir(parents=True, exist_ok=True)
    _json(sealed_dir / "pool.json", pool)
    _json(sealed_dir / "near_misses.json", near)
    _json(sealed_dir / "mapping.sealed.json", {
        "paper": paper, "missing": missing, "raters": list(raters), "author": author, "nonauthor": nonauthor, "joint": joint,
        "claims": {cid: {"sources": by_id[cid]["sources"], "source_severities": by_id[cid]["source_severities"],
                         "pages": by_id[cid]["pages"], "adjudication": claim_adjudication(by_id[cid]),
                         "overruled": by_id[cid]["overruled"]} for cid in ids}})
    for rater in raters:
        name = f"sheet-{rater}.DRYRUN.csv" if dry_run else f"sheet-{rater}.csv"
        _write_sheet(raters_dir / name, [by_id[cid] for cid in order[rater]], dry_run)
    (raters_dir / "instructions.txt").write_text(INSTRUCTIONS, encoding="utf-8")
    return dict(pool, merge_order=claims)
