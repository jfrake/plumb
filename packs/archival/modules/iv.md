# Design module: instrumental variables (IV)

Scope. This module applies when the `Designs:` line lists IV: the paper estimates the effect of an endogenous variable using a variable (an instrument) that shifts it, by two-stage least squares, LIML, GMM, or a control function with an excluded instrument. It covers judge and examiner designs, shift-share instruments, lagged and peer-average instruments, and dynamic panel GMM. A Heckman selection model or inverse Mills ratio belongs to the Selection module, not here.

Encouragement designs. The experiments pack reads this file when the `Designs:` line lists `IV (encouragement)`: a randomized offer, invitation, or encouragement instruments uptake. That pack runs only IV1, IV2, IV3, IV4, IV5 (the channel argument only: assignment affecting outcomes other than through uptake), IV9, and IV11, under its own severity rules. The design-checks agent does not run this module for `IV (encouragement)`.

Before starting, note for each instrumented estimate a hypothesis rests on: the number of instruments and endogenous regressors; the error structure (iid, robust, clustered); the first-stage statistic reported and the software that produced it; and whether the headline claim rests on the 2SLS estimate being significant.

## Protocol

### IV1. First-stage strength with a statistic that fits

Classify each reported first-stage statistic before judging it. Software labels:
- fixest: `ivf` reports "the Cragg-Donald F statistic in the presence of only one endogenous regressor", which is not robust even when the model's standard errors are clustered; `ivwald` uses the model's variance matrix and "is equivalent to the Kleibergen-Paap statistic" with one endogenous regressor. A fixest table's "F-test (1st stage)" under clustered errors is usually `ivf`, the non-robust statistic.
- ivreg2 and ivreghdfe print the Kleibergen-Paap rk Wald F as the robust weak-identification statistic, beside "the Stock-Yogo critical values for the Cragg-Donald i.i.d. case".
- ivreg2's Kleibergen-Paap F carries a cluster small-sample adjustment, so a small gap between a paper's Kleibergen-Paap F and an effective F computed with `weakivtest` is not an error.

The rule. With one instrument and one endogenous regressor, the robust F, the Kleibergen-Paap Wald F, and the effective F are the same statistic, and comparing it with the Stock-Yogo size critical values (16.38 for 10 percent maximal size of a 5 percent test) or with the Montiel Olea-Pflueger critical value is correct. Flag only (a) a Cragg-Donald or other non-robust F offered under robust or clustered errors, and (b) with several instruments, a Kleibergen-Paap or robust F compared with Stock-Yogo values in place of the effective F (Montiel Olea and Pflueger 2013; Andrews, Stock, and Sun 2019). No first-stage statistic for an estimate a hypothesis rests on is also a finding.

When a paper says its F "passes" a Stock-Yogo value, report which value it names and whether that value applies to the statistic it reports. A non-robust F under robust or clustered errors does not qualify, whatever value it clears. Do not supply critical values from memory other than the 16.38 above.

### IV2. Inference robust to weak instruments

Where first-stage strength is not clearly strong, the estimates hypotheses rest on should also get inference that stays valid with weak instruments: Anderson-Rubin, conditional likelihood ratio, or tF intervals (Andrews, Stock, and Sun 2019; Lee, McCrary, Moreira, and Porter 2022). Andrews, Stock, and Sun recommend Anderson-Rubin intervals with a single instrument whatever the first-stage F.

Severity with IV1. "Undermines the main claim" when, for the estimate the headline rests on, the paper reports no first-stage statistic; or the statistic that fits its error structure (robust F with one instrument, effective F with several) is below 10; or only a non-robust F is reported and it is below 10; and in each case the paper reports no Anderson-Rubin, conditional likelihood ratio, or tF interval, and the headline claim rests on the 2SLS estimate being significant. The basis: in Andrews, Stock, and Sun's simulations calibrated to published AER specifications (Section 5.4), a procedure that uses a t-test when the effective F exceeds 10 and an Anderson-Rubin test otherwise kept size near nominal; a paper below 10 with only t-based inference has left that procedure. Above 10, a missing robust interval is at most "Weakens a claim". When the first stage is clearly strong, a missing Anderson-Rubin interval is at most "Minor". Do not state a general rule that an F above 10 is adequate, and do not use a recalled tF critical value.

### IV3. Several endogenous regressors

When an endogenous variable and its interaction with a moderator are both instrumented, or several endogenous variables enter, one joint first-stage statistic is not enough: each endogenous regressor needs a conditional first-stage statistic (Sanderson and Windmeijer 2016).

### IV4. First stage and reduced form

Both the first stage and the reduced form (outcome on instrument) should be reported, with signs and sizes that fit the paper's account of how the instrument works. A missing reduced form, or a first-stage sign that contradicts the mechanism the exclusion argument relies on, is a finding.

Forbidden regression. Flag fitted values from a nonlinear first stage (probit or logit) substituted for the endogenous regressor in an OLS second stage. Using those fitted values as an excluded instrument in 2SLS is valid and is not a finding. Also flag a hand-run two-step 2SLS whose second-stage standard errors ignore the first step. At most "Weakens a claim".

