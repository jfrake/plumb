from __future__ import annotations
from pathlib import Path
import pytest
from plumb import packs

ROOT = Path(__file__).resolve().parents[1] / "packs"

def test_archival_pack_loads():
    p = packs.load_pack(ROOT / "archival")
    assert p.name == "archival"
    assert set(p.slots) <= set(packs.SLOTS)
    assert p.checklist and all(i["adjudication"] in packs.ADJUDICATION for i in p.checklist)
    assert all(a.exists() for a in packs.agents_for(p, "diagnose"))

def _mini(tmp_path, pack_yaml, checklist="- {id: c1, text: t, adjudication: paper}\n", fixture=True):
    d = tmp_path / "p"; (d / "agents").mkdir(parents=True); (d / "checklists").mkdir()
    (d / "agents" / "a.md").write_text("x")
    (d / "pack.yaml").write_text(pack_yaml)
    (d / "checklists" / "c.yaml").write_text(checklist)
    if fixture:
        (d / "fixtures" / "f1").mkdir(parents=True)
        (d / "fixtures" / "f1" / "expected.yaml").write_text("status: pending_planting\nowner: author\npaper: planted.pdf\nmust_catch: []\n")
    return d

def test_unknown_slot_rejected(tmp_path):
    d = _mini(tmp_path, "name: p\ndetection_cues: [x]\nslots: {wander: [a.md]}\n")
    with pytest.raises(packs.PackError, match="unknown slot"):
        packs.load_pack(d)

def test_missing_agent_rejected(tmp_path):
    d = _mini(tmp_path, "name: p\ndetection_cues: [x]\nslots: {diagnose: [ghost.md]}\n")
    with pytest.raises(packs.PackError, match="missing agent"):
        packs.load_pack(d)

def test_bad_adjudication_rejected(tmp_path):
    d = _mini(tmp_path, "name: p\ndetection_cues: [x]\nslots: {diagnose: [a.md]}\n",
              checklist="- {id: c1, text: t, adjudication: vibes}\n")
    with pytest.raises(packs.PackError, match="adjudication"):
        packs.load_pack(d)

def test_fixture_required(tmp_path):
    d = _mini(tmp_path, "name: p\ndetection_cues: [x]\nslots: {diagnose: [a.md]}\n", fixture=False)
    with pytest.raises(packs.PackError, match="fixtures"):
        packs.load_pack(d)

def test_pending_fixture_is_reported(tmp_path):
    d = _mini(tmp_path, "name: p\ndetection_cues: [x]\nslots: {diagnose: [a.md]}\n")
    assert packs.load_pack(d).fixture_status == "pending_planting"

def test_overlay_defaults_to_false(tmp_path):
    d = _mini(tmp_path, "name: p\ndetection_cues: [x]\nslots: {diagnose: [a.md]}\n")
    assert packs.load_pack(d).overlay is False

def test_overlay_true_is_read(tmp_path):
    d = _mini(tmp_path, "name: p\noverlay: true\ndetection_cues: [x]\nslots: {diagnose: [a.md]}\n")
    assert packs.load_pack(d).overlay is True

@pytest.mark.parametrize("value", ['"true"', "yes-please", "1"])
def test_overlay_must_be_a_boolean(tmp_path, value):
    d = _mini(tmp_path, f"name: p\noverlay: {value}\ndetection_cues: [x]\nslots: {{diagnose: [a.md]}}\n")
    with pytest.raises(packs.PackError, match="overlay"):
        packs.load_pack(d)

def _built():
    a = packs.Pack(name="archival", path=Path("."), detection_cues=[], slots={})
    c = packs.Pack(name="computational", path=Path("."), detection_cues=[], slots={}, overlay=True)
    return {"archival": a, "computational": c}

def test_run_packs_types_then_overlays():
    r = packs.run_packs(_built(), ["Archival", "none"], ["computational"])
    assert r == {"packs": ["archival", "computational"], "overlays": ["computational"], "types_without_pack": [],
                 "primary_pack": "archival"}

def test_run_packs_never_lists_a_pack_twice():
    r = packs.run_packs(_built(), ["computational", "archival"], ["computational"])
    assert r["packs"] == ["computational", "archival"] and r["overlays"] == []

def test_run_packs_omits_skipped_overlays():
    r = packs.run_packs(_built(), ["archival", ""], [])
    assert r == {"packs": ["archival"], "overlays": [], "types_without_pack": [], "primary_pack": "archival"}

def test_run_packs_reports_types_without_pack():
    r = packs.run_packs(_built(), ["qualitative", "other"], [])
    assert r == {"packs": [], "overlays": [], "types_without_pack": ["qualitative", "other"],
                 "primary_pack": None}

def test_run_packs_rejects_an_unknown_overlay():
    with pytest.raises(packs.PackError, match="overlay"):
        packs.run_packs(_built(), ["archival"], ["archival"])


MODULE_YAML = (
    "name: m1\nlabel: M\ndefinition: \"A design.\"\ndetection_cues: [cue]\n"
    "encouragement: []\nchecklist:\n  - {id: MM1, text: t, adjudication: paper}\n"
)


def _with_module(tmp_path, module_yaml=MODULE_YAML, md=True, fixture_module="m1"):
    d = _mini(tmp_path, "name: p\ndetection_cues: [x]\nslots: {diagnose: [a.md]}\n")
    (d / "modules").mkdir()
    (d / "modules" / "m1.yaml").write_text(module_yaml)
    if md:
        (d / "modules" / "m1.md").write_text("# M\n")
    if fixture_module:
        (d / "fixtures" / "m1-1").mkdir()
        (d / "fixtures" / "m1-1" / "expected.yaml").write_text(
            f"status: pending_planting\nmodule: {fixture_module}\nmust_catch: []\n")
    return d


