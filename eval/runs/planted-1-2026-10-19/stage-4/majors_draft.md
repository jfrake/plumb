# Candidate major issues

Contribution type: theory testing. Journal: generic. Issues are ordered by how much they do to the main claim (H1: a higher backing ratio in a Fed Chair speech raises the speech-day change in the VIX, Table 2 Model 2, BR = 0.036, SE 0.018, N = 339, p. 56).

## 1. The paper's own pre-speech placebo is significant and slightly larger than the speech-day effect, yet the text reports it as a null, so the speech-day coefficient cannot be read as the effect of the speech.

Severity: Undermines the main claim. Adjudication: paper.
Pack: archival.
Rests on alternative 1.

What the paper claims: The robustness section says that, consistent with the speech not being public before delivery, BR "did not predict market uncertainty for the two-day event window before the day of the speech" (p. 25). The Discussion then says the author "proved" that reaffirming the framework "causes uncertainty" (p. 25).

The problem: The numbers printed in that same sentence are β = .041, "σ2" = 0.017, p = .017 (p. 25). Read as a standard error, that is t = 2.41, two-tailed p = .016, with a 95 percent interval of about 0.008 to 0.074 that excludes zero and contains the main estimate. The placebo point estimate (0.041) is larger than the speech-day estimate (0.036, SE 0.018, Table 2 Model 2, p. 56), which has t = 2.00. Put per day, the BR slope is about 0.04 the day before and 0.036 on the speech day, so a single straight line fits both windows with no break at the speech. A speech cannot move the VIX before it is given, and the paper rules out leakage by its own premise (p. 25). Whatever produces the pre-speech association is something correlated with BR that moves the VIX around high-BR speeches, and that same factor can produce the speech-day coefficient with no help from the speech. The paper itself offers one candidate on p. 34, where it reads a high backing ratio as reflecting "low levels of cognitive legitimacy," which runs the arrow from contestation to backing. The placebo window's exact days are not stated, no event-time path is shown, and the Discussion (pp. 25-26) does not mention the result. The paper's control for prior 1-, 10-, and 30-day average VIX changes "did not change my results" (p. 24), but no coefficients are shown, and conditioning on yesterday's change does not remove a slow common factor.

Why it matters: For a theory-testing paper, H1's causal reading carries the contribution (pp. 2-3, 32-34). As printed, the paper's only test that separates "the speech causes uncertainty" from "backing-heavy speeches arrive when uncertainty is already rising" favors the second reading at least as much as the first, and the text describes it as the opposite.

What would settle it: Report the placebo in a table beside Model 2, with the same controls, sample, and standard errors, and state the window's days. Estimate the BR coefficient for each daily VIX change from t-5 to t+5 and plot it, so a reader can see whether there is a jump at t0 or a build-up before it. Test whether the t0 coefficient exceeds the pre-speech coefficients. Re-estimate Model 2 with the pre-speech VIX path (t-5 to t-1) as a control and show the coefficients the p. 24 sentence refers to. Correct the p. 25 sentence so it says what the numbers show. The paper already has the single pre-window estimate (p. 25) but nothing else.

Excerpt: "Third, consistent with the expectation that the speech is not made public until the date and time denoted on the transcript, the BR did not predict market uncertainty for the two-day event window before the day of the speech (β = .041, σ2 = 0.017, p = .017, adjusted R-squared = 0.083)."
Page: 25

## 2. No analysis separates the proposed mechanism (lost taken-for-grantedness) from the reading that backing paragraphs carry policy news, so H1 does not test the theory against its main rival.

Severity: Undermines the main claim. Adjudication: paper.
Pack: archival.
Rests on alternative 2.

What the paper claims: Backing paragraphs restate an unchanged framework and "likely" carry no new information, so the VIX rise reflects the framework losing its taken-for-granted status and judgments diverging (pp. 8-9, 27).

The problem: The coding rule counts a paragraph as backing when the Chair discusses "the nature and boundaries of monetary policy objectives and conventional tools" (p. 14), and much of the sample (2008-2014) is a period when those tools and goals were changing: asset purchases and forward guidance from late 2008, and a formal 2 percent goal adopted January 25, 2012. One of the paper's two illustrative backing paragraphs (Bernanke, October 18, 2011, pp. 14-15) discusses whether the Fed should have a formal inflation target, three months before it adopted one. News the market has not priced raises implied volatility on arrival, which gives a positive BR coefficient with no change in taken-for-grantedness. The paper never measures its mediator, the dispersion of market judgments (p. 9). Its one relevant check, controlling for whether backing paragraphs discussed change, future orientation, or position, is reported only as "consistent results" with no coefficients (p. 25), and as built it conditions on features of the treatment rather than splitting the treatment into restatement and change-discussing shares. The crisis-period attenuation (BR x crisis = -0.051, p = .088, p. 20) fits a news account as well, since news can raise or settle uncertainty in a crisis.

