from __future__ import annotations
import re
from pathlib import Path

import yaml

from plumb import packs

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "packs" / "nonlinear"
IDS = [f"N{i}" for i in range(1, 14)]
JUDGMENT = {"N2", "N7", "N12"}
CHECKLIST = {
    "N1": "A U-shaped or inverted-U claim is tested in the range of the data: the turning point implied by the reported coefficients lies inside the observed range of the variable, on the scale the model uses; the slopes at the low and high ends of that range have opposite signs and each is distinguishable from zero (or an equivalent test such as two lines or the Lind and Mehlum test is reported); the turning point is reported with an interval (a Fieller interval when the squared term is imprecise); and the text claims no rise, fall, or interior optimum that the reported slopes and range do not show",
    "N2": "A moderated curve is specified and shown for what the hypothesis claims (a shifted turning point, a flatter or steeper curve, or both), with curves plotted at low and high moderator values inside the moderator's range, and a change of shape across that range is checked",
    "N3": "A product term in a linear model comes with all its constitutive terms, and each lower-order coefficient is read as the effect where the other variable equals zero, a value that lies inside that variable's observed range. A lower-order term absorbed by the model's fixed effects counts as included",
    "N4": "Moderation is shown as the conditional effect across the moderator with intervals, not only as the product-term coefficient, and the moderator values plotted or tested (such as the mean plus or minus one standard deviation, or a Johnson-Neyman region) lie inside the moderator's observed range where the data have observations",
    "N5": "Mean-centering is not presented as a remedy for multicollinearity, and multicollinearity is not used to explain away a weak interaction",
    "N6": "A claim that an effect differs across groups, periods, or subsamples rests on a test of the difference (a pooled interaction or a test of equal coefficients), not on one estimate being significant and the other not",
    "N7": "When a squared term sits in a model with unit fixed effects, the curve is read as within-unit, and no unit-level optimum is drawn from the pooled range of levels",
    "N8": "In a logit, probit, count, or hazard model, an interaction or squared term is judged on the scale the hypothesis names (probability, count, rate, hazard, or survival): the paper states the scale and reports second differences, cross-partial effects, or predicted outcomes across the moderator with intervals, and does not rest the claim on the sign and significance of the coefficient alone",
    "N9": "Odds ratios, incidence rate ratios, and hazard ratios are described correctly (an odds ratio is not a ratio of probabilities), and logit or probit coefficients are not compared across models or groups as if they shared a scale",
    "N10": "When an outcome with many zeros enters as log(1+y), log(y+c), or the inverse hyperbolic sine, the share of zeros is reported, the coefficient is not read as a percentage change or elasticity without support, and the result is shown robust to the units of y or replaced by an estimate with a clear scale (Poisson or PPML, a two-part model, or separate extensive and intensive margins)",
    "N11": "A three-way interaction includes all lower-order two-way and main-effect terms, and the pattern the hypothesis states is tested with simple slopes and tests of slope differences at stated moderator values, not only by the sign of the triple product. A lower-order term absorbed by the model's fixed effects counts as included",
    "N12": "The functional form a nonlinear claim rests on is checked with a flexible alternative (bins, splines, two lines, or a binning or kernel interaction estimator); an interaction between correlated variables is checked against the squared terms of each, and a curve against the interaction",
    "N13": "The size of each nonlinear effect the paper claims is stated in the outcome's units over a meaningful change in the variable, at stated moderator values, with its uncertainty",
}
SEVERITIES = ("Undermines the main claim", "Weakens a claim", "Minor")

def _expected():
    return yaml.safe_load((PACK / "fixtures" / "planted-1" / "expected.yaml").read_text(encoding="utf-8"))


def test_nonlinear_pack_loads_as_an_overlay():
    p = packs.load_pack(PACK)
    assert p.name == "nonlinear" and p.overlay is True
    assert "context" not in p.slots
    assert [i["id"] for i in p.checklist] == IDS


def test_checklist_matches_the_spec():
    items = {i["id"]: i for i in packs.load_pack(PACK).checklist}
    for k in IDS:
        assert items[k]["text"] == CHECKLIST[k], k
        assert items[k]["adjudication"] == ("judgment" if k in JUDGMENT else "paper"), k


