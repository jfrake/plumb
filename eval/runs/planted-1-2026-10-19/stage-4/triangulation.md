## Triangulation Report

Agent: Triangulation Agent. Inputs read: stage-0 (phase1_summary, contribution_defense, fingerprint), stage-1 (numeric_fidelity, arithmetic, hypothesis_ledger.json), stage-2 (timeline, dgp_map), stage-3 (alternatives, argument_map, mechanism_discrimination, theory_devil_report), run.json, brief.md, and PDF pp. 12-35 and 50-53 (the methods, results, discussion, and all figures). Table digits come from `extracted_tables/table_01.csv` and `extracted_tables/table_02.csv`. No external search was run; the 2016-06-01 cap is respected. Page numbers are PDF pages, which match the printed folios.

Scope notes. The `Designs:` line lists only Selection (ITCV), not DiD or IV, so the straight-line test applies and the IV block does not. `nonlinear` is in `run.json` packs, so the difference-in-significance check on split samples within this one study (crisis vs. full sample, p. 20) is left to the nonlinear pack; this report uses those numbers only for the additivity check. Stage 1 already flagged the placebo's "did not predict" wording (Issue 1), the Model 2 stars, the Model 4 fear cell, the Model 5 adjusted R-squared, the ITCV 0.014 vs. 0.030 conflict, the effect-size arithmetic, and N = 337 vs. 339. They are not re-flagged here except where a cross-result implication is new.

Paper's best version (contract 8): BR is fixed months before the speech, so a speech-day VIX rise that scales with BR, survives a wide control set and audience fixed effects, is absent before the speech, and is moderated by tone and fear in the predicted directions shows that reaffirming taken-for-granted assumptions destabilizes them (pp. 18-25).

### Internal Tensions

