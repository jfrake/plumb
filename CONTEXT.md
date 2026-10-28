# Plumb glossary

Terms used across the repo, the spec, and the issue tracker. Implementation detail belongs in `docs/spec.md`, not here.

- **Pilot paper**: one of the four submitted manuscripts the fall pilot runs on (an archival paper, an experiment, a qualitative paper with an event study, and a theory paper). Private. Never public.
- **Planted fixture**: a real, published, sole-authored paper with errors planted by hand and an answer key (`expected.yaml`). Public with the repo. Today: `packs/archival/fixtures/planted-1`.
- **Synthetic test paper**: a pack's fictional paper written by a blind agent with planted errors and decoys. Public. Every pack has one.
- **Shakedown run**: the first end-to-end run on a cleared paper that is not a pilot paper. Finds breakage and records cost per run. Not part of the evaluation.
- **Pilot run**: an evaluation run on a pilot paper under the preregistered design. Nothing about the pilot papers is touched before the preregistration is posted.
- **Condition**: a source of issues in the blind head-to-head: fixed-prompt ChatGPT, fixed-prompt Claude, Plumb on Auto, Plumb on Standard run by a reader blind to the referee reports, and the real referee reports where consent allows.
