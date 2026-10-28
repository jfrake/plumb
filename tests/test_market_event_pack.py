from __future__ import annotations
import re
from pathlib import Path

import pytest
import yaml

from plumb import packs

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "review"
PACK = ROOT / "packs" / "market-event"
IDS = [f"R{i}" for i in range(1, 19)]
MEASURES = ("short-window CAR", "long-window CAR", "BHAR", "calendar-time portfolio",
            "single-firm abnormal return", "cross-sectional CAR regression")
ROLES = ("main hypothesis", "other hypothesis", "control or robustness")
DEFINITION = ("A market event analysis is a test built on abnormal stock returns (a stock's return minus the return "
              "a benchmark predicts) summed or compounded around dated announcements.")


# --- Task 1: the fingerprint lists market event analyses ---

def test_fingerprint_lists_market_event_analyses_with_roles():
    text = (SKILL / "agents" / "manuscript-audit.md").read_text(encoding="utf-8")
    template = text.split("# Fingerprint", 1)[1].split("```", 1)[0]
    line = ("Market event analyses:\n- <event and window as the paper labels them>: <measure>; events: <N>; "
            "distinct dates: <k, or \"not reported\">; role: <role>")
    assert line in template and template.index("Designs:") < template.index("Market event analyses:")
    para = text.split("Under `Market event analyses:`", 1)[1].split("\n\n", 1)[0]
    for s in MEASURES + ROLES + ("are not market event analyses", "Distinct dates"):
        assert s in para, s
    assert ("List the market-event overlay under `Overlays:` only when some line under `Market event analyses:` "
            "has role main hypothesis or other hypothesis.") in text


# --- Task 3: the pack's frame ---

JUDGMENT = {"R4", "R5", "R12", "R13", "R16", "R17"}
EXTERNAL = {"R2", "R8"}
SEVERITIES = ("Undermines the main claim", "Weakens a claim", "Minor")
CHECKLIST = {
    "R1": "Each event's date is the first public disclosure of the news, the source of the dates is named, the paper says how it looked for earlier reports, leaks, or rumors, and announcements made after the market close or on a non-trading day are assigned to the next trading day, or the window includes it",
    "R2": "For a study of about ten or fewer events, or for an event the paper discusses by name, no public report of the same news appeared before the date the paper uses",
    "R3": "The return model (market-adjusted, market model, or a named factor model), the market index and its weighting, the estimation window's length and its gap before the event, the minimum number of returns required, the return data source, and the software or code are reported; the estimation window ends before the event window begins",
    "R4": "In a multi-country sample, the benchmark allows for world as well as home-market movements and trading calendars are aligned before returns are cumulated; where many stocks trade thinly, the paper screens them out or adjusts for it",
    "R5": "The main event window is short, named before the results, and justified by when the news reached the market; results for the other windows the paper computed are reported; a hypothesis stated for one window is not declared supported by a different window",
    "R6": "The CAR over a window before the event is reported, and anticipation or leakage is discussed where the news was likely expected or leaked before the announcement",
    "R7": "The confounding-event screen is stated: which kinds of news, over which days, from which source, and how many events it removed; the main result is shown with and without the removed events",
    "R8": "For a study of about ten or fewer events, or for an event the paper discusses by name, no earnings release, dividend change, merger news, or executive change of the same firm falls inside the event window without being screened out or discussed",
    "R9": "When events share announcement dates (many firms reacting to one regulation, ruling, or election, several events on one day, or repeat events of one firm with overlapping windows), the paper reports at least one test that allows for cross-sectional correlation of abnormal returns (such as the Kolari and Pynnonen adjustment, or a portfolio or calendar-time approach), and it does not rest the result only on tests that assume abnormal returns are independent across events",
    "R10": "The reported numbers for each abnormal-return test cohere: a statistic the paper identifies as the cross-sectional t matches the mean CAR, its standard deviation or standard error, and N; its stars and p-values match it; a window's mean CAR equals the sum of the daily mean abnormal returns or sub-window CARs it contains when they are computed on the same events and extreme values are handled before summing; the share of positive CARs is possible with the stated N; and the sample counts reconcile from raw events to the final sample",
    "R11": "The median CAR and the share of positive CARs are reported beside the mean with a test that does not rest on the mean alone (a sign or rank test), the rule for extreme returns (winsorizing level, trimming, or none) is stated and applied the same way throughout, and the main result is shown with and without it; a result resting only on the Patell test, where the event plausibly raises return variance, is supported by a test robust to event-induced variance (BMP or the cross-sectional t)",
    "R12": "Each test states its number of events; tests on small subgroups are not read as support without an argument about precision; a study of one firm or a few events does not rest its inference on a standard test of the event-window return against estimation-window residuals",
    "R13": "A short-window CAR is read as the market's revised expectation at the announcement, relative to what investors already anticipated; claims about long-run value creation, realized performance, or stakeholder welfare rest on more than that window; a null CAR is not read as \"investors do not value\" the action when the event was likely anticipated; and a pooled mean over events whose news runs in opposite directions is not read as no reaction",
    "R14": "When returns are measured over months or years, the paper uses buy-and-hold returns against carefully built reference portfolios or matched firms, or calendar-time portfolios, addresses dependence from overlapping windows, and does not present a long-window CAR tested as if the windows were independent",
    "R15": "Regressions with a CAR as the dependent variable use standard errors that allow for unequal return variance across firms, and, when events share announcement dates, for correlation among them; the paper says which it uses",
    "R16": "Controls in a CAR regression are measured before the event; terms revealed at or after the announcement (deal terms, post-announcement analyst actions, later financials) are not used as controls when the paper claims the effect of an earlier trait",
    "R17": "When the main claim reads a trait's coefficient in a CAR regression as the market's causal valuation of that trait, the paper addresses why firms with the trait chose to announce; a Heckman correction has a first-stage variable excluded from the second stage, and the significance of the inverse Mills ratio is not read as proof that selection is present or absent",
    "R18": "The population of events is defined (which firms, which kinds of announcement, which years), and every screen from raw events to the final sample (listing, return data, minimum estimation-window returns, confounding events) is stated with its count",
}


