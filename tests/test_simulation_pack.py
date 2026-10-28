from __future__ import annotations
import re
from pathlib import Path

import pytest
import yaml

from plumb import packs

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "review"
PACK = ROOT / "packs" / "simulation"
IDS = [f"K{i}" for i in range(1, 16)]
FAMILIES = ("NK landscape", "March-style learning", "other agent-based", "system dynamics", "LLM agents")
SCOPES = ("inside the model", "general proposition", "quantitative or prescriptive")


# --- Task 3: the fingerprint lines ---

def test_fingerprint_template_has_the_simulation_lines():
    text = (SKILL / "agents" / "manuscript-audit.md").read_text(encoding="utf-8")
    template = text.split("\n# Fingerprint\n", 1)[1].split("```", 1)[0]
    assert ('Simulation model: <family>; extends: <named model and year, or "none">; '
            "code: <link given | on request | none stated>") in template
    assert ("Simulation results:\n- <headline result in one line>; page <n>; claim scope: "
            "<inside the model | general proposition | quantitative or prescriptive>") in template


def test_fingerprint_defines_family_headline_and_claim_scope():
    text = (SKILL / "agents" / "manuscript-audit.md").read_text(encoding="utf-8")
    assert "only when the paper type or second paper type is simulation" in text
    for fam in FAMILIES:
        assert fam in text, fam
    for scope in SCOPES:
        assert f"- {scope}: " in text, scope
    assert "in the introduction's summary of findings, or as a numbered proposition" in text
    assert "Results derived by hand (equilibria, proofs, analytic comparative statics) are not simulation results." in text
    assert ("Tests, p-values, and significance marks computed across simulation runs, including regressions of "
            "simulated outcomes on model parameters, are not estimates from data: do not list them under "
            "`Inference:` or `Nonlinear terms:`.") in text


# --- Task 5: the pack's frame ---

CHECKLIST = {
    "K1": "The model can be reimplemented from the paper and its appendix: entities and their state variables, scales, initialization, every decision rule or submodel, the order and timing of updates (all at once or one at a time, fixed or random order), tie-breaking, and the stopping rule are stated in text, pseudo-code, or an ODD-style description; for LLM agents, prompts and memory rules count as decision rules",
    "K2": "The simulation code, with the seeds or configuration files that produce the reported results, is public or deposited with the submission; \"available on request\" does not meet this",
    "K3": "The number of runs per condition, the number of periods, and the stopping rule are stated and justified (for example by the stability of the outcome's variance across runs or by convergence), not set by habit",
    "K4": "Run-to-run uncertainty (standard deviation, standard error, or bands across runs) is reported for every compared outcome, and each difference the text calls meaningful is larger than that uncertainty",
    "K5": "No claim rests on significance tests or stars computed across simulation runs, whose number the authors choose; the size of each difference is reported in the outcome's units or as a standardized effect",
    "K6": "The parameter values behind the headline results are justified, and each claim is bounded to the parameter region where the paper's own results show it holds",
    "K7": "Sensitivity analysis varies the parameters the result plausibly depends on, jointly where interactions could matter, and does not rest on one-at-a-time sweeps around a single baseline",
    "K8": "The model is verified before it is used: it reproduces the known behavior of the model it extends, analytical limits, or extreme-value cases, and intermediate variables are tracked to show the code does what the text says",
    "K9": "When the paper extends a named published model, its base case agrees with the original's published results, or the paper explains the difference",
    "K10": "For NK and other landscape models: N, K, how interactions are assigned (adjacent, random, block, or other), how fitness contributions are drawn and combined, the number of landscapes, the search rule, and starting positions are stated",
    "K11": "The paper shows which model element produces each headline result, by switching the element off, tracking intermediate variables, or tracing runs, and rules out artifacts of update order, initialization, and run length",
    "K12": "No headline result is built in: the compared conditions differ only in the element the paper names, and no stated assumption grants the result directly",
    "K13": "Validation matches the claim: calibrated magnitudes, numerical thresholds, and prescriptions are tied to calibration, stylized facts, or data; general propositions offered without testing are grounded in stylized facts; claims kept inside the model need neither",
    "K14": "For simulations whose agents are LLMs, validation is tied to the mechanism and to empirical patterns, not to how realistic the agents' transcripts read",
    "K15": "When LLM agents produce a known collective pattern (a convention, a canonical game outcome, a published finding), the paper rules out that the model recalls it from training, for example by disguising the task or using material the model cannot have seen",
}
JUDGMENT = {"K7", "K11", "K12", "K13", "K14", "K15"}
EXTERNAL = {"K9"}
OTHER_PACK_NOTES = ("packs/inference/agents/inference-numbers.md", "packs/inference/agents/inference-dependence.md",
                    "packs/inference/agents/inference-claims.md", "packs/archival/agents/methods-checks.md",
                    "packs/computational/agents/measurement-validity.md")