def test_pack_without_modules_has_none(tmp_path):
    d = _mini(tmp_path, "name: p\ndetection_cues: [x]\nslots: {diagnose: [a.md]}\n")
    assert packs.load_pack(d).modules == {}


def test_module_loads_and_joins_the_checklist(tmp_path):
    p = packs.load_pack(_with_module(tmp_path))
    m = p.modules["m1"]
    assert m.label == "M" and m.definition == "A design." and m.detection_cues == ["cue"]
    assert [i["id"] for i in m.checklist] == ["MM1"] and m.encouragement == []
    assert [i["id"] for i in p.checklist] == ["c1", "MM1"]


def test_module_without_its_prompt_file_is_rejected(tmp_path):
    with pytest.raises(packs.PackError, match="modules/m1.md"):
        packs.load_pack(_with_module(tmp_path, md=False))


def test_module_bad_adjudication_is_rejected(tmp_path):
    with pytest.raises(packs.PackError, match="adjudication"):
        packs.load_pack(_with_module(tmp_path, MODULE_YAML.replace("adjudication: paper", "adjudication: vibes")))


def test_duplicate_ids_across_checklist_and_modules_are_rejected(tmp_path):
    with pytest.raises(packs.PackError, match="duplicate checklist ids: c1"):
        packs.load_pack(_with_module(tmp_path, MODULE_YAML.replace("id: MM1", "id: c1")))


def test_encouragement_ids_must_be_module_checks(tmp_path):
    with pytest.raises(packs.PackError, match="encouragement id MM9"):
        packs.load_pack(_with_module(tmp_path, MODULE_YAML.replace("encouragement: []", "encouragement: [MM9]")))


def test_module_needs_a_fixture_that_names_it(tmp_path):
    with pytest.raises(packs.PackError, match="no fixture"):
        packs.load_pack(_with_module(tmp_path, fixture_module=""))


def _load_err(d, match):
    with pytest.raises(packs.PackError, match=match) as e:
        packs.load_pack(d)
    assert str(e.value).startswith("p: ")


def test_module_yaml_not_a_mapping_is_rejected(tmp_path):
    _load_err(_with_module(tmp_path, "- just\n- a list\n"), "modules/m1.yaml must be a mapping")


def test_module_checklist_not_list_of_mappings_is_rejected(tmp_path):
    _load_err(_with_module(tmp_path, MODULE_YAML.replace("  - {id: MM1, text: t, adjudication: paper}", "  - oops")),
              "checklist")
    _load_err(_with_module(tmp_path / "x",
                           MODULE_YAML.split("checklist:")[0] + "checklist: notalist\n"), "checklist")


def test_module_empty_or_null_checklist_is_rejected(tmp_path):
    base = MODULE_YAML.split("checklist:")[0]
    _load_err(_with_module(tmp_path / "a", base + "checklist: []\n"), "checklist")
    _load_err(_with_module(tmp_path / "b", base + "checklist:\n"), "checklist")


def test_module_missing_required_key_is_rejected(tmp_path):
    _load_err(_with_module(tmp_path, MODULE_YAML.replace("label: M\n", "")), "missing label")


def test_module_name_must_match_file_stem(tmp_path):
    _load_err(_with_module(tmp_path, MODULE_YAML.replace("name: m1", "name: other")), "does not match")


def test_module_names_must_be_unique(tmp_path):
    d = _with_module(tmp_path)
    (d / "modules" / "m2.yaml").write_text(MODULE_YAML.replace("MM1", "MM2"))
    (d / "modules" / "m2.md").write_text("# M\n")
    # a second file cannot reuse a name; the stem check and the duplicate check both refuse it
    _load_err(d, "does not match|duplicate module")


def test_encouragement_bare_string_is_rejected(tmp_path):
    _load_err(_with_module(tmp_path, MODULE_YAML.replace("encouragement: []", "encouragement: MM1")),
              "encouragement must be a list")


def test_fixture_not_a_mapping_is_rejected(tmp_path):
    d = _with_module(tmp_path)
    (d / "fixtures" / "m1-1" / "expected.yaml").write_text("- a\n- b\n")
    _load_err(d, "expected.yaml must be a mapping")


def test_fixture_naming_unknown_module_is_rejected(tmp_path):
    d = _with_module(tmp_path)
    (d / "fixtures" / "z-1").mkdir()
    (d / "fixtures" / "z-1" / "expected.yaml").write_text("status: pending_planting\nmodule: ghost\nmust_catch: []\n")
    _load_err(d, "names module 'ghost'")


def test_fixture_module_not_a_string_is_rejected(tmp_path):
    d = _with_module(tmp_path)
    (d / "fixtures" / "m1-1" / "expected.yaml").write_text("status: pending_planting\nmodule: [m1]\nmust_catch: []\n")
    _load_err(d, "module must be a string")


def test_module_labels_must_be_unique(tmp_path):
    d = _with_module(tmp_path)
    (d / "modules" / "m2.yaml").write_text(MODULE_YAML.replace("name: m1", "name: m2").replace("MM1", "MM2"))
    (d / "modules" / "m2.md").write_text("# M\n")
    (d / "fixtures" / "m2-1").mkdir()
    (d / "fixtures" / "m2-1" / "expected.yaml").write_text("status: pending_planting\nmodule: m2\nmust_catch: []\n")
    _load_err(d, "share the label 'M'")
