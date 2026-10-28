"""
Shared body-citation extractor for Plumb.

Both verify_citations.py and verify_claim_attribution.py import from here so
they parse the same citation forms. verify_claim_attribution.py previously
carried its own inline copy; verify_citations.py had a narrower version.
This module supersedes both.

Recognised citation forms
--------------------------
Narrative (inline):
  Author (Year)                       Smith (2020)
  Author and Author (Year)            Smith and Jones (2020)
  Author, Author, and Author (Year)   Smith, Jones, and Lee (2020)
  Author et al. (Year)                Smith et al. (2020)
  Author et al. (Year)                de la Smith et al. (2020)

Parenthetical (short-reference):
  (Author Year)                       (Smith 2020)
  (Author and Author Year)            (Smith and Jones 2020)
  (Author et al. Year)                (Smith et al. 2020)
  (Author Year; Author Year)          (Smith 2020; Jones 2021)

Name forms supported:
  - Plain surnames: Smith
  - Hyphenated: Montiel-Olea
  - Particles (von, de, van, der, del): von Hippel, de la Smith
  - Accented characters: Abadie, Gonzalez-Navarro, Chetverikov
"""

from __future__ import annotations

import re
from pathlib import Path

# One name token: optional particle(s) then a capitalised word with possible
# hyphens and accented Latin characters.
_NAME = (
    r"(?:(?:von|de|van|der|del|la)\s+)*"   # optional particle(s)
    r"[A-Z][A-Za-zÀ-ž'\-]+"       # capitalised surname
)

# Recognised surname particles (all lowercase).
_PARTICLES: frozenset[str] = frozenset(
    {"von", "van", "de", "der", "del", "di", "la", "le"}
)


def surname_lookup_keys(name_token: str) -> set[str]:
    """Return the set of lowercase lookup keys for a surname token.

    For plain surnames ("Smith") returns {"smith"}.
    For particle surnames ("von Hippel", "de la Cruz") returns both the full
    compound lowercased AND the terminal (non-particle) word lowercased, so
    that a reference stored as "von" and a body citation stored as "Hippel"
    (or vice-versa) can both be matched against the same key set.

    This is the canonical normalization used by both extract_references_from_text
    (in verify_citations.py) and the dangling-citation checker so they agree on
    how to index particle names.
    """
    token = name_token.strip()
    if not token:
        return set()
    words = token.lower().split()
    if len(words) == 1:
        return {words[0]}
    # Separate leading particles from the terminal surname word.
    particle_words = []
    rest = list(words)
    while rest and rest[0] in _PARTICLES:
        particle_words.append(rest.pop(0))
    if not rest:
        # All words were particles (degenerate input) -- return as-is.
        return {token.lower()}
    terminal = rest[-1]
    compound = " ".join(particle_words + rest)
    keys: set[str] = {terminal, compound}
    return keys

# Structural-reference stop-words; a "citation" whose first token is one of
# these is a cross-reference to a part of the paper, not an external source.
_STRUCTURAL_STOPWORDS: frozenset[str] = frozenset({
    "figure", "table", "section", "panel", "model", "column",
    "equation", "appendix", "footnote", "page", "chapter", "note", "row",
})


def _build_patterns() -> list[str]:
    n = _NAME
    return [
        # Narrative: Author (Year) and Author and Author (Year)
        rf"({n}(?:\s+(?:and|&)\s+{n})?(?:\s+et\s+al\.?)?)\s*\((\d{{4}})\)",
        rf"({n}(?:,\s*{n})?(?:,?\s*(?:and|&)\s+{n})?)\s*\((\d{{4}})\)",
        # Parenthetical: (Author Year) and (Author and Author Year)
        rf"\(({n}(?:\s+(?:and|&)\s+{n})?(?:\s+et\s+al\.?)?)\s+(\d{{4}})\)",
        rf"\(({n}(?:,\s*{n})?(?:,?\s*(?:and|&)\s+{n})?)\s+(\d{{4}})\)",
    ]


_PATTERNS: list[re.Pattern] = [re.compile(p) for p in _build_patterns()]

# Three-or-more-author narrative: first author captured, rest consumed.
_THREE_PLUS = re.compile(
    rf"({_NAME})"                                # first author
    r"(?:,\s*[A-Z][A-Za-zÀ-ž'\-]+){2,}"  # 2+ additional comma-sep names
    r"(?:,?\s*(?:and|&)\s+[A-Z][A-Za-zÀ-ž'\-]+)?"  # optional final "and Name"
    r"\s*\((\d{4})\)"                            # year
)

# Semicolon-separated multi-cite block: (Author Year; Author Year; ...)
_SEMICOLON_BLOCK = re.compile(r"\(([A-Z][A-Za-zÀ-ž'\-][^)]*?;[^)]*?)\)")
_ENTRY_IN_BLOCK = re.compile(
    rf"({_NAME}(?:\s+et\s+al\.?)?)\s+(\d{{4}})"
)


def extract_body_citations(review_path: str | Path) -> set[tuple[str, int]]:
    """Extract all in-text citations from the review body (before REFERENCES section).

    Returns a set of (author_string, year_int) tuples.  author_string is the
    raw text that appeared in the citation (e.g. 'Smith', 'Smith and Jones',
    'von Hippel', 'Montiel-Olea and Pflueger').

    This function is the canonical implementation used by both
    verify_citations.py and verify_claim_attribution.py.
    """
    content = Path(review_path).read_text(encoding="utf-8", errors="replace")

    ref_match = re.search(r"^REFERENCES\s*$", content, re.MULTILINE)
    body = content if ref_match is None else content[: ref_match.start()]

    candidates: set[tuple[str, int]] = set()

    # Standard narrative and parenthetical patterns.
    for pattern in _PATTERNS:
        for m in pattern.finditer(body):
            candidates.add((m.group(1).strip(), int(m.group(2))))

    # Three-or-more-author narrative.
    for m in _THREE_PLUS.finditer(body):
        candidates.add((m.group(1).strip(), int(m.group(2))))

    # Semicolon multi-cite blocks: (Smith 2020; Jones 2021; ...)
    for block_m in _SEMICOLON_BLOCK.finditer(body):
        inner = block_m.group(1)
        if ";" not in inner:
            continue
        for entry_m in _ENTRY_IN_BLOCK.finditer(inner):
            candidates.add((entry_m.group(1).strip(), int(entry_m.group(2))))

    # Filter structural cross-references (Figure, Table, Section, ...).
    citations: set[tuple[str, int]] = set()
    for author_part, year in candidates:
        first_token = author_part.split()[0].lower().rstrip(".")
        if first_token not in _STRUCTURAL_STOPWORDS:
            citations.add((author_part, year))

    return citations