NOTED = {"construction-ledger-producer.md", "face-validity.md", "formal-model.md", "completeness.md",
         "boundary-conditions.md", "contribution-auditor.md", "stage-4-compiler"} | set(OTHER_PACK_NOTES)
INFERENCE_NOTE = ("Tests, p-values, significance marks, and intervals computed across simulation runs, including "
                  "regressions of simulated outcomes on model parameters, belong to the simulation pack (K4 and K5): "
                  "skip them in every check. Keep every estimate the paper computes from data.")
SEVERITIES = ("Undermines the main claim", "Weakens a claim", "Minor")


def _expected():
    return yaml.safe_load((PACK / "fixtures" / "planted-1" / "expected.yaml").read_text(encoding="utf-8"))


def test_simulation_pack_loads_as_a_type_pack():
    p = packs.load_pack(PACK)
    assert p.name == "simulation" and p.overlay is False
    assert [i["id"] for i in p.checklist] == IDS


def test_checklist_matches_the_spec():
    items = {i["id"]: i for i in packs.load_pack(PACK).checklist}
    for k in IDS:
        assert items[k]["text"] == CHECKLIST[k], k
        want = "judgment" if k in JUDGMENT else ("external" if k in EXTERNAL else "paper")
        assert items[k]["adjudication"] == want, k


def test_severity_rules():
    rules = packs.load_pack(PACK).severity_rules
    assert len(rules) == 10
    owners = ["K4 (simulation-claims)", "K6 (simulation-claims)", "K9 (model-specification)",
              "K8 (model-specification)", "K1, K10, K2, K3 (model-specification)", "K5 (simulation-claims)",
              "K13 and K14 (simulation-claims)", "K12 (model-mechanism)", "K7, K11, K15",
              "Every other simulation finding"]
    for rule, owner in zip(rules, owners):
        assert rule.startswith(owner), owner
    assert "independent draws" in rules[0] and "report the uncertainty of the difference" in rules[0]
    assert "bound the claim" in rules[1] and "N = 10 to 16" in rules[1]
    assert "two or more reported values" in rules[3]
    assert "require code at submission" in rules[4] and "on its own" in rules[4]
    assert "'quantitative or prescriptive'" in rules[6] and "proposition for later testing" in rules[6]
    assert "finds no run that equalizes it" in rules[7]
    assert "(figure only) is 'Weakens a claim'" in rules[0] and "Without a cited convention" in rules[1]
    assert all("down one level" not in r and "downgrade" not in r for r in rules)


def test_turns_off_setting_and_timeline_research_with_reasons():
    p = packs.load_pack(PACK)
    assert [e["agent"] for e in p.turns_off] == ["setting-research.md", "timeline-research.md"]
    assert all(e["reason"] for e in p.turns_off)


def test_core_notes_target_the_agents_the_spec_names():
    notes = packs.load_pack(PACK).core_notes
    assert set(notes) == NOTED
    assert "Skip Steps 1 to 6" in notes["face-validity.md"][0] and "Do Step 7" in notes["face-validity.md"][0]
    assert "derives by hand" in notes["formal-model.md"][0]
    assert "K13, K2, and K1" in notes["completeness.md"][0]
    assert "K6" in notes["boundary-conditions.md"][0]
    assert "stage-2/reference_model.md" in notes["contribution-auditor.md"][0]
    assert "face-validity Step 7" in notes["stage-4-compiler"][0] and "K12" in notes["stage-4-compiler"][0]


