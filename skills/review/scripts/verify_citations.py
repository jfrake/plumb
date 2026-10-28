#!/usr/bin/env python3
"""
Citation Verifier for Plumb
Verifies that references cited in a review.txt file are real papers
with correct authors, years, and venues.

Uses OpenAlex API (free, no key needed, polite pool with mailto).

Usage:
    python3 verify_citations.py <draft> <output_path> [mailto]

Output:
    A markdown report with verification status for each reference.

Input format (plain text review):
    REFERENCES section is identified by a line "REFERENCES" (ALL CAPS).
    Each reference is a paragraph separated from the next by a blank line.

Exit codes:
    0   No structural defects detected and no hard verification failures.
    1   One or more DEFINITE CONTENT DEFECTS exist (hard block):
          - Body contains in-text citations but the REFERENCES section is absent
            or empty (reviewer fabricated citations without a reference list).
          - Dangling body citations: cited in the review body but absent from
            the REFERENCES section (mismatched citation / reference list).
          - NOT_FOUND: a listed reference could not be matched in any academic
            database (possible hallucination).
          - AUTHOR_MISMATCH: a reference title matches a real paper but the
            cited authors do not (likely misattribution).
    2   One or more INFRASTRUCTURE/PARSE FAILURES (non-blocking, surface to human):
          - COULD_NOT_SEARCH: a reference entry contained insufficient metadata
            to form a search query (no extractable author, title, or year).
          - All network/API lookups returned empty results (transient failure).
        These are flagged in citation_verification.md for human review but must
        NOT block the accuracy-audit gate the way a content defect does: log a
        warning and proceed; do NOT FATAL.

    LIKELY_MATCH and VERIFIED outcomes do not contribute to a nonzero exit.
    ACCEPTED (a NOT_FOUND or AUTHOR_MISMATCH entry the user marked a false flag,
    read with --workspace from the run's audit log) does not either.
    Exit 1 takes priority over exit 2 when both classes are present.
"""
from __future__ import annotations

import sys
import re
import time
import json
from pathlib import Path

try:
    import requests
except ImportError:
    # requests is an infrastructure dependency, not a content problem.
    # Exit 2 (non-blocking infra unavailable) rather than 1 (content defect).
    print("ERROR: requests not installed (infra unavailable). Run: pip install requests")
    sys.exit(2)

# Module-level import of citation_parser with importlib fallback so a misconfigured
# sys.path fails at startup (before any citations are processed) rather than mid-run
# when extract_body_citations is first called.  Mirrors the pattern in
# verify_claim_attribution.py.
try:
    from citation_parser import (
        extract_body_citations as _parse_body_citations,
        surname_lookup_keys as _surname_lookup_keys,
    )
except ImportError:
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location(
        "citation_parser",
        str(Path(__file__).parent / "citation_parser.py"),
    )
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    _parse_body_citations = _mod.extract_body_citations
    _surname_lookup_keys = _mod.surname_lookup_keys


MAILTO = ""  # For OpenAlex/CrossRef polite pool; overridable via the mailto CLI arg


class LookupUnavailable(Exception):
    """Raised by search helpers when the API is unreachable (network error, 429, 5xx).

    Distinct from an empty successful response (HTTP 200 with zero results).
    A reference that triggers this on EVERY API is classified SEARCH_UNAVAILABLE,
    which maps to exit 2 (non-blocking infra failure), NOT NOT_FOUND (exit 1).
    """


