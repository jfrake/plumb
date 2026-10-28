#!/bin/bash
# SubagentStop and Stop: while a Plumb run is active, record where this session's usage is logged.
# Always exits 0 and prints nothing. With no active run it does nothing and starts no Python.
DIR="${HOME:-/nonexistent}/.config/plumb"
if [ -s "$DIR/active_runs.json" ]; then
  python3 "${0%/*}/record_usage.py" 2>>"$DIR/hook_errors.log"
else
  cat >/dev/null
fi
exit 0
