# Design module: difference-in-differences (DiD)

Scope. This module applies when the `Designs:` line lists DiD: the paper compares the change in an outcome for units that receive a treatment with the change for units that do not, over periods before and after the treatment, including event-study regressions with leads and lags and designs where units adopt at different times. It does not apply to cumulative abnormal returns around an announcement (the market-event pack), to randomized experiments (the experiments pack), or to a cross-sectional regression with fixed effects and no before-after comparison.

Before starting, note three facts from the paper, since several checks turn on them: whether adoption timing varies across units (staggered) or all treated units adopt at one date; which estimator produces the headline number; and whether the paper has units that are never treated within the panel.

## Protocol

### DD1. Staggered timing and two-way fixed effects

Applies only when adoption timing varies. With one adoption date, TWFE is the 2x2 estimator; write "DD1: one adoption date" under "Checked and fine" and move on.

With staggered timing, the TWFE coefficient averages all 2x2 comparisons, including ones that use already-treated units as controls, and with effects that change over time those comparisons can carry the wrong sign (Goodman-Bacon 2021; de Chaisemartin and D'Haultfoeuille 2020). DD1 passes in any of three ways:

1. The headline estimate comes from a heterogeneity-robust estimator. Accept: Callaway and Sant'Anna (2021); Sun and Abraham (2021); the Borusyak, Jaravel and Spiess (2024) imputation estimator and Gardner's two-stage estimator; de Chaisemartin and D'Haultfoeuille (`did_multiplegt`, `did_multiplegt_dyn`); Wooldridge's extended TWFE with cohort-by-period interactions (`jwdid`, `etwfe`), which is a TWFE regression but a robust one; stacked DiD with clean controls; synthetic DiD. Name Wooldridge's and the stacked estimators without a citation.
2. The paper shows a Goodman-Bacon decomposition or negative-weight diagnostics indicating the TWFE estimate is not driven by forbidden comparisons.
3. A heterogeneity-robust estimate reported anywhere in the paper (a robustness table, an appendix) agrees with the headline in sign and is of similar size.

Search the robustness section, appendices, and table notes before concluding no robust estimate exists, and name where you looked. When the paper has no robust estimate and no diagnostics, the finding is "Weakens a claim": say what the paper should report, and do not predict what it would show.

### DD2. The robust estimator's choices fit the sample

A named package run with its defaults passes. An unstated choice (control group, base period, anticipation window, covariates, aggregation weights) is "Minor". A stated choice that contradicts the sample is "Weakens a claim": "never-treated" controls when every unit adopts within the panel; Sun and Abraham with no never-treated or last-treated cohort; a not-yet-treated control group in a paper that also says units anticipate adoption without an anticipation window (for example Callaway and Sant'Anna `anticipation = k`). For the imputation and two-stage estimators, the second-stage standard errors must account for the first stage; plain OLS standard errors from the second stage do not.

### DD3. A clean comparison group

Check the cohort or timing table against the text. Units called never-treated must be untreated for the whole panel; a cohort that adopts in the panel's last year is not-yet-treated, not never-treated. Controls should not respond before their own adoption, be treated by spillovers from treated units, or be treated by events the treatment coding missed (a census of treatment events drawn from a subset of sources leaves covertly treated controls).

Matched comparison groups. When the paper matches treated and control units on pre-period outcome levels before running the DiD, ask whether it defends against regression to the mean. Daw and Hatfield (2018) show by simulation that when pre-period outcome levels are correlated with assignment, an unmatched DiD is unbiased but matching on those levels produces biased estimates. Flag a matched DiD on pre-period outcomes only when the paper neither argues why regression to the mean does not arise nor shows the unmatched estimate. At most "Weakens a claim".

### DD4. Event-study specification

Read every event-study figure and its note. Check: the reference period is stated (an anticipated period used as the reference is a problem); distant leads and lags are binned or the window restricted, and the paper says how; the window is balanced, or the paper reports that units change across event time (a late cohort has fewer post periods than the window shows). When adoption is staggered, the leads and lags should come from an estimator that does not mix effects across relative periods (Sun and Abraham 2021); a TWFE event study with staggered adoption fails that clause. With one adoption date that clause does not apply. An unstated reference period alone is "Minor".

### DD5. Pre-period evidence read with limited power

Wording. Flag language that treats a pre-trend test as proof: "the joint test (p = 0.31) confirms the identifying assumption", "parallel trends hold", or a drift dismissed because single leads are insignificant. Pre-trend tests can have low power against violations large enough to matter, and conditioning on passing them distorts the estimate (Roth 2022). Flag any sample, control, or specification choice the paper made because of a pre-test result. A power analysis of the pre-test, as Roth (2022) proposes, counts toward passing.

Figures. Extract coefficients only from an event study with a common reference period, stated or visible. For a Callaway and Sant'Anna plot with a varying base period (pre-period points are period-to-period changes), or a Borusyak, Jaravel and Spiess pre-trend plot (estimated separately on untreated observations), say the straight-line reading does not apply and why, then check the wording only.

For an event study with a common reference period, write a table of the approximate coefficient at each event time, read from a table where one exists, otherwise from the figure:

```
| Event time | Approx. coefficient | Source (table or figure) |
```

Fit a line through the pre-period event-study coefficients, excluding the normalized reference period, and extrapolate it into the post period. Report the slope, the extrapolated post-period values, and the actual post-period estimates, and say whether the post-period estimates exceed, match, or fall below the extrapolation.

Severity. "Undermines the main claim" only when all of these hold for the design the headline rests on: at least four pre-period coefficients (a conservative gate set by this pack, not a rule from the literature), read from a table or a clearly legible figure; a common reference period; monotone drift in the direction of the claimed effect; post-period estimates within the linear extrapolation of the pre-period trend (each post-period point estimate is no larger in magnitude, in the direction of the claimed effect, than the extrapolated line's value at that event time); and no DD6 analysis that allows a linear trend (for example Rambachan and Roth smoothness bounds) and still excludes zero. Every other DD5 finding is at most "Weakens a claim".

### DD6. Sensitivity to violations of parallel trends

Look for bounds on the post-period violation tied to the pre-period (Rambachan and Roth 2023; HonestDiD), with a breakdown value, and for a statement of the conclusion at a violation the paper argues is plausible. The recommended workflow in Roth, Sant'Anna, Bilinski and Poe (2023) includes such sensitivity analysis.

Flag two misuses. The first is results reported only at Mbar = 0, which is exact parallel trends, or only at M = 0 under smoothness restrictions, which allows only an exact linear extrapolation of the pre-trend. Either way no breakdown value is shown. The second is HonestDiD run on a Callaway and Sant'Anna event study that states a varying base period (the HonestDiD wrapper for that estimator requires a universal base period).

Severity. When no sensitivity analysis is reported and DD5 found no drift, "Minor". When DD5 found drift, "Weakens a claim".

### DD7. Anticipation and the treatment date

Find both the announcement date and the effective date of the treatment in the paper, or in `{WORKSPACE}/stage-2/timeline.md` and `dgp_map.md` when they exist. When units could respond before the effective date (a law announced two years ahead, an acquisition announced before closing), the paper should date treatment at the announcement or use an estimator with an anticipation window, and nonzero leads just before the effective date should not be read as a pre-trend or as noise.

### DD8. The outcome's scale

Parallel trends is generally not invariant to the outcome's scale (Roth and Sant'Anna 2023). When treated and control units differ greatly in size, or the outcome is log(1+y) with many zeros, the paper should justify the scale and show whether the conclusion holds on the other plausible scale. A statement that results on the other scale are "weaker and omitted" or "available on request" is a finding.

### DD9. Continuous or multi-valued treatment

With a dose or intensity interacted with Post, comparisons across doses carry selection bias that ordinary parallel trends does not rule out (Callaway, Goodman-Bacon and Sant'Anna, working paper). Flag a slope in dose read as the effect of one more unit of treatment without a stronger assumption, and say whether units with zero dose exist.

### DD10. Treatment that switches off

Look for reversals in the treatment timeline or data description (programs dropped, laws repealed, practices abandoned). When they exist, the paper must say so, state its estimand (first adoption, current status, or exposure length), and use an estimator that allows switching (de Chaisemartin and D'Haultfoeuille 2020; 2024). An ever-treated dummy read as the effect of adoption fails.

### DD11. Covariates in the DiD

Flag a covariate only when the paper's own theory, text, or results imply the treatment moves it (for example current-year headcount when the paper says the law raised headcount). Firm age, founding year, and other traits the treatment cannot move never qualify. Report each such covariate once, here, not under methods-checks CHECK 3.

Adding covariates to a staggered TWFE regression in the belief that they fix the timing problem is a second clause (Sant'Anna and Zhao 2020 on conditional parallel trends). On its own it is "Minor"; when DD1 fires, fold it into the DD1 issue.

### DD12. Triple differences

A triple difference needs its own identifying assumption about the third dimension (Olden and Moen 2022). Check that the paper states what the third comparison identifies, that the third-dimension comparison group is not itself treated or affected by spillovers (an untreated industry that supplies or substitutes for the treated one), and that every lower-order interaction is in the model: Moderator x Treated and Moderator x Post as well as the triple term.

### DD14. Treatment defined and dated from implementation

Flag treatment defined by an event the outcome or the expected outcome could cause, including adoption timed by units' own shocks (units adopt after a bad year); treatment dated from a text mention or a press date instead of an implementation record; and treated status inferred from incomplete records, so some controls are covertly treated. Misclassification and mis-dating bias the standard estimators.

### DD15. Few treated units (only when the inference overlay does not run)

If `run.json` `overlays` lists `inference`, skip this check; that pack owns it. Otherwise: with one or a few treated units or clusters, or an outcome that persists over time, the paper should report the number of treated clusters and use inference that fits that design (Bertrand, Duflo and Mullainathan 2004 on serial correlation). Flag the absence of the treated-cluster count only after searching the tables and notes.

## Severity

- Undermines the main claim, only on the design the headline rests on: DD1, when a heterogeneity-robust estimate reported in the paper has the opposite sign from the headline TWFE estimate, or is materially smaller and not significant at the 10 percent level while the headline claims 5 percent or better, and the headline still uses the TWFE number; DD5, in the case stated there.
- Minor: DD2 when a named package's default is unstated; DD4 when only the reference period is unstated; DD6 when no sensitivity analysis is reported and DD5 found no drift; DD11's second clause when DD1 does not fire.
- Everything else: at most Weakens a claim.

## Hand-offs

- The clustering level stays with methods-checks CHECK 5 and CHECK 7b, or with the inference overlay (I1) when it runs. Cluster counts and few-treated-cluster inference belong to the inference overlay when it runs, and to DD15 when it does not.
- The straight-line reading of event-study plots is this module's (DD5); the triangulation agent skips it when DiD is listed.
- Covariates in a DiD regression are reported here (DD11), not under methods-checks CHECK 3.
