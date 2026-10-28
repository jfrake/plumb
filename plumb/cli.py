"""Command-line entry used by the orchestrator and stage files."""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

from . import (audit, checkin, config, consent, deps, depth, outputs, packs, profiles, progress, rundir, stress,
               usage, validated)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="plumb")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("stops", help="the check-in stops asked at a level and depth")
    s.add_argument("level"); s.add_argument("tier")
    s = sub.add_parser("limits", help="the revision and search limits for a depth"); s.add_argument("depth")
    s = sub.add_parser("models", help="the model for each role at a depth"); s.add_argument("depth")
    s.add_argument("--platform", default="claude", choices=list(depth.PLATFORMS),
                   help="codex: a Claude model in the config becomes inherit")
    s = sub.add_parser("consent-check", help="check the consent record; on success log it (plumb egress logs what leaves, later)")
    s.add_argument("record_json"); s.add_argument("workspace")
    s.add_argument("--profiles", default="", help="profiles dir; with --journal, applies the journal's consent rules")
    s.add_argument("--journal", default="")
    s.add_argument("--needs-zero-retention", action="store_true",
                   help="the referee decision needs zero retention; the record must confirm it")
    s.add_argument("--no-log", action="store_true", help="check only; do not log the consent event (resume)")
    s = sub.add_parser("egress", help="log what leaves this machine, once, when the paper is first sent")
    s.add_argument("workspace")
    s = sub.add_parser("referee-decision", help="the outputs a referee may get at a journal")
    s.add_argument("profiles_dir"); s.add_argument("journal")
    s.add_argument("outputs", help="comma-separated: issues_list, annotated_pdf, report, editor_memo")
    s.add_argument("--depth", default="", help="the run's depth; at quick no report and a facts-only list")
    s.add_argument("--self-confirmed", action="store_true", help="referee confirmed the journal allows AI tools in review")
    s = sub.add_parser("filter-outputs", help="drop editor_memo from a mapped outputs list unless it is offered")
    s.add_argument("permission", help="mine, author_asked, or journal")
    s.add_argument("depth", help="the run's depth")
    s.add_argument("outputs", help="comma-separated: issues_list, annotated_pdf, report, editor_memo")
    s.add_argument("--profiles", default="", help="profiles dir; with --journal, checks the journal's upload policy")
    s.add_argument("--journal", default="")
    s = sub.add_parser("validate-packs", help="load and check every pack"); s.add_argument("packs_dir")
    s = sub.add_parser("run-packs", help="the packs a run uses for its paper types and overlays")
    s.add_argument("packs_dir")
    s.add_argument("--type", default=""); s.add_argument("--second-type", default="")
    s.add_argument("--overlay", action="append", default=[])
    s = sub.add_parser("core-adjust", help="work out which core agents the run's packs turn off")
    s.add_argument("packs_dir"); s.add_argument("run_json")
    s = sub.add_parser("log", help="log an audit event")
    s.add_argument("workspace"); s.add_argument("kind"); s.add_argument("data_json")
    s = sub.add_parser("checkin", help="record a check-in answer")
    s.add_argument("workspace"); s.add_argument("stop"); s.add_argument("item")
    s.add_argument("recommended"); s.add_argument("answer"); s.add_argument("--note", default="")
    s = sub.add_parser("answered", help="list the answered check-in items"); s.add_argument("workspace")
    s.add_argument("--labels", action="store_true", help="print each item's chosen label (last answer wins)")
    s = sub.add_parser("frontier", help="the open questions whose prerequisites are answered")
    s.add_argument("questions_json"); s.add_argument("workspace")
    s = sub.add_parser("render-audit", help="write the audit package"); s.add_argument("workspace")
    s = sub.add_parser("counts", help="override and answer counts for a run"); s.add_argument("workspace")
    s = sub.add_parser("stress-test-decision", help="decide which engine runs the stress test")
    s.add_argument("workspace")
    s = sub.add_parser("run-dir", help="create, move, find, or adopt a run folder")
    rd = s.add_subparsers(dest="action", required=True)
    s = rd.add_parser("new", help="create a run folder for a PDF")
    s.add_argument("pdf"); s.add_argument("--cwd", default=None); s.add_argument("--date", default="")
    s.add_argument("--fresh", action="store_true",
                   help="start a fresh run beside an unfinished run of this PDF, never resuming it; "
                        "run.json names the run left as it was")
    s.add_argument("--search-before", default="",
                   help="cap web searches at this date (YYYY-MM-DD); an evaluation option, never asked in setup")
    s = rd.add_parser("move", help="move a run folder to another folder")
    s.add_argument("run_dir"); s.add_argument("folder")
    s = rd.add_parser("find", help="find an unfinished run of a PDF")
    s.add_argument("pdf"); s.add_argument("--cwd", default=None)
    s = rd.add_parser("adopt", help="move an old review_workspace into a run folder")
    s.add_argument("legacy_workspace"); s.add_argument("pdf"); s.add_argument("--cwd", default=None)
    s = sub.add_parser("search-cap", help="cap an existing run's web searches at a date (an evaluation option): write search_before into run.json")
    s.add_argument("workspace"); s.add_argument("date", help="YYYY-MM-DD, usually the submission date")
    s = sub.add_parser("page-offset", help="write page_offset (PDF page minus printed page) into run.json")
    s.add_argument("workspace"); s.add_argument("offset", help="the integer locate_issues.py --page-offset printed")
    s = sub.add_parser("migrate-run", help="update an older run's run.json"); s.add_argument("workspace")
    s = sub.add_parser("readme", help="write the run folder's README")
    s.add_argument("workspace"); s.add_argument("--profiles", default="")
    s = sub.add_parser("sha256", help="print a file's SHA-256 hash"); s.add_argument("file")
    s = sub.add_parser("runlog", help="append a line to the run log")
    s.add_argument("workspace"); s.add_argument("line")
    s = sub.add_parser("put", help="move a staging file into the run folder")
    s.add_argument("run_dir"); s.add_argument("target")
    s.add_argument("--from", dest="staging", required=True, help="the staging file to move into the run folder")
    s = sub.add_parser("stage-header", help="the header line and time left for a stage")
    s.add_argument("depth", help="the run's depth, or none at Stage 0 before the depth is chosen")
    s.add_argument("stage", type=int)
    s.add_argument("--packs", type=int, default=0, help="the number of packs the run uses; each adds time")
    s = sub.add_parser("scoreboard", help="the end-of-run scoreboard"); s.add_argument("workspace")
    s = sub.add_parser("recap", help="the table of setup choices shown before the review starts")
    s.add_argument("workspace"); s.add_argument("--profiles", default="")
    s = sub.add_parser("usage", help="record and report token usage")
    us = s.add_subparsers(dest="action", required=True)
    s = us.add_parser("mark", help="point the usage hook at this run")
    s.add_argument("workspace"); s.add_argument("--cwd", default=None)
    s = us.add_parser("stage-end", help="mark the end of a stage for usage")
    s.add_argument("workspace"); s.add_argument("stage", type=int)
    s = us.add_parser("report", help="write usage.json"); s.add_argument("workspace")
    s = sub.add_parser("validated", help="write validated.json and dropped.json"); s.add_argument("workspace")
    s.add_argument("--allow-missing-excerpt", action="store_true",
                   help="keep an issue with no excerpt; it is placed by its page alone")
    s = sub.add_parser("check-issues", help="check the shape of an issues.json file")
    s.add_argument("file", help="stage-5/issues.json or stage-6/issues.json")
    s.add_argument("--draft", help="the same stage's draft.md, checked for metaphors too")
    s = sub.add_parser("check-minors", help="check that every kept minor is in the Stage 5 draft")
    s.add_argument("workspace")
    s = sub.add_parser("provider-facts", help="the saved answers about each model provider's terms, and whether they are fresh")
    s.add_argument("action", nargs="?", choices=["show", "set"], default="show")
    s.add_argument("provider", nargs="?", choices=list(config.PROVIDERS))
    s.add_argument("--trains", choices=["yes", "no", "unsure"], help="set: does the account train on inputs")
    s.add_argument("--retention-days", help="set: days the provider keeps inputs, or unsure")
    s.add_argument("--today", default="", help=argparse.SUPPRESS)
    s = sub.add_parser("validate-output", help="check an output's format and rules")
    s.add_argument("kind", choices=["fix_list", "issues_list", "report",
                                                                              "editor_memo"])
    s.add_argument("file")
    s.add_argument("--mode", default="full", choices=["full", "facts_only"],
                   help="issues_list and editor_memo only")
    s.add_argument("--validated", default="", help="stage-7/validated.json")
    s.add_argument("--dropped", default="", help="issues_list only: stage-7/dropped.json")
    s.add_argument("--trace", default="", help="report only: stage-7/report_trace.json")
    s.add_argument("--permission", default="", help="report only: the run's permission; journal needs the disclosure line")
    s.add_argument("--run", default="", help="run.json: with a search_before cap, citations dated after it fail; "
                   "with page_offset 0, one page number is enough")
    sub.add_parser("deps", help="report missing packages and whether Codex is on PATH")
    a = ap.parse_args(argv)

    if a.cmd == "counts":
        print(json.dumps(audit.counts(a.workspace), sort_keys=True)); return 0
    if a.cmd == "stops":
        print(json.dumps(checkin.stops_for(a.level, a.tier))); return 0
    if a.cmd == "limits":
        try:
            print(json.dumps(depth.limits(a.depth)))
        except ValueError as exc:
            print(str(exc)); return 1
        return 0
    if a.cmd == "models":
        try:
            print(json.dumps(depth.models(a.depth, config.load().models, a.platform)))
        except ValueError as exc:
            print(str(exc)); return 1
        return 0
    if a.cmd == "consent-check":
        try:
            rec = consent.from_dict(json.loads(Path(a.record_json).read_text()))
        except consent.ConsentError as exc:
            print(str(exc)); return 1
        requires_author_consent = False
        journal_policy_recorded = True
        needs_zero_retention = a.needs_zero_retention
        if rec.role == "referee":
            if not a.journal:
                print("A referee's consent record is checked against the journal: pass --journal."); return 1
            try:
                prof = profiles.load_profile(a.profiles or profiles.PROFILES_DIR, a.journal)
            except ValueError as exc:
                print(str(exc)); return 1
            if prof.upload == "banned":
                print(f"Referee mode is off: {prof.name} bans uploading manuscripts to AI tools."); return 1
            consent.apply_journal_profile(rec, prof.upload)
            requires_author_consent = prof.requires_author_consent
            journal_policy_recorded = prof.upload != "unknown"
            needs_zero_retention = needs_zero_retention or profiles.needs_zero_retention(prof)
        problems = consent.missing_consents(rec, requires_author_consent, needs_zero_retention,
                                            journal_policy_recorded)
        if problems:
            print("\n".join(problems)); return 1
        if a.no_log:
            print("OK"); return 0
        audit.log_event(a.workspace, "consent", **asdict(rec))
        print("OK"); return 0
    if a.cmd == "egress":
        ws = Path(a.workspace)
        try:
            rec = consent.from_dict(json.loads((ws / "consent.json").read_text(encoding="utf-8")))
        except (OSError, ValueError, consent.ConsentError) as exc:
            print(f"consent.json: {exc}"); return 1
        done = {(e.get("item"), e.get("to")) for e in audit.read_events(ws) if e["kind"] == "egress"}
        logged = []
        for item in rec.egress:
            to = consent.EGRESS_RECIPIENTS.get(item, rec.provider)
            if item in consent.LOGGED_AT_USE or (item, to) in done:
                continue
            audit.log_event(ws, "egress", item=item, to=to)
            logged.append(item)
        print(json.dumps(logged)); return 0
    if a.cmd == "stress-test-decision":
        ws = Path(a.workspace)
        run_cfg = json.loads((ws / "run.json").read_text())
        try:
            run_depth = depth.from_run(run_cfg, checkin.answers(ws).get("setup:depth", ""))
        except ValueError as exc:
            print(f"run.json: {exc}"); return 1
        cpath = ws / "consent.json"
        try:
            rec = consent.from_dict(json.loads(cpath.read_text())) if cpath.exists() else None
        except consent.ConsentError:
            rec = None
        codex_enabled = config.load().codex_enabled
        engine, reason = stress.decide(run_depth, codex_enabled, deps.codex_available(),
                                       rec, profiles.run_needs_zero_retention(run_cfg, rec))
        # The user asked for Codex and it cannot run: say so. Without Codex enabled, or with the Codex
        # stress test never declared in the consent record, Claude is the plan.
        if engine == "claude" and codex_enabled and rec is not None and "codex_stress_test" in rec.egress:
            audit.log_event(ws, "dependency", name="codex_stress_test",
                            message=f"{reason} A Claude agent runs the stress test instead.")
        print(json.dumps({"run": bool(engine), "engine": engine, "reason": reason})); return 0
    if a.cmd == "referee-decision":
        try:
            profile = profiles.load_profile(a.profiles_dir, a.journal)
        except ValueError as exc:
            print(str(exc)); return 3
        try:
            d = profiles.referee_decision(profile, a.outputs, self_confirmed=a.self_confirmed, depth=a.depth)
        except ValueError as exc:
            print(str(exc)); return 1
        print(json.dumps(asdict(d))); return 0 if d.allowed else 3
    if a.cmd == "filter-outputs":
        try:
            items = profiles.parse_outputs(a.outputs)
        except ValueError as exc:
            print(str(exc)); return 1
        profile = None
        if a.profiles and a.journal:
            try:
                profile = profiles.load_profile(a.profiles, a.journal)
            except ValueError as exc:
                print(str(exc)); return 1
        kept = profiles.filter_outputs_for_role(items, a.permission, a.depth, profile)
        if not kept:
            print("No output is left: the checked-facts memo is not offered here. Ask the outputs question again.")
            return 1
        print(json.dumps(kept)); return 0
    if a.cmd == "validate-packs":
        try:
            loaded = packs.load_all(a.packs_dir)
        except packs.PackError as exc:
            print(str(exc)); return 1
        print(json.dumps({"packs": {n: p.fixture_status for n, p in loaded.items()},
                          "overlays": [n for n, p in loaded.items() if p.overlay],
                          "cues": {n: p.detection_cues for n, p in loaded.items() if p.overlay},
                          "modules": {n: [{"name": m.name, "label": m.label, "definition": m.definition,
                                           "cues": m.detection_cues} for m in p.modules.values()]
                                      for n, p in loaded.items() if p.modules}})); return 0
    if a.cmd == "run-packs":
        try:
            result = packs.run_packs(packs.load_all(a.packs_dir), [a.type, a.second_type], a.overlay)
        except packs.PackError as exc:
            print(str(exc)); return 1
        print(json.dumps(result)); return 0
    if a.cmd == "core-adjust":
        run_path = Path(a.run_json)
        try:
            run = json.loads(run_path.read_text(encoding="utf-8"))
            adjust = packs.core_adjust(packs.load_all(a.packs_dir), run)
        except (OSError, ValueError, packs.PackError) as exc:
            print(str(exc)); return 1
        workspace = run_path.parent
        try:
            packs.write_core_adjust(workspace, adjust)
        except (OSError, ValueError) as exc:
            print(str(exc)); return 1
        if run.get("core_adjust") != adjust:
            prev = run.get("core_adjust")
            prev_off = set(prev.get("off") or {}) if isinstance(prev, dict) and isinstance(prev.get("off"), dict) else set()
            for agent, entry in adjust["off"].items():
                if agent not in prev_off:
                    audit.warn_dependency(workspace, f"core:{agent}", f"Turned off by design: {entry['reason']}")
            audit.log_event(workspace, "verification", check="core_adjust", off=sorted(adjust["off"]),
                            notes={k: [n["pack"] for n in v] for k, v in adjust["notes"].items()})
            run["core_adjust"] = adjust
            run_path.write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(adjust)); return 0
    if a.cmd == "log":
        data = json.loads(a.data_json)
        print(json.dumps(audit.log_event(a.workspace, a.kind, **data)))
        if a.kind == "output" and data.get("final") is True:
            rundir.mark_finished(Path(a.workspace), Path.home())
            usage.clear_active(Path(a.workspace), Path.home())
            files = ", ".join(str(f) for f in data.get("files") or []) or "none listed"
            progress.log_line(a.workspace, f"Stage 7 done: the run finished. Files written: {files}.")
        return 0
    if a.cmd == "checkin":
        print(json.dumps(checkin.record(a.workspace, a.stop, a.item, a.recommended, a.answer, a.note))); return 0
    if a.cmd == "frontier":
        qs = json.loads(Path(a.questions_json).read_text())
        print(json.dumps(checkin.frontier(qs, a.workspace))); return 0
    if a.cmd == "answered":
        if a.labels:
            print(json.dumps(checkin.answers(a.workspace), sort_keys=True)); return 0
        print(json.dumps(sorted(checkin.answered(a.workspace)))); return 0
    if a.cmd == "render-audit":
        print(audit.render_package(a.workspace)); return 0
    if a.cmd == "run-dir":
        home = Path.home()
        if a.action == "new":
            try:
                out = rundir.new_run(Path(a.pdf), a.cwd, home, a.date, a.search_before, fresh=a.fresh)
            except ValueError as exc:
                print(str(exc)); return 1
        elif a.action == "move":
            out = rundir.move_run(Path(a.run_dir), Path(a.folder), home)
        elif a.action == "find":
            out = rundir.find_unfinished(Path(a.pdf), a.cwd, home)
        else:
            out = rundir.adopt_legacy(Path(a.legacy_workspace), Path(a.pdf), a.cwd, home)
        print(json.dumps(out)); return 0
    if a.cmd == "search-cap":
        try:
            print(rundir.set_search_before(Path(a.workspace), a.date))
        except ValueError as exc:
            print(str(exc)); return 1
        return 0
    if a.cmd == "page-offset":
        try:
            print(rundir.set_page_offset(Path(a.workspace), a.offset))
        except ValueError as exc:
            print(str(exc)); return 1
        return 0
    if a.cmd == "migrate-run":
        answers = checkin.answers(a.workspace)
        print(json.dumps(rundir.migrate_run(Path(a.workspace), answers.get("setup:output", ""),
                                            answers.get("setup:role", "")))); return 0
    if a.cmd == "usage":
        if a.action == "mark":
            print(json.dumps(usage.mark_active(Path(a.workspace), a.cwd, Path.home()))); return 0
        if a.action == "stage-end":
            print(json.dumps(usage.stage_end(Path(a.workspace), a.stage))); return 0
        rep = usage.write_report(Path(a.workspace))
        usage.write_model_record(Path(a.workspace))
        print(json.dumps({"measured": rep["measured"], "total": rep.get("total"), "reason": rep.get("reason", "")}))
        return 0
    if a.cmd == "runlog":
        try:
            print(progress.log_line(a.workspace, a.line))
        except ValueError as exc:
            print(str(exc)); return 1
        return 0
    if a.cmd == "put":
        try:
            print(rundir.put(a.run_dir, a.target, a.staging))
        except ValueError as exc:
            print(str(exc)); return 2
        return 0
    if a.cmd == "stage-header":
        try:
            print(json.dumps({"header": progress.stage_header(a.depth, a.stage, packs=a.packs),
                              "left": progress.time_left(a.depth, a.stage, packs=a.packs)}))
        except ValueError as exc:
            print(str(exc)); return 1
        return 0
    if a.cmd == "scoreboard":
        print(progress.scoreboard(a.workspace)); return 0
    if a.cmd == "recap":
        try:
            cfg = config.load()
            print(progress.recap(a.workspace, a.profiles or None, cfg.codex_enabled,
                                 deps.codex_available(), cfg.provider_facts))
        except ValueError as exc:
            print(str(exc)); return 1
        return 0
    if a.cmd == "sha256":
        print(hashlib.sha256(Path(a.file).read_bytes()).hexdigest()); return 0
    if a.cmd == "readme":
        print(rundir.write_readme(Path(a.workspace), a.profiles or None)); return 0
    if a.cmd == "validated":
        try:
            print(json.dumps(validated.write(a.workspace, a.allow_missing_excerpt)))
        except validated.MissingExcerpt as exc:
            print(str(exc)); return 1
        except validated.UnauditedSummary as exc:
            print(str(exc)); return 3
        except validated.InputError as exc:
            print(str(exc)); return 2
        return 0
    if a.cmd == "check-issues":
        try:
            problems = validated.metaphor_problems(Path(a.file), a.draft)
        except validated.InputError as exc:
            print(str(exc)); return 2
        for p in problems:
            print(p)
        if problems:
            return 1
        print("OK"); return 0
    if a.cmd == "check-minors":
        try:
            missing = validated.minors_missing_from_draft(a.workspace)
        except validated.InputError as exc:
            print(str(exc)); return 2
        for i in missing:
            print(f"Minor {i['id']} ({i.get('title', '')}) was kept, but its summary is not in "
                  "stage-5/draft.md word for word.")
        if missing:
            return 1
        print("OK"); return 0
    if a.cmd == "provider-facts":
        today = date.fromisoformat(a.today) if a.today else None
        if a.action == "show":
            print(json.dumps(config.facts_status(config.load(), today))); return 0
        if not a.provider or not a.trains or not a.retention_days:
            print("set needs a provider, --trains, and --retention-days."); return 1
        days = None
        if a.retention_days != "unsure":
            if not a.retention_days.isdigit():
                print("--retention-days takes a whole number of days or unsure."); return 1
            days = int(a.retention_days)
        trains = {"yes": True, "no": False, "unsure": None}[a.trains]
        print(json.dumps(config.set_facts(a.provider, trains, days, today))); return 0
    if a.cmd == "validate-output":
        text = Path(a.file).read_text(encoding="utf-8")
        kept = json.loads(Path(a.validated).read_text(encoding="utf-8")) if a.validated else None
        run = json.loads(Path(a.run).read_text(encoding="utf-8")) if a.run else {}
        same = run.get("page_offset") == 0
        if a.kind == "issues_list":
            gone = json.loads(Path(a.dropped).read_text(encoding="utf-8")) if a.dropped else None
            errs = outputs.validate_issues_list(text, a.mode, kept, gone, same_pages=same)
        elif a.kind == "editor_memo":
            errs = outputs.validate_editor_memo(text, validated=kept, mode=a.mode, same_pages=same)
        else:
            errs = outputs.validate_report(text, validated=kept, permission=a.permission) if a.kind == "report" \
                else outputs.validate_fix_list(text)
            if a.kind == "report" and a.trace:
                trace = json.loads(Path(a.trace).read_text(encoding="utf-8"))
                errs += outputs.report_trace_errors(text, trace, kept or [])
        if a.run:
            errs += outputs.post_cap_errors(text, run.get("search_before", ""))
        print("\n".join(errs) if errs else "OK"); return 1 if errs else 0
    if a.cmd == "deps":
        print(json.dumps(deps.report(config.load()))); return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
