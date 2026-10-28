#!/usr/bin/env python3
"""SubagentStop, Stop, and PostToolUse-on-Bash hook body: while a Plumb run is active, bind
sessions to it and note where each one's usage is logged. It never blocks or fails a session: it
always exits 0, prints nothing, and writes its own errors to ~/.config/plumb/hook_errors.log."""
from __future__ import annotations
import datetime
import json
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    home = os.environ.get("HOME")
    raw = sys.stdin.read()
    if not home:
        return
    try:
        from plumb import usage
        payload = json.loads(raw)
        if payload.get("hook_event_name") == "PostToolUse":
            usage.bind_hook(payload, home)
        else:
            usage.record_hook(payload, home)
    except Exception:  # noqa: BLE001 -- a hook must never fail a session; the error is logged
        stamp = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds")
        try:
            log = Path(home) / ".config" / "plumb" / "hook_errors.log"
            log.parent.mkdir(parents=True, exist_ok=True)
            with log.open("a", encoding="utf-8") as fh:
                fh.write(f"{stamp} record_usage\n{traceback.format_exc()}\n")
        except OSError:
            traceback.print_exc()


if __name__ == "__main__":
    main()
    sys.exit(0)
