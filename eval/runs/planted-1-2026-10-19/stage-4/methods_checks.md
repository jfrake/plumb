## Methods Checks Report

Agent: Methods Checks Agent. Search cap 2016-06-01 respected; the one external page used is the Federal Reserve's 2013 speech list (speeches dated within the sample period).

Scope notes. Packs running: archival, computational, nonlinear, inference, framing (run.json). Per the inference pack note, this report does not cover clustering or inference level (CHECK 5 except the Cragg-Donald note), cluster counts, the wrong-cluster-level pattern, serial correlation or cross-sectional dependence, multiple testing (CHECK 7), interval readings of null findings, absence of evidence vs. evidence of absence, or whether the paper states effect sizes. Per the nonlinear pack split, the size and reading of BR x tone and BR x fear and the crisis split-sample comparison as a moderation reading are left to that pack. The fingerprint's `Designs:` line lists Selection (ITCV, secondary), so covariates in a score model (SO13), sample restrictions on a variable the treatment could affect (SO14: the outlier trimming on studentized residuals, p. 12, and the "below-mean fear" crisis subsample, p. 21), and omitted-variable sensitivity (SO12: ITCV) are left to the design-checks agent. Stage 1 issues (placebo p = .017, N 337 vs 339, star errors, ITCV 0.014 vs 0.030, effect-size arithmetic, Model 5 adjusted R-squared) are not repeated.

### Checks Performed