def extract_references_from_text(review_path):
    """Extract structured references from the REFERENCES section of a plain-text review."""
    with open(review_path, "r") as f:
        content = f.read()

    # Find the REFERENCES section (ALL CAPS header on its own line)
    ref_match = re.search(
        r"^REFERENCES\s*\n(.*?)(?=^[A-Z][A-Z ]{2,}$|\Z)",
        content,
        re.DOTALL | re.MULTILINE,
    )
    if not ref_match:
        return []

    ref_text = ref_match.group(1)

    # Each reference is a paragraph separated by blank line(s)
    raw_refs = re.split(r"\n\s*\n", ref_text)
    raw_refs = [r.strip() for r in raw_refs if r.strip()]

    references = []
    for raw in raw_refs:
        # Plain text — no LaTeX commands to strip; just normalize whitespace
        clean = re.sub(r"\s+", " ", raw).strip()

        # Try to extract structured info
        ref = {"raw": clean}

        # Extract year — matches "(2020)" or "Author. 2020." (period-delimited)
        year_match = re.search(r"\((\d{4})\)|(?<=[\s.])(\d{4})(?=[.\s,])", clean)
        if year_match:
            ref["year"] = int(year_match.group(1) or year_match.group(2))

        # Extract authors (everything before the year)
        if year_match:
            author_text = clean[: year_match.start()].strip().rstrip(",").rstrip(".")
            # Split on " and " or ", "
            ref["authors_raw"] = author_text

            # Extract last names (including particle surnames like "von Hippel").
            # Splitting on commas handles "Smith, J." style but also gives us
            # "von Hippel" as a single chunk when the reference is formatted as
            # "von Hippel, E. (2005)".
            parts = re.split(r",\s*(?:and\s+)?", author_text)
            last_names = []
            from citation_parser import _PARTICLES as _CP_PARTICLES
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                # "Smith, J.H." -> part is "Smith" after comma split -> "Smith"
                # "J.H. Smith"  -> first long non-initial word -> "Smith"
                # "von Hippel"  -> particle + capitalized word -> "von Hippel"
                words = part.split()
                # Phase 1: skip leading initials (e.g., "J.H." in "J.H. Smith")
                # but do NOT skip particles (particles are the prefix of the
                # compound surname, e.g. "von" in "von Hippel").
                idx = 0
                while idx < len(words):
                    w = words[idx]
                    is_particle = w.lower() in _CP_PARTICLES
                    is_initial = len(w) <= 2 or w.endswith(".")
                    if is_initial and not is_particle:
                        idx += 1  # skip this initial
                    else:
                        break  # reached a particle or a real surname word
                # Phase 2: collect the compound surname (particles + terminal word).
                # Accumulate consecutive particles, then one non-particle word.
                collected: list[str] = []
                while idx < len(words):
                    w = words[idx]
                    is_particle = w.lower() in _CP_PARTICLES
                    collected.append(w)
                    idx += 1
                    if not is_particle:
                        # Terminal word of the surname; stop.
                        break
                if collected:
                    last_names.append(" ".join(collected))
            ref["last_names"] = last_names

        # Extract title (usually between year and journal)
        if year_match:
            after_year = clean[year_match.end() :].strip().lstrip(".").strip()
            # Title is typically before the first italic/journal reference
            # or before a period followed by a journal name
            title_match = re.match(r"([^.]+(?:\.[^.]+)?)\.", after_year)
            if title_match:
                ref["title_fragment"] = title_match.group(1).strip()

        references.append(ref)

    return references


def extract_body_citations(review_path):
    """Extract all in-text citations from the review body (before REFERENCES section).

    Delegates to citation_parser.extract_body_citations so that this script and
    verify_claim_attribution.py use the same parser.  See citation_parser.py for
    the full list of recognised citation forms (narrative, parenthetical, particles,
    accented characters, hyphenated names, semicolon multi-cite).
    """
    return _parse_body_citations(review_path)