Why it matters: A theory-testing paper has to show that the evidence favors its mechanism over a standard alternative. Here a news-arrival account predicts H1 equally well, so the main estimate by itself does not discriminate.

What would settle it: Split BR into the share of paragraphs that only restate the mandate and the share that discuss tool boundaries or possible change, and report both coefficients in one model. Estimate Model 2 separately for 1998-2007, when the framework was most stable, and for 2008-2014. Report VIX changes through t+1, t+3, and t+5 (a news jump tends to fade; destabilization should persist). Use the dispersion of fed funds futures-implied rate paths or of professional rate forecasts on speech days as a mediator outcome. The paper has the p. 25 feature controls, but without estimates and in a form that cannot answer this.

Excerpt: "In this context, reaffirming the assumptions that underlie the monetary policy framework likely does not provide new information, but rather, presumably seeks to clarify and increase the “signal to noise ratio” in the Fed’s communications (Walsh, 2001; Blinder, 2009; Plosser, 2012), thereby intendedly reducing uncertainty in the market."
Page: 27

## 3. The paper's defenses against a slow-moving common cause (drafting lead times, the 40-pair comparison, and the omitted-variable bound) cannot detect a confounder of the size that would be enough, and the bound is reported at two different values.

Severity: Weakens a claim. Adjudication: paper.
Pack: archival.
Rests on alternative 1.

What the paper claims: Because high-BR speeches are written one to six months ahead and rarely changed in the final week, acute speech-day shocks cannot drive BR (pp. 21-23). Nearby speeches differ in BR, so no systemic factor drives it (pp. 23-24). An omitted variable would need to correlate at 0.12 with both BR and the outcome, which is "substantially larger than every other control variable" (p. 24; Figure 7, p. 53).

The problem: Lead times rule out shocks that arrive after drafting, not a condition (open debate about the framework, a weak labor market, a period of policy experimentation) that starts before drafting and lasts through the speech, which is what the placebo in issue 1 points to. BR already correlates 0.26 with unemployment and 0.16 with dissent by regional presidents (Table 1, p. 54). The 40-pair test reports an average BR gap of 0.21 with no interval and no benchmark (p. 23); two independent draws from a normal distribution with BR's SD of 0.22 would differ by about 0.25 on average, so nearby speeches look, if anything, slightly more alike than random pairs. A confounder at the paper's own 0.12 threshold explains about 1.4 percent of BR's variance and could not show up in that comparison. The bound itself is 0.014 in the text (0.12 x 0.12, p. 24) but drawn at 0.030 in Figure 7 (p. 53). At 0.014, observed covariates already exceed it: speech negative tone (0.27 x 0.08 = 0.022) and speech complexity (0.42 x 0.05 = 0.021, Table 1), and Figure 7 itself shows four covariate bars above 0.014. The paper does not say whether the bound uses zero-order or partial correlations or which critical value defines "below significance." The paper also reads a high backing ratio as reflecting low cognitive legitimacy (p. 34), which is the reverse-causality reading these defenses are meant to exclude.

Why it matters: The design is selection on observables (p. 18; Table 2 note, p. 57), so these defenses are the paper's whole case against confounding. As reported they do not reach the kind of confounder the placebo suggests, and the stated bound's conclusion holds only against the figure's value, not the text's.

What would settle it: Benchmark the pair test against random same-year pairs or a permutation of BR within year, with an interval. Regress BR on lagged slow-moving indicators (change in unemployment, prior three-month VIX trend, counts of press articles questioning the mandate or tools in the prior 30 to 60 days) and report the fit. Report one omitted-variable bound computed from Model 2 with its stated critical value and partial correlations, redraw Figure 7 at that value, and add a sensitivity measure benchmarked against observed covariates. Reconcile the p. 34 reading with the causal claim.

Excerpt: "This figure shows that the size of the omitted variable needed to invalidate my results is substantially larger than every other control variable used in existing literature."
Page: 24

## 4. The main estimate sits at the edge of significance and its stated size is overstated: the triple star on BR is one level too generous, the effect is below what the design can reliably detect, the 1.0 percent figure does not follow from the coefficient, and the errors do not allow for speeches that share market days.

Severity: Weakens a claim. Adjudication: paper.
Pack: inference.

What the paper claims: BR in Model 2 is 0.036*** (0.018) under one-tailed tests for directional hypotheses (Table 2, pp. 56-57), and a one-SD rise in BR "will increase this expected range by 1.0 percent" (p. 18). The Discussion says the author "proved" causation (p. 25).

