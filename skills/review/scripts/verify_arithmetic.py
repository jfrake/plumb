#!/usr/bin/env python3
"""Deterministic arithmetic checks over reconciled table CSVs.

Schema-adaptive: each check runs only when its inputs are present in the CSV,
otherwise it emits status 'not_computable' and the LLM numeric-fidelity agent
covers it. Report-only (exit 0); findings are flags for downstream agents.

Significance marks: each table's note (table_NN_note.txt, copied by the transcribers with the
table's title) gives the key to the marks and what the parentheses hold. A mark is flagged only
when it claims more significance than the printed coefficient and standard error allow. A note
the parser cannot read is reported as not computable, never guessed.

Usage: verify_arithmetic.py <extracted_tables_dir> [out_md]
"""
from __future__ import annotations

import sys, csv, re, json, math
from pathlib import Path

import pvalues

_NUM = re.compile(r"-?\d*\.?\d+")
_ONE_TAILED = re.compile(r"one[- ]tail(?:ed)?|single[- ]tail(?:ed)?|one[- ]sided|1[- ]tail(?:ed)?", re.I)
_PRINTED = re.compile(r"^(<\s*=?\s*)?([-+]?(?:\d+\.?\d*|\.\d+))(?![\d.eE])")
_SCI = re.compile(r"[eE][-+]?\d")


def _cleaned(cell):
    """A cell's text with brackets and thousands commas removed, or None when empty."""
    if cell is None:
        return None
    s = str(cell).strip().replace(",", "").strip("[]()").rstrip("*\u2020\u2021 ").strip("[]()").strip()
    return s or None


def _printed(cell):
    """The number in a cell as printed (brackets and marks removed, "<" kept), or None."""
    if cell is None:
        return None
    s = str(cell).strip().replace("\u2212", "-").replace(",", "").strip("[]()").strip()
    m = _PRINTED.match(s)
    return ((m.group(1) or "").replace(" ", "") + m.group(2)) if m else None

# ---------------------------------------------------------------------------
# Header vocabulary (Gap 2)
# ---------------------------------------------------------------------------

# Recognised base tokens after normalisation (lower, strip trailing . , ;)
_SE_TOKENS = {
    "se", "s.e", "std err", "std. err", "std. error", "standard error", "stderr"
}
_P_TOKENS = {
    "p", "p-value", "p value", "pval", "p-val", "sig.", "sig",
    "pr(>|t|)", "pr(>|z|)", "p>|t|", "p>|z|"
}
_T_TOKENS = {
    "t", "t-stat", "t stat", "t value", "t-value",
    "z", "z-stat", "z stat", "z value", "z-value"
}

def _norm_header(h):
    """Normalise a header token for vocabulary lookup."""
    s = str(h).strip().lower().rstrip(".,;")
    return s

def _classify_header(raw):
    """Return 'coef', 'se', 'p', 't', or None for a raw header string."""
    n = _norm_header(raw)
    if n in _SE_TOKENS:
        return "se"
    if n in _P_TOKENS:
        return "p"
    if n in _T_TOKENS:
        return "t"
    # Treat anything with 'coef' or 'beta' or 'b' (exact) as coef
    if n in ("coef", "coefficient", "beta", "b", "estimate", "est", "coeff"):
        return "coef"
    return None

# ---------------------------------------------------------------------------
# Suffix extraction for wide multi-model layout (Gap 1)
# ---------------------------------------------------------------------------

_SUFFIX_RE = re.compile(
    r"^(.+?)[\s_]*"                 # base (non-greedy)
    r"[(_]?"                        # optional open paren or underscore
    r"(m?\d+|model\d+)"            # numeric or model-name suffix
    r"[)_]?$",                      # optional close paren or underscore
    re.IGNORECASE
)

def _split_suffix(token):
    """Return (base, suffix) by stripping a trailing numeric/model suffix, or None."""
    t = str(token).strip().lower().replace(" ", "_")
    # Remove trailing punctuation first
    t = t.rstrip(".,;")
    m = _SUFFIX_RE.match(t)
    if m:
        base = m.group(1).rstrip("_").rstrip(".")
        suffix = m.group(2).lstrip("m").lstrip("_") if m.group(2).lower().startswith("m") else m.group(2)
        # Normalise 'model1' -> '1'
        suffix = re.sub(r"^model", "", suffix.lower())
        return base, suffix
    return None

def _detect_wide_groups(header):
    """Detect wide multi-model layout.

    Returns a dict mapping suffix -> {col_type: [col_index, ...]}
    when at least two suffix groups each contain a coef column AND at least
    one SE-or-p column. Returns None when the layout is not wide multi-model.
    """
    groups = {}  # suffix -> {"coef": [], "se": [], "p": [], "t": []}
    for i, h in enumerate(header):
        if i == 0:
            continue  # skip the label column
        result = _split_suffix(h)
        if result is None:
            continue
        base, suffix = result
        col_type = _classify_header(base)
        if col_type is None:
            continue
        if suffix not in groups:
            groups[suffix] = {"coef": [], "se": [], "p": [], "t": []}
        groups[suffix][col_type].append(i)

    # Keep only groups that have at least a coef AND at least one SE or p
    valid = {
        s: g for s, g in groups.items()
        if g["coef"] and (g["se"] or g["p"])
    }
    if len(valid) >= 2:
        return valid
    return None


# ---------------------------------------------------------------------------
# Core parsing helpers
# ---------------------------------------------------------------------------

def _to_float(cell):
    if cell is None: return None
    s = str(cell).strip().strip("[]()").replace(",", "")
    m = _NUM.search(s)
    return float(m.group(0)) if m else None