def search_semantic_scholar(query, limit=5):
    """Search Semantic Scholar (primary — better for book chapters and econ papers).

    Returns a list of normalised paper records on HTTP 200.
    Raises LookupUnavailable on network errors, 429 (rate-limit), or 5xx so that
    the caller can distinguish reachability failure from a successful empty result.
    """
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": query,
        "limit": limit,
        "fields": "title,authors,year,venue,citationCount,externalIds",
    }
    # S2 API key from environment if available (higher rate limits)
    api_key = __import__("os").environ.get("S2_API_KEY")
    headers = {"x-api-key": api_key} if api_key else {}

    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=15)
            if r.status_code == 200:
                data = r.json().get("data", [])
                # Normalize to OpenAlex-like format for match_reference
                normalized = []
                for paper in data:
                    authors = [
                        {"author": {"display_name": a.get("name", "")}}
                        for a in paper.get("authors", [])
                    ]
                    normalized.append({
                        "title": paper.get("title", ""),
                        "authorships": authors,
                        "publication_year": paper.get("year"),
                        "primary_location": {
                            "source": {"display_name": paper.get("venue", "")}
                        },
                        "cited_by_count": paper.get("citationCount", 0),
                        "doi": paper.get("externalIds", {}).get("DOI", ""),
                    })
                return normalized
            elif r.status_code == 429:
                wait = 2 ** (attempt + 1)
                time.sleep(wait)
                last_exc = LookupUnavailable(f"S2 rate-limited (429) after {attempt+1} attempt(s)")
                continue
            else:
                raise LookupUnavailable(f"S2 HTTP {r.status_code}")
        except LookupUnavailable:
            raise
        except Exception as exc:
            raise LookupUnavailable(f"S2 network error: {exc}") from exc
    # All attempts exhausted (repeated 429s)
    raise last_exc or LookupUnavailable("S2 all retries exhausted")


def search_openalex(query, limit=5, mailto=None):
    """Search OpenAlex (fallback — better coverage for older/obscure papers).

    Returns a list of records on HTTP 200.
    Raises LookupUnavailable on network errors or non-200 responses.
    """
    mailto = MAILTO if mailto is None else mailto
    url = "https://api.openalex.org/works"
    params = {"search": query, "per_page": limit}
    if mailto:
        params["mailto"] = mailto

    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 200:
            return r.json().get("results", [])
        raise LookupUnavailable(f"OpenAlex HTTP {r.status_code}")
    except LookupUnavailable:
        raise
    except Exception as exc:
        raise LookupUnavailable(f"OpenAlex network error: {exc}") from exc


def search_crossref(query, limit=5):
    """Search CrossRef (primary — best for book chapters, no rate limits with mailto).

    Returns a list of normalised records on HTTP 200.
    Raises LookupUnavailable on network errors or non-200 responses.
    """
    url = "https://api.crossref.org/works"
    params = {"query": query, "rows": limit}
    if MAILTO:
        params["mailto"] = MAILTO

    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 200:
            items = r.json().get("message", {}).get("items", [])
            normalized = []
            for item in items:
                authors_raw = item.get("author", [])
                authors = [
                    {"author": {"display_name": f"{a.get('given', '')} {a.get('family', '')}"}}
                    for a in authors_raw
                ]
                year_parts = item.get(
                    "published-print",
                    item.get("published-online", item.get("created", {})),
                )
                year = (
                    year_parts.get("date-parts", [[None]])[0][0]
                    if year_parts
                    else None
                )
                title = item.get("title", [""])[0] if item.get("title") else ""
                venue = (
                    item.get("container-title", [""])[0]
                    if item.get("container-title")
                    else ""
                )
                normalized.append({
                    "title": title,
                    "authorships": authors,
                    "publication_year": year,
                    "primary_location": {"source": {"display_name": venue}},
                    "cited_by_count": item.get("is-referenced-by-count", 0),
                    "doi": item.get("DOI", ""),
                })
            return normalized
        raise LookupUnavailable(f"CrossRef HTTP {r.status_code}")
    except LookupUnavailable:
        raise
    except Exception as exc:
        raise LookupUnavailable(f"CrossRef network error: {exc}") from exc


