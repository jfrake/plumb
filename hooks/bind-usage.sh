#!/bin/bash
# PostToolUse on Bash: fires on every Bash call, so the fast path must not stat or start anything.
# It exits at once unless stdin contains the text "usage mark"; only then does it start Python,
# which checks whether the command is really this session's own `plumb usage mark <ws>` call and,
# if so, binds this session to that run. Always exits 0 and prints nothing.
payload="$(cat)"
case "$payload" in
  *"usage mark"*)
    DIR="${HOME:-/nonexistent}/.config/plumb"
    mkdir -p "$DIR" 2>/dev/null
    printf '%s' "$payload" | python3 "${0%/*}/record_usage.py" 2>>"$DIR/hook_errors.log"
    ;;
esac
exit 0
