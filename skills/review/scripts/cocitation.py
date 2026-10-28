#!/usr/bin/env python3
"""Works the paper's own references keep citing that the paper does not cite, from OpenAlex.

Usage:
    python3 cocitation.py <workspace> [mailto] 

Reads <workspace>/stage-1/reference_list_input.txt and <workspace>/run.json. Writes
<workspace>/stage-2/cocitation.md and cocitation.json: a list of classics (works cited by many
of the paper's references) and a list of close recent work (works that cite two or more of
them), each without works the paper cites and without works published after the search cap.
It calls no model and judges nothing. References without a DOI are matched through CrossRef.

The OpenAlex key, when there is one, comes from the OPENALEX_API_KEY environment variable, else
the Plumb config's openalex_api_key (read with plumb/config.py, which honors PLUMB_CONFIG). It is
never taken from the command line, is sent only as an Authorization header, and is never printed.

Exit codes:
    0  the lists were written
    2  the lists could not be built (OpenAlex or CrossRef unreachable, OpenAlex's daily budget
       used up, OpenAlex rejected the key, no reference list, or no readable run.json); nothing
       written. Any lists from an earlier run are deleted at the start, so a failed rerun leaves
       none. The last printed line says why.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
import time
import unicodedata
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_citations as vc  # noqa: E402

API = "https://api.openalex.org/works"
TOP = 15
PER_SEED = 100
THIN = 10
BATCH = 50
FIELDS = "id,title,display_name,publication_year,publication_date,authorships,primary_location,type,language"
KEEP_TYPES = {"article", "book", "book-chapter", "review", "preprint", "report"}
_TITLE_PREFIX = re.compile(
    r"^\s*(?:\d+\s+|(?:original contribution|research notes?|book reviews?|review article)\b[\s.:]*)+", re.I)
# Most backward candidates whose records are fetched to merge duplicate records, per run.
MERGE_CAP = 3000
MAILTO = ""
API_KEY = ""
# OpenAlex spending this run: the sum of x-ratelimit-cost-usd, and the last x-ratelimit-remaining-usd.
COST_USD = 0.0
REMAINING_USD = None
# A folder for OpenAlex and CrossRef replies (PLUMB_COCITATION_CACHE), so repeated evaluation runs
# cost nothing. Off when empty. Holds no API key and no error reply.
CACHE_DIR = ""


def _cache_file(kind: str, key) -> Path | None:
    if not CACHE_DIR:
        return None
    h = hashlib.sha256(json.dumps([kind, key], sort_keys=True).encode("utf-8")).hexdigest()[:32]
    return Path(CACHE_DIR) / f"{kind}-{h}.json"


def _cache_read(path: Path | None):
    """The cached reply, or None on a miss. A file that does not parse is deleted and is a miss."""
    if not path or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        path.unlink(missing_ok=True)
        return None


def _cache_write(path: Path | None, data) -> None:
    """Write `data` to `path` through a temp file in the same folder and os.replace, so a reader
    never sees half a file. The folder is 0700 and the file 0600."""
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(data))
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


# ---- OpenAlex access ----

RETRY_STATUS = (429, 503)
ATTEMPTS = 3
RETRY_AFTER_MAX = 30
_SEARCH_JUNK = re.compile(r'[?!:,"()\[\]{}|*\\/]')


class BudgetUsedUp(vc.LookupUnavailable):
    """OpenAlex still answered 429 after the retries: the daily budget is spent. `reset` is the
    seconds until it resets, or None when OpenAlex did not say."""

    def __init__(self, reset):
        self.reset = reset
        super().__init__("OpenAlex HTTP 429")


KEY_REJECTED = ("OpenAlex rejected the API key; check OPENALEX_API_KEY or openalex_api_key in the "
                "Plumb config")


class KeyRejected(vc.LookupUnavailable):
    """OpenAlex answered 401 or 403 to a request that carried the API key."""

    def __init__(self):
        super().__init__(KEY_REJECTED)


def _header(r, name: str):
    """Header `name` of reply `r`, matched without regard to case, or None."""
    headers = getattr(r, "headers", None) or {}
    for k, v in headers.items():
        if str(k).lower() == name:
            return v
    return None


def _float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _meter(r) -> None:
    """Add the reply's cost to COST_USD and keep its remaining budget."""
    global COST_USD, REMAINING_USD
    COST_USD += _float(_header(r, "x-ratelimit-cost-usd")) or 0.0
    remaining = _float(_header(r, "x-ratelimit-remaining-usd"))
    if remaining is not None:
        REMAINING_USD = remaining


