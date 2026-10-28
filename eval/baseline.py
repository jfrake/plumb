#!/usr/bin/env python3
"""
Fixed-prompt baseline: one prompt, one PDF, two models over their APIs.

Sends a manuscript PDF with the prompt in eval/baseline_prompt.txt to gpt-6-astra (OpenAI
Responses API, reasoning effort high) and claude-fable-5-1 (Anthropic Messages API, effort high),
with no system prompt, no tools, and no sampling parameters. Each run is archived as it returns.

Usage:
    python3 eval/baseline.py paper.pdf --journal "Organization Science" --out ~/baseline/paper
    python3 eval/baseline.py --show-prompt-hash

Keys come from OPENAI_API_KEY and ANTHROPIC_API_KEY in the environment and are never written.
Run it only on papers whose consent record covers sending them to both providers.
The PDF is sent to OpenAI and Anthropic; Anthropic retains it for up to 30 days.

Output (one --out folder per paper, outside the repo):
    <out>/<model>/run-<n>/request.json    what was sent: hashes, prompt text, settings, versions
    <out>/<model>/run-<n>/response.json   the full response object as the API returned it
    <out>/<model>/run-<n>/issues.md       the model's text
    <out>/<model>/run-<n>/done            written last; a folder without it is redone
    <out>/manifest.json                   every run folder on disk with its status
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import platform
import sys
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
PROMPT_FILE = HERE / "baseline_prompt.txt"
# sha256 of eval/baseline_prompt.txt. The preregistration cites this hash; the script refuses to
# run if the file no longer matches it. Print it with --show-prompt-hash.
PROMPT_SHA256 = "4658fe67db80c86896bdd4bc8f0d0b8470a708c270bd733416c5f3d0694a7666"

OPENAI_MODEL = "gpt-6-astra"
ANTHROPIC_MODEL = "claude-fable-5-1"
MODELS = (OPENAI_MODEL, ANTHROPIC_MODEL)
KEY_VARS = {OPENAI_MODEL: "OPENAI_API_KEY", ANTHROPIC_MODEL: "ANTHROPIC_API_KEY"}
EFFORT = "high"
# Anthropic requires max_tokens; 64000 is a ceiling, not a sampling parameter, and the response
# is streamed so the request cannot hit an HTTP timeout. OpenAI's max_output_tokens is left unset.
ANTHROPIC_MAX_TOKENS = 64000
# OpenAI stores responses, with the PDF they were given, for 30 days by default; the baseline turns
# that off. Anthropic has no such switch and retains the PDF for up to 30 days.
OPENAI_STORE = False
# Size limits, checked before any call. Anthropic caps a request at 32 MB, and the PDF travels as
# base64 (4/3 of its size) next to the prompt; OpenAI caps each file at 50 MB, and the limit is
# applied to the base64 data URL too, to stay on the safe side of which size it means.
MB = 1024 * 1024
ANTHROPIC_REQUEST_LIMIT = 32 * MB
OPENAI_FILE_LIMIT = 50 * MB
# One attempt per run: the SDKs' automatic retries are off so nothing is retried silently.
TIMEOUT_SECONDS = 3600.0
RUN_FILES = ("request.json", "response.json", "issues.md")
DONE_FILE = "done"


class BaselineError(Exception):
    """A condition that stops the script before or between runs."""


# --- hashes and the prompt ---

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def prompt_file_sha256() -> str:
    return sha256_bytes(PROMPT_FILE.read_bytes())


def load_prompt_template() -> str:
    """The prompt file's text, after checking its hash against the pinned constant."""
    found = prompt_file_sha256()
    if found != PROMPT_SHA256:
        raise BaselineError(f"{PROMPT_FILE.name} has sha256 {found}, not the pinned {PROMPT_SHA256}; "
                            "the prompt is fixed for the preregistration, so restore the file or update "
                            "the pin and the preregistration together")
    return PROMPT_FILE.read_text(encoding="utf-8").rstrip("\n")


def fill_prompt(template: str, journal: str) -> str:
    if "{journal}" not in template:
        raise BaselineError("the prompt template has no {journal} slot")
    return template.replace("{journal}", journal)


# --- the two API calls (the SDKs load only here, so the rest of Plumb never needs them) ---

def call_openai(pdf_bytes: bytes, filename: str, prompt: str) -> dict:
    """gpt-6-astra over the Responses API: the PDF as an input_file plus the prompt in one user turn.
    Returns the full response as a plain dict.

    Shape from developers.openai.com/api/docs/guides/pdf-files (base64 file_data in an input_file
    block) and developers.openai.com/api/docs/guides/reasoning (reasoning.effort). No tools, no
    web search, no system or developer message, no temperature. store=False: by default OpenAI
    keeps a response, with the PDF it was given, for 30 days on the dashboard.
    """
    from openai import OpenAI

    client = OpenAI(max_retries=0, timeout=TIMEOUT_SECONDS)
    data = base64.b64encode(pdf_bytes).decode("ascii")
    response = client.responses.create(
        model=OPENAI_MODEL,
        reasoning={"effort": EFFORT},
        store=OPENAI_STORE,
        input=[{"role": "user", "content": [
            {"type": "input_file", "filename": filename, "file_data": f"data:application/pdf;base64,{data}"},
            {"type": "input_text", "text": prompt},
        ]}],
    )
    return response.model_dump(mode="json")


