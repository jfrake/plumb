from __future__ import annotations
import re
from pathlib import Path

import pytest
import yaml

from plumb import packs

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "review"
PACK = ROOT / "packs" / "network"


# --- Task 1: the fingerprint fields ---

def _audit():
    return (SKILL / "agents" / "manuscript-audit.md").read_text(encoding="utf-8")


def test_fingerprint_records_network_design_and_variables():
    text = _audit()
    template = text.split("# Fingerprint", 1)[1].split("```", 1)[0]
    assert ("Network design: <one or more of: measure as variable | dyadic ties | whole-network model | spread through ties>; "
            "data: <archival records | whole-network survey | egocentric survey | digital traces>; "
            "mode: <one-mode | two-mode projected to one mode | two-mode analyzed as two-mode>") in template
    assert "Network variables:\n- <variable name>: <kind>; role: <role>" in template
    for kind in ("degree or tie count", "structural holes (constraint, effective size, efficiency)",
                 "exposure to alters", "tie as outcome"):
        assert kind in text, kind


def test_network_threshold_excludes_counts_controls_and_simulated_networks():
    text = _audit()
    for phrase in ("a network variable of any kind except degree or tie count has role main treatment, main outcome, "
                   "or moderator or mechanism",
                   "A network measure used only as a control does not count, and neither does a degree or tie count alone.",
                   "A network the paper generates by simulation or from a formal model does not count",
                   "A network variable is one the paper computes from ties among actors that it observes (records, a "
                   "roster or name-generator survey, or digital traces). A questionnaire scale, a role or title, or a "
                   "theory term such as brokerage, closure, or embeddedness with no tie data is not one. A claim of "
                   "spread counts only when the paper estimates it with data on who is tied to whom, or who shares a "
                   "group.",
                   "List the network overlay under `Overlays:` only when `Network design:` is not \"none\"."):
        assert phrase in text, phrase


# --- Task 3: the pack frame ---

