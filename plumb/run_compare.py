"""Compare repeat runs of one paper: match each run's `stage-5/issues.json` to the others' and
report how far the runs agree. Section 14 asks for three runs per paper; ruling 21 names the two
reliability numbers, the mean pairwise Jaccard overlap of major issues and the share of Judgment
items with identical calls across all runs.

Issues are matched one to one across runs by the fixture scorer's key. Runs are taken in the order
given; each later run's issues are tried against the groups built so far, strongest strategy first,
each strategy over every open group and every free issue before the next: a hand match from the
`--hand-matches` file; a check id both issues carry (`check`, `checks`, or a check id in `sources`),
with the page required to agree only when that id sits on more than one issue in either run; a check
id recovered from stage-4 for both excerpts, with the same page; then text overlap on title plus
summary plus excerpt, by the scorer's locator rule: one issue's excerpt inside the other's text, or
more than LOCATOR_SHARE of the smaller issue's content words (at least LOCATOR_MIN_WORDS) in the
other's. Within a strategy every allowed (group, issue) pair is ranked, excerpt containment first,
then word share, then input order, and assigned best first, so two similar issues listed in the
other order still pair with their twins. A text join is vetoed when any member of the group carries
explicit or recovered check ids disjoint from the candidate's. An issue that joins no group opens a
new one, so a run-2 issue can still meet a run-3 issue. A group holds at most one issue per run.

Major means severity in the top two labels. A Judgment item is a (stop, item) check-in answer at a
judgment stop (numbers, read, against, majors, minors, draft) in `audit/events.jsonl`, the final
answer per item as `checkin.final_answers` reads it, Auto answers included; setup answers are
preferences and are left out. Its call is identical when every run answered it with the same
option. Items are compared by their recorded id, so a numbered item (`majors:3`) compares the
third major of each run whether or not the runs numbered the same issue third. A Quick run writes
no stage-5/issues.json and counts as zero issues, as the scorer does.

Runs must be of one PDF: the `pdf_sha256` in run.json where every labeled run records one, else
the case-folded file name of `pdf_path`; a run with neither is compared on trust and the report says
so. Runs are named by the shortest trailing path that tells their folders apart, so three runs the
runner wrote on one day read as "o1/plumb_output/2026-10-05" and so on. `eval/compare_runs.py`
wraps `compare_paths` and prints the scorecard."""
from __future__ import annotations
import itertools
import re
from pathlib import Path

import yaml

from . import audit
from . import checkin
from . import fixture_score as fs
from .rundir import WORKSPACE
from .validated import SEVERITIES

MAJOR = tuple(SEVERITIES[:2])
JUDGMENT_STOPS = checkin.OVERRIDE_STOPS
SOURCES = ("hand", "check", "stage-4", "text")


class CompareError(Exception):
    """A required input is missing, has the wrong shape, or the runs are not of one paper."""


# --- loading ------------------------------------------------------------------------------------


def _run_dir(ws: Path) -> Path:
    return ws.parent if ws.name == WORKSPACE else ws


def run_names(dirs: list) -> list:
    """The shortest trailing path that tells the run folders apart, as "o1/plumb_output/2026-10-05"
    when three runs share a date folder name. One trailing part when the folder names already differ."""
    parts = [d.resolve().parts for d in dirs]
    for k in range(1, max(len(x) for x in parts) + 1):
        names = ["/".join(x[-k:]) for x in parts]
        if len(set(names)) == len(names):
            return names
    return ["/".join(x) for x in parts]


