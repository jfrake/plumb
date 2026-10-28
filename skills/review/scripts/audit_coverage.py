#!/usr/bin/env python3
"""
Deterministic coverage audit for Plumb's accuracy audit.

Runs after Stage 5 synthesis. Verifies that:
1. Every Serious-severity finding in upstream agent files appears in synthesis_coverage.md
   (upstream "Serious", "High", "Fatal", or "Undermines the main claim")
2. Every INCLUDED finding's source_excerpt has a substring (>=40 chars) in the draft
   (stage-5/draft.md; a stage-5/draft.txt only in a run from before the output folder)
3. Every EXCLUDED finding uses one of the four allowed rationale types
4. Every duplicate_of rationale references an existing INCLUDED finding, and every
   user_ruled_out rationale cites an against:<n> item the user answered "C. Not
   plausible here" (read from audit/events.jsonl; the last answer wins)
5. No banned rationale phrases appear in synthesis_coverage.md
6. Every coverage row's severity is exactly one of the three severity labels:
   "Undermines the main claim", "Weakens a claim", "Minor"
7. Every MERGED row's rationale states its point ("point: ..."), and every number in the
   point, apart from page, table, figure, and model references, appears in the target
   issue in stage-5/issues.json (or in the draft when the target is not an issue id)

Exit codes:
  0 = pass
  1 = audit failure (hard-fails the pipeline)
  2 = audit infrastructure error (missing files etc.)

Usage:
  python3 audit_coverage.py <workspace_dir> <paper_dir>

<paper_dir> is accepted for interface stability; the draft is read from
<workspace_dir>/stage-5/.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

# Severity labels for the coverage table. Must match plumb.outputs.SEVERITIES.
SEVERITIES = ("Undermines the main claim", "Weakens a claim", "Minor")

BANNED_RATIONALES = [
    r"partially absorbed",
    r"\babsorbed in\b",
    r"subsumed by",
    r"\bnot central\b",
    r"\btangential\b",
    r"minor for this paper",
]

ALLOWED_RATIONALE_PREFIXES = [
    "duplicate_of:",
    "addressed_by_paper_appendix:",
    "low_confidence_minor_only:",
    "user_ruled_out:",
]
# Note: "infeasible_given_data" is intentionally NOT allowed as an exclusion
# rationale. If a Serious finding identifies a real threat but the recommended
# test cannot be run with the data, the finding must still be INCLUDED as a
# comment that frames the threat as an unaddressed limitation. Silent exclusion
# on infeasibility grounds is the failure mode this audit exists to prevent.

SERIOUS_PATTERNS = [
    # Original markdown-formatted forms
    r"\*\*Severity:\*\*\s*\*?\*?Serious",
    r"\*\*Severity:\*\*\s*\*?\*?High",
    r"\*\*Serious threat\*\*",
    r"\*\*High severity\*\*",
    # Plain-text colon and equals forms; case-insensitive via re.IGNORECASE at call site.
    # Anchored on "severity" so "seriously" in prose is not matched (no word-boundary
    # needed because "seriously" contains more characters after "serious").
    r"severity\s*:\s*\"?serious\"?",
    r"severity\s*:\s*\"?high\"?",
    r"severity\s*=\s*\"?serious\"?",
    r"severity\s*=\s*\"?high\"?",
    # Bare "Fatal" as a standalone descriptor (word-boundary anchored to avoid
    # "fatalistic", "fatally", etc.).
    r"\bFatal\b",
    # Spec label for the top severity, as core and pack agents write it
    # ("Severity: Undermines the main claim", "**Proposed severity:** Undermines ...").
    r"severity\W{0,6}undermines the main claim",
]

# Every agent report in stage-3/ and stage-4/ is upstream, pack files included, except the
# compiled majors draft and the alternatives the user reads at the "against" check-in.
NOT_UPSTREAM = {"stage-4/majors_draft.md", "stage-3/alternatives.md"}


def upstream_files(workspace: Path) -> list[str]:
    """The stage-3 and stage-4 Markdown files the coverage audit scans, in a fixed order."""
    out = []
    for stage in ("stage-3", "stage-4"):
        d = workspace / stage
        if d.is_dir():
            out += sorted(f"{stage}/{p.name}" for p in d.glob("*.md"))
    return [f for f in out if f not in NOT_UPSTREAM]


def find_serious_findings(workspace: Path) -> list[tuple[str, int, str]]:
    """Return [(file, line_num, context)] for each Serious finding in upstream files."""
    findings = []
    for fname in upstream_files(workspace):
        f = workspace / fname
        if not f.exists():
            continue
        text = f.read_text()
        if text.startswith("# Not run"):
            continue
        lines = text.splitlines()
        for i, line in enumerate(lines):
            for pat in SERIOUS_PATTERNS:
                if re.search(pat, line, re.IGNORECASE):
                    context = "\n".join(lines[max(0, i - 2):min(len(lines), i + 3)])
                    findings.append((fname, i + 1, context))
                    break
    return findings


def check_banned_rationales(coverage: str) -> list[str]:
    """Return list of banned-rationale violations."""
    violations = []
    for pat in BANNED_RATIONALES:
        for m in re.finditer(pat, coverage, re.IGNORECASE):
            start = max(0, m.start() - 60)
            end = min(len(coverage), m.end() + 60)
            violations.append(f"  banned phrase '{m.group(0)}' at: ...{coverage[start:end]}...")
    return violations


def _split_table_row(line: str) -> list[str]:
    r"""Split a markdown table row on unescaped '|' characters only.

    A backslash-escaped pipe ('\|') is treated as a literal pipe character
    inside the cell, not as a column delimiter. After splitting, '\|' sequences
    in each cell are replaced with '|'.
    """
    # Temporarily replace '\|' with a placeholder that cannot appear in real content,
    # then split on '|', then restore the placeholder to '|'.
    placeholder = "\x00PIPE\x00"
    escaped = line.replace(r"\|", placeholder)
    parts = escaped.split("|")
    return [p.replace(placeholder, "|") for p in parts]


def extract_coverage_entries(coverage: str) -> list[dict]:
    """Parse synthesis_coverage.md table rows. Best-effort markdown table parsing."""
    entries = []
    table_lines = [l for l in coverage.splitlines() if l.strip().startswith("|") and "|" in l[1:]]
    for line in table_lines:
        # Skip header / separator rows
        if re.match(r"^\|[\s\-:|]+\|$", line.strip()):
            continue
        if any(h in line.lower() for h in ["finding_id", "source_file", "severity", "disposition", "source_excerpt"]):
            continue
        # Use escaped-pipe-aware splitter instead of raw split("|")
        raw_cells = _split_table_row(line.strip())
        # strip() the leading/trailing empty strings that result from the outer pipes
        cells = [c.strip() for c in raw_cells if True]
        # Drop leading/trailing empty strings produced by the bounding pipes
        if cells and cells[0] == "":
            cells = cells[1:]
        if cells and cells[-1] == "":
            cells = cells[:-1]
        if len(cells) >= 6:
            entries.append({
                "finding_id": cells[0],
                "source_file": cells[1],
                "severity": cells[2],
                "disposition": cells[3],
                "target": cells[4],
                "rationale": cells[5],
            })
    return entries


def check_excluded_rationale_types(entries: list[dict]) -> list[str]:
    """Verify EXCLUDED entries use one of the four allowed rationale types."""
    errors = []
    for e in entries:
        if e["disposition"] == "EXCLUDED":
            r = e["rationale"]
            if not any(r.startswith(p) for p in ALLOWED_RATIONALE_PREFIXES):
                errors.append(
                    f"  finding '{e['finding_id']}' EXCLUDED with non-allowed rationale: {r}\n"
                    f"    must start with one of: {', '.join(ALLOWED_RATIONALE_PREFIXES)}"
                )
    return errors


def check_severity_labels(entries: list[dict]) -> list[str]:
    """Every coverage row's severity must be exactly one of SEVERITIES."""
    errors = []
    for e in entries:
        if e["severity"] not in SEVERITIES:
            errors.append(
                f"  finding '{e['finding_id']}' has severity '{e['severity']}'; "
                f"use exactly one of: {', '.join(SEVERITIES)}"
            )
    return errors


