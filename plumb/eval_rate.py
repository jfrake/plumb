"""The preregistered numbers from two filled rating sheets and the sealed mapping that
eval/pool.py wrote. Validity is the paper's author's correctness call and importance the
non-author's severity call (the top two levels count); with --joint both raters must agree on
each. The headline, the count of valid and important claims found by only one source, is reported
under that rule and under full agreement, with percent agreement and Cohen's kappa, the share of
claims each rater recognized, the headline rerun on unrecognized claims, and for each point the
Standard reviewer overruled, whether the blind ratings sided with the reviewer or the tool.
`eval/rate_analysis.py` wraps `analyse` and prints JSON then markdown. The sealed mapping is
read only from the path the caller passes."""
from __future__ import annotations
import csv
from pathlib import Path

from .eval_pool import CONDITIONS
from .validated import SEVERITIES

SHEET_COLUMNS = ("claim_id", "claim", "pages", "correct", "reason_if_incorrect", "importance", "recognized")
TOP_TWO = tuple(SEVERITIES[:2])
YES_NO = {"yes": True, "no": False, "y": True, "n": False, "true": True, "false": False}
SIDES = ("tool", "reviewer", "partial")


class RateError(Exception):
    """A sheet or the mapping is missing, malformed, or not fully filled."""


# --- reading ---

def _yes_no(value, column, cid) -> bool:
    v = str(value or "").strip().casefold()
    if not v:
        raise RateError(f"claim {cid}: the {column} cell is blank; a sheet locks only when every cell is filled")
    if v not in YES_NO:
        raise RateError(f"claim {cid}: {column} must be yes or no, not {value!r}")
    return YES_NO[v]


def _importance(value, cid) -> str:
    v = str(value or "").strip()
    if not v:
        raise RateError(f"claim {cid}: the importance cell is blank; a sheet locks only when every cell is filled")
    for level in SEVERITIES:
        if v.casefold() == level.casefold():
            return level
    raise RateError(f"claim {cid}: importance must be one of {', '.join(SEVERITIES)}, not {value!r}")


def read_sheet(path) -> dict:
    """{claim id: {correct, reason, importance, recognized}} from a filled sheet. Every cell must be
    filled, a reason is required when correct is no, and a claim appears once."""
    path = Path(path)
    if not path.is_file():
        raise RateError(f"{path} is missing")
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if tuple(reader.fieldnames or ()) != SHEET_COLUMNS:
            raise RateError(f"{path}: the columns must be {', '.join(SHEET_COLUMNS)}")
        out = {}
        for row in reader:
            cid = str(row.get("claim_id") or "").strip()
            if not cid:
                raise RateError(f"{path}: a row has no claim id")
            if cid in out:
                raise RateError(f"{path}: claim {cid} appears twice")
            correct = _yes_no(row.get("correct"), "correct", cid)
            reason = str(row.get("reason_if_incorrect") or "").strip()
            if not correct and not reason:
                raise RateError(f"claim {cid}: marked incorrect with no reason; every incorrect needs one")
            out[cid] = {"correct": correct, "reason": reason, "importance": _importance(row.get("importance"), cid),
                        "recognized": _yes_no(row.get("recognized"), "recognized", cid)}
    if not out:
        raise RateError(f"{path}: no claims")
    return out


def read_mapping(path) -> dict:
    """The sealed mapping, from the path given and nowhere else."""
    import json
    path = Path(path)
    if not path.is_file():
        raise RateError(f"{path} is missing")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise RateError(f"{path} is not valid JSON: {exc}")
    if not isinstance(data, dict) or not isinstance(data.get("claims"), dict):
        raise RateError(f"{path} must be an object with a 'claims' mapping")
    return data


# --- rules ---

ADJUDICATION_ORDER = ("paper", "external", "judgment", "unknown", "untyped")
# Ruling R3, the side the blind ratings took on an overruled point.
SIDE_RULE = {"reviewer": "the claim was rated not valid",
             "tool": f"valid and rated {TOP_TWO[0]} or {TOP_TWO[1]}",
             "partial": "valid and rated Minor"}


def _judge(cid: str, sheets: dict, author: str, nonauthor: str, joint: bool) -> tuple:
    """(valid, important) under the primary rule."""
    a, n = sheets[author][cid], sheets[nonauthor][cid]
    if joint:
        return a["correct"] and n["correct"], a["importance"] in TOP_TWO and n["importance"] in TOP_TWO
    return a["correct"], n["importance"] in TOP_TWO