def test_notes_leave_simulated_results_to_this_pack_and_keep_the_rest():
    notes = packs.load_pack(PACK).core_notes
    for key in OTHER_PACK_NOTES[:3]:
        assert notes[key] == [INFERENCE_NOTE], key
    assert "only to estimates the paper computes from data" in notes["packs/archival/agents/methods-checks.md"][0]
    mv = notes["packs/computational/agents/measurement-validity.md"][0]
    assert "(K14 and K15)" in mv and "Keep C14" in mv
    for key in ("face-validity.md", "completeness.md", "construction-ledger-producer.md"):
        assert "from data" in notes[key][0], key
    run = {"packs": ["archival", "simulation"], "overlays": [], "types_without_pack": [], "primary_pack": "archival"}
    adj = packs.core_adjust(packs.load_all(ROOT / "packs"), run)
    assert any(n["pack"] == "simulation" and n["role"] == "second type"
               for n in adj["notes"]["packs/archival/agents/methods-checks.md"])
    assert not any(n["pack"] == "simulation" for n in adj["notes"].get("packs/inference/agents/inference-claims.md", []))


def test_checklist_is_marked_unfrozen_until_the_editorial_is_read():
    meta = yaml.safe_load((PACK / "pack.yaml").read_text(encoding="utf-8"))
    assert meta["unfrozen"] is True and "Wibbens and Kretschmer (2026)" in meta["unfrozen_note"]
    assert (PACK / "checklists" / "simulation.yaml").read_text(encoding="utf-8").startswith("# Unfrozen:")


def test_ledger_note_values_pass_the_gate_enums():
    import importlib.util
    spec = importlib.util.spec_from_file_location("vcl", SKILL / "scripts" / "verify_construction_ledger.py")
    vcl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vcl)
    note = packs.load_pack(PACK).core_notes["construction-ledger-producer.md"][0]
    roles = set(re.findall(r"as role `([^`]+)`|as `([^`]+)`", note))
    roles = {a or b for a, b in roles}
    assert roles == {"treatment", "DV", "control"} and roles <= vcl.ROLE_ENUM
    levels = {"individual", "firm", "other"}
    for lvl in levels:
        assert f"`{lvl}`" in note, lvl
    assert levels <= vcl.LEVEL_ENUM
    assert "`simulated: <model family>`" in note
    assert "`time-varying`" in note and "`time-invariant`" in note
    assert "Do not set `no_entries_reason`" in note


def test_read_checkin_shows_the_simulation_results():
    assert packs.load_pack(PACK).read_checkin_lines == ["Simulation results:"]


@pytest.mark.parametrize("run,off", [
    ({"packs": ["simulation"], "overlays": [], "types_without_pack": [], "primary_pack": "simulation"},
     {"setting-research.md", "timeline-research.md"}),
    ({"packs": ["simulation", "archival"], "overlays": [], "types_without_pack": [], "primary_pack": "simulation"},
     set()),
    ({"packs": ["simulation", "computational"], "overlays": ["computational"], "types_without_pack": [],
      "primary_pack": "simulation"}, {"setting-research.md", "timeline-research.md"}),
])
def test_core_adjust_serves_the_simulation_pack(run, off):
    adj = packs.core_adjust(packs.load_all(ROOT / "packs"), run)
    assert set(adj["off"]) == off
    assert adj["read_lines"]["simulation"] == ["Simulation results:"]
    for target in ("construction-ledger-producer.md", "construction-ledger-checker.md", "face-validity.md"):
        assert any(n["pack"] == "simulation" and n["role"] == "primary type" for n in adj["notes"][target]), target


def test_fixture_is_labeled_synthetic():
    exp = _expected()
    assert exp["synthetic"] is True and exp["owner"] == "blind-agent"
    assert exp["label"] == "SYNTHETIC TEST PAPER, NOT REAL RESEARCH"
    assert exp["status"] in ("pending_planting", "ready")
    for key in ("must_catch", "must_not_flag", "also_fair"):
        for item in exp.get(key) or []:
            assert {"check", "page", "locator", "note"} <= set(item), item
    for key in ("must_catch", "must_not_flag"):
        for item in exp.get(key) or []:
            assert item["check"] in IDS, item
    for item in exp.get("must_catch") or []:
        assert item.get("severity") in SEVERITIES, item
    plants = {(i["check"], str(i["page"]), i["locator"]) for i in exp.get("must_catch") or []}
    for d in exp.get("must_not_flag") or []:
        assert (d["check"], str(d["page"]), d["locator"]) not in plants, d


# --- Tasks 6 to 10: the agents ---

AGENTS = ["simulation-numbers.md", "reference-model.md", "model-mechanism.md", "model-specification.md",
          "simulation-claims.md"]
