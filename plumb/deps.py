"""Detect required and optional dependencies without importing heavy packages."""
from __future__ import annotations
import importlib.util
import shutil

REQUIRED = {"pymupdf": "pymupdf", "pdfplumber": "pdfplumber", "requests": "requests", "yaml": "pyyaml"}


def missing_required() -> list[str]:
    return [pkg for mod, pkg in REQUIRED.items() if importlib.util.find_spec(mod) is None]


def codex_available() -> bool:
    return shutil.which("codex") is not None


def report(cfg) -> dict:
    return {
        "missing_required": missing_required(),
        "codex": codex_available(),
    }
