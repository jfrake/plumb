Pack: inference
# Inference claims

## Issues
1. The pre-speech placebo is read as a null ("did not predict"), but the estimate the paper prints for it is significant by the paper's own threshold and larger than the main effect it is meant to validate.
   Check: I16 (with I13 wording). Estimate: BR in the pre-speech two-day window, text-only re-estimate of Model 2 (robustness check for the main result; not listed under `Inference:`). Tag: [paper]
   Paper's best case: Because the speech text is not public until delivery, a BR effect that appears only on the speech day and not before it would support the reading that the speech itself moves the VIX.
   Evidence: p. 25 prints β = .041, "σ2" = 0.017, p = .017. Stage 1 note int-placebo (inference_numbers.md, Notes) gives the interval 0.00768 to 0.07432 when "σ2" is read as a standard error. That interval excludes zero and contains the Table 2 Model 2 main effect of 0.036 (table_02.csv:2:3). The placebo point estimate (0.041) is larger than the main effect (0.036). The hypothesis ledger search note records the same mismatch (hypothesis_ledger.md, H1). The test the paper offers is a significant positive estimate, and the sentence reads it as absence of an effect.
   Excerpt: "Third, consistent with the expectation that the speech is not made public until the date and time denoted on the transcript, the BR did not predict market uncertainty for the two-day event window before the day of the speech (β = .041, σ2 = 0.017, p = .017, adjusted R-squared = 0.083)."
   Page: 25
   Severity: Weakens a claim
   What would settle it: Report the placebo estimate beside the speech-day estimate in a table, with the same specification, standard errors, and N, plus a test of the difference between the two windows; and state what the placebo result means for H1 as printed, or revise the sentence so it matches the printed p-value.

2. The main result's significance mark is one level too generous, and whether its interval excludes zero depends on the printed rounding.
   Check: I13. Estimate: BR, Table 2 Model 2, 0.036*** (0.018) (main result, H1). Tag: [paper]
   Paper's best case: The Table 2 note states one-tailed tests for directional hypotheses, H1 is directional, and on that reading the estimate clears the 0.05 level.
   Evidence: Core star check (arithmetic.md, `stars_vs_se` table_02.csv BR / Model 2): |t| 1.919 to 2.086, one-tailed p 0.019 to 0.027, so the printed *** (p < 0.01) is not supported; the digits support **. Stage 1 note int-h1: the 95 percent interval is 0.00072 to 0.07128, and whether it excludes zero depends on rounding. The same BR coefficient is marked ** in Models 3 and 5 (0.034, SE 0.018; 0.041, SE 0.019; table_02.csv:2:4, 2:6). The Discussion (p. 25) then states the finding as proof of causation. The hypothesis verdict itself belongs to the core hypothesis audit; this entry concerns only the mark and how close the estimate sits to the threshold.
   Excerpt: "Using speeches made by the Chair of the United States Federal Reserve from 1998 to 2014, I proved that reaffirming the assumptions underlying the monetary policy framework causes uncertainty in financial markets around the world."
   Page: 57 (Table 2); 25 (Discussion)
   Severity: Weakens a claim
   What would settle it: Correct the mark, report the exact p-value and the interval for BR in Model 2, and state the size of the evidence at the level the text relies on rather than as proof.

3. The stated size of the main effect does not follow from the reported coefficient, and no interval is given for it.
   Check: I15. Estimate: BR, Table 2 Model 2 (main result, H1). Tag: [paper]
   Paper's best case: The paper does translate the coefficient into the outcome's units over a one-SD change in BR and explains why a change of that size matters to traders and hedgers.
   Evidence: Stage 1 flag 1 (inference_numbers.md, Record mag-h1): with BR = 0.036 and a logged outcome, a 0.21 change in BR gives a 0.759 percent change in the VIX (0.730 to 0.788 given rounding), not the 1.0 percent the text states. The text uses 0.21 for one SD; Table 1 prints 0.22 (table_01.csv:3:3; numeric fidelity owns that comparison). The stated 1.0 percent is then carried into the H2 and H3 conditional statements on pp. 18-19 ("the aforementioned 1.0 percent increase"). No interval accompanies the magnitude; applying the Stage 1 interval for the coefficient (0.00072 to 0.07128) to a 0.21 change would run from near zero to roughly 1.5 percent.
   Excerpt: "A one standard deviation increase in the BR of a speech (i.e., 0.21)—which is equivalent to adding five backing-related paragraphs in a 25 paragraph speech—will increase this expected range by 1.0 percent."
   Page: 18
   Severity: Weakens a claim
   What would settle it: Recompute the one-SD effect from the printed coefficient and the Table 1 SD, report it with its interval, and carry the corrected figure into the H2 and H3 paragraphs.

