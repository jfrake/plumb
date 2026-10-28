"""Structural validators for the three outputs. They never judge content."""
from __future__ import annotations
import re

SEVERITIES = ("Undermines the main claim", "Weakens a claim", "Minor")
TAGS = ("quick fix", "new analysis", "new data", "can't fix, narrow the claim")

# Decision vocabulary for editorial recommendations
_DECISION_WORDS = r"(?:accept(?:ance|ed)?|reject(?:ion|ing)?|major\s+revisions?|minor\s+revisions?|revisions|major\s+r&r|minor\s+r&r|r&r|revise\s+and\s+resubmit)"

# Speaker forms: "I recommend", "we recommend", "I would recommend", "we would recommend"
_WHO_RECOMMENDS = r"\b(?:i|we)(?:\s+would)?\s+recommend"
# Possessive forms: "my recommendation", "our recommendation"
_WHOSE_RECOMMENDATION = r"\b(?:my|our)\s+recommendation"

# Patterns to detect editorial recommendations
_RECO_PATTERNS = [
    # Pattern 1: Standalone decision on its own line
    re.compile(rf"^\s*{_DECISION_WORDS}\s*\.?\s*$", re.I | re.M),
    # Pattern 2: Label followed by decision word in same sentence
    re.compile(rf"(?:recommendation|recommend|recommended\s+decision|decision)\s*:\s*{_DECISION_WORDS}", re.I),
    # Pattern 3: "My/Our recommendation is to ..." or similar
    re.compile(rf"{_WHOSE_RECOMMENDATION}\s+is\s+(?:to\s+)?(?:accept|reject|major|minor|revise|r&r)", re.I),
    # Pattern 4: "I/We (would) recommend ..." followed by decision noun (not verb). A bare
    # "revisions" or "publication" followed by what to revise or publish ("revisions to Section 2",
    # "publication of the code", "publication bias diagnostics") is fix advice.
    re.compile(rf"{_WHO_RECOMMENDS}\s+(?:a\s+)?(?:(?:accept(?:ance|ed)?|reject(?:ion)?)\b"
               r"|publication\b(?!\s+(?:bias|of|quality)\b|-)"
               r"|major\s+revisions?|minor\s+revisions?"
               r"|revisions?\b(?!\s+(?:to|of|in|on|for|that|where|so)\b)"
               r"|major\s+r&r|minor\s+r&r|r&r|revise\s+and\s+resubmit)", re.I),
    # Pattern 5: "I/We recommend that the editor <verb>"
    re.compile(rf"{_WHO_RECOMMENDS}\s+(?:that\s+)?(?:(?:the\s+)?editor\s+)?(?:reject|accept|revise)\b", re.I),
    # Pattern 6: "I/We recommend the paper be <verb>ed"
    re.compile(rf"{_WHO_RECOMMENDS}\s+(?:that\s+)?(?:(?:(?:the|this)\s+)?(?:paper|manuscript|submission|article)|it)"
               r"\s+be\s+(?:accept|reject)", re.I),
    # Pattern 7: "I/We (would) recommend <verb>ing the paper"
    re.compile(rf"{_WHO_RECOMMENDS}\s+(?:reject|accept)ing\s+(?:the\s+)?paper", re.I),
    # Pattern 8: "Recommend: ..." label
    re.compile(r"recommend\s*:\s*(?:accept|reject|major|minor|revise|r&r)", re.I),
]


def has_recommendation(text: str) -> bool:
    """Detect editorial recommendations. Excludes casual uses like 'I recommend clustering'."""
    # Fix advice that starts like a recommendation: "I recommend you ...", "we recommend adding ...".
    # Each exclusion is tested at the start of the match it would excuse, so one piece of fix
    # advice never excuses a verdict elsewhere in the text.
    exclusion_patterns = [
        re.compile(rf"{_WHO_RECOMMENDS}\s+(?:you|adding|a\s+placebo|clustering)", re.I),
        re.compile(rf"{_WHO_RECOMMENDS}\s+you\s+revise", re.I),
    ]
    for pattern in _RECO_PATTERNS:
        for match in pattern.finditer(text):
            if pattern is not _RECO_PATTERNS[0] and pattern is not _RECO_PATTERNS[1]:
                if any(excl.match(text, match.start()) for excl in exclusion_patterns):
                    continue
            # "major revision of Section 2" is fix advice, not a decision
            context = text[match.end():match.end() + 15]
            if "of" in context and "section" in context.lower():
                if "decision" not in text[match.start():match.end()].lower():
                    continue
            return True
    return False