DEFS = """Definitions, for when you read the fingerprint or build it yourself:

- Family: NK landscape, March-style learning, other agent-based, system dynamics, LLM agents, or other.
- Headline result: a result stated in the abstract, in the introduction's summary of findings, or as a numbered proposition.
- Claim scope: "inside the model" (the paper states the result as a property of the model); "general proposition" (a directional claim about organizations, managers, or teams, including one offered for later empirical testing); "quantitative or prescriptive" (a calibrated magnitude, a numerical threshold, or advice to managers)."""
DEFER = ("When `computational` is in `run.json` `packs`, leave prompt and model disclosure, prompt and model "
         "sensitivity, training cutoffs, and individual-level fidelity of LLM agents to that pack's C3, C4, C5, "
         "and C14, and do not flag them.")
ABSENCE = ("Flag an absence only after searching the methods section, the appendices, the footnotes, "
           "and every table and figure note, and name where you looked.")
TEMPLATE_LINES = ("Unit: <headline result or model element>. Tag: [paper | external | judgment]",
                  "Paper's best case: <one sentence>",
                  'Excerpt: "<one sentence copied word for word from the paper where the problem shows>"',
                  "Page: <the page the paper prints there; for something missing, the page of the section where it belongs>",
                  "Severity: <Undermines the main claim | Weakens a claim | Minor>",
                  "## Checked and fine")


def _agent(name):
    return (PACK / "agents" / name).read_text(encoding="utf-8")


def _follows_the_lessons(name):
    text = _agent(name)
    front = text.split("---", 2)[1]
    for key in ("name:", "description:", "maxTurns:"):
        assert key in front, (name, key)
    assert "skills/review/shared/contracts.md" in text, name
    assert ("The works named in this file are background for you. Cite one in your output only if you fetched "
            "it in this run; otherwise state the concern without the citation.") in text, name
    assert "The orchestrator will provide `PDF_PATH`, `PAGE_COUNT`" in text, name
    assert 'If either says "none" or is missing' in text, name
    assert DEFS in text, name
    assert "Reply to the orchestrator in one sentence that names" in text, name
    assert "\u2014" not in text, name
    assert not re.search(r"(cat|echo|printf|tee)[^\n`]*>", text), name
    return text


def _severity_copy(text, indices):
    rules = packs.load_pack(PACK).severity_rules
    for i in indices:
        assert f"- {rules[i]}" in text, i


def test_numbers_agent():
    assert packs.load_pack(PACK).slots.get("verify") == ["simulation-numbers.md"]
    text = _follows_the_lessons("simulation-numbers.md")
    for s in ("stage-1/simulation_numbers.md", "## Experiments", "## Comparisons", "## Flags", "## Not computed",
              "Quick", "Record: <id, or \"none\">. Table: <label, or \"none\">. Cells: <table:row:col, ...>.",
              "Never read a value off a plot.", "`inside_noise`", "`independence_unstated`", "`runs_for_p05`",
              "the core arithmetic check does that"):
        assert s in text, s
    for field in ("`spread_of`", "`common_random_numbers`", "`claim`", "`spread_kind`"):
        assert field in text, field
    assert "`no` only when the paper says each condition draws its own landscapes or seeds" in text
    assert "Copy `mean` and `spread` as strings exactly as the paper prints them" in text


def test_numbers_agent_runs_the_script_with_its_own_tools():
    text = _agent("simulation-numbers.md")
    assert "tools: [Read, Write, Bash, Glob]" in text.split("---", 2)[1]
    assert "The orchestrator will provide `PDF_PATH`, `PAGE_COUNT`, `{WORKSPACE}`, and `{PLUGIN}`." in text
    assert ("`python3 {PLUGIN}/packs/simulation/scripts/run_noise.py "
            "{WORKSPACE}/stage-1/simulation_noise_input.json`") in text
    assert "with the file-writing tool" in text
    assert (PACK / "scripts" / "run_noise.py").exists()


def test_reference_model_agent():
    assert packs.load_pack(PACK).slots.get("context") == ["reference-model.md"]
    text = _follows_the_lessons("reference-model.md")
    for s in ("stage-2/reference_model.md", "## Reference model", "## Model-family literature",
              "## Stylized facts and calibration sources", "## Journal code policy", "## Could not establish",
              "skills/review/shared/research-protocol.md", "no reference model named", "verbatim quote"):
        assert s in text, s
    assert "Search budget: about 15 searches at Standard depth, 25-35 at Deep. Read `depth` from `run.json`." in text
    assert "When `run.json` has `search_before`, cap searches at that date" in text
    assert "author guidelines" in text and "profiles/" not in text


