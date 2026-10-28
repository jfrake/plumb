#!/usr/bin/env python3
"""
Claim-Attribution Verifier for Plumb

Deterministic completeness gate over Plumb's accuracy audit evidence ledger.

The accuracy audit's claim-verification step ("verify every external reference claim via
web search") used to be free-form prose: the agent could assert it verified a citation
without recording what it actually fetched, and nothing confirmed it covered every
citation. That soft instruction is exactly the layer that failed when "Smith et al." was
expanded to the wrong authors and the finding-direction was never re-checked against a
live source.

This script turns "I checked" into "here is what I checked." It does NOT make semantic
judgments (the CONFIRMED/REFUTED verdict is the agent's). It mechanically enforces that:
  1. Every external citation in review.txt has at least one ledger entry.
  2. Each entry that claims to CONFIRM or REFUTE a finding records a fetched source URL
     and a verbatim evidence quote (you cannot confirm a finding from training data).
  3. Verdicts and claim types use the allowed vocabulary.
Then it surfaces REFUTED (content error) and UNVERIFIABLE (needs a human) entries.

Ledger format: claim_attribution.jsonl, one JSON object per line:
  {
    "citation":       "Smith et al. (2023)",         // as written in the review
    "review_claim":   "the review's exact characterization of this source",
    "claim_type":     "finding|framing|method|benchmark|existence-only",
    "source_url":     "https://...",                 // the URL actually fetched
    "evidence_quote": "verbatim text from the fetched source",
    "verdict":        "CONFIRMED|REFUTED|UNVERIFIABLE",
    "note":           "optional free text"
  }

Usage:
    python3 verify_claim_attribution.py <draft> <ledger_jsonl> <output_md>

Exit codes:
    0  PASS -- all citations documented, no REFUTED entries.
    1  FAIL -- structural failure (missing/incomplete ledger entries) or content
               failure (at least one REFUTED attribution).
    2  REVIEW_NEEDED -- no structural or content failures, but at least one
                        UNVERIFIABLE entry requires human judgment.

The --uncited mode always exits 0 (advisory, report-only).
"""
from __future__ import annotations

import sys
import re
import json
from pathlib import Path


try:
    from citation_parser import extract_body_citations  # shared canonical implementation
except ImportError:
    # Fallback: resolve relative to this file so the module can be found when
    # the scripts directory is not on sys.path (e.g. direct subprocess calls).
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location(
        "citation_parser",
        str(Path(__file__).parent / "citation_parser.py"),
    )
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    extract_body_citations = _mod.extract_body_citations


ALLOWED_VERDICTS = {"CONFIRMED", "REFUTED", "UNVERIFIABLE"}
ALLOWED_CLAIM_TYPES = {"finding", "framing", "method", "benchmark", "existence-only"}
# Claim types whose CONFIRMED/REFUTED verdict requires a fetched source + evidence quote.
EVIDENCE_REQUIRED_TYPES = {"finding", "framing", "method", "benchmark"}


def primary_surname(author_part):
    """First capitalized surname token in a body-citation author string."""
    for tok in author_part.replace(",", " ").split():
        if tok[:1].isupper() and tok.lower() not in ("and", "et", "al", "al."):
            return tok.lower().rstrip(".")
    return author_part.strip().lower()


def load_ledger(ledger_path):
    """Parse the JSONL ledger. Returns (records, malformed_lines)."""
    records, malformed = [], []
    text = Path(ledger_path).read_text()
    for i, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                records.append(obj)
            else:
                malformed.append((i, line[:80]))
        except json.JSONDecodeError:
            malformed.append((i, line[:80]))
    return records, malformed


def record_covers(record, surname, year):
    """Does this ledger record correspond to the (surname, year) body citation?

    Surname must appear in the record's citation string; year must match within +/-1
    to tolerate the online-first vs. print-year gap (e.g., 2022 vs 2023)."""
    cite = str(record.get("citation", "")).lower()
    if surname not in cite:
        return False
    years = [int(y) for y in re.findall(r"\b(?:19|20)\d{2}\b", cite)]
    if not years:
        return True  # surname matched and no year in the citation string; accept
    return any(abs(y - year) <= 1 for y in years)