The problem: The printed digits give |t| of about 1.92 to 2.09 and a one-tailed p of about .02 to .03, which supports two stars, not three; the same-size BR coefficients in Models 3 and 5 carry two stars (p. 56). The 95 percent interval runs from about 0.001 to 0.071, so whether it excludes zero depends on rounding. At 80 percent power the smallest effect the design reliably detects is about 0.045 one-tailed (0.050 two-tailed), so the estimate is 70 to 80 percent of that, and a significant estimate from an underpowered design tends to overstate the true effect. The effect size: 0.036 x 0.21 = 0.76 percent, not 1.0 percent, and Table 1 gives the SD of BR as 0.22, not 0.21 (p. 54). The 1.0 percent figure is then carried into the H2 and H3 statements ("the aforementioned 1.0 percent increase," pp. 18-19). The errors are heteroskedasticity-robust only (p. 57), with no allowance for speeches on the same or adjacent trading days, which share the outcome or part of the fear moderator; the fixed effects (year, topic, audience) and the weekday dummies (stated on p. 17; inclusion in Table 2 unconfirmed) do not absorb shocks common to a day or week. A rise in the standard error of about 17 to 27 percent would move the one-tailed p above .05.

Why it matters: A result this close to the threshold is presented as proof (p. 25). Each of these points, alone, is a reporting fix; together with issue 1 they mean the paper cannot show that BR's association with the VIX is larger on the speech day than before it.

What would settle it: Correct the star, report the exact p-value and the interval for BR in Model 2, and recompute the one-SD effect from the printed coefficient and Table 1 SD with its interval (roughly 0 to 1.5 percent), carrying the corrected figure into pp. 18-19. Report how many speeches share a trading date or week and re-estimate Models 2 to 5 with errors clustered by trading date or week, or with errors that allow for correlation over calendar time. Add a design analysis (power and expected exaggeration) for plausible true effects.

Excerpt: "Results show robust regressions with robust standard errors in parentheses."
Page: 57

## 5. Every robustness and endogeneity check is asserted in words, with no coefficients, tables, or appendix, and the one dependence check reported cannot address the dependence that matters.

Severity: Weakens a claim. Adjudication: paper.
Pack: inference.

What the paper claims: The results hold under GEE with AR(1) errors across a Chair's speeches ("strong support for all my hypotheses"), under controls for backing-paragraph features, under prior-VIX-change controls at 1, 10, and 30 days, with local-audience controls, with the federal funds rate in place of policy dummies, with 2- and 4-day fear windows, and with 15- and 150-day existing-uncertainty windows (pp. 23-25).

The problem: None of these checks reports a coefficient, standard error, or N, and the manuscript has no appendix (pp. 23-25, 49-57). The local-audience sentence (p. 23) is ambiguous because every Table 2 model already includes audience fixed effects (p. 57). The GEE groups speeches by three Chairs (159 Greenspan, 166 Bernanke, 12 Yellen, p. 12) and orders them by speech sequence, not calendar time. If its variance is a robust sandwich by Chair, it rests on three very unequal clusters; if model-based, it relies on the AR(1) structure being right; either way it does not speak to speeches that share trading days (issue 4). The paper does not say which variance it used. The backing-feature controls are the paper's only answer to the policy-news reading (issue 2), and the prior-VIX controls are its only answer to the pre-speech association (issue 1), so the reader cannot see the two checks that matter most.

Why it matters: With a main estimate at t of about 2.0 and a selection-on-observables design, these checks are the evidence behind "Despite the robustness of this simple finding" and "I proved ... causes" (p. 25). A reader cannot judge whether BR keeps its size under any of them.

What would settle it: One appendix table reporting BR, BR x tone, and BR x fear with standard errors and N under each check on pp. 23-25, with the GEE estimates in their own columns, the GEE variance type, and its panel and time variables stated. Clarify what the local-audience check compared.

Excerpt: "When doing so, I find strong support for all my hypotheses."
Page: 25

## 6. The outcome is a one-day change in U.S. equity implied volatility, but the paper claims to show institutional destabilization and uncertainty "in financial markets around the world," with no measure of the institution's stability, of the proposed mediator, or of whether the rise persists.

Severity: Weakens a claim. Adjudication: judgment.
Pack: core.

What the paper claims: The introduction asks what happens to "the stability of an institution" when a leader reaffirms its assumptions (p. 1) and states that reaffirmation "will destabilize the prevailing institution" (p. 2), through "greater heterogeneity in overall judgments" (p. 9). The Discussion says the author "proved" that reaffirmation "causes uncertainty in financial markets around the world" (p. 25), that it "disrupts the institution" (p. 26), and offers a "more general principle" illustrated by teachers and pilots (pp. 26-27).

