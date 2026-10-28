#!/usr/bin/env python3
"""
Programmatic Quote Verification for Plumb

Extracts quoted text from a plain-text review and verifies each quote against
the source PDF using fuzzy matching. Produces a verification ledger that
the accuracy audit agent uses to prioritize checking.

Uses a three-tier approach:
  Tier 1: Exact substring match (whitespace-normalized)
  Tier 2: Jaccard pre-filter + SequenceMatcher (0.80 prose, 0.92 numbers)
  Tier 3: Flag as UNVERIFIABLE

Usage:
    python3 verify_quotes.py <draft> <pdf_path> <output_dir> [csv_dir]

Output:
    <output_dir>/quote_verification.md
"""

from __future__ import annotations

import csv
import difflib
import re
import sys
from pathlib import Path

import pymupdf


# --- Thresholds ---

MIN_MATCH_RATIO_PROSE = 0.80
MIN_MATCH_RATIO_NUMERIC = 0.92
JACCARD_PREFILTER_THRESHOLD = 0.15
JACCARD_TOP_K = 5
MIN_QUOTE_LENGTH = 10  # Skip very short quotes


# --- Quote extraction from plain text ---

# Patterns that capture quoted paper text in plain-text reviews.
# Plain-text reviews use straight double quotes "..." or single quotes '...';
# curly quotes ("...", '...') are also supported in case the model emits them.
QUOTE_PATTERNS = [
    # Straight double quotes "..."
    re.compile(r'"([^"\n]{10,}?)"'),
    # Curly double quotes "..."
    re.compile(r'“([^”\n]{10,}?)”'),
    # Single quotes '...' (only when likely to be a quote, not contraction)
    re.compile(r"(?<!\w)'([^'\n]{10,}?)'(?!\w)"),
    # Curly single quotes '...'
    re.compile(r"(?<!\w)‘([^’\n]{10,}?)’(?!\w)"),
]

# Pattern to detect numeric content (coefficients, p-values, sample sizes)
NUMERIC_PATTERN = re.compile(
    r"\d+\.\d+"          # decimals
    r"|\bp\s*[<>=]"      # p-values
    r"|\bN\s*="          # sample sizes
    r"|[*]{1,3}"         # significance stars
    r"|\b\d{2,}"         # multi-digit numbers
)


def extract_quotes_from_review(review_path: str) -> list[dict]:
    """Extract all quoted text from a plain-text review file.

    Returns list of dicts: {quote, line_num, pattern, is_numeric}
    """
    text = Path(review_path).read_text(encoding="utf-8")
    quotes = []
    seen = set()

    for line_num, line in enumerate(text.splitlines(), 1):
        for pattern in QUOTE_PATTERNS:
            for match in pattern.finditer(line):
                quote = _normalize(match.group(1).strip())

                if len(quote) < MIN_QUOTE_LENGTH:
                    continue
                if quote in seen:
                    continue
                seen.add(quote)

                is_numeric = bool(NUMERIC_PATTERN.search(quote))
                quotes.append({
                    "quote": quote,
                    "line_num": line_num,
                    "pattern": pattern.pattern[:30],
                    "is_numeric": is_numeric,
                })

    return quotes


def _normalize(text: str) -> str:
    """Normalize whitespace in quoted text."""
    return re.sub(r"\s+", " ", text).strip()


# --- PDF text extraction ---

def extract_pdf_text(pdf_path: str) -> str:
    """Extract full text from PDF."""
    doc = pymupdf.open(pdf_path)
    parts = []
    for page in doc:
        parts.append(page.get_text("text"))
    doc.close()
    return "\n".join(parts)


# --- Fuzzy matching ---

def _tokenize(text: str) -> set[str]:
    """Split lowercased text into word-level tokens."""
    return set(text.lower().split())


