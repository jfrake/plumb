"""Load and validate paper-type packs, and work out what the core does differently for a run."""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

SLOTS = {"verify": 1, "context": 2, "theory": 3, "diagnose": 4, "severity": 5, "audit": 6}
ADJUDICATION = {"paper", "external", "judgment"}

CORE = Path(__file__).resolve().parents[1] / "skills" / "review"
CORE_AGENTS = CORE / "agents"
STRESS_PROMPT = CORE / "shared" / "stress-test-prompt.md"

# A paper type the manuscript audit may still name, and the pack that serves it.
TYPE_ALIASES = {"correlational": "archival"}

# Core agents a pack may turn off, and the output files each leaves as a stub.
OFFABLE = {
    "construction-ledger-producer.md": ["stage-2/construction_ledger.md"],
    "setting-research.md": ["stage-2/setting.md"],
    "timeline-research.md": ["stage-2/timeline.md"],
    "face-validity.md": ["stage-4/face_validity.md"],
}
# Turning off the ledger producer turns off the whole ledger unit.
LEDGER_UNIT = {
    "construction-ledger-checker.md": [],
    "construction-claim-audit.md": ["stage-5/construction_claim_audit.md"],
}
# Notes may also go to these, which are not agent files.
NOTE_TARGETS = {"stage-4-compiler", "stress-test-prompt"}
# A note to another pack's agent is keyed by its path in the packs folder.
PACK_AGENT_KEY = re.compile(r"^packs/([a-z0-9-]+)/agents/([a-z0-9-]+\.md)$")
# Agent files that take no notes of their own, and why.
NO_NOTES = {
    "construction-ledger-checker.md": "note construction-ledger-producer.md instead; "
                                      "the ledger unit passes its notes to the checker",
    "stress-tester.md": "note stress-test-prompt instead; the stress tester reads its notes from its prompt file",
    "hypothesis-ledger-checker.md": "note hypothesis-ledger-producer.md instead; "
                                    "the ledger pair passes its notes to the checker",
}


class PackError(Exception):
    pass


@dataclass
class Pack:
    name: str
    path: Path
    detection_cues: list
    slots: dict
    turns_off: list = field(default_factory=list)
    severity_rules: list = field(default_factory=list)
    checklist: list = field(default_factory=list)
    fixture_status: str = "pending_planting"
    overlay: bool = False
    core_notes: dict = field(default_factory=dict)
    read_checkin_lines: list = field(default_factory=list)
    modules: dict = field(default_factory=dict)


@dataclass
class Module:
    name: str
    label: str
    definition: str
    detection_cues: list
    checklist: list
    encouragement: list = field(default_factory=list)


def _load_modules(path: Path, errors: list) -> dict:
    """Design modules: modules/<name>.yaml plus modules/<name>.md, loaded only by a pack agent."""
    modules = {}
    for f in sorted((path / "modules").glob("*.yaml")):
        meta = yaml.safe_load(f.read_text(encoding="utf-8"))
        if not isinstance(meta, dict):
            errors.append(f"modules/{f.name} must be a mapping")
            continue
        name = meta.get("name") or f.stem
        if name != f.stem:
            errors.append(f"module name {name!r} does not match its file name modules/{f.name}")
            continue
        if name in modules:
            errors.append(f"duplicate module name '{name}'")
            continue
        missing = [k for k in ("label", "definition", "detection_cues", "checklist") if k not in meta]
        if missing:
            errors.append(f"modules/{f.name} missing {', '.join(missing)}")
            continue
        items = meta["checklist"]
        if not isinstance(items, list) or not items or not all(isinstance(i, dict) for i in items):
            errors.append(f"modules/{f.name} checklist must be a non-empty list of mappings")
            continue
        if not isinstance(meta["detection_cues"], list):
            errors.append(f"modules/{f.name} detection_cues must be a list")
            continue
        enc = meta.get("encouragement") or []
        if not isinstance(enc, list):
            errors.append(f"modules/{f.name} encouragement must be a list of checklist ids")
            continue
        if not (path / "modules" / f"{name}.md").exists():
            errors.append(f"module '{name}' has no modules/{name}.md")
        ids = {i.get("id") for i in items}
        for item in items:
            if item.get("adjudication") not in ADJUDICATION:
                errors.append(f"modules/{f.name}:{item.get('id')} has adjudication {item.get('adjudication')!r}; "
                              "must be paper, external, or judgment")
        for e in enc:
            if e not in ids:
                errors.append(f"module '{name}' encouragement id {e} is not in its checklist")
        modules[name] = Module(name=name, label=meta["label"], definition=meta["definition"],
                               detection_cues=meta["detection_cues"], checklist=items, encouragement=enc)
    by_label = {}
    for m in modules.values():
        by_label.setdefault(m.label, []).append(m.name)
    for label, names in by_label.items():
        if len(names) > 1:
            errors.append(f"modules {', '.join(names)} share the label {label!r}")
    return modules


