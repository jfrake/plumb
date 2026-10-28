#!/usr/bin/env python3
"""
OCR Garble Detection for Plumb

Scores extracted PDF text for OCR artifacts and encoding corruption.
Detects ligature corruption, broken Unicode, encoding artifacts common
in older scanned PDFs. Outputs a quality report with per-page scores.

Usage:
    python3 garble_score.py <pdf_path> <output_dir>

Output:
    <output_dir>/garble_report.md
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pymupdf


# --- Garble detection patterns ---

# Characters that suggest OCR encoding failures
GARBLE_CHARS = re.compile(
    r"[\ufffd\ufffe\uffff"         # Unicode replacement / noncharacters
    r"\u00ae"                       # registered sign used as ligature artifact
    r"\u00f5\u00c8\u00c0\u00c1"    # Latin chars appearing where they shouldn't
    r"]"
    r"|/C[0-9]{2}"                 # PostScript character codes leaking through
    r"|glyph\[\\w+\]"             # Explicit glyph references
    r"|/lscript"                   # Script font artifacts
)

# Orphaned combining diacriticals (accent marks without base characters)
ORPHAN_DIACRITICALS = re.compile(
    r"(?<![a-zA-Z])[\u0300-\u036f]"  # combining marks not preceded by a letter
)

# Suspicious control characters (excluding normal whitespace)
CONTROL_CHARS = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]"
)

# Sequences of 3+ consecutive non-ASCII non-space chars (often garbled runs)
GARBLE_RUNS = re.compile(
    r"[^\x00-\x7f\s]{3,}"
)


# --- Known ligature corruptions and their fixes ---
# Common in pre-2005 PDFs with non-standard font encodings

LIGATURE_FIXES = [
    # fi ligature corruption (most common)
    ("eect", "effect"),
    ("bene\u00aet", "benefit"),
    ("signi\u00aecant", "significant"),
    ("speci\u00aec", "specific"),
    ("identi\u00aeed", "identified"),
    ("coef\u00aecient", "coefficient"),
    # ff ligature
    ("di\u00aerent", "different"),
    ("e\u00aerent", "efferent"),
    # fl ligature
    ("con\u00afict", "conflict"),
    ("in\u00afuence", "influence"),
    # Registered sign as fi
    ("\u00aeld", "field"),
    ("\u00aend", "find"),
    ("\u00aerst", "first"),
    ("\u00aerm", "firm"),
    ("\u00aenancial", "financial"),
    ("\u00aexed", "fixed"),
    ("\u00aescal", "fiscal"),
    ("\u00ae\u00aece", "office"),
    ("\u00aere", "fire"),
    ("\u00aene", "fine"),
    ("\u00aet", "fit"),
    ("de\u00aene", "define"),
    ("de\u00aened", "defined"),
    ("de\u00aenition", "definition"),
    ("in\u00aenite", "infinite"),
    # PostScript code leakage
    ("/C40", "("),
    ("/C41", ")"),
    # Naive with garbled diacriticals
    ("na\u00f5\u00c8ve", "na\u00efve"),
    ("na\u00f5\u00e8ve", "na\u00efve"),
]

# Social-science specific terms that commonly garble
SOCIAL_SCIENCE_FIXES = [
    # Greek letters in economics/stats
    ("\u00ae", "fi"),              # fi ligature as registered sign
    ("\u00c0", "\u03b1"),          # A-grave → alpha (context-dependent, flagged only)
    # En-dash vs minus confusion
    ("\u2013", "-"),               # en-dash to hyphen in numeric contexts
]


def compute_garble_score(text: str) -> dict:
    """Score a text string for OCR garble artifacts.

    Returns dict with:
        garble_ratio: float 0-1 (fraction of chars that are artifacts)
        quality_score: int 0-100 (100 = clean)
        artifact_count: int
        details: list of (pattern_name, count) tuples
    """
    if not text:
        return {"garble_ratio": 0.0, "quality_score": 100, "artifact_count": 0, "details": []}

    details = []
    total_artifacts = 0

    garble_matches = GARBLE_CHARS.findall(text)
    if garble_matches:
        details.append(("encoding_artifacts", len(garble_matches)))
        total_artifacts += sum(len(m) for m in garble_matches)

    orphan_matches = ORPHAN_DIACRITICALS.findall(text)
    if orphan_matches:
        details.append(("orphan_diacriticals", len(orphan_matches)))
        total_artifacts += len(orphan_matches)

    control_matches = CONTROL_CHARS.findall(text)
    if control_matches:
        details.append(("control_characters", len(control_matches)))
        total_artifacts += len(control_matches)

    garble_runs = GARBLE_RUNS.findall(text)
    # Filter out legitimate non-ASCII (common accented words, CJK, etc.)
    suspicious_runs = [r for r in garble_runs if not _is_legitimate_unicode(r)]
    if suspicious_runs:
        details.append(("suspicious_runs", len(suspicious_runs)))
        total_artifacts += sum(len(r) for r in suspicious_runs)

    text_len = max(len(text), 1)
    garble_ratio = total_artifacts / text_len
    quality_score = max(0, min(100, int((1 - garble_ratio * 50) * 100)))

    return {
        "garble_ratio": garble_ratio,
        "quality_score": quality_score,
        "artifact_count": total_artifacts,
        "details": details,
    }


def _is_legitimate_unicode(run: str) -> bool:
    """Check if a non-ASCII run is legitimate (accented text, etc.) vs garble."""
    # Common accented Latin characters are legitimate
    if all(
        "\u00c0" <= c <= "\u024f"  # Latin Extended
        or "\u1e00" <= c <= "\u1eff"  # Latin Extended Additional
        for c in run
    ):
        return True
    return False


def apply_known_fixes(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Apply known garble-to-correct replacements.

    Returns (fixed_text, list of (garbled, correct) replacements made).
    """
    fixes_applied = []
    result = text

    for garbled, correct in LIGATURE_FIXES + SOCIAL_SCIENCE_FIXES:
        if garbled in result:
            count = result.count(garbled)
            result = result.replace(garbled, correct)
            fixes_applied.append((garbled, f"{correct} (x{count})"))

    return result, fixes_applied