def validate_fix_list(text: str, max_words: int = 2200, require_items: bool = True,
                      metaphors: bool = True) -> list:
    errs = []

    # Check for required "## Issues" header
    if "## Issues" not in text:
        errs.append("Missing the '## Issues' section.")

    heads = list(re.finditer(r"^### (\d+)\. (.+)$", text, re.M))
    if not heads and require_items:
        errs.append("No numbered '### N. title' items found.")
    nums = [int(h.group(1)) for h in heads]
    if nums != list(range(1, len(nums) + 1)):
        errs.append("Items must be numbered 1..N in order.")
    ranks = []
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        block = text[h.end():end]
        sev = re.search(r"^Severity: (.+)$", block, re.M)
        if not sev:
            errs.append(f"Item {i + 1} needs a 'Severity:' line using one of: {', '.join(SEVERITIES)}.")
        else:
            sev_value = sev.group(1).strip()
            if sev_value not in SEVERITIES:
                errs.append(f"Item {i + 1} has Severity '{sev_value}'; use exactly one of: {', '.join(SEVERITIES)}.")
            else:
                ranks.append(SEVERITIES.index(sev_value))
        tag = re.search(r"^Fix: (.+)$", block, re.M)
        if not tag:
            errs.append(f"Item {i + 1} needs a 'Fix:' line using one of: {', '.join(TAGS)}.")
        else:
            tag_value = tag.group(1).strip()
            if tag_value not in TAGS:
                errs.append(f"Item {i + 1} has Fix '{tag_value}'; use exactly one of: {', '.join(TAGS)}.")
    if ranks != sorted(ranks):
        errs.append("Items must be ordered by consequence: more severe items first.")
    if "## What I left out" not in text:
        errs.append("Missing the '## What I left out' section.")
    if len(text.split()) > max_words:
        errs.append(f"Fix list runs {len(text.split())} words; the ceiling is {max_words}.")
    if has_recommendation(text):
        errs.append("Output contains an editorial recommendation.")
    if metaphors:
        errs += metaphor_errors(text)
    return errs


def _copied(validated, fields=("title", "summary", "why_it_matters", "settle")) -> list:
    """The validated.json text a writer copies word for word, exempt from the metaphor check here
    because `plumb check-issues` checks it where synthesis writes it."""
    return [v[k] for v in validated or [] for k in fields if isinstance(v.get(k), str)]


# The last line of a report written for a referee (permission "journal").
DISCLOSURE_LINE = "I used Plumb, an AI review tool, to check this report. The judgments and conclusions are my own."


def validate_report(text: str, max_words: int = 3000, validated=None, permission: str = "") -> list:
    """Given an empty validated.json, a report with no comment and the one NO_ISSUES sentence is valid.
    With permission "journal", the last line must be DISCLOSURE_LINE exactly."""
    errs = []
    if permission == "journal":
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if not lines or lines[-1] != DISCLOSURE_LINE:
            errs.append(f"A referee's report ends with this disclosure line, word for word: '{DISCLOSURE_LINE}'")
    heads = list(re.finditer(r"^(\d+)\. ", text, re.M))
    nums = [int(m.group(1)) for m in heads]
    empty = validated == [] and not nums and REPORT_NO_ISSUES in text
    if not empty and (not nums or nums != list(range(1, len(nums) + 1))):
        errs.append("Comments must be numbered 1..N in a single sequence.")
    for m in heads:
        if m.start() > 0 and not text[:m.start()].endswith("\n\n"):
            errs.append(f"Comment {m.group(1)} needs a blank line before it. If it is a sub-point inside a comment, write it as prose (First, Second, ...) instead of a numbered line.")
    if re.search(r"^#", text, re.M):
        errs.append("Plain text only: remove '#' headers.")
    if re.search(r"^\s*[-*] ", text, re.M):
        errs.append("Plain text only: remove bullet lines.")
    if len(text.split()) > max_words:
        errs.append(f"Report runs {len(text.split())} words; the ceiling is {max_words}.")
    if has_recommendation(text):
        errs.append("Output contains an editorial recommendation.")
    errs += verdict_errors(text)
    errs += tool_talk_errors(text)
    errs += metaphor_errors(text)
    return errs


