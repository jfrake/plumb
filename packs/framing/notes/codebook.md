# Framing codebook

The definitions behind `data/norms.yaml`. The framing record applies them to the manuscript exactly as they were applied to the 1,000 published introductions, so the diagnosis compares like with like (the published introductions were coded with two more puzzle roots, now counted under standing and hidden anomaly). Code what the introduction **does**, not what it should have done. Use only the names in this codebook.

## What to read

- Read the abstract and the introduction. Both count: if the abstract states the framing more sharply than the introduction, code from it.
- The introduction ends at the first major heading after it, such as Theory, Background, Literature Review, Hypotheses, Setting, Methods, or Data. If there's no such heading, it ends where the paper turns to building theory or describing data.
- If the introduction is very short (two paragraphs or fewer), also read the first section after it, up to its first subheading or about two pages, and code from all three. Say so in `intro_location`.
- Ignore cover pages, title pages, and footnotes.
- Read further only to settle a design question you can't answer from what you've read.

## Rules for the root and its strength

These are two separate questions. First decide which root the introduction points toward. Then decide how strongly it plays that root.

**The root** is the move the introduction points toward to justify the paper, usually in the paragraphs that state the problem and the contribution. Always pick the closest root, even when the introduction plays it weakly. Use `none` only when the introduction points toward no root at all, and `none fits` only when it plays a clear move that no root describes.

**Strength:**
- **carried:** the introduction shows the root's trouble. It names the theory or belief and says what it gets wrong, can't explain, or wrongly limits. Asserting that something is unknown doesn't count.
- **gestured:** the root's pieces are there (a theory is named, a new domain or a mechanism is pointed to), but the justification the introduction leans on is a weak frame, most often that the topic is unstudied.
- **absent:** no root is played. The justification is a weak frame alone.

**Close calls that recur:**
- *Wider reach* is carried when the introduction argues that the theory was thought not to apply, or that the new level or outcome is a real test of it. "Not yet studied in setting Y" is wider reach gestured, resting on unstudied topic.
- *Theory repair* is carried when the introduction says the theory conflates things or doesn't imply what it claims. "The theory has neglected a distinction" is theory repair gestured.
- *Hidden anomaly* is carried when the introduction shows a pattern that a named theory says shouldn't exist. A pattern that is merely understudied is gestured.
- *Head-to-head* needs two named rival explanations tested against each other. One belief tested with better evidence is *shaky foundation*.
- *Rival account* proposes a new explanation for a known pattern. *Theory repair* fixes the existing explanation itself.

## Roots

**Puzzles: something in the world is unexplained.**

1. **Standing anomaly.** A known pattern still lacks a sound explanation, and the paper explains it plus what the old theory explained. Either the field knows the pattern is unexplained, or it credits a theory with explaining it when the theory's assumptions rarely hold there. Foil: the received theory, which says the pattern shouldn't happen or is credited with explaining it.
2. **Hidden anomaly.** A pattern the field hasn't seen as a puzzle contradicts our best theories, and the paper points it out and resolves it. The pattern is in plain sight and taken for granted, or the author's own data turned it up. Foil: the theory that, taken seriously, says the pattern shouldn't exist.

**Challenges to an accepted account.**

3. **Rival account.** The accepted theory explains the evidence, but so does a rival the paper proposes, ideally with fewer assumptions or new predictions. Foil: the accepted explanation.
4. **Shaky foundation.** A belief rests on thin or confounded evidence, and the paper supplies better evidence. Foil: the belief, and the alternative the old evidence couldn't rule out.
5. **Theory repair.** The theory itself is flawed: it conflates distinct things, or doesn't imply what it claims. The paper fixes it. Foil: the theory as currently stated.
6. **Wider reach.** A favored theory explains more than we thought: a new level, domain, or outcome. Foil: the view that the theory's reach stops where it has been applied.

**An opposed pair.**

7. **Head-to-head.** Two rival explanations, and the paper's data or method picks the winner, or shows where each applies more strongly. Foil: two confident camps.
8. **Dissolved debate.** An apparent debate is misconceived, because both sides are special cases of a larger view. Foil: the debate as the field has framed it.

## Weak frames

These go in `rests_on`, never in `root`.

- **Unstudied topic.** The justification is that X hasn't been studied, or not in setting Y, without showing that this causes trouble for any theory.
- **Process for its own sake.** "We know X affects Y, but not how": opening up a process without showing that it changes a prediction.
- **Literature-only puzzle.** The puzzle exists only inside the literature, such as a tension between papers, with no real-world pattern behind it.
- **No stated claim.** The paper sets out to explore, with no claim about what readers should believe afterward.

## Portrayal: how the introduction portrays prior work

- **scattered:** relevant work is spread across streams not usually cited together, and the paper connects them.
- **cumulative:** a mature, agreed-upon line of work that has advanced step by step.
- **contested:** an important domain where researchers disagree.

## Push: how much the paper claims to change that work

- **completes:** the literature is on the right track, and the paper fills in what's missing.
- **adds:** the literature missed a perspective, which the paper adds alongside existing work.
- **overturns:** the literature is wrong, and the paper replaces it.

## Surprise: which belief the paper says it reverses

Pick the main belief the introduction says readers hold and the paper reverses. Code `none` if the paper extends or confirms without reversing anything.

About one thing:
- **order:** what seems disordered is ordered, or the reverse.
- **one-or-many:** what seems one thing is several, or several things are one.
- **unit:** what seems individual is collective, or the reverse.
- **scope:** what seems local is general, or the reverse.
- **stability:** what seems stable is changing, or the reverse.
- **effectiveness:** what seems to work doesn't, or the reverse.
- **value:** what seems bad is good, or the reverse.

About relations between things:
- **connection:** what seem unrelated are related, or the reverse.
- **compatibility:** what seem unable to coexist do, or the reverse.
- **direction:** a relationship that seems positive is negative (or not linear), or the reverse.
- **likeness:** what seem opposite are alike, or the reverse.
- **causal order:** what seems the cause is the effect (or they cause each other), or the reverse.

## Conditions

- **design:** the paper's main empirical approach. Use `abductive or mixed` only when qualitative and quantitative evidence each carry a substantial part of the argument, or when the paper's method is to move back and forth between data and theory. A quantitative study with a few interviews for context is coded by its main evidence (archival, survey, or experiment), and so is a paper that calls itself abductive but uses one kind of data. Use `conceptual` for papers with no data.
- **home_literature:** the conversation the paper mainly addresses, judged from its framing and the work it cites, not from the journal.
- **level:** micro for individuals and small groups, meso for teams, units, and organizations, macro for fields, industries, markets, and institutions.
- **idea:** the kind of contribution: a new mechanism, a boundary condition, a new construct, a new phenomenon, adjudicating between rivals, or better evidence for an existing claim.