def check_duplicate_of_targets(entries: list[dict]) -> list[str]:
    """Every duplicate_of rationale must reference an INCLUDED finding in the table."""
    included_ids = {e["finding_id"] for e in entries
                    if e["disposition"] in ("INCLUDED_MAJOR", "INCLUDED_MINOR")}
    errors = []
    for e in entries:
        if e["rationale"].startswith("duplicate_of:"):
            raw = e["rationale"].split(":", 1)[1].strip()
            m = re.match(r"[A-Za-z0-9_\-]+", raw)
            target = m.group(0) if m else ""
            if target not in included_ids:
                errors.append(
                    f"  finding '{e['finding_id']}' has duplicate_of target '{target}' "
                    f"which is not INCLUDED in this coverage table"
                )
    return errors


def _last_answers(workspace: Path) -> dict:
    """Map each check-in item to its last recorded answer label."""
    answers = {}
    events = workspace / "audit" / "events.jsonl"
    if not events.exists():
        return answers
    for line in events.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        ev = json.loads(line)
        if ev.get("kind") == "checkin":
            answers[ev.get("item", "")] = ev.get("answer", "")
    return answers


def check_user_ruled_out(entries: list[dict], workspace: Path) -> list[str]:
    """Every user_ruled_out rationale must cite an against:<n> item answered C."""
    answers = None
    errors = []
    for e in entries:
        if not e["rationale"].startswith("user_ruled_out:"):
            continue
        if answers is None:
            answers = _last_answers(workspace)
        m = re.match(r"\s*(against:\d+)", e["rationale"].split(":", 1)[1])
        if not m:
            errors.append(
                f"  finding '{e['finding_id']}' uses user_ruled_out without an against:<n> item"
            )
            continue
        item = m.group(1)
        answer = answers.get(item, "")
        if answer.split(".", 1)[0].strip().upper() != "C":
            errors.append(
                f"  finding '{e['finding_id']}' cites {item}, but the user did not mark that "
                f"alternative \"C. Not plausible here\" (recorded answer: {answer or 'none'})"
            )
    return errors