REPORT_NO_ISSUES = "I have no concerns that need to be raised with the authors."
# Phrases that only the review tool would write. The mock report reads as a human referee's.
_TOOL_TALK = re.compile(r"\bPlumb\b|(?i:\bcheck-ins?\b|\bskipped by design\b|\bturned off by design\b|"
                        r"\bsurvived the (?:checks|audit)\b|\bthe review tool\b)|\b[\w-]+\.(?:json|md)\b")


def tool_talk_errors(text: str) -> list:
    """The report never talks about the tool that produced it. The disclosure line is the one exception."""
    body = "\n".join(l for l in text.splitlines() if l.strip() != DISCLOSURE_LINE)
    found = sorted({m.group(0) for m in _TOOL_TALK.finditer(body)})
    if not found:
        return []
    return ["Write the report as a human referee would: leave out anything about the review tool, its checks, "
            "or what was or was not run. Found: " + ", ".join(repr(f) for f in found[:5]) + "."]


# Figurative phrases that are almost never literal in a referee report. "Carry" counts only with an
# argument as its object ("carries the contribution"), so "firms carry debt", "carries a negative
# sign", and "carries a weight equal to" pass. Bare "do the work", "lean on", and "stand on" are
# often literal and are left to the prompt rule.
_METAPHOR = re.compile(r"""\b(?:
    load[-\s]bearing
  | (?:rest|rests|rested|resting)\s+on
  | (?:hinge|hinges|hinged|hinging)\s+on
  | (?:does|did|doing)\s+the\s+work
  | heavy[-\s]lifting
  | (?:bear|bears|bore|bearing)\s+on(?!\s+average)
  | (?:stand|stands|stood|standing)\s+on\s+its\s+own
  | (?:sit|sits|sat|sitting)\s+(?:uneasily|poorly|awkwardly)
  | (?:trade|trades|traded|trading)\s+weight
  | unpack(?:s|ed|ing)?
  | outr(?:un|uns|an|unning)
  | see-?saws?
  | landscapes?
  | backbones?
  | lens(?:es)?
  | carr(?:y|ies|ied|ying)\s+
    (?: (?:(?:the\s+)?(?:much|most|more|less)\s+|the\s+|(?:no|little|some|real|any|enough)\s+)?weight
      | (?:(?:the|all|every|each|your|its|their|this|that|these|those|one|a|an|much|most|both|whole)\s+){0,2}
        (?:[\w'’-]+\s+)?
        (?:claims?|contributions?|results?|findings?|arguments?|paper|headline|abstract
           |h\d\w*|hypothes[ie]s|moderation|identification|burden|story|case|mechanism|conclusions?)
    )
)\b""", re.I | re.X)
# Quoted passages, at most 300 characters: straight and curly doubles (across line breaks), curly
# singles, and straight singles used as quotes. A straight single opens only after a non-word
# character and before a letter ("'90s" is not a quote), and closes only before a non-word character.
_QUOTED = re.compile(r"“[^”]{0,300}”|‘[^’\n]{0,300}’"
                     r"|(?<![\w'])'(?=[A-Za-z])[^'\n]{1,300}(?<=[\w.,;:!?])'(?![\w'])")


def _drop_double_quoted(text: str) -> str:
    """Blank out straight double-quoted spans, pairing the marks in order (first with second, third
    with fourth), so a too-long span never pairs its closing mark with the next opening one. With an
    odd number of marks (an inch mark, a stray quote) the pairing is unreliable and nothing is blanked."""
    marks = [m.start() for m in re.finditer('"', text)]
    if len(marks) % 2:
        return text
    out, last = [], 0
    for a, b in zip(marks[::2], marks[1::2]):
        if b - a - 1 <= 300:
            out += [text[last:a], " "]
            last = b + 1
    return "".join(out) + text[last:]
_REPORT_TITLE = re.compile(r"^Referee Report on .*$", re.M)
METAPHOR_MESSAGE = ("Use no metaphors: name the variable, test, or assumption and say literally how they "
                    "relate. Text quoted from the paper in quotation marks is not checked.")


def _metaphor_phrases(text: str) -> list:
    plain = _QUOTED.sub(" ", _drop_double_quoted(text))
    return [" ".join(m.group(0).lower().split()) for m in _METAPHOR.finditer(plain)]


