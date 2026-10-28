# Design module: regression discontinuity (RD)

Scope. This module applies when the `Designs:` line lists RD: treatment changes discontinuously when a score, count, vote share, distance, or date crosses a cutoff, and the paper estimates the effect from units near the cutoff. It covers sharp, fuzzy, geographic, multi-cutoff, close-vote, and RD-in-time designs. It does not apply to a threshold used only to split a sample for an ordinary regression. Kink designs are out of scope for this version.

Before starting, note: the running variable and whether it is continuous or takes few values near the cutoff; sharp or fuzzy; the estimator, bandwidth, and inference the headline uses; and whether the setting lets units manipulate the running variable (firm size near a regulatory threshold, vote counts in a small meeting).

## Protocol

### RD1. Estimation and inference

Pass when the paper does one of three things: (a) local polynomial estimation with a named bandwidth selector and robust bias-corrected inference reported beside or instead of conventional inference (Calonico, Cattaneo, and Titiunik 2014, Econometrica 82(6)), saying whether the bandwidth targets mean squared error or coverage error (Calonico, Cattaneo, and Farrell 2020 on coverage-error-optimal bandwidths); (b) a local randomization analysis with a stated window-selection rule; (c) bias-aware (honest) intervals with a stated smoothness bound. A fixed window chosen by convention, with no selector named and conventional intervals only, fails. So does `rdrobust` output where only the conventional row is reported.

### RD2. Local, not global, polynomials

The polynomial should be local linear or local quadratic near the cutoff. Global cubic or higher-order polynomials give noisy estimates, sensitivity to the degree, and poor coverage (Gelman and Imbens 2019). "Undermines the main claim" when the headline comes from a global polynomial of order three or higher and the paper's own local linear estimate is not significant or has the opposite sign. Otherwise at most "Weakens a claim".

### RD3. Manipulation of the running variable

Look for a density test suited to the running variable (McCrary 2008; the local polynomial density test of Cattaneo, Jansson, and Ma 2020, `rddensity`), with its result. Flag an absent test where units could plausibly sort, and a failed or marginal test described as showing no manipulation. "Undermines the main claim" when the paper's own density test rejects at 5 percent on the design the headline rests on and the paper does not address it.

### RD4. Close votes

For shareholder proposals, say-on-pay, or director elections decided near 50 percent, Bach and Metzger (2019) document a discontinuous drop in the density of vote results at 50 percent and a management advantage in close votes. The paper should show its own density and covariate-balance evidence at 50 percent and engage with that finding before treating passage as as good as random. Close-vote RD is not banned: other electoral settings show no such pattern (Eggers et al. 2015). "Undermines the main claim" when, on the design the headline rests on, either the paper's own density test rejects, or bin counts from the paper's own table or figure on each side of the threshold show the drop, and the paper does not address it. State the test result or the bin counts in the finding.

### RD5. Covariate balance at the cutoff

Balance should be tested with the same RD estimator and inference as the outcome, using either the outcome's bandwidth or the same selector applied to each covariate, for pre-treatment covariates that matter in the setting (Calonico, Cattaneo, Farrell, and Titiunik 2019 on covariates in RD). Compare the windows across tables: a balance table in a fixed plus or minus 40 window, not chosen by a bandwidth selector, beside an outcome estimated in plus or minus 15 fails. When covariates enter the main model, the estimate without them should also appear.

### RD6. Robustness across bandwidths and specifications

Look for results at, for example, half and double the chosen bandwidth, with more than one kernel and polynomial order, and a donut specification when heaping or bunching near the cutoff is plausible (Barreca, Lindo, and Waddell 2016 on heaping). "Results are robust" with one bandwidth shown is a finding. A sign flip across the reported bandwidths described as robust is a finding. Bandwidth, kernel, and polynomial variants are robustness of one test and stay with RD6. Several RD outcomes offered for one claim are a family for the inference overlay (I11) when it runs, and for methods-checks CHECK 7 otherwise.

### RD7. Placebo cutoffs

Placebo cutoffs should be estimated with the same estimator, on each side of the true cutoff, in windows that exclude it. Jumps at placebo cutoffs comparable in size to the main estimate, described as "generally insignificant", are a finding. "Placebo tests found no effect" with no table is a finding.