The problem: The only outcome is ln(VIX_t / VIX_t-1) over t-1 to t0 (pp. 13, 18). The VIX is computed from S&P 500 option prices (p. 13) and measures risk-neutral expected equity volatility, which includes risk aversion; it does not measure how far traders' judgments diverge. Prior work decomposes the VIX into a risk-aversion part and an expected-volatility part and finds that monetary policy moves the risk-aversion part more (Bekaert, Hoerova and Lo Duca, NBER WP 16397, 2010). The paper never measures dispersion of judgments, never shows whether the speech-day rise persists past t0 (destabilization implies it should; a news jump would partly fade), and uses no non-U.S. market. A one-SD BR effect is about 0.13 SD of one day's VIX change and adds 0.008 to R-squared (Table 2, p. 57). The paper also has no limitations section.

Why it matters: The contribution the paper claims is institutional (pp. 2-3, 32-35). What is delivered is a one-day equity volatility association, so the theory's central construct has no direct measure, and the global claim has no evidence at all.

What would settle it: Report the BR coefficient for post-speech windows (t+1, t+3, t+5). Add outcomes closer to the policy framework, such as interest-rate implied volatility or the dispersion of professional rate forecasts or fed funds futures paths on speech days, and state in advance what each account predicts. Restate the finding at the scope of the test (speech-day S&P 500 implied volatility, 1998-2014), present destabilization as the proposed mechanism rather than the finding, remove "around the world" or add non-U.S. indices, and add a limitations section.

Excerpt: "Using speeches made by the Chair of the United States Federal Reserve from 1998 to 2014, I proved that reaffirming the assumptions underlying the monetary policy framework causes uncertainty in financial markets around the world."
Page: 25

## 7. Some speeches in the sample were given when the market could not react on the speech day (weekends, after the 4 p.m. close), and the paper does not say how these were mapped to trading days.

Severity: Weakens a claim. Adjudication: external.
Pack: archival.

What the paper claims: The outcome is the VIX change on "the day of the speech" (pp. 13, 18), and the speech is "not made public until the date and time denoted on the transcript" (p. 25). The text says weekday dummies were included (p. 17), but Table 2 and its note do not list them (p. 57).

The problem: Table 2 reports df = 57 for Model 1 (p. 57). The listed controls (23), year (16), topic (8), and audience (4) dummies come to 51, leaving 6 unlisted terms. These could be other unlisted controls. If they are weekday dummies, the only stated candidate, six of them imply seven day-of-week categories, which would be consistent with weekend speech dates in the data. The Federal Reserve's 2013 speech list, whose count matches the paper's 2013 bar in Figure 2 (p. 50), includes a Saturday speech (May 18, 2013) and a Sunday speech (June 2, 2013), plus two items on December 16, 2013 that would share one outcome value. The paper does not list its speeches, so whether these are in its sample is not confirmed. At least one framework speech ("A Century of U.S. Central Banking: Goals, Frameworks, Accountability," July 10, 2013) was delivered after the close. A weekend or after-close speech has no t0 close that reflects it: if mapped to the prior trading day the outcome is a pre-speech change, and if to the next it spans several days of other news. For these speeches any BR-VIX association at t0 cannot run through the backing, which is the pattern the placebo in issue 1 shows. Commencement and special-occasion speeches plausibly go to layperson audiences, the lowest-BR group (r = -0.34, p. 22), more often than other topics, though the paper reports no topic-by-audience breakdown. If those speeches are also the misdated ones, misdated rows may cluster at low BR.

Why it matters: The timing of the outcome is what lets the paper attribute a VIX change to the speech. If a share of rows measure a window the speech could not have affected, part of the estimate is not the mechanism.

What would settle it: List every regressor in Table 2, including weekday categories. Report how many speeches fall on weekends, holidays, or after 4 p.m. ET and how each was mapped. Re-estimate Model 2 dropping them, and again assigning them to the next trading day, and test whether the t0 slope is zero and the t+1 slope positive for after-close speeches. Collapse or drop same-day duplicates.

Excerpt: "Consistent with work in finance (Chang, Pinegar, and Ravichandran, 1993; Dubois and Louvet, 1996; Choudhry, 2000; Connolly, Stivers, and Sun, 2005), I controlled for day on which the speech took place by creating dummy variables for each weekday."
Page: 17

## 8. Because BR is a share of a speech's paragraphs, a high-BR speech is also a speech with little outlook content, and the paper does not test whether the missing outlook information, not the backing, accounts for the result.

Severity: Weakens a claim. Adjudication: paper.
Pack: core.
Rests on alternative 3.

What the paper claims: Backing is the component of an argument that carries taken-for-granted assumptions, unlike claims and data (pp. 5-7, 14), and its share in a speech drives the VIX change (p. 18).