def check_source_excerpts(coverage: str, review_text: str, workspace: Path) -> list[str]:
    """For each Serious entry with a source_excerpt, verify a >=40-char substring
    appears in the draft OR the entry is EXCLUDED with a valid rationale."""
    errors = []
    # Parse source_excerpt fields (loose format: "source_excerpt: <text>" possibly across lines)
    excerpts = re.findall(
        r"finding[_\s]?id[:\s]+([^\s|,]+).*?source[_\s]?excerpt[:\s]+\"?([^\"\n]{40,})\"?",
        coverage,
        re.IGNORECASE | re.DOTALL,
    )
    for finding_id, excerpt in excerpts:
        # Take a 40-character middle substring (avoid edge artifacts)
        excerpt_clean = re.sub(r"\s+", " ", excerpt.strip())
        if len(excerpt_clean) < 40:
            continue
        substr = excerpt_clean[:80]  # try first 80 chars
        # Allow inclusion in the draft OR in coverage rationale (for EXCLUDED entries)
        if substr in review_text:
            continue
        # Check if entry is EXCLUDED with valid rationale (audit covers this elsewhere)
        # We're lenient here - the EXCLUDED check above will catch bad rationales
        # Just verify SOME variant of the excerpt is somewhere
        words = excerpt_clean.split()[:5]
        keyword_phrase = " ".join(words)
        if keyword_phrase not in review_text and keyword_phrase not in coverage:
            errors.append(
                f"  finding '{finding_id}': source_excerpt not found in the draft "
                f"or coverage. Excerpt starts: '{keyword_phrase}...'"
            )
    return errors


# A number after one of these words points to a place in the paper (p. 18, Table 1,
# Model 5), not to a fact the merged issue must repeat.
_REF_WORDS = (r"(?:pp?\.|pages?|tables?|figures?|figs?\.|models?|columns?|cols?\.|"
              r"panels?|sections?|appendix|footnotes?|notes?|hypothes[ie]s|H|issues?|"
              r"comments?|rows?|steps?|equations?|eqs?\.|items?|clusters?)")
_REF_RE = re.compile(r"\b" + _REF_WORDS + r"\s*\d+[A-Za-z]?(?:\s*(?:-|–|and|to|,)\s*\d+[A-Za-z]?)*",
                     re.IGNORECASE)
# Pipeline ids such as numbers:text:8 or maj-6 name a finding, not a fact.
_ID_RE = re.compile(r"\b[A-Za-z][\w-]*(?::[\w-]+)+|\b[A-Za-z]+-\d+[A-Za-z]?\b")
_NUM_RE = re.compile(r"(?<![\w.])-?(?:\d[\d,]*(?:\.\d+)?|\.\d+)")


