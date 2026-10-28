#!/usr/bin/env python3
"""Stress-test each point in a draft review against the paper using the Codex CLI.

Codex is a text agent (not multimodal), so the manuscript is fed as extracted text
(pymupdf) rather than as an uploaded PDF.

Usage:
  python codex_stress_test.py <pdf_path> <draft_path> <prompt_path> <output_dir>
      [--parallel N] [--model MODEL] [--response-letter PATH] [--timeout SECONDS] [--resume]
      [--mode points|missed|prepare|summarize] [--engine codex|claude]

--mode prepare writes the same inputs for a Claude agent instead of calling Codex: input/paper.txt,
input/points.json, one input/<point_id>.txt per point (the message Codex would get), and
run_manifest.json. After the agent has written one JSON file per point, --mode summarize
--engine claude adds each point's text and writes summary.json. Neither mode needs the codex CLI.
The Codex run (--mode points) also writes usage.json with the token counts `codex exec --json`
printed, when it printed any.

By default every per-point JSON is overwritten on each run so that stale results from a
previous version of review.txt cannot persist. Pass --resume to skip files that already
exist (useful when resuming an interrupted run mid-way through the same review.txt).

Requires the `codex` CLI on PATH (authenticated via ~/.codex). No API key env var needed.
Each point is sent to `codex exec --skip-git-repo-check --sandbox read-only -o <file> -`
with the prompt on stdin; the final agent message (the JSON object) is read back from <file>.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time

# Section headers are ALL CAPS on their own line; body runs to the next ALL CAPS header.
SECTION_RE = re.compile(
    r"^(MAJOR|MINOR) COMMENTS\s*\n(.+?)(?=^[A-Z][A-Z ]{2,}\s*$|\Z)",
    re.DOTALL | re.MULTILINE,
)
# Numbered item: "<digits>. " at line start, content until the next numbered line or EOF.
ITEM_RE = re.compile(r"^(\d+)\.\s+(.+?)(?=^\d+\.\s+|\Z)", re.DOTALL | re.MULTILINE)


def parse_review(text: str):
    """Return [{point_id, section, index, text}] for every numbered MAJOR/MINOR item."""
    out = []
    for m in SECTION_RE.finditer(text):
        section = m.group(1).lower()
        for item in ITEM_RE.finditer(m.group(2)):
            out.append({
                "point_id": f"{section}-{int(item.group(1))}",
                "section": section,
                "index": int(item.group(1)),
                "text": item.group(2).strip(),
            })
    return out


# Plumb drafts: a fix list numbers items "### N. title"; a report numbers comments
# "N. " at line start in one sequence and may end with a REFERENCES section.
FIX_ITEM_RE = re.compile(r"^### (\d+)\.\s+(.+?)(?=^### \d+\.\s+|^## |\Z)", re.DOTALL | re.MULTILINE)
REPORT_ITEM_RE = re.compile(r"^(\d+)\.\s+(.+?)(?=^\d+\.\s+|^REFERENCES\s*$|\Z)", re.DOTALL | re.MULTILINE)


def parse_draft(text: str):
    """Return points from a Plumb fix list or report, in parse_review's shape."""
    items, section = list(FIX_ITEM_RE.finditer(text)), "issue"
    if not items:
        items, section = list(REPORT_ITEM_RE.finditer(text)), "comment"
    return [{"point_id": f"{section}-{int(m.group(1))}", "section": section,
             "index": int(m.group(1)), "text": m.group(2).strip()} for m in items]


def extract_paper_text(pdf_path: pathlib.Path) -> str:
    try:
        import pymupdf
    except ImportError:
        print("ERROR: pymupdf not installed. Run: pip install pymupdf", file=sys.stderr)
        sys.exit(1)
    doc = pymupdf.open(pdf_path)
    return "\n\n".join(f"[page {i + 1}]\n{page.get_text()}" for i, page in enumerate(doc))


def build_user_message(point: dict) -> str:
    return (
        f"POINT ID: {point['point_id']}\n"
        f"SECTION: {point['section'].title()} Comments, item #{point['index']}\n\n"
        "POINT TEXT (plain text from the referee report):\n"
        "----- BEGIN POINT -----\n"
        f"{point['text']}\n"
        "----- END POINT -----\n\n"
        "Stress-test this point against the manuscript text above following the checklist. "
        "Return ONLY the JSON object per the schema. No prose outside the JSON block."
    )


def _strip_to_json(raw: str):
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip()).strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", s, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