def _parse_ci(cell):
    """Parse a confidence-interval cell like '[0.12, 0.45]' into (lo, hi) or None."""
    nums = _NUM.findall(str(cell))
    if len(nums) >= 2:
        return (float(nums[0]), float(nums[1]))
    return None

def _delim(cell):
    """Return 'paren', 'square', or 'none' for a bracketed value cell."""
    s = str(cell).strip()
    if s.startswith("(") and s.endswith(")"): return "paren"
    if s.startswith("[") and s.endswith("]"): return "square"
    return "none"

def _is_value_row(label):
    return str(label).strip() == ""  # interleaved SE/p rows have an empty Variables cell

def _classify_interleaved(values, delims):
    """Classify an interleaved row as 'se' or 'p'.
    Delimiter-first: square brackets -> p, parentheses -> se. A square-bracketed
    value > 1 stays 'p' on purpose so the pval_range check flags it as a malformed
    p-value rather than silently reclassifying it. Only when the delimiter does not
    decide (none/tie) does magnitude break the tie (any value > 1 cannot be a p)."""
    sq = delims.count("square"); pr = delims.count("paren")
    if sq > pr:
        return "p"
    if pr > sq:
        return "se"
    nums = [v for v in values if v is not None]
    if any(v > 1 for v in nums):
        return "se"
    return "p"


# ---------------------------------------------------------------------------
# parse_table_csv
# ---------------------------------------------------------------------------

def parse_table_csv(path, value_type="unknown"):
    with open(path, newline="") as fh:
        rows_raw = list(csv.reader(fh))
    if not rows_raw: return {"columns": [], "rows": []}
    header = rows_raw[0]
    model_cols = header[1:]

    # --- Gap 1: detect wide multi-model layout ---
    wide_groups = _detect_wide_groups(header)
    if wide_groups is not None:
        rows = []
        for r in rows_raw[1:]:
            label = r[0] if r else ""
            if not label.strip():
                continue
            coeffs, ses, pvals, tvals, raw, sci = {}, {}, {}, {}, {}, set()
            for suffix, g in wide_groups.items():
                cell = lambda idx: r[idx] if idx < len(r) else None
                raw[suffix] = {"coef": _printed(cell(g["coef"][-1])) if g["coef"] else None,
                               "se": _printed(cell(g["se"][-1])) if g["se"] else None,
                               "p": _cleaned(cell(g["p"][-1])) if g["p"] else None,
                               "t": _printed(cell(g["t"][-1])) if g["t"] else None}
                if any(_SCI.search(str(cell(idx) or "")) for k in ("coef", "se", "p", "t") for idx in g[k]):
                    sci.add(suffix)
                for ci in g["coef"]:
                    coeffs[suffix] = _to_float(r[ci]) if ci < len(r) else None
                for si in g["se"]:
                    ses[suffix] = _to_float(r[si]) if si < len(r) else None
                for pi in g["p"]:
                    pvals[suffix] = _to_float(r[pi]) if pi < len(r) else None
                for ti in g["t"]:
                    tvals[suffix] = _to_float(r[ti]) if ti < len(r) else None
            rows.append({
                "label": label,
                "coeffs": coeffs,
                "ses": ses,
                "pvals": pvals,
                "cis": {s: None for s in wide_groups},
                "stars": {},
                "_tvals": tvals,
                "_raw": raw,
                "_sci": sci,
            })
        return {"columns": list(wide_groups.keys()), "rows": rows}

    # --- Gap 2: detect explicit SE / p / t columns with broadened vocab ---
    lower_raw = header  # keep raw for index lookup
    se_idx = next(
        (i for i, h in enumerate(lower_raw) if _classify_header(h) == "se"),
        None
    )
    p_idx = next(
        (i for i, h in enumerate(lower_raw) if _classify_header(h) == "p"),
        None
    )
    t_idx = next(
        (i for i, h in enumerate(lower_raw) if _classify_header(h) == "t"),
        None
    )

    rows = []
    i = 1
    while i < len(rows_raw):
        r = rows_raw[i]
        label = r[0] if r else ""
        if se_idx is not None or p_idx is not None or t_idx is not None:
            # single-row layout: coeff in col 1, SE/p/t in their columns
            coeff = _to_float(r[1]) if len(r) > 1 else None
            se = _to_float(r[se_idx]) if se_idx is not None and len(r) > se_idx else None
            pv = _to_float(r[p_idx]) if p_idx is not None and len(r) > p_idx else None
            tv = _to_float(r[t_idx]) if t_idx is not None and len(r) > t_idx else None
            rows.append({
                "label": label,
                "coeffs": {"m": coeff},
                "ses": {"m": se},
                "pvals": {"m": pv},
                "cis": {"m": None},
                "stars": {"m": ""},
                "_tvals": {"m": tv},
                "_raw": {"m": {"coef": _printed(r[1]) if len(r) > 1 else None,
                               "se": _printed(r[se_idx]) if se_idx is not None and len(r) > se_idx else None,
                               "p": _cleaned(r[p_idx]) if p_idx is not None and len(r) > p_idx else None,
                               "t": _printed(r[t_idx]) if t_idx is not None and len(r) > t_idx else None}},
                "_sci": {"m"} if any(_SCI.search(r[k]) for k in (1, se_idx, p_idx, t_idx)
                                     if k is not None and k < len(r)) else set(),
            })
            i += 1
        else:
            # interleaved layout: coeff row, then a bracketed value row. The note-derived
            # value_type decides what that row holds; 'unknown' falls back to delimiter/magnitude.
            coeffs = {model_cols[j]: _to_float(r[j+1]) for j in range(len(model_cols)) if j+1 < len(r)}
            ses, pvals, cis = {}, {}, {}
            if i+1 < len(rows_raw) and _is_value_row(rows_raw[i+1][0] if rows_raw[i+1] else ""):
                pr = rows_raw[i+1]
                cells = {model_cols[j]: pr[j+1] for j in range(len(model_cols)) if j+1 < len(pr)}
                vals = {k: _to_float(v) for k, v in cells.items()}
                if value_type == "confidence_interval":
                    cis = {k: _parse_ci(v) for k, v in cells.items()}
                elif value_type == "standard_error":
                    ses = vals
                elif value_type == "p_value":
                    pvals = vals
                elif value_type == "t_statistic":
                    pass  # t-stats alone are not checkable here; numeric-fidelity agent covers
                else:  # unknown: delimiter/magnitude fallback
                    delims = [_delim(v) for v in cells.values()]
                    if _classify_interleaved(list(vals.values()), delims) == "se":
                        ses = vals
                    else:
                        pvals = vals
                i += 2
            else:
                i += 1
            if label.strip():
                rows.append({"label": label, "coeffs": coeffs, "ses": ses,
                             "pvals": pvals, "cis": cis, "stars": {}})
    return {"columns": model_cols, "rows": rows}