IDS = ["G1", "G2", "G3", "G4", "G6", "G7", "G8", "G9", "G10", "G11", "G12", "G13", "G15", "G16"]
JUDGMENT = {"G13", "G15"}
CHECKLIST = {
    'G1': 'Descriptive network statistics agree with the counts they come from when the paper states both for the same network: density with the numbers of actors and ties, mean degree with ties per actor, and the number of dyads with the actors, periods, and sampling described',
    'G2': 'The network boundary (which actors and which kinds of tie are included) is stated, and the set of actors used to compute each network measure matches the population the hypotheses describe; ties to actors outside the sample are either included in the measure or the omission is stated and its effect considered; actors with no ties in the window are included or excluded by a stated rule, and a sample restricted to actors with ties is noted as conditioning on tie formation; closeness, path length, and small-world statistics state how unreachable pairs in a disconnected network are handled',
    'G3': 'What counts as a tie, when it starts, and when it ends are stated; the time window or decay rule is stated, ties the data record as ended are not kept active without a stated reason, and the main result is shown under at least one other window or decay rule',
    'G4': "Missing actors and ties are quantified: for survey data, the response rate and the shares of pairs in which both members, and at least one member, responded; for archival data, the coverage limits of the source; the handling of missing actors and ties is stated; and, for survey data, and for archival data where the paper's own description shows the coverage gap bears on the measure, the main network measures are shown to be robust to plausible missingness",
    'G6': 'How actors are identified across records (inventor disambiguation, firm names, parents and subsidiaries, mergers, director identity) is described, with a match rate or error rate or a bound on it',
    'G7': 'When ties come from shared affiliations (boards, patents, deals, papers) projected to one mode, the paper says so, and it does not read clustering, transitivity, density, or small-world statistics of the projection as evidence of closure or cohesion without a baseline that keeps the affiliation structure or a measure defined on the two-mode data',
    'G8': 'For network data collected by survey, the name generator and any cap on the number of contacts are stated; ego-network measures built from respondent-reported ties among contacts are described as such and not read as position in the whole network; and the rule that turns one or two reports into a tie (either reports, both report) is stated, with results under the other rule when reciprocity or tie-level results are claimed',
    'G9': "When constraint, effective size, efficiency, or a centrality score other than degree is a main or moderating variable, the model includes the actor's number of contacts (degree or ego-network size) or the paper reports the correlation and shows the result is not an effect of having more ties",
    'G10': 'In any model whose unit is a dyad or a directed tie, inference allows for correlation among all dyads that share an actor, in either position (dyadic-robust standard errors, a permutation test such as QAP, or a model of the dependence); clustering on one member of the pair, or by dyad alone, does not meet this; when no actor can appear in both positions (two-mode dyads such as investor and startup), two-way clustering on the two members meets it',
    'G11': 'In a tie-formation model, the set of pairs at risk of forming a tie is defined and defended; when non-ties are sampled, the sampling ratio is reported and the estimates are reweighted or corrected, or the paper does not interpret the intercept, predicted probabilities, or baseline rates; and actor-level propensity to form ties is handled for both members of the pair (actor fixed effects, or degree or activity controls for both)',
    'G12': "When the paper estimates an ERGM, TERGM, SAOM, relational event, or latent space model: for simulation-based estimates (MCMC maximum likelihood for ERGM and TERGM, SAOM method of moments, Bayesian latent space), it reports convergence for every parameter against the software's stated criteria and checks for degeneracy where the model family is prone to it; for pseudo-likelihood estimates, it states the bootstrap used; for every ERGM, TERGM, and SAOM, it reports goodness of fit on network statistics not included in the model; QAP results state which permutation method was used",
    'G13': "A claim that an outcome spreads through ties (influence, contagion, imitation, learning from partners) rests on a design that separates spread from selection on similar traits, shared environment, and the partner choice itself (randomized ties or treatments, an outside shock to ties, a dynamic model of selection and influence, identification from network structure (peers of peers who are not peers; Bramoulle, Djebbari, and Fortin 2009), or placebo outcomes and timing tests); otherwise the wording is associational; a regression of an actor's outcome on the contemporaneous mean outcome of its peers or group is read as an endogenous peer effect only with a stated identification argument, and is separated from the effects of peers' characteristics and of shared conditions",
    'G15': 'When network position is a main predictor of performance and no archival adversarial agent runs, the paper names what produces the position (prior status, prior ties, shared affiliations, the traits that also drive the outcome) and its design addresses those; instruments for position are judged by the IV checks, not here',
    'G16': 'Network measures are computed from ties formed before the outcome is measured; when the window for the measure overlaps the outcome period, the paper says so and shows a specification without the overlap; tie formation and tie persistence are not pooled when the claim concerns only one',
}
RULES = [
    "G13 wording test. The claim is causal when the abstract, the hypotheses, or the conclusions use causal verbs for spread (causes, leads to, influences, learns from, spreads to, imitates because). A paper that uses associational wording throughout ('is associated with', 'consistent with') gets no G13 finding. A paper whose abstract or conclusion is causal while the results section hedges gets 'Weakens a claim' at most, and the fix is wording.",
    "G13 design. When the claim is causal, is the main claim, the paper is theory testing, and the design has no strategy that separates spread from selection, such as those G13 lists, the finding is 'Undermines the main claim'. When the design uses one of them and a gap remains, or the claim is not the main claim, it is 'Weakens a claim'. Causal wording on a secondary result whose design the paper otherwise treats as associational is 'Minor'.",
    "G13 reflection. A linear-in-means coefficient that the main claim reads as an endogenous peer effect, with no identification argument, is 'Undermines the main claim'. The same with an argument that the paper does not defend against the correlated-effects reading is 'Weakens a claim'.",
    'For a phenomenon-driven paper, lower each G13 finding by one level. The Stage 4 compiler applies this rule once; the network agents never apply it.',
    "G10. Errors that do not meet G10 (default, heteroskedasticity-robust only, clustered by dyad only, or clustered on one member only) in a model that tests any hypothesis are 'Weakens a claim'. The finding is 'Undermines the main claim' only when the model tests the headline hypothesis and the paper's own estimate with errors that meet G10 is not significant at the level the text uses for the headline. Two-way clustering on the two members' identities in one-mode dyads is 'Minor'.",
    "G12. When the paper's own reported convergence statistics fail the criteria the paper or its software documentation states, for a parameter that carries a hypothesis, the finding is 'Undermines the main claim' if that hypothesis is the headline one and 'Weakens a claim' otherwise. Missing diagnostics are 'Weakens a claim' for the model that carries the main claim and 'Minor' for a robustness model.",
    "G1. A descriptive network statistic that the paper's own counts cannot produce is a number flag at the Stage 1 check-in, not a major issue, unless the same number enters a model; then it is 'Weakens a claim'.",
    "A finding on a network statistic that carries no hypothesis is 'Minor'.",
    "A missing statement (no boundary, no window, no match rate) is 'Minor' when the choice is a common convention the paper cites, even when the variable it affects carries the main claim, and 'Weakens a claim' when that variable carries the main claim and the paper cites no such precedent.",
    "G3. No alternative window, with a conventional window stated, is 'Minor'. It is 'Weakens a claim' when the paper keeps ties active past end dates it says the source records, or when the variable carries the main claim and the window is unconventional or unstated.",
    "Every other network finding is capped at 'Weakens a claim'.",
]
SHIFT = RULES[3]
MEASUREMENT_RULES = [RULES[i] for i in (6, 7, 8, 9, 10)]
INFERENCE_RULES = [RULES[i] for i in (0, 1, 2, 4, 5, 7, 8, 10)]
SEVERITIES = ("Undermines the main claim", "Weakens a claim", "Minor", "number flag")


