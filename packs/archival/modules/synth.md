# Design module: synthetic control (SC)

Scope. This module applies when the `Designs:` line lists SC: the paper builds the counterfactual for one or a few treated units as a weighted combination of untreated units, fitted on pre-treatment outcomes or predictors. It covers augmented and demeaned SC, synthetic DiD (SDID), generalized synthetic control, matrix completion, and staggered SC. It does not apply to synthetic data, synthetic products, or control variables. A synthetic control appended to a DiD paper as a robustness check loads this module with role secondary.

Before starting, note: the number of treated units; the number of donors J and of pre-periods T0; the estimator's name as the paper gives it and whether its weights can be negative or include an intercept; and the inference the paper reports.

## Protocol

### SC1. Pre-treatment fit reported as a number

Look for the pre-period RMSPE or mean gap on the outcome's scale, and a predictor balance table with the treated unit, its synthetic control, and the donor average (Abadie 2021, the reunification application as template). Compare the text's description of the fit ("excellent", "close") with the numbers and the figure. A gap visibly a large share of the claimed effect, described as a close fit, is a finding. Do not apply a numeric cutoff for good fit; none is accepted.

### SC2. Pre-periods, donors, and noise

A short pre-period with many donors and a volatile outcome can produce a close fit by over-fitting, without matching the unobserved factors (Abadie 2021, section 3.3). The paper should report T0, J, and the outcome's volatility, and should not offer a near-perfect fit from few pre-periods and many donors as proof of validity.

### SC3. The donor pool rule

The pool should follow a stated rule that excludes units treated by the same or a similar intervention and units hit by large idiosyncratic shocks, while keeping units that share the treated unit's regional or common shocks (Abadie 2021, section 5). "All other firms in the industry", including firms that adopted the same practice, fails. Use `{WORKSPACE}/stage-2/dgp_map.md` for donor-specific shocks when it exists.

### SC4. Spillovers and anticipation

When donors are competitors, suppliers, or firms in the same market, they may respond to the treatment. The paper should address this and state the direction of the resulting bias. Flag a donor pool made of the rivals the paper elsewhere says responded. When the treatment was announced or expected before its date, the paper should backdate the intervention.

### SC5. Weights, their meaning, and the convex hull

Donor weights should be reported. Concentration or dispersion is not by itself a flaw: Abadie (2021) values sparse weights for interpretability, augmented SC "allows negative weights on some donor units" (Ben-Michael, Feller, and Rothstein 2021), and SDID weights are by design less sparse than SC weights (Arkhangelsky et al. 2021). Ask instead that the paper discuss what its weights mean for the counterfactual: when one donor carries most of the weight, whether that donor had its own shock (leave-one-out, SC7). Check the convex hull condition: a treated unit more extreme than every donor on a key predictor has no credible synthetic control, and the paper should use an estimator built for that case.

### SC6. Predictors

The predictor set should be stated and justified and measured before treatment. When every pre-period outcome enters as a separate predictor, the other covariates become irrelevant to the weights (Kaul, Klossner, Pfeifer, and Schieler 2022), so a claim that covariate balance matters is inconsistent with that specification. Balance on pre-period outcomes does not imply balance on covariates (Botosaru and Ferman 2019).

### SC7. Specification choices shown

Ordinary SC leaves real room for specification search (Ferman, Pinto, and Possebom 2020). The paper should show alternative predictor sets and leave-one-out donor results and say how the reported specification was chosen. A leave-one-out result that flips the sign, dismissed in a sentence, is a finding.

### SC8. Permutation inference

Check four things. Placebos run over the full donor pool, or a stated rule for discarding poor-fit placebos. The statistic is fit-adjusted (for example the post/pre RMSPE ratio), or the paper states a rule for discarding poorly fitting placebos. With one treated unit and in-space permutation, the p-value is no smaller than 1/(J+1), where J is the number of placebos the paper says it kept, or the donor count when it states none; never reconstruct a count from a discard rule. With N treated units permuted as a set, the floor is 1/C(J+N, N) (Abadie 2021; Firpo and Possebom 2018). For conformal inference (Chernozhukov, Wuthrich, and Zhu 2021), the floor depends on the number of time permutations, not J; skip the floor check. The p-value is not described as a sampling-based test when assignment was not random (Abadie 2021, section 3.5).

Do the arithmetic. Compute the floor, and when the paper reports the treated unit's rank among placebos, compute rank/(J+1) (rank/C(J+N, N) with N treated units permuted as a set). When the floor 1/(J+1) equals the claimed level (for example J = 19 and a claim of p < 0.05), the paper cannot reach that level strictly, so flag it the same way as a floor above the claimed level.

Severity. "Undermines the main claim" when the floor (1/(J+1), or 1/C(J+N, N) with N treated units permuted as a set), or the p-value implied by the reported rank, is above the significance level the main claim uses, and the main claim rests on that significance. A reported p-value below the floor while the floor still clears the claimed level is "Minor".

### SC9. In-time placebo

Look for a backdating placebo or a hold-out validation period, placed far enough before the true date to avoid anticipation. A placebo date one year before a treatment that was announced two years ahead is a finding.

### SC10. Imperfect fit and the estimator's name

With imperfect pre-treatment fit, SC is generally biased when assignment correlates with unobserved confounders (Ferman and Pinto 2021). The paper should use and name an estimator built for that case (augmented, demeaned, or intercept-shifted SC, or SDID) and show its estimate beside SC and DiD. Flag weights that can be negative, or an intercept, under the name "synthetic control", and a visibly offset pre-period fit described as matching.

### SC11. Synthetic DiD

The paper should report SDID's unit and time weights and regularization, and its variance estimator should fit the number of treated units: the jackknife is undefined with one treated unit, the bootstrap and jackknife are built for many treated units, and the placebo method assumes homoskedasticity across units (Arkhangelsky et al. 2021).

### SC12. Several treated units and staggered adoption

With several treated units or cohorts, the paper should state how it pools and aggregates and show fit for each treated unit or cohort as well as for the average (Ben-Michael, Feller, and Rothstein 2022). An average fit that hides poor unit-level fit is a finding.

### SC13. Generalized SC and matrix completion

The paper should report the number of factors or the regularization parameter, how it was chosen, the pre-periods available per treated unit, and how uncertainty was computed (Xu 2017; Athey et al. 2021). "Default settings" with no factor count is a finding; a stated factor count whose selection is not described is "Minor".

### SC15. Effect size against volatility, and generalization

Judge the effect against the outcome's volatility and the spread of placebo gaps (Abadie 2021, section 5). An effect no larger than the range of placebo gaps is a finding. Conclusions from one or a few treated units should not be generalized to firms or industries at large.

## Severity

- Undermines the main claim, only on the design the headline rests on: SC8 in the case stated there.
- Minor: SC8 when the reported p-value is below the floor but the floor still clears the claimed level; SC13 when the factor count is stated but its selection is not.
- Everything else: at most Weakens a claim.

## Hand-offs

- Inference for SC-family estimators (permutation, conformal, SDID variance) is this module's; cluster-robust standard errors are not the inference method for one or few treated units, and the inference overlay skips SC estimates when SC is listed.
