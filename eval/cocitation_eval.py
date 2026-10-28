#!/usr/bin/env python3
"""How many works a referee said a paper should engage appear in the citation gap lists.

Usage:
    python3 eval/cocitation_eval.py <cases_dir> --split dev|test|all
        [--set NAME=VALUE ...] [--mailto ADDRESS] [--reach] --out <results.json>

<cases_dir> holds cases.json (a list of {"folder", "search_before", "missing_specific":
[{"authors", "year", "title"}], ...}), split.json ({"dev": [folders], "test": [folders]}), and one
folder per case with reference_list_input.txt. Each case runs cocitation.py in a scratch workspace.
Nothing in <cases_dir> is written except the reply cache in <cases_dir>/_cache. --out must be
outside the repository, because results name works from confidential referee reports. --set
overrides a cocitation.py setting for this run, for example --set TOP=25.

A named work counts as found when a listed work has the same first-author surname and a year at
most one apart, or when the two titles share at least TITLE_MATCH of their words.

With --reach, each named work is also found in OpenAlex by title and marked reachable when it is
in the script's backward or forward candidate pool (before filtering and ranking), so recall can
be read against the works any ranking could have listed.
"""
from __future__ import annotations

import argparse
import contextlib
import importlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "review" / "scripts"))
cc = importlib.import_module("cocitation")

TITLE_MATCH = 0.6
SETTABLE = {"TOP"}


# ---- matching ----

_LETTERS = str.maketrans({"ø": "o", "Ø": "O", "ł": "l", "Ł": "L", "ß": "ss", "æ": "ae", "Æ": "AE",
                          "đ": "d", "Đ": "D"})
_ET_AL = re.compile(r"\bet\.?\s*al\b\.?", re.I)
_SUFFIX = re.compile(r"(?:\b(?:jr|sr)\b\.?|\b(?:II|III|IV)\b)", re.I)
_STOP = {"about", "after", "among", "between", "from", "into", "over", "that", "their", "them", "then",
         "there", "these", "this", "those", "through", "under", "what", "when", "where", "which",
         "while", "with", "within", "without", "your", "have", "been", "does", "than", "towards"}


