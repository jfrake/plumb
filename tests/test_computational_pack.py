from __future__ import annotations
import datetime as dt
import re
from pathlib import Path

import yaml

from plumb import packs

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "packs" / "computational"
IDS = [f"C{i}" for i in range(1, 15)]


def test_computational_pack_loads_as_an_overlay():
    p = packs.load_pack(PACK)
    assert p.name == "computational" and p.overlay is True
    assert [i["id"] for i in p.checklist] == IDS
    assert {i["adjudication"] for i in p.checklist} <= packs.ADJUDICATION


def test_checklist_adjudication_matches_the_spec():
    tags = {i["id"]: i["adjudication"] for i in packs.load_pack(PACK).checklist}
    assert tags["C5"] == "external"
    assert {k for k, v in tags.items() if v == "judgment"} == {"C8", "C9", "C13"}


def test_severity_rules_carry_the_either_counts_rule():
    rules = " ".join(packs.load_pack(PACK).severity_rules)
    assert "main treatment or main outcome" in rules
    assert "Undermines the main claim" in rules and "Weakens a claim" in rules
    assert "C1" in rules and "C2" in rules and "C4" in rules


DATE = re.compile(r"^\d{4}-\d{2}(-\d{2})?$")
KEYS = {"provider", "family", "version", "aliases", "release_date", "training_cutoff",
        "deprecated", "url", "quote", "checked_on"}


def test_model_cutoffs_rows_are_complete_and_dated():
    rows = yaml.safe_load((PACK / "data" / "model_cutoffs.yaml").read_text(encoding="utf-8"))
    assert isinstance(rows, list) and len(rows) >= 8
    today = dt.date.today()
    for r in rows:
        assert set(r) == KEYS, r
        assert r["url"].startswith("https://") and r["quote"].strip()
        assert isinstance(r["aliases"], list) and r["aliases"]
        for k in ("release_date", "training_cutoff", "deprecated"):
            assert r[k] is None or DATE.match(str(r[k])), (r["family"], k)
        checked = dt.date.fromisoformat(str(r["checked_on"]))
        assert checked <= today
    assert any(r["training_cutoff"] for r in rows)


def test_fixture_is_labeled_synthetic():
    exp = yaml.safe_load((PACK / "fixtures" / "planted-1" / "expected.yaml").read_text(encoding="utf-8"))
    assert exp["synthetic"] is True and exp["owner"] == "blind-agent"
    assert exp["status"] in ("pending_planting", "ready")
    for item in exp.get("must_catch", []) + exp.get("must_not_flag", []):
        assert item["check"] in IDS


def test_llama_3_sizes_have_their_own_cutoffs():
    rows = yaml.safe_load((PACK / "data" / "model_cutoffs.yaml").read_text(encoding="utf-8"))
    llama3 = {r["version"]: r["training_cutoff"] for r in rows if r["family"].lower().startswith("llama") and str(r["version"]).startswith("3 ")}
    assert llama3.get("3 8B") == "2023-03" and llama3.get("3 70B") == "2023-12"


def _agent(name):
    return (PACK / "agents" / name).read_text(encoding="utf-8")


def test_measurement_numbers_agent():
    p = packs.load_pack(PACK)
    assert p.slots.get("verify") == ["measurement-numbers.md"]
    text = _agent("measurement-numbers.md")
    assert "stage-1/computational_numbers.md" in text and "## Flags" in text
    assert "C1" in text and "base rate" in text and "Quick" in text
    assert "shared/contracts.md" in text


def test_measurement_numbers_f1_identity_is_limited_to_single_class_or_micro():
    text = _agent("measurement-numbers.md")
    assert "micro-averaged" in text and "Do not apply this identity to macro-averaged" in text
    assert "only after searching" in text and "Do not flag a statistic you could not locate" not in text


def test_model_provenance_agent():
    p = packs.load_pack(PACK)
    assert p.slots.get("context") == ["model-provenance.md"]
    text = _agent("model-provenance.md")
    assert "stage-2/model_provenance.md" in text and "data/model_cutoffs.yaml" in text
    for c in ("C3", "C5", "C8"):
        assert c in text
    assert "research-protocol.md" in text


def test_provenance_agent_refetches_missing_or_stale_rows():
    text = _agent("model-provenance.md")
    assert "180 days" in text and "not in the table" in text and "verbatim" in text


def test_provenance_agent_has_its_own_budget_and_fetches_disclosure_rules():
    text = _agent("model-provenance.md")
    assert "about 15 searches at Standard depth, 25-35 at Deep" in text
    assert "never report them as disclosure rules" in text and "WEB-fetch the journal's author guidelines" in text
    assert "not stated by provider" in text and "Cite one in your output only if you fetched it" in text


