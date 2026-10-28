"""Depth tiers: which stages run, loop caps, search budgets, and turn guidance, in one place."""
from __future__ import annotations

DEPTHS = ("quick", "standard", "deep")
# Runs recorded before the rename used "full" for what is now "deep".
ALIASES = {"full": "deep"}

STAGES = {"quick": (0, 1, 2, 7), "standard": tuple(range(8)), "deep": tuple(range(8))}
# Revision cycles allowed in every bounded loop: theory-devil revisions, construction-claim
# audit corrections, the coverage-audit retry, synthesis-critic revisions, the Stage 6
# accuracy retries (before and after adjudication), and the Stage 7 resends.
REVISIONS = {"quick": 1, "standard": 2, "deep": 4}
# Guidance multipliers for agent turns and working-notes length. Output caps never change.
TURN_FACTOR = {"quick": 1, "standard": 1, "deep": 2}
NOTES_FACTOR = {"quick": 1, "standard": 1, "deep": 2}
# Web searches per research agent, worded as the agent files state them.
SEARCH_BUDGET = {
    "setting-research": {"standard": "about 15", "deep": "70-100"},
    "timeline-research": {"standard": "about 15", "deep": "25-35"},
    "contribution-research": {"standard": "about 15", "deep": "25-35"},
    "adjacent-literature": {"standard": "about 15", "deep": "25-35"},
    "boundary-conditions": {"standard": "about 15", "deep": "25-35"},
    "editor-reader": {"standard": "about 10", "deep": "about 20"},
}
STRESS_TEST = {"quick": False, "standard": True, "deep": True}


def normalize(depth: str) -> str:
    d = ALIASES.get(depth, depth)
    if d not in DEPTHS:
        raise ValueError(f"depth must be one of {DEPTHS}")
    return d


def limits(depth: str) -> dict:
    d = normalize(depth)
    return {
        "depth": d,
        "stages": list(STAGES[d]),
        "revisions": REVISIONS[d],
        "turn_factor": TURN_FACTOR[d],
        "notes_factor": NOTES_FACTOR[d],
        "searches": {agent: by_depth[d] for agent, by_depth in SEARCH_BUDGET.items() if d in by_depth},
        "stress_test": STRESS_TEST[d],
    }


# Dispatches that use the mechanical model below Deep; stage files mark them "(mechanical)".
# Every other dispatch, pack agents and the Stage 7 writers included, uses the judgment model.
MECHANICAL = ("compiler",)


PLATFORMS = ("claude", "codex")
# Tier aliases the Claude Task tool accepts. The config is shared across platforms, so Codex must
# never receive one of these, or any other Claude model name.
CLAUDE_ALIASES = ("sonnet", "opus", "haiku")


def _for_platform(model: str, platform: str) -> str:
    if platform == "codex" and (model.lower() in CLAUDE_ALIASES or model.lower().startswith("claude")):
        return "inherit"
    return model


def models(depth: str, configured: dict, platform: str = "claude") -> dict:
    """The model for each role at this depth. Deep uses the judgment model for every agent.
    On Codex a Claude model in the config becomes `inherit` (the session's model)."""
    if platform not in PLATFORMS:
        raise ValueError(f"platform must be one of {PLATFORMS}")
    d = normalize(depth)
    judgment = _for_platform(configured.get("judgment", "inherit"), platform)
    mechanical = judgment if d == "deep" else _for_platform(configured.get("mechanical", "inherit"), platform)
    return {"mechanical": mechanical, "judgment": judgment}


def from_answer(label: str):
    """The depth a recorded `setup:depth` answer names, or None."""
    text = (label or "").lower()
    for word, d in (("quick", "quick"), ("standard", "standard"), ("deep", "deep"), ("full", "deep")):
        if word in text:
            return d
    return None


def from_run(run_cfg: dict, depth_answer: str = "") -> str:
    """The depth of a run from its run.json. Older runs may carry "full" (now deep),
    the key `tier` in place of `depth`, or no depth at all; then the recorded `setup:depth` answer
    decides, and with no answer the run is treated as Standard, the recommended depth."""
    raw = run_cfg.get("depth") or run_cfg.get("tier") or from_answer(depth_answer) or "standard"
    return normalize(str(raw).lower())