def test_severity_rules():
    rules = packs.load_pack(PACK).severity_rules
    assert len(rules) == 6
    assert "main hypothesis" in rules[0] and "'Undermines the main claim'" in rules[0]
    assert "point estimates" in rules[0] and "curvature that changes sign" in rules[0]
    assert "'Weakens a claim'" in rules[1] and "under every covariance" in rules[1]
    assert "capped at 'Weakens a claim'" in rules[2]
    assert rules[3].startswith("N5") and "'Minor'" in rules[3]
    assert "once per check, listing every term" in rules[4]
    assert rules[5].startswith("N9") and "'Minor'" in rules[5]


def test_fixture_is_labeled_synthetic():
    exp = _expected()
    assert exp["synthetic"] is True and exp["owner"] == "blind-agent"
    assert exp["label"] == "SYNTHETIC TEST PAPER, NOT REAL RESEARCH"
    assert exp["status"] in ("pending_planting", "ready")
    for key in ("must_catch", "must_not_flag", "also_fair"):
        for item in exp.get(key) or []:
            assert {"check", "page", "locator", "note"} <= set(item), item
            assert item["check"] in IDS, item
    for item in exp.get("must_catch") or []:
        assert item.get("severity") in SEVERITIES, item
    plants = {(i["check"], str(i["page"]), i["locator"]) for i in exp.get("must_catch") or []}
    for d in exp.get("must_not_flag") or []:
        assert (d["check"], str(d["page"]), d["locator"]) not in plants, d


def _agent(name):
    return (PACK / "agents" / name).read_text(encoding="utf-8")


def test_numbers_agent():
    assert packs.load_pack(PACK).slots.get("verify") == ["nonlinear-numbers.md"]
    text = _agent("nonlinear-numbers.md")
    for s in ("stage-1/nonlinear_numbers.md", "## Terms checked", "## Flags", "## Not computed", "Quick",
              "Record: <id>. Table: <label>. Cells: <table:row:col, ...>."):
        assert s in text, s
    for kind in ("quadratic", "moderated_quadratic", "linear_interaction", "plotted_points", "difference", "odds_ratio"):
        assert f"`{kind}`" in text, kind
    assert "Flag nothing as missing" in text


def test_numbers_agent_converts_the_range_to_the_model_scale():
    text = _agent("nonlinear-numbers.md")
    assert "Put every range on the scale the model uses." in text and "`scale_note`" in text
    assert "converted values as strings" in text


def test_numbers_agent_runs_the_script_with_its_own_tools():
    text = _agent("nonlinear-numbers.md")
    assert "tools: [Read, Write, Bash, Glob]" in text.split("---", 2)[1]
    assert "The orchestrator will provide `PDF_PATH`, `PAGE_COUNT`, `{WORKSPACE}`, and `{PLUGIN}`." in text
    assert ("`python3 {PLUGIN}/packs/nonlinear/scripts/nonlinear_arith.py "
            "{WORKSPACE}/stage-1/nonlinear_inputs.json {WORKSPACE}/stage-1/nonlinear_arith.json`") in text
    assert "with the file-writing tool" in text
    assert not re.search(r"(cat|echo|printf|tee)[^\n`]*>", text)
    assert (PACK / "scripts" / "nonlinear_arith.py").exists()


def test_numbers_agent_passes_printed_values_and_separates_rounding_sensitive_results():
    text = _agent("nonlinear-numbers.md")
    for s in ("exactly as the paper prints it", "fraction", "## Rounding-sensitive"):
        assert s in text, s


def test_numbers_agent_handles_every_status_and_cleans_printed_strings():
    text = _agent("nonlinear-numbers.md")
    for s in ("not_computable", "ASCII minus", "blank in `extracted_tables/`", "Table: <label>. Cells:"):
        assert s in text, s
    stage = Path(__file__).resolve().parents[1] / "skills" / "review" / "stages" / "stage-1-verify.md"
    keys = stage.read_text(encoding="utf-8")
    assert "`Table:` and `Cells:`" in keys