# ---------------------------------------------------------------------------
# run_checks
# ---------------------------------------------------------------------------

def _two_sided_p(t):
    # normal approximation; adequate for a consistency sanity check
    return 2 * (1 - 0.5 * (1 + math.erf(abs(t) / math.sqrt(2))))


def _t_vs_p(t_bounds, p_text, one_tailed=False):
    """Compare a printed p with the |t| bounds the printed digits allow. Returns the p range the
    digits allow when the printed p falls outside it, else None. The range runs from the normal
    (the smallest p, the reference for any over-claim; halved when the note states one-tailed tests)
    to Student t with 1 degree of freedom (the largest), because the paper rarely states its df."""
    printed = pvalues.printed_p_range(p_text) if p_text else None
    if t_bounds is None or printed is None:
        return None
    lo, hi = pvalues.p_normal(t_bounds[1]), pvalues.p_student(t_bounds[0], 1)
    if one_tailed:
        lo = lo / 2
    if printed[1] < lo or printed[0] > hi:
        return lo, hi
    return None

def run_checks(tables, one_tailed=()):
    findings = []
    for tname, t in tables.items():
        # Gap 3: surface parse errors immediately
        if t.get("error"):
            findings.append({
                "check": "parse_error",
                "table": tname,
                "cell": "-",
                "status": "error",
                "detail": f"CSV parse failed: {t['error']}",
            })
            continue

        t_vs_p_ran = False
        for row in t.get("rows", []):
            # pval_range: every present p must be in [0,1]
            for mdl, pv in row["pvals"].items():
                if pv is None: continue
                if pv < 0 or pv > 1:
                    findings.append({"check":"pval_range","table":tname,
                        "cell":f"{row['label']} / {mdl}","status":"error",
                        "detail":f"p={pv} outside [0,1]"})
            # se_positive: every present SE must be > 0 (coefficient-over-SE layout)
            for mdl, se in row["ses"].items():
                if se is None: continue
                if se <= 0:
                    findings.append({"check":"se_positive","table":tname,
                        "cell":f"{row['label']} / {mdl}","status":"error",
                        "detail":f"SE={se} is not positive"})
            # confidence-interval checks: ordered bounds, and the coefficient inside its CI
            for mdl, ci in row.get("cis", {}).items():
                if not ci: continue
                lo, hi = ci
                if lo > hi:
                    findings.append({"check":"ci_order","table":tname,
                        "cell":f"{row['label']} / {mdl}","status":"error",
                        "detail":f"CI [{lo}, {hi}] lower bound exceeds upper bound"})
                    continue
                coeff = row["coeffs"].get(mdl)
                if coeff is not None and not (lo <= coeff <= hi):
                    findings.append({"check":"ci_contains_coeff","table":tname,
                        "cell":f"{row['label']} / {mdl}","status":"error",
                        "detail":f"coeff {coeff} lies outside its CI [{lo}, {hi}]"})
            # t_vs_p: flag only when the old 0.02 rule and the rounding bounds both find a
            # mismatch, so this check adds no flag the old one did not raise.
            raw = row.get("_raw", {})
            # A coefficient, SE, t, or p printed in scientific notation is not read here.
            sci = row.get("_sci", set())
            one = tname in one_tailed
            ref = "normal, one-tailed," if one else "normal"
            for mdl, coeff in row["coeffs"].items():
                if mdl in sci:
                    continue
                se = row["ses"].get(mdl)
                pv = row["pvals"].get(mdl)
                if coeff is not None and se not in (None, 0) and pv is not None:
                    t_vs_p_ran = True
                    expected = _two_sided_p(coeff/se)
                    if abs(expected - pv) > 0.02 and not (expected < 0.001 and pv < 0.001):
                        cells = raw.get(mdl) or {}
                        b_text, se_text = cells.get("coef") or str(coeff), cells.get("se") or str(se)
                        bad = _t_vs_p(pvalues.abs_t_bounds(b_text, se_text), cells.get("p", str(pv)), one)
                        if bad:
                            findings.append({"check":"t_vs_p","table":tname,
                                "cell":f"{row['label']} / {mdl}","status":"error",
                                "detail":f"coeff/SE={b_text}/{se_text} implies p~{expected:.3f}; the printed digits "
                                         f"allow p {bad[0]:.3f} to {bad[1]:.3f} ({ref} to Student t with 1 df), "
                                         f"printed p={pv}"})
            # t_vs_p via explicit t-stat column (Gap 2 extension)
            tvals = row.get("_tvals", {})
            for mdl, tv in tvals.items():
                if mdl in sci:
                    continue
                pv = row["pvals"].get(mdl)
                if tv is not None and pv is not None:
                    t_vs_p_ran = True
                    expected = _two_sided_p(tv)
                    if abs(expected - pv) > 0.02 and not (expected < 0.001 and pv < 0.001):
                        cells = raw.get(mdl) or {}
                        t_text = cells.get("t") or str(tv)
                        bad = _t_vs_p(pvalues.abs_t_bounds_from_t(t_text), cells.get("p", str(pv)), one)
                        if bad:
                            findings.append({"check":"t_vs_p","table":tname,
                                "cell":f"{row['label']} / {mdl}","status":"error",
                                "detail":f"t={t_text} implies p~{expected:.3f}; the printed digits allow p "
                                         f"{bad[0]:.3f} to {bad[1]:.3f} ({ref} to Student t with 1 df), "
                                         f"printed p={pv}"})
        if not t_vs_p_ran:
            findings.append({"check":"t_vs_p","table":tname,"cell":"-",
                "status":"not_computable",
                "detail":"no coeff+SE+p triple in this layout; numeric-fidelity agent covers it"})
    return findings