def _fold(text: str) -> str:
    """Lowercase ASCII letters, digits, and single spaces."""
    t = unicodedata.normalize("NFKD", (text or "").translate(_LETTERS)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", t.lower())).strip()


def _year(value):
    """The four-digit year at the start of `value` ("1954a" gives 1954), or None."""
    m = re.match(r"\d{4}", str(value).strip())
    return int(m.group(0)) if m else None


def first_surname(authors: str) -> str:
    """The first author's surname from "Fakeman, P. E., & Other, R." or "Paul E. Fakeman, Other"."""
    text = _SUFFIX.sub(" ", _ET_AL.sub(" ", authors or "")).strip()
    head = re.split(r"&|;|\band\b", text)[0]
    parts = [p.strip() for p in head.split(",") if p.strip()]
    if not parts:
        return ""
    # "Fakeman, P. E." puts the surname first; "Paul E. Fakeman" puts it last.
    if len(parts) > 1 and re.fullmatch(r"(?:[A-Z]\.?\s*)+", parts[1]):
        name = parts[0]
    else:
        name = parts[0].split()[-1]
    folded = _fold(name)
    return folded.split()[-1] if folded else ""


def _words(title: str) -> set:
    return set(_fold(title).split())


def _content(title: str) -> set:
    """Words of four or more letters that are not stopwords."""
    return {w for w in _words(title) if len(w) >= 4 and w not in _STOP}


def matches(missing: dict, row: dict) -> bool:
    surname = first_surname(missing.get("authors", ""))
    ym, yr = _year(missing.get("year")), _year(row.get("year"))
    close = ym is not None and yr is not None and abs(ym - yr) <= 1
    if surname and close and surname == first_surname(row.get("authors", "")):
        # A common surname and a nearby year are not enough when both titles are given and share
        # no content word.
        ca, cb = _content(missing.get("title", "")), _content(row.get("title", ""))
        if not (ca and cb) or ca & cb:
            return True
    a, b = _words(missing.get("title", "")), _words(row.get("title", ""))
    return bool(a and b) and len(a & b) / len(a | b) >= TITLE_MATCH


def match_row(missing: dict, data: dict):
    """The first listed work that `matches` the referee-named work, or None."""
    rows = list(data.get("classics") or []) + list(data.get("recent") or [])
    return next((r for r in rows if matches(missing, r)), None)


def found(missing: list, data: dict) -> list:
    return [match_row(m, data) is not None for m in missing]


# ---- running ----

ERROR_LINES = 5


def run_case(case: dict, cases_dir: Path, settings: dict, mailto: str = "",
             pools: bool = False) -> dict:
    """cocitation.json for one case, run in a scratch workspace, or {"error": ...}. The error
    holds the exit code and the last ERROR_LINES lines the script printed, with the API key
    blanked. With `pools`, the script also writes its candidate pools (--emit-pools)."""
    if not case.get("search_before"):
        return {"error": "no search cap"}
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "ws"
        (ws / "stage-1").mkdir(parents=True)
        shutil.copy(cases_dir / case["folder"] / "reference_list_input.txt",
                    ws / "stage-1" / "reference_list_input.txt")
        (ws / "run.json").write_text(json.dumps({"search_before": case["search_before"]}), encoding="utf-8")
        old = {k: getattr(cc, k) for k in list(settings) + ["CACHE_DIR", "MAILTO"]}
        old_vc_mailto = cc.vc.MAILTO
        os.environ["PLUMB_COCITATION_CACHE"] = str(cases_dir / "_cache")
        printed = io.StringIO()
        try:
            for k, v in settings.items():
                setattr(cc, k, v)
            with contextlib.redirect_stdout(printed):
                rc = cc.main([str(ws)] + ([mailto] if mailto else []) + (["--emit-pools"] if pools else []))
            tail = [cc._scrub(line) for line in printed.getvalue().splitlines() if line.strip()][-ERROR_LINES:]
        finally:
            for k, v in old.items():
                setattr(cc, k, v)
            cc.vc.MAILTO = old_vc_mailto
            os.environ.pop("PLUMB_COCITATION_CACHE", None)
        sys.stdout.write(cc._scrub(printed.getvalue()))
        out = ws / "stage-2" / "cocitation.json"
        if rc != 0 or not out.exists():
            return {"error": "\n".join([f"exit {rc}"] + tail)}
        return json.loads(out.read_text(encoding="utf-8"))


def named_id(missing: dict, memo: dict):
    """The OpenAlex id of a referee-named work, or None: one OpenAlex title search (years within
    one of the named year when there is one), taking the first result whose `_title_key` matches
    the named title's. Replies go through cocitation's reply cache; `memo` saves repeats within
    a run."""
    title, year = missing.get("title") or "", _year(missing.get("year"))
    key = cc._title_key(title)
    if not key:
        return None
    ask = (cc._clean_search(title), year)
    if ask not in memo:
        params = {"search": ask[0], "select": "id,title,display_name,publication_year", "per_page": 10}
        if year:
            params["filter"] = f"publication_year:{year - 1}-{year + 1}"
        results = cc._get(params).get("results") or []
        memo[ask] = next((cc._wid(w["id"]) for w in results if w.get("id")
                          and cc._title_key(w.get("title") or w.get("display_name") or "") == key), None)
    return memo[ask]


BUDGET = "unresolved (budget)"


def reach_of(missing: dict, pools: dict, memo: dict, cases_dir: Path, mailto: str = "",
             state: dict | None = None) -> str:
    """"backward:k" or "forward:k" (k links) when the named work is in that candidate pool
    (backward first), "none" when it resolves but is in neither, "unresolved" otherwise.
    `state` carries "cost" (OpenAlex dollars the lookups spent) and "budget" (True once OpenAlex
    refused with BudgetUsedUp; from then on no lookup is made and every work is BUDGET)."""
    state = {"cost": 0.0, "budget": False} if state is None else state
    if state["budget"]:
        return BUDGET
    old = (cc.CACHE_DIR, cc.MAILTO, cc.API_KEY)
    spent_before = cc.COST_USD
    try:
        cc.CACHE_DIR, cc.MAILTO = str(cases_dir / "_cache"), mailto
        cc.API_KEY = cc.API_KEY or cc._load_key()
        wid = named_id(missing, memo)
    except cc.BudgetUsedUp:
        print("Named-work lookups stopped: the OpenAlex budget is used up.", file=sys.stderr)
        state["budget"] = True
        return BUDGET
    except cc.vc.LookupUnavailable as exc:
        print(f"Named-work lookup failed: {cc._scrub(exc)}", file=sys.stderr)
        wid = None
    finally:
        cc.CACHE_DIR, cc.MAILTO, cc.API_KEY = old
        state["cost"] += cc.COST_USD - spent_before
    if wid is None:
        return "unresolved"
    for side in ("backward", "forward"):
        k = (pools.get(side) or {}).get(wid)
        if k:
            return f"{side}:{k}"
    return "none"


def _student(case: dict) -> bool:
    """Dissertation or proposal feedback, not a journal referee report."""
    return any(w in case.get("folder", "").lower() for w in ("dissertation", "proposal"))


def _macro(per_case: list, kind: str, keep=lambda c: True):
    """Mean over cases of the share of that case's missing works of this kind that were found.
    Each case counts once, so a case naming 18 works weighs no more than one naming 2."""
    shares = [c["by_kind"][kind]["found"] / c["by_kind"][kind]["missing"]
              for c in per_case if keep(c) and c["by_kind"].get(kind, {}).get("missing")]
    return round(sum(shares) / len(shares), 4) if shares else None


def _referee(m: dict) -> str:
    return f"{m.get('authors', '')} {m.get('year', '')}"


def evaluate(cases: list, cases_dir: Path, settings: dict, mailto: str = "",
             reach: bool = False) -> dict:
    """Recall over `cases`. With `reach`, each named work is also looked up in OpenAlex and marked
    reachable when it is in the script's backward or forward candidate pool, and the result adds
    reachable, found_among_reachable, and recall_reachable, overall and for substantive works."""
    per_case, hits, total, cost, memo = [], 0, 0, 0.0, {}
    state = {"cost": 0.0, "budget": False}
    tally = {"all": [0, 0], "substantive": [0, 0]}
    for case in cases:
        missing = case.get("missing_specific") or []
        data = run_case(case, cases_dir, settings, mailto, pools=reach)
        rows = [match_row(m, data) if "error" not in data else None for m in missing]
        got = [r is not None for r in rows]
        hits, total = hits + sum(got), total + len(missing)
        cost += float(data.get("openalex_cost_usd") or 0)
        by_kind = {}
        for m, g in zip(missing, got):
            k = by_kind.setdefault(m.get("kind") or "substantive", {"missing": 0, "found": 0})
            k["missing"] += 1
            k["found"] += int(g)
        row = {"folder": case["folder"], "missing": len(missing), "found": sum(got),
               "by_kind": by_kind, "student": _student(case),
               "unaided": str(case.get("report_ai_assisted", "")).lower() in ("no", "false"),
               "error": data.get("error"), "seeds": data.get("seeds"),
               "hits": [{"referee": _referee(m), "authors": r.get("authors"), "year": r.get("year"),
                         "title": r.get("title"), "id": r.get("id")}
                        for m, r in zip(missing, rows) if r is not None]}
        if reach and "pools" in data:
            where = [reach_of(m, data["pools"], memo, cases_dir, mailto, state) for m in missing]
            for m, g, w in zip(missing, got, where):
                if w.startswith(("backward:", "forward:")):
                    for kind in ("all", "substantive"):
                        if kind == "all" or (m.get("kind") or "substantive") == "substantive":
                            tally[kind][0] += 1
                            tally[kind][1] += int(g)
            row["misses"] = [{"referee": _referee(m), "reach": w}
                             for m, g, w in zip(missing, got, where) if not g]
        per_case.append(row)
    res = {"settings": settings, "cases": len(cases), "missing": total, "found": hits,
           "errors": [c["folder"] for c in per_case if c["error"]],
           "recall": round(hits / total, 4) if total else None,
           "substantive_macro": _macro(per_case, "substantive"),
           "substantive_macro_no_student": _macro(per_case, "substantive", lambda c: not c["student"]),
           "substantive_macro_unaided": _macro(per_case, "substantive", lambda c: c["unaided"]),
           "methods_macro": _macro(per_case, "methods"),
           "openalex_cost_usd": round(cost, 6)}
    if reach:
        for kind, prefix in (("all", ""), ("substantive", "substantive_")):
            n, k = tally[kind]
            res[f"{prefix}reachable"] = n
            res[f"{prefix}found_among_reachable"] = k
            res[f"{prefix}recall_reachable"] = round(k / n, 4) if n else None
        res["reach_cost_usd"] = round(state["cost"], 6)
        res["openalex_cost_usd"] = round(cost + state["cost"], 6)
        res["reach_budget_used_up"] = state["budget"]
    res["per_case"] = per_case
    return res


def _number(value: str):
    try:
        return int(value)
    except ValueError:
        return float(value)


def _inside_git_tree(path: Path, any_tree: bool = True) -> bool:
    """True when `path` (resolved) is, or lies under, ROOT or (with `any_tree`) a folder holding
    .git. Compared without regard to case, since macOS volumes usually are not case-sensitive."""
    p = path.resolve()
    root = str(ROOT.resolve()).casefold()
    for q in [p, *p.parents]:
        if str(q).casefold() == root or (any_tree and (q / ".git").exists()):
            return True
    return False


def main(argv: list | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("cases_dir")
    p.add_argument("--split", choices=["dev", "test", "all"], required=True)
    p.add_argument("--set", action="append", default=[], metavar="NAME=VALUE")
    p.add_argument("--mailto", default="")
    p.add_argument("--out", required=True)
    p.add_argument("--reach", action="store_true",
                   help="also report how many named works were in the candidate pools at all")
    a = p.parse_args(argv)
    out = Path(a.out).resolve()
    if _inside_git_tree(out):
        p.error("--out must be outside the repository and outside any git work tree")
    cases_dir = Path(a.cases_dir)
    if _inside_git_tree(cases_dir, any_tree=False):
        p.error("cases_dir must be outside the repository")
    settings = {}
    for s in a.set:
        name, _, value = s.partition("=")
        if name not in SETTABLE:
            p.error(f"--set {name}: not one of {sorted(SETTABLE)}")
        try:
            settings[name] = _number(value)
        except ValueError:
            p.error(f"--set {name}={value}: not a number")
    cases = json.loads((cases_dir / "cases.json").read_text(encoding="utf-8"))
    if a.split != "all":
        keep = set(json.loads((cases_dir / "split.json").read_text(encoding="utf-8"))[a.split])
        cases = [c for c in cases if c["folder"] in keep]
    res = evaluate(cases, cases_dir, settings, a.mailto, reach=a.reach)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=2), encoding="utf-8")
    line = (f"{settings}: {res['found']}/{res['missing']} found, recall {res['recall']}, "
            f"substantive macro {res['substantive_macro']}")
    if a.reach and res["reach_budget_used_up"]:
        line += "; reach lookups stopped: OpenAlex budget used up, later works marked unresolved (budget)"
    if a.reach:
        line += (f", reachable substantive {res['substantive_reachable']}, "
                 f"found among reachable {res['substantive_found_among_reachable']}")
    print(line + f", {res['cases']} cases, {len(res['errors'])} errors, OpenAlex ${res['openalex_cost_usd']}")
    if res["errors"]:
        print(f"Cases that errored: {', '.join(res['errors'])}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
