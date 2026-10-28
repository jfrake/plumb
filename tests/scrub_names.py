"""Banned names for the scrub tests, read from an untracked local file so the repository never holds them.

The file is the path in $PLUMB_SCRUB_NAMES, or tests/.scrub_names.local (gitignored). One entry per line:
a plain phrase ("first last", a handle) or "sha256:<hex of the lowercase phrase>". Blank lines and lines
starting with # are ignored. Matching is by whole lowercase words, punctuation dropped, on sequences of
1 to 3 words, so a phrase never matches inside a longer word. With no file, the name checks are skipped.
"""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

LOCAL = Path(__file__).resolve().parent / ".scrub_names.local"
WORD = re.compile(r"[a-z0-9]+")


def names_file() -> Path | None:
    env = os.environ.get("PLUMB_SCRUB_NAMES")
    p = Path(env) if env else LOCAL
    return p if p.is_file() else None


def banned_hashes() -> set:
    p = names_file()
    if p is None:
        return set()
    out = set()
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("sha256:"):
            out.add(line[7:].strip().lower())
        else:
            phrase = " ".join(WORD.findall(line.lower()))
            out.add(hashlib.sha256(phrase.encode()).hexdigest())
    return out


def name_hits(text: str, hashes: set) -> int:
    """How many distinct banned phrases appear in text (the phrases themselves are never returned)."""
    if not hashes:
        return 0
    words = WORD.findall(text.lower())
    grams = {" ".join(words[i:i + n]) for n in (1, 2, 3) for i in range(len(words) - n + 1)}
    return sum(hashlib.sha256(g.encode()).hexdigest() in hashes for g in grams)
