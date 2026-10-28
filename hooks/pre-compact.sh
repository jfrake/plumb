#!/bin/bash
# Re-inject the run brief before context compaction so a long review can continue.
# Never exits nonzero and prints nothing when no brief is found (both hooks in
# this directory must be silent, harmless no-ops in the common case).
cat >/dev/null

# A run's brief is <run folder>/.workspace/brief.md. Plumb lists every run folder in
# $HOME/.config/plumb/runs.json, so read that first and take the most recently modified
# brief of an unfinished run. Without one, look for <root>/plumb_output/<date>/ in the
# project directory or up to two levels below it.
BRIEF=$(python3 -c "
import glob, json, os
matches = []
home = os.environ.get('HOME')
if home:
    try:
        runs = json.load(open(os.path.join(home, '.config', 'plumb', 'runs.json')))
    except (OSError, ValueError):
        runs = []
    for r in runs if isinstance(runs, list) else []:
        if isinstance(r, dict) and r.get('run_dir') and not r.get('finished'):
            b = os.path.join(r['run_dir'], '.workspace', 'brief.md')
            if os.path.isfile(b):
                matches.append(b)
if not matches:
    base = os.environ.get('CLAUDE_PROJECT_DIR', '.')
    for depth in ('', '*', os.path.join('*', '*')):
        matches += glob.glob(os.path.join(base, depth, 'plumb_output', '*', '.workspace', 'brief.md'))
if matches:
    matches.sort(key=os.path.getmtime, reverse=True)
    print(matches[0])
" 2>/dev/null)

if [ -n "$BRIEF" ] && [ -f "$BRIEF" ]; then
  echo "## Plumb resume context"
  echo
  cat "$BRIEF"
fi
exit 0