def call_anthropic(pdf_bytes: bytes, filename: str, prompt: str) -> dict:
    """claude-fable-5-1 over the Messages API: a base64 PDF document block then the prompt in one
    user turn. Returns the full message as a plain dict.

    Thinking is always on for this model and is controlled by output_config.effort; no thinking
    parameter, no system prompt, no tools, no temperature. Streamed so a long turn cannot hit an
    HTTP timeout; the final message is the same object a non-streamed call returns. The server-side
    fallbacks parameter is deliberately omitted: with it a refusal would be re-run on another model,
    and a baseline run must never be served by a model other than the one requested. A refusal
    comes back as stop_reason "refusal" and is archived and flagged as such.
    """
    import anthropic

    client = anthropic.Anthropic(max_retries=0, timeout=TIMEOUT_SECONDS)
    data = base64.standard_b64encode(pdf_bytes).decode("ascii")
    with client.messages.stream(
        model=ANTHROPIC_MODEL,
        max_tokens=ANTHROPIC_MAX_TOKENS,
        output_config={"effort": EFFORT},
        messages=[{"role": "user", "content": [
            {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": data},
             "title": filename},
            {"type": "text", "text": prompt},
        ]}],
    ) as stream:
        message = stream.get_final_message()
    return message.to_dict()


def response_text(model: str, response: dict) -> str:
    """The model's text: output_text parts of message items (OpenAI) or text blocks (Anthropic)."""
    if model == OPENAI_MODEL:
        return "".join(part.get("text", "") for item in response.get("output") or []
                       if item.get("type") == "message" for part in item.get("content") or []
                       if part.get("type") == "output_text")
    return "".join(block.get("text", "") for block in response.get("content") or [] if block.get("type") == "text")


def openai_refusals(response: dict) -> list:
    """The refusal parts of the message items, if the model declined instead of answering."""
    return [part.get("refusal", "") for item in response.get("output") or [] if item.get("type") == "message"
            for part in item.get("content") or [] if part.get("type") == "refusal"]


CLEAN_FINISH = ("completed", "end_turn")


def response_finish(model: str, response: dict) -> str:
    """How the run ended. "completed" or "end_turn" means nothing went wrong; anything else names the
    problem: a refusal (with Anthropic's category), an incomplete response (with OpenAI's reason), an
    error object, or a stop at the output cap."""
    if model == OPENAI_MODEL:
        status = response.get("status") or "unknown"
        if openai_refusals(response):
            return "refusal"
        error = response.get("error") or {}
        if error:
            return f"{status}: {error.get('code') or error.get('message') or 'error'}"
        details = response.get("incomplete_details") or {}
        if status == "incomplete" or details:
            return f"incomplete: {details.get('reason') or 'unknown reason'}"
        return status
    stop = response.get("stop_reason") or "unknown"
    details = response.get("stop_details") or {}
    if stop == "refusal" and details.get("category"):
        return f"refusal: {details['category']}"
    return stop


def finish_note(model: str, response: dict, finish: str) -> str:
    """What to tell the user about a run that did not end cleanly, with the text of a refusal or error."""
    if finish in CLEAN_FINISH:
        return ""
    extras = []
    if model == OPENAI_MODEL:
        extras += [t for t in openai_refusals(response) if t]
        error = response.get("error") or {}
        if error.get("message"):
            extras.append(error["message"])
    else:
        details = response.get("stop_details") or {}
        if details.get("explanation"):
            extras.append(details["explanation"])
    return finish + ("; " + " | ".join(extras) if extras else "")


def caller(model: str):
    """Looked up at call time so a test can replace either function on the module."""
    return {OPENAI_MODEL: call_openai, ANTHROPIC_MODEL: call_anthropic}[model]


