# Design module: selection on observables and selection corrections

Scope. This module applies when the `Designs:` line lists Selection: the paper addresses non-random treatment or sample selection by matching, weighting, entropy balancing, a doubly robust or double machine learning treatment-effect estimator, a Heckman or treatment-effects model, or a named sensitivity analysis for omitted variables (Oster, Cinelli-Hazlett, ITCV, Rosenbaum bounds). A paper that only adds control variables does not load this module; methods-checks CHECK 3 keeps it.

Before starting, note which of the named methods the paper uses, the estimate each one supports, and the estimand it claims (ATT or ATE). Run only the checks for the methods present, plus SO14 and SO15 whenever the module loads.

## Protocol

### SO1. Heckman exclusion restriction

A Heckman selection model needs an excluded variable that affects selection but not the outcome, named and defended, or a statement that identification rests on functional form alone. Compare the first-stage and second-stage variable lists: identical lists plus year dummies fail. An industry average of the endogenous choice offered as the exclusion is a finding. Only 54 of 165 relevant strategy and organization papers claimed a valid exclusion restriction, and without one Heckman results are often less reliable than OLS (Wolfolds and Siegel 2019). Severity: at most "Weakens a claim", since the uncorrected estimate remains.

### SO2. Selection into the sample or into treatment

A sample-selection correction is for an outcome observed only for some units. When the outcome is observed for all units and the problem is self-selected treatment, the paper needs a treatment-effects model, an instrument, or a design, not a Heckman sample-selection lambda (Certo, Busenbark, Woo, and Semadeni 2016). Compare the outcome's coverage with the selection equation's dependent variable.

### SO3. What the inverse Mills ratio shows

For sample selection bias to exist, the variable of interest must predict selection in the first stage; a significant lambda alone does not show that selection bias existed or was corrected (Certo et al. 2016). Read both numbers, which usually sit in adjacent tables. A focal variable insignificant in the first stage beside a claim that "selection bias is present and our results are corrected" is a finding.

### SO4. With and without the correction

The estimate should appear with and without the selection correction, and collinearity between the inverse Mills ratio and the second-stage regressors should be reported (Puhani 2000; Lennox, Francis, and Wang 2012 on fragility). A focal coefficient that collapses when lambda enters, with only the corrected column shown, is a finding. So is a hand-run two-step whose second-stage standard errors ignore the estimated lambda (Heckman 1979; Wooldridge 2010, section 19.6). Both columns present with only the collinearity diagnostic missing is "Minor".

### SO5. Selection corrections in panels

A firm-year panel with firm fixed effects and a lambda from a pooled or year-by-year cross-sectional probit that omits the time averages (or leads and lags) of the covariates does not respect the panel structure. The Wooldridge (1995) and Semykina and Wooldridge (2010) procedures, which include them and interact lambda with time in the fixed-effects equation, pass. The paper should use a panel selection estimator or say why a pooled correction is acceptable.

### SO6. Balance after matching

Balance should be shown for each covariate with standardized differences before and after matching, not only t-tests or p-values, which depend on the matched sample's size (Imbens 2015). Compute standardized differences from the table's means and standard deviations when they are given: (mean_t - mean_c) / sqrt((sd_t^2 + sd_c^2) / 2). A covariate with a large standardized difference called balanced is a finding. The numbers of units matched and discarded in each group should be reported.

### SO7. Propensity score matching choices

The paper should state the score model, the algorithm, replacement, caliper, number of matches, and the estimand (ATT or ATE), and show the result under at least one alternative such as covariate matching, CEM, or weighting. Propensity score matching can increase imbalance and model dependence (King and Nielsen 2019), so a single specification is a finding. Do not reject propensity score matching outright; ask for balance and an alternative.

### SO8. Overlap and trimming

Overlap should be shown by group (score distributions). Trimming should report its rule, the number of treated units removed, and that the estimand now refers to the retained sample; the 0.1 to 0.9 rule of Crump, Hotz, Imbens, and Mitnik (2009) is one accepted rule, not a requirement. Many treated units with scores near 1 and no overlap check is a finding.

### SO9. Standard errors after matching (only when the inference overlay does not run)

If `run.json` `overlays` lists `inference`, skip this check; that pack owns it. Otherwise, standard errors after matching or weighting should account for the matching step and for estimating the score (Abadie and Imbens 2006; 2016), or the paper should state how it handled them. Do not state a direction or size for the error; it depends on the design.