def load_runs(paths) -> list:
    """One record per run, in the order given: name, path, workspace, run.json, depth, issues,
    issues_from, stage-4 check table, and final check-in answers. Two runs is the minimum; the same
    run folder given twice is refused."""
    if len(paths) < 2:
        raise CompareError(f"at least two runs are needed to compare; {len(paths)} given.")
    out = []
    for p in paths:
        try:
            rec = fs.load_run(p)
        except fs.ScoreError as exc:
            raise CompareError(str(exc))
        ws = rec["workspace"]
        rec.update({"path": str(p), "dir": _run_dir(ws), "stage4": fs.stage4_checks(ws),
                    "answers": checkin.final_answers(audit.read_events(ws))})
        out.append(rec)
    resolved = [r["dir"].resolve() for r in out]
    for n, d in enumerate(resolved):
        if d in resolved[:n]:
            raise CompareError(f"the run {d} is given twice.")
    for r, name in zip(out, run_names([r["dir"] for r in out])):
        r["name"] = name
    return out


SHA_KEY = "pdf_sha256"


def paper_label(run: dict):
    """("sha256", <hash>) when run.json records `pdf_sha256`, else ("file", <basename, case folded>)
    from `pdf_path`, else None."""
    if run.get(SHA_KEY):
        return ("sha256", str(run[SHA_KEY]))
    if run.get("pdf_path"):
        return ("file", Path(str(run["pdf_path"])).name.casefold())
    return None


def check_same_paper(runs: list) -> dict:
    """The paper the runs share: {kind, value, unlabeled}, or CompareError naming each run's paper
    when they differ. The sha decides where every labeled run records one; otherwise the PDF's file
    name does, case folded, since the hash is not yet written by every run. A run with neither is
    listed under `unlabeled` and compared on trust."""
    labels = [paper_label(r["run"]) for r in runs]
    if not all(lab and lab[0] == "sha256" for lab in labels if lab):
        labels = [("file", Path(str(r["run"]["pdf_path"])).name.casefold()) if r["run"].get("pdf_path") else None
                  for r in runs]
    seen = {lab for lab in labels if lab}
    if len(seen) > 1:
        detail = "; ".join(f"{r['name']}: {lab[1] if lab else 'no pdf_path recorded'}" for r, lab in zip(runs, labels))
        raise CompareError(f"the runs are not of one paper ({detail}). Compare runs of the same PDF only.")
    lab = next(iter(seen), None)
    return {"kind": lab[0] if lab else None, "value": lab[1] if lab else None,
            "unlabeled": [r["name"] for r, lab in zip(runs, labels) if lab is None]}


# --- hand matches ---------------------------------------------------------------------------------


def _resolve_run(ref, runs: list) -> dict:
    """The run a hand-match entry names: by the run's name, or by a path to its folder or workspace."""
    ref = str(ref).strip()
    for r in runs:
        if ref == r["name"]:
            return r
    try:
        target = Path(ref).resolve()
    except OSError:
        target = None
    for r in runs:
        if target is not None and target in (r["dir"].resolve(), Path(r["workspace"]).resolve()):
            return r
    raise CompareError(f"hand match names a run that was not given: {ref!r} (runs: {', '.join(r['name'] for r in runs)}).")


def _resolve_end(end, runs: list) -> tuple:
    if not isinstance(end, dict) or "run" not in end or "id" not in end:
        raise CompareError(f"each end of a hand match must be a mapping with 'run' and 'id', not {end!r}.")
    r = _resolve_run(end["run"], runs)
    iid = str(end["id"]).strip()
    if iid not in {str(i["id"]) for i in r["issues"]}:
        raise CompareError(f"hand match names issue {iid!r} that run {r['name']} does not have.")
    return (r["name"], iid)