def test_model_mechanism_agent():
    p = packs.load_pack(PACK)
    assert p.slots.get("theory") == ["model-mechanism.md"]
    text = _follows_the_lessons("model-mechanism.md")
    assert DEFER in text and ABSENCE in text
    for c in ("K11", "K12"):
        assert re.search(rf"^### {c}\. ", text, re.M), c
    for s in ("`{WORKSPACE}/stage-3/model_mechanism.md`", "`{WORKSPACE}/stage-4/model_mechanism_issues.md`",
              "## Discrimination table", "Ruled out, Partially addressed, or Not addressed",
              "## Differences between compared conditions", "names both files",
              "they are not rival theories", "Never cite prior work as the reason for a K12 issue",
              "stage-3/theory_devil_report.md", "rewrite both files"):
        assert s in text, s
    for line in TEMPLATE_LINES:
        assert line in text, line
    assert "```markdown\nPack: simulation\n" in text
    _severity_copy(text, [7, 8])


def test_model_specification_agent():
    p = packs.load_pack(PACK)
    assert p.slots.get("diagnose", [])[:1] == ["model-specification.md"]
    text = _follows_the_lessons("model-specification.md")
    assert DEFER in text and ABSENCE in text
    for c in ("K1", "K2", "K3", "K8", "K9", "K10"):
        assert re.search(rf"^### {c}\. ", text, re.M), c
    for s in ("`{WORKSPACE}/stage-4/model_specification.md`", "{WORKSPACE}/stage-1/dropped_flags.md",
              "If the file is missing, no flag was dropped.", "never flag its absence",
              "map it to that flag's `Record:` line",
              "K = 0 and continuous fitness draws has exactly one peak"):
        assert s in text, s
    for line in TEMPLATE_LINES:
        assert line in text, line
    assert "```markdown\nPack: simulation\n" in text
    _severity_copy(text, [2, 3, 4])


def test_k9_compares_like_for_like():
    spec = _agent("model-specification.md")
    assert "at the original model's parameter values" in spec
    assert "values the published results do not cover cannot be compared" in spec
    assert "and do not rate K9" in spec
    ref = _agent("reference-model.md")
    assert "the parameter values it holds at" in ref
    assert "<result> at <parameter values> per <URL>" in ref


def test_simulation_claims_agent():
    p = packs.load_pack(PACK)
    assert p.slots.get("diagnose") == ["model-specification.md", "simulation-claims.md"]
    text = _follows_the_lessons("simulation-claims.md")
    assert DEFER in text and ABSENCE in text
    for c in ("K4", "K5", "K6", "K7", "K13", "K14", "K15"):
        assert re.search(rf"^### {c}\. ", text, re.M), c
    for s in ("`{WORKSPACE}/stage-4/simulation_claims.md`", "{WORKSPACE}/stage-1/dropped_flags.md",
              "`independence_unstated`", "figure only", "tagged judgment and rated at most 'Weakens a claim'",
              "A claim covers the region its wording names", "the two are independent",
              "this check is for patterns that emerge among interacting agents", "stage-3/boundaries.md",
              "map it to that flag's `Record:` line"):
        assert s in text, s
    for scope in SCOPES:
        assert scope in text, scope
    for line in TEMPLATE_LINES:
        assert line in text, line
    assert "```markdown\nPack: simulation\n" in text
    _severity_copy(text, [0, 1, 5, 6, 8])


def test_every_check_is_owned_by_exactly_one_agent_heading():
    owners = {}
    for a in AGENTS:
        for k in re.findall(r"^### (K\d+)\. ", _agent(a), re.M):
            owners.setdefault(k, []).append(a)
    assert sorted(owners, key=lambda k: int(k[1:])) == IDS
    assert all(len(v) == 1 for v in owners.values()), owners


def test_every_severity_rule_is_applied_by_one_agent():
    rules = packs.load_pack(PACK).severity_rules
    shared = {8: ["model-mechanism.md", "simulation-claims.md"]}
    for i, rule in enumerate(rules):
        holders = [a for a in AGENTS if f"- {rule}" in _agent(a)]
        assert holders == shared.get(i, holders) and len(holders) == len(shared.get(i, [0])), (i, holders)