### SO10. Weighting and entropy balancing

Weighting and entropy balancing should report the weight distribution, the effective sample size, and the covariates and moments balanced (Li, Morgan, and Zaslavsky 2018; Hainmueller 2012). Balance holds only on the moments and covariates chosen, so "perfect balance" claimed for covariates outside the balancing set is a finding, as are a few observations carrying most of the weight with no mention.

### SO11. Doubly robust and double machine learning estimates

A doubly robust estimate is consistent if either the outcome model or the score model is right; it does nothing about unobserved confounding (Kang and Schafer 2007). Flag a claim that the estimator makes the result causal or unbiased "even if the model is misspecified" in general. The covariate set of a doubly robust or double machine learning estimate should contain no post-treatment variables; a few bad controls can distort double machine learning badly (Hunermund, Louw, and Caspi 2023). Learners and cross-fitting stay with methods-checks CHECK 9.

### SO12. Sensitivity to unobserved confounding

The headline result should have a sensitivity analysis that fits the design, with its inputs stated. For Oster's delta, the assumed maximum R-squared and the proportional-selection assumption (Oster 2019); the benchmark maximum R-squared of 1.3 times the controlled R-squared is a rule of thumb, not a threshold. For Rosenbaum bounds, a matched design and a rank or binary test (Rosenbaum 1987); a gamma reported for a weighted regression is a misuse. Cinelli and Hazlett's robustness value (2020) comes with benchmarking against observed covariates.

For omitted-variable sensitivity, suggest Cinelli and Hazlett (2020), whose robustness value is benchmarked against observed covariates, or Oster (2019) with its inputs stated. The ITCV (Frank 2000) is a recognized sensitivity measure in management research; do not call it invalid and do not ask a paper that reports it to replace it. If it is the only analysis, ask for benchmarking against observed covariates.

### SO13. Covariates in the score, matching, or weighting model

Each covariate in the propensity score, matching, or weighting model should be measured before treatment or argued not to be a mediator or collider, and the set should have a stated causal rationale (Cinelli, Forney, and Pearl 2024). Board size or pay measured the year after a 2015 treatment, in a 2015 score model, is a finding. Controls in the outcome regression stay with methods-checks CHECK 3. Report each covariate once, here.

### SO14. Sample restrictions and data coverage

The sample should not be restricted on a variable the treatment could affect or on a later outcome: survival, continued coverage, non-missing later outcomes (Elwert and Winship 2014). The data source's coverage of the population the theory concerns should be addressed; public-firm databases do not cover private firms, and measures built on them can mislead (Ali, Klasa, and Yeung 2009).

Direction. Work out which way the restriction pushes the estimate using the paper's own evidence (for example, which group was more likely to leave the sample, and with what outcomes). "Undermines the main claim" when the paper's own evidence implies the restriction favors the headline's sign, on the estimate the headline rests on, and the removed units are numerous enough that plausible outcomes for them could account for the headline estimate (for example, a Lee (2009) trimming bound or a worst-case calculation from the paper's own numbers includes zero). When the restriction works against the headline or its direction is unclear, "Weakens a claim". Direction outranks methods-checks CHECK 7b's automatic High for this check. Report each restriction once, here.

### SO15. The method is an assumption, not a solution

Matching, weighting, and selection corrections rest on an assumption: that the observed covariates capture selection, or that the excluded variable is valid. The paper should say which and argue it. Flag "propensity score matching addresses endogeneity" or "we correct for endogeneity using Heckman" when the threats section names no unobserved reason for selection (Hill, Johnson, Greco, O'Boyle, and Walter 2021).

## Severity

- Undermines the main claim, only on the design the headline rests on: SO14 in the case stated there.
- Minor: SO4 when both columns are reported and only the collinearity diagnostic is missing.
- Everything else: at most Weakens a claim. SO1 is never above "Weakens a claim".

## Hand-offs

- Standard errors after matching or weighting belong to the inference overlay when it runs; SO9 runs only when it does not.
- Covariates in the score, matching, or weighting model (SO13) and sample restrictions on post-treatment variables (SO14) are reported here, not under methods-checks CHECK 3, 4, or 7b; the adversarial-DGP agent cites SO14 by id.
- Instrumental variables, including lagged and industry-average instruments, are the IV module's.
