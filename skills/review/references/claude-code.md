# Platform actions: Claude Code

## ASK
AskUserQuestion. Up to four questions per call, two to four options each. The user can pick "Other" to type. Put the recommended option first with "(Recommended)" in its label.
A free-text question (page follow-ups, corrections, edits, feedback) is asked as a plain chat message, not through the lettered-option tool.
A question that allows several answers (the outputs at setup) sets `multiSelect: true`.

## Run folder
Pass `--cwd` with the session's working directory to `plumb run-dir new` and `plumb run-dir find`.

## DISPATCH
The Task tool (subagent). Pass the agent file's path and the filled placeholders ({WORKSPACE}, {PLUGIN}) in the prompt. Tell the agent to return one or two sentences.

Pass the dispatch's model (see "Models" in SKILL.md) as the Task tool's `model` parameter. If the value is `inherit`, leave `model` out, so the agent uses the session's model. The Task tool takes no turn limit. An agent file's `maxTurns` line is guidance the agent reads, and the Deep depth line in SKILL.md raises it.

## PARALLEL
Several Task calls in one message. Wait for all before the next step.

## TASKLIST
The task-list tool in your tool list (TodoWrite or TaskCreate). One item per stage.

## WEB
WebSearch to find, WebFetch to read a page.

## RUN
Bash.

## Usage
Plumb's plugin hooks (SubagentStop and Stop) note where each transcript is while a run is active, and `plumb usage report` totals them at Stage 7. Run the `plumb usage` commands the stage files name; nothing else is needed.
