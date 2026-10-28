#!/bin/bash
# Install Plumb's skill for Codex. Default destination: $CODEX_SKILLS_DIR, else ~/.codex/skills; override with --dest.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DEST="${CODEX_SKILLS_DIR:-$HOME/.codex/skills}"
if [ "${1:-}" = "--dest" ]; then
  if [ "$#" -lt 2 ]; then
    echo "Usage: install.sh [--dest DIR]" >&2
    exit 2
  fi
  DEST="$2"
fi
mkdir -p "$DEST"
for d in "$ROOT"/skills/*/; do
  name="plumb-$(basename "$d")"
  rm -rf "$DEST/$name"
  cp -R "$d" "$DEST/$name"
done
CFG="${PLUMB_CONFIG_DIR:-$HOME/.config/plumb}"
mkdir -p "$CFG"
printf '%s\n' "$ROOT" > "$CFG/plugin_root"
echo "Installed plumb skills to $DEST. Copy adapters/codex/AGENTS.md into the folder where you run Codex, or merge it into your AGENTS.md."