def _turns_off(raw, overlay: bool, errors: list) -> list:
    """Each entry becomes {"agent": <file>, "reason": <text or "">}."""
    if not isinstance(raw, list):
        errors.append("turns_off must be a list")
        return []
    if raw and overlay:
        errors.append("an overlay never turns a core agent off; remove turns_off or move its entries to core_notes")
        return []
    out = []
    for e in raw:
        if isinstance(e, str):
            agent, reason = e, ""
        elif isinstance(e, dict) and "agent" in e and set(e) <= {"agent", "reason"}:
            agent, reason = e["agent"], e.get("reason") or ""
        else:
            errors.append(f"turns_off entry {e!r} must be an agent file name or a mapping with 'agent' and 'reason'")
            continue
        if not isinstance(agent, str) or not isinstance(reason, str):
            errors.append(f"turns_off entry {e!r}: 'agent' and 'reason' must be text")
            continue
        if agent not in OFFABLE:
            hint = f" (did you mean '{agent}.md'?)" if f"{agent}.md" in OFFABLE else ""
            errors.append(f"turns_off names '{agent}'{hint}; a pack may turn off only {', '.join(sorted(OFFABLE))}")
            continue
        out.append({"agent": agent, "reason": reason.strip()})
    return out


def _core_notes(path: Path, raw, errors: list) -> dict:
    """Map each target to its note texts, with `file:` notes read from the pack."""
    if not isinstance(raw, dict):
        errors.append("core_notes must map a core agent file to a note")
        return {}
    out = {}
    for target, notes in raw.items():
        if target in NO_NOTES:
            errors.append(f"core_notes key '{target}': {NO_NOTES[target]}")
            continue
        is_agent = isinstance(target, str) and target.endswith(".md") and (CORE_AGENTS / target).is_file()
        pack_agent = PACK_AGENT_KEY.match(target) if isinstance(target, str) else None
        if pack_agent and not (path.parent / pack_agent.group(1) / "agents" / pack_agent.group(2)).is_file():
            errors.append(f"core_notes key '{target}' names no agent file in the packs folder")
            continue
        if target not in NOTE_TARGETS and not is_agent and not pack_agent:
            errors.append(f"core_notes key '{target}' is not a file in skills/review/agents/, "
                          f"packs/<pack>/agents/<file>, or one of {', '.join(sorted(NOTE_TARGETS))}")
            continue
        texts = []
        for note in notes if isinstance(notes, list) else [notes]:
            if not isinstance(note, dict) or len(note) != 1 or not set(note) <= {"text", "file"}:
                errors.append(f"core_notes '{target}': each note is {{text: ...}} or {{file: ...}}, exactly one")
                continue
            if "text" in note:
                text = note["text"]
                if not isinstance(text, str) or not text.strip():
                    errors.append(f"core_notes '{target}': text is empty")
                    continue
                texts.append(text.strip())
                continue
            rel = note["file"]
            f = (path / rel).resolve() if isinstance(rel, str) else None
            if f is None or path.resolve() not in f.parents or not f.is_file():
                errors.append(f"core_notes '{target}': note file '{rel}' not found in the pack")
                continue
            try:
                text = f.read_text(encoding="utf-8").strip()
            except UnicodeDecodeError:
                errors.append(f"core_notes '{target}': note file '{rel}' is not UTF-8")
                continue
            if not text:
                errors.append(f"core_notes '{target}': note file '{rel}' is empty")
                continue
            texts.append(text)
        if texts:
            out[target] = texts
    return out


def _read_checkin_lines(raw, errors: list) -> list:
    ok = isinstance(raw, list) and all(
        isinstance(x, str) and x.strip().endswith(":") and len(x.strip()) > 1 for x in raw)
    if not ok:
        errors.append("read_checkin_lines must be a list of fingerprint labels, each ending in ':' "
                      "(for example 'Studies:')")
        return []
    return [x.strip() for x in raw]