def test_k4_rests_on_script_se():
    claims = _agent("simulation-claims.md")
    assert "settled by the script's `inside_noise` flag, never by eye" in claims
    assert "carries neither the flag nor the status `independence_unstated` is not a K4 issue" in claims
    assert "When the paper itself reports an interval for the difference of a headline result" in claims
    assert "For a comparison with no row in that table, when a figure prints bands" in claims


# --- Task 12: README and repo spec ---

def test_readme_and_spec_name_the_simulation_pack():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "- **Simulation** runs when you choose the simulation paper type" in readme
    assert readme.index("- **Network** is an overlay.") < readme.index("- **Simulation** runs when")
    assert len(re.findall(r"A pack adds checks for one kind of paper\. \w+ are built\.", readme)) == 1
    spec = (ROOT / "docs" / "spec.md").read_text(encoding="utf-8")
    assert "The simulation pack is a type pack for papers whose results come from running a simulation model" in spec


# --- Final fix wave A ---

LENIENT = "an independence_unstated status with inside_noise_if_independent true"


def test_nonlinear_terms_leave_out_results_across_simulation_runs():
    text = (SKILL / "agents" / "manuscript-audit.md").read_text(encoding="utf-8")
    para = text.split("Under `Nonlinear terms:`, list", 1)[1].split("\n\n", 1)[0]
    assert ("For a simulation paper, do not list a curve over a model parameter (such as an inverted U), a "
            "difference in a simulated effect across conditions, or a squared or product term in a regression "
            "across simulation runs; the simulation pack checks them.") in para


def test_k3_escalation_keys_on_inside_noise_if_independent():
    rules = packs.load_pack(PACK).severity_rules
    assert LENIENT in rules[4] and "a K4 flag (the script's inside_noise)" in rules[4]
    assert "noise flag" not in rules[4]
    spec = _agent("model-specification.md")
    k3 = spec.split("### K3. ", 1)[1].split("\n### ", 1)[0]
    assert "a K4 flag (the script's `inside_noise`)" in k3 and "`inside_noise_if_independent` true" in k3
    assert "noise flag" not in spec


def test_k4_unstated_independence_is_an_issue_only_inside_the_lenient_noise():
    claims = _agent("simulation-claims.md")
    k4 = claims.split("### K4. ", 1)[1].split("\n### ", 1)[0]
    assert ("A headline comparison with status `independence_unstated` is an issue only when its "
            "`inside_noise_if_independent` is true") in k4
    assert "When `inside_noise_if_independent` is false or null, it is not a K4 issue" in k4
    assert "A headline comparison with status `independence_unstated` is an issue:" not in k4


def test_numbers_table_has_inside_noise_if_independent_and_note_columns():
    text = _agent("simulation-numbers.md")
    assert ("| Record | Where (page) | Outcome | Difference | 95% interval | Status | Inside noise if independent "
            "| Standardized | Runs for p < .05 | Runs used | Note | Independence quote |") in text
    assert "`inside_noise_if_independent`" in text and "into the Note column" in text


def test_k5_reported_sizes_draw_no_finding():
    claims = _agent("simulation-claims.md")
    k5 = claims.split("### K5. ", 1)[1].split("\n### ", 1)[0]
    assert ("A paper that reports an effect size or the run-to-run spread next to each test draws no K5 finding, "
            "not even a 'Minor', unless the text rests a claim's importance on the test") in k5


def test_unstated_parameter_values_are_not_compared():
    ref = _agent("reference-model.md")
    assert 'write "parameter values not stated"' in ref
    spec = _agent("model-specification.md")
    k9 = spec.split("### K9. ", 1)[1].split("\n### ", 1)[0]
    assert '"parameter values not stated"' in k9 and "cannot be compared" in k9


def test_ruled_out_candidates_do_not_escalate_k1_or_k10():
    rules = packs.load_pack(PACK).severity_rules
    assert "and does not rate it 'Ruled out'" in rules[4]
    k1 = _agent("model-specification.md").split("### K1. ", 1)[1].split("\n### ", 1)[0]
    assert "and does not rate 'Ruled out'" in k1


def test_k2_wording_follows_the_rule():
    k2 = _agent("model-specification.md").split("### K2. ", 1)[1].split("\n### ", 1)[0]
    assert "the K1 finding carries the 'Weakens a claim', not K2" in k2
    assert "higher rating" not in k2