def _expected():
    return yaml.safe_load((PACK / "fixtures" / "planted-1" / "expected.yaml").read_text(encoding="utf-8"))


def test_network_pack_loads_as_an_overlay():
    p = packs.load_pack(PACK)
    assert p.name == "network" and p.overlay is True and p.turns_off == []
    assert "context" not in p.slots and "theory" not in p.slots
    assert [i["id"] for i in p.checklist] == IDS


def test_checklist_matches_the_spec():
    items = {i["id"]: i for i in packs.load_pack(PACK).checklist}
    for k in IDS:
        assert items[k]["text"] == CHECKLIST[k], k
        assert items[k]["adjudication"] == ("judgment" if k in JUDGMENT else "paper"), k


def test_severity_rules_are_the_specs():
    assert packs.load_pack(PACK).severity_rules == RULES


def test_read_checkin_lines():
    assert packs.load_pack(PACK).read_checkin_lines == ["Network design:", "Network variables:"]


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

# --- Task 4: the numbers agent ---

def _agent(name):
    return (PACK / "agents" / name).read_text(encoding="utf-8")


def test_numbers_agent():
    assert packs.load_pack(PACK).slots.get("verify") == ["network-numbers.md"]
    text = _agent("network-numbers.md")
    for s in ("stage-1/network_numbers.md", "## Statistics checked", "## Flags", "## Facts for later agents",
              "## Not computed", "Quick", "Record: <id>. Table: <label>. Cells: <table:row:col, ...>.",
              "Flag nothing as missing", "never put them under `## Flags`"):
        assert s in text, s
    for kind in ("summary", "dyads", "response", "range"):
        assert f"`{kind}`" in text, kind
    assert re.search(r"^### G1\. ", text, re.M)


def test_numbers_agent_runs_the_script_with_its_own_tools():
    text = _agent("network-numbers.md")
    assert "tools: [Read, Write, Bash, Glob]" in text.split("---", 2)[1]
    assert "The orchestrator will provide `PDF_PATH`, `PAGE_COUNT`, `{WORKSPACE}`, and `{PLUGIN}`." in text
    assert ("`python3 {PLUGIN}/packs/network/scripts/check_network_numbers.py "
            "{WORKSPACE}/stage-1/network_numbers_input.json`") in text
    assert "with the file-writing tool" in text
    assert not re.search(r"(cat|echo|printf|tee)[^\n`]*>", text)


def test_numbers_agent_gates_summary_on_one_network():
    text = _agent("network-numbers.md")
    assert ("Set `same_network` to true only when the paper states the actors, the ties, and the statistic "
            "for the same network") in text
    assert "Do not record constraint, effective size, efficiency, or normalized centrality" in text
    assert ("`ties` is the number of distinct pairs with a tie (ordered pairs when directed); a count of "
            "alliances, deals, or events is not") in text
    assert "`unstated` when the paper does not say which" in text and "add a `%` sign" in text


