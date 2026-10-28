from __future__ import annotations
import hashlib
import re
from pathlib import Path

import pytest
import yaml

from plumb import packs
from tests.scrub_names import banned_hashes, name_hits

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "packs" / "archival"
MODS = PACK / "modules"
AGENTS = PACK / "agents"
SKILL = ROOT / "skills" / "review"

STEMS = ["did", "rdd", "iv", "synth", "selection"]
IDS = {
    "did": ["DD1", "DD2", "DD3", "DD4", "DD5", "DD6", "DD7", "DD8", "DD9", "DD10", "DD11", "DD12", "DD14", "DD15"],
    "rdd": ["RD1", "RD2", "RD3", "RD4", "RD5", "RD6", "RD7", "RD8", "RD9", "RD10", "RD11", "RD12", "RD13", "RD14",
            "RD16", "RD17"],
    "iv": ["IV1", "IV2", "IV3", "IV4", "IV5", "IV6", "IV7", "IV8", "IV9", "IV11", "IV12", "IV13", "IV14", "IV15",
           "IV16"],
    "synth": ["SC1", "SC2", "SC3", "SC4", "SC5", "SC6", "SC7", "SC8", "SC9", "SC10", "SC11", "SC12", "SC13",
              "SC15"],
    "selection": [f"SO{i}" for i in range(1, 16)],
}
LATER = {"did": ["DD13"], "rdd": ["RD15"], "iv": ["IV10", "IV17"], "synth": ["SC14"], "selection": []}
DIGESTS = {"did": "c920f79b44050c89", "rdd": "32b323d60add3f01", "iv": "51e464f2cd044835",
           "synth": "372caf319efec1d8", "selection": "0b0dcaefae1fdbea"}
LABELS = {"did": "DiD", "rdd": "RD", "iv": "IV", "synth": "SC", "selection": "Selection"}
DEFS = {
    "did": "The paper compares the change in an outcome for units that receive a treatment with the change for "
           "units that do not, over periods before and after the treatment, including event-study regressions with "
           "leads and lags and designs where units adopt at different times.",
    "rdd": "Treatment changes discontinuously when a score, count, vote share, distance, or date crosses a cutoff, "
           "and the paper estimates the effect from units near the cutoff.",
    "iv": "The paper estimates the effect of an endogenous variable using a variable (an instrument) that shifts it, "
          "by two-stage least squares, LIML, GMM, or a control function with an excluded instrument.",
    "synth": "The paper builds the counterfactual for one or a few treated units as a weighted combination of "
             "untreated units, fitted on pre-treatment outcomes or predictors.",
    "selection": "The paper addresses non-random treatment or sample selection by matching, weighting, entropy "
                 "balancing, a doubly robust or double machine learning treatment-effect estimator, a Heckman or "
                 "treatment-effects model, or a named sensitivity analysis for omitted variables (Oster, "
                 "Cinelli-Hazlett, ITCV, Rosenbaum bounds).",
}


def _yaml(stem):
    return yaml.safe_load((MODS / f"{stem}.yaml").read_text(encoding="utf-8"))


def _md(stem):
    return (MODS / f"{stem}.md").read_text(encoding="utf-8")


def test_modules_load_with_the_spec_ids_and_labels():
    p = packs.load_pack(PACK)
    assert sorted(p.modules) == sorted(STEMS)
    for stem in STEMS:
        m = p.modules[stem]
        assert m.label == LABELS[stem] and m.definition == DEFS[stem], stem
        assert [i["id"] for i in m.checklist] == IDS[stem], stem


def test_module_checklist_text_is_verbatim_from_the_spec():
    for stem in STEMS:
        blob = "".join(f"{i['id']}|{i['text']}|{i['adjudication']}\n" for i in _yaml(stem)["checklist"])
        assert hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16] == DIGESTS[stem], stem


def test_cut_items_are_listed_as_later_and_never_used():
    for stem in STEMS:
        y = _yaml(stem)
        assert y["later"] == LATER[stem], stem
        assert not set(LATER[stem]) & {i["id"] for i in y["checklist"]}, stem


