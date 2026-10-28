"""Score a run against a fixture's answer key. The key is `fixtures/<id>/expected.yaml`
(must_catch, must_not_flag, also_fair); the run's issues are `stage-5/issues.json`. Each key
entry is matched to an issue by, in order: a check id the issue carries, a check id recovered
from the stage-4 file the issue came from, the locator sentence, or the page plus the check's
keywords. Assignment is one to one: each strategy runs over every unassigned entry and every
unassigned issue before the next strategy, and an issue leaves the pool once assigned. Where the
key holds the same check id in more than one entry, the two id strategies also need the issue's
page to agree. The strategy loop is the outer loop. Within one strategy, entries are tried in
the order must_catch, also_fair, must_not_flag, so where one issue matches several entries by
the same strategy, must_catch takes it first. The priority does not hold across strategies: a
must_not_flag entry that matches an issue by an earlier strategy (say, a check id) takes it
before a must_catch entry that would match it only by a later one (say, the locator). A check id recovered from stage-4 that is not the entry's check vetoes the locator and
page strategies for that issue. A Quick run writes no stage-5/issues.json; its checked facts in
stage-7/validated.json are scored instead, and with neither file it scores as zero issues.

A key entry may carry a `signature`: a list of case-insensitive regexes that name the planted
change. Such an entry is caught only by an issue whose full text (every string field of the issue,
see `issue_full_text`) matches at least one of them and whose page is within PAGE_TOLERANCE of the
entry's `page` or listed in the entry's optional `pages`. The signature strategy runs first; every
other strategy is held to the same test for a signed entry. Entries without a signature keep the
strategies above unchanged.
`eval/score_fixture.py` wraps `score_paths` and prints the scorecard."""
from __future__ import annotations
import json
import re
import unicodedata
from pathlib import Path

import yaml

from . import checkin
from . import depth as _depth
from .rundir import WORKSPACE
from .validated import FACT_KINDS, MERGED, SEVERITIES


class ScoreError(Exception):
    """A required input is missing or has the wrong shape."""


def workspace(path) -> Path:
    """The .workspace folder for a run folder or for the workspace itself."""
    p = Path(path)
    if (p / "run.json").is_file():
        return p
    if (p / WORKSPACE / "run.json").is_file():
        return p / WORKSPACE
    raise ScoreError(f"{p} is not a run folder: no run.json in it or in its {WORKSPACE}/.")


def load_key(fixture_dir) -> dict:
    f = Path(fixture_dir) / "expected.yaml"
    if not f.is_file():
        raise ScoreError(f"{f} is missing.")
    key = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    if not isinstance(key, dict):
        raise ScoreError(f"{f} must be a mapping.")
    for part in ("must_catch", "must_not_flag", "also_fair"):
        rows = key.get(part) or []
        if not isinstance(rows, list) or not all(isinstance(r, dict) and "check" in r for r in rows):
            raise ScoreError(f"{f}: {part} must be a list of entries with a 'check'.")
        for n, r in enumerate(rows):
            _check_signature(r, f"{f}: {part}[{n}]")
    return key


def _check_signature(entry: dict, where: str) -> None:
    """A `signature` must be a non-empty list of regexes that compile; `pages` a list of integers."""
    sig = entry.get("signature")
    if sig is not None:
        if not isinstance(sig, list) or not sig or not all(isinstance(s, str) and s for s in sig):
            raise ScoreError(f"{where}: signature must be a non-empty list of regex strings.")
        for s in sig:
            try:
                re.compile(s)
            except re.error as exc:
                raise ScoreError(f"{where}: signature {s!r} is not a valid regex: {exc}")
    pages = entry.get("pages")
    if pages is not None and (not isinstance(pages, list)
                              or not all(isinstance(p, int) and not isinstance(p, bool) for p in pages)):
        raise ScoreError(f"{where}: pages must be a list of integers.")


QUICK_NOTE = "Quick writes no stage-5/issues.json; every design entry counts as missed"