# ---------------------------------------------------------------------------
# Significance marks: read the table note, then check each mark
# ---------------------------------------------------------------------------

_MARKS = "*†‡+#§"          # * dagger double-dagger + # section
_MARK_RUN = "[" + re.escape(_MARKS) + "]+"
# A note that says the table's significance does not come from coefficient / standard error.
_NOTE_SKIPS = [
    (r"\bstandardi[sz]ed (?:\w+ ){0,2}(?:coefficient|beta|estimate)|beta coefficients", "standardized coefficients"),
    (r"odds ratio", "odds ratios"),
    (r"hazard ratio", "hazard ratios"),
    (r"incidence[- ]rate ratio|\birrs?\b", "incidence-rate ratios"),
    (r"relative risk|risk ratio|\brrrs?\b", "relative risk ratios"),
    (r"exponentiated|\bexp\s*\(\s*b|\be\s?\^\s*\{?\s*b\b", "exponentiated coefficients"),
    (r"marginal effect", "marginal effects"),
    (r"bootstrap", "bootstrapped significance"),
    (r"permutation|randomi[sz]ation (?:inference|test)", "permutation or randomization tests"),
    (r"adjusted p|bonferroni|\bholm\b|false discovery|\bfdr\b|romano", "adjusted p-values"),
]
_P_TERM = (r"\bp[- ]?values?\b|\bprobability values?\b|\bsignificance levels?\b"
           r"|\bconfidence intervals?\b|\bcis?\b")
_CLAUSE = re.compile(r"(?<!\bs\.e)(?<!\be\.g)(?<!\bi\.e)(?<!\bstd)(?<!\bno)(?<!\bvs)\.\s+|;", re.I)
_SE_TERM = r"\bstandard errors?\b|\bstd\.?\s*errors?\b|\bs\.\s?e\.|\bses?\b"
_T_TERM = r"\bt[- ]?stat\w*|\bt[- ]?values?\b|\bt[- ]?ratios?\b|\bz[- ]?stat\w*|\bz[- ]?scores?\b|\bz[- ]?values?\b"
_GAP = r"[^" + re.escape(_MARKS) + r";,\n\d]"
# A mark pairs with a threshold only in a significance context: "p < x" or the word "significant".
_THRESHOLD = re.compile(
    r"(?P<mark>" + _MARK_RUN + r")" + _GAP + r"{0,40}?\bp\s*(?:<=|<|≤)\s*(?P<p>0?\.\d+)", re.I)
_THRESHOLD_PCT = re.compile(
    r"(?P<mark>" + _MARK_RUN + r")" + _GAP + r"{0,30}?signific\w*" + _GAP + r"{0,30}?"
    r"(?P<pct>\d+(?:\.\d+)?)\s*(?:%|percent|per cent)", re.I)
_KEY_CUE = re.compile(r"signific|\bp\s*(?:<=|<|≤|=)", re.I)
_RESPECTIVELY = re.compile(
    r"(?P<marks>(?:" + _MARK_RUN + r"\s*,?\s*(?:and|&)?\s*){2,})[^;]*?"
    r"(?P<levels>(?:\d*\.?\d+\s*(?:%|percent|per cent)?\s*,?\s*(?:and|&)?\s*){2,})[^;]*?respectively", re.I)
_P_THEN_MARK = re.compile(r"\bp\s*(?:<=|<|≤)\s*(?P<p>0?\.\d+)\s*[(\[]?\s*(?P<mark>" + _MARK_RUN + r")", re.I)


def _skip_reason(text):
    """Why a table's marks do not follow from coefficient over standard error, or None."""
    low = str(text or "").lower()
    for pattern, reason in _NOTE_SKIPS:
        if re.search(pattern, low):
            return f"the table reports {reason}, so the marks do not follow from coefficient and standard error"
    return None


