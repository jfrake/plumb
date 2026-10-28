# Platform actions: Codex

Requires multi-agent support. In `~/.codex/config.toml` set `[features] multi_agent = true`, and enable web search. `multi_agent = true` alone does not dispatch subagents: the instruction to use subagents must be explicit in what you tell Codex to do. Trust your actual tool list over this file.

## ASK
There is no question widget. Print the round as a numbered list. Give each question lettered options with the recommended one first, marked "(Recommended)". Then stop and wait for the user's reply. Parse replies like "1A 2C 3: free text". The user's reply gives you the letter, not the option's label; map that letter to its full option label before recording the answer with the CLI.
A free-text question (page follow-ups, corrections, edits, feedback) is asked as a plain chat message, not through the lettered-option tool.
For a question that allows several answers (the outputs at setup), say so and accept several letters, as in "2AB".

## Run folder
Pass `--cwd` with the directory Codex runs in to `plumb run-dir new` and `plumb run-dir find`.

## DISPATCH
spawn_agent with `fork_turns: "none"`, so the child starts with a clean context. The task is the agent file's path and the filled placeholders. Ask for a one- or two-sentence return.

The config is shared across platforms, so it may name Claude models. On Codex, always run `plumb models <depth> --platform codex`: it turns any Claude model in the config (the `sonnet`, `opus`, and `haiku` tier aliases or a `claude-` name) into `inherit`, so Codex only ever receives `inherit` or a Codex model named in the config. Never pass a Claude model to `spawn_agent`. If `spawn_agent` in your tool list takes a model parameter, pass the dispatch's model (see "Models" in SKILL.md) unless it is `inherit`. Otherwise every agent runs on the session's model; say so once in your first status line. `spawn_agent` takes no turn limit, so the Deep depth line in SKILL.md is length guidance only.

## PARALLEL
Spawn every agent in the group, then wait_agent in stretches of 300000-600000 ms. After each stretch, post one status line and check which children have finished. Do not poll in short intervals.

## TASKLIST
The plan tool if your tool list has one (update_plan). Otherwise print a short checklist when each stage starts and ends.

## WEB
The web search tool. If it is missing, tell the user to restart Codex with web search enabled, and stop.

## RUN
The shell tool.

## Usage
Codex runs no Plumb hooks, so `plumb usage report` records "Usage not measured in this app." and the README says so. Run the `plumb usage` commands the stage files name anyway.