PLUGIN_ROOT = Path(__file__).resolve().parents[3]


def _load_key() -> str:
    """The OpenAlex key: OPENALEX_API_KEY, else openalex_api_key from the Plumb config (through
    plumb/config.py, so PLUMB_CONFIG is honored), else ''. An unreadable config means no key, and
    so does a config key that is not text (a notice is printed; the value never is)."""
    key = (os.environ.get("OPENALEX_API_KEY") or "").strip()
    if key:
        return key
    if str(PLUGIN_ROOT) not in sys.path:
        sys.path.insert(0, str(PLUGIN_ROOT))
    try:
        from plumb import config
        saved = config.load().openalex_api_key
    except (ImportError, OSError, ValueError, TypeError):
        print("Plumb config unreadable; OpenAlex runs without a key.")
        return ""
    if saved is None:
        return ""
    if not isinstance(saved, str):
        print("openalex_api_key in the Plumb config is not text; it is ignored and OpenAlex runs "
              "without a key.")
        return ""
    return saved.strip()


def _scrub(text: str) -> str:
    """`text` with the API key blanked out."""
    return str(text).replace(API_KEY, "[key]") if API_KEY else str(text)


def _clean_search(text: str) -> str:
    """`text` without the characters OpenAlex rejects in a `search` value, spaces collapsed."""
    return re.sub(r"\s+", " ", _SEARCH_JUNK.sub(" ", text or "")).strip()


def _wait(r, attempt: int) -> float:
    """Seconds to wait after a 429 or 5xx: Retry-After (0 to 30) when given, else 2 ** (attempt + 1)."""
    try:
        secs = float((getattr(r, "headers", None) or {}).get("Retry-After"))
        return min(max(secs, 0), RETRY_AFTER_MAX)
    except (TypeError, ValueError):
        return 2 ** (attempt + 1)


def _get(params: dict) -> dict:
    """One OpenAlex request, retried on a network error, 429, and any 5xx. Raises
    vc.LookupUnavailable on a network error or 5xx on the last attempt, on any other non-200 reply,
    and on a 200 reply that is not JSON; BudgetUsedUp (a kind of vc.LookupUnavailable) on a 429 on
    the last attempt; and KeyRejected (also a kind) on a 401 or 403 when a key was sent."""
    p = dict(params)
    if "search" in p:
        p["search"] = _clean_search(p["search"])
    if MAILTO:
        p["mailto"] = MAILTO
    cached = _cache_file("openalex", {k: v for k, v in p.items() if k != "mailto"})
    hit = _cache_read(cached)
    if hit is not None:
        return hit
    headers = {"Authorization": f"Bearer {API_KEY}"} if API_KEY else None
    for attempt in range(ATTEMPTS):
        failure = None
        try:
            r = vc.requests.get(API, params=p, headers=headers, timeout=20)
        except Exception as exc:
            failure = _scrub(f"OpenAlex network error: {exc}")
        if failure is not None:
            # Raised outside the except block so the original exception, whose text may hold the
            # request URL or headers, is not chained onto this one.
            if attempt == ATTEMPTS - 1:
                raise vc.LookupUnavailable(failure)
            time.sleep(2 ** (attempt + 1))
            continue
        _meter(r)
        if r.status_code == 200:
            try:
                data = r.json()
            except ValueError:
                data = None
            if not isinstance(data, dict):
                raise vc.LookupUnavailable("OpenAlex sent a reply that is not JSON")
            _cache_write(cached, data)
            return data
        if r.status_code in (401, 403) and API_KEY:
            raise KeyRejected()
        if r.status_code == 429 and attempt == ATTEMPTS - 1:
            reset = _float(_header(r, "x-ratelimit-reset"))
            raise BudgetUsedUp(int(reset) if reset is not None else None)
        retry = r.status_code in RETRY_STATUS or 500 <= r.status_code < 600
        if not retry or attempt == ATTEMPTS - 1:
            raise vc.LookupUnavailable(f"OpenAlex HTTP {r.status_code}")
        time.sleep(_wait(r, attempt))
    raise vc.LookupUnavailable("OpenAlex retries exhausted")