RETRY_NOTE = ("\n\nYour last reply was not valid JSON ({error}). Send the same JSON object again, valid "
              "this time: inside a string value, write every double quote as \\\".")


USAGE_KEYS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")


def _find_usage(obj):
    """The last dict in obj, at any depth, with integer input_tokens and output_tokens. A
    total_token_usage value (codex-cli's cumulative usage, seen in "token_count" events) is
    preferred over a sibling last_token_usage (that event's per-turn usage)."""
    found = None
    if isinstance(obj, dict):
        if "total_token_usage" in obj:
            cumulative = _find_usage(obj["total_token_usage"])
            if cumulative:
                return cumulative
        if isinstance(obj.get("input_tokens"), int) and isinstance(obj.get("output_tokens"), int):
            found = obj
        for k, v in obj.items():
            if k == "total_token_usage":
                continue
            found = _find_usage(v) or found
    elif isinstance(obj, list):
        for v in obj:
            found = _find_usage(v) or found
    return found


def parse_usage(stdout: str) -> dict:
    """Token counts from `codex exec --json` output: the last usage object it printed. Empty when
    it printed none (an older Codex, or a changed event format)."""
    last = None
    for line in (stdout or "").splitlines():
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        last = _find_usage(obj) or last
    if not last:
        return {}
    return {k: int(last.get(k) or 0) for k in USAGE_KEYS}


def call_codex(system_prompt: str, user_msg: str, paper_text: str,
               model: str | None, timeout: int, max_retries: int = 2, usage_out: dict | None = None) -> str:
    """Run one codex exec call; return the captured final message (expected JSON). Given
    usage_out, fill it with the token counts Codex printed."""
    prompt = (
        system_prompt
        + "\n\n===== BEGIN MANUSCRIPT (extracted text) =====\n"
        + paper_text
        + "\n===== END MANUSCRIPT =====\n\n"
        + user_msg
        + "\n\nReturn ONLY the JSON object. No markdown fence, no prose."
    )
    cmd = ["codex", "exec", "--skip-git-repo-check", "--sandbox", "read-only", "--color", "never", "--json"]
    if model:
        cmd += ["-m", model]
    last_err = None
    for attempt in range(max_retries):
        out_file = tempfile.NamedTemporaryFile("w+", suffix=".json", delete=False).name
        try:
            # Run in an empty directory so Codex has no local files near it to read.
            with tempfile.TemporaryDirectory() as scratch:
                r = subprocess.run(
                    cmd + ["-o", out_file, "-"],
                    input=prompt, capture_output=True, text=True, timeout=timeout, cwd=scratch,
                )
            msg = pathlib.Path(out_file).read_text().strip()
            if not msg:
                raise RuntimeError(f"empty codex output (exit {r.returncode}): {r.stderr[-300:]}")
            if usage_out is not None:
                usage_out.update(parse_usage(r.stdout))
            return msg
        except Exception as e:  # noqa: BLE001 -- retry on any failure
            last_err = e
            if attempt < max_retries - 1:
                time.sleep(10 * (attempt + 1))
        finally:
            try:
                os.unlink(out_file)
            except OSError:
                pass
    raise RuntimeError(f"codex failed after {max_retries} attempts: {last_err}")


def run_missed_pass(review_text, paper_text, system_prompt, out_dir, model, timeout):
    """One codex call: find serious criticisms ABSENT from the review. Writes missed.json."""
    user_msg = (
        "FULL DRAFT REFEREE REPORT:\n"
        "----- BEGIN REVIEW -----\n"
        f"{review_text}\n"
        "----- END REVIEW -----\n\n"
        "Identify serious, well-supported criticisms of the manuscript that are ABSENT "
        "from this review. Do not restate points the review already makes. "
        "Return ONLY the JSON object per the schema."
    )
    raw = call_codex(system_prompt, user_msg, paper_text, model, timeout)
    parsed = _strip_to_json(raw)
    (out_dir / "missed.json").write_text(json.dumps(parsed, indent=2))
    print("[ok] missed-criticism pass -> missed.json")