def test_encouragement_subset():
    assert _yaml("iv")["encouragement"] == ["IV1", "IV2", "IV3", "IV4", "IV5", "IV9", "IV11"]
    for stem in ("did", "rdd", "synth", "selection"):
        assert _yaml(stem)["encouragement"] == [], stem


def test_archival_checklist_retires_a4_a5_a9():
    ids = [i["id"] for i in yaml.safe_load((PACK / "checklists" / "archival.yaml").read_text(encoding="utf-8"))]
    assert ids == ["A1", "A2", "A3", "A6", "A7", "A8", "A10", "A11", "A12"]
    assert _yaml("did")["replaces"] == ["A4", "A9"] and _yaml("iv")["replaces"] == ["A5"]


def test_pack_yaml_carries_the_module_severity_rules_and_cues():
    p = packs.load_pack(PACK)
    rules = " ".join(p.severity_rules)
    assert "A module finding on a design whose role is secondary is 'Minor'" in rules
    assert "Report at most two findings per secondary design." in rules
    assert "the module rules replace the pack's general rule" in rules
    assert "CHECK 7b's automatic High and adversarial-DGP's auto-severity patterns do not apply to module ids" in rules
    for cue in ("synthetic control", "propensity score", "Heckman", "shift-share", "entropy balancing"):
        assert cue in p.detection_cues, cue


def test_module_fixtures_are_labeled_synthetic_stubs():
    for stem in STEMS:
        exp = yaml.safe_load((PACK / "fixtures" / f"{stem}-1" / "expected.yaml").read_text(encoding="utf-8"))
        assert exp["module"] == stem and exp["synthetic"] is True and exp["owner"] == "blind-agent", stem
        assert exp["label"] == "SYNTHETIC TEST PAPER, NOT REAL RESEARCH"
        assert exp["status"] in ("pending_planting", "ready")
        every_id = set().union(*IDS.values())
        for item in exp["must_catch"] + exp["must_not_flag"] + exp.get("also_fair", []):
            assert item["check"] in every_id, (stem, item)


def test_no_archival_file_names_the_owner_paper():
    # Author names come from the untracked local list (tests/scrub_names.py).
    hashes = banned_hashes()
    if not hashes:
        pytest.skip("no local scrub names file; name check skipped")
    for f in list(PACK.rglob("*.md")) + list(PACK.rglob("*.yaml")) + list(PACK.rglob("*.tex")):
        assert name_hits(f.read_text(encoding="utf-8"), hashes) == 0, f.name



def _headings(stem):
    return re.findall(r"^### ([A-Z]{2}\d+)\. ", _md(stem), re.M)


def test_did_module_has_one_heading_per_check():
    assert _headings("did") == IDS["did"]
    assert "### DD13." not in _md("did")


def test_did_module_carries_the_grill_rules():
    t = _md("did")
    assert "Wooldridge's extended TWFE with cohort-by-period interactions" in t and "stacked DiD with clean controls" in t
    assert "agrees with the headline in sign and is of similar size" in t
    assert "A named package run with its defaults passes." in t
    assert "at least four pre-period coefficients" in t and "common reference period" in t
    assert "3 or more consecutive" not in t and "varying base period" in t
    assert "exact linear extrapolation of the pre-trend" in t and "Mbar = 0, which is exact parallel trends" in t and "Daw and Hatfield (2018)" in t
    assert "When no sensitivity analysis is reported and DD5 found no drift, \"Minor\"." in t
    assert "Firm age, founding year, and other traits the treatment cannot move never qualify." in t
    assert "If `run.json` `overlays` lists `inference`, skip this check" in t



def test_rdd_module_has_one_heading_per_check():
    assert _headings("rdd") == IDS["rdd"]
    assert "### RD15." not in _md("rdd")


def test_rdd_module_carries_corrections_1_and_2():
    t = _md("rdd")
    assert "Calonico, Cattaneo, and Titiunik 2014" in t and "Calonico, Cattaneo, and Farrell (2014" not in t
    assert "Kolesar and Rothe (2018)" in t and "do not guard against model misspecification" in t
    assert "invalid without clustering" not in t
    assert "a local randomization analysis with a stated window-selection rule" in t
    assert "bias-aware (honest) intervals with a stated smoothness bound" in t
    assert "Bach and Metzger (2019)" in t