def _wid(url_or_id: str) -> str:
    return str(url_or_id).rstrip("/").rsplit("/", 1)[-1]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", (text or "").lower())).strip()


# ---- the paper's references ----

def parse_references(text: str) -> list:
    """The REFERENCES entries of `text`, parsed by verify_citations."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(text)
        path = f.name
    try:
        return vc.extract_references_from_text(path)
    finally:
        Path(path).unlink(missing_ok=True)


def _doi(ref: dict) -> str:
    """The DOI in the entry's raw text, without trailing punctuation, or ''."""
    m = re.search(r"10\.\d{4,9}/\S+", ref.get("raw", ""))
    return m.group(0).rstrip(".,;:)]}>\"'") if m else ""


def _query(ref: dict) -> str:
    parts = list(ref.get("last_names", [])[:3])
    if ref.get("title_fragment"):
        parts += ref["title_fragment"].split()[:6]
    if ref.get("year"):
        parts.append(str(ref["year"]))
    return " ".join(parts).strip()


def _norm_doi(doi) -> str:
    """Lowercase DOI without a doi.org prefix."""
    return re.sub(r"^https?://(dx\.)?doi\.org/", "", str(doi or "").strip().lower())


_ENTRY_STOP = {"the", "and", "for", "with", "from", "into", "onto", "its", "their", "this", "that",
               "these", "those", "are", "was", "were", "how", "why", "what", "when", "where", "who",
               "does", "not", "but", "our", "can", "between", "among", "over", "under", "about",
               "through", "toward", "towards", "upon", "via", "than"}
ENTRY_WORDS = 4
ENTRY_SHARE = 0.8
_CROSSREF_RETRY = re.compile(r"network error|HTTP (429|5\d\d)\b")


QUOTED_MIN = 2
QUOTED_AUTHOR_MAX = 3


def _fold(text: str) -> str:
    """`text` with accents removed (NFKD, ASCII only), then `_norm`."""
    return _norm(unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode())


def _author_in_entry(ref: dict, hit: dict) -> bool:
    """True when one of the hit's author surnames (last token of each display name, folded) is
    among the words of the entry's raw text, folded the same way."""
    present = set(_fold(ref.get("raw", "")).split())
    for a in hit.get("authorships") or []:
        parts = str(((a or {}).get("author") or {}).get("display_name") or "").split()
        surname = _fold(parts[-1]).split() if parts else []
        if surname and all(w in present for w in surname):
            return True
    return False
_QUOTED = re.compile(r'["“]([^"“”]+)["”]')


def _content_words(text: str) -> list:
    """Words of `text` after `_norm`, without stopwords and words under three letters."""
    return [w for w in _norm(text).split() if len(w) >= 3 and w not in _ENTRY_STOP]