def metaphor_errors(text: str, exempt=()) -> list:
    """Draft text uses no metaphors. The disclosure line, the report's "Referee Report on <title>" line,
    quoted passages, the dropped-items appendix, REFERENCES, and the `exempt` strings (summaries and
    titles the writer must copy word for word) are not checked."""
    text = _REPORT_TITLE.sub("", text.replace("\r\n", "\n"))
    body = "\n".join(l for l in _body(text).splitlines() if l.strip() != DISCLOSURE_LINE)
    # A copied summary may differ in markup or page citations, so exempt its phrases by count.
    allowed = [p for s in exempt if s for p in _metaphor_phrases(s)]
    found = []
    for p in _metaphor_phrases(body):
        if p in allowed:
            allowed.remove(p)
        elif p not in found:
            found.append(p)
    if not found:
        return []
    return [METAPHOR_MESSAGE + " Found: " + ", ".join(repr(f) for f in found[:5]) + "."]


# A cited year: "Smith (2023)", "Smith et al. (2023, p. 4)", or "(Smith, 2023)" and "(Smith et al. 2023; ...)".
_NOT_A_NAME = (r"(?!(?:In|By|Since|From|Until|After|Before|During|Through|Of|For|And|Or|To|At|On|Between|"
               r"January|February|March|April|May|June|July|August|September|October|November|December|"
               r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|Spring|Summer|Fall|Autumn|Winter)\b)")
_CITED_YEAR = re.compile(r"\b" + _NOT_A_NAME + r"[A-Z][\w'’-]+(?: et al\.)?"
                         r"(?: \(((?:19|20)\d{2})[a-z]?[),;]|,? ((?:19|20)\d{2})[a-z]?(?=\s*[;)]))")


def post_cap_errors(text: str, search_before: str = "") -> list:
    """With a search date cap, an output cites nothing dated after the cap's year."""
    if not search_before:
        return []
    cap = int(search_before[:4])
    found = sorted({m.group(0).rstrip(",;") for m in _CITED_YEAR.finditer(text)
                    if int(m.group(1) or m.group(2)) > cap})
    if not found:
        return []
    return [f"This run is capped at {search_before}: remove the citations dated after it. A point that cannot stand "
            "without one goes to the user. Found: " + ", ".join(repr(f) for f in found[:5]) + "."]


DROPPED_HEADER = "## Dropped items"
NO_ISSUES = "No issues survived the checks."
# "ms p. 30 (PDF p. 32)", "ms pp. 3-4 (PDF pp. 5-6)", with ", approximate" after an approximate PDF page.
# The flattened display form annotate_pdf.py writes, "ms p. 30, PDF p. 32" (comma, no nested
# parens, used inside the annotated PDF's index line so parens don't nest), is accepted too.
_BOTH = re.compile(
    r"\bms pp?\. [\w\-–]+ \(PDF pp?\. [\w\-–]+(?:, approximate)?\)"
    r"|\bms pp?\. [\w\-–]+, PDF pp?\. [\w\-–]+(?:, approximate)?"
)
_PDF_ONLY = re.compile(r"\bPDF pp?\. [\w\-–]+(?:, approximate)?")
_ANY_PAGE = re.compile(r"(?<![A-Za-z])pp?\. ?\d")
# A parenthetical that holds a four-digit year cites another work, as in "(Author, 2009, p. 213)".
_OTHER_WORK = re.compile(r"\([^()]*\b(?:1[5-9]|20)\d\d[a-z]?\b[^()]*\)")


_REFERENCES_LINE = re.compile(r"^REFERENCES[ \t\r]*$", re.M | re.I)


def _body(text: str) -> str:
    """The text before the dropped-items appendix and any REFERENCES block (a line reading
    REFERENCES in any case, CRLF line ends allowed)."""
    if DROPPED_HEADER in text:
        text = text.split(DROPPED_HEADER, 1)[0]
    return _REFERENCES_LINE.split(text, 1)[0]


def page_citation_errors(text: str, same_pages: bool = False) -> list:
    """Every page citation in the body must carry both numbers, "ms p. N (PDF p. M)" or the
    flattened "ms p. N, PDF p. M", or be a lone "PDF p. M" when the paper prints no page there.
    Citations of other works are skipped. With `same_pages` (run.json `page_offset` is 0), the
    printed page is the PDF page, so one number, "p. N", is the citation and nothing fails."""
    if same_pages:
        return []
    rest = _OTHER_WORK.sub("", _PDF_ONLY.sub("", _BOTH.sub("", _body(text))))
    bad = sorted({m.group(0) for m in _ANY_PAGE.finditer(rest)})
    if not bad:
        return []
    return ["Every page citation needs both numbers, as in 'ms p. 30 (PDF p. 32)'. Found a bare citation: "
            + ", ".join(repr(b) for b in bad[:5]) + "."]


