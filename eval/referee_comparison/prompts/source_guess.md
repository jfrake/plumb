# Blind source-guess agent

Source: the implementation plan for the blind rating (October 20, 2026), Task 2.

A fresh agent reads only `items_public.json`, which holds each item's id, paper label, title, and text, and nothing about its source, class, or match.

Instructions given to the agent:

- Some of these points come from human referees and some from an AI review tool.
- For every item, guess its source and say how confident you are.
- Write `guesses.json`: a list of `{"id": str, "guess": "referee"|"plumb", "confidence": "low"|"high"}`, one entry per item.

After the run:

1. Score with `python3 pool/score_guess.py items.json guesses.json`.
2. Rewrite every item the agent guessed correctly with high confidence (`confident_correct`).
3. Rerun the validator, write the public file again, and run a fresh blind agent once more.
4. The target is an accuracy of 0.60 or less.