def load_hand_matches(path, runs: list) -> set:
    """{frozenset({(run name, issue id), (run name, issue id)})} from a YAML or JSON file: a list of
    pairs, each pair a list of two {run, id} mappings, or a mapping with that list under `matches`.
    A run is named by its folder name or the path given on the command line."""
    f = Path(path)
    if not f.is_file():
        raise CompareError(f"{f} is missing.")
    try:
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise CompareError(f"{f} is not valid YAML or JSON: {exc}")
    if isinstance(data, dict):
        data = data.get("matches")
    if data is None:
        return set()
    if not isinstance(data, list):
        raise CompareError(f"{f} must be a list of pairs (or a mapping with the list under 'matches').")
    out = set()
    for n, pair in enumerate(data, 1):
        if not isinstance(pair, list) or len(pair) != 2:
            raise CompareError(f"{f}: pair {n} must be a list of exactly two {{run, id}} mappings.")
        a, b = (_resolve_end(e, runs) for e in pair)
        if a[0] == b[0]:
            raise CompareError(f"{f}: pair {n} names two issues of the same run ({a[0]}).")
        out.add(frozenset({a, b}))
    # One issue cannot be the same as two different issues of one other run.
    partners = {}
    for pair in sorted(out, key=sorted):
        for end, other in ((min(pair), max(pair)), (max(pair), min(pair))):
            partners.setdefault(end, {}).setdefault(other[0], set()).add(other[1])
    for end, by_run in sorted(partners.items()):
        for run_name, ids in sorted(by_run.items()):
            if len(ids) > 1:
                raise CompareError(f"{f}: {end[0]}:{end[1]} is paired with two issues of {run_name}: "
                                   + ", ".join(f"{run_name}:{i}" for i in sorted(ids)) + ".")
    return out


def check_hand_pairs(groups: list, hand) -> None:
    """CompareError naming the first hand pair whose two issues did not end in one group (a third
    hand pair or an earlier join took the group's seat for that run)."""
    where = {(name, str(issue["id"])): n for n, g in enumerate(groups) for name, (issue, _) in g.items()}
    for pair in sorted(hand, key=sorted):
        a, b = sorted(pair)
        if where.get(a) != where.get(b):
            raise CompareError(f"hand match {a[0]}:{a[1]} and {b[0]}:{b[1]} could not be kept: the two issues "
                               f"ended in different groups because another match took the seat for that run.")


# --- matching -----------------------------------------------------------------------------------


def _recurring_checks(issues: list) -> set:
    counts = {}
    for i in issues:
        for c in fs.issue_checks(i):
            counts[c] = counts.get(c, 0) + 1
    return {c for c, n in counts.items() if n > 1}


def _same_page(a: dict, b: dict) -> bool:
    return fs._page(a) is not None and fs._page(a) == fs._page(b)


def _by_check(a: dict, b: dict, ra: dict, rb: dict) -> bool:
    shared = fs.issue_checks(a) & fs.issue_checks(b)
    if not shared:
        return False
    if shared & (ra["recurring"] | rb["recurring"]):
        return _same_page(a, b)
    return True


def _recovered(issue: dict, run: dict) -> set:
    return fs._cf(fs.recovered_checks(issue, {"stage4": run["stage4"]}))


def _by_stage4(a: dict, b: dict, ra: dict, rb: dict) -> bool:
    return bool(_recovered(a, ra) & _recovered(b, rb)) and _same_page(a, b)


def _vetoed(a: dict, b: dict, ra: dict, rb: dict) -> bool:
    """Check ids known for both issues that do not meet: the issues are about different checks."""
    for x, y in ((fs.issue_checks(a), fs.issue_checks(b)), (_recovered(a, ra), _recovered(b, rb))):
        if x and y and not (x & y):
            return True
    return False


def text_rank(a: dict, b: dict) -> tuple:
    """(containment, share): 1 when one issue's excerpt sits inside the other's title plus summary plus
    excerpt, and the share of the smaller issue's content words found in the other's."""
    ta, tb = fs._norm(fs.issue_text(a)), fs._norm(fs.issue_text(b))
    contain = any(ex and ex in text for ex, text in ((fs._norm(a.get("excerpt")), tb), (fs._norm(b.get("excerpt")), ta)))
    wa, wb = fs.content_words(ta), fs.content_words(tb)
    small = min(len(wa), len(wb))
    return (int(contain), len(wa & wb) / small if small else 0.0)