def _entry_agrees(ref: dict, hit: dict) -> bool:
    """True when the hit's title and year agree with the entry's raw text, for entries
    verify_citations parses badly, such as `Surname, First, "Title," Journal, volume (year), pages`.
    Content words drop stopwords and words under three letters. When the entry has a quoted
    segment (straight or curly double quotes), only that segment counts as the title: it needs at
    least QUOTED_MIN content words, and they must be the leading content words of the hit's title,
    in order (a subtitle may follow); with QUOTED_AUTHOR_MAX or fewer, one of the hit's author
    surnames must also appear in the entry (`_author_in_entry`). Otherwise the hit's title needs at least ENTRY_WORDS
    content words and ENTRY_SHARE of them anywhere in the entry. Either way the hit's year must be
    within one of a four-digit year in the entry."""
    words = _content_words(hit.get("title") or "")
    quoted = _QUOTED.search(ref.get("raw", ""))
    if quoted:
        segment = _content_words(quoted.group(1))
        if len(segment) < QUOTED_MIN or words[:len(segment)] != segment:
            return False
        if len(segment) <= QUOTED_AUTHOR_MAX and not _author_in_entry(ref, hit):
            return False
    else:
        if len(words) < ENTRY_WORDS:
            return False
        present = set(_norm(ref.get("raw", "")).split())
        if sum(w in present for w in words) < ENTRY_SHARE * len(words):
            return False
    year = hit.get("publication_year")
    years = {int(y) for y in re.findall(r"(?<!\d)(\d{4})(?!\d)", ref.get("raw", ""))}
    return isinstance(year, int) and any(abs(year - y) <= 1 for y in years)


def _crossref(q: str) -> list:
    """vc.search_crossref(q), retried on a network error, 429, or 5xx: up to ATTEMPTS attempts,
    waiting 2 s, then 4 s. The last failure is raised as is."""
    for attempt in range(ATTEMPTS):
        try:
            return vc.search_crossref(q)
        except vc.LookupUnavailable as exc:
            if attempt == ATTEMPTS - 1 or not _CROSSREF_RETRY.search(str(exc)):
                raise
        time.sleep(2 ** (attempt + 1))
    raise vc.LookupUnavailable("CrossRef retries exhausted")


def _search(ref: dict) -> tuple:
    """(kind, value) for the entry's match from vc.search_crossref: ("doi", doi) or ("id", OpenAlex
    id), or None. A VERIFIED match counts; so does a LIKELY_MATCH or AUTHOR_MISMATCH that
    `_entry_agrees` with the entry's raw text. Raises vc.LookupUnavailable when CrossRef is
    unreachable."""
    q = _clean_search(_query(ref))
    if not q:
        return None
    cached = _cache_file("crossref", q)
    results = _cache_read(cached)
    if results is None:
        results = _crossref(q)
        time.sleep(0.5)
        _cache_write(cached, results)
    quality, hit = vc.match_reference(ref, results)
    if not hit:
        return None
    if quality != "VERIFIED" and not (quality in ("LIKELY_MATCH", "AUTHOR_MISMATCH") and _entry_agrees(ref, hit)):
        return None
    doi = _norm_doi(hit.get("doi"))
    if doi:
        return ("doi", doi)
    hid = str(hit.get("id") or "")
    if hid.startswith("https://openalex.org/"):
        return ("id", _wid(hid))
    return None


def _bad_item(exc: Exception) -> bool:
    """True when OpenAlex refused the request itself (HTTP 400, 404, or 422). A 429 is never a
    bad item: it is rate limiting, and it ends the run."""
    return not isinstance(exc, BudgetUsedUp) and bool(re.search(r"HTTP (400|404|422)\b", str(exc)))


def _doi_ids(dois: list) -> tuple:
    """(normalized DOI -> OpenAlex id, DOIs OpenAlex rejected), one request per batch of BATCH.
    A batch OpenAlex rejects (400, 404, 422) is retried one DOI at a time so one bad DOI spoils
    only itself. Network errors, 429, and 5xx raise vc.LookupUnavailable."""
    found, rejected = {}, set()
    uniq = list(dict.fromkeys(dois))
    for i in range(0, len(uniq), BATCH):
        batch = uniq[i:i + BATCH]
        try:
            data = _get({"filter": "doi:" + "|".join(batch), "select": "id,doi", "per_page": BATCH})
        except vc.LookupUnavailable as exc:
            if not _bad_item(exc):
                raise
            if len(batch) == 1:
                rejected.add(batch[0])
                continue
            for d in batch:
                f, r = _doi_ids([d])
                found.update(f)
                rejected |= r
            continue
        for w in data.get("results", []):
            if w.get("id") and w.get("doi"):
                found[_norm_doi(w["doi"])] = _wid(w["id"])
    return found, rejected