def _both(cid: str, sheets: dict) -> tuple:
    rows = [s[cid] for s in sheets.values()]
    return all(r["correct"] for r in rows), all(r["importance"] in TOP_TWO for r in rows)


def _share(part: int, whole: int) -> float:
    return round(100 * part / whole, 2) if whole else 0.0


def _counts(ids: list, verdicts: dict, claims: dict, labels: list, missing: list) -> dict:
    """Counts for one rule over the claim ids given: the valid and important claims, those found
    by only one source, and per source how many it shares in, how many are its alone, and that
    count as a share of all valid and important claims."""
    hits = [cid for cid in ids if all(verdicts[cid])]
    by_source = {label: {"any": 0, "only": 0} for label in labels}
    only, none = {}, []
    for cid in hits:
        srcs = claims[cid]["sources"]
        for s in srcs:
            by_source.setdefault(s, {"any": 0, "only": 0})["any"] += 1
        if len(srcs) == 1:
            by_source[srcs[0]]["only"] += 1
            only.setdefault(srcs[0], []).append(cid)
        elif not srcs:
            none.append(cid)
    # Ruling (minor 8): a claim credited to no source is out of the share's denominator and
    # counted apart.
    sourced = len(hits) - len(none)
    for label, row in by_source.items():
        row["only_share"] = _share(row["only"], sourced)
        row["status"] = "missing" if label in missing else "present"
    n_only = sum(len(v) for v in only.values())
    return {"claims": len(ids), "valid_important": hits, "sourced": sourced, "only_source": only, "no_source": none,
            "by_source": by_source, "only_any_source": {"count": n_only, "share": _share(n_only, sourced)}}


def _headline(ids: list, verdicts: dict, claims: dict, labels: list, missing: list) -> dict:
    """One rule's counts over every claim, split by adjudication type, and over every claim but
    the External ones, which the preregistration reports apart (the baselines ran without
    search and Plumb with a capped one)."""
    out = _counts(ids, verdicts, claims, labels, missing)
    out["by_adjudication"] = {
        adj: _counts([cid for cid in ids if claims[cid].get("adjudication", "untyped") == adj], verdicts, claims, labels, missing)
        for adj in ADJUDICATION_ORDER}
    out["external_apart"] = _counts([cid for cid in ids if claims[cid].get("adjudication") != "external"], verdicts,
                                    claims, labels, missing)
    return out


# --- agreement ---

def agreement(a: list, b: list) -> dict:
    """Percent agreement and Cohen's kappa for two raters' nominal labels, in claim order. When
    chance agreement is total (one label each), kappa is 1 for full agreement and 0 otherwise."""
    if len(a) != len(b) or not a:
        raise RateError("agreement needs two label lists of the same non-zero length")
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    cats = set(a) | set(b)
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    kappa = (1.0 if po == 1.0 else 0.0) if pe == 1.0 else (po - pe) / (1 - pe)
    return {"percent": round(100 * po, 2), "kappa": round(kappa, 4), "n": n}


def _agreement(rows: list) -> dict:
    """Correctness and three-level importance agreement from per-claim ratings keyed by role."""
    return {"correctness": agreement([r["correct"]["author"] for r in rows], [r["correct"]["nonauthor"] for r in rows]),
            "importance": agreement([r["importance"]["author"] for r in rows], [r["importance"]["nonauthor"] for r in rows])}


# --- the analysis ---

def _check_roles(sheets: dict, mapping: dict, author: str, nonauthor: str, joint: bool) -> None:
    raters = mapping.get("raters")
    if raters and sorted(raters) != sorted(sheets):
        raise RateError(f"the sheets are for {', '.join(sorted(sheets))} but the pool's raters are {', '.join(raters)}")
    for key, given, flag in (("author", author, "--author"), ("nonauthor", nonauthor, "--nonauthor")):
        if mapping.get(key) is not None and mapping[key] != given:
            raise RateError(f"{flag} {given!r} does not match the pool, built with {key} {mapping[key]!r}")
    if mapping.get("joint") is not None and bool(mapping["joint"]) != bool(joint):
        raise RateError("--joint " + ("was not given but the pool was built as the joint paper"
                                      if mapping["joint"] else "was given but the pool was not built as the joint paper"))


def _tally(overrides: list, key: str) -> dict:
    out = {}
    for row in overrides:
        cell = out.setdefault(str(row.get(key)), {s: 0 for s in SIDES})
        cell[row["sided_with"]] += 1
    return out


