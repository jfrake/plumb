"""Fails if confidential identifiers, personal paths, or detection-evasion language enter the repo."""
from __future__ import annotations
import hashlib
import re
from pathlib import Path

import pytest

from tests.scrub_names import banned_hashes, name_hits, names_file

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "review_workspace", "plumb_output", ".superpowers"}
SELF = Path(__file__).resolve()
_names = names_file()
LOCAL_NAMES = _names.resolve() if _names else None
# Known manuscript numbers, stored only as SHA-256 hashes of the digits.
BANNED_NUMBER_HASHES = {"51a3e8ccea4bba0b30a9d8f075b8ce124ea6ff5ebcd9b02ee6aa2ac85955dedc"}
NUMBER = re.compile(r"\b\d{6,9}\b")
# Author names come from an untracked local file (see tests/scrub_names.py); without it the name check is skipped.
NAME_HASHES = banned_hashes()
EMAIL = re.compile(r"\b([A-Za-z0-9._%+-]+)@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,})\b")
# An address may appear only at a reserved example domain (RFC 2606) or as a no-reply sender.
EMAIL_OK_DOMAIN = re.compile(r"^(?:.*\.)?(?:example\.(?:com|org|net)|example|test|invalid)$", re.I)
EMAIL_OK_LOCAL = re.compile(r"^no-?reply$", re.I)

BANNED = [
    (re.compile(r"\b(ASQ|SMJ|MS|AMJ|AMR|ORSC)-\d{2}-\d{3,}\b"), "journal manuscript ID"),
    (re.compile(r"\bMS-ORG-\d{4}-\d+\b"), "journal manuscript ID"),
    (re.compile(r"\bORSC-MS-\d{4}-\d+\b"), "journal manuscript ID"),
    (re.compile(r"Service/reviews|Plumb pilot papers"), "personal review folder"),
    (re.compile(r"/Users/[A-Za-z]"), "personal absolute path"),
    (re.compile(r"marker-env"), "personal virtualenv path"),
    (re.compile(r"Mitigating AI Detection|avoid(ing)? (AI )?detection|evade detection", re.I), "detection-evasion language"),
    (re.compile(r"claude-(opus|sonnet|haiku)-\d"), "pinned model name"),
]

def _files():
    for p in ROOT.rglob("*"):
        if p.is_dir() or any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.resolve() in (SELF, LOCAL_NAMES) or p.suffix in {".pdf", ".png", ".gif"}:
            continue
        yield p

def test_no_banned_content():
    hits = []
    for p in _files():
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for rx, label in BANNED:
            for m in rx.finditer(text):
                hits.append(f"{p.relative_to(ROOT)}: {label}: {m.group(0)!r}")
        for m in NUMBER.finditer(text):
            if hashlib.sha256(m.group(0).encode()).hexdigest() in BANNED_NUMBER_HASHES:
                hits.append(f"{p.relative_to(ROOT)}: manuscript number")
        for m in EMAIL.finditer(text):
            if not (EMAIL_OK_DOMAIN.match(m.group(2)) or EMAIL_OK_LOCAL.match(m.group(1))):
                hits.append(f"{p.relative_to(ROOT)}: email address: {m.group(0)!r}")
        if name_hits(text, NAME_HASHES):
            hits.append(f"{p.relative_to(ROOT)}: author name or handle")
    assert not hits, "Scrub violations:\n" + "\n".join(hits)


def test_name_check_is_configured_or_skipped_visibly():
    if not NAME_HASHES:
        pytest.skip("no local scrub names file (tests/.scrub_names.local or $PLUMB_SCRUB_NAMES); name check skipped")
    assert name_hits("Alice Example wrote this", {__import__("hashlib").sha256(b"alice example").hexdigest()}) == 1


def test_email_check_allows_only_example_and_noreply_addresses():
    ok = ["someone@example.org", "x@mail.example.com", "noreply@anthropic.com"]
    bad = ["person@university.edu", "someone@company.com"]
    allowed = lambda e: bool(EMAIL_OK_DOMAIN.match(EMAIL.search(e).group(2)) or EMAIL_OK_LOCAL.match(EMAIL.search(e).group(1)))
    assert all(allowed(e) for e in ok) and not any(allowed(e) for e in bad)