def _value_kind(clause):
    """'se', 't', 'p' (p-values or intervals, which this check does not read), 'ambiguous', or None
    for the text that describes one set of parentheses or brackets. When p-terms and
    other terms compete, the term nearest the end (the parenthesis word) wins only if it is the p-term."""
    terms = [(m.end(), k) for k, pat in (("p", _P_TERM), ("se", _SE_TERM), ("t", _T_TERM))
             for m in re.finditer(pat, clause, re.I)]
    kinds = {k for _, k in terms}
    if "p" in kinds:
        if len(kinds) == 1 or max(terms)[1] == "p":
            return "p"
        return "ambiguous"
    if kinds == {"se"}:
        return "se"
    if kinds == {"t"}:
        return "t"
    if kinds == {"se", "t"}:
        if re.search(r"(?:" + _T_TERM + r").{0,40}?\b(?:based on|computed (?:from|with|using)|"
                     r"calculated (?:from|with|using)|using|from)\b.{0,40}?(?:" + _SE_TERM + ")",
                     clause, re.I):
            return "t"
        return "ambiguous"
    return None


def _clause_value_kinds(clause):
    """[(delimiter, kind)] for each 'parentheses' or 'brackets' in a clause. Each is described by
    the text before it since the previous such word, else by the text after it."""
    words = [(m.start(), m.end(), "(" if m.group(0).lower().startswith("parenthes") else "[")
             for m in re.finditer(r"parenthes\w*|bracket\w*", clause, re.I)]
    out = []
    for n, (start, end, delim) in enumerate(words):
        before = clause[(words[n - 1][1] if n else 0):start]
        after = clause[end:(words[n + 1][0] if n + 1 < len(words) else len(clause))]
        after = re.split(r"[,;]", after, maxsplit=1)[0]
        # "and" ends this delimiter's description only when the next delimiter word follows with its own kind.
        if n + 1 < len(words):
            head, sep, tail = after.partition(" and ")
            if sep and _value_kind(tail):
                after = head
        kind, later = _value_kind(before), _value_kind(after)
        if kind == "p":
            pass
        elif kind is None:
            kind = later
        elif later is not None and later != kind:
            kind = "ambiguous"
        out.append((delim, kind))
    return out


def parse_note(text):
    """Read a table note. Returns markers ({mark: threshold}), value_rows ({"(" or "[": "se" | "t"}),
    tails ("one", "two", or "unstated"), and skip_reason (None when the star check can run).
    Anything it cannot read is a skip, never a guess."""
    out = {"markers": {}, "value_rows": {}, "tails": "unstated", "skip_reason": None}
    note = " ".join(str(text or "").replace("−", "-").split())
    if not note:
        out["skip_reason"] = "no table note"
        return out
    low = note.lower()
    if _ONE_TAILED.search(low):
        out["tails"] = "one"
    elif re.search(r"two[- ]tailed|two[- ]sided|2[- ]tailed", low):
        out["tails"] = "two"
    skip = _skip_reason(note)
    if skip:
        out["skip_reason"] = skip
        return out
    pairs = []
    if "respectively" in low:
        for m in _RESPECTIVELY.finditer(note):
            if not _KEY_CUE.search(m.group(0)):
                continue
            marks = re.findall(_MARK_RUN, m.group("marks"))
            levels = [float(x) for x in re.findall(r"\d*\.?\d+", m.group("levels"))]
            if len(marks) == len(levels):
                pct = bool(re.search(r"%|percent|per cent", m.group("levels"), re.I))
                pairs += [(mk, lv / 100 if pct or lv >= 1 else lv) for mk, lv in zip(marks, levels)]
    if not pairs:
        for m in _THRESHOLD.finditer(note):
            pairs.append((m.group("mark"), float(m.group("p"))))
        for m in _THRESHOLD_PCT.finditer(note):
            pairs.append((m.group("mark"), float(m.group("pct")) / 100))
    if not pairs:
        pairs = [(m.group("mark"), float(m.group("p"))) for m in _P_THEN_MARK.finditer(note)]
    for mark, threshold in pairs:
        if out["markers"].get(mark, threshold) != threshold or not 0 < threshold <= 0.5:
            out["markers"] = {}
            out["skip_reason"] = "the note's key to the marks is inconsistent"
            return out
        out["markers"][mark] = threshold
    if not out["markers"]:
        out["skip_reason"] = "no key to the marks in the note"
        return out
    # Completeness guard: every mark run in a clause that gives the key must have been paired.
    # Letter marks (a, b, ...) are footnote labels and are ignored; they never carry a threshold.
    clauses = _CLAUSE.split(note)
    for clause in clauses:
        if _KEY_CUE.search(clause) and any(r not in out["markers"] for r in re.findall(_MARK_RUN, clause)):
            out["markers"] = {}
            out["skip_reason"] = "key not read: a mark in the note's key has no threshold I can pair with it"
            return out
    for clause in clauses:
        for delim, kind in _clause_value_kinds(clause):
            if kind == "ambiguous" or (kind and out["value_rows"].get(delim, kind) != kind):
                out["value_rows"] = {}
                out["skip_reason"] = "the note does not say clearly what the parentheses hold"
                return out
            if kind:
                out["value_rows"][delim] = kind
    if not any(k in ("se", "t") for k in out["value_rows"].values()):
        out["skip_reason"] = "the note does not say the parentheses hold standard errors or t statistics"
    return out


_COEF_CELL = re.compile(r"^([-+]?(?:\d+\.?\d*|\.\d+))\s*(\S*)$")
_SAME_CELL = re.compile(r"^([-+]?(?:\d+\.?\d*|\.\d+))\s*(" + _MARK_RUN + r")?[a-z]*\s*([(\[])\s*"
                        r"([-+]?(?:\d+\.?\d*|\.\d+))\s*[)\]]\s*(" + _MARK_RUN + r")?[a-z]*$")