def test_iv_module_has_one_heading_per_check():
    assert _headings("iv") == IDS["iv"]
    assert "### IV10." not in _md("iv") and "### IV17." not in _md("iv")


def test_iv_module_carries_correction_3_and_software_labels():
    t = _md("iv")
    assert ("With one instrument and one endogenous regressor, the robust F, the Kleibergen-Paap Wald F, and the "
            "effective F are the same statistic") in t
    assert "Neither Cragg-Donald nor Kleibergen-Paap" not in t and "wrong diagnostic" not in t
    assert "\"the Cragg-Donald F statistic in the presence of only one endogenous regressor\"" in t
    assert "\"is equivalent to the Kleibergen-Paap statistic\"" in t
    assert "cluster small-sample adjustment" in t
    assert "Do not state a general rule that an F above 10 is adequate" in t
    assert "Section 5.4" in t and "2309.01637" not in t and "Windmeijer 2025" not in t
    assert "z_i = (S_gt - x_i)/(n_gt - 1)" in t and "Forbidden regression." in t


def test_iv_module_names_the_encouragement_subset():
    t = _md("iv")
    assert "IV1, IV2, IV3, IV4, IV5 (the channel argument only" in t and "IV9, and IV11" in t



def test_synth_module_has_one_heading_per_check():
    assert _headings("synth") == IDS["synth"]
    assert "### SC14." not in _md("synth")


def test_synth_module_carries_correction_4_and_the_floor_rule():
    t = _md("synth")
    assert "Concentration or dispersion is not by itself a flaw" in t and "Sparsity:" not in t
    assert "allows negative weights on some donor units" in t
    assert "never reconstruct a count from a discard rule" in t
    assert "A reported p-value below the floor while the floor still clears the claimed level is \"Minor\"." in t
    assert "Do not apply a numeric cutoff for good fit" in t



def test_selection_module_has_one_heading_per_check():
    assert _headings("selection") == IDS["selection"]


def test_selection_module_carries_correction_5_and_the_direction_rule():
    t = _md("selection")
    assert "do not call it invalid and do not ask a paper that reports it to replace it" in t
    assert "Do NOT recommend the ITCV" not in t
    assert "the paper's own evidence implies the restriction favors the headline's sign" in t
    assert "Direction outranks methods-checks CHECK 7b's automatic High" in t
    assert "A paper that only adds control variables does not load this module" in t
    assert "SO1 is never above \"Weakens a claim\"." in t


def test_every_module_id_is_owned_by_exactly_one_heading():
    for stem in STEMS:
        for cid in IDS[stem]:
            assert _md(stem).count(f"### {cid}. ") == 1, cid


def _agent(name):
    return (AGENTS / name).read_text(encoding="utf-8")


def test_design_checks_agent_runs_in_the_diagnose_slot():
    p = packs.load_pack(PACK)
    assert p.slots["diagnose"] == ["methods-checks.md", "adversarial-dgp.md", "triangulation.md", "design-checks.md"]
    t = _agent("design-checks.md")
    assert t.startswith("---\nname: design-checks-agent\n") and "maxTurns: 30" in t
    assert "The orchestrator will provide `PDF_PATH`, `PAGE_COUNT`, and `{WORKSPACE}`." in t
    assert "skills/review/shared/contracts.md" in t and "Cite one in your output only if you fetched it" in t
    assert "Reply to the orchestrator in one sentence" in t


def test_design_checks_loads_only_listed_modules_and_falls_back_only_when_missing():
    t = _agent("design-checks.md")
    for stem in STEMS:
        assert f"{{PLUGIN}}/packs/archival/modules/{stem}.md" in t, stem
    assert "Ignore `IV (encouragement)`" in t
    assert "If the field says \"none\", load nothing" in t
    assert "Only if the `Designs:` field is missing from the fingerprint" in t
    for stem in STEMS:
        assert DEFS[stem] in t, stem


def test_design_checks_copies_the_pack_severity_rules():
    t = _agent("design-checks.md")
    for rule in packs.load_pack(PACK).severity_rules[2:]:
        assert rule in t, rule
    assert "Apply only rules that set a level." in t
    assert "so the Stage 4 compiler applies it, not you" in t


