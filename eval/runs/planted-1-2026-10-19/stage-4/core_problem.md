# Core Problem (Skeptical Reviewer)

Contribution type: theory testing (run.json; stage-0/phase1_summary.md). Headline estimate located through stage-1/hypothesis_ledger.json, row H1 (carries_main_result): Table 2, Model 2, BR = 0.036*** (0.018), N = 339 (extracted_tables/table_02.csv; p. 56).

Paper's best version (contract 8): speeches are scheduled about six months ahead and backing-heavy speeches are written one to six months ahead and rarely changed in the final week (pp. 21-22). So the backing ratio is fixed well before the speech, and a VIX change on the speech day that rises with BR is the market's response to hearing the backing made explicit (pp. 9, 18, 25).

The single most fundamental weakness: the paper's own falsification test fails, and the text reports it as a pass. BR predicts the VIX change before the speech exists in public about as strongly as it predicts the change on the speech day. So the design does not separate an effect of the speech from a standing association between backing-heavy speeches and rising uncertainty. Findings 2 and 3 explain why nothing else in the paper closes that gap.

## 1. The pre-speech placebo is significant and at least as large as the main effect, so the speech-day coefficient cannot be read as the speech's effect

- **Claim.** The placebo window is the paper's only test whose prediction differs between "the speech causes uncertainty" and "BR is attached to periods or occasions of rising uncertainty." The paper's mechanism requires a zero placebo. The printed placebo is not zero, and the paper describes it as a null. As printed, the evidence supports the second reading at least as well as the first, and H1's causal claim ("I proved that reaffirming the assumptions underlying the monetary policy framework causes uncertainty," p. 25) does not follow.
- **Location.** Robustness Checks, p. 25 (text lines on the "two-day event window before the day of the speech"); Table 2 Model 2, p. 56; Discussion, p. 25.
- **Evidence (verified facts).**
  - p. 25, verbatim: "consistent with the expectation that the speech is not made public until the date and time denoted on the transcript, the BR did not predict market uncertainty for the two-day event window before the day of the speech (β = .041, σ2 = 0.017, p = .017, adjusted R-squared = 0.083)."
  - Table 2, Model 2 (extracted_tables/table_02.csv): BR = 0.036 (0.018).
  - Arithmetic (mine, normal approximation): placebo t = 0.041 / 0.017 = 2.41, two-tailed p = .016, which matches the printed p = .017 if the "σ2" value is the standard error. The placebo therefore clears .05 even two-tailed. The main effect is t = 0.036 / 0.018 = 2.00, one-tailed p = .023, two-tailed p = .046.
  - The placebo point estimate (0.041) exceeds the speech-day estimate (0.036). The paper reports no test of the difference and no speech-day estimate net of the pre-speech association.
  - Stage 1 flagged the text-number contradiction (stage-1/flags.json, id 8: "As printed, the falsification test fails").
- **Inference (kept apart from the facts).** A speech cannot move the VIX before it is delivered, and the paper rules out leakage by its own premise ("the speech is not made public until the date and time denoted on the transcript," p. 25). A positive pre-speech association of the same size means something correlated with BR moves the VIX across the days around high-BR speeches. That same thing can produce the speech-day coefficient with no contribution from the speech. The theory-devil report gives one concrete version: backing rises when the framework is already being questioned, which is the reading the paper itself offers on p. 34 ("a high backing ratio reflects low levels of cognitive legitimacy because it indicates that people feel the need to discuss, or request others to discuss, these assumptions directly"). On that reading BR measures declining taken-for-grantedness rather than causing it, which reverses the arrow the contribution (pp. 2-3, 32-34) depends on. FOMC-cycle position (stage-3/adjacent.md finding 4) is a second candidate. I do not claim to know which common cause operates; the point is that the paper's design, by its own test, leaves room for one.
- **What would settle it (paper).** Report the placebo in a table alongside Model 2, day by day from t-5 to t-1 and for t0, with the same controls and sample. Test whether the t0 coefficient exceeds the pre-speech coefficients. Re-estimate Model 2 controlling for the pre-speech VIX change over the same window used in the placebo (p. 24 reports 1-, 10-, and 30-day average controls only in prose, with no coefficients). Correct the p. 25 sentence so it describes what the numbers show. I make no prediction about what these checks will show.
- **Adjudication type.** paper (the contradiction and the magnitudes are on pp. 25 and 56); judgment (what the failed placebo implies for the causal reading).
- **Proposed severity.** Undermines the main claim.

## 2. The design's only defense against a slow-moving common cause is interview testimony about drafting lead times, and lead times do not address it

- **Claim.** The endogeneity section argues that because high-BR speeches are written one to six months ahead, "acute market factors arising on or near the speech date are extremely unlikely to influence the speechwriting process" (p. 23). That rules out reverse causation from the speech day's own shocks. It does not rule out a condition that starts before drafting and persists through the speech, which is the kind of factor the placebo points to (Finding 1). Early drafting of high-BR speeches is compatible with a contested period that lasts months.
- **Location.** pp. 21-24 (interviews; acute versus systemic factors; ITCV); Table 1 (BR correlation with unemployment 0.26, per stage-3/theory_devil_report.md and summary).
- **Evidence (verified facts).** The identification strategy is selection on observables with year, topic, and audience fixed effects (p. 18; Table 2 note, p. 57). The two "systemic factor" tests are (a) an average BR gap of 0.21 between speeches within three days of each other, N = 40 pairs, and (b) lagged VIX-change controls reported as "did not change my results" with no estimates (pp. 23-24). The ITCV is given as 0.014 in the text (p. 24) and drawn at 0.030 in Figure 7 (p. 53); stage-1/flags.json id 12 notes that at 0.014 at least two observed covariates exceed it.
- **Inference.** Test (a) shows BR varies across nearby speeches, which bears on whether a common cause drives all speeches, not on whether it drives the VIX movement around a given high-BR speech. Test (b) has no reported numbers. The ITCV argument is internally inconsistent across text and figure. None of these speaks to the pre-speech association in Finding 1.
- **Adjudication type.** paper; judgment.
- **Proposed severity.** Weakens a claim (it compounds Finding 1 rather than standing alone).

## 3. The headline estimate sits at the edge of significance, so the placebo comparison is decisive rather than a footnote

- **Claim.** With the main effect at t = 2.00 under a one-tailed test, and the placebo at t = 2.41, the data give no basis for treating the speech-day estimate as the more credible of the two. The *** on BR in Model 2 overstates it (stage-1/flags.json ids 6 and 9: one-tailed p about .02 supports **).
- **Location.** Table 2, Model 2, p. 56; Table 2 note, p. 57 ("Significance tests are one-tailed for directional hypotheses").
- **Evidence (verified facts).** BR = 0.036 (0.018); thresholds * p<0.1, ** p<0.05, *** p<0.01 (extracted_tables/table_02_note.txt). Practical-significance text uses 1.0 percent for a one-SD change (p. 18); 0.036 x 0.21 = 0.76 percent (stage-1/flags.json ids 13, 25).
- **Inference.** The fragility of H1 alone would be a "Weakens a claim" item. Combined with Finding 1, it means the paper cannot currently show that BR's association with the VIX is larger on the speech day than on days when no speech has occurred.
- **Adjudication type.** paper.
- **Proposed severity.** Weakens a claim.

No external sources were needed for these findings; every point rests on numbers and text printed in the paper or on arithmetic from them. Search cap 2016-06-01 respected (no searches run).