def _by_text(a: dict, b: dict, ra: dict, rb: dict) -> bool:
    """The scorer's locator rule: the excerpt inside the other text, or more than LOCATOR_SHARE of the
    smaller issue's content words (at least LOCATOR_MIN_WORDS) in the other's. The veto over the whole
    group is applied by `match`."""
    contain, share = text_rank(a, b)
    if contain:
        return True
    small = min(len(fs.content_words(fs.issue_text(a))), len(fs.content_words(fs.issue_text(b))))
    return small >= fs.LOCATOR_MIN_WORDS and share > fs.LOCATOR_SHARE


STRATEGIES = (("check", _by_check), ("stage-4", _by_stage4), ("text", _by_text))


def _candidates(groups: list, free: list, rb: dict, byname: dict, fn, veto: bool) -> list:
    """Every (group index, issue index) a strategy allows, best first: excerpt containment, then word
    share, then input order. A group's rank is its best member's. With `veto`, a member whose known
    check ids are disjoint from the candidate's blocks the join."""
    out = []
    for gi, g in enumerate(groups):
        if rb["name"] in g:
            continue
        for ii, b in enumerate(free):
            members = [(byname[ra], a) for ra, (a, _) in g.items()]
            if veto and any(_vetoed(a, b, ra, rb) for ra, a in members):
                continue
            ranks = [text_rank(a, b) for ra, a in members if fn(a, b, ra, rb)]
            if ranks:
                out.append((max(ranks), gi, ii))
    return sorted(out, key=lambda c: (-c[0][0], -c[0][1], c[1], c[2]))


def match(runs: list, hand=frozenset()) -> list:
    """Groups of issues judged the same across runs: [{run name: (issue, strategy)}], in the order
    the groups opened. The first run's issues each open a group; each later run's free issues join
    an open group lacking that run (hand matches first, then the automatic strategies, each over
    every group before the next, the best-ranked candidate pair first) or open one. The strategy is
    how the issue joined; a group's first issue has None."""
    for r in runs:
        r["recurring"] = _recurring_checks(r["issues"])
    byname = {r["name"]: r for r in runs}
    groups = [{runs[0]["name"]: (i, None)} for i in runs[0]["issues"]]
    for rb in runs[1:]:
        free = list(rb["issues"])

        def hand_fn(a, b, ra, rb_=rb):
            return frozenset({(ra["name"], str(a["id"])), (rb_["name"], str(b["id"]))}) in hand

        for name, fn in (("hand", hand_fn),) + STRATEGIES:
            taken_groups, taken_issues = set(), set()
            for _, gi, ii in _candidates(groups, free, rb, byname, fn, veto=(name == "text")):
                if gi in taken_groups or ii in taken_issues:
                    continue
                groups[gi][rb["name"]] = (free[ii], name)
                taken_groups.add(gi)
                taken_issues.add(ii)
            free = [b for ii, b in enumerate(free) if ii not in taken_issues]
        groups += [{rb["name"]: (i, None)} for i in free]
    return groups


# --- scorecard -----------------------------------------------------------------------------------


def _share(part: int, whole: int):
    return None if whole == 0 else part / whole


def major_overlap(rows: list, names: list) -> dict:
    """Pairwise Jaccard overlap of major issues, over matched groups: a group is in a run's major set
    when that run's member has a top-two severity. None where neither run has a major issue."""
    major = {name: {row["group"] for row in rows
                    if name in row["members"] and row["members"][name]["severity"] in MAJOR} for name in names}
    pairs = []
    for a, b in itertools.combinations(names, 2):
        shared, union = len(major[a] & major[b]), len(major[a] | major[b])
        pairs.append({"runs": [a, b], "shared": shared, "union": union, "jaccard": _share(shared, union)})
    defined = [p["jaccard"] for p in pairs if p["jaccard"] is not None]
    return {"pairs": pairs, "mean": sum(defined) / len(defined) if defined else None}