_MARKED_NUMBER = re.compile(r"\d\s*%?\s*[)\]]?\s*" + _MARK_RUN + r"$")
_VALUE_CELL = re.compile(r"^([(\[])\s*([-+]?(?:\d+\.?\d*|\.\d+))\s*[)\]]\s*(\S*)$")
_FOOTNOTE_LETTERS = re.compile(r"[A-Za-z]+$")
_WINDOW = re.compile(r"^[(\[]\s*[-+]?\d+\s*,\s*[-+]?\d+\s*[)\]]$")


def _clean(cell):
    s = str(cell or "").strip().replace("−", "-").replace("–", "-")
    m = re.match(r"^([(\[]?\s*[-+]?)(\d{1,3}(?:,\d{3})+(?:\.\d+)?)(?!\d)", s)
    return m.group(1) + m.group(2).replace(",", "") + s[m.end():] if m else s


def _marked_pairs(rows, percent=None):
    """Each (label, column, coefficient text, mark, delimiter, value text) for a coefficient row
    followed by a value row, or a cell holding both ("0.084** (0.047)"), where the coefficient
    or its value carries a mark."""
    header, out = rows[0], []
    for r in rows[1:]:
        if not r or not _clean(r[0]):
            continue
        for j in range(1, len(r)):
            s = _SAME_CELL.match(_clean(r[j]))
            if s and (s.group(2) or s.group(5)):
                col = header[j] if j < len(header) else str(j)
                out.append((_clean(r[0]), col, s.group(1), s.group(2) or s.group(5), s.group(3), s.group(4)))
    for i in range(1, len(rows) - 1):
        top, below = rows[i], rows[i + 1]
        if not top or not _clean(top[0]) or (below and _clean(below[0])):
            continue
        for j in range(1, min(len(top), len(below))):
            c, v = _COEF_CELL.match(_clean(top[j])), _VALUE_CELL.match(_clean(below[j]))
            if not c or not v:
                continue
            # A trailing letter is a footnote label, not a significance mark.
            mark = _FOOTNOTE_LETTERS.sub("", c.group(2)) or _FOOTNOTE_LETTERS.sub("", v.group(3))
            if "%" in c.group(2) or "%" in v.group(3):
                if percent is not None:
                    percent.append(1)
                continue  # a percentage is not a coefficient this check reads
            if mark:
                col = header[j] if j < len(header) else str(j)
                out.append((_clean(top[0]), col, c.group(1), mark, v.group(1), v.group(2)))
    return out


def _is_car_mean_table(rows, note_text=""):
    """A table of abnormal-return mean tests: a header or note that names CAR, CAAR, or abnormal
    returns, with event windows as row labels or a mean column, which the market-event overlay checks when it runs."""
    header = " ".join(_clean(h).lower() for h in rows[0])
    names_car = re.search(r"\bcars?\b|\bcaars?\b|abnormal return", header + " " + str(note_text or "").lower())
    if not names_car:
        return False
    body = " ".join(_clean(r[0]).lower() for r in rows[1:] if r)
    if (re.search(r"\b(?:cars?|caars?|bhars?)\b|abnormal return", header)
            and not re.search(r"constant|intercept|r-?squared|r2|observations|r²|r\^2|\badj\b", body)):
        return True
    if re.search(r"\bcaar\b", header) or re.search(r"\b(?:mean|average|median)\b", header):
        return True
    return any(r and _WINDOW.match(_clean(r[0])) for r in rows[1:])


def _fmt_p(x):
    return f"{x:.4f}" if x < 0.01 else f"{x:.3f}"


def check_stars(tname, rows, note_text):
    """Flag a mark only when it claims more significance than every value the printed digits allow,
    under the two-sided normal (the most lenient two-sided reference), or one-tailed when the note
    says so. Missing or weaker marks are never flagged."""
    if not rows:
        return []
    percent = []
    pairs = _marked_pairs(rows, percent)
    skipped = lambda why: [{"check": "stars_vs_se", "table": tname, "cell": "-", "status": "not_computable",
                            "detail": f"star check skipped: {why}"}]
    pct_note = [{"check": "stars_vs_se", "table": tname, "cell": "-", "status": "not_computable",
                 "detail": f"star check skipped for {len(percent)} percentage cell(s); not read as coefficients"}]
    if not pairs and percent:
        return pct_note
    if not pairs:
        marked = any(_MARKED_NUMBER.search(_clean(c)) for r in rows[1:] for c in r[1:])
        return skipped("layout not read (coefficient and standard error not in adjacent rows)") if marked else []
    if _is_car_mean_table(rows, note_text):
        return skipped("abnormal-return mean tests, which the market-event overlay checks when it runs")
    labels = " ".join(_clean(c) for c in rows[0]) + " " + " ".join(_clean(r[0]) for r in rows[1:] if r)
    if _skip_reason(labels):
        return skipped(_skip_reason(labels))
    scheme = parse_note(note_text)
    if scheme["skip_reason"]:
        return skipped(scheme["skip_reason"])
    out = []
    one = scheme["tails"] == "one"
    for label, col, b, mark, delim, value in pairs:
        cell = f"{label} / {col}"
        if mark not in scheme["markers"]:
            out.append({"check": "stars_vs_se", "table": tname, "cell": cell, "status": "not_computable",
                        "detail": f"mark '{mark}' is not in the note's key"})
            continue
        kind = scheme["value_rows"].get(delim)
        bounds = pvalues.abs_t_bounds(b, value) if kind == "se" else (
            pvalues.abs_t_bounds_from_t(value) if kind == "t" else None)
        if bounds is None:
            continue
        lo, hi = pvalues.p_range(*bounds, one_tailed=one)
        tau = scheme["markers"][mark]
        if lo <= tau:
            continue
        tails = "one-tailed, as the note states" if one else "two-sided"
        detail = (f"|t| {bounds[0]:.3f} to {bounds[1]:.3f}, p {_fmt_p(lo)} to {_fmt_p(hi)} ({tails}, normal); "
                  f"printed {mark} needs p <= {tau:g}")
        if not one:
            olo, ohi = pvalues.p_range(*bounds, one_tailed=True)
            detail += f"; a one-tailed test, which the note does not state, would give p {_fmt_p(olo)} to {_fmt_p(ohi)}"
        out.append({"check": "stars_vs_se", "table": tname, "cell": cell, "status": "error", "detail": detail})
    return out + (pct_note if percent else [])


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Significance claims in the text (claims mode, used by the inference pack)
# ---------------------------------------------------------------------------