def analyse(sheets: dict, mapping: dict, author: str, nonauthor: str, joint: bool = False) -> dict:
    """Every number for one paper. `sheets` maps rater name to read_sheet output; the two raters
    must be the author and the non-author and the pool's raters, the roles must match what the
    pool recorded, and the sheets and the mapping must name the same claims."""
    if len(sheets) != 2:
        raise RateError("two sheets are needed, one per rater")
    for name in (author, nonauthor):
        if name not in sheets:
            raise RateError(f"rater {name!r} has no sheet; the sheets are for {', '.join(sheets)}")
    if author == nonauthor:
        raise RateError("--author and --nonauthor must be different raters")
    _check_roles(sheets, mapping, author, nonauthor, joint)
    claims = mapping["claims"]
    ids = sorted(claims)
    for name, ratings in sheets.items():
        gap = sorted(set(ids) ^ set(ratings))
        if gap:
            raise RateError(f"sheet {name} and the mapping disagree on the claims: {', '.join(gap)}")
    missing = list(mapping.get("missing") or [])
    labels = list(CONDITIONS)
    for cid in ids:
        for s in claims[cid]["sources"]:
            if s not in labels:
                labels.append(s)
    primary = {cid: _judge(cid, sheets, author, nonauthor, joint) for cid in ids}
    both = {cid: _both(cid, sheets) for cid in ids}
    roles = {"author": author, "nonauthor": nonauthor}
    rows = []
    for cid in ids:
        rows.append({"id": cid, "paper": mapping.get("paper"), "sources": claims[cid]["sources"],
                     "adjudication": claims[cid].get("adjudication", "untyped"), "overruled": claims[cid].get("overruled") or [],
                     "correct": {role: sheets[r][cid]["correct"] for role, r in roles.items()},
                     "importance": {role: sheets[r][cid]["importance"] for role, r in roles.items()},
                     "recognized": {role: sheets[r][cid]["recognized"] for role, r in roles.items()},
                     "primary": list(primary[cid]), "both_agree": list(both[cid])})
    unrec = [cid for cid in ids if not any(sheets[r][cid]["recognized"] for r in roles.values())]
    overrides = []
    for cid in ids:
        for o in claims[cid].get("overruled") or []:
            valid, important = primary[cid]
            side = "reviewer" if not valid else ("tool" if important else "partial")
            overrides.append({"id": cid, "paper": mapping.get("paper"), "item": o.get("item"), "stop": o.get("stop"),
                              "pack": o.get("pack"), "adjudication": o.get("adjudication"), "valid": valid,
                              "important": important, "sided_with": side})
    return {
        "paper": mapping.get("paper"), "author": author, "nonauthor": nonauthor, "joint": joint,
        "claims": len(ids), "sources": labels, "missing": missing,
        "rules": {"primary": _headline(ids, primary, claims, labels, missing),
                  "both_agree": _headline(ids, both, claims, labels, missing)},
        "validity_by_rater": {r: {"correct": sum(sheets[r][c]["correct"] for c in ids), "of": len(ids)} for r in roles.values()},
        "agreement": _agreement(rows),
        "recognized": {r: {"count": sum(sheets[r][c]["recognized"] for c in ids), "of": len(ids)} for r in roles.values()},
        "unrecognized": {"claims": unrec, "primary": _headline(unrec, primary, claims, labels, missing),
                         "both_agree": _headline(unrec, both, claims, labels, missing)},
        "overrides": {"claims": overrides, "by_stop": _tally(overrides, "stop"), "by_pack": _tally(overrides, "pack"),
                      "by_adjudication": _tally(overrides, "adjudication")},
        "claim_ratings": rows,
    }


# --- pooled across papers ---

def _pooled_counts(rows: list, rule: str, labels: list, missing_by_paper: dict) -> dict:
    hits = [r for r in rows if all(r[rule])]
    by_source = {label: {"any": 0, "only": 0} for label in labels}
    only, none = {}, []
    for r in hits:
        for s in r["sources"]:
            by_source.setdefault(s, {"any": 0, "only": 0})["any"] += 1
        if len(r["sources"]) == 1:
            by_source[r["sources"][0]]["only"] += 1
            only.setdefault(r["sources"][0], []).append(f"{r['paper']}:{r['id']}")
        elif not r["sources"]:
            none.append(f"{r['paper']}:{r['id']}")
    sourced = len(hits) - len(none)
    for label, row in by_source.items():
        row["only_share"] = _share(row["only"], sourced)
        row["papers_missing"] = [paper for paper, gone in missing_by_paper.items() if label in gone]
    n_only = sum(len(v) for v in only.values())
    return {"claims": len(rows), "valid_important": [f"{r['paper']}:{r['id']}" for r in hits], "sourced": sourced,
            "only_source": only, "no_source": none, "by_source": by_source,
            "only_any_source": {"count": n_only, "share": _share(n_only, sourced)}}