def resolve(refs: list) -> tuple:
    """(seed ids, unresolved count). An entry with a DOI seeds the work that DOI names. Any other
    entry is searched in CrossRef only and seeds on a VERIFIED match, or on a LIKELY_MATCH or
    AUTHOR_MISMATCH whose title and year agree with the entry's raw text (`_entry_agrees`); any
    other entry counts as unresolved. DOIs become OpenAlex ids in batches; a DOI OpenAlex does not
    return counts as unresolved. An entry whose own DOI OpenAlex rejects (400, 404, 422) is
    searched instead."""
    slots = [("doi", _norm_doi(_doi(ref))) if _doi(ref) else _search(ref) for ref in refs]
    found, rejected = _doi_ids([s[1] for s in slots if s and s[0] == "doi"])
    retry = [i for i, s in enumerate(slots) if s and s[0] == "doi" and s[1] in rejected
             and _doi(refs[i])]
    for i in retry:
        slots[i] = _search(refs[i])
    more, _ = _doi_ids([slots[i][1] for i in retry if slots[i] and slots[i][0] == "doi"])
    found.update(more)
    seeds, unresolved = [], 0
    for s in slots:
        wid = (s[1] if s[0] == "id" else found.get(s[1])) if s else None
        if wid:
            seeds.append(wid)
        else:
            unresolved += 1
    return list(dict.fromkeys(seeds)), unresolved


# ---- counting ----

def seed_refs(seeds: list) -> tuple:
    """(seed id -> set of the work ids it cites, the seeds' most common language or "",
    seed id -> OpenAlex record), fetched in batches."""
    refs, langs, meta = {}, Counter(), {}
    for i in range(0, len(seeds), BATCH):
        batch = seeds[i:i + BATCH]
        data = _get({"filter": "openalex_id:" + "|".join(batch), "select": FIELDS + ",referenced_works",
                     "per_page": BATCH})
        for w in data.get("results", []):
            wid = _wid(w["id"])
            refs[wid] = {_wid(x) for x in w.get("referenced_works") or []}
            meta[wid] = w
            if w.get("language"):
                langs[w["language"]] += 1
    return refs, (langs.most_common(1)[0][0] if langs else ""), meta


def _count(refs_by_seed: dict) -> Counter:
    """For each work, how many seeds cite it."""
    return Counter(r for rs in refs_by_seed.values() for r in rs)


def backward(seeds: list) -> Counter:
    """For each work, how many seed works cite it."""
    return _count(seed_refs(seeds)[0])


def forward_sets(seeds: list, cap: str) -> tuple:
    """Works published by `cap` that cite one or more seeds: (id -> the seeds it cites,
    id -> record)."""
    seedset, cites, meta = set(seeds), {}, {}
    for s in seeds:
        data = _get({"filter": f"cites:{s},to_publication_date:{cap}",
                     "select": FIELDS + ",referenced_works", "sort": "cited_by_count:desc",
                     "per_page": PER_SEED})
        for w in data.get("results", []):
            hit = seedset & {_wid(x) for x in w.get("referenced_works") or []}
            if hit:
                wid = _wid(w["id"])
                cites[wid] = hit
                meta[wid] = w
        time.sleep(0.1)
    return cites, meta


def _two_or_more(cites: dict) -> Counter:
    return Counter({w: len(s) for w, s in cites.items() if len(s) >= 2})


def forward(seeds: list, cap: str) -> tuple:
    """Works published by `cap` that cite two or more seeds: (counts, id -> record)."""
    cites, meta = forward_sets(seeds, cap)
    counts = _two_or_more(cites)
    return counts, {w: meta[w] for w in counts}