def search_paper(query, limit=5):
    """Search three APIs: CrossRef first, then Semantic Scholar, then OpenAlex.

    Returns (results, source, all_unavailable) where:
      results        -- list of normalised paper records (may be [])
      source         -- string name of the API that answered, or None
      all_unavailable -- True when EVERY API call raised LookupUnavailable
                         (network outage / all rate-limited). False when at
                         least one API returned HTTP 200 (even with zero results).

    Callers must inspect all_unavailable before treating an empty results list as
    evidence that the paper does not exist. Empty results + all_unavailable means
    "could not check", NOT "not found".
    """
    apis = [
        ("CrossRef", search_crossref),
        ("Semantic Scholar", search_semantic_scholar),
        ("OpenAlex", search_openalex),
    ]

    any_reachable = False
    for source_name, fn in apis:
        try:
            results = fn(query, limit)
            # fn returned normally -> API was reachable (HTTP 200), even if empty
            any_reachable = True
            if results:
                return results, source_name, False
        except LookupUnavailable:
            # This API was unreachable; try the next one
            continue

    # No API returned results. Distinguish "all failed" from "all returned []".
    return [], None, not any_reachable


def _is_review_of(ref, result):
    """A book review: the record's title names the work and then "By <a cited author>"."""
    names = [n for n in ref.get("last_names", []) if n]
    if not names:
        return False
    # A record by a cited author is the work itself, never a review of it.
    for a in result.get("authorships", []):
        parts = (a.get("author", {}).get("display_name") or "").split()
        if parts and parts[-1].lower() in {n.lower() for n in names}:
            return False
    for m in re.finditer(r"\bby\s+(.{0,120})", result.get("title") or "", flags=re.IGNORECASE):
        if any(re.search(r"\b" + re.escape(n) + r"\b", m.group(1), flags=re.IGNORECASE) for n in names):
            return True
    return False


def match_reference(ref, results):
    """
    Check if any OpenAlex result matches the reference.
    Returns (match_quality, matched_result) or (None, None). A VERIFIED result that comes before
    any scored hit wins. A VERIFIED result after an earlier scored hit wins only when it also
    matches the title strongly (more than half the title words). Otherwise the first result that
    scores a weaker match is returned. A record that is a review of the cited work is skipped.
    """
    if not results:
        return None, None

    first = None
    for result in results:
        if _is_review_of(ref, result):
            continue
        score = 0
        details = []

        # Year match (allow ±3 years for working paper → published version gaps)
        if ref.get("year") and result.get("publication_year"):
            year_diff = abs(ref["year"] - result["publication_year"])
            if year_diff == 0:
                score += 3
                details.append("year match")
            elif year_diff <= 1:
                score += 2
                details.append(f"year close ({ref['year']} vs {result['publication_year']})")
            elif year_diff <= 3:
                score += 1
                details.append(f"year within 3 ({ref['year']} vs {result['publication_year']}, likely WP→pub gap)")

        # Author match (check if last names overlap)
        ref_last = [n.lower() for n in ref.get("last_names", [])]
        result_authors = [
            a.get("author", {}).get("display_name", "")
            for a in result.get("authorships", [])
        ]
        result_last_names = []
        for name in result_authors:
            parts = name.split()
            if parts:
                result_last_names.append(parts[-1].lower())

        present = [n for n in ref_last if n in result_last_names]
        matches = len(present)
        if ref_last:
            if matches >= 2:
                score += 4
                details.append(f"{matches} author last names match")
            elif matches == 1 and len(ref_last) == 1:
                score += 2
                details.append("single author match")
            elif matches == 1:
                score += 1
                details.append("1 of multiple authors match")

        # Title fragment match (fuzzy)
        title_overlap = 0.0
        if ref.get("title_fragment") and result.get("title"):
            ref_words = set(ref["title_fragment"].lower().split())
            result_words = set(result["title"].lower().split())
            # Remove common words
            stopwords = {"a", "an", "the", "of", "in", "for", "and", "on", "to", "with", "by"}
            ref_words -= stopwords
            result_words -= stopwords
            if ref_words and result_words:
                title_overlap = len(ref_words & result_words) / max(len(ref_words), 1)
                if title_overlap > 0.5:
                    score += 3
                    details.append(f"title overlap {title_overlap:.0%}")
                elif title_overlap > 0.25:
                    score += 1
                    details.append(f"partial title overlap {title_overlap:.0%}")

        # Author-consistency gate. A strong title match with the WRONG authors is a
        # misattribution: a real paper cited with fabricated or incorrect co-authors.
        # That is more dangerous than a missing reference because it passes a naive
        # existence check. It must never be reported as VERIFIED. This is the failure
        # that let "Smith, Jones, Lee" pass for a paper actually by Smith, Park, Kim:
        # title + year alone cleared the threshold while two of three cited authors
        # were absent from the record and cost nothing.
        author_ratio = (matches / len(ref_last)) if ref_last else 1.0
        title_strong = title_overlap > 0.5
        author_inconsistent = bool(ref_last) and author_ratio < 0.6

        if score >= 5:
            if not author_inconsistent:
                # A VERIFIED hit after an earlier scored hit must also match the title strongly,
                # so year plus one shared surname cannot overturn a misattribution.
                if first is None or title_strong:
                    return "VERIFIED", result
                continue
            # Right title, wrong authors: a misattribution. Title/year alone: a likely match.
            quality = "AUTHOR_MISMATCH" if title_strong else "LIKELY_MATCH"
        elif score >= 3:
            quality = "LIKELY_MATCH"
        else:
            continue
        if first is None:
            first = (quality, result)

    return first or (None, None)


