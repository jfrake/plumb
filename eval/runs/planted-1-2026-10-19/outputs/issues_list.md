## Issues

### 1. The pre-speech placebo is significant and at least as large as the speech-day effect, and the defenses against a slow-moving common cause do not close the gap.

Severity: Undermines the main claim
Fix: new analysis
Where: p. 25

The p. 25 text says BR "did not predict" the VIX change in the two days before the speech, but the printed placebo is significant (β = .041, p = .017) and at least as large as the speech-day estimate (0.036, Table 2 Model 2), with a larger t (2.4 against 2.0). A speech cannot move the VIX before it is given, so something correlated with BR may produce the speech-day coefficient. As printed, H1's own falsification test fails. The placebo's controls are not described, and its adjusted R-squared (0.083) differs from Model 2's (0.177).

Drafting months ahead excludes later shocks, not conditions that persist. The 40 nearby pairs differ in BR by 0.21, less than the roughly 0.25 expected for random pairs. The prior-VIX controls have no printed estimates, and the omitted-variable bound is 0.014 in the text but 0.030 in Figure 7.

Start with BR coefficients on daily VIX changes from t-5 to t+5 with the Model 2 controls, testing the leads jointly and against t0. Rerun the placebo with those controls, print the prior-VIX estimates, benchmark the pair test against random pairs, and report one omitted-variable bound. Correct the p. 25 sentence. If the leads stay comparable to t0, present H1 as an association without causal language.

### 2. The p. 25 control does not separate lost taken-for-grantedness from the reading that backing paragraphs carry news about the policy rules.

Severity: Undermines the main claim
Fix: new analysis
Where: p. 14

Your theory holds that stating the backing lowers its taken-for-grantedness and so widens market judgments. A news reading predicts the same sign. The coding rule counts discussion of "the nature and boundaries of monetary policy objectives and conventional tools" as backing, in a sample that spans the 2008 tool changes and the 2012 adoption of a numerical inflation goal. If traders read such paragraphs as news about the rules, ordinary asset pricing raises volatility (Pástor and Veronesi 2013) with no loss of taken-for-grantedness. Your control for change-discussing paragraphs is reported without numbers. Meeting timing could produce the same pattern, since central banks communicate more before policy meetings (Ehrmann and Fratzscher 2007), and you control for the last meeting's decision but not the distance to the next. Until restatement is separated from news, H1 support does not test the mechanism.

Recode each backing paragraph as restatement or as discussing a change, and enter both shares in Model 2. Show whether BR varies with days to the next FOMC (Federal Open Market Committee) meeting, and add a pre-meeting indicator and its interaction with BR. If you can do only one, do the split.

### 3. The outcome is the t-1 to t0 change in U.S. equity implied volatility, but the paper concludes that backing "causes uncertainty in financial markets around the world."

Severity: Weakens a claim
Fix: new analysis
Where: p. 25

What evidence beyond the speech-day VIX change shows that the policy framework, rather than near-term volatility expectations, became less taken for granted? The VIX includes risk aversion, which monetary policy moves (Bekaert, Hoerova and Lo Duca 2010). It does not measure the dispersion of judgments the theory names, and no non-U.S. market is studied.

Do both. Report BR coefficients for t+1, t+3, and t+5, and add a dispersion outcome such as professional rate forecasts. Then restate the conclusion at the scope of the test: a speech-day change in U.S. equity implied volatility.

### 4. The paper does not say what BR adds to finance research on Fed speech content, or to Harmon, Green and Goodnight (2015), whose model it tests.

Severity: Weakens a claim
Fix: can't fix, narrow the claim
Where: p. 3

If the paper contributes to central-bank communication, you must show what BR adds to known speech effects. Bligh and Hess (2006) find that coded Greenspan language forecasts financial market variables. Born, Ehrmann and Fratzscher (2011) find that speeches matter mainly in the 2007-10 crisis, as in your crisis split. Heaphy (2013) and Ashforth and Gibbs (1990) address whether invoking the backing maintains or erodes it.

New data cannot fix this, so narrow the claim. Present the paper as a test of Harmon et al.'s model with a daily market outcome, claim only what BR adds beyond coded tone and policy content, and drop sentences that present the Fed speech-market link as unstudied.

### 5. BR may capture missing outlook content and speech topic rather than reaffirmation, and the paper does not show that its coding was blind to outcomes.

Severity: Weakens a claim
Fix: new analysis
Where: p. 22

BR is backing paragraphs over all paragraphs, and p. 22 calls speeches that "discuss the current outlook of the economy" low-BR speeches. If outlook content resolves uncertainty, BR's construction alone predicts the H1 sign. BR's raw correlation with the outcome (0.09) is below the 0.11 the Table 1 note gives for significance, so the estimate depends on the 58-df specification. Coders who knew which speeches moved markets could read policy discussion as backing, an error correlated with the outcome, and coder blinding is not reported.

Report the R-squared of BR on the other regressors and its within-topic variation, and build Model 2 up from BR alone. Code outlook paragraphs and add their share beside BR. Have blind coders re-code a random sample and compare agreement and the BR coefficient across codings.

