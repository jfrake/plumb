from __future__ import annotations
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from plumb import packs

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/review"
STAGES = {n: SKILL / "stages" / name for n, name in enumerate([
    "stage-0-intake.md", "stage-1-verify.md", "stage-2-understand.md", "stage-3-theory.md",
    "stage-4-diagnose.md", "stage-5-synthesize.md", "stage-6-audit.md", "stage-7-output.md"])}


def _step(text, n):
    return text.split(f"\n{n}. ", 1)[1].split(f"\n{n + 1}. ", 1)[0]


def _step_with(text, anchor):
    """The numbered step that contains anchor, found by its text, since a rebase may renumber steps."""
    steps = [s for s in re.split(r"\n(?=\d+\. )", text) if anchor in s]
    assert len(steps) == 1, (anchor, len(steps))
    return steps[0]


def _pack(tmp_path, body="", files=None, name="p"):
    d = tmp_path / name
    (d / "agents").mkdir(parents=True)
    (d / "checklists").mkdir()
    (d / "fixtures" / "f").mkdir(parents=True)
    (d / "agents" / "a.md").write_text("x")
    (d / "checklists" / "c.yaml").write_text("- {id: c1, text: t, adjudication: paper}\n")
    (d / "fixtures" / "f" / "expected.yaml").write_text("status: pending_planting\n")
    (d / "pack.yaml").write_text(f"name: {name}\ndetection_cues: [x]\nslots: {{diagnose: [a.md]}}\n" + body)
    for rel, text in (files or {}).items():
        f = d / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text)
    return d


# --- Task 1: the loader reads and checks the new pack.yaml fields ---

def test_turns_off_accepts_a_bare_string_and_a_mapping(tmp_path):
    d = _pack(tmp_path, "turns_off:\n  - timeline-research.md\n"
                        "  - {agent: setting-research.md, reason: \"No empirical setting.\"}\n")
    p = packs.load_pack(d)
    assert p.turns_off == [{"agent": "timeline-research.md", "reason": ""},
                           {"agent": "setting-research.md", "reason": "No empirical setting."}]


def test_core_notes_read_text_and_files(tmp_path):
    d = _pack(tmp_path, "core_notes:\n  face-validity.md:\n    - {text: \"Skip Step 5.\"}\n"
                        "    - {file: notes/fv.md}\n  stage-4-compiler: {text: \"Merge them.\"}\n",
              files={"notes/fv.md": "Benchmark only regression estimates.\n"})
    p = packs.load_pack(d)
    assert p.core_notes == {"face-validity.md": ["Skip Step 5.", "Benchmark only regression estimates."],
                            "stage-4-compiler": ["Merge them."]}


def test_read_checkin_lines_loads(tmp_path):
    d = _pack(tmp_path, "read_checkin_lines: [\"Studies:\", \"Theory form:\"]\n")
    assert packs.load_pack(d).read_checkin_lines == ["Studies:", "Theory form:"]


def test_built_packs_still_load():
    built = packs.load_all(ROOT / "packs")
    for name in ("archival", "computational"):
        assert built[name].turns_off == [] and built[name].core_notes == {}


def test_a_note_may_go_to_another_packs_agent(tmp_path):
    _pack(tmp_path, name="archival")
    d = _pack(tmp_path, "overlay: true\ncore_notes:\n  packs/archival/agents/a.md: {text: \"Leave ties to the network pack.\"}\n",
              name="network")
    assert packs.load_pack(d).core_notes == {"packs/archival/agents/a.md": ["Leave ties to the network pack."]}


BAD = [
    ("not-offable", "turns_off: [theory-logic.md]\n", {}, "a pack may turn off only"),
    ("no-md", "turns_off: [timeline-research]\n", {}, "did you mean 'timeline-research.md'"),
    ("bad-entry", "turns_off: [{agent: timeline-research.md, why: x}]\n", {}, "must be an agent file name"),
    ("overlay-off", "overlay: true\nturns_off: [timeline-research.md]\n", {}, "an overlay never turns"),
    ("notes-not-map", "core_notes: [face-validity.md]\n", {}, "core_notes must map"),
    ("unknown-target", "core_notes: {ghost.md: {text: x}}\n", {}, "is not a file in skills/review/agents/"),
    ("checker", "core_notes: {construction-ledger-checker.md: {text: x}}\n", {}, "ledger unit passes its notes"),
    ("stress-tester", "core_notes: {stress-tester.md: {text: x}}\n", {}, "note stress-test-prompt instead"),
    ("both", "core_notes: {face-validity.md: {text: x, file: notes/a.md}}\n", {"notes/a.md": "y"}, "exactly one"),
    ("missing-file", "core_notes: {face-validity.md: {file: notes/none.md}}\n", {}, "not found in the pack"),
    ("outside", "core_notes: {face-validity.md: {file: ../outside.md}}\n", {}, "not found in the pack"),
    ("empty-text", "core_notes: {face-validity.md: {text: \"  \"}}\n", {}, "text is empty"),
    ("read-lines", "read_checkin_lines: [Studies]\n", {}, "read_checkin_lines must be a list"),
    ("pack-agent-missing", "core_notes: {packs/archival/agents/ghost.md: {text: x}}\n", {},
     "names no agent file in the packs folder"),
]