def test_numbers_agent_script_hardening_sentences():
    text = _agent("network-numbers.md")
    assert "record `12%`, not `12`" in text
    assert "contains a comma" in text and "list it under `## Not computed`" in text
    assert "If the script exits with a Python traceback, write a tool error under `## Not computed`" in text
    assert "never rewrite records to make it pass" in text
    assert "Number the flags consecutively from 1 in the order of the script's `results` list" in text
    assert ("- `{WORKSPACE}/brief.md`, section \"User corrections\": a corrected role or mode there overrides the "
            "fingerprint, and a corrected mode decides `same_network`.") in text
    assert "also go under `## Facts for later agents`" in text


# --- Task 5: the measurement agent ---

def test_measurement_agent():
    assert packs.load_pack(PACK).slots.get("diagnose", [])[:1] == ["network-measurement.md"]
    text = _agent("network-measurement.md")
    assert "stage-4/network_measurement.md" in text and "Its first line is exactly `Pack: network`." in text
    for c in ("G2", "G3", "G4", "G6", "G7", "G8", "G9", "G16"):
        assert re.search(rf"^### {c}\. ", text, re.M), c
    for s in ("Excerpt:", "Page:", "## Checked and fine", "Severity: <Undermines the main claim | Weakens a claim | Minor>"):
        assert s in text, s
    for rule in MEASUREMENT_RULES:
        assert rule in text, rule


def test_measurement_agent_never_asks_degree_to_control_for_degree():
    text = _agent("network-measurement.md")
    assert "Never ask a paper whose variable is degree to control for degree." in text
    assert "Constraint can exceed 1; never treat a value above 1 as an error." in text
    assert "for any tie weights it is at least 1/n" in text
    assert "field's convention" not in text
    assert ("Treat a stated window as conventional when the paper cites earlier studies that use the same "
            "length or decay rule") in text


def test_measurement_agent_checks_every_interpreted_statistic():
    text = _agent("network-measurement.md")
    assert "Check every network statistic the paper interprets, not only the variables listed in the fingerprint" in text
    assert "### Stage 1 flags that enter a model" in text


def test_measurement_agent_reads_response_shares_without_a_threshold():
    text = _agent("network-measurement.md")
    assert "Name no response-rate threshold" in text and "Only pairs where both responded are fully observed." in text
    assert "{WORKSPACE}/stage-1/dropped_flags.md" in text and "If the file is missing, no flag was dropped." in text
    assert "map it to that flag's `Record:` line" in text
    assert ("When `survey` is in `run.json` `packs`, leave to the survey pack (check S10) whether the frame, "
            "contacts, responses, and response rate are reported and add up") in text


# --- Task 6: the inference agent, coverage, and the lessons ---

AGENTS = ("network-numbers.md", "network-measurement.md", "network-inference.md")


def test_inference_agent():
    assert packs.load_pack(PACK).slots.get("diagnose") == ["network-measurement.md", "network-inference.md"]
    text = _agent("network-inference.md")
    assert "stage-4/network_inference.md" in text and "Its first line is exactly `Pack: network`." in text
    for c in ("G10", "G11", "G12", "G13", "G15"):
        assert re.search(rf"^### {c}\. ", text, re.M), c
    for s in ("Excerpt:", "Page:", "## Checked and fine", "Severity: <Undermines the main claim | Weakens a claim | Minor>",
              "up to 3 web fetches in this run"):
        assert s in text, s
    for rule in INFERENCE_RULES:
        assert rule in text, rule


def test_inference_agent_g10_undermines_only_on_the_papers_own_compliant_estimate():
    text = _agent("network-inference.md")
    assert "look for the paper's own estimate of the headline with errors that meet G10" in text
    assert "Set no cutoff on the printed t" in text and "2.6" not in text
    assert ("When the number of actors in a model could be small, ask for it, since dyadic-robust errors with few "
            "actors are unreliable (Aronow, Samii, and Assenova 2015); name no cutoff.") in text
    assert ("Call that estimate not significant only when no rounding of its printed digits" in text
            and "read a directional hypothesis whose tails the paper does not state as one-tailed" in text)
    assert "map it to that flag's `Record:` line" in text


def test_inference_agent_g10_accepts_two_way_clustering_in_two_mode_dyads():
    text = _agent("network-inference.md")
    assert ("In two-mode dyads (investor and startup, director and board, inventor and firm), no actor can appear in "
            "both positions, and two-way clustering on the two members meets G10.") in text
    assert "clustering by dyad alone" in text