def test_design_checks_output_uses_the_issue_template():
    t = _agent("design-checks.md")
    assert "{WORKSPACE}/stage-4/design_checks.md" in t and "Modules loaded:" in t
    assert "```markdown\nPack: archival\n\n# Design checks" in t
    assert "Design: <label> (<role>)" in t and "Excerpt:" in t and "Page:" in t
    assert "Severity: <Undermines the main claim | Weakens a claim | Minor>" in t
    assert "## Checked and fine" in t and "stage-1/dropped_flags.md" in t




def test_methods_checks_hands_the_designs_to_the_modules():
    t = _agent("methods-checks.md")
    for gone in ("#### If Difference-in-Differences (DiD):", "#### If Instrumental Variables (IV):",
                 "#### If Regression Discontinuity (RD):", "#### If Matching / Propensity Score:",
                 "#### If Shift-Share / Bartik Instrument:", "#### If Synthetic Control:"):
        assert gone not in t, gone
    for kept in ("#### If AKM", "#### If Bunching", "#### If Event Study (distinct from DiD):",
                 "#### If Double/Debiased Machine Learning", "#### If Mediation Analysis:"):
        assert kept in t, kept
    assert "are checked by the archival design-checks agent. Do not check them here." in t
    assert "If it lists DiD, skip covariates in a DiD regression (DD11). If it lists Selection, skip covariates in a score, matching, or weighting model (SO13) and sample restrictions on a variable the treatment could affect (SO14)." in t
    assert "Skip this block when the `Designs:` line lists DiD" in t
    assert "maxTurns: 30" in t


def test_methods_checks_corrections():
    t = _agent("methods-checks.md")
    for gone in ("Calonico, Cattaneo, and Farrell (2014", "invalid without clustering",
                 "Neither Cragg-Donald nor Kleibergen-Paap", "Do NOT rely on rules of thumb",
                 "Do NOT recommend the ITCV", "note that Kleibergen-Paap is preferred", "**LATE vs. ATE:**"):
        assert gone not in t, gone
    assert "The ITCV (Frank 2000) is a recognized sensitivity measure in management research" in t
    assert "the design-checks agent's IV module (IV15) owns it" in t


def test_triangulation_and_adversarial_dgp_defer_to_the_modules():
    tri = _agent("triangulation.md")
    assert "If `Designs:` lists DiD, skip the straight-line test; the design module owns it." in tri
    assert "as corrected in `{WORKSPACE}/brief.md` (section 'User corrections'), lists IV (the label" in tri
    assert "Skip the standard tests of a design listed in the `Designs:` line" in tri
    assert "any method the paper uses that is not listed" in tri
    adv = _agent("adversarial-dgp.md")
    assert "cite the design module's check SO14 by id and do not set their severity" in adv


def test_fingerprint_lists_designs_with_roles():
    text = (SKILL / "agents" / "manuscript-audit.md").read_text(encoding="utf-8")
    template = text.split("# Fingerprint", 1)[1].split("```", 1)[0]
    assert "Designs:\n- <label>: role: <main | secondary>; cue: <phrase, table, or figure, with page>" in template
    for stem in STEMS:
        assert f"- {LABELS[stem]}: \"{DEFS[stem]}\"" in text, stem
    assert "- IV (encouragement):" in text and "Copy what the paper does; judge nothing." in text


def test_archival_pack_shows_the_design_lines_at_the_read_checkin():
    assert packs.load_pack(PACK).read_checkin_lines == ["Designs:"]


def test_stage_0_passes_module_cues_to_the_auditor():
    s0 = (SKILL / "stages" / "stage-0-intake.md").read_text(encoding="utf-8")
    step4 = s0.split("\n4. ", 1)[1].split("\n", 1)[0]
    step10 = s0.split("\n10. ", 1)[1].split("\n", 1)[0]
    assert ("keep all three, with each pack's status, for steps 10, 11, and 13. It also prints `\"modules\"`: each "
            "pack's design modules with their labels, definitions, and cues; keep it for step 10.") in step4
    assert "Pass the auditor the overlay labels and cues from the step 4 output." in step10
    assert ("Pass it the module labels, definitions, and cues from the step 4 output as well; it uses them for the "
            "`Designs:` line.") in step10