@pytest.mark.parametrize("body,files,match", [b[1:] for b in BAD], ids=[b[0] for b in BAD])
def test_loader_rejects_bad_core_fields(tmp_path, body, files, match):
    (tmp_path / "outside.md").write_text("outside the pack")
    d = _pack(tmp_path, body, files)
    with pytest.raises(packs.PackError, match=match):
        packs.load_pack(d)


# --- Task 2: run_packs names the primary pack and maps "correlational" to archival ---

def _two():
    a = packs.Pack(name="archival", path=Path("."), detection_cues=[], slots={})
    m = packs.Pack(name="meta-analysis", path=Path("."), detection_cues=[], slots={})
    return {"archival": a, "meta-analysis": m}


def test_primary_pack_is_the_first_types_pack():
    r = packs.run_packs(_two(), ["meta-analysis", "archival"], [])
    assert r["primary_pack"] == "meta-analysis" and r["packs"] == ["meta-analysis", "archival"]


def test_primary_pack_is_null_when_the_first_type_has_no_pack():
    r = packs.run_packs(_two(), ["experiments", "meta-analysis"], [])
    assert r == {"packs": ["meta-analysis"], "overlays": [], "types_without_pack": ["experiments"],
                 "primary_pack": None}


def test_primary_pack_is_the_first_type_that_survives_a_blank():
    r = packs.run_packs(_two(), ["", "meta-analysis"], [])
    assert r["primary_pack"] == "meta-analysis"
    r = packs.run_packs(_two(), ["none", "experiments"], [])
    assert r["primary_pack"] is None


def test_correlational_maps_to_archival():
    r = packs.run_packs(_two(), ["Correlational", "archival"], [])
    assert r == {"packs": ["archival"], "overlays": [], "types_without_pack": [], "primary_pack": "archival"}


# --- Task 3: core_adjust, the stub files, and plumb core-adjust ---

THEORY_OFF = ("construction-ledger-producer.md", "setting-research.md", "timeline-research.md",
              "face-validity.md")
UNIT = ("construction-ledger-checker.md", "construction-claim-audit.md")


def _p(name, off=(), notes=None, overlay=False):
    return packs.Pack(name=name, path=Path("."), detection_cues=[], slots={}, overlay=overlay,
                      turns_off=[{"agent": a, "reason": "the paper has no data"} for a in off],
                      core_notes=notes or {})


BUILT = {
    "theory": _p("theory", THEORY_OFF),
    "archival": _p("archival"),
    "simulation": _p("simulation", ("setting-research.md", "timeline-research.md"),
                     {"construction-ledger-producer.md": ["Enter simulated parameters."],
                      "face-validity.md": ["Do Step 7 only."]}),
    "qualitative": _p("qualitative", notes={"theory-logic.md": ["Rivals are interpretations."],
                                            "stress-test-prompt": ["Judge by the paper's approach."]}),
    "computational": _p("computational", overlay=True),
    "network": _p("network", overlay=True, notes={"packs/archival/agents/methods-checks.md": ["Skip dyads."]}),
}
BUILT["computational"].read_checkin_lines = ["Generated variables:"]


def _run(names, overlays=(), missing=(), primary="first"):
    if primary == "first":
        primary = names[0] if names else None
    return {"packs": list(names), "overlays": list(overlays), "types_without_pack": list(missing),
            "primary_pack": primary}


def test_theory_alone_turns_off_four_agents_and_the_ledger_unit():
    off = packs.core_adjust(BUILT, _run(["theory"]))["off"]
    assert set(off) == set(THEORY_OFF) | set(UNIT)
    assert off["setting-research.md"]["stubs"] == ["stage-2/setting.md"]
    assert off["construction-ledger-checker.md"]["stubs"] == []
    assert off["construction-claim-audit.md"]["stubs"] == ["stage-5/construction_claim_audit.md"]