def test_inference_agent_g13_wording_test():
    text = _agent("network-inference.md")
    assert "Apply the G13 wording test first." in text and RULES[0] in text
    assert "A timing test counts only when it shows that future partner adoption does not predict current adoption" in text


def test_inference_agent_g15_skips_with_archival_and_hands_off_instruments():
    text = _agent("network-inference.md")
    assert "Skip this check when `archival` is in `run.json` `packs`" in text
    assert "belong to the IV checks" in text and "If the file is missing, assume no other pack runs and run G15." in text
    assert ("when `archival` is not in `run.json` `packs`, or the `Designs:` line (as corrected in `brief.md`) does not list IV, say in one line that they were not assessed") in text


def test_agents_leave_shift_rules_to_the_compiler():
    for name in AGENTS:
        assert SHIFT not in _agent(name), name
    assert "never apply it yourself" in _agent("network-inference.md")


def test_every_check_is_owned_by_one_agent():
    owners = {}
    for a in AGENTS:
        for c in re.findall(r"^### (G\d+)\. ", _agent(a), re.M):
            assert c not in owners, c
            owners[c] = a
    assert sorted(owners, key=lambda c: int(c[1:])) == IDS


@pytest.mark.parametrize("name", AGENTS)
def test_agents_follow_the_lessons(name):
    text = _agent(name)
    front = text.split("---", 2)[1]
    for key in ("name:", "description:", "maxTurns:"):
        assert key in front, key
    assert "skills/review/shared/contracts.md" in text
    assert ("Cite one in your output only if you fetched it in this run; otherwise state the concern "
            "without the citation.") in text
    assert "The orchestrator will provide `PDF_PATH`, `PAGE_COUNT`, " in text
    assert "two-mode projected to one mode" in text and "whole-network model (ERGM" in text
    assert "\u2014" not in text


def test_inference_agent_carry_notes_and_safeguards():
    text = _agent("network-inference.md")
    assert "Bramoulle, Djebbari, and Fortin 2009" in text
    assert "moves to \"Weakens a claim\" at most" in text
    assert "double semi-partialling (Dekker, Krackhardt, and Snijders 2007)" in text
    assert 'write that as a note under "Checked and fine", never as an issue' in text
    assert "counted from 1" in text and "skip the other reasons of that flagged result" in text
    assert "If the file is missing, say so under \"Checked and fine\" and work from the PDF." in text


# --- Task 7: notes to other agents ---

NOTE_TARGETS = {"face-validity.md", "completeness.md", "packs/archival/agents/methods-checks.md",
                "packs/archival/agents/adversarial-dgp.md", "packs/archival/agents/design-checks.md",
                "packs/inference/agents/inference-dependence.md", "packs/inference/agents/inference-claims.md",
                "packs/nonlinear/agents/nonlinear-numbers.md", "packs/nonlinear/agents/nonlinear-claims.md"}
STRUCTURAL = ("In ERGM, TERGM, SAOM, relational event, and latent space models, terms computed from the network "
              "being modeled (triangles, shared partners, reciprocity, degree terms) are how the model represents "
              "dependence; do not treat them as measurement tautology, bad controls, or reverse causality.")


def _notes():
    return packs.load_pack(PACK).core_notes


