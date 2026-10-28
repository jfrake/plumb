"""Which stress test runs. Standard and Deep run one, and it is never a gate: Codex when the config
enables it, it is on PATH, and the consent record covers OpenAI; otherwise a fresh Claude agent.
Quick has none."""
from __future__ import annotations

from . import consent, depth

ENGINES = ("codex", "claude")


def codex_problem(codex_enabled: bool, codex_on_path: bool, record, needs_zero_retention: bool = False) -> str:
    """Why Codex cannot run the stress test; empty when it can."""
    if not codex_enabled:
        return "Codex is not enabled in the Plumb config."
    if not codex_on_path:
        return "The codex command is not on PATH."
    if record is None:
        return "No consent record was found."
    return " ".join(consent.stress_test_problems(record, needs_zero_retention))


def decide(depth_name: str, codex_enabled: bool, codex_on_path: bool, record,
           needs_zero_retention: bool = False) -> tuple:
    """Return (engine, reason). engine is "codex", "claude", or "" when the depth has no stress
    test. reason says why Codex does not run; it is empty when engine is "codex"."""
    if not depth.limits(depth_name)["stress_test"]:
        return "", "Quick depth has no stress test."
    problem = codex_problem(codex_enabled, codex_on_path, record, needs_zero_retention)
    return ("claude", problem) if problem else ("codex", "")
