#!/bin/bash
# Desktop notification where available; never fails.
MSG=$(cat | python3 -c "import sys,json; print(json.load(sys.stdin).get('message','Plumb needs you'))" 2>/dev/null || echo "Plumb needs you")
SAFE=$(printf '%s' "$MSG" | tr -d '"\\`$')
if command -v osascript >/dev/null 2>&1; then
  osascript -e "display notification \"$SAFE\" with title \"Plumb\"" >/dev/null 2>&1
elif command -v notify-send >/dev/null 2>&1; then
  notify-send "Plumb" "$MSG" >/dev/null 2>&1
fi
exit 0