def test_notes_go_to_the_agents_the_spec_names():
    notes = _notes()
    assert set(notes) == NOTE_TARGETS and all(len(v) == 1 for v in notes.values())
    iv = notes["packs/archival/agents/design-checks.md"][0]
    assert "G13" in iv and "IV15" in iv and "exogenous" in iv
    assert "G10 and G12" in notes["packs/inference/agents/inference-dependence.md"][0]
    dep = notes["packs/inference/agents/inference-dependence.md"][0]
    assert ("skip I3, I5, and I8, and skip I1 except when the treatment or key regressor varies at the level of an "
            "actor or above (for example a firm-level, country-level, region-level, or industry-level treatment); "
            "then I1 and I4 apply, counting clusters and treated groups at that level") in dep
    assert "skip I1 and I4" not in dep and "I7, I9, and I10 still apply" in dep
    methods = notes["packs/archival/agents/methods-checks.md"][0]
    assert ("except when the treatment or key regressor varies at the level of an actor or above (for example a "
            "firm-level, country-level, region-level, or industry-level treatment); then CHECK 5 applies, counting "
            "clusters at that level") in methods
    assert notes["packs/nonlinear/agents/nonlinear-numbers.md"][0] == (
        "In a tie-formation model with sampled non-ties, the sample mean of the outcome is not the base rate; make no "
        "odds_ratio record unless the paper reports the population rate.")
    assert notes["packs/nonlinear/agents/nonlinear-claims.md"][0] == (
        "In a tie-formation model with sampled non-ties, ask for predicted outcomes on the probability scale only "
        "after reweighting or a prior correction; the network pack's G11 owns the sampling. "
        "In N9, do not read an odds ratio at the sample mean of a sample with sampled non-ties.")
    for target in NOTE_TARGETS:
        if target.startswith("packs/"):
            assert (ROOT / target).is_file(), target
    assert "in every check" not in dep.split("ERGM", 1)[0]
    claims = notes["packs/inference/agents/inference-claims.md"][0]
    assert "In I12" in claims and "G10" in claims and "keep I11 and I13 to I16" in claims


def test_notes_read_the_fingerprint_and_never_run_json():
    notes = _notes()
    for target, texts in notes.items():
        assert all("run.json" not in t for t in texts), target
    for target in ("face-validity.md", "packs/archival/agents/methods-checks.md",
                   "packs/archival/agents/adversarial-dgp.md", "packs/inference/agents/inference-dependence.md"):
        assert "`{WORKSPACE}/stage-0/fingerprint.md`" in notes[target][0], target
        assert "as corrected in `{WORKSPACE}/brief.md` (section 'User corrections')" in notes[target][0], target


def test_structural_terms_note_reaches_methods_checks_and_adversarial_dgp():
    notes = _notes()
    methods = notes["packs/archival/agents/methods-checks.md"][0]
    adversarial = notes["packs/archival/agents/adversarial-dgp.md"][0]
    assert STRUCTURAL in methods and STRUCTURAL in adversarial
    assert "prior status, prior ties, shared educational or employment affiliations" in adversarial
    assert "Keep clustering checks" not in methods
    assert "CHECK 6 and CHECK 7 stay yours for those models" in methods


def _run(names, overlays, primary):
    return {"packs": names, "overlays": overlays, "types_without_pack": [], "primary_pack": primary}


def test_archival_notes_apply_only_when_archival_runs():
    built = packs.load_all(ROOT / "packs")
    both = packs.core_adjust(built, _run(["archival", "network"], ["network"], "archival"))["notes"]
    assert any(n["pack"] == "network" and n["role"] == "overlay"
               for n in both["packs/archival/agents/methods-checks.md"])
    alone = packs.core_adjust(built, _run(["network"], ["network"], None))["notes"]
    assert not [k for k in alone if k.startswith(("packs/archival/", "packs/inference/", "packs/nonlinear/"))]
    assert any(n["pack"] == "network" for n in alone["face-validity.md"])


def test_network_turns_nothing_off():
    built = packs.load_all(ROOT / "packs")
    assert built["network"].turns_off == []
    adjust = packs.core_adjust(built, _run(["network"], ["network"], None))
    assert adjust["off"] == {} and adjust["read_lines"]["network"] == ["Network design:", "Network variables:"]
    # The inference pack gates on `packs` and the survey pack on `overlays`; a chosen overlay is in both.
    chosen = packs.run_packs(built, ["survey"], ["network"])
    assert "network" in chosen["packs"] and "network" in chosen["overlays"]


# --- Task 9: README and repo spec ---

WORDS = ["Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve",
         "Thirteen", "Fourteen", "Fifteen"]


def test_readme_and_spec_name_the_network_overlay():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "- **Network** is an overlay." in readme
    assert readme.index("- **Market event** is an overlay.") < readme.index("- **Network** is an overlay.")
    section = readme.split("## Packs", 1)[1].split("\n## ", 1)[0]
    bullets = len(re.findall(r"^- \*\*", section, re.M))
    assert f"A pack adds checks for one kind of paper. {WORDS[bullets]} are built." in readme
    spec = (ROOT / "docs" / "spec.md").read_text(encoding="utf-8")
    assert "market-event (abnormal stock returns around announcements), network, configurational, and framing" in spec