def test_theory_with_archival_turns_off_nothing():
    assert packs.core_adjust(BUILT, _run(["theory", "archival"]))["off"] == {}


def test_pack_less_type_blocks_every_turn_off():
    assert packs.core_adjust(BUILT, _run(["theory"], missing=["other"]))["off"] == {}


def test_overlays_never_count_for_or_against():
    off = packs.core_adjust(BUILT, _run(["theory", "computational"], overlays=["computational"]))["off"]
    assert set(off) == set(THEORY_OFF) | set(UNIT)
    assert packs.core_adjust(BUILT, _run(["computational"], overlays=["computational"], primary=None))["off"] == {}
    # computational chosen as the second paper type is still an overlay pack
    off = packs.core_adjust(BUILT, _run(["theory", "computational"]))["off"]
    assert set(off) == set(THEORY_OFF) | set(UNIT)


def test_two_type_packs_turn_off_only_what_both_list():
    off = packs.core_adjust(BUILT, _run(["theory", "simulation"]))["off"]
    assert set(off) == {"setting-research.md", "timeline-research.md"}


def test_notes_apply_whenever_the_pack_runs_and_carry_its_role():
    notes = packs.core_adjust(BUILT, _run(["archival", "qualitative"]))["notes"]
    assert notes["theory-logic.md"] == [{"pack": "qualitative", "role": "second type",
                                         "text": "Rivals are interpretations."}]
    notes = packs.core_adjust(BUILT, _run(["qualitative"], missing=["experiments"], primary=None))["notes"]
    assert notes["theory-logic.md"][0]["role"] == "second type"
    notes = packs.core_adjust(BUILT, _run(["qualitative"]))["notes"]
    assert notes["theory-logic.md"][0]["role"] == "primary type"


def test_a_note_to_another_packs_agent_needs_that_pack_in_the_run():
    run = _run(["archival", "network"], overlays=["network"])
    assert packs.core_adjust(BUILT, run)["notes"]["packs/archival/agents/methods-checks.md"][0]["pack"] == "network"
    run = _run(["theory", "network"], overlays=["network"])
    assert "packs/archival/agents/methods-checks.md" not in packs.core_adjust(BUILT, run)["notes"]


def test_read_lines_list_each_running_packs_labels():
    run = _run(["archival", "computational"], overlays=["computational"])
    assert packs.core_adjust(BUILT, run)["read_lines"] == {"computational": ["Generated variables:"]}


def test_read_lines_for_a_type_pack_with_no_overlays():
    run = _run(["computational"], overlays=[])
    assert packs.core_adjust(BUILT, run)["read_lines"] == {"computational": ["Generated variables:"]}


def test_ledger_notes_reach_the_checker():
    notes = packs.core_adjust(BUILT, _run(["simulation"]))["notes"]
    assert notes["construction-ledger-checker.md"] == notes["construction-ledger-producer.md"]
    assert notes["construction-ledger-checker.md"][0]["text"] == "Enter simulated parameters."


def test_notes_to_a_turned_off_agent_are_dropped():
    theory = _p("theory", THEORY_OFF, {"face-validity.md": ["x"], "theory-logic.md": ["y"]})
    notes = packs.core_adjust({"theory": theory}, _run(["theory"]))["notes"]
    assert "face-validity.md" not in notes and notes["theory-logic.md"][0]["text"] == "y"


def test_reason_names_the_pack():
    off = packs.core_adjust(BUILT, _run(["theory"]))["off"]
    assert off["timeline-research.md"]["reason"] == "Turned off by the theory pack: the paper has no data"
    bare = _p("experiments")
    bare.turns_off = [{"agent": "timeline-research.md", "reason": ""}]
    off = packs.core_adjust({"experiments": bare}, _run(["experiments"]))["off"]
    assert off["timeline-research.md"]["reason"] == "Turned off by the experiments pack"


def test_write_core_adjust_writes_stubs_and_the_stress_prompt(tmp_path):
    adjust = packs.core_adjust(BUILT, _run(["theory"]))
    written = packs.write_core_adjust(tmp_path, adjust)
    assert "stage-2/setting.md" in written and "stage-5/construction_claim_audit.md" in written
    assert (tmp_path / "stage-2/timeline.md").read_text().startswith("# Not run")
    assert not (tmp_path / "stage-2/construction_ledger.json").exists()
    assert not (tmp_path / "stage-6/stress_prompt.md").exists()
    adjust = packs.core_adjust(BUILT, _run(["qualitative"]))
    packs.write_core_adjust(tmp_path, adjust)
    prompt = (tmp_path / "stage-6/stress_prompt.md").read_text()
    assert prompt.startswith(packs.STRESS_PROMPT.read_text().rstrip()[:200])
    assert "Pack note (qualitative, primary type): Judge by the paper's approach." in prompt
    packs.write_core_adjust(tmp_path, packs.core_adjust(BUILT, _run(["archival"])))
    assert not (tmp_path / "stage-6/stress_prompt.md").exists()