def process_point(point, out_dir, system_prompt, paper_text, model, timeout, resume=False, usage=None):
    pid = point["point_id"]
    out_path = out_dir / f"{pid}.json"
    if resume and out_path.exists():
        print(f"[skip] {pid} (exists, --resume mode)")
        return pid, "skipped"
    raw = None
    slot = {}
    if usage is not None:
        usage[pid] = slot
    try:
        raw = call_codex(system_prompt, build_user_message(point), paper_text, model, timeout, usage_out=slot)
        try:
            parsed = _strip_to_json(raw)
        except json.JSONDecodeError as first:
            # One retry, with the parse error: Codex sometimes leaves a quote unescaped.
            more = {}
            raw = call_codex(system_prompt, build_user_message(point) + RETRY_NOTE.format(error=first),
                             paper_text, model, timeout, usage_out=more)
            for k, v in more.items():
                slot[k] = slot.get(k, 0) + v
            parsed = _strip_to_json(raw)
        parsed["_point_text"] = point["text"]
        out_path.write_text(json.dumps(parsed, indent=2))
        print(f"[ok]   {pid}  verdict={parsed.get('verdict', '?')}  rec={parsed.get('recommendation', '?')}")
        return pid, "ok"
    except json.JSONDecodeError as e:
        if raw is not None:
            out_path.with_suffix(".raw.txt").write_text(raw)
        print(f"[json] {pid} — JSON parse failed, raw saved: {e}", file=sys.stderr)
        return pid, "json_error"
    except Exception as e:  # noqa: BLE001
        print(f"[err]  {pid} — {e}", file=sys.stderr)
        return pid, f"error: {e}"


def _count_by(rows, key):
    out = {}
    for r in rows:
        v = r.get(key) or "null"
        out[v] = out.get(v, 0) + 1
    return out