### 6. The standard errors ignore speeches that may share trading days, the sample was trimmed on residuals from an unnamed model, and most robustness checks print no estimates.

Severity: Weakens a claim
Fix: new analysis
Where: p. 57

The paper reports 40 pairs of speeches within three days of each other, so some may share event-window dates, yet the errors are robust only, and the GEE check links each speech's error to the same Chair's prior speech. Seven speeches were dropped on studentized residuals from an unnamed model, which risks selecting on the outcome, and the remaining 337 do not match the 339 in Tables 1 and 2. The one-tailed p for 0.036 (0.018) is about .023: two stars, not three.

Cluster errors by trading date and, as a check, by week. Name the trimming model and the estimator, reconcile the counts, and report the main models with the seven speeches retained. Add an appendix table of the BR coefficient, standard error, and N under each robustness check.

### 7. The tone and fear moderators may not measure the emotions H2 and H3 name, and the conditional effects stated in the text are untested and do not match the estimates.

Severity: Weakens a claim
Fix: new analysis
Where: p. 19

LIWC positive words such as *good* and *favorable* usually describe the economy in Fed speeches, and general dictionaries misclassify financial text (Loughran and McDonald 2011). The text says that at +1 SD of tone backing "in fact, reduces" uncertainty, but reports no test of that slope. If tone is centered, Model 3 gives a slope of about -0.023 (0.034 - 0.056 x 1.01). Fear averages t-1 to t+1, so it can report on the speech and that day's market move, and it correlates -0.43 with unemployment (Table 1).

Score tone on non-backing paragraphs and with a finance dictionary's positive list, and add BR x word count. Rebuild fear from days before t0 and add BR x existing uncertainty to Model 5. Report each conditional effect with its standard error, or narrow the claims to attenuation and amplification.

### 8. The crisis extension, called "additional validation" in the Discussion, comes from a subsample selected on both moderators and a model with more parameters than speeches.

Severity: Weakens a claim
Fix: new analysis
Where: p. 26

The Results call this analysis tentative and "preliminary evidence", but the Discussion calls it "additional validation". The crisis-only estimate (0.035, p = .335) is almost identical to the full-sample 0.036, which shows imprecision, not a smaller effect. The interaction p-values of .088 and .026 match one-tailed tests the paper does not state. The 48-speech reversal is cut at the means of both moderators, one measured after the outcome, and fits Table 2's 58-df model to 48 speeches.

Report Models 2 and 5 for crisis and non-crisis speeches with N and tails, say which terms were kept for the 48 speeches, show other cutoffs, and estimate the same high-tone, low-fear cell outside the crisis. Or call the crisis result preliminary in the Discussion, as the Results already do.

## Minor issues

- 9. The paper does not say how speeches on weekends or late in the trading day were mapped to the t-1 to t0 window. (p. 13)
- 10. The only source you cite for the step from lower taken-for-grantedness to more dispersed judgments, the 2008 Organization Science article listed under Thessaly in your references, could not be found, and its stated pages overlap another article in that volume. (p. 9)
- 11. The only scholarly source you cite for central bankers' beliefs, the 2011 Journal of Monetary Economics article listed under Brandvold and Halvorsen in your references, could not be found, and the pages it gives belong to other articles. (p. 3)
- 12. Page 7 says the backing is only more taken for granted than the other components, but p. 8 says it "typically goes without saying"; say how backing the Chair discusses regularly can still lose taken-for-grantedness. (p. 8)
- 13. The word-count coefficient prints as -0.000 (0.000) in every model, so the Discussion's claim that longer speeches reduce uncertainty cannot be checked; report it per 1,000 words. (p. 28)
- 14. Which recommendation, wrapping backing in positive language or discussing the assumptions more regularly, does the evidence support, and what result would show that the extra uncertainty deters risk-taking? (p. 32)
- 15. Business media fear in Model 4 is 0.005** with a standard error of 2.924, which cannot be significant. (p. 56)
- 16. The Model 5 adjusted R-squared of 0.261 does not follow from its R-squared of 0.355 with 339 observations and 60 df, which give 0.216. (p. 57)
- 17. The text-only estimates label their uncertainty "σ2," which reads as a variance, not a standard error. (p. 20)
- 18. The stars on the positive-tone main effect require one-tailed tests, but the Table 2 note says controls are tested two-tailed. (p. 57)
- 19. Audience fixed effects remove five category means, not attention differences within a category; a t0 newswire count per speech and its interaction with BR would address this. (p. 57)
- 20. Under your mechanism, should traders who follow Fed policy closely react more or less to backing than others, and can you show which group moves the VIX on high-BR days? (p. 22)
- 21. Year fixed effects nearly absorb Chair identity, but no BR x Chair term tests whether markets read backing differently across three Chairs with very different speech counts. (p. 12)
- 22. The paper describes the VIX as traders' estimate of the direction of the S&P 500, but it measures the expected size of moves, so the argument about optimistic and pessimistic directions is not tested by it. (p. 13)
- 23. The introduction says we still know little about leaders who reaffirm assumptions and uses a practitioner belief as its foil, while signaling theory, which holds the view the paper argues against, appears only in the Discussion, where the promised reversal becomes complementary under a condition never measured. (p. 27)
- 24. The three language controls for Fedspeak come from dictionaries validated in other domains, and the partial vagueness dictionary is not specified. (p. 17)
- 25. Both interactions use a single linear product term, with no binned check that the BR slope changes linearly with tone or fear. (p. 18)
- 26. H2 and H3 extend Pfarrer et al. (2010), as the paper says, so their space might go to the H1 mechanism. (p. 28)
- 27. Research on ease of retrieval in persuasion offers a tested micro-mechanism for H1 and a moderator, audience elaboration, that the paper could use or rule out. (p. 10)
- 28. The VXX translation does not follow from a spot-VIX coefficient, because the VXX began trading in 2009 and its issuer states it will not necessarily track the VIX. (p. 18)
- 29. Table 1 prints an SD of 0.64 for the Washington, D.C. dummy, impossible for a 0/1 variable with mean 0.29, and prints fear's SD as 0.00; report it unrounded. (p. 54)
- 30. The reference list misspells McDonald as "McDonaold" in Loughran and McDonald (2011). (p. 44)
- 31. The audience correlations show that BR varies with audience, not that it measures reaffirmation rather than technical content, and the benchmark is the expectation of the author of about half the speeches; check BR against an independent coding of restatement. (p. 23)