def _jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity between two token sets."""
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _normalize_whitespace(text: str) -> str:
    """Normalize all whitespace to single spaces, lowercase."""
    return re.sub(r"\s+", " ", text.lower()).strip()


def find_best_match(
    quote: str, paper_text: str, window_factor: float = 1.5
) -> tuple[str, float]:
    """Find the passage in paper_text most similar to quote.

    Two-phase approach:
    1. Cheap Jaccard pre-filter on overlapping chunks
    2. Expensive SequenceMatcher on top-k candidates

    Returns (best_matching_passage, match_ratio).
    """
    if not quote or not paper_text:
        return "", 0.0

    quote_len = len(quote)
    window_size = max(int(quote_len * window_factor), 50)
    step = max(1, quote_len // 4)

    quote_tokens = _tokenize(quote)

    # Phase 1: Jaccard pre-filter
    candidates: list[tuple[float, int]] = []
    max_start = len(paper_text) - min(quote_len, len(paper_text)) + 1
    for i in range(0, max_start, step):
        chunk = paper_text[i : i + window_size]
        score = _jaccard(quote_tokens, _tokenize(chunk))
        if score >= JACCARD_PREFILTER_THRESHOLD:
            candidates.append((score, i))

    if not candidates:
        return "", 0.0

    # Take top-k by Jaccard score
    candidates.sort(key=lambda x: x[0], reverse=True)
    top_candidates = candidates[:JACCARD_TOP_K]

    # Phase 2: SequenceMatcher on top candidates
    quote_lower = quote.lower()
    best_ratio = 0.0
    best_passage = ""

    for _, i in top_candidates:
        candidate = paper_text[i : i + window_size]
        ratio = difflib.SequenceMatcher(
            None, quote_lower, candidate.lower()
        ).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_passage = candidate

    # Trim to best-fitting subsequence
    if best_passage and best_ratio >= MIN_MATCH_RATIO_PROSE:
        best_passage = _trim_to_best_match(quote, best_passage)

    return best_passage, best_ratio


def _trim_to_best_match(quote: str, passage: str) -> str:
    """Find the subsequence of passage that best matches quote."""
    if len(passage) <= len(quote):
        return passage

    window = min(len(passage), int(len(quote) * 1.5))
    best_ratio = 0.0
    best_sub = passage[:window]

    for start in range(0, len(passage) - window + 1, max(1, window // 8)):
        sub = passage[start : start + window]
        ratio = difflib.SequenceMatcher(None, quote.lower(), sub.lower()).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_sub = sub

    return best_sub.strip()


# --- CSV cross-check for numeric quotes ---

def check_against_csvs(quote: str, csv_dir: str) -> tuple[bool, str]:
    """Check if numeric values in a quote appear in extracted table CSVs.

    Strictness requirement: ALL distinct material numbers in the quote must be
    present somewhere in the CSV corpus (across all CSV files combined).  A
    quote is NOT verified when only a subset of its numbers are found.

    Star requirement: ALL distinct significance-star sequences in the quote
    (* ** ***) must also appear somewhere in the CSV corpus.  This prevents a
    fabricated significance level (e.g. "0.30***" when the paper reports "0.30")
    from passing via the CSV route when the reconciled CSVs do not contain the
    star token.  Uses _STAR_PATTERN, the same pattern used by the passage route,
    to keep both routes consistent.

    Returns (found, details_string).
    """
    csv_path = Path(csv_dir)
    if not csv_path.exists():
        return False, "no CSV directory"

    # Extract distinct numbers from the quote.
    numbers = list(dict.fromkeys(re.findall(r"-?\d+\.?\d*", quote)))
    if not numbers:
        return False, "no numbers in quote"

    # Extract distinct star sequences from the quote (reuse _STAR_PATTERN).
    star_sequences = list(dict.fromkeys(_STAR_PATTERN.findall(quote)))

    # Search CSVs for these numbers
    csv_files = list(csv_path.glob("*.csv"))
    if not csv_files:
        return False, "no CSV files"

    # Build the set of all numbers found anywhere in the CSV corpus.
    # Use token-boundary matching so "0.3" does not spuriously match inside "0.30".
    corpus_text_parts: list[str] = []
    per_file_hits: list[str] = []
    for csv_file in csv_files:
        try:
            content = csv_file.read_text(encoding="utf-8")
            corpus_text_parts.append(content)
            hits = sum(
                1 for n in numbers
                if re.search(r"(?<![.\d])" + re.escape(n) + r"(?![.\d])", content)
            )
            if hits > 0:
                per_file_hits.append(f"{csv_file.name} ({hits}/{len(numbers)} numbers)")
        except Exception:
            continue

    # Require every distinct number to appear somewhere in the combined corpus
    # at a token boundary (not as a substring of a longer number).
    corpus_text = "\n".join(corpus_text_parts)
    missing = [
        n for n in numbers
        if not re.search(r"(?<![.\d])" + re.escape(n) + r"(?![.\d])", corpus_text)
    ]

    if missing:
        missing_str = ", ".join(missing)
        found_count = len(numbers) - len(missing)
        return False, (
            f"{found_count}/{len(numbers)} numbers found; missing: {missing_str}"
        )

    # Require every distinct star sequence to appear in the combined corpus.
    missing_stars = [s for s in star_sequences if s not in corpus_text]
    if missing_stars:
        missing_stars_str = ", ".join(missing_stars)
        return False, (
            f"all numbers found but significance stars absent from corpus: {missing_stars_str}"
        )

    details = "; ".join(per_file_hits) if per_file_hits else "all numbers found in corpus"
    return True, details


# --- Numeric token verification against a passage ---

# Star sequences that can appear in a quote as significance markers (* ** ***).
# Sorted longest-first so *** is matched before ** or *.
_STAR_PATTERN = re.compile(r"\*{1,3}")


def _numbers_verified_in_passage(quote: str, passage: str) -> bool:
    """Return True if every distinct number AND significance star sequence in the
    quote appears in the passage.

    Number check: uses token-boundary regex so "0.3" does not spuriously match
    inside "0.30".  Returns True vacuously on the number side when the quote
    contains no digit tokens.

    Star check: each distinct star sequence present in the quote (* ** ***) must
    appear somewhere in the passage.  Fabricated significance attribution (e.g., a
    reviewer quoting "b=0.30***" when the paper reports "b=0.30" without stars, or
    with only one star) is caught here.  Returns True vacuously on the star side
    when the quote contains no star sequences.

    Both checks must pass.
    """
    passage_lower = passage.lower()

    # Number check.
    numbers = list(dict.fromkeys(re.findall(r"-?\d+\.?\d*", quote)))
    for n in numbers:
        if not re.search(r"(?<![.\d])" + re.escape(n) + r"(?![.\d])", passage_lower):
            return False

    # Star check: each distinct star sequence in the quote must appear in the passage.
    star_sequences = list(dict.fromkeys(_STAR_PATTERN.findall(quote)))
    for stars in star_sequences:
        if stars not in passage and stars not in passage_lower:
            return False

    return True


# --- Main verification ---

def verify_all_quotes(
    quotes: list[dict],
    paper_text: str,
    csv_dir: str | None = None,
) -> list[dict]:
    """Verify all quotes against paper text.

    Returns list of dicts with verification results.

    For numeric quotes the text-ratio threshold alone is not sufficient for
    acceptance: all distinct numbers in the quote must also be verified.
    Verification succeeds via one of two routes:
      (a) Passage route: every number in the quote appears in the best matched
          passage at a token boundary (same strictness as the CSV check).
      (b) CSV route: check_against_csvs confirms all numbers are present in the
          CSV corpus.
    If the text ratio is high but neither route verifies the numbers, the quote
    is marked UNVERIFIABLE.  Pure-prose (non-numeric) quotes are unchanged: a
    text ratio >= MIN_MATCH_RATIO_PROSE (0.80) is sufficient for FUZZY.
    """
    paper_lower = _normalize_whitespace(paper_text)
    results = []

    for q in quotes:
        quote = q["quote"]
        quote_normalized = _normalize_whitespace(quote)
        is_numeric = q["is_numeric"]
        threshold = MIN_MATCH_RATIO_NUMERIC if is_numeric else MIN_MATCH_RATIO_PROSE

        result = {
            **q,
            "status": "UNVERIFIABLE",
            "match_ratio": 0.0,
            "best_match": "",
            "csv_check": "",
        }

        # Tier 1: Exact substring match
        if quote_normalized in paper_lower:
            result["status"] = "EXACT"
            result["match_ratio"] = 1.0
            results.append(result)
            continue

        # Tier 2: Fuzzy match
        best_match, ratio = find_best_match(quote, paper_text)

        if ratio >= threshold:
            result["match_ratio"] = ratio
            result["best_match"] = best_match[:200]

            if not is_numeric:
                # Pure-prose quote: text ratio alone is sufficient.
                result["status"] = "FUZZY"
                results.append(result)
                continue

            # Numeric quote: verify numbers against the matched passage (route a).
            if _numbers_verified_in_passage(quote, best_match):
                result["status"] = "FUZZY"
                results.append(result)
                continue

            # Route (a) failed; try CSV route (route b).
            if csv_dir:
                csv_found, csv_details = check_against_csvs(quote, csv_dir)
                result["csv_check"] = csv_details
                if csv_found:
                    result["status"] = "CSV_VERIFIED"
                    results.append(result)
                    continue

            # Neither route verified the numbers; mark as UNVERIFIABLE so the
            # gate flags it, even though the surrounding text was highly similar.
            results.append(result)
            continue

        # Text ratio below threshold; for numeric quotes also try the CSV route.
        if is_numeric and csv_dir:
            csv_found, csv_details = check_against_csvs(quote, csv_dir)
            result["csv_check"] = csv_details
            if csv_found:
                result["status"] = "CSV_VERIFIED"
                result["match_ratio"] = ratio  # Keep the text ratio for reference
                results.append(result)
                continue

        # Tier 3: Unverifiable
        result["match_ratio"] = ratio
        if best_match:
            result["best_match"] = best_match[:200]
        results.append(result)

    return results


def generate_report(results: list[dict]) -> str:
    """Generate markdown verification report."""
    lines = []
    lines.append("# Quote Verification Report\n")

    # Summary counts
    exact = sum(1 for r in results if r["status"] == "EXACT")
    fuzzy = sum(1 for r in results if r["status"] == "FUZZY")
    csv_v = sum(1 for r in results if r["status"] == "CSV_VERIFIED")
    unverifiable = sum(1 for r in results if r["status"] == "UNVERIFIABLE")
    total = len(results)

    lines.append(f"**Total quotes checked:** {total}")
    lines.append(f"**Exact matches:** {exact}")
    lines.append(f"**Fuzzy matches:** {fuzzy}")
    lines.append(f"**CSV-verified:** {csv_v}")
    lines.append(f"**Unverifiable:** {unverifiable}")
    lines.append("")

    if unverifiable > 0:
        lines.append(f"> **ACTION REQUIRED:** {unverifiable} quote(s) could not be verified against")
        lines.append("> the paper text. The accuracy audit agent MUST fix or remove each one.")
        lines.append("")

    # Detailed ledger
    lines.append("## Verification Ledger\n")
    lines.append("| # | Line | Status | Ratio | Quote (truncated) | Notes |")
    lines.append("|---|------|--------|-------|--------------------|-------|")

    for i, r in enumerate(results, 1):
        quote_trunc = r["quote"][:60].replace("|", "\\|")
        if len(r["quote"]) > 60:
            quote_trunc += "..."
        notes = ""
        if r["status"] == "FUZZY":
            notes = f"Best match: {r['best_match'][:50]}..."
        elif r["status"] == "CSV_VERIFIED":
            notes = f"CSV: {r['csv_check']}"
        elif r["status"] == "UNVERIFIABLE":
            notes = f"Best ratio: {r['match_ratio']:.2f}"
            if r["best_match"]:
                notes += f"; nearest: {r['best_match'][:40]}..."
        notes = notes.replace("|", "\\|")

        numeric_tag = " [NUM]" if r["is_numeric"] else ""
        lines.append(
            f"| {i} | {r['line_num']} | {r['status']}{numeric_tag} | "
            f"{r['match_ratio']:.2f} | {quote_trunc} | {notes} |"
        )

    lines.append("")

    # Unverifiable detail section
    if unverifiable > 0:
        lines.append("## Unverifiable Quotes — Requires Manual Review\n")
        for i, r in enumerate(results, 1):
            if r["status"] != "UNVERIFIABLE":
                continue
            lines.append(f"### Quote {i} (line {r['line_num']})\n")
            lines.append(f"**Quote:** {r['quote']}\n")
            lines.append(f"**Best match ratio:** {r['match_ratio']:.2f}")
            if r["best_match"]:
                lines.append(f"**Nearest passage:** {r['best_match']}")
            if r["csv_check"]:
                lines.append(f"**CSV check:** {r['csv_check']}")
            lines.append(f"**Type:** {'Numeric' if r['is_numeric'] else 'Prose'}")
            lines.append(f"**Threshold:** {MIN_MATCH_RATIO_NUMERIC if r['is_numeric'] else MIN_MATCH_RATIO_PROSE}")
            lines.append("")

    return "\n".join(lines)


def main():
    if len(sys.argv) < 4:
        print(
            "Usage: python3 verify_quotes.py <draft> <paper.pdf> <output_dir> [csv_dir]",
            file=sys.stderr,
        )
        sys.exit(1)

    review_path = sys.argv[1]
    pdf_path = sys.argv[2]
    output_dir = Path(sys.argv[3])
    csv_dir = sys.argv[4] if len(sys.argv) > 4 else None

    output_dir.mkdir(parents=True, exist_ok=True)

    if not Path(review_path).exists():
        print(f"Error: Review file not found: {review_path}", file=sys.stderr)
        sys.exit(1)
    if not Path(pdf_path).exists():
        print(f"Error: PDF not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    # Extract quotes from review
    quotes = extract_quotes_from_review(review_path)
    if not quotes:
        print("No quotes found in review file.")
        report_path = output_dir / "quote_verification.md"
        report_path.write_text(
            "# Quote Verification Report\n\nNo quotes found in review file.\n",
            encoding="utf-8",
        )
        sys.exit(0)

    # Extract paper text
    paper_text = extract_pdf_text(pdf_path)

    # Verify
    results = verify_all_quotes(quotes, paper_text, csv_dir)
    report = generate_report(results)

    report_path = output_dir / "quote_verification.md"
    report_path.write_text(report, encoding="utf-8")

    # Summary to stdout
    exact = sum(1 for r in results if r["status"] == "EXACT")
    fuzzy = sum(1 for r in results if r["status"] == "FUZZY")
    unverifiable = sum(1 for r in results if r["status"] == "UNVERIFIABLE")
    print(f"Quote verification: {exact} exact, {fuzzy} fuzzy, {unverifiable} unverifiable out of {len(results)} quotes")

    # Exit code: 0 if all verified, 1 if any unverifiable
    sys.exit(1 if unverifiable > 0 else 0)


if __name__ == "__main__":
    main()