CORRECTED = "the `Designs:` line in `{WORKSPACE}/stage-0/fingerprint.md`, as corrected in `{WORKSPACE}/brief.md` (section 'User corrections'),"
MISSING_GATE = "When the `Designs:` line is missing, skip nothing; the design-checks agent may also report these items and Stage 4 merges duplicates."


def test_gates_read_the_corrected_designs_line():
    m = _agent("methods-checks.md")
    tri = _agent("triangulation.md")
    adv = _agent("adversarial-dgp.md")
    assert m.count(CORRECTED) == 2
    assert tri.count(CORRECTED) == 2
    assert "section 'User corrections')); its design module owns them." in tri
    assert adv.count(CORRECTED) == 1
    for t in (m, tri, adv):
        assert t.count(MISSING_GATE) == 1
    stage2 = (SKILL / "stages" / "stage-2-understand.md").read_text(encoding="utf-8")
    assert 'append it to `brief.md` under "User corrections"' in stage2


def test_methods_checks_clustering_level_stays_for_did():
    m = _agent("methods-checks.md")
    assert "lists DiD, leave cluster counts and few-treated-cluster inference for those estimates to the design-checks agent (DD15); keep the clustering-level hierarchy in CHECK 5 and the wrong-cluster-level pattern in CHECK 7b for DiD estimates." in m
    assert "When it lists SC, or IV with shift-share, leave all clustering and inference for those estimates to the design-checks agent (SC8 and SC11, IV14)." in m
    assert "  - the DiD triple difference is the design-checks agent's (DD12);" not in m
    assert "\nThe DiD triple difference is the design-checks agent's (DD12).\n" in m
    assert "Skip this bullet when the `Designs:` line lists Selection (SO12 owns it)." in m
    assert "Skip this bullet when the `Designs:` line lists Selection (SO8 owns it)." in m
    tri = _agent("triangulation.md")
    assert "should recommend Rambachan and Roth (2023)" not in tri
    assert "For a non-DiD event study, note that a joint pretest that fails to reject is weak evidence." in tri


def test_final_fix_module_substance():
    did = _md("did")
    assert "or is materially smaller and not significant at the 10 percent level while the headline claims 5 percent or better" in did
    assert "(control group, base period, anticipation window, covariates, aggregation weights)" in did
    assert "(a conservative gate set by this pack, not a rule from the literature)" in did
    sc = _md("synth")
    assert "With N treated units permuted as a set, the floor is 1/C(J+N, N) (Abadie 2021; Firpo and Possebom 2018)." in sc
    assert "the floor depends on the number of time permutations, not J; skip the floor check." in sc
    assert "The statistic is fit-adjusted (for example the post/pre RMSPE ratio), or the paper states a rule for discarding poorly fitting placebos." in sc
    assert "a Lee (2009) trimming bound or a worst-case calculation from the paper's own numbers includes zero" in _md("selection")
    assert "bin counts from the paper's own table or figure on each side of the threshold show the drop" in _md("rdd")
    iv = _md("iv")
    assert "When the first stage is clearly strong, a missing Anderson-Rubin interval is at most \"Minor\"." in iv
    assert "2SLS reproduces OLS exactly when group sizes are equal and a group-size-weighted OLS otherwise" in iv
    rule = "(DD1, RD2, RD3, RD4, SC8, IV1 below 10, IV15, and DD5 and SO14 in their Undermines cases)"
    assert rule in (ROOT / "packs" / "archival" / "pack.yaml").read_text(encoding="utf-8")
    assert rule in _agent("design-checks.md")


def test_did_handoff_keeps_clustering_level_with_methods_checks():
    did = (ROOT / "packs" / "archival" / "modules" / "did.md").read_text(encoding="utf-8")
    assert "The clustering level stays with methods-checks CHECK 5 and CHECK 7b, or with the inference overlay (I1) when it runs." in did
    assert "Clustering level and count, and few treated clusters, belong to the inference overlay" not in did