| Check | Applicable? | Result | Severity |
|-------|-------------|--------|----------|
| Industry-year FE vs. industry-level argument | No | N/A (no industry FE; single-institution time series) | N/A |
| Lags as a fix for endogeneity | Yes | Pass (the paper argues pre-determination from drafting lead times, pp. 21-22, not from lagging BR) | N/A |
| Measurement tautology | Yes | Concern (fear moderator and control partly measured on and after the outcome day) | Moderate |
| Variation audit | Yes | Concern (unlisted regressors in df imply weekend speech-days; residual BR variation unreported; 48-speech subsample cannot carry the stated specification) | Moderate |
| Bad controls | Yes | Concern (business media fear t0 and t+1 in the H1 model; topic FE co-determined with BR; robustness controls that are features of the treatment) | Moderate |
| Collider/selection | Yes | Outcome-based trimming and fear-based subsample left to design-checks (SO14) | N/A here |
| Clustering/inference | Yes | Left to inference pack | N/A here |
| Power/precision | Yes | Concern (main estimate below the design's minimum detectable effect; positive interval spans trivial to sizable) | Moderate |
| Multiple testing | Yes | Left to inference pack | N/A here |
| External validity | Yes | Concern (US S&P 500 implied volatility generalized to "financial markets around the world" and to institutions generally) | Low |
| Method-specific (event study; text-as-data) | Yes | Concern (single pre-window; no event-time path; attenuation from coded BR) | Moderate |
| Economic significance (plausibility vs. benchmarks) | Yes | Pass for H1 main effect | N/A |

### Detailed Findings

#### Variation audit: the regression has six regressors the paper does not list, and the arithmetic points to weekend speech-days with no VIX close on t0
- **Evidence:** Table 2 reports df = 57 for Model 1 (p. 57), and Stage 1 confirms df is the regressor count excluding the constant (adjusted R-squared reproduces with N - df - 1 for Models 1-4). The listed regressors in Model 1 are 23 controls (Table 2 rows), plus 16 year dummies (1998-2014), 8 topic dummies (nine topics, p. 17) and 4 audience dummies (five audiences, p. 17): 51 in all. That leaves 6. Weekday dummies (p. 17) are the only stated candidate. Five trading days give 4 dummies, which leaves 2 unexplained. Six dummies requires seven day-of-week categories. The Federal Reserve's 2013 list (https://www.federalreserve.gov/newsevents/speech/2013-speeches.htm) shows 17 Bernanke items, which matches the 2013 bar in Figure 2 (about 17, p. 50). Two fall on weekends: "Economic Prospects for the Long Run," 5/18/2013 (Saturday), and "The Ten Suggestions," 6/2/2013 (Sunday). The same list has two items on 12/16/2013 ("Opening Remarks" and "Concluding Remarks"), which would share one DV value and every day-level control.
- **Concern:** The DV is ln(VIX_t / VIX_t-1) on the speech day (pp. 13, 18). A Saturday or Sunday has no VIX close. Whatever date the author assigned, the window cannot be "the day of the speech" for these rows. If the weekend speech is mapped to the prior Friday, the DV is a pre-speech change; if to Monday, the window spans three calendar days of other news. Commencement addresses and special-occasion remarks are two of the nine topics (p. 17) and plausibly go to layperson audiences more often (the paper reports no topic-by-audience breakdown), the audience with the lowest BR (r = -0.34, p. 22). If these are the misdated rows, which the paper's unstated delivery timing does not let us confirm, the misdated rows may be concentrated at low BR. Same-day duplicates add rows with identical outcomes. The Stage 2 DGP map raised after-close timing and noted that weekend assignment is unstated; the df arithmetic and the 2013 list show the problem is present in the estimation sample, not hypothetical.
- **Threshold:** Event-window studies of Fed speeches date speeches given outside trading hours to the next business day (Kohn and Sack 2003, FEDS 2003-55, cited in stage-2/setting.md).
- **Suggestion:** List every regressor in Table 2 or its note, including weekday categories. Report how many speeches fall on weekends, holidays, or after 4 p.m. ET, and how each was mapped to a trading day. Re-estimate Model 2 (a) dropping those speeches and (b) assigning them to the next trading day. Collapse or drop same-day duplicate speeches, or show that results hold either way.
- **Severity:** Moderate
- **Confidence:** Medium. The df arithmetic is exact, but the six extra terms could in principle be other unlisted controls; the weekend speeches in the 2013 list are verified, though the paper does not confirm they are in its sample.

#### Variation audit: residual variation in BR after the fixed effects and text controls is not reported, and topic is coded from the same text as BR
- **Evidence:** BR varies at the speech level, so year, topic, and audience fixed effects do not absorb it, and the coefficient is identified. But the model spends 58 regressors on 339 speeches (Table 2, Model 2). BR correlates 0.35 with the linear audience variable (p. 22), 0.42 with speech complexity, 0.37 with speech power, 0.27 with speech negative tone, 0.26 with unemployment, and 0.23 with word count (Table 1, column 2). Topic is coded inductively from speech content (p. 17), and categories such as "central banking" and "economic history" describe speeches about the framework itself, which by the coding rule (p. 14) are high-BR speeches. The estimator sentence on p. 18 ("OLS regression with year-fixed effects") names only year fixed effects; topic and audience enter as dummy-variable controls described on p. 17 and as fixed effects in the Table 2 note (p. 57).
- **Concern:** Topic is chosen together with BR when the speech is written, so topic fixed effects remove the between-topic variation that the theory is about (speeches devoted to the framework vs. speeches on the outlook). H1 is then identified only from within-topic BR differences after partialling out 57 other terms, and the paper never shows how much BR variation is left. The p. 23 statement that "controlling for the local audience does not change my results" does not say which model was compared, since every Table 2 model already includes audience fixed effects.
- **Threshold:** Report the within-R-squared of BR on the full fixed-effect and control set, or the SD of residualized BR (standard variation-audit practice; Angrist and Pischke 2009, ch. 3).
- **Suggestion:** Report the R-squared from regressing BR on year, topic, audience, weekday, and the controls, and the SD of residualized BR. Report Model 2 with year fixed effects only, then adding topic, then adding audience, so the reader can see where the BR coefficient comes from. Report mean BR by topic.
- **Severity:** Moderate
- **Confidence:** Medium

#### Variation audit: the 48-speech crisis subsample cannot have been estimated with the Model 2 specification, and the reported p implies about 20 residual degrees of freedom
- **Evidence:** The paper says it "ran Model 2 again" on 48 crisis speeches with above-mean tone and below-mean fear and reports beta = -0.155, SE ("sigma^2") 0.063, p = .022, adjusted R-squared 0.363 (p. 21). Within 2008-2012, Model 2 still carries 23 listed controls, BR, 4 year dummies, up to 8 topic and 4 audience dummies, and 4 to 6 weekday dummies: roughly 44 to 46 terms plus a constant for 48 observations, which leaves one to three residual df before any collinear drops. With |t| = 0.155/0.063 = 2.46, a two-tailed p of .022 corresponds to about 22 residual df (two-tailed p is .133 at 2 df, .057 at 5, .034 at 10, .023 at 20, .022 at 22; t-distribution, computed here). Allowing for rounding of beta and SE (|t| from 2.43 to 2.49), the implied residual df ranges from about 18 to 30, so the estimated model had roughly 17 to 29 regressors.
- **Concern:** Either some 15 to 25 terms dropped out (constant dummies such as contractionary policy in 2008-2012 will drop, but not that many), or the model was not Model 2. In either case, the specification behind Figure 6 and the "main effect entirely reversed" claim, which the Discussion calls "additional validation of this story" (p. 26), is undisclosed, and with so few observations per parameter the estimate rests on a near-saturated fit. Stage 1 (Issue 12) flagged the parameter count as questionable; the df implied by the printed p is the added evidence. The sample restriction on below-mean fear is a separate problem left to design-checks (SO14).
- **Threshold:** Report the regressors actually estimated and the residual df for every subsample model; a model with fewer than about 10 to 20 observations per parameter is overfit for inference (Harrell 2001, Regression Modeling Strategies).
- **Suggestion:** Report a table for the crisis analyses listing the regressors that entered, residual df, and N for the full crisis sample (not given) and the 48-speech subsample. Re-estimate with a parsimonious, pre-stated control set, and show the BR x crisis x tone x fear specification in the full sample instead of a split on two post-hoc cut points.
- **Severity:** Moderate
- **Confidence:** Medium (the df inference depends on rounding of the printed beta and SE and on which terms Stata dropped)

#### Bad controls: business media fear in the H1 model is measured partly on the outcome day and the day after
- **Evidence:** Fear is the average of the MarketPsych daily index over t-1 to t+1 (p. 16) and enters as a main-effect control in every model, including Model 2, which carries H1 (Table 2, p. 56). The DV window is t-1 to t0 (p. 13). Two of the three days in the fear average are the DV day and the day after it. Fear correlates 0.10 with the DV and -0.23 with BR (Table 1).
- **Concern:** Media fear on t0 and t+1 is partly a report of the same VIX move the DV measures, and partly a reaction to the speech. In the H1 model it is a post-treatment control. Its coefficient is imprecise (-1.176, SE 2.925, Model 2), so the bias to the BR main effect is likely small, but the paper does not show H1 without it. The H3 problem (fear as a post-outcome moderator) is raised in stage-4/mechanism_discrimination_issues.md (MD-4) and in the Stage 2 DGP map and is not repeated here. The robustness check with "a two- and four-day window" (p. 25) does not say whether those windows exclude t0 and t+1.
- **Threshold:** Controls must be determined before treatment (Angrist and Pischke 2009, sec. 3.2.3).
- **Suggestion:** Rebuild fear over a window ending at t-1 (for example t-3 to t-1), report Model 2 with that version and without fear, and state the day spans of the 2- and 4-day windows.
- **Severity:** Low for H1 (Moderate for H3, carried in MD-4)
- **Confidence:** High on the timing, which is stated in the paper; Low on the size of any bias to H1

#### Bad controls: robustness controls that are features of the treatment itself
- **Evidence:** The robustness check codes each backing paragraph for whether a change to the backing was discussed, future orientation, and position in the first five or ten paragraphs, and controls for these (p. 25). No coefficients are reported, and the aggregation to the speech level is not stated (construction ledger).
- **Concern:** These are attributes of the backing paragraphs, so controlling for them conditions on part of the treatment. The check cannot separate restatement from discussion of change, which is what the policy-news alternative (stage-3 alternative 2; MD-1) needs. "Produced consistent results" does not show whether restatement-only backing carries the effect.
- **Threshold:** A treatment component used to test a mechanism should be entered as a separate treatment share, not as a control (Angrist and Pischke 2009, sec. 3.2.3).
- **Suggestion:** Split BR into the share of restatement-only backing paragraphs and the share of change-discussing or future-oriented backing paragraphs, and report both coefficients in a table.
- **Severity:** Low (the substantive request is already in MD-1; this item records that the p. 25 check is mis-specified for its purpose)
- **Confidence:** Medium

#### Power and precision: the H1 estimate is smaller than the design's minimum detectable effect
- **Evidence:** Model 2 BR = 0.036, SE 0.018 (Table 2, p. 56). At 80 percent power, the minimum detectable effect is (1.645 + 0.842) x 0.018 = 0.045 for the paper's one-tailed 5 percent test, and (1.96 + 0.842) x 0.018 = 0.050 two-tailed. The two-sided 95 percent interval for the estimate is about 0.001 to 0.071. Scaled by the Table 1 SD of BR (0.22), that is a 0.02 to 1.6 percent change in the VIX, or 0.004 to 0.26 SD of the DV (SD 0.06).
- **Concern:** The point estimate is about 70 to 80 percent of the MDE. A significant estimate from a design with power below 50 percent for an effect of its own size tends to overstate the true effect (Type M error; Gelman and Carlin 2014, Perspectives on Psychological Science). The interval runs from a negligible effect to one about twice the stated "1.0 percent," so the data do not pin the effect down. The Stage 2 setting brief notes that Kohn and Sack (2003) found no significant effects of Greenspan speeches on financial variables, which sets a low prior for any speech-day effect.
- **Threshold:** Report the MDE or a design analysis for the main estimate (Gelman and Carlin 2014).
- **Suggestion:** Report the 95 percent interval for BR in Model 2 and the effect at its bounds in VIX percent; report a design analysis (power and expected exaggeration ratio) for plausible true effects; present the effect-size discussion on p. 18 with that range.
- **Severity:** Moderate
- **Confidence:** High (computed from the printed coefficient and SE)

#### Method-specific (event study): a single pre-window and no event-time path
- **Evidence:** The paper calls the design an "event study analysis" (p. 18) but reports only the speech-day window (t-1 to t0) and one "two-day event window before the day of the speech" (p. 25). The placebo window's exact days are not given. If it is ln(VIX_t-1 / VIX_t-2), it shares VIX_t-1 with the DV, with opposite sign.
- **Concern:** Stage 1 flagged that the placebo is significant and as large as the main effect. The methods point is that one pre-window cannot show whether the BR association starts on the speech day, builds over the days before (as stage-3 alternative 1 predicts), or reflects mean reversion around a shared t-1 close. The paper also gives no post-window (t0 to t+1, t+1 to t+3), so after-close speeches and the persistence of any effect go unexamined.
- **Threshold:** Report the full event-time path and read the pattern of pre-event coefficients, not one test (MacKinlay 1997, Journal of Economic Literature).
- **Suggestion:** Estimate Model 2 separately for each daily log VIX change from t-5 to t+5 and plot the BR coefficients with intervals. Report the speech-day coefficient net of the pre-window coefficient. State the placebo window's days.
- **Severity:** Moderate
- **Confidence:** High on what is missing; the substantive placebo result is Stage 1's

#### Method-specific (text-as-data): attenuation from coded BR, compounded in the interaction terms
- **Evidence:** BR is hand-coded at the paragraph level, with Krippendorff's alpha 0.88 on the first 60 speeches and .84 on the last 10, and no reliability for the middle 267 (p. 13). Positive tone is an LIWC dictionary share; the setting brief documents that general dictionaries misclassify financial text (Loughran and McDonald 2011).
- **Concern:** Coding error in BR attenuates the H1 slope; this works against the paper's main finding, so it is not a threat to the sign. For H2, error in both BR and LIWC tone attenuates the product term further, which also works against finding H2. The concern is narrower: reliability is unreported for 79 percent of speeches, so the size of attenuation is unknown, and paragraph-level alpha does not give speech-level BR reliability. Coder blinding to market outcomes is not stated (construction ledger), and blinding failure, unlike random error, could bias toward the hypothesis.
- **Threshold:** Report reliability on a random sample spanning the full period and at the level of the analysis variable (Krippendorff 2003, cited by the paper).
- **Suggestion:** Report speech-level BR reliability (ICC between coders' BR values) on a random sample drawn across 1998-2014; state whether coders saw market data; report how disagreements were resolved.
- **Severity:** Low
- **Confidence:** Medium

#### External validity: the outcome is US S&P 500 implied volatility, but the claims extend further
- **Evidence:** The Discussion states "I proved that reaffirming the assumptions underlying the monetary policy framework causes uncertainty in financial markets around the world" (p. 25). The only outcome is the CBOE VIX, which is computed from S&P 500 options (p. 13). The sample is three Chairs of one central bank, and Yellen contributes 12 speeches (p. 12).
- **Concern:** No non-US market or other asset class is measured, so "around the world" has no support in the data. Generalizing from one institution and essentially two Chairs to institutions and leaders generally (pp. 26, 35) needs a statement of scope conditions.
- **Threshold:** Claims should match the sampled population and outcome.
- **Suggestion:** Restrict the claim to US equity-option implied volatility, or add outcomes such as VSTOXX or Treasury implied volatility (MOVE) to support a broader claim. Report results by Chair.
- **Severity:** Low
- **Confidence:** High

#### Economic significance (plausibility vs. benchmarks): pass for the H1 main effect
- A 0.22 change in BR implies about 0.8 percent of the VIX, about 0.13 SD of the daily DV. That is within the range of Fed-communication effects on implied volatility the paper cites (Nikkinen and Sahlstrom 2004; Chen and Clements 2007) and is not implausibly large. The low prior from Kohn and Sack (2003) is noted under power. Interaction sizes are left to the nonlinear pack.

### Items checked and passed or not applicable
- CHECK 0a: no industry-year fixed effects; N/A.
- CHECK 0b: identification relies on drafting lead times and interviews (pp. 21-22), not on lagging BR; pass. The interviews are not data the reader can check, but that is a design question for other agents.
- CHECK 1 (tautology for BR): BR is coded from text and the DV is a market price; no definitional link. The fear timing issue is under bad controls.
- CHECK 3, remaining controls: existing uncertainty (30-day prior), unemployment and inflation (prior month), FOMC policy dummies and dissents (prior meeting), scheduled CPI, PPI, and unemployment releases, governor speeches, testimony, location, local audience, and weekday are pre-determined relative to the speech-day VIX change. Speech-text controls (complexity, power, negative tone, word count) correlate 0.23 to 0.42 with BR, but their coefficients are small and imprecise in every model, so any mediator bias to BR is likely small; not raised.
- CHECK 6, separation and events per variable: no logit or probit model; N/A.
- CHECK 9, AKM, LPM, bunching, DML, conjoint, mediation, multilevel: N/A. GEE by Chair (pp. 24-25) is an inference question left to the inference pack.
- Crisis dummy with year fixed effects (p. 20): the 2008-2012 main effect is a linear combination of year dummies and is not separately identified; the interaction is. Recorded in the construction ledger; not repeated.

### Methods Summary
The H1 coefficient is identified in principle, since BR varies across speeches within year, topic, and audience. But the estimate is below the design's minimum detectable effect, and the paper never shows how much BR variation survives 57 other regressors. Table 2's degrees of freedom imply six unlisted regressors, consistent with weekend speech-days. The Fed's own 2013 list confirms weekend Chair speeches with no VIX close on the speech day, which widens the timing problem raised in Stage 2. The 48-speech crisis reversal cannot have been estimated with the stated Model 2 specification. The fixes are disclosure and re-estimation the author can do with existing data: a full regressor list, explicit trading-day mapping, an event-time path from t-5 to t+5, a fear measure ending at t-1, and a design analysis for H1.