def library_versions() -> dict:
    out = {}
    for name in ("openai", "anthropic"):
        try:
            out[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            out[name] = None
    return out


# --- runs and the manifest ---

def run_folder(out: Path, model: str, n: int) -> Path:
    return out / model / f"run-{n}"


def run_is_complete(folder: Path) -> bool:
    """The done marker is written last, after the three files, so its presence means all of them
    landed whole; a folder from an interrupted run has no marker and is redone."""
    return all((folder / name).is_file() for name in RUN_FILES + (DONE_FILE,))


def write_atomic(path: Path, text: str) -> None:
    """Write to a sibling temp file, then rename over the target, so a reader never sees a half file."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def write_json(path: Path, data) -> None:
    write_atomic(path, json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n")


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise BaselineError(f"cannot read {path}: {type(e).__name__}: {e}")


def do_run(out: Path, model: str, n: int, pdf: Path, pdf_bytes: bytes, journal: str, prompt: str) -> dict:
    """Call the model once and archive the request, the response, the text, and last the done marker
    holding the manifest entry. A failed call leaves no marker, so the folder is redone next time."""
    folder = run_folder(out, model, n)
    folder.mkdir(parents=True, exist_ok=True)
    request = {
        "model_requested": model, "run": n, "effort": EFFORT,
        "journal": journal, "pdf": pdf.name, "pdf_sha256": sha256_bytes(pdf_bytes),
        "prompt_file": PROMPT_FILE.name, "prompt_sha256": PROMPT_SHA256,
        "prompt_text": prompt, "prompt_text_sha256": sha256_bytes(prompt.encode("utf-8")),
        "system_prompt": None, "tools": [], "temperature": None,
        "anthropic_max_tokens": ANTHROPIC_MAX_TOKENS if model == ANTHROPIC_MODEL else None,
        "store": OPENAI_STORE if model == OPENAI_MODEL else None,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python_version": platform.python_version(), "library_versions": library_versions(),
    }
    write_json(folder / "request.json", request)
    response = caller(model)(pdf_bytes, pdf.name, prompt)
    write_json(folder / "response.json", response)
    write_atomic(folder / "issues.md", response_text(model, response))
    finish = response_finish(model, response)
    entry = {"model": model, "run": n, "folder": f"{model}/run-{n}",
             "status": "complete" if finish in CLEAN_FINISH else f"complete ({finish})",
             "model_returned": response.get("model"), "finish": finish,
             "note": finish_note(model, response, finish) or None,
             "timestamp_utc": request["timestamp_utc"]}
    if model == OPENAI_MODEL and openai_refusals(response):
        entry["refusal"] = "\n".join(openai_refusals(response))
    write_json(folder / DONE_FILE, entry)
    return entry


def runs_on_disk(out: Path, events: dict) -> list:
    """One manifest entry per <model>/run-<n> folder under out, in model order then run order. A
    complete folder's entry is its done marker; this invocation's events (a failure, say) override."""
    runs = []
    for model in MODELS:
        folders = []
        for p in (out / model).glob("run-*") if (out / model).is_dir() else []:
            if p.is_dir() and p.name[4:].isdigit():
                folders.append((int(p.name[4:]), p))
        for n, folder in sorted(folders):
            if (model, n) in events:
                runs.append(events[(model, n)])
            elif run_is_complete(folder):
                runs.append(read_json(folder / DONE_FILE))
            else:
                runs.append({"model": model, "run": n, "folder": f"{model}/run-{n}", "status": "incomplete"})
    return runs


def write_manifest(out: Path, head: dict, events: dict) -> None:
    write_json(out / "manifest.json", dict(head, runs=runs_on_disk(out, events)))


def check_out_folder(out: Path, head: dict) -> None:
    """Refuse a folder inside the repo, and a folder whose manifest was written for another paper or
    with other settings; one --out folder holds one paper under one set of settings."""
    try:
        out.resolve().relative_to(REPO.resolve())
    except ValueError:
        pass
    else:
        raise BaselineError(f"--out {out} is inside the repo; baseline outputs go outside it")
    manifest = out / "manifest.json"
    if not manifest.is_file():
        return
    old = read_json(manifest)
    if old.get("pdf_sha256") not in (None, head["pdf_sha256"]):
        raise BaselineError(f"--out {out} already holds runs for another PDF (sha256 {old['pdf_sha256']}); "
                            "use one --out folder per paper")
    for field in ("journal", "prompt_sha256", "effort", "run_of_record"):
        if field in old and old[field] != head[field]:
            raise BaselineError(f"--out {out} was written with {field} = {old[field]!r}, not {head[field]!r}; "
                                "use another --out folder for other settings")


def check_size(models: list, pdf_bytes: bytes, prompt: str) -> None:
    """Refuse a PDF a requested provider would reject for size, in one line, before anything is sent."""
    encoded = 4 * ((len(pdf_bytes) + 2) // 3)
    anthropic_request = encoded + len(prompt.encode("utf-8")) + 4096
    too_big = []
    if ANTHROPIC_MODEL in models and anthropic_request > ANTHROPIC_REQUEST_LIMIT:
        too_big.append(f"Anthropic (request {anthropic_request / MB:.1f} MB, limit {ANTHROPIC_REQUEST_LIMIT / MB:.0f} MB)")
    if OPENAI_MODEL in models and encoded > OPENAI_FILE_LIMIT:
        too_big.append(f"OpenAI (file {encoded / MB:.1f} MB, limit {OPENAI_FILE_LIMIT / MB:.0f} MB)")
    if too_big:
        raise BaselineError(f"the PDF is {len(pdf_bytes) / MB:.1f} MB, too large for " + " and ".join(too_big)
                            + "; shrink the PDF before running the baseline")


def check_keys(models: list) -> None:
    missing = [KEY_VARS[m] for m in models if not os.environ.get(KEY_VARS[m])]
    if missing:
        raise BaselineError("missing API key in the environment: " + ", ".join(missing)
                            + "; export it and run again (the script never stores keys)")


def read_pdf(pdf: Path) -> bytes:
    if not pdf.is_file():
        raise BaselineError(f"no such file: {pdf}")
    data = pdf.read_bytes()
    if not data.startswith(b"%PDF"):
        raise BaselineError(f"{pdf} does not start with %PDF; the baseline sends a PDF")
    return data


# --- CLI ---

def parse_args(argv) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Send one fixed prompt and a PDF to gpt-6-astra and claude-fable-5-1; archive every run.",
        epilog="Run it only on papers whose consent record covers sending them to both providers.\n"
               "The PDF is sent to OpenAI and Anthropic; Anthropic retains it for up to 30 days.\n\n"
               "Examples:\n"
               "  python3 eval/baseline.py paper.pdf --journal \"Organization Science\" --out ~/baseline/paper\n"
               "  python3 eval/baseline.py --show-prompt-hash",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf", nargs="?", help="the manuscript PDF")
    ap.add_argument("--journal", default="", help="fills the prompt's {journal} slot")
    ap.add_argument("--out", default="", help="output folder for this paper; must be outside the repo")
    ap.add_argument("--models", default=",".join(MODELS),
                    help="comma-separated subset of: " + ", ".join(MODELS) + " (default both)")
    ap.add_argument("--runs", type=int, default=3, help="runs per model (default 3)")
    ap.add_argument("--run-of-record", type=int, default=1,
                    help="the run that enters the main analysis; recorded in the manifest (default 1)")
    ap.add_argument("--show-prompt-hash", action="store_true", help="print the prompt file's sha256 and exit")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    try:
        return _main(args)
    except BaselineError as e:
        print(f"baseline: {e}", file=sys.stderr)
        return 2


def _main(args) -> int:
    if args.show_prompt_hash:
        print(prompt_file_sha256())
        return 0
    if not args.pdf or not args.journal or not args.out:
        raise BaselineError("pdf, --journal, and --out are required")
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    unknown = [m for m in models if m not in MODELS]
    if unknown:
        raise BaselineError("unknown model(s): " + ", ".join(unknown) + "; choose from " + ", ".join(MODELS))
    if args.runs < 1 or not 1 <= args.run_of_record <= args.runs:
        raise BaselineError("--runs must be at least 1 and --run-of-record must be within it")

    template = load_prompt_template()
    prompt = fill_prompt(template, args.journal)
    pdf = Path(args.pdf)
    pdf_bytes = read_pdf(pdf)
    pdf_sha = sha256_bytes(pdf_bytes)
    out = Path(args.out).expanduser()
    head = {"pdf": pdf.name, "pdf_sha256": pdf_sha, "prompt_file": PROMPT_FILE.name,
            "prompt_sha256": PROMPT_SHA256, "journal": args.journal, "effort": EFFORT,
            "run_of_record": args.run_of_record}
    check_out_folder(out, head)
    check_size(models, pdf_bytes, prompt)
    check_keys(models)

    out.mkdir(parents=True, exist_ok=True)
    events = {}
    for model in models:
        for n in range(1, args.runs + 1):
            folder = run_folder(out, model, n)
            if run_is_complete(folder):
                print(f"{model} run-{n}: already complete, skipped")
                write_manifest(out, head, events)
                continue
            print(f"{model} run-{n}: calling", flush=True)
            try:
                entry = do_run(out, model, n, pdf, pdf_bytes, args.journal, prompt)
            except Exception as e:
                events[(model, n)] = {"model": model, "run": n, "folder": f"{model}/run-{n}", "status": "failed",
                                      "error": f"{type(e).__name__}: {e}"}
                write_manifest(out, head, events)
                raise BaselineError(f"{model} run-{n} failed: {type(e).__name__}: {e}; "
                                    "nothing was retried; run the same command again to redo it")
            events[(model, n)] = entry
            write_manifest(out, head, events)
            print(f"{model} run-{n}: {entry['status']}, returned model {entry['model_returned']}")
            if entry["note"]:
                print(f"baseline: {model} run-{n} did not end cleanly ({entry['note']}); the run is archived "
                      "as is and will not be redone", file=sys.stderr)
    print(f"manifest: {out / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