_CLAIMS_USAGE = "Usage: verify_arithmetic.py --claims <claims.json> <out_md> [--json <out.json>]"


def _given(rec, key):
    value = rec.get(key)
    return value is not None and str(value).strip() != ""


_TAILS = {"one": "one", "one-tailed": "one", "one tailed": "one", "1": "one",
          "two": "two", "two-tailed": "two", "two tailed": "two", "2": "two"}
_TIE = 1e-9


def _norm_tails(value):
    return _TAILS.get(str(value if value is not None else "").strip().lower(), "unstated")


def _bad_types(rec):
    """Name the first field of an unexpected type, or None."""
    for key in ("b", "se", "t", "p"):
        if rec.get(key) is not None and not isinstance(rec[key], (str, int, float)):
            return key
    if rec.get("claim") is not None and not isinstance(rec["claim"], dict):
        return "claim"
    for key in ("level", "p", "op"):
        if isinstance(rec.get("claim"), dict) and rec["claim"].get(key) is not None \
                and not isinstance(rec["claim"][key], (str, int, float)):
            return "claim." + key
    return None


def _claim_readings(rec):
    """The p intervals a claim is judged against, as (label, (low, high)) pairs, or None.
    A printed p is read as printed. Otherwise the two-sided normal interval from the printed
    coefficient and standard error (or t), halved when the paper states one-tailed tests; when
    the paper says nothing about tails and the hypothesis is directional, both readings count."""
    tails = _norm_tails(rec.get("tails"))
    could_be_one = tails == "one" or (tails == "unstated" and bool(rec.get("directional")))
    if _given(rec, "p"):
        rng = pvalues.printed_p_range(rec["p"])
        if not rng:
            return None
        readings = [("as printed", rng)]
        if could_be_one:
            readings.append(("one-tailed (printed p halved)", (rng[0] / 2, rng[1] / 2)))
        return readings
    if _given(rec, "se"):
        bounds = pvalues.abs_t_bounds(rec.get("b"), rec["se"])
    elif _given(rec, "t"):
        bounds = pvalues.abs_t_bounds_from_t(rec["t"])
    else:
        return None
    if bounds is None:
        return None
    two = pvalues.p_range(*bounds)
    one = pvalues.p_range(*bounds, one_tailed=True)
    if tails == "one":
        return [("one-tailed, as the paper states", one)]
    if tails == "two" or not rec.get("directional"):
        return [("two-sided", two)]
    return [("two-sided", two), ("one-tailed, which the paper does not state", one)]


def _claim_p(x):
    return f"{x:.4f}" if x < 0.01 else f"{x:.3f}"


def check_claim(rec):
    """Flag a sentence that claims more significance than the printed numbers allow under every
    reading the paper leaves open. Claims of non-significance are never flagged."""
    out = {"id": rec.get("id"), "check": "claim_vs_se", "status": "ok", "flag": False, "detail": "", "values": {}}
    bad = _bad_types(rec)
    if bad:
        out.update(status="invalid", detail=f"field {bad} has an unexpected type")
        return out
    claim = rec.get("claim")
    if not claim:
        out.update(status="not_computable", detail="no significance claim given")
        return out
    op = claim.get("op")
    if op not in ("<", "<=", "="):
        out.update(status="not_computable", detail="only claims of significance (op <, <=, or =) are checked")
        return out
    if op == "=":
        claimed = pvalues.printed_p_range(str(claim.get("p", "")))
        target = claimed[1] if claimed else None
        said = f"p = {claim.get('p')}"
    else:
        level = pvalues.parse_printed(str(claim.get("level", "")))
        target = level[0] if level else None
        if target is not None and not 0 < target <= 1:
            out.update(status="not_computable", detail="claim level must lie in (0, 1]")
            return out
        said = f"p {op} {claim.get('level')}"
    readings = _claim_readings(rec)
    if target is None or readings is None:
        out.update(status="not_computable", detail="the record lacks a readable claim, or a coefficient with a standard error, t, or p")
        return out
    out["values"] = {label: [lo, hi] for label, (lo, hi) in readings}
    if all(lo > target * (1 + _TIE) for _, (lo, hi) in readings):
        shown = "; ".join(f"{label}: p {_claim_p(lo)} to {_claim_p(hi)}" for label, (lo, hi) in readings)
        source = f"p {rec['p']}" if _given(rec, "p") else (
            f"{rec.get('b')} ({rec['se']})" if _given(rec, "se") else f"t {rec.get('t')}")
        out.update(flag=True, detail=f"{source} allows {shown}{' (normal)' if not _given(rec, 'p') else ''}; the text claims {said}")
    return out