def _match_key(text: str) -> str:
    """Text for matching a summary: page citations and parentheticals naming a page removed,
    whitespace collapsed, case folded."""
    text = _BOTH.sub(" ", text)
    text = _PDF_ONLY.sub(" ", text)
    text = re.sub(r"\((?:ms )?pp?\. ?[\w\-–]+\)", " ", text)
    text = re.sub(r"(?:\bms )?(?<![A-Za-z])pp?\. ?[\w\-–]+", " ", text)
    text = re.sub(r"[()]", " ", text)
    text = re.sub(r"\s+([.,;:])", r"\1", text)
    return re.sub(r"\s+", " ", text).strip().casefold()


def dropped_errors(text: str, dropped=None) -> list:
    heads = [m.group(0).strip() for m in re.finditer(r"^## .+$", text, re.M)]
    if DROPPED_HEADER not in heads:
        return [f"Missing the '{DROPPED_HEADER}' section at the end."]
    errs = []
    if heads[-1] != DROPPED_HEADER:
        errs.append(f"'{DROPPED_HEADER}' must be the last '##' section.")
    section = text.split(DROPPED_HEADER, 1)[1].split("\nREFERENCES\n", 1)[0]
    lines = [l for l in section.splitlines() if l.startswith("- ")]
    if dropped is not None:
        if not dropped and not lines and "None" not in section:
            errs.append(f"'{DROPPED_HEADER}' is empty; write 'None.' when nothing was dropped.")
        if len(lines) != len(dropped):
            errs.append(f"'{DROPPED_HEADER}' lists {len(lines)} items; dropped.json has {len(dropped)}.")
        for d in dropped:
            if not any(d["reason"] in l for l in lines):
                errs.append(f"No dropped line gives the reason '{d['reason']}' for {d['item']}.")
    return errs


def validate_issues_list(text: str, mode: str = "full", validated=None, dropped=None,
                         max_words: int = 2200, same_pages: bool = False) -> list:
    """The issues list. `full`: the fix-list checks, minors numbered on in `## Minor issues`.
    `facts_only`: numbered `### N.` checked facts under `## Checked facts`, with no fixes.
    Both: a `Where:` line on every item, both page numbers on every page citation, the dropped-items
    appendix last, and, given validated.json, one item per validated issue carrying its summary."""
    if mode not in ("full", "facts_only"):
        raise ValueError("mode must be 'full' or 'facts_only'")
    body = _body(text)
    heads = list(re.finditer(r"^### (\d+)\. (.+)$", body, re.M))
    errs = []
    if mode == "full":
        # Numbered items hold the major issues; a list whose issues are all Minor has none.
        majors = validated is None or any(v.get("severity") != "Minor" for v in validated)
        errs += validate_fix_list(body + "\n", max_words=max_words, require_items=majors, metaphors=False)
        # The body check above misses the dropped-items appendix and REFERENCES; check the whole file.
        if has_recommendation(text) and not has_recommendation(body + "\n"):
            errs.append("Output contains an editorial recommendation.")
        if validated == [] and NO_ISSUES not in body:
            errs.append(f"No issue survived: write the one line '{NO_ISSUES}' under '## Issues'.")
    else:
        if "## Checked facts" not in body:
            errs.append("Missing the '## Checked facts' section.")
        if [int(h.group(1)) for h in heads] != list(range(1, len(heads) + 1)):
            errs.append("Items must be numbered 1..N in order.")
        if re.search(r"^Fix: ", body, re.M):
            errs.append("A facts-only list gives no fixes: remove the 'Fix:' lines.")
        if len(body.split()) > max_words:
            errs.append(f"Issues list runs {len(body.split())} words before the appendix; the ceiling is {max_words}.")
        if has_recommendation(text):
            errs.append("Output contains an editorial recommendation.")
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(body)
        if not re.search(r"^Where: .+$", body[h.end():end], re.M):
            errs.append(f"Item {h.group(1)} needs a 'Where:' line, as in 'Where: ms p. 30 (PDF p. 32)'.")
    errs += verdict_errors(text)
    errs += metaphor_errors(text, _copied(validated))
    errs += page_citation_errors(text, same_pages)
    errs += dropped_errors(text, dropped)
    if validated is not None:
        numbers = [int(h.group(1)) for h in heads]
        numbers += [int(n) for n in re.findall(r"^- (\d+)\. ", body.split("## Minor issues", 1)[1], re.M)] \
            if "## Minor issues" in body else []
        want = [int(v["id"]) for v in validated]
        if sorted(numbers) != want:
            errs.append(f"The list numbers items {sorted(numbers)}; validated.json has items {want}.")
        key = _match_key(body)
        for v in validated:
            if v.get("summary") and _match_key(v["summary"]) not in key:
                errs.append(f"Item {v['id']} must include its summary from validated.json word for word.")
    return errs