### IV5. The exclusion restriction

The paper should name the channels through which the instrument could affect the outcome other than through the treatment and argue each one, and report at least one falsification test the argument implies: a placebo outcome, a sample where the first stage is zero, or a pre-period outcome (Conley, Hansen, and Rossi 2012 on plausibly exogenous instruments). A single sentence that the instrument is "determined outside the firm" is a finding. An exclusion argument cannot be proved; ask for the channel argument and the test, not certainty.

### IV6. Sensitivity to a direct effect

For an instrument with a plausible direct channel to the outcome, the paper should report how large a direct effect would overturn the result, or bounds that allow one (Conley, Hansen, and Rossi 2012).

### IV7. Overidentification tests

A passed Hansen or Sargan test is not proof that the instruments are valid: it has power only against violations that differ across instruments (Parente and Santos Silva 2012), and under heterogeneous effects a rejection may reflect different local effects. Flag "the Hansen J test confirms that our instruments are valid" and a p-value near 1 with many instruments offered as reassurance.

### IV8. IV far from OLS

When the IV estimate differs from OLS by a large factor, compute the ratio and ask whether the paper explains it with a specific argument: measurement error (with a reason to expect it), complier effects, weak-instrument bias, or a possible exclusion violation. Reading the gap as proof that OLS was biased is a finding (Semadeni, Withers, and Certo 2014; Young 2022).

### IV9. Compliers

The estimate is a local average treatment effect for compliers (Imbens and Angrist 1994). The paper should describe who the compliers are and state the effect for them, not for all units. Flag an abstract or conclusion that generalizes to firms in general.

### IV11. Monotonicity

Monotonicity should be stated and defended, including when several instruments are pooled (Mogstad, Torgovitsky, and Walters 2021) or several treatment categories are instrumented. Opposite-signed first stages for different types of units, with the text asserting monotonicity, is a finding.

### IV12. Judge, examiner, and agent-assignment designs

When the instrument is an agent's decision rate (a judge's, examiner's, loan officer's, or reviewer's leniency), check that the leniency measure leaves out the focal case; that the paper shows quasi-random assignment within the assignment stratum (balance of case traits on the instrument within the stratum); that first-stage strength is reported; and that the paper reports or discusses tests of exclusion and monotonicity (Frandsen, Lefgren, and Leslie 2023).

### IV13. Skill as well as stringency

When agents may differ in skill as well as stringency, a high decision rate can mark accuracy, not leniency, and the instrument then correlates with case quality (Chan, Gentzkow, and Yu 2022). Flag a design where the paper observes something that varies with agent skill (later reversals, invalidations, defaults) and does not discuss it.

### IV14. Shift-share instruments

The paper should state whether identification rests on the shares (Goldsmith-Pinkham, Sorkin, and Swift 2020) or on the shocks (Borusyak, Hull, and Jaravel 2022) and report the diagnostics that choice needs: Rotemberg weights and share pre-trends for shares; shock balance and the effective number of shocks for shocks. Standard errors should allow for correlation among units with similar shares (Adao, Kolesar, and Morales 2019); heteroskedasticity-robust or region-clustered errors alone do not. These standard errors are this module's, not the inference overlay's.

### IV15. Lagged, industry-average, and peer-average instruments

An instrument built from lagged values of the endogenous variable, industry or peer averages, or the same firm's values in other periods needs an explicit exclusion argument given persistence in unobservables, common shocks, and spillovers; lagging does not remove simultaneity (Reed 2015).

The leave-one-out case. When the instrument is a group mean of the endogenous variable, including a leave-one-out mean z_i = (S_gt - x_i)/(n_gt - 1), and the model has fixed effects at that group-by-period level, the instrument moves within the fixed effects only as -x_i/(n_gt - 1): the instrument is the endogenous variable rescaled, and 2SLS reproduces OLS exactly when group sizes are equal and a group-size-weighted OLS otherwise; the conclusion is unchanged. That case is "Undermines the main claim" when the headline rests on it. An instrument absorbed entirely by the fixed effects is dropped by the software and is methods-checks CHECK 2's, not this module's.

### IV16. Dynamic panel GMM

Difference or system GMM should report the instrument count against the number of groups and whether instruments are collapsed. A Hansen p-value near 1 with many instruments is not validation; instrument proliferation weakens the test. An instrument count reported without a statement on collapsing is "Minor".

## Severity

- Undermines the main claim, only on the design the headline rests on: IV1 with IV2, and IV15, in the cases stated there.
- Minor: IV16 when the instrument count is reported but collapse is not stated.
- Everything else: at most Weakens a claim.

## Hand-offs

- Shift-share standard errors are this module's (IV14); the inference overlay skips shift-share estimates when IV is listed.
- Heckman selection models and control functions without an excluded instrument are the Selection module's.
- The triangulation agent skips its IV consistency block when IV is listed; IV4 and IV7 own it.
- LATE and complier questions from methods-checks CHECK 8 are IV9's.