def entry_completeness(record):
    """Return (status, reasons) for a single ledger record.

    status in {"OK", "INCOMPLETE"}. INCOMPLETE means the agent did not document the
    verification well enough to trust it (missing fetched source, missing evidence,
    bad vocabulary)."""
    reasons = []
    verdict = str(record.get("verdict", "")).strip().upper()
    claim_type = str(record.get("claim_type", "")).strip().lower()
    url = str(record.get("source_url", "")).strip()
    evidence = str(record.get("evidence_quote", "")).strip()

    if not str(record.get("citation", "")).strip():
        reasons.append("missing citation")
    if not str(record.get("review_claim", "")).strip():
        reasons.append("missing review_claim")
    if verdict not in ALLOWED_VERDICTS:
        reasons.append(f"verdict '{verdict or '(empty)'}' not in {sorted(ALLOWED_VERDICTS)}")
    if claim_type not in ALLOWED_CLAIM_TYPES:
        reasons.append(f"claim_type '{claim_type or '(empty)'}' not in {sorted(ALLOWED_CLAIM_TYPES)}")

    # A CONFIRMED/REFUTED verdict must be backed by something actually fetched.
    if verdict in ("CONFIRMED", "REFUTED"):
        if not (url.startswith("http://") or url.startswith("https://")):
            reasons.append("CONFIRMED/REFUTED with no fetched source_url (looks like training-data recall)")
        if claim_type in EVIDENCE_REQUIRED_TYPES and not evidence:
            reasons.append(f"CONFIRMED/REFUTED {claim_type} claim with no evidence_quote")

    return ("OK" if not reasons else "INCOMPLETE", reasons)


def verify(review_path, ledger_path, output_path):
    """Run the claim-attribution gate.

    Returns an integer exit code:
        0 -- PASS
        1 -- FAIL (structural or content)
        2 -- REVIEW_NEEDED (unverifiable entries, no structural/content failures)
    """
    review_path = Path(review_path)
    ledger_path = Path(ledger_path)
    output_path = Path(output_path)

    structural_fail = []   # missing entries / incomplete entries / malformed ledger
    content_fail = []      # REFUTED
    needs_human = []       # UNVERIFIABLE
    ok = []

    # 1. Ledger must exist.
    if not ledger_path.exists():
        output_path.write_text(
            "# Claim-Attribution Verification\n\n"
            "**VERDICT: FAIL (structural)**\n\n"
            f"The evidence ledger `{ledger_path.name}` does not exist. The accuracy audit "
            "must write one JSON record per external citation.\n"
        )
        print("CLAIM_ATTRIBUTION_VERDICT: FAIL (no ledger)")
        return 1

    records, malformed = load_ledger(ledger_path)
    for ln, snippet in malformed:
        structural_fail.append(f"Malformed ledger line {ln}: `{snippet}`")

    # 2. Per-record completeness.
    for idx, rec in enumerate(records, 1):
        status, reasons = entry_completeness(rec)
        cite = str(rec.get("citation", f"(record {idx})"))
        verdict = str(rec.get("verdict", "")).strip().upper()
        if status == "INCOMPLETE":
            structural_fail.append(f"`{cite}`: {'; '.join(reasons)}")
        elif verdict == "REFUTED":
            content_fail.append(rec)
        elif verdict == "UNVERIFIABLE":
            needs_human.append(rec)
        else:
            ok.append(rec)

    # 3. Coverage: every external body citation must have a ledger entry.
    body_citations = set()
    if extract_body_citations is not None:
        try:
            body_citations = extract_body_citations(str(review_path))
        except Exception as e:
            structural_fail.append(f"Could not extract body citations from review: {e}")

    uncovered = []
    for author_part, year in sorted(body_citations):
        surname = primary_surname(author_part)
        if not any(record_covers(rec, surname, year) for rec in records):
            uncovered.append(f"{author_part} ({year})")
    for u in uncovered:
        structural_fail.append(f"No ledger entry for cited source: {u}")

    # 4. Verdict and exit code.
    if structural_fail:
        verdict = "FAIL (structural)"
        exit_code = 1
    elif content_fail:
        verdict = "FAIL (content: refuted attribution)"
        exit_code = 1
    elif needs_human:
        verdict = "REVIEW_NEEDED (unverifiable attributions)"
        exit_code = 2
    else:
        verdict = "PASS"
        exit_code = 0

    # 5. Report.
    out = []
    out.append("# Claim-Attribution Verification\n")
    out.append(f"**Review file:** {review_path.name}")
    out.append(f"**Ledger:** {ledger_path.name}")
    out.append(f"**External citations in review body:** {len(body_citations)}")
    out.append(f"**Ledger records:** {len(records)}")
    out.append(f"**Confirmed:** {len(ok)} | **Refuted:** {len(content_fail)} | "
               f"**Unverifiable:** {len(needs_human)} | **Structural issues:** {len(structural_fail)}\n")
    out.append(f"**VERDICT: {verdict}**\n")

    if structural_fail:
        out.append("## Structural failures (agent must fix the ledger or re-verify)\n")
        out.append("These mean a citation was skipped, or a verdict was asserted without a "
                   "fetched source and evidence. Treat as a hard gate: the attribution was "
                   "not actually documented.\n")
        for s in structural_fail:
            out.append(f"- {s}")
        out.append("")

    if content_fail:
        out.append("## Refuted attributions (CRITICAL: fix the review text)\n")
        out.append("The agent fetched a source and found the review's characterization is "
                   "wrong. Correct the review or remove the claim.\n")
        for rec in content_fail:
            out.append(f"### {rec.get('citation', '?')}")
            out.append(f"- **Review claims:** {rec.get('review_claim', '')}")
            out.append(f"- **Source:** {rec.get('source_url', '')}")
            out.append(f"- **Evidence:** {rec.get('evidence_quote', '')}")
            if rec.get("note"):
                out.append(f"- **Note:** {rec['note']}")
            out.append("")

    if needs_human:
        out.append("## Unverifiable attributions (surface to reviewer)\n")
        for rec in needs_human:
            out.append(f"- **{rec.get('citation', '?')}** — {rec.get('review_claim', '')} "
                       f"(note: {rec.get('note', 'no source found')})")
        out.append("")

    if ok:
        out.append("## Confirmed attributions\n")
        out.append("| Citation | Type | Verdict | Source |")
        out.append("|----------|------|---------|--------|")
        for rec in ok:
            out.append(f"| {rec.get('citation','?')} | {rec.get('claim_type','')} | "
                       f"{rec.get('verdict','')} | {rec.get('source_url','')} |")
        out.append("")

    output_path.write_text("\n".join(out))
    print(f"CLAIM_ATTRIBUTION_VERDICT: {verdict}")
    print(f"Report: {output_path}")
    return exit_code