def _expected():
    return yaml.safe_load((PACK / "fixtures" / "planted-1" / "expected.yaml").read_text(encoding="utf-8"))


def test_market_event_pack_loads_as_an_overlay():
    p = packs.load_pack(PACK)
    assert p.name == "market-event" and p.overlay is True
    assert "theory" not in p.slots and p.turns_off == []
    assert p.read_checkin_lines == ["Market event analyses:"]
    assert [i["id"] for i in p.checklist] == IDS


def test_checklist_matches_the_spec():
    items = {i["id"]: i for i in packs.load_pack(PACK).checklist}
    for k in IDS:
        assert items[k]["text"] == CHECKLIST[k], k
        want = "judgment" if k in JUDGMENT else "external" if k in EXTERNAL else "paper"
        assert items[k]["adjudication"] == want, k


def test_severity_rules():
    rules = packs.load_pack(PACK).severity_rules
    assert len(rules) == 10
    assert "'Undermines the main claim' in three cases, and only these" in rules[0]
    assert "all four hold" in rules[0] and "the cross-sectional t" in rules[0] and "(c) all events fall on one date or a handful of dates" in rules[0]
    assert "about ten or fewer events, a named event, or a plausible confound" in rules[4]
    assert rules[1].startswith("R9") and "share announcement dates" in rules[1] and "Never predict" in rules[1]
    assert rules[2].startswith("R13") and rules[3].startswith("R6") and rules[4].startswith("R7")
    assert rules[5].startswith("R11") and rules[6].startswith("R2 and R8") and "about ten or fewer events" in rules[6]
    assert rules[7].startswith("R10") and "`stars_exceed_under_t`" in rules[7]
    assert rules[8].startswith("Reporting-only findings are 'Minor'") and "overlaps the event window" in rules[8]
    assert "capped at 'Weakens a claim'" in rules[9] and "at 'Minor'" in rules[9]
    for r in rules:
        assert "down one level" not in r and "downgraded" not in r


