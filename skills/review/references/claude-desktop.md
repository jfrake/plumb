# Platform actions: Claude desktop app (Claude and Code tabs)

## ASK
AskUserQuestion. Up to four questions per call, two to four options each. The user can pick "Other" to type. Put the recommended option first with "(Recommended)" in its label.
A free-text question (page follow-ups, corrections, edits, feedback) is asked as a plain chat message, not through the lettered-option tool.
A question that allows several answers (the outputs at setup) sets `multiSelect: true`.

## Run folder
In the Code tab, pass `--cwd` with the working directory to `plumb run-dir new` and `plumb run-dir find`. In the Claude tab there is no project directory: leave `--cwd` out, so the run folder goes next to the PDF.

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
In the Code tab plugin hooks run, as in Claude Code, and Stage 7 totals the run's tokens and time. In the Claude tab they do not run, so `plumb usage report` records "Usage not measured in this app." and the README says so. Run the `plumb usage` commands the stage files name in both tabs.