The problem: BR is paragraphs with backing divided by all paragraphs (pp. 13-14), so a higher BR mechanically means fewer paragraphs on the economic outlook and data. The paper itself equates low-BR speeches with speeches that "discuss the current outlook of the economy" (p. 22) and reads the negative word-count coefficient as longer speeches carrying more information (p. 28). Outlook content tends to settle uncertainty, so a high-BR speech can settle less and show a higher VIX change by comparison, with the backing doing nothing. Topic fixed effects are speech-level and do not capture this within-speech trade-off (p. 17). The paper already codes every paragraph (p. 13) but reports only the backing share.

Why it matters: This account predicts the H1 sign from how the measure is built, with no claim about cognition. For a theory-testing paper the absence of a specificity test leaves the mechanism unidentified against a simpler explanation.

What would settle it: Code each paragraph into the Toulmin components the paper already describes (data, claim, warrant, backing; Figure 1, p. 50) and enter the component shares or counts together, with one omitted, in one table. Or add the outlook and data paragraph share alongside BR. If BR keeps its coefficient with outlook content held fixed, the paper's reading is strengthened.

Excerpt: "For speeches that discuss the current outlook of the economy (i.e., low BR speeches), writing starts a month before so the most current economic indicators are used."
Page: 22

## 9. Backing-heavy speeches may fall at points in the policy-meeting cycle, or in periods of debate over tools, when traders reasonably expect the rules to change, and the paper does not control for meeting-cycle position or test this reading.

Severity: Weakens a claim. Adjudication: external.
Pack: archival.
Rests on alternative 4.

What the paper claims: Discussing the rules makes alternatives thinkable, not more probable, so uncertainty rises because the framework loses its fact-like status (pp. 8-9).

The problem: If traders read a Chair's discussion of the rules as a sign that a rule change is more likely, ordinary asset pricing raises volatility, especially in weak markets (Pástor and Veronesi 2013), which gives the H1 sign and the H3 sign without any loss of taken-for-grantedness. Fed communication also intensifies before policy meetings, especially before rate changes, and markets react more to it then (Ehrmann and Fratzscher 2007). The paper controls for the last meeting's decision and dissents and for same-day releases (p. 16), but not for days to the next meeting. Governor speeches enter only as a same-day dummy (p. 16), so the paper cannot compare the Chair's BR slope to that of less powerful speakers.

Why it matters: This is a second rival account that predicts the main result and one moderator. Without a test, H1 cannot be credited to the paper's mechanism.

What would settle it: Add days-to-next-meeting fixed effects and a BR x pre-meeting interaction, and a BR x unconventional-tools-period indicator. Code BR for a sample of governor or regional-president speeches and compare slopes. Check whether the effect concentrates where a rule change was plausible (before meetings, around the January 2012 goal statement), and whether it shows in the dispersion of expected rate paths.

Excerpt: "I controlled for expansionary and contractionary monetary policy conditions by creating two dummy variables that were coded “1” if the most recent FOMC meeting resulted in lowering the federal funds rate (i.e., expansionary monetary policy) or raising the federal funds rate (i.e., contractionary monetary policy)."
Page: 16

## 10. The financial-crisis extension, which the Discussion calls "additional validation," rests on estimates that do not fit together and on a 48-speech subsample selected on both moderators and on a fear measure taken after the outcome.

Severity: Weakens a claim. Adjudication: paper.
Pack: nonlinear.

What the paper claims: When taken-for-grantedness was weakened in 2008-2012, reaffirming the backing no longer raised uncertainty "to the same extent," and in high-tone, low-fear crisis speeches it "actually decreases uncertainty" (pp. 19-21; Figure 6, p. 52). The Results label this tentative and preliminary (pp. 19-20); the Discussion calls it "additional validation of this story" (p. 26).

The problem: Three estimates are given only in text. The pooled BR x crisis interaction is -0.051 ("σ2" 0.038), p = .088 with year fixed effects (p. 20); read as a standard error, t = 1.34, so that p is one-tailed (two-tailed about .18) for a term that is not a numbered hypothesis, while the Table 2 note limits one-tailed tests to directional hypotheses (p. 57). The crisis-only split gives BR = 0.035 (p = .335, p. 20), the same point estimate as the full sample's 0.036, so the split shows lost precision, not a smaller effect; with about 30 percent crisis speeches, the pooled interaction instead implies a crisis slope near zero. The 48-speech reversal (β = -0.155, p = .022, p. 21) comes from crisis speeches above the mean on tone and below the mean on fear, re-estimated with "Model 2," which omits the BR x tone and BR x fear terms; the full-sample Model 5 already predicts a negative BR slope in that cell anywhere in the sample (about -0.03), so the cell cannot isolate a crisis effect. Model 2 has df = 58 (p. 57), more parameters than 48 observations, so the stated specification cannot have been estimated; the printed p implies roughly 20 residual degrees of freedom, and the terms actually used are not reported. The fear cut uses a measure averaged over t-1 to t+1 (p. 16), which includes the outcome day and the day after; keeping only low-fear days can remove high-BR speeches followed by VIX rises and so build in a negative slope. Taken-for-grantedness is never measured, and no estimate is given for the non-crisis years where the theory says it applies best.