def report_trace_errors(text: str, trace: dict, validated: list) -> list:
    """Every numbered comment in the report traces to at least one validated issue id, and every
    validated issue is raised in some comment."""
    ids = [str(v["id"]) for v in validated]
    errs, raised = [], set()
    for n in re.findall(r"^(\d+)\. ", text, re.M):
        linked = {str(x) for x in trace.get(n, [])}
        raised |= linked
        if not linked:
            errs.append(f"Comment {n} does not trace to an issue in validated.json.")
        elif not linked <= set(ids):
            errs.append(f"Comment {n} traces to {sorted(linked - set(ids))}, which are not in validated.json.")
    for i in ids:
        if i not in raised:
            errs.append(f"Issue {i} in validated.json is not raised in any comment.")
    return errs


# The checked-facts memo for an editor (editor_memo.md).
MEMO_SUMMARY = "## The paper"
MEMO_ISSUES = "## Most serious issues"
MEMO_TOP = 5
MEMO_FIELDS = ("Severity:", "Where:", "What the paper claims:", "The problem:", "Why it matters:",
               "What would settle it:")
# In facts-only mode (a journal whose policy bars AI drafting), the memo
# drops these two judgment fields and keeps only the checked facts.
MEMO_FACTS_FIELDS = MEMO_FIELDS[:4]
MEMO_DROPPED_FIELDS = MEMO_FIELDS[4:]
_ALLOWED_SECTIONS = (MEMO_SUMMARY, MEMO_ISSUES)
_SECTION_HEADING = re.compile(r"^##\s+.+$", re.M)
# High-precision verdict and desk-reject signals the memo must never carry, on top of
# has_recommendation. The guarantee mainly rests on the memo's fixed structure and the writer's
# instructions (design guarantee over exhaustive filter); these patterns catch only unambiguous
# verdict wording, not every soft phrasing.
_DESK_REJECT = [
    # "revise the paper to report X" is fix advice, so only accept and reject count here.
    re.compile(r"\b(?:accept|reject)(?:s|ed|ing|ion|ance)?\s+(?:the|this)\s+"
               r"(?:paper|manuscript|submission|article)\b(?!['’]s)", re.I),
    re.compile(r"\b(?:the|this)\s+(?:paper|manuscript|submission|article)\s+should\s+"
               r"(?:not\s+)?be\s+(?:accepted|rejected)\b", re.I),
    re.compile(r"\bdesk[\s-]*reject", re.I),
    re.compile(r"^\s*(?:[-*•]\s*)?\**\s*(?:decision|verdict|score|rating|grade)\**\s*:", re.I | re.M),
]


def desk_reject_phrases(text: str) -> list:
    """Each verdict or desk-reject phrase in the text, once, in sorted order."""
    return sorted({m.group(0).strip() for rx in _DESK_REJECT for m in rx.finditer(text)})


def verdict_errors(text: str) -> list:
    """The error a report or an issues list gets when it carries a verdict or desk-reject phrase."""
    hits = desk_reject_phrases(text)
    if not hits:
        return []
    return ["The output gives a verdict or a desk-reject signal: " + ", ".join(repr(h) for h in hits[:5])
            + ". State the facts and leave the decision to the editor."]


def memo_issues(validated: list) -> list:
    """The issues the memo shows: the first five in validated.json, which lists the kept issues
    most serious first, or all of them when fewer survived."""
    return list(validated[:MEMO_TOP])


def fewer_than_five(n: int) -> str:
    """The sentence the memo gives when fewer than five issues survived; empty otherwise."""
    if n >= MEMO_TOP:
        return ""
    if n == 0:
        return NO_ISSUES
    if n == 1:
        return "Only 1 issue survived the checks, so this memo lists it."
    return f"Only {n} issues survived the checks, so this memo lists all of them."