def pooled(results: list) -> dict:
    """The numbers over several papers' results (analyse output, or result.json): counts summed,
    agreement recomputed over every claim's ratings by role, the override table summed."""
    if not results:
        raise RateError("--pool needs at least one result file")
    papers = [r.get("paper") for r in results]
    rows = [row for r in results for row in r.get("claim_ratings") or []]
    if not rows:
        raise RateError("the result files carry no claim_ratings; rerun rate_analysis on each paper first")
    labels = list(CONDITIONS)
    for r in results:
        for s in r.get("sources") or []:
            if s not in labels:
                labels.append(s)
    missing = {r.get("paper"): list(r.get("missing") or []) for r in results}
    overrides = [o for r in results for o in r["overrides"]["claims"]]

    def rule(name, subset):
        out = _pooled_counts(subset, name, labels, missing)
        out["by_adjudication"] = {adj: _pooled_counts([x for x in subset if x["adjudication"] == adj], name, labels, missing)
                                  for adj in ADJUDICATION_ORDER}
        out["external_apart"] = _pooled_counts([x for x in subset if x["adjudication"] != "external"], name, labels, missing)
        return out

    unrec = [x for x in rows if not any(x["recognized"].values())]
    return {
        "papers": papers, "claims": len(rows), "sources": labels, "missing": missing,
        "per_paper": [{"paper": r.get("paper"), "claims": r["claims"], "author": r["author"], "nonauthor": r["nonauthor"],
                       "joint": r["joint"], "valid_important": len(r["rules"]["primary"]["valid_important"]),
                       "only_any_source": r["rules"]["primary"]["only_any_source"],
                       "by_source": {k: v["only"] for k, v in r["rules"]["primary"]["by_source"].items()},
                       "agreement": r["agreement"]} for r in results],
        "rules": {"primary": rule("primary", rows), "both_agree": rule("both_agree", rows)},
        "agreement": _agreement(rows),
        "recognized": {role: {"count": sum(x["recognized"][role] for x in rows), "of": len(rows)} for role in ("author", "nonauthor")},
        "unrecognized": {"claims": len(unrec), "primary": rule("primary", unrec), "both_agree": rule("both_agree", unrec)},
        "overrides": {"claims": overrides, "by_stop": _tally(overrides, "stop"), "by_pack": _tally(overrides, "pack"),
                      "by_adjudication": _tally(overrides, "adjudication")},
    }


# --- markdown ---

def _line(*cells) -> str:
    return "| " + " | ".join(str("" if c is None else c).replace("|", "/") for c in cells) + " |"


def _table(header: tuple, rows: list) -> list:
    return [_line(*header), "|" + "|".join("---" for _ in header) + "|"] + rows


def _source_rows(rule: dict, pooled_rows: bool = False) -> list:
    out = []
    for s, v in rule["by_source"].items():
        if v.get("status") == "missing":
            out.append(_line(s, "missing for this paper", ""))
        elif pooled_rows:
            out.append(_line(s, v["any"], f"{v['only']} ({v['only_share']:g}%)", ", ".join(v.get("papers_missing") or [])))
        else:
            out.append(_line(s, v["any"], f"{v['only']} ({v['only_share']:g}%)"))
    return out


def _rule_block(title: str, rule: dict, pooled_rows: bool = False) -> list:
    n = len(rule["valid_important"])
    lines = [f"### {title}", "",
             f"{n} of {rule['claims']} claims valid and important; {rule['only_any_source']['count']} "
             f"({rule['only_any_source']['share']:g}%) found by only one source"
             + (f"; {len(rule['no_source'])} held only by a point the Standard reviewer dropped, credited to no source "
                f"and counted apart (shares are over the {rule['sourced']} claims credited to a source)"
                if rule.get("no_source") else "") + ".", ""]
    header = ("source", "found", "only this source (share of valid and important)")
    lines += _table(header + (("missing on",) if pooled_rows else ()), _source_rows(rule, pooled_rows))
    if "by_adjudication" in rule:
        lines += ["", "By adjudication type (External apart: the baselines ran without search, Plumb with a capped one):", ""]
        lines += _table(("type", "claims", "valid and important", "only one source") + tuple(rule["by_source"]), [
            _line(adj, v["claims"], len(v["valid_important"]), v["only_any_source"]["count"],
                  *[v["by_source"].get(s, {}).get("only", 0) for s in rule["by_source"]])
            for adj, v in rule["by_adjudication"].items() if v["claims"]])
        ex = rule["external_apart"]
        lines += ["", f"Without External: {len(ex['valid_important'])} of {ex['claims']} valid and important; "
                      f"{ex['only_any_source']['count']} ({ex['only_any_source']['share']:g}%) found by only one source."]
    return lines + [""]