def _natural(text: str) -> tuple:
    """A sort key that puts majors:2 before majors:10."""
    return tuple(int(part) if part.isdigit() else part for part in re.split(r"(\d+)", str(text)))


def judgment_calls(runs: list) -> dict:
    """Judgment items with identical calls across every run: each (stop, item) answered at a judgment
    stop in any run, identical when every run answered it with the same option (`checkin._choice`).
    An item one run never answered is not identical."""
    names = [r["name"] for r in runs]
    keys = sorted({k for r in runs for k in r["answers"] if k[0] in JUDGMENT_STOPS},
                  key=lambda k: (checkin.STOP_STAGE[k[0]], _natural(k[1])))
    rows = []
    for stop, item in keys:
        calls = {r["name"]: (checkin._choice(r["answers"][(stop, item)]["answer"])
                             if (stop, item) in r["answers"] else None) for r in runs}
        same = len(set(calls.values())) == 1 and None not in calls.values()
        rows.append({"stop": stop, "item": item, "identical": same, "calls": calls})
    by_stop = {}
    for row in rows:
        s = by_stop.setdefault(row["stop"], {"items": 0, "identical": 0})
        s["items"] += 1
        s["identical"] += row["identical"]
    for s in by_stop.values():
        s["share"] = _share(s["identical"], s["items"])
    identical = sum(row["identical"] for row in rows)
    return {"items": len(rows), "identical": identical, "share": _share(identical, len(rows)),
            "by_stop": by_stop, "rows": rows}


def compare(runs: list, hand=frozenset()) -> dict:
    groups = match(runs, hand)
    check_hand_pairs(groups, hand)
    names = [r["name"] for r in runs]
    rows = []
    for n, g in enumerate(groups, 1):
        members = {name: {"id": str(g[name][0]["id"]), "severity": g[name][0].get("severity"),
                          "kind": g[name][0].get("kind"), "title": g[name][0].get("title"), "strategy": g[name][1]}
                   for name in names if name in g}
        sevs = {m["severity"] for m in members.values()}
        rows.append({"group": n, "runs": len(members), "members": members,
                     "severity_identical": None if len(members) < 2 else len(sevs) == 1})
    by_source = {s: 0 for s in SOURCES}
    for row in rows:
        for m in row["members"].values():
            if m["strategy"]:
                by_source[m["strategy"]] += 1
    matched = [row for row in rows if row["runs"] > 1]
    agreed = sum(1 for row in matched if row["severity_identical"])
    return {
        "runs": [{"name": r["name"], "path": r["path"], "workspace": str(r["workspace"]), "depth": r["depth"],
                  "issues": len(r["issues"]), "issues_from": r["issues_from"],
                  "major": sum(1 for i in r["issues"] if i.get("severity") in MAJOR)} for r in runs],
        "groups": rows,
        "matches_by_source": by_source,
        "unmatched": {name: [row["members"][name]["id"] for row in rows if row["runs"] == 1 and name in row["members"]]
                      for name in names},
        "major_overlap": major_overlap(rows, names),
        "severity_agreement": {"matched": len(matched), "identical": agreed, "share": _share(agreed, len(matched))},
        "judgment": judgment_calls(runs),
    }


def compare_paths(paths, hand_matches=None) -> dict:
    """The scorecard for the run folders (or workspaces) in `paths`, with the hand-match file applied
    first when given."""
    runs = load_runs([str(p) for p in paths])
    paper = check_same_paper(runs)
    hand = load_hand_matches(hand_matches, runs) if hand_matches else set()
    card = {"paper": paper,
            "hand_matches": {"file": None if hand_matches is None else str(hand_matches), "pairs": len(hand)}}
    card.update(compare(runs, hand))
    return card


# --- report ---------------------------------------------------------------------------------------