Why it matters: The Discussion builds a contingent theory and practical advice on this result (pp. 26, 30). As reported, the crisis evidence does not show attenuation in the point estimate, and the reversal may come from how the subsample was cut.

What would settle it: Report the crisis analyses in a table with full term lists, residual degrees of freedom, N, standard errors labeled as such, and stated tails. Estimate the crisis difference in the full sample with Model 5 plus BR x crisis (and BR x crisis x tone, BR x crisis x fear), and report the same high-tone, low-fear cell outside the crisis. Rebuild fear over days before the speech and redo the split. Report Model 2 for non-crisis years. Otherwise keep the Discussion at the Results' "preliminary" wording.

Excerpt: "Interestingly, as additional validation of this story, I also illustrated how, during the financial crisis, when the taken-for-grantedness of these assumptions had weakened, reaffirming them no longer creates uncertainty to the same extent."
Page: 26

## 11. The business media fear moderator behind H3 is averaged over a window that includes the speech day and the day after, comes from a vendor series back-scored for most of the sample, and moves with the macro era, so BR x fear may not measure the emotional climate the theory names.

Severity: Weakens a claim. Adjudication: paper.
Pack: computational.

What the paper claims: Fear in business media at the time of the speech is the "prevailing zeitgeist of the market" in which traders read the speech, and it amplifies the BR effect (pp. 11-12, 19; Table 2 Models 4-5, BR x fear = 30.590, SE 12.626, and 26.293, SE 12.482, p. 56).

The problem: Fear is the average of a daily index over t-1 to t+1 (p. 16), while the outcome is t-1 to t0 (p. 13). Two of the three days are the outcome day and the day after, when business news reports on that day's market move and on the speech itself, so the moderator is partly caused by the outcome or the treatment. It also enters every model, including the H1 model, as a control. The window robustness check (2- and 4-day, p. 25) does not say whether those windows end before t0 and shows no estimates. The vendor's own releases say the indices launched in 2012 and cover history from 1998, so values for 1998 to mid-2012 were scored after the fact, from a source mix that likely changed; the paper's "dictionary approach" description (p. 15) differs from the vendor's, and no validation is reported. Table 1 prints fear's SD as 0.00 (p. 54), so H3 magnitudes cannot be recomputed. In the paper's data fear is lower when unemployment is higher (r = -0.43) and higher with inflation (0.30) (Table 1), so low-fear speeches cluster in the high-unemployment crisis years where the BR slope is said to be smaller (p. 20). BR x fear may then restate the crisis pattern, or larger log-VIX moves in volatile periods, rather than framing; existing uncertainty enters only as a main effect.

Why it matters: H3 is one of three hypotheses and one of the paper's two moderation claims (pp. 3, 29). A moderator measured partly after the outcome and tied to the macro era cannot show that fear at the time of the speech shapes how traders read it.

What would settle it: Rebuild fear from days strictly before t0 (for example t-5 to t-1) and re-estimate Models 4-5. Add BR x existing uncertainty, BR x unemployment, BR x crisis, and BR x Chair to Model 5. Re-estimate H3 with fear demeaned within year. State the vendor feed, version, extraction date, and backfill, report H3 separately before and after the 2012 launch, and print fear's SD with enough digits.

Excerpt: "I constructed a business media fear variable by taking the average of this fear index over a three-day window (t-1 to t+1) around the day of the speech."
Page: 16

## 12. The LIWC positive-tone moderator behind H2 likely measures favorable economic content and speech genre rather than the speaker's emotional tone, and the model leaves out the BR interactions that would separate them.

Severity: Weakens a claim. Adjudication: external.
Pack: computational.

What the paper claims: Positive emotional tone narrows attention to optimistic interpretations and suppresses the BR effect (pp. 10-11, 18; Table 2 Model 3, BR x tone = -0.056, SE 0.020, p. 56).