def records(ids: list) -> dict:
    """id -> OpenAlex record, fetched in batches."""
    out = {}
    for i in range(0, len(ids), BATCH):
        batch = ids[i:i + BATCH]
        data = _get({"filter": "openalex_id:" + "|".join(batch), "select": FIELDS, "per_page": BATCH})
        for w in data.get("results", []):
            out[_wid(w["id"])] = w
    return out


def _authors(w: dict) -> str:
    names = [(a.get("author") or {}).get("display_name", "") for a in w.get("authorships") or []]
    names = [n for n in names if n]
    if len(names) > 3:
        return ", ".join(names[:3]) + ", et al."
    return ", ".join(names)


def _cited(title: str, cited_text: str) -> bool:
    """True when the normalized title (cut to whole words within 40 characters) appears in
    `cited_text` on word boundaries. Titles under three words are never matched."""
    n = _norm(title)
    if len(n.split()) < 3:
        return False
    key = n[:40]
    if len(n) > 40 and n[40] != " ":
        key = key.rsplit(" ", 1)[0]
    return f" {key} " in f" {cited_text} "


def _title_key(title: str) -> str:
    """A title for spotting duplicate records: leading section labels ("ORIGINAL CONTRIBUTION",
    "RESEARCH NOTES") and chapter numbers removed, normalized, first eight words."""
    return " ".join(_norm(_TITLE_PREFIX.sub("", title or "")).split()[:8])


def merge_duplicates(refs_by_seed: dict, meta: dict) -> dict:
    """`refs_by_seed` with duplicate OpenAlex records of one work folded into one id. Ids in `meta`
    whose `_title_key` matches and whose years are at most one apart are one work; the id more
    seeds cite stands for it (ties by id), so its count becomes the number of distinct seeds citing
    any of them. Ids without a record, title, or year are left alone."""
    alias = _aliases(_count(refs_by_seed), meta)
    if not alias:
        return refs_by_seed
    return {s: {alias.get(r, r) for r in rs} for s, rs in refs_by_seed.items()}


def merge_citing(seeds_by_work: dict, meta: dict) -> dict:
    """`seeds_by_work` (citing work -> the seeds it cites) with duplicate records of one citing work
    folded into one id, as `merge_duplicates` does: the id citing more seeds stands for the work and
    cites the union of their seeds."""
    alias = _aliases(Counter({w: len(s) for w, s in seeds_by_work.items()}), meta)
    out = {}
    for w, s in seeds_by_work.items():
        out.setdefault(alias.get(w, w), set()).update(s)
    return out


def _aliases(count: Counter, meta: dict) -> dict:
    """id -> the id that stands for it, for ids in `meta` that duplicate a more-counted id (same
    `_title_key`, years at most one apart; ties by id)."""
    reps, alias = {}, {}
    for wid in sorted((w for w in meta if w in count), key=lambda w: (-count[w], w)):
        w = meta[wid] or {}
        title, year = w.get("title") or w.get("display_name") or "", w.get("publication_year")
        if not title or not year:
            continue
        key = _title_key(title)
        rep = next((r for r, y in reps.get(key, []) if abs(y - year) <= 1), None)
        if rep is None:
            reps.setdefault(key, []).append((wid, year))
        else:
            alias[wid] = rep
    return alias


def _keep(w: dict, lang: str = "") -> bool:
    """False for a work whose OpenAlex type is not an article, book, chapter, review, preprint, or report, or whose
    language differs from `lang`. A work with no type or no language is kept."""
    typ = w.get("type")
    if typ and typ not in KEEP_TYPES:
        return False
    wl = w.get("language")
    return not (lang and wl and wl != lang)