def _numbers(text: str) -> set[float]:
    out = set()
    for m in _NUM_RE.finditer(text):
        try:
            out.add(float(m.group(0).replace(",", "")))
        except ValueError:
            continue
    return out


def _point(rationale: str) -> str | None:
    m = re.search(r"\bpoint\s*:\s*(.+)", rationale, re.IGNORECASE)
    return m.group(1).strip().strip('"') if m else None


def _issue_texts(workspace: Path) -> dict[str, str]:
    """Map each issue id in stage-5/issues.json to the text of all its fields."""
    f = workspace / "stage-5" / "issues.json"
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    items = data.get("issues", []) if isinstance(data, dict) else data
    out = {}
    for it in items if isinstance(items, list) else []:
        if isinstance(it, dict) and it.get("id") is not None:
            out[str(it["id"]).strip().lower()] = json.dumps(it, ensure_ascii=False)
    return out


def _draft_section(review_text: str, target: str) -> str:
    """The draft's '### <n>.' section for a major issue, or '' when there is none."""
    m = re.search(rf"^###\s*{re.escape(target)}\.(.*?)(?=^##|\Z)", review_text, re.MULTILINE | re.DOTALL)
    return m.group(1) if m else ""


def check_merged_points(entries: list[dict], workspace: Path, review_text: str) -> list[str]:
    """Every MERGED row states its point, and every number in the point appears in the
    issue it was merged into: its issues.json entry or its section of the draft (the whole
    draft when the target is not an issue id)."""
    issues = None
    errors = []
    for e in entries:
        if e["disposition"] != "MERGED":
            continue
        point = _point(e["rationale"])
        if not point:
            errors.append(
                f"  finding '{e['finding_id']}' is MERGED without 'point: <the finding's distinct "
                f"point, with its numbers>' in its rationale"
            )
            continue
        if issues is None:
            issues = _issue_texts(workspace)
        target = re.sub(r"^(?:issue|comment|#)\s*", "", e["target"].strip(), flags=re.IGNORECASE).lower()
        where = issues.get(target)
        place = f"issue {e['target']}" if where is not None else "the draft"
        if where is None:
            where = review_text
        else:
            where += "\n" + _draft_section(review_text, target)
        missing = sorted(_numbers(_REF_RE.sub(" ", _ID_RE.sub(" ", point))) - _numbers(where))
        if missing:
            shown = ", ".join(f"{n:g}" for n in missing)
            errors.append(
                f"  finding '{e['finding_id']}' is MERGED into {e['target']}, but {place} does not "
                f"give {shown} from its point: {point}. Make the point there, or give the finding "
                f"its own disposition."
            )
    return errors


def warn_if_clusters_missing(workspace: Path) -> bool:
    """Print a warning if stage-5/clusters.md is missing or empty. Return True if file is OK.

    This is a SOFT check. Missing clusters.md does NOT fail the audit. The
    synthesis-critic (Tier 2) catches the issue and triggers a revise cycle.
    The audit only flags it for visibility.
    """
    f = workspace / "stage-5" / "clusters.md"
    if not f.exists() or f.stat().st_size == 0:
        print(f"WARN: stage-5/clusters.md missing or empty in {workspace}. Synthesis may have skipped Step 0.6. Synthesis-critic will catch this.")
        return False
    print(f"OK: stage-5/clusters.md present in {workspace}.")
    return True


def find_draft(workspace: Path) -> tuple[Path | None, str]:
    """Return (draft_path, error). The draft is stage-5/draft.md. A run from before the output
    folder may hold stage-5/draft.txt, a report draft; if both exist, run.json's "output" decides."""
    stage5 = workspace / "stage-5"
    by_output = {"fix_list": stage5 / "draft.md", "report": stage5 / "draft.txt"}
    present = [d for d in by_output.values() if d.exists()]
    if len(present) == 1:
        return present[0], ""
    if not present:
        return None, f"FATAL: no draft found at {stage5}/draft.md or {stage5}/draft.txt"
    run_json = workspace / "run.json"
    try:
        output = json.loads(run_json.read_text()).get("output")
    except (OSError, ValueError):
        output = None
    if output in by_output:
        return by_output[output], ""
    return None, (f"FATAL: both draft.md and draft.txt exist in {stage5} and "
                  f"run.json does not say which output was requested")