def test_claims_agent():
    p = packs.load_pack(PACK)
    assert p.slots.get("diagnose", [])[:1] == ["nonlinear-claims.md"]
    text = _agent("nonlinear-claims.md")
    assert "stage-4/nonlinear_claims.md" in text
    for c in ("N1", "N3", "N4", "N5", "N6", "N8", "N9", "N10", "N11", "N13"):
        assert re.search(rf"^### {c}\. ", text, re.M), c
    for s in ("Excerpt:", "Page:", "Term: <term> (<kind>, <role>)", "## Checked and fine",
              "Severity: <Undermines the main claim | Weakens a claim | Minor>"):
        assert s in text, s
    for rule in p.severity_rules:
        assert rule in text


def test_claims_agent_counts_absorbed_terms_as_included():
    text = _agent("nonlinear-claims.md")
    assert text.count("A lower-order term absorbed by the model's fixed effects counts as included; say which fixed effect absorbs it.") == 2


def test_claims_agent_skips_dropped_flags_and_their_records():
    text = _agent("nonlinear-claims.md")
    assert "{WORKSPACE}/stage-1/dropped_flags.md" in text
    assert "any result in `nonlinear_arith.json` whose `id` matches that flag's `Record:`" in text
    assert "If the file is missing, no flag was dropped." in text


def test_claims_agent_writes_missing_evidence_once():
    text = _agent("nonlinear-claims.md")
    assert "Write a finding that only notes missing evidence once per check, listing every term it applies to." in text
    assert ("Flag an absence only after searching the methods section, the appendices, the footnotes, "
            "and every table, and name where you looked.") in text


def test_claims_agent_leaves_owned_topics_to_other_packs():
    text = _agent("nonlinear-claims.md")
    for s in ("triple difference", "defense against an alternative explanation", "When `meta-analysis` is in `run.json` `packs`",
              "belongs to the DiD module", "This check covers outcomes only.", "inference or experiments pack"):
        assert s in text, s


def test_claims_agent_reads_numbers_sections_and_dropped_flags():
    text = _agent("nonlinear-claims.md")
    for s in ("## Terms checked", "## Flags", "## Rounding-sensitive", "stage-1/dropped_flags.md"):
        assert s in text, s
    assert "never raise it as an issue on arithmetic grounds alone" in text


def test_claims_agent_separates_monotone_claims_from_reversals():
    text = _agent("nonlinear-claims.md")
    assert ("If the paper claims only diminishing or increasing returns (no reversal and no optimum), a turning point "
            "outside the observed range is consistent with the claim; check only that the slope at the far end of the "
            "range has the claimed sign and is distinguishable from zero.") in text
    assert "Severity rule 1 does not apply to that case" in text


def test_claims_agent_applies_rounding_per_reason():
    text = _agent("nonlinear-claims.md")
    assert ("A `_rounding_sensitive` reason is not a flag. A record that is also listed under `## Flags` keeps that "
            "flag for its other reasons.") in text


def test_specification_agent():
    p = packs.load_pack(PACK)
    assert p.slots.get("diagnose") == ["nonlinear-claims.md", "nonlinear-specification.md"]
    text = _agent("nonlinear-specification.md")
    assert "stage-4/nonlinear_specification.md" in text and "stage-2/construction_ledger.json" in text
    for c in ("N2", "N7", "N12"):
        assert re.search(rf"^### {c}\. ", text, re.M), c
    assert "variation audit" in text
    for rule in p.severity_rules:
        assert rule in text


def test_specification_agent_skips_dropped_flags():
    text = _agent("nonlinear-specification.md")
    assert "{WORKSPACE}/stage-1/dropped_flags.md" in text
    assert "any result in `nonlinear_arith.json` whose `id` matches that flag's `Record:`" in text
    assert "If the file is missing, no flag was dropped." in text


def test_specification_agent_reads_numbers_sections_and_rounding():
    text = _agent("nonlinear-specification.md")
    for s in ("## Terms checked", "## Flags", "## Rounding-sensitive"):
        assert s in text, s
    assert ("A `_rounding_sensitive` reason is not a flag. A record that is also listed under `## Flags` keeps that "
            "flag for its other reasons.") in text
    assert "never raise it as an issue on arithmetic grounds alone" in text