def load_pack(path) -> Pack:
    path = Path(path)
    meta_file = path / "pack.yaml"
    if not meta_file.exists():
        raise PackError(f"{path.name}: missing pack.yaml")
    meta = yaml.safe_load(meta_file.read_text(encoding="utf-8")) or {}
    errors = [f"pack.yaml missing '{k}'" for k in ("name", "detection_cues", "slots") if k not in meta]
    overlay = meta.get("overlay", False)
    if not isinstance(overlay, bool):
        errors.append(f"overlay must be true or false, not {overlay!r}")
    slots = meta.get("slots") or {}
    for slot, agents in slots.items():
        if slot not in SLOTS:
            errors.append(f"unknown slot '{slot}'")
        for a in agents or []:
            if not (path / "agents" / a).exists():
                errors.append(f"slot '{slot}' names missing agent file agents/{a}")
    turns_off = _turns_off(meta.get("turns_off") or [], overlay is True, errors)
    core_notes = _core_notes(path, meta.get("core_notes") or {}, errors)
    read_lines = _read_checkin_lines(meta.get("read_checkin_lines") or [], errors)
    checklist = []
    for f in sorted((path / "checklists").glob("*.yaml")):
        raw_items = yaml.safe_load(f.read_text(encoding="utf-8")) or []
        if not isinstance(raw_items, list) or not all(isinstance(i, dict) for i in raw_items):
            errors.append(f"checklists/{f.name} must be a list of mappings")
            continue
        for item in raw_items:
            if item.get("adjudication") not in ADJUDICATION:
                errors.append(f"{f.name}:{item.get('id')} has adjudication {item.get('adjudication')!r}; "
                              "must be paper, external, or judgment")
            checklist.append(item)
    modules = _load_modules(path, errors)
    for m in modules.values():
        checklist.extend(m.checklist)
    seen, dupes = set(), []
    for item in checklist:
        if item.get("id") in seen:
            dupes.append(str(item.get("id")))
        seen.add(item.get("id"))
    if dupes:
        errors.append("duplicate checklist ids: " + ", ".join(dupes))
    fixtures = sorted((path / "fixtures").glob("*/expected.yaml"))
    if not fixtures:
        errors.append("pack has no fixtures/*/expected.yaml")
    fixture_modules = set()
    for f in fixtures:
        exp = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        if not isinstance(exp, dict):
            errors.append(f"fixtures/{f.parent.name}/expected.yaml must be a mapping")
            continue
        if exp.get("module") is not None:
            if not isinstance(exp["module"], str):
                errors.append(f"fixtures/{f.parent.name}/expected.yaml module must be a string, "
                              f"not {exp['module']!r}")
                continue
            if exp["module"] not in modules:
                errors.append(f"fixtures/{f.parent.name}/expected.yaml names module {exp['module']!r}, "
                              "which does not exist")
            fixture_modules.add(exp["module"])
    for name in modules:
        if name not in fixture_modules:
            errors.append(f"module '{name}' has no fixture whose expected.yaml names it")
    if errors:
        raise PackError(f"{path.name}: " + "; ".join(errors))
    statuses = {(yaml.safe_load(f.read_text()) or {}).get("status", "pending_planting") for f in fixtures}
    return Pack(name=meta["name"], path=path, detection_cues=meta["detection_cues"], slots=slots,
                turns_off=turns_off, severity_rules=meta.get("severity_rules") or [],
                checklist=checklist, fixture_status="ready" if statuses == {"ready"} else "pending_planting",
                overlay=overlay, core_notes=core_notes, read_checkin_lines=read_lines, modules=modules)


def load_all(root) -> dict:
    return {p.name: load_pack(p) for p in sorted(Path(root).iterdir()) if (p / "pack.yaml").exists()}


def agents_for(pack: Pack, slot: str) -> list:
    return [pack.path / "agents" / a for a in pack.slots.get(slot, [])]


def run_packs(built: dict, types: list, overlays: list) -> dict:
    """The packs a run uses: chosen types in order, then chosen overlays, never twice.
    primary_pack is the built pack for the first chosen type (after blanks and "none" are skipped),
    or None when that type has no pack."""
    out, over, missing = [], [], []
    primary, first = None, True
    for t in types:
        t = (t or "").strip().lower()
        t = TYPE_ALIASES.get(t, t)
        if t in ("", "none"):
            continue
        if first:
            primary, first = (t if t in built else None), False
        if t in built:
            if t not in out:
                out.append(t)
        elif t not in missing:
            missing.append(t)
    for o in overlays:
        o = (o or "").strip().lower()
        if o not in built or not built[o].overlay:
            raise PackError(f"'{o}' is not a built overlay pack")
        if o not in out:
            out.append(o)
            over.append(o)
    return {"packs": out, "overlays": over, "types_without_pack": missing, "primary_pack": primary}


