## Adversarial DGP Analysis

Agent: Adversarial DGP Agent. Inputs read: stage-0/phase1_summary.md, stage-0/contribution_defense.md, stage-0/fingerprint.md, brief.md, stage-1/numeric_fidelity.md, stage-1/arithmetic.md, stage-2/setting.md, timeline.md, dgp_map.md, stage-3/argument_map.md, alternatives.md, theory_devil_report.md, mechanism_discrimination.md, stage-4/mechanism_discrimination_issues.md, extracted_tables/table_01.csv and table_02.csv (authoritative digits), PDF pp. 12-26. Search cap 2016-06-01 respected; sources fetched are listed at the end. Five searches or fetches used.

Severity uses the contract labels: Undermines the main claim, Weakens a claim, Minor. Alternatives I could dismiss on the paper's own evidence were dropped (self-answering filter). Each finding also lists the categories I checked and set aside, with the reason.

Scope note. Stage 3 already carries four alternatives, all marked "investigate further": reverse causality from pre-existing contestation, policy news in backing paragraphs, crowded-out outlook content, and policy-rule uncertainty. It also carries FOMC-cycle position, venue attention, volatility scaling of H3, the t+1 fear window, LIWC tone as policy content, Chair composition, the VIX redefinition, and after-close misdating (stage-2). I do not restate them. The alternatives below are new, or they add a test or a magnitude calibration that the earlier reports lack. Where one builds on an earlier concern, I say which.

Fingerprint check: the `Designs:` line lists Selection (secondary; ITCV, p. 24). brief.md records no user corrections. For the two auto-severity patterns tied to selection (outcome-conditioned sample construction; survivor bias), I cite design-module check SO14 by id and do not set severity.

---

### Step 0: Steelman of the design

**Identification strategy, in the author's terms.** "To conduct this event study analysis, I used OLS regression with year-fixed effects to estimate the effect of Fed speeches' BR on market uncertainty" (p. 18). The Table 2 note adds topic and local-audience fixed effects and "robust regressions with robust standard errors" (p. 57). Identifying variation: within-year differences in the share of backing paragraphs across speeches, conditional on market, same-day-news, and speech-text controls (pp. 16-17).

**The author's case.** (1) Timing. Speeches are scheduled about six months ahead, high-BR speeches are written one to six months ahead, and speeches are "rarely, if ever, changed within one week" (pp. 21-22). So acute speech-day shocks cannot drive BR. (2) BR is driven mainly by the invited local audience (r = 0.35 for a linear sophistication scale, p. 22). That is a pre-set, non-market channel, and audience fixed effects absorb it. (3) For systemic factors: speeches within three days of each other differ in BR by 0.21 on average (N = 40 pairs), and controls for prior average daily VIX changes over 1, 10, or 30 days "did not change my results" (pp. 23-24). (4) ITCV: a confounder would need r = 0.12 with both BR and the DV (p. 24). (5) A pre-window placebo (p. 25), GEE by Chair, backing-feature controls, and alternative windows (pp. 24-25).

**What the author acknowledges.** The ideal experiment is impossible, and market factors may shape both talk and uncertainty (p. 12). An omitted market variable is "the primary endogeneity concern" (p. 21). The ITCV conclusion holds "Assuming that I have included a reasonable set of control variables" (p. 24). The crisis analysis is "tentative" and "preliminary" (pp. 19-20).

Each alternative below was checked to make sure it contradicts the claimed mechanism (explicit backing, then lost taken-for-grantedness, then diverging judgments, then higher VIX; pp. 8-9) and does not restate it.

### Step 1: Key findings