The problem: The dictionary's example words include "good," "positive," "great," "favorable" (p. 15), which in Fed speeches usually describe economic conditions. LIWC was validated on personal writing, blogs, novels, science articles, and student essays, not policy speeches, and general dictionaries misclassify financial text (Loughran and McDonald 2011), a dictionary the paper uses for speech uncertainty but not for tone (p. 17). Tone is scored over the whole speech, including the non-backing paragraphs that carry the outlook (p. 14), so tone and BR come from the same text. Table 1 shows positive tone correlates -0.41 with word count and -0.27 with complexity (p. 54): short, simple, upbeat speeches are the commencement and ceremonial genre, where backing is boilerplate. Topic and audience fixed effects remove genre levels, not genre differences in the BR slope, and BR x length, BR x complexity, or BR x topic are not in the model. The moderation per LIWC point (0.056) is larger than the BR main effect (0.034), so the paper's effect reverses for about a quarter of speeches. The LIWC version is not stated, and the "power" category the paper uses does not exist in the LIWC2007 dictionary it cites (p. 17).

Why it matters: H2 is one of the paper's two moderation claims, and the Discussion's advice to wrap backing in positive language (p. 30) rests on it. If tone is a proxy for outlook content or genre, the interaction does not show emotional framing.

What would settle it: Report the words driving the tone score in this corpus; hand-code a random sample of sentences for affective positivity versus favorable economic description and report the dictionary's precision. Re-estimate Models 3 and 5 with tone scored on non-backing paragraphs only, with economic-sense words removed, and with the Loughran-McDonald positive list. Add BR x word count, BR x complexity, and BR x topic to Model 3, and estimate it without commencement and special-occasion speeches. State the LIWC version.

Excerpt: "Positive emotional content is captured using a dictionary approach, whereby the percentage of words psychometrically related to positive emotion (e.g., happy, good, nice, positive, great, favorable, etc.) are reported in relation to all words in a speech."
Page: 15

## 13. The text says that at high positive tone reaffirming the backing "in fact, reduces" uncertainty, but the paper gives no test of that conditional slope, and the reported numbers support it only under a strongly negative covariance it does not report.

Severity: Weakens a claim. Adjudication: paper.
Pack: nonlinear.

What the paper claims: At +1 SD of positive tone the 1.0 percent increase "goes away and, in fact, reduces the expected range by 0.5 percent," and at -1 SD tone it increases the range by 3.5 percent (pp. 18-19). The Discussion advises leaders to encase backing "within more positive language" (p. 30).

The problem: Assuming tone was centered, as Figure 4 implies (p. 51), the slope at +1 SD is 0.034 - 1.01 x 0.056 = -0.023 in Model 3, and -0.009 in Model 5. With zero covariance its z is -0.83; it reaches the paper's one-tailed .10 level only if the two estimates correlate at -0.58 or lower, and .05 only at -0.75 or lower. The covariance is not reported, Figures 4 and 5 have no confidence bands, and no simple-slope test or region of significance appears (pp. 18-19, 51-52, 57). The 3.5 percent figure at -1 SD does not match Table 2 or Figure 4 (about 1.9 percent by the paper's own method). The paper does not state whether either moderator was centered, gives no range for either, and prints fear's SD as 0.00 (p. 54), so the plotted values cannot be checked against the data. By contrast, the slope at -1 SD tone (0.091) is distinguishable from zero under any covariance.

Why it matters: H2 predicts only that tone weakens the BR effect, which the product term shows. The reversal claim and the practical advice built on it go beyond what the estimates establish.

What would settle it: Report the conditional effect of BR across the observed range of tone (and fear) with standard errors from the estimated covariance, for Models 3 and 5, and add bands to Figures 4 and 5. State centering and moderator ranges. Correct the 3.5 percent figure. Or narrow the text to "attenuated at high tone" and drop the reversal reading on p. 30.

Excerpt: "Interestingly, when a speech’s positive tone is one standard deviation below its mean, this actually amplifies market uncertainty, increasing the expected range by 3.5 percent."
Page: 19

## 14. The estimation sample was trimmed on studentized residuals from an unstated model of the outcome, the count after trimming conflicts with the tables, and the estimator is described two ways.

Severity: Weakens a claim. Adjudication: paper.
Pack: inference.

What the paper claims: Seven of 344 speeches were dropped for studentized residuals beyond plus or minus three, leaving 337 (p. 12). The estimator is "OLS regression with year-fixed effects" (p. 18).

The problem: Tables 1 and 2 and Figure 2 report N = 339, not 337 (pp. 50, 54-57). The paper does not say which model produced the residuals (with or without BR and the moderators), which tail the dropped speeches came from, or their BR values, and reports no estimate on all 344. Dropping on outcome residuals selects on the dependent variable for every estimate, and the speeches with the largest unexplained VIX moves are plausibly the most market-moving speeches, the events the theory concerns; the direction of any bias cannot be signed from what is reported. The Table 2 note says "robust regressions with robust standard errors" (p. 57), and robust regression in the reweighting sense is a different estimator from OLS with robust errors (p. 18).