def write_summary(out_dir: pathlib.Path, engine: str = "codex"):
    rows = []
    for p in sorted(out_dir.glob("*.json")):
        if p.name in ("summary.json", "missed.json", "run_manifest.json", "usage.json"):
            continue
        try:
            d = json.loads(p.read_text())
        except json.JSONDecodeError:
            continue
        rows.append({
            "point_id": d.get("point_id", p.stem),
            "verdict": d.get("verdict"),
            "already_addressed": d.get("already_addressed", {}).get("status"),
            "rebuttal_strength": d.get("rebuttal_strength"),
            "recommendation": d.get("recommendation"),
            "severity_recommended": d.get("severity_recalibration", {}).get("recommended_severity"),
            "n_factual_errors": len(d.get("factual_errors", []) or []),
            "n_logical_weaknesses": len(d.get("logical_weaknesses", []) or []),
        })
    summary = {
        "n_points": len(rows),
        "engine": engine,
        "verdicts": _count_by(rows, "verdict"),
        "already_addressed": _count_by(rows, "already_addressed"),
        "rebuttal_strength": _count_by(rows, "rebuttal_strength"),
        "recommendations": _count_by(rows, "recommendation"),
        "points": rows,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\nSummary: {json.dumps(summary['recommendations'])}")


def write_usage(out_dir: pathlib.Path, usage: dict, elapsed: float) -> dict:
    """usage.json: the token counts Codex printed for each point, and the run's wall-clock time."""
    got = [u for u in usage.values() if u]
    doc = {"engine": "codex", "available": bool(got), "points_with_usage": len(got),
           "points": {pid: (u or None) for pid, u in sorted(usage.items())},
           "total": {k: sum(u.get(k, 0) for u in got) for k in USAGE_KEYS},
           "elapsed_seconds": round(elapsed, 1)}
    (out_dir / "usage.json").write_text(json.dumps(doc, indent=2))
    return doc


def prepare(out_dir: pathlib.Path, points: list, paper_text: str, resume: bool = False) -> None:
    """Inputs for a Claude agent that runs the same stress test: the paper's text, each point's
    message as Codex would get it, and the list of points. Stale results go unless --resume."""
    if not resume:
        for p in list(out_dir.glob("*.json")) + list(out_dir.glob("*.raw.txt")):
            if p.name != "run_manifest.json":
                p.unlink()
    inp = out_dir / "input"
    inp.mkdir(exist_ok=True)
    (inp / "paper.txt").write_text(paper_text)
    (inp / "points.json").write_text(json.dumps(points, indent=2))
    for p in points:
        (inp / f"{p['point_id']}.txt").write_text(build_user_message(p))
    print(f"Prepared {len(points)} points in {inp}")


def summarize(out_dir: pathlib.Path, engine: str) -> int:
    """After an agent wrote one JSON file per point: add each point's text, write summary.json,
    and return 1 when a point has no valid JSON object."""
    points = json.loads((out_dir / "input" / "points.json").read_text())
    failed = []
    for p in points:
        path = out_dir / f"{p['point_id']}.json"
        try:
            d = _strip_to_json(path.read_text())
        except (OSError, ValueError) as e:
            d = e
        if not isinstance(d, dict):
            failed.append(p["point_id"])
            print(f"[err]  {p['point_id']} - no valid JSON object: {d}", file=sys.stderr)
            continue
        d.setdefault("_point_text", p["text"])
        path.write_text(json.dumps(d, indent=2))
    write_summary(out_dir, engine)
    if failed:
        print(f"ERROR: {len(failed)} point(s) have no valid JSON: {failed}", file=sys.stderr)
        return 1
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf_path")
    ap.add_argument("review_txt_path")
    ap.add_argument("prompt_path")
    ap.add_argument("output_dir")
    ap.add_argument("--parallel", type=int, default=4)
    ap.add_argument("--model", default=None, help="Codex model (defaults to ~/.codex config)")
    ap.add_argument("--response-letter", default=None)
    ap.add_argument("--timeout", type=int, default=300, help="Per-point codex timeout (seconds)")
    ap.add_argument("--mode", choices=["points", "missed", "prepare", "summarize"], default="points")
    ap.add_argument("--engine", choices=["codex", "claude"], default="codex",
                    help="who runs the stress test; summarize records it in summary.json")
    ap.add_argument(
        "--resume",
        action="store_true",
        default=False,
        help=(
            "Skip per-point files that already exist (resume an interrupted run). "
            "Default behavior (no --resume) overwrites every per-point JSON so that "
            "stale results from a previous review.txt never persist."
        ),
    )
    args = ap.parse_args()
    out_dir = pathlib.Path(args.output_dir)

    if args.mode == "summarize":
        sys.exit(summarize(out_dir, args.engine))

    if args.mode in ("points", "missed") and not shutil.which("codex"):
        print("ERROR: `codex` CLI not on PATH. Install/auth the Codex CLI (~/.codex).", file=sys.stderr)
        sys.exit(1)

    system_prompt = pathlib.Path(args.prompt_path).read_text()
    paper_text = extract_paper_text(pathlib.Path(args.pdf_path))
    if args.response_letter:
        paper_text += (
            "\n\n===== BEGIN RESPONSE LETTER (extracted text) =====\n"
            + extract_paper_text(pathlib.Path(args.response_letter))
            + "\n===== END RESPONSE LETTER =====\n"
        )
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.mode == "missed":
        review_text = pathlib.Path(args.review_txt_path).read_text()
        run_missed_pass(review_text, paper_text, system_prompt, out_dir, args.model, args.timeout)
        return

    draft_text = pathlib.Path(args.review_txt_path).read_text()
    points = parse_review(draft_text) or parse_draft(draft_text)
    if not points:
        print(
            "ERROR: no numbered points parsed from the draft. Expected '### N.' fix-list items, "
            "'N.' report comments, or MAJOR COMMENTS / MINOR COMMENTS sections.",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"Parsed {len(points)} points; paper text {len(paper_text):,} chars; engine={args.engine}")

    # RT13: write a manifest of every point_id being dispatched so that
    # verify_stress_test.py can detect points whose JSON failed to write.
    manifest_ids = [p["point_id"] for p in points]
    (out_dir / "run_manifest.json").write_text(
        json.dumps({"point_ids": manifest_ids}, indent=2)
    )
    print(f"Manifest written: {len(manifest_ids)} point_ids -> run_manifest.json")

    if args.mode == "prepare":
        prepare(out_dir, points, paper_text, args.resume)
        return

    results = {}
    usage = {}
    started = time.time()
    with cf.ThreadPoolExecutor(max_workers=args.parallel) as ex:
        futs = {
            ex.submit(
                process_point, p, out_dir, system_prompt, paper_text,
                args.model, args.timeout, args.resume, usage
            ): p["point_id"]
            for p in points
        }
        for f in cf.as_completed(futs):
            pid, status = f.result()
            results[pid] = status

    write_summary(out_dir)
    write_usage(out_dir, usage, time.time() - started)

    # RT13: exit nonzero if any point returned a non-ok worker result so the
    # orchestrator knows to treat this as a failed run rather than silently
    # continuing with incomplete output.
    failed = [pid for pid, status in results.items() if status not in ("ok", "skipped")]
    if failed:
        print(
            f"ERROR: {len(failed)} point(s) failed to produce valid JSON: {failed}",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
