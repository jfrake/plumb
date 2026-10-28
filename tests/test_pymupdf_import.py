"""PyMuPDF 1.28 prints a deprecation warning to stdout on `import fitz`, which corrupts the JSON the
scripts print (issue #1). Every file imports `pymupdf`, which exists from 1.24.3."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FITZ_IMPORT = re.compile(r"^\s*(import fitz\b|from fitz\b)", re.M)


def test_no_file_imports_fitz():
    offenders = [str(p.relative_to(ROOT)) for d in ("plumb", "skills", "packs", "tests")
                 for p in (ROOT / d).rglob("*.py") if FITZ_IMPORT.search(p.read_text(encoding="utf-8"))]
    assert offenders == []


def test_requirements_floor_has_the_pymupdf_module():
    line = next(l for l in (ROOT / "requirements.txt").read_text().splitlines() if l.startswith("pymupdf"))
    floor = tuple(int(x) for x in line.split(">=")[1].split("."))
    assert floor >= (1, 24, 3)