def rank(counts: Counter, meta: dict, seeds: set, cap_year: int, cited_text: str, top: int = TOP,
         cap_date: str = "", lang: str = "") -> list:
    """The top works by links, without seeds, works after the cap, works
    the paper cites, works `_keep` rejects, and near-duplicates of a work already listed (same
    `_title_key`, years at most one apart)."""
    out, seen = [], {}
    ids = [w for w, _ in counts.most_common()]
    for wid in ids:
        n = counts.get(wid, 0)
        w = meta.get(wid)
        if wid in seeds or not w or not _keep(w, lang):
            continue
        year = w.get("publication_year")
        title = w.get("title") or w.get("display_name") or ""
        if not year or year > cap_year or not title:
            continue
        date = w.get("publication_date")
        if cap_date and date and date > cap_date:
            continue
        if _cited(title, cited_text):
            continue
        key = _title_key(title)
        if key in seen and abs(seen[key] - year) <= 1:
            continue
        seen.setdefault(key, year)
        venue = ((w.get("primary_location") or {}).get("source") or {}).get("display_name", "")
        out.append({"id": wid, "authors": _authors(w), "year": year, "title": title, "venue": venue,
                    "links": n})
        if len(out) == top:
            break
    return out


# ---- the command ----

def cap_for(run: dict) -> str:
    """The search cap, or the run's start date when there is none."""
    cap = str(run.get("search_before") or "").strip()
    if cap:
        return cap[:10]
    return str(run.get("started") or time.strftime("%Y-%m-%d"))[:10]


CELL_MAX = 300


def _cell(text) -> str:
    """One table cell from outside text: control characters become spaces, whitespace collapses,
    pipes become slashes, and the cell is cut to CELL_MAX characters."""
    s = re.sub(r"[\x00-\x1f\x7f-\x9f  ]", " ", str(text))
    s = re.sub(r"\s+", " ", s).strip().replace("|", "/")
    return s if len(s) <= CELL_MAX else s[:CELL_MAX] + "..."


def _table(rows: list) -> list:
    if not rows:
        return ["None found.", ""]
    head = ["Authors", "Year", "Title", "Venue", "OpenAlex", "Links"]
    right = {"Year", "Links"}
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---:" if h in right else "---" for h in head) + "|"]
    for r in rows:
        cells = [r["authors"], r["year"], r["title"], r["venue"], r["id"], r["links"]]
        out.append("| " + " | ".join(_cell(c) for c in cells) + " |")
    return out + [""]


