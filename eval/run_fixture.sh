#!/usr/bin/env bash
# Run Plumb on a fixture's planted paper at one depth, headlessly, then score the run.
#
# Usage:
#   bash eval/run_fixture.sh <fixture folder> <quick|standard|deep> <output folder> [--dry-run]
#        [--search-before YYYY-MM-DD] [claude flags...]
#
# <fixture folder> is packs/<pack>/fixtures/<id>/ (expected.yaml names the paper). The paper is
# copied to <output folder>/<fixture>-<depth>/, the claude CLI runs there so the run folder lands at
# <output folder>/<fixture>-<depth>/plumb_output/<date>/, and eval/score_fixture.py scores the run
# folder with the newest modification time, writing score.json beside it. --dry-run prints the
# claude command and stops. A Quick run writes no issues list; the scorer counts every design entry
# as missed and says so on the card.
#
# The script loads the plugin from its own checkout with --plugin-dir, so the run exercises this
# code and not an installed copy. Any arguments after the output folder (other than --dry-run) go to
# the claude call as given, each as one argument, so a path with spaces survives; the default
# --permission-mode acceptEdits is dropped when you pass your own --permission-mode.
#
# --search-before caps the run's web searches at that date (the paper's submission date), so the
# run cannot find the published article. Without the flag, a search_before date in expected.yaml
# is used; with neither, the run has no cap. Setup never asks about the cap: the prompt tells the
# skill to pass the date to plumb run-dir new --search-before. After a capped run, the runner checks
# that run.json holds the date and exits non-zero if it does not.
#
# Environment:
#   CLAUDE_BIN    the claude executable (default: claude on PATH)
#
# UNTESTED: the headless invocation below (the claude -p call and the setup answers in its prompt)
# has not been run end to end. The review skill asks its setup and consent questions with
# AskUserQuestion, which a -p session cannot answer, so the prompt states every answer and asks the
# skill to record them with plumb checkin. Whether the skill honours that, and which permission flags
# a full run needs, is settled by the shakedown run (ticket #22). The scorer this script calls is
# fully tested, and the tests cover this script with a stand-in claude.
set -euo pipefail

usage() { sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//'; }

if [ "$#" -lt 3 ]; then usage >&2; exit 1; fi
FIXTURE=$1
DEPTH=$2
OUT=$3
shift 3
DRY_RUN=0
EXTRA=()
OWN_MODE=0
CAP=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --search-before)
      [ "$#" -ge 2 ] || { echo "run_fixture: --search-before needs a date (YYYY-MM-DD)" >&2; exit 1; }
      CAP=$2; shift ;;
    *) EXTRA+=("$1"); [ "$1" = "--permission-mode" ] && OWN_MODE=1 ;;
  esac
  shift
done

case "$DEPTH" in
  quick) LABEL="B. Quick" ;;
  standard) LABEL="A. Standard (Recommended)" ;;
  deep) LABEL="C. Deep" ;;
  *) echo "run_fixture: depth must be quick, standard, or deep, not '$DEPTH'" >&2; exit 1 ;;
esac

HERE=$(cd "$(dirname "$0")/.." && pwd)
FIXTURE=$(cd "$FIXTURE" && pwd)
NAME=$(basename "$FIXTURE")
PACK_DIR=$(cd "$FIXTURE/../.." && pwd)
PACK=$(basename "$PACK_DIR")
KEY="$FIXTURE/expected.yaml"
[ -f "$KEY" ] || { echo "run_fixture: $KEY is missing" >&2; exit 1; }
PAPER=$(python3 -c 'import sys, yaml; print((yaml.safe_load(open(sys.argv[1])) or {}).get("paper") or "")' "$KEY")
[ -n "$PAPER" ] || { echo "run_fixture: $KEY names no paper" >&2; exit 1; }
[ -f "$FIXTURE/$PAPER" ] || { echo "run_fixture: $FIXTURE/$PAPER is missing" >&2; exit 1; }
if [ -z "$CAP" ]; then
  CAP=$(python3 -c 'import sys, yaml; v = (yaml.safe_load(open(sys.argv[1])) or {}).get("search_before"); print(v or "")' "$KEY")
fi
if [ -n "$CAP" ]; then
  python3 -c 'import sys, datetime; datetime.date.fromisoformat(sys.argv[1])' "$CAP" 2>/dev/null && [ "${#CAP}" = 10 ] \
    || { echo "run_fixture: search cap '$CAP' is not a YYYY-MM-DD date" >&2; exit 1; }
  CAP_LINE="Search date cap (an evaluation option, not a setup question): create the run folder with \
plumb run-dir new adding --search-before $CAP, so run.json holds search_before.

