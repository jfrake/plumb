#!/bin/bash
# Block edits to an author's submitted or final files.
INPUT=$(cat)
# Normalize lexically (no filesystem access, no symlink resolution) so a path like
# proj/submitted/x/plumb_output/../paper.pdf can't dodge the submitted/ check below by
# hiding behind the plumb_output/ exemption.
FILE=$(printf '%s' "$INPUT" | python3 -c "import sys,json,os; d=json.load(sys.stdin); print(os.path.normpath((d.get('tool_input') or {}).get('file_path','')))" 2>/dev/null)
# plumb_output/ is the tool's own output folder, even when the paper sits in a protected folder.
case "$FILE" in
  */plumb_output/*) exit 0 ;;
esac
case "$FILE" in
  */submitted/*|*/final/*|*/published/*|*/archived/*|*-FINAL.*|*-SUBMITTED.*|*-PUBLISHED.*)
    python3 -c "import json,sys; print(json.dumps({'hookSpecificOutput':{'hookEventName':'PreToolUse','permissionDecision':'deny','permissionDecisionReason':'Plumb does not edit submitted or final files: '+sys.argv[1]}}))" "$FILE"
    exit 2 ;;
esac
exit 0