def score_pdf(pdf_path: str) -> dict:
    """Score an entire PDF for garble artifacts.

    Returns dict with global score and per-page breakdown.
    """
    doc = pymupdf.open(pdf_path)
    page_scores = []
    full_text_parts = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        full_text_parts.append(text)

        if not text.strip():
            page_scores.append({
                "page": page_num + 1,
                "quality_score": 100,
                "garble_ratio": 0.0,
                "char_count": 0,
                "note": "empty page",
            })
            continue

        score = compute_garble_score(text)
        page_scores.append({
            "page": page_num + 1,
            "quality_score": score["quality_score"],
            "garble_ratio": score["garble_ratio"],
            "char_count": len(text),
            "artifact_count": score["artifact_count"],
            "details": score["details"],
        })

    doc.close()

    full_text = "\n".join(full_text_parts)
    global_score = compute_garble_score(full_text)
    _, fixes_available = apply_known_fixes(full_text)

    # Flag pages below threshold
    flagged_pages = [p for p in page_scores if p["quality_score"] < 70]

    result = {
        "global_quality_score": global_score["quality_score"],
        "global_garble_ratio": global_score["garble_ratio"],
        "total_artifacts": global_score["artifact_count"],
        "total_chars": len(full_text),
        "total_pages": len(page_scores),
        "flagged_pages": flagged_pages,
        "page_scores": page_scores,
        "fixes_available": fixes_available,
        "details": global_score["details"],
    }
    # Detect image-only / scanned PDFs with essentially no extracted text.
    # Computed after building the result dict so _is_empty_text can be reused.
    result["empty_text"] = _is_empty_text(result)
    return result


# Minimum total characters to consider a PDF as having extractable text.
# Below this threshold the PDF is likely image-only or scanned without OCR.
EMPTY_TEXT_CHAR_THRESHOLD = 50


def _is_empty_text(scores: dict) -> bool:
    """Return True when the extracted text is so sparse that quality scores are meaningless."""
    # Honour an explicit flag if the caller set it (e.g. score_pdf sets it; tests may inject it)
    if scores.get("empty_text"):
        return True
    total_chars = scores.get("total_chars", 0)
    total_pages = max(scores.get("total_pages", 1), 1)
    chars_per_page = total_chars / total_pages
    # Fewer than threshold chars overall, or fewer than 10 chars/page on average
    return total_chars < EMPTY_TEXT_CHAR_THRESHOLD or chars_per_page < 10