4. Most robustness and specification checks are described but not shown, including a GEE re-estimation of all analyses and several alternative control specifications.
   Check: I12 (with I13 recomputability). Estimate: BR (main result, H1); BR * Speech positive tone (H2); BR * Business media fear (H3). Tag: [paper]
   Paper's best case: The paper names each alternative it tried (GEE with AR(1) within Chair, backing-feature controls, prior-VIX-change controls at 1, 10, and 30 days, local-audience controls, federal funds rate in place of dummies, two- and four-day fear windows, 15- and 150-day existing-uncertainty windows) and reports that each leaves the results unchanged.
   Evidence: pp. 23-25. The GEE results are summarized as "strong support for all my hypotheses" with no coefficient, standard error, or N. The feature controls "produced consistent results", prior-VIX controls "did not change my results", and the alternative specifications left findings "consistent". Local-audience controls "does not change my results" (p. 23). Stage 1 ledger (inference_ledger.md, Table 2, "Other estimates of the same result") confirms no estimates are reported for any of these. I searched the methods, results, Table 1 and 2 notes, and figure pages (pp. 49-57); the manuscript has no appendix or footnotes. Given that the main estimate sits near the 0.05 one-tailed threshold (issue 2), whether it holds across these choices is not visible to a reader.
   Excerpt: "When doing so, I find strong support for all my hypotheses."
   Page: 24-25
   Severity: Weakens a claim
   What would settle it: An appendix table reporting the BR, BR * tone, and BR * fear estimates, standard errors, and N under each alternative, with the GEE estimates and their standard errors in their own columns.

5. The sample is cut on the model's own residuals and the estimator is described two ways, and no results are shown with the excluded speeches or under the other estimator.
   Check: I12. Estimate: BR, Table 2 Model 2 (main result, H1), and all Table 2 estimates. Tag: [paper]
   Paper's best case: Removing seven speeches with studentized residuals beyond plus or minus three is a common way to keep a few extreme VIX days from driving OLS estimates.
   Evidence: p. 12: 344 speeches, seven removed by studentized residual, final N 337; Table 1 and Table 2 report N = 339 (numeric fidelity owns the count mismatch). The residual rule depends on the fitted model, so which speeches are dropped depends on the specification used to compute residuals, which the paper does not name. The text calls the estimator "OLS regression with year-fixed effects" (p. 18); the Table 2 note says "robust regressions with robust standard errors", and robust regression in the sense of reweighting observations is a different estimator from OLS with robust standard errors. No reason is given for the cutoff beyond the outlier analysis, and no estimate on the full 344 is reported.
   Excerpt: "Seven speeches were removed because, based on an outlier analysis, their studentized residuals exceeded plus or minus three."
   Page: 12
   Severity: Weakens a claim
   What would settle it: State which model produced the residuals, name the estimator used in Table 2 exactly, and report Table 2 Model 2 to 5 on the full 344 speeches beside the trimmed sample.

6. The financial-crisis extension rests on a "marginally significant" interaction whose p-values hold only on an unstated one-tailed reading, and on a 48-speech subsample defined by cuts on both moderators that cannot carry the Model 2 specification as printed.
   Check: I13 and I12. Estimate: BR * crisis dummy and BR in crisis subsamples, text-only re-estimates of Model 2 (not listed under `Inference:`; restated in the Discussion as validation of the theory). Tag: [paper]
   Paper's best case: The paper labels the crisis analysis as supplemental and "preliminary" (p. 20), motivates the crisis window from an outside timeline, and the direction of each estimate fits the extension it proposes.
   Evidence: p. 20: the interaction with year fixed effects is "marginal significance" (β = -0.051, "σ2" = 0.038, p = .088), and only without year fixed effects is it significant (p = .026). Stage 1 note (inference_numbers.md, Notes): |t| about 1.34 and 1.97, so p = .088 and p = .026 hold only on one-tailed readings, and the paper states no tails for these text-only tests; the Table 2 note covers only Table 2. p. 21: the reversal comes from crisis speeches above the mean on tone and below the mean on fear, N = 48, with the two cutoffs chosen without stated reasons. Stage 1 note: Table 2 reports df = 58 for Model 2 (table_02.csv:59:3), more parameters than the 48 observations, so the subsample estimate cannot come from the specification the text names. The Discussion (p. 26) presents these results as validation. Whether the crisis effect differs from the non-crisis effect, given that one is significant and the other is not, is left to the nonlinear pack.
   Excerpt: "The interaction term reaches marginal significance (β = -0.051, σ2 = 0.038, p = .088, adjusted R-squared = 0.191)."
   Page: 20-21; 26
   Severity: Weakens a claim
   What would settle it: State the tails for each crisis test, report the crisis models in a table with their full specification and N, say which controls and fixed effects were dropped to fit 48 speeches, and either justify the mean cuts on tone and fear or show the estimate across other cutoffs. Present "marginal" results as exploratory rather than as validation.