def _heading(ref):
    """The heading a reference gets in the report's attention list."""
    return f"{ref.get('authors_raw', ref['raw'][:50])} ({ref.get('year', '?')})"


def _key(text):
    return " ".join(str(text).split()).casefold()


def accepted_refs(workspace):
    """Reference entries the user marked false flags: `verification` events with check
    "accepted_flag" and step "verify_citations" in <workspace>/audit/events.jsonl, keyed by the
    entry's text."""
    p = Path(workspace) / "audit" / "events.jsonl"
    out = set()
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if (e.get("kind") == "verification" and e.get("check") == "accepted_flag"
                and e.get("step") == "verify_citations" and e.get("ref")):
            out.add(_key(e["ref"]))
    return out


def verify_references(review_path, output_path, accepted=frozenset()):
    """Main verification pipeline."""
    review_path = Path(review_path)
    output_path = Path(output_path)

    # Extract references and body citations
    references = extract_references_from_text(review_path)
    body_citations = extract_body_citations(review_path)

    if not references:
        with open(output_path, "w") as f:
            f.write("# Citation Verification Report\n\nNo references found in the review.\n")
            if body_citations:
                f.write(
                    "\n> GATE FAIL: The review body contains in-text citations but "
                    "the REFERENCES section is absent or empty.\n"
                )
        print("No references found")
        # If there are body citations and no REFERENCES section, that is a structural defect.
        return 1 if body_citations else 0

    print(f"Found {len(references)} references and {len(body_citations)} body citations")

    # Verify each reference
    results = []
    for i, ref in enumerate(references):
        # Build search query from available info
        query_parts = []
        if ref.get("last_names"):
            query_parts.extend(ref["last_names"][:3])
        if ref.get("title_fragment"):
            # Use first 6 meaningful words of title
            words = ref["title_fragment"].split()[:6]
            query_parts.extend(words)
        if ref.get("year"):
            query_parts.append(str(ref["year"]))

        query = " ".join(query_parts)

        if not query.strip():
            results.append({
                "ref": ref,
                "status": "COULD_NOT_SEARCH",
                "detail": "No searchable content extracted",
            })
            continue

        print(f"  [{i+1}/{len(references)}] Searching: {query[:60]}...")
        search_results, source, all_unavailable = search_paper(query)
        time.sleep(0.5)  # Rate limiting

        # Track whether any search attempt for this reference received a
        # reachable response (HTTP 200, even with zero results).  A reference
        # is SEARCH_UNAVAILABLE only if NO attempt ever got a reachable
        # response.  If the precise pass was reachable-empty but the broad
        # retry is all-unavailable, the reference is still NOT_FOUND (because
        # we know the APIs can be reached and found nothing on the precise
        # query).
        saw_reachable_empty = not all_unavailable

        # If every API was unreachable on the precise search (network outage /
        # all rate-limited), tentatively classify as SEARCH_UNAVAILABLE.  We
        # will confirm or downgrade after the broad retry below.
        if all_unavailable:
            results.append({
                "ref": ref,
                "status": "SEARCH_UNAVAILABLE",
                "detail": (
                    "All citation APIs unreachable (network outage or rate-limit). "
                    "Cannot determine whether this reference exists. Recheck manually."
                ),
            })
            continue

        match_quality, matched = match_reference(ref, search_results)

        if match_quality == "VERIFIED":
            result_authors = [
                a.get("author", {}).get("display_name", "")
                for a in matched.get("authorships", [])[:5]
            ]
            results.append({
                "ref": ref,
                "status": "VERIFIED",
                "matched_title": matched.get("title", ""),
                "matched_authors": result_authors,
                "matched_year": matched.get("publication_year"),
                "matched_venue": matched.get("primary_location", {}).get(
                    "source", {}
                ).get("display_name", ""),
                "citations": matched.get("cited_by_count", 0),
                "doi": matched.get("doi", ""),
            })
        elif match_quality == "LIKELY_MATCH":
            result_authors = [
                a.get("author", {}).get("display_name", "")
                for a in matched.get("authorships", [])[:5]
            ]
            results.append({
                "ref": ref,
                "status": "LIKELY_MATCH",
                "matched_title": matched.get("title", ""),
                "matched_authors": result_authors,
                "matched_year": matched.get("publication_year"),
                "matched_venue": matched.get("primary_location", {}).get(
                    "source", {}
                ).get("display_name", ""),
                "citations": matched.get("cited_by_count", 0),
                "doi": matched.get("doi", ""),
                "note": "Partial match -- verify manually",
            })
        elif match_quality == "AUTHOR_MISMATCH":
            result_authors = [
                a.get("author", {}).get("display_name", "")
                for a in matched.get("authorships", [])[:5]
            ]
            results.append({
                "ref": ref,
                "status": "AUTHOR_MISMATCH",
                "matched_title": matched.get("title", ""),
                "matched_authors": result_authors,
                "matched_year": matched.get("publication_year"),
                "matched_venue": matched.get("primary_location", {}).get(
                    "source", {}
                ).get("display_name", ""),
                "citations": matched.get("cited_by_count", 0),
                "doi": matched.get("doi", ""),
                "note": (
                    "TITLE MATCHES a real paper but the cited AUTHORS do not. "
                    "Likely a misattribution. Replace the cited authors with the "
                    "matched record's authors, or drop the citation."
                ),
            })
        else:
            # At least one API answered (HTTP 200) with zero results on the
            # precise search.  Try a broader search with just author + year
            # before giving up.
            if ref.get("last_names") and ref.get("year"):
                broad_query = f"{ref['last_names'][0]} {ref['year']}"
                broad_results, _, broad_unavailable = search_paper(broad_query, limit=10)
                time.sleep(0.5)
                # Update the reachable flag: if the broad retry also got a
                # reachable response, saw_reachable_empty stays True (or
                # becomes True).
                if not broad_unavailable:
                    saw_reachable_empty = True
                if broad_unavailable and not saw_reachable_empty:
                    # Neither attempt ever reached a working API -- genuine
                    # infra failure.
                    results.append({
                        "ref": ref,
                        "status": "SEARCH_UNAVAILABLE",
                        "detail": (
                            "All citation APIs unreachable on broad search. "
                            "Cannot determine whether this reference exists."
                        ),
                    })
                    continue
                match_quality2, matched2 = match_reference(ref, broad_results)
                if match_quality2:
                    result_authors = [
                        a.get("author", {}).get("display_name", "")
                        for a in matched2.get("authorships", [])[:5]
                    ]
                    results.append({
                        "ref": ref,
                        "status": match_quality2,
                        "matched_title": matched2.get("title", ""),
                        "matched_authors": result_authors,
                        "matched_year": matched2.get("publication_year"),
                        "matched_venue": matched2.get("primary_location", {}).get(
                            "source", {}
                        ).get("display_name", ""),
                        "citations": matched2.get("cited_by_count", 0),
                        "doi": matched2.get("doi", ""),
                        "note": "Found on broad search",
                    })
                    continue

            # API(s) answered HTTP 200 with zero results on both attempts.
            # This is a genuine NOT_FOUND (content defect, exit 1).
            results.append({
                "ref": ref,
                "status": "NOT_FOUND",
                "detail": f"No match found for query: {query[:80]}",
            })

    # A reference the user marked a false flag counts as checked.
    for r in results:
        if r["status"] in ("NOT_FOUND", "AUTHOR_MISMATCH") and _key(r["ref"]["raw"]) in accepted:
            r["status"] = "ACCEPTED"
            r["note"] = "You marked this a false flag; it counts as checked."

    # Check for dangling body citations (cited in text but not in References).
    # Both sides are normalized via _surname_lookup_keys so that particle
    # surnames like "von Hippel" match whether the reference stored "von Hippel"
    # as a unit or whether the body citation spelled out "Hippel" alone.
    ref_keys_years: set[tuple[str, int]] = set()
    for ref in references:
        if ref.get("last_names") and ref.get("year"):
            for name in ref["last_names"]:
                for key in _surname_lookup_keys(name):
                    ref_keys_years.add((key, ref["year"]))

    dangling_citations = []
    for author_text, year in body_citations:
        # Expand the body-citation author string into lookup keys covering
        # both plain surnames and full particle+surname compounds.
        found = False
        for key in _surname_lookup_keys(author_text):
            if (key, year) in ref_keys_years:
                found = True
                break
        if not found:
            # Also check individual capitalised words longer than 2 chars
            # (preserves the original behaviour for non-particle names).
            author_words = [
                w.lower()
                for w in author_text.split()
                if len(w) > 2 and w[0].isupper()
            ]
            for name in author_words:
                if (name, year) in ref_keys_years:
                    found = True
                    break
        if not found:
            dangling_citations.append(f"{author_text} ({year})")

    # Write report
    with open(output_path, "w") as f:
        f.write("# Citation Verification Report\n\n")
        f.write(f"**Review file:** {review_path.name}\n")
        f.write(f"**References checked:** {len(references)}\n")

        verified = sum(1 for r in results if r["status"] == "VERIFIED")
        likely = sum(1 for r in results if r["status"] == "LIKELY_MATCH")
        author_mismatch = sum(1 for r in results if r["status"] == "AUTHOR_MISMATCH")
        not_found = sum(1 for r in results if r["status"] == "NOT_FOUND")
        search_unavailable = sum(1 for r in results if r["status"] == "SEARCH_UNAVAILABLE")
        could_not_search = sum(1 for r in results if r["status"] == "COULD_NOT_SEARCH")
        f.write(
            f"**Verified:** {verified} | **Likely match:** {likely} | "
            f"**Author mismatch:** {author_mismatch} | **Not found:** {not_found} | "
            f"**Search unavailable (infra):** {search_unavailable} | "
            f"**Could not search (parse):** {could_not_search}\n\n"
        )
        if author_mismatch:
            f.write(f"> WARNING: {author_mismatch} reference(s) match a real paper's title but cite the WRONG authors (likely misattribution). See Issues Requiring Attention.\n\n")

        if dangling_citations:
            f.write("## Dangling Body Citations\n\n")
            f.write("These citations appear in the review text but have no matching References entry:\n\n")
            for dc in sorted(dangling_citations):
                f.write(f"- {dc}\n")
            f.write("\n")

        f.write("## Verification Details\n\n")
        f.write("| # | Review Reference | Status | Matched Title | Year | Venue | Citations |\n")
        f.write("|---|-----------------|--------|---------------|------|-------|-----------|\n")

        for i, r in enumerate(results, 1):
            ref_short = r["ref"].get("authors_raw", r["ref"]["raw"][:40])[:35]
            year = r["ref"].get("year", "?")
            status = r["status"]

            if status in ("VERIFIED", "LIKELY_MATCH", "AUTHOR_MISMATCH"):
                title = r["matched_title"][:40] if r.get("matched_title") else ""
                venue = r.get("matched_venue", "")[:25]
                cites = r.get("citations", "")
                f.write(f"| {i} | {ref_short} ({year}) | {status} | {title} | {r.get('matched_year', '')} | {venue} | {cites} |\n")
            else:
                detail = r.get("detail", "")[:40]
                f.write(f"| {i} | {ref_short} ({year}) | {status} | {detail} | | | |\n")

        # Detailed findings for non-verified
        issues = [r for r in results if r["status"] not in ("VERIFIED",)]
        if issues:
            f.write("\n## Issues Requiring Attention\n\n")
            for r in issues:
                ref = r["ref"]
                f.write(f"### {_heading(ref)}\n\n")
                f.write(f"- **Entry:** {ref['raw']}\n")
                f.write(f"- **Status:** {r['status']}\n")
                if r.get("matched_title"):
                    f.write(f"- **Closest match:** {r['matched_title']}\n")
                    f.write(f"- **Match authors:** {', '.join(r.get('matched_authors', []))}\n")
                    f.write(f"- **Match year:** {r.get('matched_year')}\n")
                if r.get("note"):
                    f.write(f"- **Note:** {r['note']}\n")
                if r.get("detail"):
                    f.write(f"- **Detail:** {r['detail']}\n")
                f.write("\n")

    print(f"\nResults: {verified} verified, {likely} likely, {not_found} not found, "
          f"{search_unavailable} search_unavailable, {could_not_search} could_not_search")
    print(f"Report: {output_path}")

    # Content defects: hard block (exit 1).  These indicate actual accuracy
    # problems -- fabricated references or misattributed authors.
    content_defects = sum(
        1 for r in results
        if r["status"] in ("NOT_FOUND", "AUTHOR_MISMATCH")
    )
    # Dangling body citations are also a content/structural defect.
    if dangling_citations:
        content_defects += len(dangling_citations)

    # Infrastructure/parse failures: non-blocking (exit 2).  These signal that
    # the verifier could not evaluate the reference due to missing metadata or a
    # transient network problem -- NOT that the reference is wrong.
    #   COULD_NOT_SEARCH   -- no extractable author/title/year to form a query
    #   SEARCH_UNAVAILABLE -- every API was unreachable (network outage / rate-limit)
    infra_failures = sum(
        1 for r in results
        if r["status"] in ("COULD_NOT_SEARCH", "SEARCH_UNAVAILABLE")
    )

    if content_defects > 0:
        return 1
    if infra_failures > 0:
        return 2
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    workspace = None
    if "--workspace" in args:
        i = args.index("--workspace")
        workspace = args[i + 1] if i + 1 < len(args) else None
        del args[i:i + 2]
    if len(args) < 2:
        print(f"Usage: {sys.argv[0]} <draft> <output.md> [mailto] [--workspace <workspace>]")
        sys.exit(1)

    review_path = args[0]
    output_path = args[1]
    if len(args) > 2:
        MAILTO = args[2]

    if not Path(review_path).exists():
        print(f"ERROR: File not found: {review_path}")
        sys.exit(1)

    sys.exit(verify_references(review_path, output_path,
                               accepted_refs(workspace) if workspace else frozenset()))