## What I left out

This is the whole list of issues that survived the checks. None of the items below is a separate request.

## Dropped items

- The defenses against a slow-moving common cause cannot detect a confounder of the size that would suffice, and the omitted-variable bound is reported at two values.: merged into a kept issue in the audit
- Backing-heavy speeches may fall where traders expect the rules to change, and the paper does not control for position in the policy-meeting cycle.: merged into a kept issue in the audit
- BR is coded with a broad rule by coders whose blinding is not reported, and reliability covers only 70 of the speeches.: merged into a kept issue in the audit
- Every robustness and endogeneity check is described in words, with no coefficients, tables, or appendix.: merged into a kept issue in the audit
- The sample was trimmed on residuals from an unstated model of the outcome, the count conflicts with the tables, and the estimator is described two ways.: merged into a kept issue in the audit
- The paper does not show how much BR variation is left after 57 other regressors, and topic is coded from the same content as BR.: merged into a kept issue in the audit
- The text says that at high positive tone backing "in fact, reduces" uncertainty, but no test of that conditional slope is reported.: merged into a kept issue in the audit
- The business media fear moderator used for H3 is averaged over a window that includes the day after the speech, and it moves with the macro era.: merged into a kept issue in the audit
- The gap statement does not say what existing theory gets wrong.: merged into a kept issue in the audit
- The promised reversal is recast as complementary in the Discussion.: merged into a kept issue in the audit
- The query about the Kincaid readability report's author list did not match.: overruled in the audit
- Estimate the main model separately before and after 2008: cut from a kept issue in the audit
- Compare the Chair's backing-ratio slope with that of governors: cut from a kept issue in the audit
- Fear series values before the vendor launch were scored retrospectively: cut from a kept issue in the audit
- Add Chair fixed effects to the model: cut from a kept issue in the audit

REFERENCES

Ashforth, B. E., and Gibbs, B. W. (1990). The double-edge of organizational legitimation. Organization Science, 1(2), 177-194.

Bekaert, G., Hoerova, M., and Lo Duca, M. (2010). Risk, uncertainty and monetary policy. NBER Working Paper 16397.

Bligh, M., and Hess, G. D. (2006). A quantitative assessment of the qualitative aspects of Chairman Greenspan's communications. Computing in Economics and Finance 2006, No. 213. Society for Computational Economics.

Born, B., Ehrmann, M., and Fratzscher, M. (2011). Central bank communication on financial stability. National Bank of Poland Working Paper 93.

Ehrmann, M., and Fratzscher, M. (2007). The timing of central bank communication. European Journal of Political Economy, 23(1), 124-145.

Harmon, D. J., Green, S. E., Jr., and Goodnight, G. T. (2015). A model of rhetorical legitimation: The structure of communication and cognition underlying institutional maintenance and change. Academy of Management Review, 40(1), 76-95.

Heaphy, E. D. (2013). Repairing breaches with rules: Maintaining institutions in the face of everyday disruptions. Organization Science, 24(5), 1291-1315.

Loughran, T., and McDonald, B. (2011). When is a liability not a liability? Textual analysis, dictionaries, and 10-Ks. Journal of Finance, 66(1), 35-65.

Pfarrer, M. D., Pollock, T. G., and Rindova, V. P. (2010). A tale of two assets: The effects of firm reputation and celebrity on earnings surprises and investors' reactions. Academy of Management Journal, 53(5), 1131-1152.

Pástor, L., and Veronesi, P. (2013). Political uncertainty and risk premia. Journal of Financial Economics, 110(3), 520-545.