_ASSERT_PAT = re.compile(
    r"(requires|mandates|covers|changed its|began|introduced|reports that|"
    r"methodology|market share|jurisdiction)", re.IGNORECASE)
_CITE_NEAR = re.compile(
    r"\(\s*[A-Za-z][^)]*\d{4}\s*\)"          # (Author Year)
    r"|\[\d+(?:[,\-]\s*\d+)*\]"              # [1], [3, 4], [5-7]
)
_ACRONYM_PAT = re.compile(r"\b[A-Z]{2,}\b|\b[A-Z]&[A-Z]\b")


def extract_uncited_assertions(review_text):
    """Sentences with a third-party institutional/market/methodology claim and
    no adjacent (Author Year) or numeric [n] citation. Heuristic; flags for the audit to verify."""
    out = []
    for sent in re.split(r"(?<=[.!?])\s+", review_text):
        if _ASSERT_PAT.search(sent) and not _CITE_NEAR.search(sent):
            # require a capitalized proper-noun third party: either an acronym/ampersand-name
            # anywhere in the sentence, or a capitalized multi-char word that is NOT the
            # sentence-initial token (to avoid matching "The", "This", etc.).
            tokens = sent.split()
            has_acronym = bool(_ACRONYM_PAT.search(sent))
            has_mid_proper = any(
                t[0].isupper() and len(re.sub(r"[^A-Za-z]", "", t)) > 1
                for t in tokens[1:]
            )
            if has_acronym or has_mid_proper:
                out.append(sent.strip())
    return out


def run_uncited(review_path_str, output_path_str):
    """CLI entry point for --uncited mode.

    Reads review_path_str, calls extract_uncited_assertions, and writes a
    numbered Markdown report to output_path_str. Exit code is always 0
    (advisory; the accuracy audit decides what to do with each flag).
    """
    review_path = Path(review_path_str)
    output_path = Path(output_path_str)

    text = review_path.read_text()
    flagged = extract_uncited_assertions(text)

    lines = ["# Uncited Assertions\n"]
    if flagged:
        lines.append(
            "Candidate uncited third-party factual claims detected by the "
            "deterministic heuristic. For each, WebFetch-verify or "
            "remove/hedge per the accuracy-audit uncited-third-party-assertion check.\n"
        )
        for i, sent in enumerate(flagged, 1):
            lines.append(f"{i}. {sent}")
    else:
        lines.append("none found")

    output_path.write_text("\n".join(lines) + "\n")
    print(f"UNCITED_ASSERTIONS: {len(flagged)} flagged")
    print(f"Report: {output_path}")


if __name__ == "__main__":
    # --uncited <draft> <out_md>  -- advisory uncited-assertion detector
    if len(sys.argv) >= 2 and sys.argv[1] == "--uncited":
        if len(sys.argv) < 4:
            print(f"Usage: {sys.argv[0]} --uncited <draft> <out_md>")
            sys.exit(1)
        if not Path(sys.argv[2]).exists():
            print(f"ERROR: review file not found: {sys.argv[2]}")
            sys.exit(1)
        run_uncited(sys.argv[2], sys.argv[3])
        sys.exit(0)

    # Default: claim-attribution gate
    if len(sys.argv) < 4:
        print(f"Usage: {sys.argv[0]} <draft> <claim_attribution.jsonl> <output.md>")
        sys.exit(1)
    if not Path(sys.argv[1]).exists():
        print(f"ERROR: review file not found: {sys.argv[1]}")
        sys.exit(1)
    sys.exit(verify(sys.argv[1], sys.argv[2], sys.argv[3]))