def _override_block(r: dict, with_paper: bool = False) -> list:
    lines = ["### overrides: where the blind ratings sided", "",
             "Side, under the primary rule: " + "; ".join(f"{k}: {v}" for k, v in SIDE_RULE.items()) + ".", ""]
    if not r["overrides"]["claims"]:
        return lines + ["None.", ""]
    head = (("paper",) if with_paper else ()) + ("claim", "item", "stop", "pack", "adjudication", "valid", "important", "sided with")
    lines += _table(head, [
        _line(*((o["paper"],) if with_paper else ()), o["id"], o["item"], o["stop"], o["pack"], o["adjudication"], o["valid"],
              o["important"], o["sided_with"]) for o in r["overrides"]["claims"]]) + [""]
    for key in ("by_stop", "by_pack", "by_adjudication"):
        lines += [f"#### {key.replace('_', ' ')}", ""] + _table(
            (key[3:], "tool", "reviewer", "partial"),
            [_line(k, v["tool"], v["reviewer"], v["partial"]) for k, v in r["overrides"][key].items()]) + [""]
    return lines


def markdown(r: dict) -> str:
    lines = [f"## {r.get('paper')}: ratings by {r['author']} (author) and {r['nonauthor']} (non-author)"
             + (", joint paper" if r["joint"] else ""), "",
             f"{r['claims']} claims; sources: {', '.join(r['sources'])}"
             + (f"; missing for this paper: {', '.join(r['missing'])}" if r.get("missing") else ""), ""]
    lines += _rule_block("headline, primary rule (author validity, non-author importance)", r["rules"]["primary"])
    lines += _rule_block("headline, both raters agree", r["rules"]["both_agree"])
    lines += ["### validity by rater", ""] + [f"- {name}: {v['correct']} of {v['of']} marked correct"
                                             for name, v in r["validity_by_rater"].items()] + [""]
    lines += ["### agreement", ""] + _table(("measure", "percent", "kappa", "n"), [
        _line(k, v["percent"], v["kappa"], v["n"]) for k, v in r["agreement"].items()]) + [""]
    lines += ["### recognized", ""] + [f"- {name}: {v['count']} of {v['of']} claims recognized"
                                      for name, v in r["recognized"].items()]
    lines += [f"- unrecognized by both: {len(r['unrecognized']['claims'])} claims", ""]
    lines += _rule_block("headline on unrecognized claims, primary rule", r["unrecognized"]["primary"])
    lines += _rule_block("headline on unrecognized claims, both agree", r["unrecognized"]["both_agree"])
    lines += _override_block(r)
    return "\n".join(lines)


def pooled_markdown(p: dict) -> str:
    lines = [f"## pooled over {len(p['papers'])} papers: {', '.join(str(x) for x in p['papers'])}", "",
             f"{p['claims']} claims; sources: {', '.join(p['sources'])}", "", "### per paper", ""]
    lines += _table(("paper", "claims", "author", "joint", "valid and important", "only one source", "correctness kappa",
                     "importance kappa") + tuple(p["sources"]), [
        _line(x["paper"], x["claims"], x["author"], x["joint"], x["valid_important"],
              f"{x['only_any_source']['count']} ({x['only_any_source']['share']:g}%)",
              x["agreement"]["correctness"]["kappa"], x["agreement"]["importance"]["kappa"],
              *[x["by_source"].get(s, 0) for s in p["sources"]]) for x in p["per_paper"]]) + [""]
    lines += _rule_block("pooled headline, primary rule", p["rules"]["primary"], pooled_rows=True)
    lines += _rule_block("pooled headline, both raters agree", p["rules"]["both_agree"], pooled_rows=True)
    lines += ["### pooled agreement", ""] + _table(("measure", "percent", "kappa", "n"), [
        _line(k, v["percent"], v["kappa"], v["n"]) for k, v in p["agreement"].items()]) + [""]
    lines += ["### recognized", ""] + [f"- {role}: {v['count']} of {v['of']} claims recognized" for role, v in p["recognized"].items()]
    lines += [f"- unrecognized by both: {p['unrecognized']['claims']} claims", ""]
    lines += _rule_block("pooled headline on unrecognized claims, primary rule", p["unrecognized"]["primary"], pooled_rows=True)
    lines += _override_block(p, with_paper=True)
    return "\n".join(lines)