def write(ws: Path, classics: list, recent: list, seeds: int, total: int, cap: str,
          cost_usd: float = 0.0, remaining_usd=None,
          pools: dict | None = None, merge_capped: dict | None = None) -> None:
    thin = seeds < THIN
    data = {"cap": cap, "seeds": seeds, "references": total, "thin": thin,
            "openalex_cost_usd": round(cost_usd, 6), "openalex_remaining_usd": remaining_usd,
            "classics": classics, "recent": recent}
    if pools is not None:
        data["pools"] = pools
    if merge_capped:
        data["merge_capped"] = merge_capped
    lines = ["# Works the paper's references cite that the paper does not", "",
             f"Found {seeds} of the paper's {total} references in OpenAlex. Search cap: {cap}. "
             "Works the paper cites and works published after the cap are left out. "
             "Links counts how many of the paper's references connect to each work.", ""]
    if thin:
        lines += [f"These lists are thin: only {seeds} references were found, so a missing work here "
                  "says little.", ""]
    if merge_capped:
        lines += [f"Note: duplicate records were merged only among the {merge_capped['records_fetched']} "
                  f"most-linked of the {merge_capped['backward_candidates']} works the references cite.", ""]
    lines += ["## Classics: works many of the paper's references cite", ""] + _table(classics)
    lines += ["## Close recent work: works that cite two or more of the paper's references", ""]
    lines += _table(recent)
    out = ws / "stage-2"
    out.mkdir(parents=True, exist_ok=True)
    (out / "cocitation.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    (out / "cocitation.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv: list | None = None) -> int:
    global MAILTO, API_KEY, COST_USD, REMAINING_USD, CACHE_DIR
    args = sys.argv[1:] if argv is None else argv
    flags = [a for a in args if a.startswith("--")]
    args = [a for a in args if not a.startswith("--")]
    # --emit-pools (hidden, for eval/cocitation_eval.py --reach): also write every candidate id
    # with its link count, before filtering and ranking.
    emit_pools = "--emit-pools" in flags
    if not args:
        print("Usage: cocitation.py <workspace> [mailto]")
        return 2
    ws = Path(args[0])
    # Lists from an earlier run go first, so a failed rerun never leaves them looking current.
    for name in ("cocitation.md", "cocitation.json"):
        (ws / "stage-2" / name).unlink(missing_ok=True)
    if len(args) > 1:
        MAILTO = vc.MAILTO = args[1]
    API_KEY = _load_key()
    CACHE_DIR = os.environ.get("PLUMB_COCITATION_CACHE", "")
    COST_USD, REMAINING_USD = 0.0, None
    listing = ws / "stage-1" / "reference_list_input.txt"
    text = listing.read_text(encoding="utf-8") if listing.exists() else ""
    refs = parse_references(text) if text.strip() else []
    if not refs:
        print("No reference list; nothing written.")
        return 2
    run_path = ws / "run.json"
    try:
        run = json.loads(run_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        run = None
    cap = cap_for(run) if isinstance(run, dict) else ""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", cap):
        print(f"No readable run.json with a search cap or start date at {run_path}; nothing written.")
        return 2
    cited = _norm(text)
    merge_capped = None
    try:
        seeds, unresolved = resolve(refs)
        refs_by_seed, lang, _ = seed_refs(seeds)
        # Duplicate OpenAlex records of one work are merged over every candidate with a link
        # before any ranking: records for the backward candidates (at most MERGE_CAP, the most
        # cited first); the forward candidates' records come with their replies.
        seedset = set(seeds)
        raw_back = Counter({w: n for w, n in _count(refs_by_seed).items() if w not in seedset})
        fetch = sorted(raw_back, key=lambda w: (-raw_back[w], w))
        if len(fetch) > MERGE_CAP:
            merge_capped = {"backward_candidates": len(fetch), "records_fetched": MERGE_CAP}
            fetch = fetch[:MERGE_CAP]
        back_meta = records(fetch)
        refs_by_seed = merge_duplicates(refs_by_seed, back_meta)
        back = _count(refs_by_seed)
        # Ranked over every fetched candidate, so the list still fills when the most-linked works
        # drop out as cited by the paper or published after the cap.
        classics = rank(back, back_meta, seedset, int(cap[:4]), cited, cap_date=cap, lang=lang)
        fwd_cites, meta = forward_sets(seeds, cap)
        fwd_cites = merge_citing(fwd_cites, meta)
        fwd = _two_or_more(fwd_cites)
        pools = None
        if emit_pools:
            pools = {"backward": {w: n for w, n in back.items() if w not in seedset}, "forward": dict(fwd)}
        recent = rank(fwd, meta, seedset, int(cap[:4]), cited, cap_date=cap, lang=lang)
    except BudgetUsedUp as exc:
        when = f"it resets in {exc.reset} seconds" if exc.reset is not None else "reset time unknown"
        print(f"OpenAlex refused with HTTP 429: the OpenAlex daily budget is used up; {when}. "
              f"OpenAlex cost this run: ${COST_USD:.4f}. Nothing written.")
        return 2
    except KeyRejected:
        print(f"{KEY_REJECTED}. Nothing written.")
        return 2
    except vc.LookupUnavailable as exc:
        print(f"Citation lookup unreachable: {_scrub(exc)}; nothing written.")
        return 2
    write(ws, classics, recent, len(seeds), len(refs), cap, COST_USD, REMAINING_USD,
          pools=pools, merge_capped=merge_capped)
    left = f"${REMAINING_USD}" if REMAINING_USD is not None else "unknown"
    print(f"cocitation: {len(seeds)} seeds, {len(classics)} classics, {len(recent)} recent; "
          f"OpenAlex cost ${round(COST_USD, 6)}, remaining {left}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