def test_specification_agent_uses_the_shared_issue_template():
    text = _agent("nonlinear-specification.md")
    claims = _agent("nonlinear-claims.md")
    def tmpl(t):
        return t.split("```markdown", 1)[1].split("```", 1)[0]
    assert tmpl(text).split("## Issues", 1)[1] == tmpl(claims).split("## Issues", 1)[1]
    assert 'each as "<name> (<kind>, <role>)"' in text


def test_specification_agent_names_the_owner_of_overlapping_topics():
    text = _agent("nonlinear-specification.md")
    assert "nonlinear claims agent" in text
    assert "archival pack's variation audit" in text


def test_every_check_is_owned_by_one_diagnose_agent():
    owners = {}
    for a in ("nonlinear-claims.md", "nonlinear-specification.md"):
        for c in re.findall(r"^### (N\d+)\. ", _agent(a), re.M):
            assert c not in owners, c
            owners[c] = a
    assert sorted(owners, key=lambda c: int(c[1:])) == IDS


AGENTS = ("nonlinear-numbers.md", "nonlinear-claims.md", "nonlinear-specification.md")


def test_every_nonlinear_agent_follows_the_authoring_rules():
    for a in AGENTS:
        text = _agent(a)
        head = text.split("---", 2)[1]
        for k in ("name:", "description:", "maxTurns:"):
            assert k in head, (a, k)
        assert "The contracts in `skills/review/shared/contracts.md` bind you." in text, a
        assert ("Cite one in your output only if you fetched it in this run; "
                "otherwise state the concern without the citation.") in text, a
        assert text.split("## Input", 1)[1].lstrip().startswith("The orchestrator will provide `PDF_PATH`, `PAGE_COUNT`,"), a
        assert 'If the list says "none" or is missing' in text, a
        for s in ("log-like outcome with zeros", "subsample comparison", "at most two terms have this role"):
            assert s in text, (a, s)
        assert "Reply to the orchestrator in one sentence that names the file you wrote." in text, a
        assert "\u2014" not in text, a
    for a in AGENTS[1:]:
        assert "Never predict the result" in _agent(a), a


def test_specification_agent_n2_terms_and_scope():
    text = _agent("nonlinear-specification.md")
    n2 = text.split("### N2.", 1)[1].split("### N7.", 1)[0]
    assert "x times m for a shift, x squared times m for a change in curvature" in n2
    assert "only that curves at low and high moderator values are shown" in n2
    assert "owned by the nonlinear claims agent's N4" in n2


def test_specification_agent_n12_skips():
    text = _agent("nonlinear-specification.md")
    n12 = text.split("### N12.", 1)[1].split("## Output", 1)[0]
    assert "A binary moderator (a dummy or a randomized arm) needs no linearity check." in n12
    assert "already flexible (bins, splines, piecewise, or two lines) needs none" in n12
    assert "Skip the squares-of-correlated-variables check when either variable is binary." in n12


def test_specification_agent_n7_skips_and_reverse_reading():
    text = _agent("nonlinear-specification.md")
    n7 = text.split("### N7.", 1)[1].split("### N12.", 1)[0]
    assert "sit above the level at which the optimum is claimed" in n7
    assert "only an average population-level curve" in n7
    assert "already reports the within-unit range next to the optimum" in n7
    assert "firms with intermediate levels do best" in n7
    assert "only as the comparison for the claimed optimum" in n7
    assert "`run.json` `packs`" in n7 and "archival" in n7
    assert "{WORKSPACE}/run.json" in text


def test_specification_agent_caps_model_form_findings():
    text = _agent("nonlinear-specification.md")
    assert ('Model-form findings (N2, N7, N12) are at most "Weakens a claim" unless severity rule 1 applies.') in text