def test_run_json_naming_an_unbuilt_pack_is_an_error():
    with pytest.raises(packs.PackError, match="not built"):
        packs.core_adjust(BUILT, _run(["survey"]))


def _cli(*args, home):
    env = dict(os.environ, PYTHONPATH=str(ROOT), HOME=str(home))
    return subprocess.run([sys.executable, "-m", "plumb", *args], capture_output=True, text=True,
                          cwd=ROOT, env=env)


def test_core_adjust_cli_writes_run_json_and_logs_once(tmp_path):
    root = tmp_path / "packs"
    root.mkdir()
    _pack(root, "turns_off:\n  - {agent: timeline-research.md, reason: researchers assigned the treatment}\n",
          name="experiments")
    ws = tmp_path / "ws"
    ws.mkdir()
    run_json = ws / "run.json"
    run_json.write_text(json.dumps({"depth": "standard", "packs": ["experiments"], "overlays": [],
                                    "types_without_pack": [], "primary_pack": "experiments"}))
    for _ in range(2):
        r = _cli("core-adjust", str(root), str(run_json), home=tmp_path)
        assert r.returncode == 0, r.stdout + r.stderr
    run = json.loads(run_json.read_text())
    assert run["depth"] == "standard"
    assert run["core_adjust"]["off"]["timeline-research.md"]["reason"] == (
        "Turned off by the experiments pack: researchers assigned the treatment")
    assert (ws / "stage-2/timeline.md").read_text().startswith("# Not run")
    events = [json.loads(x) for x in (ws / "audit/events.jsonl").read_text().splitlines()]
    deps = [e for e in events if e["kind"] == "dependency"]
    assert [e["name"] for e in deps] == ["core:timeline-research.md"]
    assert deps[0]["message"].startswith("Turned off by design: ")
    assert sum(1 for e in events if e.get("check") == "core_adjust") == 1


