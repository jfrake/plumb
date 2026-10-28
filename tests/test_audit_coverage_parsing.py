# tests/test_audit_coverage_parsing.py
"""
TDD tests for audit_coverage robustness gaps.

(a) Escaped-pipe parsing: a coverage row with '\|' inside a cell must split
    into the correct number of cells and preserve the literal '|' in that cell.
(b) Serious-finding detection: 'Fatal', 'severity: serious', 'severity=serious'
    (and lowercase) must all be detected; 'seriously' in unrelated prose must not.

Fail-first: written before the implementation is in place.
"""
from __future__ import annotations

import sys
import pathlib

SD = pathlib.Path(__file__).resolve().parents[1] / "skills/review/scripts"
sys.path.insert(0, str(SD))
import importlib
ac = importlib.import_module("audit_coverage")


# ---------------------------------------------------------------------------
# Escaped-pipe parsing
# ---------------------------------------------------------------------------

class TestEscapedPipeParsing:
    """extract_coverage_entries must handle '\|' inside cells."""

    def _basic_header(self):
        return (
            "| finding_id | source_file | severity | disposition | target | rationale |\n"
            "|---|---|---|---|---|---|\n"
        )

    def test_escaped_pipe_in_excerpt_gives_correct_cell_count(self):
        """A row with '\|' in the rationale cell must produce 6 cells, not 7+."""
        md = (
            self._basic_header()
            + r"| F01 | methods_checks.md | Serious | INCLUDED_MAJOR | s2 | see p.5 for n\|a details |"
            + "\n"
        )
        entries = ac.extract_coverage_entries(md)
        assert len(entries) == 1, f"Expected 1 entry, got {len(entries)}"

    def test_escaped_pipe_preserved_as_literal_pipe(self):
        r"""After parsing, '\|' in a cell should become '|'."""
        md = (
            self._basic_header()
            + r"| F01 | methods_checks.md | Serious | INCLUDED_MAJOR | s2 | see n\|a here |"
            + "\n"
        )
        entries = ac.extract_coverage_entries(md)
        assert len(entries) == 1
        # The rationale cell should contain a literal pipe, not a backslash-pipe
        assert "|" in entries[0]["rationale"], (
            f"Expected literal '|' in rationale, got: {entries[0]['rationale']!r}"
        )
        assert r"\|" not in entries[0]["rationale"], (
            f"Expected backslash-pipe to be unescaped, got: {entries[0]['rationale']!r}"
        )

    def test_escaped_pipe_in_finding_id_cell(self):
        r"""'\|' in the finding_id cell is unusual but must not explode."""
        md = (
            self._basic_header()
            + r"| F0\|1 | methods_checks.md | Serious | INCLUDED_MAJOR | s2 | rationale |"
            + "\n"
        )
        entries = ac.extract_coverage_entries(md)
        # We get exactly one entry even though the id cell contains an escaped pipe
        assert len(entries) == 1

    def test_normal_row_still_parses_correctly(self):
        """Regular rows without escaped pipes continue to work."""
        md = (
            self._basic_header()
            + "| F01 | methods_checks.md | Serious | INCLUDED_MAJOR | s2 | normal rationale |\n"
        )
        entries = ac.extract_coverage_entries(md)
        assert len(entries) == 1
        assert entries[0]["finding_id"] == "F01"
        assert entries[0]["rationale"] == "normal rationale"

    def test_multiple_escaped_pipes_in_single_cell(self):
        r"""Multiple '\|' in one cell should all be unescaped."""
        md = (
            self._basic_header()
            + r"| F01 | methods_checks.md | Serious | INCLUDED_MAJOR | s2 | a\|b\|c |"
            + "\n"
        )
        entries = ac.extract_coverage_entries(md)
        assert len(entries) == 1
        rationale = entries[0]["rationale"]
        assert "a|b|c" in rationale, f"Expected 'a|b|c' in rationale, got: {rationale!r}"