| # | Pattern (Table 2 digits from table_02.csv) | Author's mechanism |
|---|---|---|
| 1 | BR raises the speech-day ln(VIX_t/VIX_t-1): 0.036 (0.018), Model 2; one SD of BR is about 0.8 percent of VIX (0.036 x 0.22), against an outcome SD of 6 percent (Table 1) | Explicit backing removes taken-for-grantedness, so judgments diverge (pp. 8-9) |
| 2 | BR x speech positive tone = -0.056 (0.020), Model 3; -0.049 (0.020), Model 5 | Positive tone narrows attention to optimistic alternatives (pp. 10-11) |
| 3 | BR x business media fear = 30.590 (12.626), Model 4; 26.293 (12.482), Model 5 | Fear widens the divergence (pp. 11-12) |
| 4 | Crisis heterogeneity: BR x crisis = -0.051, p = .088; among 48 crisis speeches with high tone and low fear, BR = -0.155, p = .022 (pp. 20-21, Figure 6) | Taken-for-grantedness was already weakened in the crisis, so reaffirmation stabilizes (pp. 19-21, 26) |

---

### Finding 1: Backing ratio raises speech-day VIX change (H1)
**Authors' mechanism:** reaffirming the backing makes alternatives thinkable, market judgments diverge, and implied volatility rises (pp. 8-9).