def test_hand_off_notes_reach_the_archival_agents_only_when_both_packs_run():
    built = packs.load_all(ROOT / "packs")
    targets = {"packs/archival/agents/methods-checks.md", "packs/archival/agents/triangulation.md",
               "packs/archival/agents/adversarial-dgp.md"}
    inference = "packs/inference/agents/inference-claims.md"
    assert set(built["market-event"].core_notes) == targets | {inference}
    run = {"packs": ["archival", "market-event"], "overlays": ["market-event"], "types_without_pack": [],
           "primary_pack": "archival"}
    notes = packs.core_adjust(built, run)["notes"]
    for t in targets:
        [n] = [n for n in notes[t] if n["pack"] == "market-event"]
        assert n["role"] == "overlay" and n["text"].startswith("The market-event overlay runs on this paper.")
    assert "If Event Study (distinct from DiD)" in notes["packs/archival/agents/methods-checks.md"][-1]["text"]
    assert "any other pack's note assign them" in notes["packs/archival/agents/methods-checks.md"][-1]["text"]
    assert inference not in notes
    run = {"packs": ["archival", "inference", "market-event"], "overlays": ["inference", "market-event"],
           "types_without_pack": [], "primary_pack": "archival"}
    [n] = [n for n in packs.core_adjust(built, run)["notes"][inference] if n["pack"] == "market-event"]
    assert n["role"] == "overlay" and "(check R5)" in n["text"] and "in I16, a null mean CAR read as no market reaction (check R13)" in n["text"]
    run = {"packs": ["archival"], "overlays": [], "types_without_pack": [], "primary_pack": "archival"}
    notes = packs.core_adjust(built, run)["notes"]
    assert not any(n["pack"] == "market-event" for t in targets for n in notes.get(t, []))


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


# --- Task 4: the verify agent ---

def _agent(name):
    return (PACK / "agents" / name).read_text(encoding="utf-8")


def test_numbers_agent():
    assert packs.load_pack(PACK).slots.get("verify") == ["event-numbers.md"]
    text = _agent("event-numbers.md")
    for s in ("stage-1/market-event_numbers.md", "## Tests checked", "## Flags", "## Facts for diagnosis",
              "## Not computed", "Quick", "Record: <id>. Table: <label>. Cells: <table:row:col, ...>.",
              "Flag nothing as missing"):
        assert s in text, s
    for kind in ("car_test", "window_sum", "sign", "sample_flow", "period_counts", "event_dates"):
        assert f"`{kind}`" in text, kind


def test_numbers_agent_names_the_statistic_only_from_the_paper():
    text = _agent("event-numbers.md")
    assert 'Set `test` to "cross-sectional t" only when the paper calls its statistic that or gives its formula' in text
    assert "`formula_stated`" in text and '"unspecified" for a bare "t" the paper never defines' in text
    for level in ('"daily"', '"window"', '"none"', '"unstated"'):
        assert level in text, level
    assert "Never build a date list from outside sources." in text


def test_numbers_agent_defers_to_the_core_and_runs_the_script_itself():
    text = _agent("event-numbers.md")
    assert "tools: [Read, Write, Bash, Glob]" in text.split("---", 2)[1]
    assert "The orchestrator will provide `PDF_PATH`, `PAGE_COUNT`, `{WORKSPACE}`, and `{PLUGIN}`." in text
    assert ("`python3 {PLUGIN}/packs/market-event/scripts/event_arith.py "
            "{WORKSPACE}/stage-1/event_inputs.json {WORKSPACE}/stage-1/event_arith.json`") in text
    assert "Skip regression tables whose dependent variable is a CAR; the core star check covers them." in text
    reason = "abnormal-return mean tests, which the market-event overlay checks when it runs"
    assert f'"{reason}"; every such table is yours.' in text
    assert reason in (SKILL / "scripts" / "verify_arithmetic.py").read_text(encoding="utf-8")
    assert "already allows every reference from the normal to Student t with 1 degree of freedom" in text
    assert "`{WORKSPACE}/stage-1/numeric_fidelity.md`" in text and "`t_vs_p`" in text
    assert "with the file-writing tool" in text
    assert not re.search(r"(cat|echo|printf|tee)[^\n`]*>", text)
    assert (PACK / "scripts" / "event_arith.py").exists()