def claims_main(argv):
    opts, positional, i = {}, [], 0
    while i < len(argv):
        if argv[i] in ("--claims", "--json"):
            if i + 1 >= len(argv):
                print(_CLAIMS_USAGE, file=sys.stderr)
                return 2
            opts[argv[i]] = argv[i + 1]
            i += 2
        else:
            positional.append(argv[i])
            i += 1
    if len(positional) != 1 or "--claims" not in opts:
        print(_CLAIMS_USAGE, file=sys.stderr)
        return 2
    try:
        records = json.loads(Path(opts["--claims"]).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"claims file not readable: {e}", file=sys.stderr)
        return 2
    if not isinstance(records, list):
        print("claims file must hold a JSON list of records", file=sys.stderr)
        return 2
    results = []
    for rec in records:
        if isinstance(rec, dict):
            results.append(check_claim(rec))
        else:
            results.append({"id": None, "check": "claim_vs_se", "status": "invalid", "flag": False,
                            "detail": "record is not a JSON object", "values": {}})
    errors = sum(1 for r in results if r["flag"])
    n_ok = sum(1 for r in results if r["status"] == "ok" and not r["flag"])
    n_nc = sum(1 for r in results if r["status"] == "not_computable")
    n_inv = sum(1 for r in results if r["status"] == "invalid")
    verdict = "ERRORS_FOUND" if errors else ("NOTHING_CHECKED" if not n_ok else "OK")
    lines = [f"VERDICT: {verdict}", "", "# Significance claims (deterministic)\n",
             f"Claims checked: {len(results)} | errors: {errors}",
             f"flagged: {errors} | ok: {n_ok} | not_computable: {n_nc} | invalid: {n_inv}\n"]
    for r in results:
        if r["flag"]:
            lines.append(f"- [ERROR] claim_vs_se text ({r['id']}): {r['detail']}")
        elif r["status"] != "ok":
            lines.append(f"- [{r['status'].upper()}] claim_vs_se text ({r['id']}): {r['detail']}")
    out = Path(positional[0])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if "--json" in opts:
        Path(opts["--json"]).parent.mkdir(parents=True, exist_ok=True)
        Path(opts["--json"]).write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"CLAIMS: {errors} errors, {len(results)} claims")
    return 0


def main():
    if "--claims" in sys.argv[1:]:
        sys.exit(claims_main(sys.argv[1:]))
    if len(sys.argv) < 2:
        print("Usage: verify_arithmetic.py <extracted_tables_dir> [out_md]"); sys.exit(2)
    d = Path(sys.argv[1])
    meta = {}
    meta_path = d / "table_meta.json"
    if meta_path.exists():
        try: meta = json.loads(meta_path.read_text())
        except Exception: meta = {}
    tables = {}
    for csvf in sorted(d.glob("table_*.csv")):
        vt = (meta.get(csvf.name) or {}).get("value_type", "unknown")
        try: tables[csvf.name] = parse_table_csv(csvf, value_type=vt)
        except Exception as e:
            tables[csvf.name] = {"columns": [], "rows": [], "error": str(e)}
    one_tailed = set()
    for csvf in sorted(d.glob("table_*.csv")):
        note = csvf.with_name(csvf.stem + "_note.txt")
        if note.exists() and _ONE_TAILED.search(note.read_text(encoding="utf-8", errors="replace")):
            one_tailed.add(csvf.name)
    findings = run_checks(tables, one_tailed)
    for csvf in sorted(d.glob("table_*.csv")):
        note = csvf.with_name(csvf.stem + "_note.txt")
        try:
            with open(csvf, newline="", encoding="utf-8") as fh:
                rows = list(csv.reader(fh))
        except (OSError, UnicodeDecodeError, csv.Error):
            continue  # the parse_error finding above already reports this table
        try:
            note_text = note.read_text(encoding="utf-8", errors="replace") if note.exists() else ""
        except OSError:
            findings.append({"check": "stars_vs_se", "table": csvf.name, "cell": "-",
                             "status": "not_computable", "detail": "star check skipped: note not readable"})
            continue
        findings += check_stars(csvf.name, rows, note_text)
    errs = [f for f in findings if f["status"] == "error"]
    parse_errs = [f for f in errs if f["check"] == "parse_error"]
    arith_errs = [f for f in errs if f["check"] != "parse_error"]

    # Gap 3: determine VERDICT
    if not tables:
        verdict = "NO_TABLES"
    elif parse_errs:
        verdict = "PARSE_ERRORS_PRESENT"
    elif arith_errs:
        verdict = "ERRORS_FOUND"
    else:
        verdict = "OK"

    lines = [
        f"VERDICT: {verdict}",
        "",
        "# Arithmetic Verification (deterministic)\n",
        f"Tables checked: {len(tables)} | errors: {len(errs)} | "
        f"not-computable: {sum(1 for f in findings if f['status']=='not_computable')}\n",
    ]
    for f in findings:
        if f["status"] != "ok":
            lines.append(f"- [{f['status'].upper()}] {f['check']} {f['table']} ({f['cell']}): {f['detail']}")
    out = sys.argv[2] if len(sys.argv) >= 3 else None
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text("\n".join(lines))
    print(f"ARITHMETIC: {len(errs)} errors, {len(tables)} tables [VERDICT: {verdict}]")
    sys.exit(0)

if __name__ == "__main__":
    main()