7. The Discussion builds a theoretical point on the word-count coefficient, whose printed digits cannot be tested and whose size is never stated.
   Check: I13 and I15. Estimate: Speech word count, Table 2 Models 1-5, -0.000*** (0.000) (control, restated as a result in the Discussion). Tag: [paper]
   Paper's best case: The coefficient is marked at the 0.01 level in every model, so the paper may have a precise estimate that simply rounds to zero at three decimals.
   Evidence: table_02.csv:40:2 to 41:6 print -0.000 (0.000) in every model; the core arithmetic flags the zero standard errors (arithmetic.md, `se_positive`), and Stage 1 lists the claim as not computable (inference_numbers.md, Not computed, wordcount-text). The Discussion then states that this result is "strong support for the signaling perspective" (p. 28), without a magnitude in the outcome's units.
   Excerpt: "Specifically, Table 2 indicates that longer speeches significantly reduce market uncertainty."
   Page: 28
   Severity: Weakens a claim
   What would settle it: Rescale word count (for example, per 1,000 words) so the coefficient and standard error print with significant digits, and state the effect of a meaningful change in speech length with its interval.

8. The uncertainty figure for every text-only estimate is labeled "σ2", which reads as a variance, so none of those tests can be recomputed from the label as written.
   Check: I13 (recomputability; rule 6). Estimate: crisis interaction with and without year fixed effects, crisis subsample, crisis N = 48 subsample, pre-speech placebo (pp. 20, 21, 25). Tag: [paper]
   Paper's best case: The printed p-values agree with the coefficients when "σ2" is read as a standard error (Stage 1 records crisis-int-fe, crisis-int-nofe, crisis-n48), so the label is likely a typesetting slip.
   Evidence: Stage 1 note (inference_numbers.md, Notes) on the "σ2" label. None of these five estimates reports N except the N = 48 subsample, and none reports its standard-error type.
   Excerpt: "If I split the sample and run Model 2 on speeches only given during the financial crisis period, the main effect results for H1 drop below significance (β = 0.035, σ2 = 0.036, p = .335, adjusted R-squared = 0.244)."
   Page: 20
   Severity: Minor
   What would settle it: Relabel the statistic as the standard error, and give N and the error type for each text-only estimate.

9. Two significance marks on Table 2 terms that are not hypothesis tests do not match the test the note states for them.
   Check: I13. Estimate: Business media fear, Model 4, 0.005** (2.924); Speech positive tone, Models 1, 3, 5 (-0.006* and -0.007** with SE 0.004) (lower-order terms, not hypotheses). Tag: [paper]
   Paper's best case: Neither mark changes which hypotheses the text calls supported, and the H2 and H3 product terms carry the hypotheses.
   Evidence: Core star check (arithmetic.md, `stars_vs_se` Business media fear / Model 4): |t| 0.002, p 0.499, printed **. The coefficient also changes sign and magnitude relative to Models 1-3 and 5 (-1.616 to -0.537), which numeric fidelity notes. For Speech positive tone, -0.007 (0.004) gives |t| about 1.75: two-tailed p about .08 supports *, one-tailed p about .04 supports **; the note says controls are two-tailed, so the marks follow a one-tailed reading for a term with no stated hypothesis (numeric_fidelity.md, Issue 16).
   Excerpt: "Significance tests are one-tailed for directional hypotheses, two-tailed for control variables."
   Page: 57
   Severity: Minor
   What would settle it: Check the Model 4 Business media fear entry against the output, and state which tails apply to the moderator main effects.

## Checked and fine
- I11, all hypotheses: each of H1-H3 is tested on one outcome and one focal term; Models 2-5 are re-estimates, not a family (inference_numbers.md, Notes; Table 2, p. 56). The crisis analyses are taken up under I12 and I13 above.
- I13, tails: the Table 2 note states one-tailed tests for directional hypotheses and two-tailed for controls (p. 57), and H1-H3 are all directional (pp. 9, 11, 12).
- I13, BR * Speech positive tone, Model 3, -0.056*** (0.020), and Model 5, -0.049*** (0.020): marks agree with the one-tailed reading the note states (arithmetic.md raises no flag; p. 56).
- I13, BR * Business media fear, Model 4, 30.590*** (12.626), and Model 5, 26.293** (12.482): marks agree with the one-tailed reading the note states (arithmetic.md raises no flag; p. 56). The *** in Model 4 relies on the one-tailed reading, which the note declares.
- I13, H1-H3 support sentences (pp. 18-19): Stage 1 claim records h1-text, h2-text, h3-text hold at 0.10 on the stated one-tailed reading (inference_claims_check.md, 0 flagged).
- I13, local-audience correlations (pp. 22-23): r = 0.25, -0.34, and 0.35 clear the 0.01 threshold the Table 1 note gives for N = 339 (|r| > 0.14, p. 54).
- I15, magnitude format: the paper states the main effect in the outcome's units over a one-SD change in BR and the conditional effects at plus or minus one SD of each moderator (pp. 18-19). The arithmetic is taken up in issue 3; the conditional effects of the interaction terms are left to the nonlinear pack.
- Exclusions: no SC or shift-share IV estimates in this paper (fingerprint `Designs:` lists only the ITCV selection analysis).
- Inputs: dropped_flags.md lists none; hypothesis_checks.md has no rows under "Not computed", so no tails point arises from it.