def generate_report(scores: dict) -> str:
    """Generate markdown report from score dict."""
    lines = []
    lines.append("# OCR Quality Report\n")

    qs = scores["global_quality_score"]

    # Empty-text check takes priority: a high quality_score is meaningless when
    # there is virtually no text to score.
    if _is_empty_text(scores):
        status = "DEGRADED_EMPTY_TEXT"
    else:
        status = "CLEAN" if qs >= 85 else "WARNING" if qs >= 70 else "DEGRADED"

    lines.append(f"**Overall Quality Score:** {qs}/100 ({status})")
    lines.append(f"**Total Characters:** {scores['total_chars']:,}")
    lines.append(f"**Total Artifacts:** {scores['total_artifacts']:,}")
    lines.append(f"**Garble Ratio:** {scores['global_garble_ratio']:.4f}")
    lines.append(f"**Pages Scanned:** {scores['total_pages']}")
    lines.append("")

    if status == "DEGRADED_EMPTY_TEXT":
        lines.append("> **WARNING:** PDF text extraction yielded no usable text (likely a")
        lines.append("> scanned or image-only PDF without an OCR layer). Downstream agents")
        lines.append("> must use visual PDF reading exclusively. Do NOT use extracted text.")
        lines.append("> Numbers and quotes must be sourced directly from the PDF images.")
        lines.append("")
    elif status == "DEGRADED":
        lines.append("> **WARNING:** PDF text extraction quality is low. Downstream agents")
        lines.append("> should rely on visual PDF reading over extracted text for verification.")
        lines.append("> Numbers extracted from text should be tagged as [ESTIMATED] unless")
        lines.append("> visually confirmed from the PDF.")
        lines.append("")

    # Artifact breakdown
    if scores["details"]:
        lines.append("## Artifact Breakdown\n")
        lines.append("| Type | Count |")
        lines.append("|------|-------|")
        for pattern_name, count in scores["details"]:
            lines.append(f"| {pattern_name} | {count} |")
        lines.append("")

    # Flagged pages
    if scores["flagged_pages"]:
        lines.append("## Flagged Pages (quality < 70)\n")
        lines.append("| Page | Quality | Artifacts | Details |")
        lines.append("|------|---------|-----------|---------|")
        for p in scores["flagged_pages"]:
            details_str = ", ".join(f"{d[0]}:{d[1]}" for d in p.get("details", []))
            lines.append(f"| {p['page']} | {p['quality_score']}/100 | {p.get('artifact_count', 0)} | {details_str} |")
        lines.append("")

    # Available fixes
    if scores["fixes_available"]:
        lines.append("## Known Fixes Available\n")
        lines.append("The following known OCR corruptions were detected and can be auto-corrected:\n")
        for garbled, correct in scores["fixes_available"]:
            lines.append(f"- `{repr(garbled)}` -> {correct}")
        lines.append("")

    return "\n".join(lines)


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 garble_score.py <pdf_path> <output_dir>", file=sys.stderr)
        sys.exit(1)

    pdf_path = sys.argv[1]
    output_dir = Path(sys.argv[2])
    output_dir.mkdir(parents=True, exist_ok=True)

    if not Path(pdf_path).exists():
        print(f"Error: PDF not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    scores = score_pdf(pdf_path)
    report = generate_report(scores)

    report_path = output_dir / "garble_report.md"
    report_path.write_text(report, encoding="utf-8")

    # Print summary to stdout for orchestrator
    qs = scores["global_quality_score"]
    if scores.get("empty_text"):
        status = "DEGRADED_EMPTY_TEXT"
    else:
        status = "CLEAN" if qs >= 85 else "WARNING" if qs >= 70 else "DEGRADED"
    print(f"Garble score: {qs}/100 ({status})")
    if scores["flagged_pages"]:
        print(f"Flagged pages: {', '.join(str(p['page']) for p in scores['flagged_pages'])}")

    # Exit code signals quality level; empty-text is treated as DEGRADED (exit 2)
    if status == "DEGRADED_EMPTY_TEXT" or qs < 70:
        sys.exit(2)  # DEGRADED / DEGRADED_EMPTY_TEXT
    elif qs < 85:
        sys.exit(1)  # WARNING
    else:
        sys.exit(0)  # CLEAN


if __name__ == "__main__":
    main()