"
else
  CAP_LINE=""
fi
# A pack whose pack.yaml says overlay: true is run as an overlay, not as the paper type.
OVERLAY=$(python3 -c 'import sys, yaml, os
f = sys.argv[1]
meta = yaml.safe_load(open(f)) if os.path.isfile(f) else {}
print("yes" if isinstance(meta, dict) and meta.get("overlay") is True else "no")' "$PACK_DIR/pack.yaml")

if [ "$OVERLAY" = yes ]; then
  TYPE_ANSWER="the detected type, marked Recommended (the $PACK pack is an overlay, not a paper type)"
  OVERLAY_ANSWER="\"A. Run the $PACK checks\" for setup:overlay:$PACK, and \"B. Skip them\" for every other overlay"
else
  TYPE_ANSWER="\"$PACK\" (the fixture's pack; it is the detected type unless detection failed)"
  OVERLAY_ANSWER="\"B. Skip them\" for every setup:overlay:<pack> question"
fi

WORK="$OUT/$NAME-$DEPTH"
PROMPT="/plumb:review $PAPER

This is a headless evaluation run on a synthetic test paper that its authors planted errors in; it \
is their own paper, not a submission. No one can answer a question, so at every question in Stage 0 \
take the answer listed here without asking, record each with plumb checkin as the stage says, and \
run every later check-in at the Auto level (take the recommended option, --note auto).

${CAP_LINE}Setup, round 1: setup:permission \"A. It's mine or my coauthors'\"; setup:journal \"A. Organization \
Science\"; setup:depth \"$LABEL\"; setup:level \"D. Auto\"; setup:output \"A. Issues list\"; \
setup:output_dir \"A. Outputs will go to <run folder> (Recommended)\".

Consent screen: the coauthors agree to sending the paper to the model provider (coauthors_agree \
true); the ethics attestation is \"A. Yes, or the paper quotes none\" (irb_allows_excerpts true); \
provider terms: use the saved Anthropic answers when plumb provider-facts shows them fresh, otherwise \
write provider_trains_on_inputs and retention_days as null, and never run plumb provider-facts set; \
manuscript_text and search_queries go in egress; setup:stress_test \"B. Skip it\", so no \
codex_stress_test and no stress_test_provider. Run plumb consent-check as the stage says.

Recap: setup:recap \"A. Start the review and send the paper (Recommended)\".

Setup, round 2 (Auto: use these answers, ask nothing): setup:type $TYPE_ANSWER; setup:second_type \
the detected second type, or \"None\"; setup:contribution the detected contribution type; overlays: \
$OVERLAY_ANSWER; setup:journal_confirm \"A. Keep Organization Science (Recommended)\" if it applies."

CLAUDE_BIN=${CLAUDE_BIN:-claude}
ARGS=(-p --plugin-dir "$HERE")
[ "$OWN_MODE" = 1 ] || ARGS+=(--permission-mode acceptEdits)
ARGS+=("${EXTRA[@]+"${EXTRA[@]}"}")

if [ "$DRY_RUN" = 1 ]; then
  echo "cd $WORK"
  printf '%s' "$CLAUDE_BIN"; printf ' %q' "${ARGS[@]}"; echo ' "<prompt>"'
  echo "python3 $HERE/eval/score_fixture.py $FIXTURE $WORK/plumb_output/<newest by mtime> --out $WORK/score.json"
  echo
  echo "prompt:"
  echo "$PROMPT"
  exit 0
fi

mkdir -p "$WORK"
cp "$FIXTURE/$PAPER" "$WORK/$PAPER"
(cd "$WORK" && "$CLAUDE_BIN" "${ARGS[@]}" "$PROMPT")

# The newest run by modification time: a name sort would put 2026-10-05/ after 2026-10-05-2/.
RUN=$(ls -dt "$WORK"/plumb_output/*/ 2>/dev/null | head -n 1 || true)
[ -n "$RUN" ] || { echo "run_fixture: no run folder under $WORK/plumb_output/ after the claude call" >&2; exit 1; }
python3 "$HERE/eval/score_fixture.py" "$FIXTURE" "$RUN" --out "$WORK/score.json"

if [ -n "$CAP" ]; then
  GOT=$(python3 -c 'import sys, json, os
for f in (os.path.join(sys.argv[1], ".workspace", "run.json"), os.path.join(sys.argv[1], "run.json")):
    if os.path.isfile(f):
        print(json.load(open(f)).get("search_before") or ""); break' "$RUN")
  [ "$GOT" = "$CAP" ] || { echo "run_fixture: asked for a search cap of $CAP, but the run recorded '${GOT}'; its searches may not have been capped" >&2; exit 1; }
fi