# --- Task 5: the context agent ---

def test_dating_agent():
    assert packs.load_pack(PACK).slots.get("context") == ["event-dating.md"]
    text = _agent("event-dating.md")
    for s in ("stage-2/event_dating.md", "about 15 searches at Standard depth, 25-35 at Deep",
              "Read `depth` from `run.json`", "`search_before`", "SEC EDGAR", "about ten or fewer events",
              "Do not sample from a longer list.", "Does not apply:", "is not proof that none existed",
              "## Earlier disclosure", "## Confounding news in the window", "## Could not establish",
              "skills/review/shared/research-protocol.md"):
        assert s in text, s
    assert "profiles/" not in text


# --- Task 6: the test agent ---

def test_test_agent():
    p = packs.load_pack(PACK)
    assert p.slots.get("diagnose", [])[:1] == ["event-test.md"]
    text = _agent("event-test.md")
    assert "stage-4/event_test.md" in text and "The first line is `Pack: market-event`." in text
    for i in range(1, 13):
        assert re.search(rf"^### R{i}\. ", text, re.M), i
    for s in ("Excerpt:", "Page:", "Analysis: <analysis> (<measure>, <role>)", "## Checked and fine",
              "Severity: <Undermines the main claim | Weakens a claim | Minor>"):
        assert s in text, s
    for rule in p.severity_rules:
        assert rule in text


def test_test_agent_skips_dropped_flags_and_missing_outside_checks():
    text = _agent("event-test.md")
    assert "{WORKSPACE}/stage-1/dropped_flags.md" in text and "If the file is missing, no flag was dropped." in text
    assert "any result in `event_arith.json` whose `id` matches that flag's `Record:`" in text
    assert "skip R2 and R8 and say so under \"Checked and fine\"" in text
    assert ("(`<n>` is the flag's position under `## Flags` in `market-event_numbers.md`; "
            "map it to that flag's `Record:` line)") in text


def test_test_agent_counts_only_the_confirmed_tests_as_robust_to_shared_dates():
    text = _agent("event-test.md")
    r9 = text.split("### R9. ", 1)[1].split("### R10. ", 1)[0]
    assert ("Count only the Kolari and Pynnonen adjustment, portfolio or calendar-time approaches, and, when there "
            "are many distinct dates, standard errors clustered by event date as allowing for cross-sectional "
            "correlation of abnormal returns.") in r9
    assert "date clusters are too few to rely on (MacKinnon and Webb 2017)" in r9
    assert "without asserting their properties" in r9 and "Never predict" in r9
    r5 = text.split("### R5. ", 1)[1].split("### R6. ", 1)[0]
    assert "all four of its conditions hold" in r5 and "a paper whose windows all agree passes" in r5


# --- Task 7: the claims agent, coverage, and the authoring rules ---

def test_claims_agent():
    p = packs.load_pack(PACK)
    assert p.slots.get("diagnose") == ["event-test.md", "event-claims.md"]
    text = _agent("event-claims.md")
    assert "stage-4/event_claims.md" in text and "The first line is `Pack: market-event`." in text
    for i in range(13, 19):
        assert re.search(rf"^### R{i}\. ", text, re.M), i
    for rule in p.severity_rules:
        assert rule in text
    assert "{WORKSPACE}/stage-2/construction_ledger.json" in text
    assert "{WORKSPACE}/stage-1/dropped_flags.md" in text and "If the file is missing, no flag was dropped." in text
    assert ("(`<n>` is the flag's position under `## Flags` in `market-event_numbers.md`; "
            "map it to that flag's `Record:` line)") in text
    assert "`Designs:` line, as corrected in `{WORKSPACE}/brief.md` (section 'User corrections')" in text
    assert "`{WORKSPACE}/run.json`: `packs` and `overlays`" in text
    r15 = text.split("### R15. ", 1)[1].split("### R16. ", 1)[0]
    assert "belong to the inference pack when `inference` is in `run.json` `overlays`" in r15
    assert "check them yourself when neither runs" in r15 and "states its standard-error method (I1)" in r15