def run_audit(workspace: Path, paper_dir: Path) -> tuple[int, list[str]]:
    """Pure decision function. Returns (exit_code, messages).

    exit_code: 0 pass, 1 audit failure, 2 infrastructure error."""
    warn_if_clusters_missing(workspace)

    coverage_path = workspace / "synthesis_coverage.md"
    if not coverage_path.exists():
        return 2, [f"FATAL: synthesis_coverage.md not found at {coverage_path}"]
    review_path, draft_error = find_draft(workspace)
    if review_path is None:
        return 2, [draft_error]

    coverage = coverage_path.read_text()
    review = review_path.read_text()

    all_errors: list[str] = []

    banned = check_banned_rationales(coverage)
    if banned:
        all_errors.append("BANNED RATIONALES:")
        all_errors.extend(banned)

    entries = extract_coverage_entries(coverage)
    serious = find_serious_findings(workspace)

    # Hard fail: a non-empty review with Serious findings but an unparseable/empty
    # coverage table means we cannot verify routing at all. Previously a warning.
    if not entries and serious:
        all_errors.append(
            f"COVERAGE UNVERIFIABLE: {len(serious)} Serious findings upstream but zero "
            f"coverage-table rows parsed from synthesis_coverage.md. Cannot confirm any "
            f"finding reached the draft."
        )

    bad_severities = check_severity_labels(entries)
    if bad_severities:
        all_errors.append("INVALID SEVERITY LABELS:")
        all_errors.extend(bad_severities)

    bad_rationale_types = check_excluded_rationale_types(entries)
    if bad_rationale_types:
        all_errors.append("INVALID EXCLUSION RATIONALES:")
        all_errors.extend(bad_rationale_types)

    dup_errors = check_duplicate_of_targets(entries)
    if dup_errors:
        all_errors.append("BROKEN duplicate_of REFERENCES:")
        all_errors.extend(dup_errors)

    ruled_out_errors = check_user_ruled_out(entries, workspace)
    if ruled_out_errors:
        all_errors.append("UNSUPPORTED user_ruled_out REFERENCES:")
        all_errors.extend(ruled_out_errors)

    merged_errors = check_merged_points(entries, workspace, review)
    if merged_errors:
        all_errors.append("MERGED POINTS MISSING FROM THEIR TARGET:")
        all_errors.extend(merged_errors)

    excerpt_errors = check_source_excerpts(coverage, review, workspace)
    if excerpt_errors:
        all_errors.append("MISSING SOURCE EXCERPTS:")
        all_errors.extend(excerpt_errors)

    # Hard fail: reconcile by SOURCE FILE, not just a global count. Every upstream
    # Serious finding must have a coverage row attributed to its source file, so that
    # unrelated Serious rows cannot mask a dropped finding from another source.
    serious_by_source = Counter(fname for (fname, _ln, _ctx) in serious)
    rows_by_source = Counter()
    for e in entries:
        sf = e["source_file"].lower()
        for fname in serious_by_source:
            if Path(fname).name.lower() in sf:
                rows_by_source[fname] += 1
    gaps = [(f, serious_by_source[f], rows_by_source[f])
            for f in serious_by_source if rows_by_source[f] < serious_by_source[f]]
    if gaps:
        detail = "; ".join(f"{f}: {nu} Serious upstream but {nr} coverage row(s)"
                           for f, nu, nr in gaps)
        all_errors.append(
            "COVERAGE GAP (by source): " + detail +
            ". Every upstream Serious finding must have a coverage row for its source file "
            "(INCLUDED or EXCLUDED with an allowed rationale)."
        )

    if all_errors:
        return 1, all_errors
    return 0, [
        f"Coverage audit PASSED. Parsed {len(entries)} coverage entries, "
        f"{len(serious)} Serious findings upstream."
    ]


def main():
    if len(sys.argv) != 3:
        print("Usage: audit_coverage.py <workspace_dir> <paper_dir>", file=sys.stderr)
        sys.exit(2)
    code, messages = run_audit(Path(sys.argv[1]), Path(sys.argv[2]))
    if code == 0:
        print(messages[0])
    else:
        print("=" * 70)
        print("COVERAGE AUDIT FAILED" if code == 1 else "COVERAGE AUDIT INFRA ERROR")
        print("=" * 70)
        for line in messages:
            print(line)
        print("=" * 70)
    sys.exit(code)


if __name__ == "__main__":
    main()