def test_measurement_validity_agent():
    p = packs.load_pack(PACK)
    assert "measurement-validity.md" in p.slots.get("diagnose", [])
    text = _agent("measurement-validity.md")
    assert "stage-4/measurement_validity.md" in text
    for c in ("C1", "C7", "C8", "C9", "C14"):
        assert f"### {c}" in text, c
    assert "stage-2/model_provenance.md" in text and "stage-1/computational_numbers.md" in text


def test_measurement_validity_cites_only_fetched_works():
    text = _agent("measurement-validity.md")
    assert "Cite one in your output only if you fetched it" in text and "PDF_PATH" in text


def test_measurement_validity_leaves_the_joint_rule_to_the_compiler():
    text = _agent("measurement-validity.md")
    assert "## Joint rule" in text and "C1 <met | not met>" in text
    assert "Excerpt:" in text and "Page:" in text
    assert "Severity: <Weakens a claim | Minor>" in text


AGENTS = ["measurement-numbers.md", "model-provenance.md", "measurement-validity.md",
          "generated-variable-inference.md"]


def test_generated_variable_inference_agent():
    p = packs.load_pack(PACK)
    assert p.slots.get("diagnose") == ["measurement-validity.md", "generated-variable-inference.md"]
    text = _agent("generated-variable-inference.md")
    assert "stage-4/generated_variable_inference.md" in text
    for c in ("C2", "C3", "C4", "C6", "C10", "C11", "C12", "C13"):
        assert f"### {c}" in text, c
    assert "either" in text.lower() and "both are missing" in text


def test_every_check_is_owned_by_an_agent():
    owned = set()
    for a in AGENTS:
        owned |= set(re.findall(r"\bC(?:1[0-4]|[1-9])\b", _agent(a)))
    assert owned == set(IDS)


def test_every_computational_agent_handles_a_missing_variable_list():
    for a in AGENTS:
        text = _agent(a)
        assert "If the list says \"none\" or is missing" in text or "If it says \"none\" or is missing" in text, a
        assert "Reply to the orchestrator in one sentence" in text, a


def test_both_diagnose_agents_write_matching_joint_rule_sections():
    mv = _agent("measurement-validity.md"); gv = _agent("generated-variable-inference.md")
    assert "## Joint rule" in mv and "## Joint rule" in gv
    assert "C1 <met | not met>" in mv and "C2 or C4 <met | not met>" in gv
    assert "Severity: <Weakens a claim | Minor>" in gv and "Excerpt:" in gv and "Page:" in gv


def test_diagnose_agents_skip_dropped_computational_flags():
    for a in ("measurement-validity.md", "generated-variable-inference.md"):
        text = _agent(a)
        assert "{WORKSPACE}/stage-1/dropped_flags.md" in text, a
        assert "Skip any `numbers:pack:computational:<n>` flag listed there" in text, a
        assert "position under `## Flags` in `computational_numbers.md`" in text, a


def test_published_measure_used_unchanged_meets_c1():
    mv = _agent("measurement-validity.md")
    assert ("C1 is met when `model_provenance.md` records a published validation on a comparable population "
            "and the paper uses the measure unchanged") in mv
    assert "Minor issue recommending a check on the paper's own data" in mv
    assert "counts as met on the `Joint rule` line" in mv
    item4 = _agent("measurement-numbers.md").split("4. **Missing basics.**", 1)[1].split("\n5. ", 1)[0]
    assert "published measure used unchanged" in item4 and "under `## Not found` instead" in item4


def test_measurement_numbers_reweights_balanced_samples_and_respects_rounding():
    text = _agent("measurement-numbers.md")
    item1 = text.split("1. **Accuracy against the base rate.**", 1)[1].split("\n2. ", 1)[0]
    assert "reweight" in item1 and "analysis-sample share" in item1
    assert "under `## Not found` and do not flag" in item1
    item2 = text.split("2. **Metrics that do not cohere.**", 1)[1].split("\n3. ", 1)[0]
    assert "exceeds what rounding of the printed P, R, and F1 allows" in item2
    assert "gap larger than 0.01" not in item2
    assert "Cite one in your output only if you fetched it in this run" in text


def test_either_counts_rule_writes_one_joint_issue_and_counts_weak_as_met():
    gv = _agent("generated-variable-inference.md")
    rule = gv.split("**The either-counts rule.**", 1)[1].split("\n\n", 1)[0]
    assert "`Check: C2, C4`" in rule
    assert "present but weak still counts as met on the `Joint rule` line" in rule
    assert "When C4 is present, a magnitude claim without a corrected or bounded estimate is at most a Minor note" in rule


def test_joint_rule_lines_use_the_fingerprint_name():
    for a in ("measurement-validity.md", "generated-variable-inference.md"):
        text = _agent(a)
        assert "exactly as the fingerprint's `Generated variables:` list names it" in text, a
        assert "the paper's own label" in text, a