def test_an_archival_only_run_changes_nothing_but_one_event_and_the_designs_read_line(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    run_json = ws / "run.json"
    run_json.write_text(json.dumps({"packs": ["archival"], "overlays": [], "types_without_pack": [],
                                    "primary_pack": "archival"}))
    r = _cli("core-adjust", str(ROOT / "packs"), str(run_json), home=tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert json.loads(run_json.read_text())["core_adjust"] == {"off": {}, "notes": {},
                                                                "read_lines": {"archival": ["Designs:"]}}
    assert sorted(p.name for p in ws.iterdir()) == ["audit", "run.json"]
    events = (ws / "audit/events.jsonl").read_text().splitlines()
    assert len(events) == 1 and json.loads(events[0])["check"] == "core_adjust"


def test_core_adjust_cli_exit_1_on_a_bad_pack(tmp_path):
    root = tmp_path / "packs"
    root.mkdir()
    _pack(root, "turns_off: [theory-logic.md]\n", name="bad")
    run_json = tmp_path / "run.json"
    run_json.write_text(json.dumps({"packs": ["bad"]}))
    r = _cli("core-adjust", str(root), str(run_json), home=tmp_path)
    assert r.returncode == 1 and "a pack may turn off only" in r.stdout


# --- Fix round 1: never overwrite real outputs, clean up stale stubs ---

def test_a_real_output_is_never_overwritten_by_a_stub(tmp_path):
    (tmp_path / "stage-2").mkdir()
    real = tmp_path / "stage-2/timeline.md"
    real.write_text("# Timeline\nreal findings\n")
    written = packs.write_core_adjust(tmp_path, packs.core_adjust(BUILT, _run(["theory"])))
    assert real.read_text() == "# Timeline\nreal findings\n"
    assert "stage-2/timeline.md" not in written and "stage-2/setting.md" in written


def test_stale_stubs_are_removed_but_real_files_are_not(tmp_path):
    packs.write_core_adjust(tmp_path, packs.core_adjust(BUILT, _run(["theory"])))
    (tmp_path / "stage-2/setting.md").write_text("# Setting\nreal\n")
    packs.write_core_adjust(tmp_path, packs.core_adjust(BUILT, _run(["archival"])))
    assert not (tmp_path / "stage-2/timeline.md").exists()
    assert not (tmp_path / "stage-5/construction_claim_audit.md").exists()
    assert (tmp_path / "stage-2/setting.md").read_text() == "# Setting\nreal\n"


def test_cli_logs_a_dependency_only_for_newly_off_agents(tmp_path):
    root = tmp_path / "packs"
    root.mkdir()
    _pack(root, "turns_off:\n  - {agent: timeline-research.md, reason: r}\n", name="experiments")
    ws = tmp_path / "ws"
    ws.mkdir()
    run_json = ws / "run.json"
    base = {"packs": ["experiments"], "overlays": [], "types_without_pack": [], "primary_pack": "experiments"}
    run_json.write_text(json.dumps(base))
    assert _cli("core-adjust", str(root), str(run_json), home=tmp_path).returncode == 0
    run = json.loads(run_json.read_text())
    run["core_adjust"]["notes"] = {"x": []}  # force a changed result with the same off set
    run_json.write_text(json.dumps(run))
    assert _cli("core-adjust", str(root), str(run_json), home=tmp_path).returncode == 0
    events = [json.loads(x) for x in (ws / "audit/events.jsonl").read_text().splitlines()]
    assert sum(1 for e in events if e["kind"] == "dependency") == 1
    assert sum(1 for e in events if e.get("check") == "core_adjust") == 2


@pytest.mark.parametrize("body", ["[1, 2]", '{"packs": "archival"}', '{"packs": [1]}', "not json"])
def test_cli_bad_run_json_exits_1_with_one_line(tmp_path, body):
    run_json = tmp_path / "run.json"
    run_json.write_text(body)
    r = _cli("core-adjust", str(ROOT / "packs"), str(run_json), home=tmp_path)
    assert r.returncode == 1 and "Traceback" not in r.stderr and len(r.stdout.strip().splitlines()) == 1


# --- Task 4: Stage 0, SKILL.md, and the manuscript audit ---

def test_skill_md_applies_core_adjust_before_every_dispatch():
    text = (SKILL / "SKILL.md").read_text()
    rule = text.split("- Core adjustments.", 1)[1].split("\n- ", 1)[0]
    for phrase in ("`run.json` `core_adjust`", "before every DISPATCH of a core agent (a file in `agents/`) or a pack agent",
                   "by `packs/<pack>/agents/<file>` for a pack agent",
                   "do not dispatch it", "Pack note (<pack>, <role>): <text>",
                   "Where a note conflicts with your instructions, follow the note.",
                   "Turned off for this paper:", "`stage-4-compiler`", "A run without the key has none."):
        assert phrase in rule, phrase


def test_stage_0_writes_primary_pack_and_runs_core_adjust():
    text = STAGES[0].read_text()
    step13 = _step_with(text, "plumb core-adjust {PLUGIN}/packs {WORKSPACE}/run.json")
    assert '`"primary_pack"`' in step13
    assert step13.index("plumb core-adjust") < step13.index("plumb stops <level> <depth>")
    assert "which checks will not run and why" in step13
    step10 = _step_with(text, "agents/manuscript-audit.md")
    assert "built pack names from step 4" in step10
    assert "Pass the auditor the overlay labels and cues from the step 4 output." in step10
    assert '"cues": {<overlay>: [<cues>]}' in _step_with(text, "plumb validate-packs {PLUGIN}/packs")


def test_validate_packs_prints_each_overlays_cues(tmp_path):
    r = _cli("validate-packs", str(ROOT / "packs"), home=tmp_path)
    out = json.loads(r.stdout)
    assert r.returncode == 0 and set(out["cues"]) == set(out["overlays"])
    assert out["cues"]["computational"] == packs.load_pack(ROOT / "packs/computational").detection_cues


def test_manuscript_audit_takes_built_packs_from_the_orchestrator():
    text = (SKILL / "agents/manuscript-audit.md").read_text()
    assert "Packs are built for archival and computational" not in text
    assert "The orchestrator gives you the names of the built packs" in text


def test_correlational_is_not_a_paper_type():
    text = (SKILL / "agents/manuscript-audit.md").read_text()
    types = text.split("Classify the paper as one or two of: `", 1)[1].split("`", 1)[0]
    assert "correlational" not in types and "archival" in types
    assert "There is no correlational type" in text


# --- Task 5: one ledger for variables and constructs ---

def test_contract_3_and_ledger_agents_cover_constructs():
    contracts = (SKILL / "shared/contracts.md").read_text()
    assert "When the construction ledger" in contracts and "variable or construct" in contracts
    for name, start, end in (("construction-ledger-producer.md", "### Step 4b", "### Step 5"),
                             ("construction-ledger-checker.md", "### Step 3b", "### Step 4")):
        text = (SKILL / "agents" / name).read_text()
        for phrase in ('"constructs"', "evidence_anchor", "none shown", "aggregate dimension | theme | concept",
                       "individual | group | organization | field | event | other"):
            assert phrase in text, (name, phrase)
        section = text.split(start, 1)[1].split(end, 1)[0]
        assert "time_variation" in section and "\u2014" not in section
        assert "no_entries_reason" in text
    audit = (SKILL / "agents/construction-claim-audit.md").read_text()
    assert "Check claims about a construct against its `constructs` entry" in audit
    assert "a construct has no `time_variation`" in audit and "evidence_anchor" in audit


# --- Task 6: the ledger unit in Stages 2 and 5, the read summary, and Stage 7 ---

def test_ledger_unit_is_skipped_in_stages_2_and_5():
    step1 = _step(STAGES[2].read_text(), 1)
    assert "`construction-ledger-producer.md` is under `run.json` `core_adjust` `off`" in step1
    assert step1.index("skip this step") < step1.index("agents/construction-ledger-producer.md`, then")
    assert "is not a failure" in STAGES[2].read_text().split("\n1. ", 1)[0]
    step1 = _step(STAGES[5].read_text(), 1)
    assert "`construction-claim-audit.md` is under `run.json` `core_adjust` `off`" in step1
    assert '"verdict":"NOT RUN"' in step1 and "as for CLEAN" in step1
    assert "Empty ledger: the paper reports no measured variables and no coded constructs" in _step(STAGES[2].read_text(), 1)


def test_claim_audit_agent_reports_a_missing_ledger():
    text = (ROOT / "skills" / "review" / "agents" / "construction-claim-audit.md").read_text()
    inp = text.split("## Input", 1)[1].split("\n## ", 1)[0]
    assert "If `{WORKSPACE}/stage-2/construction_ledger.json` is missing, do not audit: report in one sentence that the ledger the run expected is missing, and stop." in inp
    assert "(When a pack turns the ledger off, Stage 5 does not dispatch this agent.)" in inp
    assert "NOT RUN" not in text and "Never fail on a missing ledger" not in text


def test_read_summary_uses_constructs_and_pack_read_lines():
    step3 = _step(STAGES[2].read_text(), 3)
    assert "variables or constructs" in step3
    assert "`run.json` `core_adjust` `read_lines`" in step3 and "`run.json` `packs`" in step3
    assert "the pack lines do not count toward that cap" in step3
    assert "When `run.json` `overlays` is not empty" not in step3
    built = packs.load_all(ROOT / "packs")
    assert built["computational"].read_checkin_lines == ["Generated variables:"]
    assert built["nonlinear"].read_checkin_lines == ["Nonlinear terms:"]


def test_stage_7_names_checks_that_did_not_run():
    text = STAGES[7].read_text()
    assert "`core_adjust` `off`" in text and "which checks were skipped by design for this paper and why" in text
    assert "never by file name and never as a failure" in text


# --- Task 7: theory-slot issues in stage-4/, the devil reads pack reports, the Stage 4 compiler ---

def test_theory_slot_agents_write_issues_to_stage_4():
    text = STAGES[3].read_text()
    step2 = _step(text, 2)
    assert "`Pack: <pack>`" in step2 and "`{WORKSPACE}/stage-4/`" in step2 and "names every file it wrote in its reply" in step2
    assert "pack theory reports" in _step(text, 3)
    step4 = _step(text, 4)
    assert "each flagged agent, core or pack, by the name the report gives" in step4
    assert "rewrites every file it wrote" in step4


def test_theory_devil_reads_pack_theory_reports():
    devil = (SKILL / "agents/theory-devil.md").read_text()
    assert "4. **Pack theory reports, if any (the orchestrator lists them):**" in devil
    challenge2 = devil.split("### Challenge 2", 1)[1].split("## Output Format", 1)[0]
    assert challenge2.count("pack theory report") == 2
    assert "<Pack agent, by the name its report gives>" in devil
    rule3 = devil.split("\n3. At least one challenge", 1)[1].split("\n4. ", 1)[0]
    assert "pack theory report" in rule3


def test_stage_4_compiler_reads_severity_rules_and_pack_lines():
    step3 = _step(STAGES[4].read_text(), 3)
    for phrase in ("`severity_rules` in `{PLUGIN}/packs/<pack>/pack.yaml` for each pack in `run.json` `packs`",
                   "a first line `Pack: <name>` is used when present", "`run.json` `primary_pack`", "when `primary_pack` is null",
                   "starts `# Not run` holds no findings", "the merged issue stays protected",
                   "`stage-4-compiler`", "Apply each rule once",
                   "a rule that shifts a level (for example, down one level) is applied only by the compiler",
                   "any other overlay's fingerprint item whose role that pack's severity rules name as main"):
        assert phrase in step3, phrase


def test_stage_4_compiler_still_merges_every_stage_4_file():
    step3 = _step(STAGES[4].read_text(), 3)
    assert "merges the stage-4 files into `stage-4/majors_draft.md`" in step3
    assert 'Second-pack findings are capped at "Weakens a claim" unless they undermine the main claim.' in step3
    assert step3.count("When two source files raise the same problem") == 1
    assert "A construct counts as a variable here" in step3


def test_fix1_compiler_attributes_pack_findings_by_slot():
    step3 = _step(STAGES[4].read_text(), 3)
    assert "attributes each stage-4 file to a pack by slot ownership" in step3
    assert "written by the diagnose or theory agents of a pack in `run.json` `packs`" in step3
    assert "each agent's Output section names its file" in step3
    assert "a first line `Pack: <name>` is used when present" in step3


def test_fix1_no_stacking_of_shifting_rules():
    step3 = _step(STAGES[4].read_text(), 3)
    assert "applies to the level the pack's own file gives" in step3
    assert "must not discount the same finding again for the same reason" in step3


def test_fix1_devil_reads_a_named_report_once():
    devil = (SKILL / "agents/theory-devil.md").read_text()
    assert "read it once and report it once" in devil


# --- Task 8: the coverage audit reads every stage-3 and stage-4 report ---

sys.path.insert(0, str(SKILL / "scripts"))
import audit_coverage  # noqa: E402


def test_coverage_audit_reads_pack_files_in_stage_3_and_4(tmp_path):
    (tmp_path / "stage-3").mkdir()
    (tmp_path / "stage-4").mkdir()
    issue = "1. A problem.\n   Severity: Undermines the main claim\n"
    (tmp_path / "stage-4/theory_propositions.md").write_text("Pack: theory\n\n" + issue)
    (tmp_path / "stage-3/formal_model.md").write_text(issue)
    found = {f for f, _, _ in audit_coverage.find_serious_findings(tmp_path)}
    assert found == {"stage-4/theory_propositions.md", "stage-3/formal_model.md"}


def test_coverage_audit_skips_the_majors_draft_alternatives_and_stubs(tmp_path):
    (tmp_path / "stage-3").mkdir()
    (tmp_path / "stage-4").mkdir()
    issue = "Severity: Undermines the main claim\n"
    (tmp_path / "stage-4/majors_draft.md").write_text(issue)
    (tmp_path / "stage-3/alternatives.md").write_text(issue)
    (tmp_path / "stage-4/face_validity.md").write_text(
        packs.stub_text("Turned off by the theory pack") + "\n" + issue
    )
    assert audit_coverage.find_serious_findings(tmp_path) == []
    assert audit_coverage.upstream_files(tmp_path) == ["stage-4/face_validity.md"]


def test_coverage_audit_reads_the_computational_files(tmp_path):
    (tmp_path / "stage-4").mkdir()
    for name in ("measurement_validity.md", "generated_variable_inference.md"):
        (tmp_path / "stage-4" / name).write_text("Severity: Undermines the main claim\n")
    found = {f for f, _, _ in audit_coverage.find_serious_findings(tmp_path)}
    assert found == {"stage-4/measurement_validity.md", "stage-4/generated_variable_inference.md"}


# --- Task 9: the stress test's per-run prompt ---

def test_stress_test_uses_the_per_run_prompt_in_both_engines():
    step3 = _step(STAGES[6].read_text(), 3)
    assert "`{WORKSPACE}/stage-6/stress_prompt.md` when it exists" in step3
    assert step3.count("{PLUGIN}/skills/review/shared/stress-test-prompt.md") == 1
    assert step3.count("<pdf> <draft> <prompt> {WORKSPACE}/stage-6/stress_test") == 2
    assert "the path `<prompt>`" in step3
    tester = (SKILL / "agents/stress-tester.md").read_text()
    assert "stage-6/stress_prompt.md" in tester


# --- Task 10: the consent attestation ---

def test_consent_screen_has_the_attestation_line():
    step7 = _step_with(STAGES[0].read_text(), "Consent screen:")
    assert ("If the paper quotes interviews, field notes, or open-ended answers, confirm that your ethics "
            "approval and any site agreement allow sending the manuscript to a model provider.") in step7
    assert '"A. Yes, or the paper quotes none" / "B. No" / "C. Not sure"' in step7
    assert "Write A as `\"irb_allows_excerpts\": true`, B as false, and C as null." in step7
    assert "Ask no other IRB question. In a referee run, do not ask it" in step7
    assert "no qualitative pack" not in step7


# --- Task 15: README and repo spec ---

def test_docs_describe_core_adjustments():
    readme = (ROOT / "README.md").read_text()
    spec = (ROOT / "docs/spec.md").read_text()
    assert "turn off core checks" in readme and "significance star" in readme
    for phrase in ("`turns_off`", "`core_notes`", "`read_checkin_lines`", "plumb core-adjust", "overlays never count"):
        assert phrase in spec, phrase
    assert "does the IRB protocol allow third-party processing" not in spec
    assert "—" not in readme and "—" not in spec


# --- Final fix wave: a note file that is not UTF-8 is a pack error ---

def test_a_note_file_that_is_not_utf8_is_a_pack_error(tmp_path):
    d = _pack(tmp_path, "core_notes: {face-validity.md: {file: notes/a.md}}\n")
    (d / "notes").mkdir()
    (d / "notes" / "a.md").write_bytes(b"caf\xe9 note")
    with pytest.raises(packs.PackError, match="not UTF-8"):
        packs.load_pack(d)


# --- Final fix wave: prompt rulings (Core extensions final review, part B) ---

AGENTS = SKILL / "agents"


def test_stage_4_primary_pack_fallback_and_no_double_discount():
    step = _step_with(STAGES[4].read_text(), "Dispatch a compiler (judgment)")
    assert ("When run.json has no primary_pack key, the pack for setup:type (the first entry of packs) "
            "is primary.") in step
    assert ("Where a pack file says it already discounted a finding for the contribution type, do not apply "
            "a shifting rule for the same reason.") in step
    item9 = (SKILL / "shared/contracts.md").read_text().split("\n9. ", 1)[1].split("\n10. ", 1)[0]
    assert "Leave a level shift that your pack.yaml states to the Stage 4 compiler." in item9


def test_ledger_agents_read_construct_evidence_and_allow_no_entries():
    producer = (AGENTS / "construction-ledger-producer.md").read_text()
    checker = (AGENTS / "construction-ledger-checker.md").read_text()
    assert ("At least one of the two lists must have an entry, unless no_entries_reason is set "
            "(see No entries).") in producer
    line = "For constructs, also read the findings and any data-structure figure or quote table."
    assert line in producer.split("### Step 2", 1)[1].split("### Step 3", 1)[0]
    assert line in checker.split("### Step 2", 1)[1].split("### Step 3", 1)[0]
    audit = (AGENTS / "construction-claim-audit.md").read_text()
    assert "0. If `{WORKSPACE}/stage-2/construction_ledger.json` is missing" in audit


def test_stage_0_asks_the_attestation_alone_for_a_solo_author():
    step = _step_with(STAGES[0].read_text(), "irb_allows_excerpts")
    assert "If no coauthor question is asked (a solo author), ask the attestation line on its own" in step


def test_docs_do_not_claim_an_unbuilt_market_pack_or_a_correlational_gap():
    spec = (ROOT / "docs/spec.md").read_text()
    assert "That type is meta-analysis." not in spec and "Those types are" not in spec
    readme = (ROOT / "README.md").read_text()
    va_src = (SKILL / "scripts/verify_arithmetic.py").read_text()
    assert "which the market-event overlay checks when it runs" in readme
    assert "which the market-event overlay checks when it runs" in va_src
    for text in (readme, va_src):
        assert "planned market-event pack" not in text
    for text in (readme, va_src):
        assert "the market-event pack checks" not in text.lower()
    devil = (AGENTS / "theory-devil.md").read_text().splitlines()
    assert "\u2014" not in devil[11]


def test_stage_4_compiler_block_carries_a_pack_line():
    step3 = _step(STAGES[4].read_text(), 3)
    block = step3.split("```", 2)[1]
    assert "   Severity: <label>. Adjudication: <paper | external | judgment>.\n   Pack: <pack name | core>.\n" in block
    assert ("The `Pack:` line names the pack whose agent wrote the issue's source file, by the slot attribution above, "
            "or `core` when a core agent (a file in `agents/`) wrote it.") in step3
    assert "A merged issue takes the pack that owns it, or, when no pack owns it, the pack of the better-evidenced source." in step3