Why it matters: The main estimate is near the threshold (issue 4), so a choice that removes the largest outcome values could matter for whether H1 holds, and a reader cannot tell which estimator produced Table 2.

What would settle it: State the reference model for the residuals, list the dropped speeches with dates, BR, and VIX changes, reconcile 337 with 339, name the Table 2 estimator exactly, and report Models 2 to 5 on all 344 speeches beside the trimmed results.

Excerpt: "Seven speeches were removed because, based on an outlier analysis, their studentized residuals exceeded plus or minus three."
Page: 12

## 15. The paper does not show how much variation in BR survives 57 other regressors, topic is coded from the same speech content as BR, and the bivariate association is below the paper's own significance threshold.

Severity: Weakens a claim. Adjudication: paper.
Pack: archival.

What the paper claims: BR's effect is estimated by "OLS regression with year-fixed effects" (p. 18), with topic and audience fixed effects added in every model (p. 17; Table 2 note, p. 57).

The problem: Model 2 spends 58 regressors on 339 speeches (p. 57). BR correlates 0.42 with complexity, 0.37 with power, 0.35 with audience sophistication, 0.27 with negative tone, 0.26 with unemployment, and 0.23 with word count (Table 1, p. 54; p. 22). Topics such as "central banking" and "economic history" (p. 17) are coded inductively from speech content and describe speeches about the framework itself, which by the coding rule are high-BR speeches, so topic fixed effects remove the between-topic contrast the theory is about and leave only within-topic differences. The estimator sentence on p. 18 names only year fixed effects. Topic and audience enter as dummy-variable controls described on p. 17 and as fixed effects in the Table 2 note (p. 57). The raw correlation of BR with the outcome is 0.09 (Table 1), below the 0.11 threshold the Table 1 note gives for p < .05; the implied bivariate slope is about 0.025, against 0.036 in Model 2, so the estimate depends on suppressor controls (for example dissent by regional presidents, r = 0.16 with BR and -0.17 with the outcome). No specification between BR alone and the full model is shown.

Why it matters: Conditioning is legitimate, but with t of about 2.0 the reader needs to see where the estimate comes from and how much identifying variation is left before accepting a "simple finding" (p. 25).

What would settle it: Report the R-squared from regressing BR on all fixed effects and controls and the SD of residualized BR. Report Model 2 built up from BR alone, then year, topic, and audience fixed effects, then controls. Report mean BR by topic.

Excerpt: "To conduct this event study analysis, I used OLS regression with year-fixed effects to estimate the effect of Fed speeches’ BR on market uncertainty."
Page: 18

## 16. The backing ratio is coded with a broad rule by coders whose blinding to speech dates and market history is not reported, and reliability is reported only for the first 60 and last 10 speeches.

Severity: Weakens a claim. Adjudication: judgment.
Pack: archival.

What the paper claims: Paragraph-level coding by the author and three undergraduates reached Krippendorff's alpha of 0.88 and .84 (pp. 13-14).

The problem: The rule codes a paragraph as backing when the Chair "reaffirms or reiterates in some way the nature and boundaries of monetary policy objectives and conventional tools" (p. 14). Coders familiar with monetary policy coded the speeches years after delivery (the records request is dated 2015, p. 13), and the paper does not say whether they saw dates, speakers, or market outcomes, or how disagreements were resolved. Coders who know which speeches moved markets can read tool and policy discussion in those speeches as backing, and that error would correlate with the outcome; high agreement among coders who share the same hindsight does not rule it out. Reliability is not reported for the middle 267 speeches (79 percent of the sample) or at the speech level the analysis uses. BR's correlations with complexity (0.42), power (0.37), and negative tone (0.27) fit policy-dense speeches more than ceremonial restatement (Table 1, p. 54). Random coding error would attenuate H1; hindsight error could bias toward it.

Why it matters: The whole test rests on BR measuring restatement of taken-for-granted assumptions. The effect per SD of BR is small next to the outcome's SD (0.008 against 0.06), so a handful of misread market-moving speeches could carry it.

What would settle it: Publish the codebook with marginal examples. Have coders blind to date and speaker re-code a random sample drawn across 1998-2014, presented out of order, and report speech-level agreement and the BR coefficient on the blind codes. State whether coders saw market data and how disagreements were resolved. Report Model 2 dropping the 10 to 20 speeches with the most newswire coverage on t0.

Excerpt: "I calculated interrater reliability at the paragraph level (Neuendorf, 2001; Krippendorff, 2003) for the first 60 speeches (Krippendorff’s alpha = 0.88) as well as for the last 10 speeches (Krippendorff’s alpha = .84) to demonstrate consistency."
Page: 13