#### Tension 1: The pre-speech window shows the same BR association as the speech day, so the event-window evidence fails the straight-line test and contradicts the ITCV conclusion
- **Result A:** Speech-day effect, ln(VIX t0 / VIX t-1) on BR: 0.036 (0.018), Table 2 Model 2, p. 56. The design logic is that "the speech is not made public until the date and time denoted on the transcript" (p. 25), so the effect should begin at t0.
- **Implies:** BR should not predict the VIX change in the two-day window that ends at t-1. Separately, the ITCV conclusion that "my primary results are not likely driven by a correlated omitted variable" (p. 24) implies that no factor tied to BR moves the VIX independently of the speech.
- **Result B:** Pre-speech window: "β = .041, σ² = 0.017, p = .017, adjusted R-squared = 0.083" (p. 25).
- **Shows:** Verified fact: the per-day BR slope is 0.041 the day before and 0.036 on the speech day (t ≈ 2.4 and 2.0). Inference: in cumulative terms the VIX rises along a straight line with slope about 0.04 per unit of BR per day from t-2 through t0, with no break at the speech. At one SD of BR (0.22, Table 1), that is about 0.9 percent before the speech and 0.8 percent on the speech day. A single line fits the pre and post points, so the speech-day estimate cannot be told apart from a trend already under way.
- **Tension:** The paper's own causal channel cannot produce movement before the speech. Whatever produces the pre-window association is, by the paper's own account, something other than the speech that is correlated with BR, which is the omitted factor the ITCV argument (p. 24) and the "acute vs. systemic" defenses (pp. 23-24) say is unlikely. The robustness section uses the placebo as support for the speech channel while its statistics point the other way. The Discussion (pp. 25-26) does not mention it.
- **Steelman:** The printed p or SE may be a typo, and the author meant a null. The control for "previous average daily changes in the VIX (i.e., using 1, 10, or 30 days prior)" (p. 24) may also be read as addressing a pre-trend. It does not settle the issue: the 1-day lag is essentially the placebo outcome, no coefficients are shown, and conditioning on yesterday's change does not remove a slow common factor's effect on today's change.
- **Possible explanations:** (a) Reverse causality or a common upstream shock: contestation of the framework raises uncertainty and draws backing-heavy speeches (Stage 3 alternative 1; the paper's own p. 34 reading). (b) Anticipation through advance texts or schedules. (c) Date misassignment for speeches given after the close or on non-trading days (dgp_map.md, Step 3). (d) A typo.
- **Severity:** Undermines the main claim.
- **Confidence:** High (both coefficients are printed; the straight-line reading is arithmetic on them).
- **Tag:** paper.

#### Tension 2: The three crisis-period estimates do not fit together, and the split-sample point estimate shows no attenuation
- **Result A:** BR x crisis = -0.051 (0.038), p = .088, with year FE (p. 20).
- **Implies:** Crisis speeches (2008-2012) carry a BR slope about 0.05 lower than non-crisis speeches. Fig. 2 bars for 2008-2012 sum to 102 of 339 speeches (about 30 percent; p. 50). Inference: if the full-sample 0.036 is roughly a weighted average, the non-crisis slope is about 0.036 + 0.051 x 0.30 = 0.051 and the crisis slope is near 0.000.
- **Result B:** Crisis-only split, Model 2: β = 0.035 (0.036), p = .335 (p. 20). Full sample: 0.036 (Table 2 Model 2).
- **Shows:** The crisis-only point estimate (0.035) equals the full-sample estimate (0.036). Additivity fails: a crisis slope of 0.035 and a full-sample slope of 0.036 imply a non-crisis slope near 0.036, not one 0.05 above the crisis slope.
- **Tension:** The paper reads both results as attenuation: "drop below significance" (p. 20) and, in the Discussion, "reaffirming them no longer creates uncertainty to the same extent" (p. 26). The split sample shows a loss of precision with an unchanged point estimate (Stage 1 directional claim 3 noted the same fact). The interaction and the split cannot both describe the same crisis slope unless the controls' coefficients differ sharply between periods, which the paper does not report. The interaction itself is p = .088 one-tailed (about .18 two-tailed; Stage 1 Issue 13).
- **Steelman:** The split lets every control coefficient vary by period, so it is not the same model as the interaction. That explains a difference but leaves the paper without a coherent estimate of the crisis slope.
- **Possible explanations:** Different specifications; control coefficients that shift in the crisis; a weak interaction that does not survive a consistent specification.
- **Severity:** Weakens a claim (the boundary-condition claim restated as "additional validation" on p. 26).
- **Confidence:** High for the printed numbers; Medium for the implied crisis slope, which uses a weighted-average approximation and Fig. 2 bar readings.
- **Tag:** paper.

#### Tension 3: The 48-speech "reversal" is already implied by the H2 and H3 moderators, so it cannot show anything about the crisis
- **Result A:** Model 5 (Table 2): BR 0.041, BR x tone -0.049, BR x fear 26.293. Fig. 4 slopes reproduce 0.034 ± 0.056 x 1.01 (numeric_fidelity, Figure slopes table), so BR is the effect at mean tone and the moderators are centered. Stage 1 infers SD(fear) ≈ 0.0015 from Fig. 5 because Table 1 prints 0.00.
- **Implies:** Among speeches with above-mean tone and below-mean fear, the full-sample model already predicts a negative BR slope. Inference with normal truncated means (0.80 SD above and below): 0.041 - 0.049 x 0.81 + 26.293 x (-0.0012) ≈ -0.03. No crisis condition is needed.
- **Result B:** Crisis speeches with high tone and low fear (N = 48): β = -0.155 (0.063), p = .022 (p. 21; Fig. 6, p. 52).
- **Shows:** The sign is what H2 and H3 predict in that cell anywhere in the sample. The size is about five times the model-implied value, from 48 speeches estimated with a specification that has about 58 parameters in the full sample (Stage 1 Issue 12).
- **Tension:** The paper presents the reversal as evidence that crisis-weakened taken-for-grantedness plus an optimistic climate makes reaffirmation reduce uncertainty (p. 21) and as "additional validation" (p. 26). Without the same cell outside the crisis, the result cannot separate a crisis effect from the moderators already estimated. The subsample is selected on the two moderators.
- **Steelman:** The author frames the analysis as exploratory ("tentatively", p. 19; "preliminary evidence", p. 20). The Discussion drops that framing.
- **Possible explanations:** Selection on moderators; a small-sample estimate with few residual df; a real crisis difference that the design cannot isolate.
- **Severity:** Weakens a claim.
- **Confidence:** Medium (the implied -0.03 rests on the Fig. 5-derived SD of fear and on centered moderators).
- **Tag:** paper + judgment.

#### Tension 4: The business-media fear measure moves against the macro conditions the theory calls a pessimistic climate, which ties H3 to the crisis result
- **Result A:** H3 treats media fear as a "pessimistic emotional climate" (p. 12) and the Discussion advises "postponing the discussion until a prevailing pessimistic climate passes" (p. 30).
- **Implies:** Fear should rise with bad macro conditions and with market-implied volatility.
- **Result B:** Table 1 (p. 54): fear correlates -0.43 with the unemployment rate, +0.30 with inflation, +0.20 with contractionary policy, and only +0.18 with existing market uncertainty (30-day average VIX). BR correlates -0.23 with fear and +0.26 with unemployment. The paper's own quote places unemployment at "10 percent in the fall of 2009" (p. 14), inside the crisis window.
- **Shows:** Verified facts: the fear index is lower when unemployment is high and is weakly related to the VIX level. Inference: the fear index runs low in the high-unemployment crisis years, where high-BR speeches also cluster. A larger BR slope at high fear (H3) and a smaller BR slope in the crisis (p. 20) may then be one pattern counted twice.
- **Tension:** argument_map.md argues that H3 predicts amplification in the crisis while the paper finds attenuation. Table 1 suggests the opposite premise: fear was not high when unemployment was. Either way the paper presents H3 and the crisis attenuation as separate confirmations without showing they are distinct. Because year fixed effects absorb only fear's level, the BR x fear interaction still uses between-year variation in fear.
- **Steelman:** MarketPsych fear is a share of fear words in business news, which can be high in tightening cycles; the theory needs only that it measures media emotion at speech time.
- **Possible explanations:** Era differences in the fear series (timeline.md notes unverified source-composition changes); fear measured through t+1 (dgp_map.md); H3 as a proxy for macro era.
- **Severity:** Weakens a claim (H3).
- **Confidence:** Medium (pooled correlations; the series by year is not reported).
- **Tag:** paper + judgment.

#### Tension 5: The paper calls nearby speeches dissimilar in BR, but the reported gap is below what random pairs would show
- **Result A:** "Examining speeches given within three days of each other (N = 40 pairs) reveals an average difference in BR of 0.21 (or roughly one standard deviation), which is inconsistent with what one would expect if systemic market factors were driving the Fed to talk about the backing" (pp. 23-24).
- **Implies:** For the test to show dissimilarity, nearby pairs should differ at least as much as randomly drawn pairs.
- **Result B:** Table 1: BR SD = 0.22.
- **Shows:** Inference: for two independent draws from a normal distribution with SD 0.22, the expected absolute difference is 2 x 0.22 / √π ≈ 0.25. The observed 0.21 is below that, so nearby speeches look, if anything, slightly more alike than random pairs.
- **Tension:** The test has no benchmark, and the obvious one does not support the reading given.
- **Steelman:** BR is bounded at 0 and likely skewed (mean 0.23, SD 0.22), so the normal benchmark may overstate the random-pair gap.
- **Possible explanations:** Skewed BR distribution; the benchmark simply was not computed.
- **Severity:** Minor (one of three endogeneity defenses).
- **Confidence:** Low to Medium (depends on the BR distribution, which is not reported).
- **Tag:** paper + judgment.

#### Tension 6: The main estimate rests on conditioning; the bivariate association falls below the paper's own significance threshold
- **Result A:** Table 1: r(BR, market uncertainty) = 0.09. The Table 1 note gives 0.11 as the two-tailed .05 threshold.
- **Implies:** The bivariate slope is 0.09 x 0.06 / 0.22 ≈ 0.025.
- **Result B:** Table 2 Model 2: 0.036, about 45 percent larger (standardized ≈ 0.036 x 0.22 / 0.06 = 0.13).
- **Shows:** Controls act as suppressors. Candidates from Table 1: dissent president (r with BR +0.16, with the outcome -0.17; Table 2 coefficient -0.020***) and contractionary policy (-0.17, +0.14). No specification between BR alone and the full model is shown.
- **Tension:** Suppression is not an error, but H1's significance (t ≈ 2.0) depends on which controls are in the model, and the paper presents the result as a "simple finding" with "robustness" (p. 25).
- **Steelman:** Prior FOMC dissent and policy direction are pre-treatment and belong in the model.
- **Severity:** Minor.
- **Confidence:** Medium (bivariate algebra on rounded Table 1 values).
- **Tag:** paper.

#### Tension 7: The Discussion reads BR as an indicator of low legitimacy, which reverses the causal direction the results claim
- **Result A:** Results and Discussion: BR "causes uncertainty" (p. 25); "high levels of backing disrupts people's taken-for-grantedness" (p. 33).
- **Result B:** Same section: "a high backing ratio reflects low levels of cognitive legitimacy because it indicates that people feel the need to discuss, or request others to discuss, these assumptions directly" (p. 34).
- **Tension:** If BR reflects legitimacy that is already low, then speeches with high BR arrive when the framework is already contested, which is the reverse-causality alternative that Tension 1's pre-window association fits. The paper offers both readings without reconciling them.
- **Steelman:** The p. 34 passage proposes BR as a measure for future work, not as an account of this sample.
- **Severity:** Weakens a claim.
- **Confidence:** High (both quotes are verbatim).
- **Tag:** paper.

### Consistency Checks

| Check | Result | Pass/Fail | Notes |
|-------|--------|-----------|-------|
| Sign consistency | BR positive in Models 2-5 (0.036, 0.034, 0.045, 0.041); BR x tone negative and BR x fear positive in both models that include them | Pass | The fear main-effect sign flip in Model 4 (0.005**) is Stage 1 Issue 3; it is not re-flagged. |
| Heterogeneity additivity | Crisis split 0.035 vs. full 0.036 vs. interaction -0.051 implying a crisis slope near 0 | Fail | Tension 2. Difference-in-significance between split samples is left to the nonlinear pack. |
| Monotonicity / dose-response | Only linear BR is estimated; Figs. 3-6 plot predictions to BR = 1, about 3.5 SD above the mean (0.23) | Not tested | The BR distribution and the share of speeches with BR = 0 are not reported. |
| Event study dynamics vs. mechanism | Pre-window 0.041 vs. speech day 0.036; one straight line fits both | Fail | Tension 1 (straight-line test). The theory's destabilization is lasting (pp. 8-9), but no post-t0 window is estimated. |
| Robustness check fidelity | GEE, backing-feature controls, alternative windows, lagged VIX changes, and the audience check are reported without coefficients (pp. 23-25) | Fail | The lagged 1-day VIX control is essentially the placebo outcome and does not address a slow common factor; "controlling for the local audience does not change my results" (p. 23) is ambiguous because all models include audience FE (Table 2 note). The 40-pair test lacks a benchmark (Tension 5). |
| Figure-table coherence | Fig. 3 slope ≈ 0.037 vs. 0.036; Fig. 3 at mean BR ≈ -0.0055 vs. DV mean -0.0051; Fig. 4 gap at BR = 0 ≈ 0.013 vs. 2 x 1.01 x 0.007 = 0.014; Fig. 5 slopes symmetric around 0.045; Fig. 7 has 57 covariate bars, equal to Model 2 df (58) minus BR | Pass, except ITCV | ITCV 0.014 vs. 0.030 is Stage 1 Issue 5. |
| Results vs. Discussion fidelity | See notes below | Fail | Overclaiming, scope creep, omitted caveats. |
| R-squared increments vs. t | Model 1 to 2: ΔR² 0.008 implies t ≈ 1.8 (range 1.75-1.87 under rounding) vs. printed 0.036/0.018 = 2.0 | Pass | Gap is within what robust vs. classical SEs can produce. Model 3: ΔR² 0.022 implies t ≈ 3.0 vs. 2.8. |
| IV consistency | n/a | n/a | No IV. |

Results vs. Discussion notes (all `paper`):
- **Overclaiming, central result.** "I proved that reaffirming the assumptions underlying the monetary policy framework causes uncertainty" and "Despite the robustness of this simple finding" (p. 25). The main estimate has t ≈ 2.0 (one-tailed p ≈ .023; Stage 1 Issue 2), the pre-window association is the same size (Tension 1), and the robustness checks have no reported estimates. Severity: Weakens a claim.
- **Scope creep.** "uncertainty in financial markets around the world" (p. 25). The outcome is the VIX on S&P 500 options (p. 13). Later passages extend the finding to "markets, social institutions, and broader financial system" (p. 29) and to teachers and airline pilots (pp. 26-27). Severity: Minor.
- **Exploratory result restated as validation.** The crisis analysis is "tentatively extend[ed]" (p. 19) and "preliminary evidence" (p. 20) in Results, but "additional validation of this story" (p. 26) in the Discussion. Tensions 2-3 show the evidence does not carry that weight. Severity: Weakens a claim.
- **A control coefficient treated as a finding.** "I nevertheless demonstrate strong support for the signaling perspective ... Table 2 indicates that longer speeches significantly reduce market uncertainty" (p. 28). Word count is a control; its coefficient and SE print as -0.000 (0.000) in every model (Table 2), so its size cannot be read; word count correlates 0.23 with BR and -0.41 with positive tone (Table 1). The causal reading of a control is not identified by the design. Severity: Minor.
- **Missing caveats.** The Discussion does not mention the pre-window result (p. 25), the crisis-only point estimate equal to the full-sample one (p. 20), or that the robustness checks are unreported.
- **Inconsistent practical guidance.** p. 30 advises leaders to avoid creating uncertainty by "encasing these statements within more positive language or postponing the discussion"; p. 32 suggests leaders "should discuss these taken-for-granted assumptions more regularly ... While doing so would create uncertainty, this is precisely the point." Severity: Minor.
- **Holds as stated.** "a context created by high (low) levels of positivity shape people's interpretations in a similar way as a context created by low (high) levels of fear" (p. 29) matches the amplification side (Fig. 4 low tone and Fig. 5 high fear both end near 0.09 at BR = 1) but only partly the suppression side (high tone reverses the slope to about -0.023; low fear only flattens it). Minor; noted, not flagged.

### Conspicuous Absences

| Missing Element | Why Expected | How Suspicious | Informed By |
|-----------------|-------------|----------------|-------------|
| Day-by-day event profile (t-5 through t+5) of the BR slope, and Model 2 with the pre-speech VIX path (t-5 to t-1) as a control | The only discriminating test reported (p. 25) shows a pre-speech association; a full profile shows whether a break occurs at t0 | Highly suspicious | Stage 3 alternative 1 (reverse causality / pre-existing contestation); theory_devil_report Challenge 1 |
| Evidence that press or public questioning of the framework before drafting predicts BR | The paper's p. 34 reading implies it; the drafting-lag defense (pp. 21-22) addresses daily shocks, not slow contestation | Moderately suspicious | Stage 3 alternative 1 |
| BR split into mandate-restatement vs. tool-boundary or change-discussing paragraphs, with both coefficients reported | The "change discussed" control is reported only as "consistent results" (p. 25); the policy-news alternative predicts the effect sits in tool paragraphs | Highly suspicious | Stage 3 alternative 2 (policy news); mechanism_discrimination "Not addressed" |
| Model 2 estimated on 1998-2007 alone | Where the framework was most plausibly taken for granted (p. 26), the theory predicts its largest effect; tools and goals changed in 2008-2014 (timeline.md) | Moderately suspicious | Stage 3 alternative 2; timeline.md |
| Share or count of outlook and data paragraphs entered alongside BR | BR is a share, so high BR displaces outlook content; the paper equates low BR with outlook speeches (p. 22) | Moderately suspicious | Stage 3 alternative 3 (crowded-out outlook) |
| Days-to-next-FOMC controls, fed funds futures rate-path dispersion on speech days, and BR coded for governor speeches | The policy-rule uncertainty account predicts effects near decisions and in rate-path dispersion; governor speeches enter only as a dummy (p. 16) | Moderately suspicious | Stage 3 alternative 4 (policy-rule uncertainty) |
| Any measure of the proposed mediator (dispersion of forecasts or judgments) | The mechanism is "increasingly diverging directions" (p. 10), which the VIX does not measure directly | Moderately suspicious | argument_map.md; mechanism_discrimination item 4 |
| VIX change over t-1 to t+1, t+3, t+5 | Destabilizing an institution implies persistence; news arrival implies partial reversal | Moderately suspicious | argument_map.md (null model); mechanism_discrimination item 3 |
| BR x existing uncertainty in Models 4-5, and fear rebuilt over days ending at t-1 | Fear is averaged over t-1 to t+1 (p. 16) and correlates with existing VIX (0.18); the 2- and 4-day windows (p. 25) do not say whether they exclude t+1 | Moderately suspicious | argument_map.md alternative 4; dgp_map.md |
| High-tone, low-fear speeches outside the crisis, estimated the same way as the 48-speech subsample | Needed to separate a crisis effect from H2/H3 (Tension 3) | Moderately suspicious | Internal (Tension 3) |
| Fear series by year, and BR x fear estimated within crisis and non-crisis periods | Needed to tell H3 from the crisis attenuation (Tension 4) | Mildly suspicious | Internal (Tension 4); timeline.md (unverified MarketPsych source changes) |
| A coefficient table for every robustness check (GEE, backing features, alternative windows, lagged VIX, audience) | All are reported in prose only (pp. 23-25); the paper has no appendix | Moderately suspicious | Methodological standard |
| Results with the seven trimmed speeches retained, and the model that defined the residuals | Trimming on DV residuals selects on the outcome (p. 12; dgp_map.md) | Moderately suspicious | dgp_map.md |
| Chair fixed effects | Three Chairs, transition years mixed; year FE only (Table 2 note) | Mildly suspicious | timeline.md; theory_devil_report |
| A model build-up from BR alone to the full model | The bivariate r (0.09) is below the Table 1 threshold; the estimate depends on suppressors (Tension 6) | Mildly suspicious | Internal (Tension 6) |
| Benchmark for the 40-pair test (random-pair or permutation distribution of BR differences) | Without it the test cannot show dissimilarity (Tension 5) | Mildly suspicious | Internal (Tension 5) |
| Speech time of day, with after-close speeches assigned to the next trading day | A misdated reaction can fall in the wrong window; one in-sample high-BR speech was given after the close (dgp_map.md) | Moderately suspicious | dgp_map.md; timeline.md |

### Summary
The paper's tables cohere with its figures, and the main BR sign is stable across models. The evidence does not tell one story about timing, though. BR predicts the VIX change the day before the speech as strongly as on the speech day (p. 25), so the speech-day estimate fails the straight-line test and contradicts the ITCV conclusion. The crisis analyses do not fit together, and the 48-speech reversal is already implied by H2 and H3. The Discussion restates these results as proof and validation without the caveats the Results section contains.