JUDGMENT_NOTE = ("Items are compared by their recorded id: numbered items (majors:N, minors:N) are compared by "
                 "number, not by matched issue, so a run that ordered its majors differently reads as a disagreement.")


def _fmt(x) -> str:
    return "none" if x is None else f"{x:.3f}"


def _count(part: int, whole: int) -> str:
    return f"{part} of {whole}" + ("" if whole == 0 else f" ({_fmt(part / whole)})")


def markdown(card: dict) -> str:
    """A short report: the runs, the reliability numbers, one row per matched group, the unmatched
    issues per run, and one row per Judgment item."""
    names = [r["name"] for r in card["runs"]]
    paper = card.get("paper") or {}
    hand = card.get("hand_matches") or {}
    unmatched = card["unmatched"]
    lines = [f"## {len(names)} runs of {paper.get('value') or 'an unnamed paper'}", ""]
    lines += [f"- {r['name']}: {r['path']}" for r in card["runs"]]
    if paper.get("unlabeled"):
        lines += ["", "runs with no PDF label (no pdf_path in run.json), compared on trust: "
                  + ", ".join(paper["unlabeled"])]
    lines.append("")
    if hand.get("pairs"):
        lines.append(f"hand matches: {hand['pairs']} pair{'s' if hand['pairs'] != 1 else ''} from {hand['file']}")
    else:
        lines.append("hand matches: none")
    lines += [""] + fs._table(("run", "depth", "issues", "major", "unmatched"),
                              [fs._line(r["name"], r["depth"], r["issues"], r["major"], len(unmatched[r["name"]]))
                               for r in card["runs"]])
    mo, j, sa = card["major_overlap"], card["judgment"], card["severity_agreement"]
    pairs = ", ".join(f"{p['runs'][0]} vs {p['runs'][1]} {_fmt(p['jaccard'])} ({p['shared']} of {p['union']})"
                      for p in mo["pairs"])
    lines += ["", "### reliability", "",
              f"- mean pairwise Jaccard overlap of major issues: {_fmt(mo['mean'])} ({pairs})"]
    if j["items"]:
        lines.append(f"- Judgment items identical across all runs: {_count(j['identical'], j['items'])}")
    else:
        lines.append("- Judgment items identical across all runs: none recorded")
    lines.append(f"  {JUDGMENT_NOTE}")
    lines += [f"  - {stop}: {_count(s['identical'], s['items'])}" for stop, s in j["by_stop"].items()]
    lines += [f"- severity agreement over matched issues: {_count(sa['identical'], sa['matched'])}",
              "- matches by source: " + ", ".join(f"{s} {n}" for s, n in card["matches_by_source"].items())]
    yes_no = {True: "yes", False: "no", None: ""}
    rows = []
    for g in card["groups"]:
        cells = [f"{g['members'][n]['id']} ({g['members'][n]['severity']})" if n in g["members"] else "" for n in names]
        strategies = ", ".join(m["strategy"] for m in g["members"].values() if m["strategy"])
        rows.append(fs._line(g["group"], *cells, yes_no[g["severity_identical"]], strategies))
    lines += ["", "### matched issue groups (one row per group; a blank cell means the run did not raise it)", ""]
    lines += fs._table(("group",) + tuple(names) + ("severity identical", "strategy"), rows) if rows else ["None."]
    lines += ["", "### unmatched issues per run", ""]
    lines += [f"- {n}: {', '.join(unmatched[n]) or 'none'}" for n in names]
    lines += ["", "### Judgment items", ""]
    if j["rows"]:
        lines += fs._table(("stop", "item") + tuple(names) + ("identical",),
                           [fs._line(r["stop"], r["item"], *[r["calls"][n] for n in names], yes_no[r["identical"]])
                            for r in j["rows"]])
    else:
        lines.append("None recorded at a judgment stop.")
    return "\n".join(lines) + "\n"