def run_record(ws) -> dict:
    f = Path(ws) / "run.json"
    try:
        run = json.loads(f.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ScoreError(f"{f} is not valid JSON: {exc}")
    if not isinstance(run, dict):
        raise ScoreError(f"{f} must be a JSON object.")
    return run


def run_depth(ws, run: dict) -> str:
    """The run's depth: run.json `depth` or `tier`, else the recorded setup:depth answer, else
    Standard, as plumb.depth.from_run reads them."""
    try:
        return _depth.from_run(run, checkin.answers(ws).get("setup:depth", ""))
    except ValueError as exc:
        raise ScoreError(f"{Path(ws) / 'run.json'}: {exc}")


VALIDATED_FIELDS = ("id", "kind", "title", "summary", "excerpt", "ms_page", "pdf_page", "severity",
                    "adjudication", "sources")


def validated_issues(ws) -> list:
    """The stage-7/validated.json records in the scorer's issue shape, or None when the file is
    absent. A Quick run writes no stage-5/issues.json, but its validated.json holds the checked
    facts, each with the quoted sentence and its page (see plumb/validated.py `_record`)."""
    f = Path(ws) / "stage-7" / "validated.json"
    if not f.is_file():
        return None
    try:
        rows = json.loads(f.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ScoreError(f"{f} is not valid JSON: {exc}")
    if not isinstance(rows, list) or not all(isinstance(r, dict) and "id" in r for r in rows):
        raise ScoreError(f"{f} must be a JSON list of records, each with an 'id'.")
    return [{k: r.get(k) for k in VALIDATED_FIELDS} for r in rows]


def load_run(run_dir) -> dict:
    """The run's workspace, run.json, depth, issues, and where the issues came from. The issues are
    stage-5/issues.json; without it, the stage-7/validated.json records (a Quick run runs Stages 0,
    1, 2, and 7 and writes only those). With neither, a Quick run scores as zero issues and any
    other depth is a ScoreError."""
    ws = workspace(run_dir)
    run = run_record(ws)
    depth = run_depth(ws, run)
    issues_file = ws / "stage-5" / "issues.json"
    if not issues_file.is_file():
        validated = validated_issues(ws)
        if validated is not None:
            source = "stage-7/validated.json" + (" (Quick: checked facts only)" if depth == "quick" else "")
            return {"workspace": ws, "run": run, "depth": depth, "issues": validated, "issues_from": source}
        if depth == "quick":
            return {"workspace": ws, "run": run, "depth": depth, "issues": [],
                    "issues_from": f"none ({QUICK_NOTE})"}
        raise ScoreError(f"{issues_file} is missing: the run has no stage-5/issues.json "
                         "or stage-7/validated.json to score.")
    try:
        issues = json.loads(issues_file.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ScoreError(f"{issues_file} is not valid JSON: {exc}")
    if not isinstance(issues, list) or not all(isinstance(i, dict) and "id" in i for i in issues):
        raise ScoreError(f"{issues_file} must be a JSON list of issues, each with an 'id'.")
    return {"workspace": ws, "run": run, "depth": depth, "issues": issues, "issues_from": "stage-5/issues.json"}


def _tokens(text) -> set:
    """Case-folded alphanumeric tokens of a source or check field, so "design_checks.md:DD5" yields
    dd5, plus the whole string, so an id with punctuation (core:literature) matches as well."""
    text = str(text or "").strip().casefold()
    return (set(re.split(r"[^a-z0-9]+", text)) | {text}) - {""}


def issue_checks(issue: dict) -> set:
    """Check ids the issue itself carries, case folded: a `check` or `checks` field, or a token in
    `sources`."""
    out = set()
    for field in ("check", "checks"):
        v = issue.get(field)
        for x in v if isinstance(v, list) else [v]:
            if isinstance(x, str) and x.strip():
                out |= _tokens(x)
    for s in issue.get("sources") or []:
        out |= _tokens(s)
    return out


def _by_check(entry: dict, issue: dict, ctx: dict) -> bool:
    return str(entry["check"]).strip().casefold() in issue_checks(issue)


def _norm(text) -> str:
    """Whitespace collapsed, quotes and trailing period dropped, case folded."""
    t = unicodedata.normalize("NFKC", str(text or ""))
    t = re.sub(r"[\"\u201c\u201d\u2018\u2019']", "", t)
    return re.sub(r"\s+", " ", t).strip().rstrip(".").casefold()


_CHECK_LINE = re.compile(r"^\s*Check:\s*(.+?)(?:\.\s|\.$|$)", re.M)
_EXCERPT_LINE = re.compile(r"^\s*Excerpt:\s*(.+)$", re.M)


def stage4_checks(ws) -> list:
    """[(normalized excerpt, {check ids})] for every entry under `## Issues` in stage-4/*.md.
    Pack agents write `Check: <id>` and `Excerpt: "<sentence>"` lines there; the compiler and
    synthesis drop the id, so the excerpt is the bridge back to it."""
    out = []
    for f in sorted(Path(ws).glob("stage-4/*.md")):
        text = f.read_text(encoding="utf-8")
        body = text.split("## Issues", 1)[1] if "## Issues" in text else ""
        body = re.split(r"^## ", body, maxsplit=1, flags=re.M)[0]
        # Only an unindented "<n>. " starts an entry; a numbered line inside the evidence does not.
        for block in re.split(r"^\d+\.\s", body, flags=re.M)[1:]:
            ids = set()
            for m in _CHECK_LINE.finditer(block):
                ids |= set(re.split(r"[\s,;()\[\]]+", m.group(1).strip())) - {""}
            ex = _EXCERPT_LINE.search(block)
            if ids and ex and _norm(ex.group(1)):
                out.append((_norm(ex.group(1)), ids))
    return out


def recovered_checks(issue: dict, ctx: dict) -> set:
    """The check ids the stage-4 files give the issue's excerpt; empty when none is recovered."""
    ex = _norm(issue.get("excerpt"))
    out = set()
    if ex:
        for excerpt, ids in ctx.get("stage4") or []:
            if ex in excerpt or excerpt in ex:
                out |= ids
    return out


def _cf(ids) -> set:
    return {str(i).casefold() for i in ids}


def _by_stage4(entry: dict, issue: dict, ctx: dict) -> bool:
    return str(entry["check"]).casefold() in _cf(recovered_checks(issue, ctx))


def _vetoed(entry: dict, issue: dict, ctx: dict) -> bool:
    """A recovered stage-4 id that is not the entry's check vetoes the text strategies: the issue
    is known to be about another check. With nothing recovered, the text decides."""
    ids = _cf(recovered_checks(issue, ctx))
    return bool(ids) and str(entry["check"]).casefold() not in ids


STOPWORDS = set("""a an the and or but of in on at to for by with from as is are was were be been being
this that these those it its into than then there their them they we our you your his her he she not no
nor so if when where which who whom whose what how all any each both more most other some such only own
same too very can will just do does did done have has had having also our between over under after before
above below up down out off again further once here about against during through because while until
""".split())
# "Most" of the locator's content words: more than half.
LOCATOR_SHARE = 0.5
LOCATOR_MIN_WORDS = 3


def _stem(word: str) -> str:
    """A light stem so "covariates", "moved", "moves", and "move" meet, as do "concludes" and
    "conclude": a plural, -ed, or -ing ending goes, then a final e."""
    if word.endswith("ies") and len(word) > 5:
        word = word[:-3] + "y"
    elif word.endswith("es") and len(word) > 5 and word[-3] in "sxz" or word.endswith(("ches", "shes")):
        word = word[:-2]
    elif word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        word = word[:-1]
    elif word.endswith("ed") and len(word) > 4:
        word = word[:-2]
    elif word.endswith("ing") and len(word) > 5:
        word = word[:-3]
    if word.endswith("e") and len(word) > 3:
        word = word[:-1]
    return word


def content_words(text) -> set:
    """Words that carry content: three letters or more, not a stopword, case folded, stemmed."""
    words = re.findall(r"[a-z0-9]+(?:[-'][a-z0-9]+)*", _norm(text))
    return {_stem(w) for w in words if len(w) >= 3 and w not in STOPWORDS}


def locator_sentence(locator) -> str:
    """The locator without its section label ("Appendix A: the sentence" gives "the sentence")."""
    text = str(locator or "").strip()
    head, sep, rest = text.partition(": ")
    if sep and rest and len(head.split()) <= 5:
        return rest
    return text


def issue_text(issue: dict) -> str:
    return " ".join(str(issue.get(k) or "") for k in ("title", "summary", "excerpt"))


def text_covers(sentence, text) -> bool:
    """Whether `text` covers `sentence`: the normalized sentence is inside the normalized text, or
    more than LOCATOR_SHARE of the sentence's content words (at least LOCATOR_MIN_WORDS of them)
    appear in the text. The locator strategy here and the pool's deduplication both use it."""
    sentence = _norm(sentence)
    if not sentence:
        return False
    if sentence in _norm(text):
        return True
    want = content_words(sentence)
    if len(want) < LOCATOR_MIN_WORDS:
        return False
    have = content_words(text)
    return len(want & have) / len(want) > LOCATOR_SHARE


def _by_locator(entry: dict, issue: dict, ctx: dict) -> bool:
    sentence = locator_sentence(entry.get("locator"))
    if not _norm(sentence) or _vetoed(entry, issue, ctx):
        return False
    return text_covers(sentence, issue_text(issue))


# The check's keywords are the checklist text plus the key entry's own note and locator, which
# describe the plant itself; checklist texts run long, so the share is low and the hit count carries.
KEYWORD_SHARE = 0.15
KEYWORD_MIN_HITS = 4


def pack_checks(pack_dir) -> dict:
    """{check id: text} from the pack's checklists/*.yaml and modules/*.yaml, read directly so a
    fixture can be scored without building the whole pack."""
    out = {}
    pack_dir = Path(pack_dir)
    for f in sorted(pack_dir.glob("checklists/*.yaml")):
        for item in yaml.safe_load(f.read_text(encoding="utf-8")) or []:
            if isinstance(item, dict) and item.get("id"):
                out[str(item["id"])] = str(item.get("text") or "")
    for f in sorted(pack_dir.glob("modules/*.yaml")):
        meta = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        for item in (meta.get("checklist") if isinstance(meta, dict) else None) or []:
            if isinstance(item, dict) and item.get("id"):
                out[str(item["id"])] = str(item.get("text") or "")
    return out


def _page(issue: dict):
    for k in ("ms_page", "pdf_page"):
        if issue.get(k) is not None:
            return str(issue[k]).strip()
    return None


def _by_page(entry: dict, issue: dict, ctx: dict) -> bool:
    if not _same_page(entry, issue) or _vetoed(entry, issue, ctx):
        return False
    want = content_words(" ".join([(ctx.get("checks") or {}).get(str(entry["check"]), ""),
                                   str(entry.get("note") or ""), locator_sentence(entry.get("locator"))]))
    if not want:
        return False
    hits = want & content_words(issue_text(issue))
    return len(hits) >= KEYWORD_MIN_HITS and len(hits) / len(want) >= KEYWORD_SHARE


def _strings(value):
    """Every string inside a value, depth first, through dicts and lists."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _strings(v)


def issue_full_text(issue: dict) -> str:
    """All string fields of the issue joined, for signature matching."""
    return " ".join(_strings(issue))


# A signed entry accepts an issue on its own page or this many pages either side.
PAGE_TOLERANCE = 1


def _near_page(entry: dict, issue: dict) -> bool:
    """The issue's page is within PAGE_TOLERANCE of the entry's page or is one of its `pages`."""
    try:
        got = int(str(_page(issue)))
    except ValueError:
        return False
    if got in (entry.get("pages") or []):
        return True
    page = entry.get("page")
    try:
        return page is not None and abs(got - int(page)) <= PAGE_TOLERANCE
    except (TypeError, ValueError):
        return False


def _signature_ok(entry: dict, issue: dict) -> bool:
    """True for an unsigned entry. For a signed one, the issue must match a signature regex and
    sit near the entry's page."""
    sig = entry.get("signature")
    if not sig:
        return True
    if not _near_page(entry, issue):
        return False
    text = issue_full_text(issue)
    return any(re.search(s, text, re.I) for s in sig)


def _by_signature(entry: dict, issue: dict, ctx: dict) -> bool:
    return bool(entry.get("signature")) and _signature_ok(entry, issue)


# Matching strategies, tried in this order over every issue before the next is tried.
STRATEGIES = (("signature", _by_signature), ("check", _by_check), ("stage-4", _by_stage4),
              ("locator", _by_locator), ("page", _by_page))


# Where one issue could belong to several entries, this order decides: must_not_flag is charged
# only for an issue nothing else explains.
PARTS = (("must_catch", "caught", "missed"), ("also_fair", "caught", "not caught"),
         ("must_not_flag", "flagged", "clean"))
# Strategies that read a check id; when the key holds that id in more than one entry, the page decides.
ID_STRATEGIES = ("check", "stage-4")


def _recurring(key: dict) -> set:
    seen, out = set(), set()
    for part, _, _ in PARTS:
        for entry in key.get(part) or []:
            cid = str(entry["check"])
            if cid in seen:
                out.add(cid)
            seen.add(cid)
    return out


def _same_page(entry: dict, issue: dict) -> bool:
    return entry.get("page") is not None and _page(issue) == str(entry["page"]).strip()


def assign(key: dict, issues: list, ctx: dict) -> dict:
    """{(part, index): (issue, strategy)} for every entry an issue explains. One issue goes to one
    entry: each strategy runs over every unassigned entry (must_catch, then also_fair, then
    must_not_flag, each in key order) and every unassigned issue before the next strategy, so a
    check-id match later in the key is never pre-empted by a locator match earlier in it."""
    recurring = _recurring(key)
    entries = [(part, n, e) for part, _, _ in PARTS for n, e in enumerate(key.get(part) or [])]
    free = list(issues)
    out = {}
    for name, fn in STRATEGIES:
        for part, n, entry in entries:
            if (part, n) in out:
                continue
            needs_page = name in ID_STRATEGIES and str(entry["check"]) in recurring
            for issue in free:
                if (fn(entry, issue, ctx) and (not needs_page or _same_page(entry, issue))
                        and _signature_ok(entry, issue)):
                    out[(part, n)] = (issue, name)
                    free.remove(issue)
                    break
    return out


def _row(entry: dict, issue, strategy, survived, merged=None) -> dict:
    row = {"check": str(entry["check"]), "page": entry.get("page"), "severity": entry.get("severity"),
           "result": None, "issue": None if issue is None else str(issue["id"]), "strategy": strategy,
           "survived": None if issue is None else survived.get(str(issue["id"]))}
    into = None if issue is None else (merged or {}).get(str(issue["id"]))
    if into is not None:
        row["merged_into"] = into
    # Optional key fields, carried only when the entry has them so older scorecards keep their shape.
    if entry.get("kind") is not None:
        row["kind"] = str(entry["kind"])
    if entry.get("signature"):
        row["signed"] = True
    return row


def _extra(issue: dict) -> dict:
    return {k: issue.get(k) for k in ("id", "kind", "severity", "adjudication", "ms_page", "title", "summary")}


def score(key: dict, issues: list, ctx=None) -> dict:
    """The scorecard for `issues` against `key`. ctx may carry `stage4` (from stage4_checks),
    `checks` ({check id: text}, from pack_checks), and `survived` ({issue id: bool}, from
    stage-7/validated.json), and `merged` ({issue id: the kept issue it was merged into}, from
    merged_into)."""
    ctx = dict(ctx or {})
    survived = ctx.get("survived") or {}
    merged = ctx.get("merged") or {}
    card = {"must_catch": [], "must_not_flag": [], "also_fair": []}
    matched = set()
    assigned = assign(key, issues, ctx)
    for part, hit, miss in PARTS:
        for n, entry in enumerate(key.get(part) or []):
            issue, strategy = assigned.get((part, n), (None, None))
            row = _row(entry, issue, strategy, survived, merged)
            row["result"] = miss if issue is None else hit
            if issue is not None:
                matched.add(str(issue["id"]))
            card[part].append(row)
    caught = {r["issue"] for r in card["must_catch"] if r["issue"] is not None}
    card["extras"] = [_extra(i) for i in issues if str(i["id"]) not in matched]
    extras = {e["id"] for e in card["extras"]}
    card["totals"] = {
        "must_catch": {"expected": len(card["must_catch"]),
                       "caught": sum(r["result"] == "caught" for r in card["must_catch"]),
                       "missed": sum(r["result"] == "missed" for r in card["must_catch"])},
        "must_not_flag": {"expected": len(card["must_not_flag"]),
                          "clean": sum(r["result"] == "clean" for r in card["must_not_flag"]),
                          "flagged": sum(r["result"] == "flagged" for r in card["must_not_flag"])},
        "also_fair": {"expected": len(card["also_fair"]),
                      "caught": sum(r["result"] == "caught" for r in card["also_fair"])},
    }
    card["by_severity"] = {
        sev: {"expected": sum(r["severity"] == sev for r in card["must_catch"]),
              "caught": sum(r["severity"] == sev and r["result"] == "caught" for r in card["must_catch"])}
        for sev in SEVERITIES}
    by_adj = {}
    for i in issues:
        adj = i.get("adjudication")
        if not adj:
            continue
        row = by_adj.setdefault(adj, {"issues": 0, "caught": 0, "extras": 0})
        row["issues"] += 1
        row["caught"] += str(i["id"]) in caught
        row["extras"] += str(i["id"]) in extras
    card["by_adjudication"] = by_adj
    return card


def _json(f):
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ScoreError(f"{f} is not valid JSON: {exc}")


def _kept(ws):
    """{issue id: its sources} for each issue stage-7/validated.json kept, or None when the file is
    absent."""
    f = Path(ws) / "stage-7" / "validated.json"
    if not f.is_file():
        return None
    return {str(r.get("source")): set(r.get("sources") or []) for r in _json(f)
            if isinstance(r, dict) and r.get("kind") not in FACT_KINDS}


def survived_ids(ws):
    """The issue ids stage-7/validated.json kept, or None when the file is absent (the run did not
    reach Stage 7), which leaves every row's `survived` None."""
    kept = _kept(ws)
    return None if kept is None else set(kept)


def merged_into(ws, issues) -> dict:
    """{issue id: the kept issue it was merged into} for issues the audit merged into an issue that
    stage-7/validated.json kept. The merge is read from `merged_from` in stage-6/issues.json. A run
    folder without that file (the stored runs in eval/runs/) falls back on stage-7/dropped.json,
    which names the merged issue but not its target; the target is the kept issue that carries the
    most of the merged issue's sources, and a tie names none."""
    ws = Path(ws)
    kept = _kept(ws) or {}
    out = {}
    stage6 = ws / "stage-6" / "issues.json"
    if stage6.is_file():
        for i in _json(stage6):
            if isinstance(i, dict) and str(i.get("id")) in kept:
                out.update({str(m): str(i["id"]) for m in i.get("merged_from") or []})
        return out
    dropped = ws / "stage-7" / "dropped.json"
    if not dropped.is_file():
        return out
    by_label = {str(i.get("checkin") or f"issue {i['id']}"): i for i in issues}
    for d in _json(dropped):
        issue = by_label.get(str(d.get("item"))) if isinstance(d, dict) and d.get("reason") == MERGED else None
        if issue is None:
            continue
        own = set(issue.get("sources") or [])
        shared = sorted(((len(own & s), k) for k, s in kept.items() if own & s), reverse=True)
        if shared and (len(shared) == 1 or shared[0][0] > shared[1][0]):
            out[str(issue["id"])] = shared[0][1]
    return out


def score_paths(fixture_dir, run_dir) -> dict:
    """The scorecard for the run folder (or its workspace) against the fixture folder's key."""
    fixture_dir = Path(fixture_dir).resolve()
    key = load_key(fixture_dir)
    run = load_run(run_dir)
    ws = run["workspace"]
    pack_dir = fixture_dir.parents[1]
    if run["issues_from"].startswith("stage-7/"):
        # The issues are the kept records themselves.
        survived, merged = {str(i["id"]): True for i in run["issues"]}, {}
    else:
        kept = survived_ids(ws)
        merged = {} if kept is None else merged_into(ws, run["issues"])
        survived = {} if kept is None else {str(i["id"]): str(i["id"]) in kept or str(i["id"]) in merged
                                            for i in run["issues"]}
    ctx = {"stage4": stage4_checks(ws), "checks": pack_checks(pack_dir), "survived": survived, "merged": merged}
    card = score(key, run["issues"], ctx)
    head = {
        "fixture": fixture_dir.name,
        "pack": pack_dir.name,
        "module": key.get("module"),
        "status": key.get("status", "pending_planting"),
        "run": str(ws),
        "depth": run["depth"],
        "packs": list(run["run"].get("packs") or []),
        "issues": len(run["issues"]),
        "issues_from": run["issues_from"],
    }
    head.update(card)
    return head


def _cell(value) -> str:
    return "" if value is None else re.sub(r"\s+", " ", str(value)).replace("|", "/").strip()


def _line(*cells) -> str:
    """One table row; an empty cell prints as a single space, so a row reads "| DD3 | 4 | | |"."""
    return "|" + "|".join(f" {_cell(c)} " if _cell(c) else " " for c in cells) + "|"


def _table(header: tuple, rows: list) -> list:
    return [_line(*header), "|" + "|".join("---" for _ in header) + "|"] + rows


def markdown(card: dict) -> str:
    """A short report: one table per key part, the totals, and the extras."""
    t = card["totals"]
    lines = [f"## {card.get('fixture', '')} ({card.get('pack', '')}) against {card.get('run', '')}", "",
             f"depth: {card.get('depth')}; packs: {', '.join(card.get('packs') or []) or 'none'}; "
             f"issues in the run: {card.get('issues', 0)}; issues from: {card.get('issues_from')}; "
             f"fixture status: {card.get('status')}", ""]
    lines += ["### must_catch", ""] + _table(
        ("check", "page", "severity", "result", "issue", "strategy"),
        [_line(r["check"], r["page"], r["severity"], r["result"], r["issue"], r["strategy"])
         for r in card["must_catch"]])
    for part, title in (("must_not_flag", "must_not_flag"), ("also_fair", "also_fair (never counted against)")):
        lines += ["", f"### {title}", ""] + _table(
            ("check", "page", "result", "issue", "strategy"),
            [_line(r["check"], r["page"], r["result"], r["issue"], r["strategy"]) for r in card[part]])
    lines += ["", "### totals", "",
              f"- must_catch: {t['must_catch']['caught']} of {t['must_catch']['expected']} caught",
              f"- must_not_flag: {t['must_not_flag']['clean']} of {t['must_not_flag']['expected']} clean",
              f"- also_fair: {t['also_fair']['caught']} of {t['also_fair']['expected']} caught"]
    lines += [f"- {sev}: {v['caught']} of {v['expected']} caught" for sev, v in card["by_severity"].items()]
    lines += [f"- adjudication {adj}: {v['issues']} issues, {v['caught']} caught, {v['extras']} extras"
              for adj, v in card["by_adjudication"].items()]
    lines += ["", "### extras: issues that match nothing in the key", ""]
    if card["extras"]:
        lines += _table(("id", "kind", "severity", "page", "summary"),
                        [_line(e["id"], e["kind"], e["severity"], e["ms_page"], e["summary"]) for e in card["extras"]])
    else:
        lines.append("None.")
    return "\n".join(lines) + "\n"