def test_claims_agent_hands_heckman_mechanics_to_the_selection_module():
    text = _agent("event-claims.md")
    r17 = text.split("### R17. ", 1)[1].split("### R18. ", 1)[0]
    assert "When the `Designs:` line lists Selection" in r17 and "keep only the question of selection into announcing" in r17
    assert "Only when the main claim reads a trait's coefficient" in r17
    r13 = text.split("### R13. ", 1)[1].split("### R14. ", 1)[0]
    assert "Advice to managers is not flagged by itself." in r13 and "a null measures surprise and not value" in r13


def test_every_check_is_owned_by_one_diagnose_agent():
    owners = {}
    for a in ("event-test.md", "event-claims.md"):
        for c in re.findall(r"^### (R\d+)\. ", _agent(a), re.M):
            assert c not in owners, c
            owners[c] = a
    assert sorted(owners, key=lambda c: int(c[1:])) == IDS


AGENTS = ("event-numbers.md", "event-dating.md", "event-test.md", "event-claims.md")


def test_every_market_event_agent_follows_the_authoring_rules():
    for a in AGENTS:
        text = _agent(a)
        head = text.split("---", 2)[1]
        for k in ("name:", "description:", "maxTurns:"):
            assert k in head, (a, k)
        assert "skills/review/shared/contracts.md" in text and "bind you." in text, a
        assert ("Cite one in your output only if you fetched it in this run; "
                "otherwise state the concern without the citation.") in text, a
        assert text.split("## Input", 1)[1].lstrip().startswith("The orchestrator will provide `PDF_PATH`, `PAGE_COUNT`,"), a
        assert 'the list says "none" or is missing' in text, a
        assert DEFINITION in text or "A market event analysis is a test built on abnormal stock returns" in text, a
        assert "Reply to the orchestrator in one sentence that names the file you wrote." in text, a
        assert "\u2014" not in text, a
    for a in AGENTS[:1] + AGENTS[2:]:
        text = _agent(a)
        for m in MEASURES + ROLES:
            assert m in text, (a, m)
    for a in AGENTS[2:]:
        text = _agent(a)
        assert "Never predict the result" in text, a
        assert ("Flag an absence only after searching the methods section, the appendices, the footnotes, "
                "and every table, and name where you looked.") in text, a


# --- Task 9: README and repo spec ---

def test_readme_and_spec_name_the_market_event_overlay():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert readme.count("- **Market event** is an overlay.") == 1
    assert readme.index("- **Survey** is a type pack.") < readme.index("- **Market event** is an overlay.")
    assert re.search(r"A pack adds checks for one kind of paper\. [A-Z][a-z]+ are built\.", readme)
    spec = (ROOT / "docs" / "spec.md").read_text(encoding="utf-8")
    assert "market-event (abnormal stock returns around announcements)" in spec


# --- Final fix B ---

def test_final_fix_hand_offs_and_scopes():
    numbers = _agent("event-numbers.md")
    step1 = numbers.split("### Step 1. ", 1)[1].split("### Step 2. ", 1)[0]
    assert ("A table the core skipped that is a CAR regression goes under `## Not computed` as "
            "\"CAR regression the core star check skipped\".") in step1
    r5 = _agent("event-test.md").split("### R5. ", 1)[1].split("### R6. ", 1)[0]
    assert ("For BHAR, long-window CAR and calendar-time analyses, the window length is R14's; check here only "
            "the choice among reported windows.") in r5
    dating = _agent("event-dating.md").split("### Step 1. ", 1)[1].split("### Step 2. ", 1)[0]
    assert "For a common-date event the text names, check R2 only." in dating
    r17 = _agent("event-claims.md").split("### R17. ", 1)[1].split("### R18. ", 1)[0]
    assert "When the `Designs:` line lists Selection and `archival` is in `run.json` `packs`," in r17
    built = packs.load_all(ROOT / "packs")
    [note] = built["market-event"].core_notes["packs/archival/agents/adversarial-dgp.md"]
    text = note["text"] if isinstance(note, dict) else note
    assert "selection into announcing, as a rival explanation of a trait's coefficient in a CAR regression" in text