def test_methods_checks_reads_run_json_and_hands_off_nonlinear_terms():
    text = (ROOT / "packs" / "archival" / "agents" / "methods-checks.md").read_text(encoding="utf-8")
    assert "`{WORKSPACE}/run.json`" in text and "if the file or the key is missing, treat the nonlinear pack as not running" in text
    marker = "When `run.json` `packs` lists `nonlinear`"
    assert text.count(marker) == 1
    handoff = text.split(marker, 1)[1].split("\n\n", 1)[0]
    for s in ("squared terms", "odds ratios", "inverse hyperbolic sine", "`Nonlinear terms:`",
              "CHECK 2", "CHECK 6", "CHECK 7b", "CHECK 10"):
        assert s in handoff, s
    assert "\u2014" not in handoff


def test_numbers_agent_builds_odds_ratio_records_only_for_probability_readings():
    text = _agent("nonlinear-numbers.md")
    bullet = text.split("- `odds_ratio` (check N9)", 1)[1].split("\n", 1)[0]
    for s in ("likelihood", "probability", "chance", '"times as likely"'):
        assert s in bullet, s
    assert '("percent higher odds") is correct and gets no record' in bullet


def test_numbers_agent_builds_difference_records_only_without_the_papers_test():
    text = _agent("nonlinear-numbers.md")
    bullet = text.split("- `difference` (check N6)", 1)[1].split("\n", 1)[0]
    assert "only when the paper reports no pooled interaction or test of equal coefficients for that difference" in bullet
    assert "note the paper's test under `## Terms checked`" in bullet


def test_numbers_agent_marks_monotone_quadratic_claims():
    text = _agent("nonlinear-numbers.md")
    bullet = text.split("- `quadratic` (check N1)", 1)[1].split("\n", 1)[0]
    assert 'Set `claim` to "monotone"' in bullet and "diminishing or increasing returns" in bullet
    assert "tests only the slope at the maximum" in bullet


def test_numbers_agent_lists_a_missing_table_under_not_computed():
    text = _agent("nonlinear-numbers.md")
    assert "If a table a record needs is missing from `extracted_tables/`" in text
    assert "under `## Not computed` with the table's label and the `<table>:<row>:<col>` of each cell" in text


def test_claims_agent_rates_a_failed_far_end_slope_on_a_monotone_claim():
    text = _agent("nonlinear-claims.md")
    n1 = text.split("### N1.", 1)[1].split("\n### ", 1)[0]
    assert '`claim` "monotone"' in n1 and "slope at the maximum" in n1
    assert ("when the term's role is main hypothesis and the far-end slope has the wrong sign or is not "
            "distinguishable from zero, the issue is 'Weakens a claim' under severity rule 2") in n1


def test_methods_checks_hand_off_is_a_list_scoped_to_nonlinear_readings():
    text = (ROOT / "packs" / "archival" / "agents" / "methods-checks.md").read_text(encoding="utf-8")
    handoff = text.split("When `run.json` `packs` lists `nonlinear`", 1)[1].split("\n\n", 1)[0]
    assert len(re.findall(r"^ *- ", handoff, re.M)) >= 12
    assert "incidence rate ratios and hazard ratios" in handoff and "N9" in handoff
    assert ("the marginal-effects check covers main effects; product and squared terms in logit or probit "
            "models go to the nonlinear pack.") in handoff


def test_diagnose_agents_describe_dropped_flags_as_not_a_problem():
    for a in ("nonlinear-claims.md", "nonlinear-specification.md"):
        text = _agent(a)
        assert "number flags the user marked as not a problem or misread" in text, a
        assert "marked as extraction errors" not in text, a


# --- Post-1e item 4 (Plan 2b Task 11) ---

def test_readme_and_spec_name_the_nonlinear_overlay():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert len(re.findall(r"A pack adds checks for one kind of paper\. \w+ are built\.", readme)) == 1
    assert "A pack adds checks for one kind of paper. Two are built." not in readme
    assert readme.count("- **Nonlinear** is an overlay.") == 1
    assert readme.index("- **Computational** is an overlay.") < readme.index("- **Nonlinear** is an overlay.")
    spec = (ROOT / "docs" / "spec.md").read_text(encoding="utf-8")
    assert "Seven packs are overlays: computational, nonlinear, inference, market-event" in spec