# ---------------------------------------------------------------------------
# Serious-finding detection broadening
# ---------------------------------------------------------------------------

class TestSeriousFindingDetection:
    """find_serious_findings (via SERIOUS_PATTERNS) must recognize broader forms."""

    def _make_workspace(self, tmp_path, fname, content):
        """Write content to stage-4/fname under tmp_path and return tmp_path as a Path."""
        (tmp_path / "stage-4").mkdir(exist_ok=True)
        (tmp_path / "stage-4" / fname).write_text(content)
        return tmp_path

    def test_detects_fatal_keyword(self, tmp_path):
        """A line containing 'Fatal' is treated as a serious finding."""
        content = "## Finding\n**Fatal**: The identification strategy is invalid.\n"
        ws = self._make_workspace(tmp_path, "methods_checks.md", content)
        findings = ac.find_serious_findings(ws)
        assert len(findings) >= 1, (
            "Expected at least one finding for 'Fatal' keyword"
        )

    def test_detects_severity_colon_serious(self, tmp_path):
        """'severity: serious' (unformatted, lowercase) is detected."""
        content = "Finding F01\nseverity: serious\nThis invalidates the IV.\n"
        ws = self._make_workspace(tmp_path, "methods_checks.md", content)
        findings = ac.find_serious_findings(ws)
        assert len(findings) >= 1, (
            "Expected finding for 'severity: serious'"
        )

    def test_detects_severity_equals_serious(self, tmp_path):
        """'severity=serious' (key=value form) is detected."""
        content = "finding_id: F02\nseverity=serious\nrationale: fatal flaw\n"
        ws = self._make_workspace(tmp_path, "methods_checks.md", content)
        findings = ac.find_serious_findings(ws)
        assert len(findings) >= 1, (
            "Expected finding for 'severity=serious'"
        )

    def test_detects_severity_serious_case_insensitive(self, tmp_path):
        """'SEVERITY: SERIOUS' (all-caps) is also detected."""
        content = "finding_id: F03\nSEVERITY: SERIOUS\nrationale: confounding\n"
        ws = self._make_workspace(tmp_path, "methods_checks.md", content)
        findings = ac.find_serious_findings(ws)
        assert len(findings) >= 1

    def test_no_false_positive_on_seriously_in_prose(self, tmp_path):
        """'seriously' as an adverb in unrelated prose must NOT be detected."""
        content = (
            "This paper takes the threat of endogeneity seriously, "
            "but the authors address it adequately.\n"
        )
        ws = self._make_workspace(tmp_path, "methods_checks.md", content)
        findings = ac.find_serious_findings(ws)
        assert len(findings) == 0, (
            f"False positive on 'seriously' in prose: {findings}"
        )

    def test_no_false_positive_on_fatal_in_unrelated_context(self, tmp_path):
        """'fatal' as part of a word like 'fatalistic' must not trigger."""
        content = "The fatalistic view of selection bias is unwarranted here.\n"
        ws = self._make_workspace(tmp_path, "methods_checks.md", content)
        findings = ac.find_serious_findings(ws)
        assert len(findings) == 0, (
            f"False positive on 'fatalistic': {findings}"
        )

    def test_existing_serious_pattern_still_detected(self, tmp_path):
        """The original '**Severity:** Serious' markdown form still works."""
        content = "## Finding F01\n**Severity:** Serious\nThe instrument is weak.\n"
        ws = self._make_workspace(tmp_path, "methods_checks.md", content)
        findings = ac.find_serious_findings(ws)
        assert len(findings) >= 1

    def test_existing_high_severity_still_detected(self, tmp_path):
        """'**Severity:** High' (existing pattern) still works."""
        content = "## Finding F02\n**Severity:** High\nMissing placebo test.\n"
        ws = self._make_workspace(tmp_path, "methods_checks.md", content)
        findings = ac.find_serious_findings(ws)
        assert len(findings) >= 1
