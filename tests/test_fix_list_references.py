"""Fix lists with a REFERENCES section. Offline only."""
from __future__ import annotations
import importlib
import sys
from pathlib import Path

from plumb import outputs

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "skills/review/scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
vc = importlib.import_module("verify_citations")

FIX_WITH_REFS = """## Issues

### 1. The instrument may violate the exclusion restriction

Severity: Undermines the main claim
Fix: new analysis

The instrument could affect the outcome through a second channel (p. 12). Report the weak-instrument test from Stock and Yogo (2005) and bound the estimate.

## Minor issues

- Table 2 omits the sample size (p. 9).

## What I left out

Nothing beyond the minor list.

REFERENCES

Stock, J. H., and Yogo, M. (2005). Testing for weak instruments in linear IV regression. In Identification and Inference for Econometric Models, pages 80-108.
"""


def test_fix_list_with_references_passes_validator():
    assert outputs.validate_fix_list(FIX_WITH_REFS) == []


def test_reference_extraction_finds_fix_list_entries(tmp_path):
    draft = tmp_path / "draft.md"
    draft.write_text(FIX_WITH_REFS, encoding="utf-8")
    refs = vc.extract_references_from_text(draft)
    assert len(refs) == 1
    assert refs[0]["year"] == 2005
    assert "Stock" in refs[0]["authors_raw"]