#### Alternative 1a: The defenses against a systemic confounder cannot detect one of the size that suffices (Category: Confounding / Reverse Causality; builds on stage-3 "pre-existing contestation")
- **Paper's best version (contract 8):** if a market factor drove BR, nearby speeches would have similar BR. They do not, so no such factor exists (pp. 23-24).
- **Mechanism:** a slow-moving factor, such as open debate about the framework, a weak labor market, or a period of policy experimentation, raises both the chance that the Chair is invited to (and accepts) framework-oriented talks and the speech-day drift in implied volatility. Because the factor is slow, months of lead time in drafting (pp. 21-22) do not break the link.
- **Grounding (paper):** By the paper's own ITCV, a confounder needs only r = 0.12 with BR and with the DV (p. 24). A factor with r = 0.12 explains 1.4 percent of BR's variance. That cannot change the average BR gap between nearby speeches in any detectable way, so the 40-pair test has essentially no power against a confounder of the size the ITCV says is enough. The 0.21 gap also lacks a benchmark. Two independent draws from a distribution with SD 0.22 (Table 1) differ on average by about 0.22 (exponential-shaped) to 0.25 (normal). Under normality, 0.21 implies a within-pair BR correlation of about 0.28. So the figure is consistent with independence and with moderate co-movement alike. It is a mean over 40 pairs with no interval (p. 23). (paper + judgment; the arithmetic is mine, from Table 1 SD 0.22 and the printed 0.21)
- **Grounding (paper):** BR already correlates with slow macro variables above the 0.12 threshold: unemployment 0.26, dissent president 0.16 (Table 1). The controls cover only these observed slow variables. Separately, the placebo shows that BR predicts the pre-speech VIX change (beta = .041, p = .017, p. 25).
- **Interference ruled out as the source of the placebo (calibration):** could a neighboring speech's own t0 effect spill into this speech's pre-window? Only about 80 of 339 speeches have a neighbor within three days (40 pairs, p. 23). With an implied within-pair correlation of 0.28, spillover could account for about 0.28 x 0.036 x 80/339, roughly 0.002, against the observed 0.041. Interference cannot explain the placebo, which leaves the common-cause reading from stage 3 standing. (judgment, arithmetic from paper numbers)
- **Additional evidence:** none searched. The point is internal to the paper's numbers.
- **Magnitude calibration:** Full effect possible. The DV is noisy (SD 0.06) and the effect per SD of BR is about 0.008, so a confounder at the ITCV threshold is enough.
- **Severity:** Weakens a claim. This is not an auto-severity pattern: the defense is underpowered rather than econometrically wrong.
- **Confidence:** Medium (the arithmetic is firm; whether such a factor exists is judgment).
- **Tag:** paper + judgment.
- **Suggested test:** (i) report the pair test with its null benchmark, either by permuting BR across speeches within year or by comparing against random same-year pairs, with an interval. (ii) Regress BR on lagged slow-moving indicators (unemployment change, the prior 3-month VIX trend, the count of media articles on the Fed's mandate in the prior 60 days) and report the R-squared. (iii) Add the pre-window change ln(VIX_t-1/VIX_t-2) and the t-5 to t-1 change as controls in Model 2 and report the BR coefficient. The paper says 1-, 10-, and 30-day average changes "did not change my results" (p. 24) but gives no coefficients.

#### Alternative 1b: Speeches the market could not have read on t0 still carry the effect (Category: Mechanism Non-Operability; builds on stage-2 timing)
- **Paper's best version:** the speech is "not made public until the date and time denoted on the transcript" (p. 25), so the t-1 to t0 window captures the market's reading of it.
- **Mechanism:** the claimed channel needs the population that sets the VIX close on t0 (S&P 500 index-option traders) to have read the backing paragraphs before the close. For speeches delivered after 4 p.m. ET, on weekends, or on market holidays, that population has not been exposed to the speech when VIX_t0 is set. Any BR-DV association in those observations cannot run through the backing. It must come from something that precedes the speech and correlates with BR (stage-3 contestation, stage-2 calendar). Stage 2 raised after-close timing as misdating that attenuates or biases. I recast it as a test the mechanism must pass: the coefficient on those speeches should be zero at t0 and positive at t+1.
- **Grounding:** the Fed speech list carries dates only, no times (dgp_map Step 3, fetched 2014 list). At least one high-BR-titled speech ("A Century of U.S. Central Banking: Goals, Frameworks, Accountability," July 10, 2013) was delivered after the close (dgp_map, Investing.com, July 11, 2013). Dinner, award, and commencement speeches are among the audience types the paper describes (p. 22). The placebo shows BR predicting VIX before the speech (p. 25), which is the pattern this alternative predicts for non-exposed observations. (external + paper)
- **Additional evidence:** no new search. Kohn and Sack (2003, FEDS 2003-55, fetched in stage 2) date after-close speeches to the next business day and find no significant speech effects on financial variables. That sets a low prior for a t0 effect.
- **Magnitude calibration:** Partial effect. The size depends on the share of after-close or non-trading-day speeches, which the paper does not report. If that share is near a quarter and those speeches carry the full coefficient, about a quarter of the estimate is non-mechanism variation.
- **Severity:** Weakens a claim.
- **Confidence:** Medium.
- **Tag:** paper + external + judgment.
- **Suggested test:** code delivery time from transcripts, press advisories, or newswire time stamps. Estimate Model 2 with BR x (after-close or non-trading-day) and report the t0 coefficient for each group, plus the t0 to t+1 window for the after-close group. The mechanism predicts a zero t0 slope and a positive t+1 slope for after-close speeches.

#### Alternative 1c: Possibly non-blind, hindsight coding of a broad rule (blinding not reported) pulls famous policy speeches into BR (Category: Measurement Error, non-classical)
- **Paper's best version:** paragraph-level coding with Krippendorff's alpha 0.88 and .84 shows a reliable measure (p. 13).
- **Mechanism:** the rule codes a paragraph as backing when the Chair "reaffirms or reiterates in some way the nature and boundaries of monetary policy objectives and conventional tools" (p. 14). Coders were "familiar with economics and monetary policy" (p. 13) and coded speeches years after delivery. The FOIA request is dated 2015 (p. 13). Coders who know which speeches moved markets (for example, the August 27, 2010 Jackson Hole speech on further asset purchases, timeline.md) can read tool and policy discussion in those speeches as "boundaries of ... tools." Misclassification then correlates with the outcome. Reliability is agreement among coders who share the same hindsight, so a high alpha does not rule this out.
- **Grounding (paper):** blinding to market outcomes, the split into paragraphs, and how disagreements were resolved are all unstated (phase1 gap 10). BR correlates with speech complexity (0.42), power (0.37), and negative tone (0.27) (Table 1). That profile fits policy-dense speeches, not ceremonial restatement. (paper + judgment)
- **Additional evidence:** none searched.
- **Magnitude calibration:** Partial effect. It could be full, because the effect is about 0.8 percent of VIX per SD of BR while the DV's SD is 6 percent. A handful of well-known, market-moving, high-BR speeches can carry a slope this small. Seven high-residual speeches were also trimmed (p. 12), which changes which famous speeches remain.
- **Severity:** Weakens a claim.
- **Confidence:** Low. Hindsight coding is plausible but undocumented.
- **Tag:** paper + judgment.
- **Suggested test:** have a coder blind to dates and speaker re-code a random 20 percent of speeches with speeches presented out of order, and report agreement and the BR coefficient on the blind codes. Separately, drop the 10 or 20 speeches with the most newswire coverage on t0 and report Model 2.

#### Alternative 1d: Outcome-based trimming (Category: Compositional)
- The seven speeches dropped for studentized residuals beyond +/-3 (p. 12) are selected on the DV. Stage 2 raised this (dgp_map critical point 1), and the counts conflict (337 text vs 339 tables). Under the Selection design module this is **design-module check SO14** (sample-construction rule that conditions on the outcome). Severity is set by SO14's rule, not here. Additional framing: the trimmed speeches are the largest market reactions, which are the events the theory is about. If they sat at high BR with VIX falls, or at low BR with VIX rises, retaining them would lower the slope. The direction cannot be signed without the dropped speeches. Tag: paper + judgment. Test: report Model 2 with all 344 speeches and list the BR, date, and residual of each dropped speech.

**Categories checked and set aside for Finding 1.** Interference / SUTVA: ruled out on magnitude (see 1a). Demand / Hawthorne: the outcome is a market price set by parties unaware of the study, so no demand channel exists. The only study participants are the coders, and that concern is covered in 1c. Reverse causality, policy news, crowd-out, rule uncertainty, FOMC cycle, and venue: already in stage 3, not restated.

---

### Finding 2: Positive tone suppresses the BR effect (H2)
**Authors' mechanism:** positive emotion focuses attention on optimistic interpretations and narrows the range of expected directions (pp. 10-11).

#### Alternative 2a: Tone marks speech genre, and backing in short ceremonial remarks draws no market attention (Category: Confounding, via an omitted interaction)
- **Paper's best version:** topic and audience fixed effects and a word-count control hold speech type constant (pp. 16-17; p. 57).
- **Mechanism:** short ceremonial speeches (commencements, special occasions, swearing-in remarks) are high in LIWC positive emotion and low in length and complexity. Their backing paragraphs are boilerplate restatements of the mandate, and option traders ignore them. Long policy lectures are lower in positive emotion, and their backing paragraphs sit inside content the market reads. So the BR slope is flatter where tone is high, and BR x tone is negative without any framing effect. The fixed effects and the word-count main effect remove level differences across genres. They do not remove differences in the BR slope across genres. With measured moderators, a covariate correlated with the moderator yields an unbiased interaction only when the covariate's own interaction with the focal variable is also in the model (Yzerbyt, Muller and Judd 2004).
- **Grounding (paper):** positive tone correlates -0.41 with word count, -0.27 with complexity, -0.28 with negative tone, and 0.18 with speech location (Table 1). The paper's own backing example from a ceremonial setting is Yellen's March 5, 2014 remarks "after being sworn in" (p. 15). (paper)
- **Additional evidence (external, fetched):** Yzerbyt, Muller and Judd (2004, JESP 40: 424-431): "In general, the interaction between the two independent variables will be estimated without bias only when the interaction between the covariate and the manipulated independent variable is included in the analysis."
- **Magnitude calibration:** Partial effect, possibly most of it. With r = -0.41 between tone and word count, a BR x word-count slope of moderate size would load substantially onto BR x tone.
- **Severity:** Weakens a claim.
- **Confidence:** Medium.
- **Tag:** paper + external + judgment.
- **Suggested test:** add BR x word count, BR x complexity, BR x negative tone, and BR x topic (or BR x audience) to Model 3, and report whether BR x tone survives. Also estimate Model 3 excluding commencement and special-occasion topics.

#### Alternative 2b: The BR slope varies by period, and tone tracks period (Category: Confounding)
- See 3a. The paper itself shows that the BR slope varies over time (BR x crisis, p. 20). There is no Chair fixed effect and no BR x Chair term (Table 2 note, p. 57), and LIWC style plausibly differs by speaker. If mean tone differs across the Greenspan, Bernanke-crisis, and later periods, BR x tone partly restates BR x period. Severity: Weakens a claim (combined with 3a; one test settles both). Confidence: Low for tone specifically, because the paper reports no descriptives by Chair (phase1 gap 17). Test: report mean tone by Chair and by year, and add BR x Chair and BR x crisis to Model 5.

**Categories checked and set aside for Finding 2.** LIWC positive words as policy content: already in stage 3 (theory devil, Minor), not restated. Reverse causality: tone is fixed when the speech is drafted, and no reverse channel to the t0 VIX change exists. Interference: tone is speech-level, so no cross-unit channel exists. Compositional and Hawthorne: nothing beyond 2a.

---

### Finding 3: Business media fear amplifies the BR effect (H3)
**Authors' mechanism:** a fearful climate widens the divergence that the backing creates (pp. 11-12).

#### Alternative 3a: The fear index is mostly a proxy for the macro state and era, so BR x fear restates the crisis attenuation (Category: Measurement Error, non-classical, plus Confounding through an omitted interaction)
- **Paper's best version:** fear in business media captures the emotional climate in which traders read the speech (pp. 15-16).
- **Mechanism:** in the paper's data, measured fear is lower when unemployment is higher (r = -0.43) and higher when inflation is higher (0.30) and after rate increases (0.20) (Table 1). Unemployment peaked in 2009-2012, which is the paper's own crisis window. So a "low-fear" speech is disproportionately a crisis-era or slack-economy speech. The paper reports that the BR slope is smaller in exactly that window (BR x crisis = -0.051, p. 20). If the BR slope is lower in 2008-2012 for any reason (policy news resolving uncertainty, stage 3; a redefined backing after 2008 and 2012, timeline.md), a regression of the DV on BR x fear without BR x period recovers a positive BR x fear coefficient. No framing is needed. The odd sign of the fear-unemployment correlation suggests why. MarketPsych scores a source mix that changed a great deal over 1998-2014 and was back-scored before 2012 (setting.md; Mondo Visione 2012; Financial IT 2015). A share-of-words index can then drift with source composition rather than with sentiment. Year fixed effects absorb the drift in fear's level, but they do not absorb an interaction of BR with that drift.
- **Grounding (paper + external via stage 2):** Table 1 correlations above. BR itself correlates -0.23 with fear. The crisis interaction is on p. 20. MarketPsych source history is in setting.md and timeline.md (backfill and source expansion; dates of expansion unverified).
- **Additional evidence (external, fetched):** Yzerbyt, Muller and Judd (2004), as in 2a. The covariates correlated with the moderator (unemployment, inflation, policy direction, period) enter only as main effects (Table 2), which is the case their result covers.
- **Internal tension that favors the alternative (paper):** H3's own logic predicts a stronger BR effect in the crisis, when fear was high. The paper finds a weaker one (p. 20) and reads it as support through a different scope condition (p. 26). On this alternative, both results come from one fact: the BR slope is lower in 2008-2012, and measured fear is low then.
- **Magnitude calibration:** Partial effect, possibly full. Because the r = -0.43 with unemployment is large, BR x unemployment or BR x crisis could absorb much of BR x fear.
- **Severity:** Weakens a claim.
- **Confidence:** Medium. The correlations are firm. The source-composition explanation for the fear-unemployment sign is judgment.
- **Tag:** paper + external + judgment.
- **Suggested test:** (i) add BR x unemployment, BR x inflation, BR x crisis, and BR x Chair to Model 5, and report BR x fear. (ii) Demean fear within year, or within month, and re-estimate H3 with the within-period fear only. (iii) Plot the annual mean of the fear index and report the vendor's source counts by year.

**Categories checked and set aside for Finding 3.** Volatility scaling and the t+1 fear window (reverse feedback): in MD-4 and the stage-2 DGP map, not restated. Interference: fear is market-wide and shared by nearby speeches, which bears on inference, and the inference pack owns that. Reverse causality beyond the t+1 window: none separate from MD-4. Hawthorne: not applicable.

---

### Finding 4: The BR effect weakens in the 2008-2012 crisis and reverses among 48 high-tone, low-fear crisis speeches
**Authors' mechanism:** with taken-for-grantedness already weakened, reaffirming the backing stabilizes the institution, especially in an optimistic emotional context (pp. 19-21, 26).

#### Alternative 4a: The N = 48 subsample conditions on a descendant of the outcome, which manufactures a negative BR slope (Category: Compositional / selection)
- **Paper's best version:** splitting on tone and fear isolates the "especially optimistic configuration of emotions" the theory points to (pp. 20-21).
- **Mechanism:** the subsample keeps crisis speeches with business media fear "below the mean" (p. 21). Fear is averaged over t-1 to t+1 (p. 16), so it includes media coverage on the speech day and the day after, and it correlates with the DV (r = 0.10, Table 1). If BR raises the speech-day VIX change and a VIX rise raises fear on t0 and t+1, then fear is a common effect of BR (through the DV) and of other shocks to the DV. Keeping only low-fear days removes the high-BR speeches that were followed by VIX rises and keeps the high-BR speeches that were followed by VIX falls. That induces a negative BR-DV association inside the subsample, even if the true crisis slope is zero or positive. The reversal to -0.155 (p. 21, Figure 6) is the pattern this selection produces.
- **Auto-severity pattern: sample-construction rule that conditions on the outcome.** The fingerprint lists Selection, so this is **design-module check SO14**. Severity is set by SO14's rule. I do not set it here.
- **Additional evidence (external, fetched):** Cole et al. (2010, International Journal of Epidemiology 39: 417-420): "In both examples, conditioning on the common effect imparts an association between two otherwise independent variables; we call this selection bias."
- **Magnitude calibration:** Full effect possible for the reversal. The subsample is small (48), and Model 2 has about 58 parameters in the full sample (stage-1 Issue 12). With that few degrees of freedom, a modest selection-induced association can produce the printed coefficient.
- **Confidence:** High on the structure; the size is unknown.
- **Tag:** paper + external + judgment.
- **Suggested test:** rebuild fear over a window ending at t-1 (for example, t-5 to t-1) and redo the 48-speech split on that pre-speech measure. Report the subsample N and the number of parameters estimated. Report the same split outside the crisis as a comparison.

#### Alternative 4b: Crisis attenuation reflects a change in what BR measures and in who speaks, not weakened taken-for-grantedness (Category: Confounding)
- Stage 3 and the timeline brief already carry the policy-news and redefined-backing readings of 2008-2012. I add only the compositional point. All 2008-2012 speeches are Bernanke's, and the comparison period mixes Greenspan (1998-2005), early Bernanke, and Yellen. BR x crisis is therefore partly BR x Chair-era. With no BR x Chair term (p. 57), the paper cannot separate "weaker taken-for-grantedness" from "a different speaker whose backing paragraphs the market read differently." Severity: Minor on its own. It is the same test as 2b and 3a (add BR x Chair). Confidence: Medium. Tag: paper + judgment.

**Categories checked and set aside for Finding 4.** Interference and Hawthorne: none. Reverse causality: covered by stage 3.

---

### Summary: Findings That Most Weaken the Paper's Claims

| Rank | Alternative | Finding | Category | Magnitude | Severity | Confidence | Can Authors Address? |
|------|------------|---------|----------|-----------|----------|------------|---------------------|
| 1 | Fear index proxies macro state and era; BR x fear restates crisis attenuation (3a) | H3 (and H2 via 2b) | Measurement error / omitted interaction | Partial to full | Weakens a claim | Medium | Yes: add BR x unemployment, BR x crisis, BR x Chair; use within-year fear |
| 2 | Low-fear subsample conditions on a descendant of the outcome (4a) | Crisis reversal, N = 48 | Compositional / selection | Full possible | Set by SO14 (auto-severity pattern) | High (structure) | Yes: rebuild fear ending at t-1 and redo the split |
| 3 | Tone marks speech genre; omitted BR x length, BR x topic (2a) | H2 | Confounding (omitted interaction) | Partial, possibly most | Weakens a claim | Medium | Yes: add BR x word count, BR x complexity, BR x topic |
| 4 | Speeches unreadable at the t0 close still carry the effect (1b) | H1 | Mechanism non-operability | Partial | Weakens a claim | Medium | Yes: code delivery time; split the t0 slope; use t+1 for after-close speeches |
| 5 | Pair test and ITCV cannot detect a confounder of sufficient size (1a) | H1 | Confounding / reverse causality | Full possible | Weakens a claim | Medium | Yes: permutation benchmark; regress BR on slow indicators; pre-trend controls |
| 6 | Possibly non-blind hindsight coding of a broad rule; blinding not reported (1c) | H1 | Measurement error (non-classical) | Partial | Weakens a claim | Low | Yes: blind re-coding of a random subsample; drop the most-covered speeches |
| 7 | Outcome-based trimming of seven speeches (1d) | H1-H3 | Compositional / selection | Unsigned | Set by SO14 | High (structure) | Yes: report N = 344 results and list the dropped speeches |
| 8 | Crisis attenuation is partly BR x Chair-era (4b) | Crisis heterogeneity | Confounding | Partial | Minor | Medium | Yes: add BR x Chair |

Fact versus inference (contract 7): every correlation, coefficient, and quote above comes from Table 1, Table 2 (extracted CSVs), or the cited page. The benchmark for the pair test (0.22-0.25), the implied within-pair correlation (about 0.28), and the spillover bound (about 0.002) are my arithmetic on those numbers. Each causal story is a judgment. I do not predict the result of any requested test (contract 11).

### Sources fetched this run
- Yzerbyt, V. Y., Muller, D., and Judd, C. M. (2004). "Adjusting researchers' approach to adjustment: On the use of covariates when testing interactions." Journal of Experimental Social Psychology 40: 424-431. https://perso.uclouvain.be/vincent.yzerbyt/Yzerbyt%20et%20al.%20JESP%202004.pdf. Quote: "In general, the interaction between the two independent variables will be estimated without bias only when the interaction between the covariate and the manipulated independent variable is included in the analysis."
- Cole, S. R., Platt, R. W., Schisterman, E. F., Chu, H., Westreich, D., Richardson, D., and Poole, C. (2010). "Illustrating bias due to conditioning on a collider." International Journal of Epidemiology 39: 417-420. https://ibg.colorado.edu/cdrom2024/5.2.causality_DaveEvans/Coleetal2010_Colliderbias.pdf. Quote: "In both examples, conditioning on the common effect imparts an association between two otherwise independent variables; we call this selection bias."
- Searched, not used: Elwert and Winship (2014), Annual Review of Sociology 40: 31-53. The citation exists, but the full text could not be fetched, so I make no claim from it.
- Relied on from earlier stages (fetched there, not re-fetched): Kohn and Sack (2003, FEDS 2003-55); the Fed 2014 speech list and the Investing.com report of July 11, 2013 (dgp_map.md); the MarketPsych releases of 2012 and 2015 (setting.md).