def core_adjust(built: dict, run: dict) -> dict:
    """Which core agents are off for this run, and which pack notes each core agent gets.

    An agent is off only when every type pack in the run lists it and every chosen type has a
    pack; an overlay pack never counts, even when the user chose it as a paper type. Notes apply
    whenever their pack is in the run; a note to another pack's agent applies only when that pack
    runs too. An overlay pack still counts as an overlay for turn-offs when the user chose it as a
    paper type, and its notes then carry the type role the user chose. read_lines lists, per pack, the fingerprint labels shown at the read check-in."""
    if not isinstance(run, dict):
        raise PackError("run.json must be a JSON object")
    names = run.get("packs") or []
    if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
        raise PackError("run.json 'packs' must be a list of pack names")
    names = list(names)
    for n in names:
        if n not in built:
            raise PackError(f"run.json lists pack '{n}', which is not built")
    overlays = set(run.get("overlays") or [])
    primary = run.get("primary_pack")
    type_packs = [n for n in names if n not in overlays and not built[n].overlay]
    off = {}
    if type_packs and not (run.get("types_without_pack") or []):
        common = set.intersection(*({e["agent"] for e in built[n].turns_off} for n in type_packs))
        for agent in sorted(common):
            parts = []
            for n in type_packs:
                for e in built[n].turns_off:
                    if e["agent"] == agent:
                        parts.append(f"the {n} pack" + (f": {e['reason']}" if e["reason"] else ""))
            off[agent] = {"reason": "Turned off by " + "; ".join(parts), "stubs": list(OFFABLE[agent])}
        if "construction-ledger-producer.md" in off:
            reason = off["construction-ledger-producer.md"]["reason"]
            for agent, stubs in LEDGER_UNIT.items():
                off[agent] = {"reason": reason, "stubs": list(stubs)}
    notes = {}
    for n in names:
        role = "overlay" if n in overlays else ("primary type" if n == primary else "second type")
        for target, texts in built[n].core_notes.items():
            targets = [target]
            if target == "construction-ledger-producer.md":
                targets.append("construction-ledger-checker.md")
            if target == "hypothesis-ledger-producer.md":
                targets.append("hypothesis-ledger-checker.md")
            for t in targets:
                m = PACK_AGENT_KEY.match(t)
                if t in off or (m and m.group(1) not in names):
                    continue
                notes.setdefault(t, []).extend({"pack": n, "role": role, "text": x} for x in texts)
    read_lines = {n: list(built[n].read_checkin_lines) for n in names if built[n].read_checkin_lines}
    return {"off": off, "notes": notes, "read_lines": read_lines}


def stub_text(reason: str) -> str:
    return (f"# Not run\n\n{reason.rstrip('.')}. This check did not run for this paper, "
            "and this file holds no findings.\n")


def _is_stub(f: Path) -> bool:
    try:
        return f.is_file() and f.read_text(encoding="utf-8").startswith("# Not run")
    except (OSError, ValueError):
        return False


def write_core_adjust(workspace, adjust: dict) -> list:
    """Write each turned-off agent's stub files and, when the stress test has notes, its per-run prompt.
    An existing file is overwritten only when it is itself a stub ("# Not run"); a real output is left
    alone. Stubs for agents no longer turned off are removed. Returns the paths written, relative to the
    workspace."""
    workspace = Path(workspace)
    written = []
    wanted = {rel for entry in adjust["off"].values() for rel in entry["stubs"]}
    for rel in sorted({r for stubs in list(OFFABLE.values()) + list(LEDGER_UNIT.values()) for r in stubs} - wanted):
        if _is_stub(workspace / rel):
            (workspace / rel).unlink()
    for entry in adjust["off"].values():
        for rel in entry["stubs"]:
            f = workspace / rel
            if f.exists() and not _is_stub(f):
                continue
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(stub_text(entry["reason"]), encoding="utf-8")
            written.append(rel)
    prompt = workspace / "stage-6" / "stress_prompt.md"
    notes = adjust["notes"].get("stress-test-prompt")
    if notes:
        prompt.parent.mkdir(parents=True, exist_ok=True)
        body = "\n\n".join(f"Pack note ({n['pack']}, {n['role']}): {n['text']}" for n in notes)
        prompt.write_text(STRESS_PROMPT.read_text(encoding="utf-8").rstrip()
                          + "\n\n## Pack notes for this paper\n\n" + body + "\n", encoding="utf-8")
        written.append("stage-6/stress_prompt.md")
    elif prompt.exists():
        prompt.unlink()
    return written