### RD8. Discrete or heaped running variables

When the running variable takes few values near the cutoff (employee counts, integer scores, ratings, vote counts), the paper should report the mass points near the cutoff and any digit preference. Clustering standard errors on the running variable is not a fix: Kolesar and Rothe (2018) show such intervals "do not guard against model misspecification" and have poor coverage, and recommend against them. Flag a paper that offers that clustering as its answer to discreteness. Clustering on the running variable for another stated reason is not by itself a finding. The alternatives are the intervals Kolesar and Rothe propose or a local randomization analysis, both accepted under RD1.

### RD9. Fuzzy RD

When compliance at the cutoff is imperfect, the paper should show the first stage (the jump in treatment probability) at the cutoff with its size and strength, discuss the exclusion restriction (the cutoff affects the outcome only through treatment), and interpret the estimate as an effect for compliers at the cutoff (Hahn, Todd, and Van der Klaauw 2001). A small first-stage jump beside a very large 2SLS estimate is a finding.

### RD10. The estimand is local

An RD estimate applies to units at the cutoff, and to compliers in a fuzzy design. Flag an abstract, discussion, or conclusion that generalizes to all firms, all governance changes, or the economy. Extrapolation beyond the cutoff needs an explicit method with its assumption (Cattaneo, Keele, Titiunik, and Vazquez-Bare 2021; Angrist and Rokkanen 2015).

### RD11. Predetermined traits of close-race winners

When the treatment is a predetermined trait of a person who won a close race (a director's or executive's gender, background, or experience), conditioning on a bare win selects on other attributes that compensated for the trait (Marshall 2024). The paper should address this before reading the jump as the effect of the trait.

### RD12. Several cutoffs

When the running variable is normalized across several cutoffs (thresholds that differ by industry, year, or program), the paper should report cutoff-specific estimates and describe the pooled estimate as a weighted average of them (Cattaneo, Keele, Titiunik, and Vazquez-Bare 2016). Cutoff-specific estimates in an appendix that the text never discusses are "Minor".

### RD13. Geographic boundaries

A geographic RD has a two-dimensional running variable (Keele and Titiunik 2015). The paper should report balance and estimates along boundary segments and check whether the boundary also marks tax, regulatory, or labor-market differences. One segment driving the result, unreported, is a finding.

### RD14. RD in time

When the running variable is calendar time, the design often lacks cross-sectional variation and uses observations far from the cutoff, and time-series properties matter (Hausman and Rapson 2018). The paper should justify time as the running variable, handle autocorrelation and trends, show results in a narrow window, and check for other events at the cutoff date. With a wide window, judge the design as an event study and say so.

### RD16. The RD plot

The plot should show binned means with a data-driven bin choice and local fits (Calonico, Cattaneo, and Titiunik 2015). Compare the visible jump with the reported estimate: a plot with no visible jump beside a large significant estimate, or a jump of the opposite sign, is a finding. Bin choice alone is "Minor".

### RD17. Effective observations

The number of observations within the bandwidth on each side determines precision. Look for it in the tables and notes; compute it from a frequency table when the paper gives one. Flag a table that reports only the full N. A result significant only near the 5 percent line, at one bandwidth, with few effective observations, should be presented as fragile (Stommes, Aronow, and Savje 2023 on power in published RD).

## Severity

- Undermines the main claim, only on the design the headline rests on: RD2 and RD3 and RD4 in the cases stated there.
- Minor: RD16 bin choice alone; RD12 when cutoff-specific estimates exist in an appendix but are not discussed.
- Everything else: at most Weakens a claim.

## Hand-offs

- RD inference (RD1) and clustering on the running variable (RD8) are this module's; the inference overlay skips clustering on the running variable.
- Bandwidth, kernel, and polynomial variants are robustness of one test and stay with RD6. Several RD outcomes offered for one claim are a family for the inference overlay (I11) when it runs, and for methods-checks CHECK 7 otherwise.
- The triangulation agent does not ask for a density test when RD is listed; RD3 owns it.