def validate_editor_memo(text: str, validated=None, max_words: int = 1500, mode: str = "full",
                         same_pages: bool = False) -> list:
    """The memo: a neutral summary, then the most serious validated issues, each with the fields
    for this mode. mode "full" requires all six MEMO_FIELDS; mode "facts_only" (a journal whose
    policy bars AI drafting) requires only
    MEMO_FACTS_FIELDS and forbids MEMO_DROPPED_FIELDS. Given validated.json, the items are its
    first five in order, each with its severity and its summary word for word, and fewer than five
    carry the fewer_than_five sentence. No section besides MEMO_SUMMARY and MEMO_ISSUES. Never a
    verdict, a score, or a desk-reject signal."""
    fields = MEMO_FACTS_FIELDS if mode == "facts_only" else MEMO_FIELDS
    dropped = MEMO_DROPPED_FIELDS if mode == "facts_only" else ()
    errs = []
    for head in (MEMO_SUMMARY, MEMO_ISSUES):
        if head not in text:
            errs.append(f"Missing the '{head}' section.")
    if MEMO_SUMMARY in text and MEMO_ISSUES in text and text.index(MEMO_SUMMARY) > text.index(MEMO_ISSUES):
        errs.append(f"'{MEMO_SUMMARY}' must come before '{MEMO_ISSUES}'.")
    extra = [h for h in _SECTION_HEADING.findall(text) if h not in _ALLOWED_SECTIONS]
    if extra:
        errs.append(f"Only '{MEMO_SUMMARY}' and '{MEMO_ISSUES}' are allowed as sections; found "
                    + ", ".join(repr(h) for h in extra) + ".")
    issues = text.split(MEMO_ISSUES, 1)[1] if MEMO_ISSUES in text else ""
    heads = list(re.finditer(r"^### (\d+)\. (.+)$", issues, re.M))
    if [int(h.group(1)) for h in heads] != list(range(1, len(heads) + 1)):
        errs.append("Items must be numbered 1..N in order.")
    if len(heads) > MEMO_TOP:
        errs.append(f"The memo lists {len(heads)} issues; list at most {MEMO_TOP}.")
    blocks = [issues[h.end():heads[i + 1].start() if i + 1 < len(heads) else len(issues)]
              for i, h in enumerate(heads)]
    for h, block in zip(heads, blocks):
        for field in fields:
            if not re.search(rf"^{re.escape(field)} \S", block, re.M):
                errs.append(f"Item {h.group(1)} needs a '{field}' line.")
        for field in dropped:
            if re.search(rf"^{re.escape(field)} \S", block, re.M):
                errs.append(f"Item {h.group(1)} must drop the '{field}' line: this journal keeps "
                            f"the memo to checked facts only.")
    errs += page_citation_errors(text, same_pages)
    errs += metaphor_errors(text, _copied(validated))
    if validated is not None:
        top = memo_issues(validated)
        if len(heads) != len(top):
            errs.append(f"The memo lists {len(heads)} issues; validated.json gives {len(top)} "
                        f"(the {MEMO_TOP} most serious, or all of them when fewer survived).")
        for h, block, v in zip(heads, blocks, top):
            sev = re.search(r"^Severity: (.+)$", block, re.M)
            if sev and sev.group(1).strip() != v.get("severity"):
                errs.append(f"Item {h.group(1)} has Severity '{sev.group(1).strip()}'; "
                            f"validated.json gives '{v.get('severity')}'.")
            if v.get("summary") and _match_key(v["summary"]) not in _match_key(block):
                errs.append(f"Item {h.group(1)} must include its summary from validated.json word for word.")
        want = fewer_than_five(len(validated))
        if want and want not in issues:
            errs.append(f"Fewer than {MEMO_TOP} issues survived: write the sentence '{want}' under '{MEMO_ISSUES}'.")
    if len(text.split()) > max_words:
        errs.append(f"Memo runs {len(text.split())} words; the ceiling is {max_words}.")
    if has_recommendation(text):
        errs.append("Output contains an editorial recommendation.")
    hits = desk_reject_phrases(text)
    if hits:
        errs.append("The memo gives a verdict or a desk-reject signal: " + ", ".join(repr(h) for h in hits[:5])
                    + ". State the facts and leave the decision to the editor.")
    return errs
