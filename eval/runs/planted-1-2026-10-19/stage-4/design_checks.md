Pack: archival

# Design checks

Modules loaded: Selection (secondary; the ITCV omitted-variable sensitivity analysis for the H1 estimate, p. 24, Figure 7 p. 53)

## Issues
1. The ITCV sensitivity analysis does not support its conclusion at the value the text reports: at 0.014, observed covariates in the paper's own Table 1 and Figure 7 already exceed the threshold, and the analysis is not benchmarked in a way a reader can reproduce.
   Check: SO12. Design: Selection (secondary). Tag: [paper]
   Paper's best case: The ITCV shows that an omitted variable would need to correlate at about 0.12 with both BR and the change in the VIX to remove H1's significance, which the author argues is larger than any observed control's impact.
   Evidence: Text, p. 24: "An omitted variable in my context would have to correlate positively with both the BR and market uncertainty at 0.12, which when multiplied together, makes my ITCV equal to 0.014" (0.12 x 0.12 = 0.0144, so the arithmetic holds). Figure 7 (p. 53) draws the ITCV bar at 0.030, not 0.014. Figure 7 itself shows three covariates in the 0.020 bin and one in the 0.015 bin, all above 0.014. From Table 1 (extracted_tables/table_01.csv), the products the text says Figure 7 plots (r with BR x r with market uncertainty) are 0.27 x 0.08 = 0.0216 for speech negative tone and 0.42 x 0.05 = 0.021 for speech complexity, both above 0.014. The claim that the needed omitted variable "is substantially larger than every other control variable" therefore holds only against the figure's 0.030. Two inputs are also unstated: the critical t used to define "below significance" (the Table 2 note, p. 57, uses one-tailed tests, and the BR coefficient in Model 2 is 0.036 with SE 0.018, t about 2.0), and whether the covariate impacts are zero-order correlations, as the p. 24 description implies, or partial correlations given the other controls and fixed effects in Model 2. Note also that the threshold correlation of 0.12 with the outcome exceeds BR's own raw correlation with the outcome in Table 1 (0.09). This overlaps Stage 1 flag 12 (ITCV 0.014 vs 0.030); the design-specific part here is the benchmarking and the unstated inputs.
   Excerpt: "This figure shows that the size of the omitted variable needed to invalidate my results is substantially larger than every other control variable used in existing literature."
   Page: 24
   Severity: Weakens a claim
   What would settle it: Report one ITCV value, computed from Model 2 with its stated critical value (one- or two-tailed) and the partial correlations conditional on the model's controls and fixed effects; redraw Figure 7 at that value with the covariate impacts computed the same way; and add a sensitivity measure benchmarked against observed covariates, such as Cinelli and Hazlett's robustness value or Oster's delta with its maximum R-squared stated. If the corrected ITCV falls below observed covariates' impacts, narrow the p. 24 conclusion.

2. The estimation sample is trimmed on studentized residuals of an unstated model of the outcome, which is selection on the dependent variable for every estimate in Tables 1 and 2, and the count after trimming is inconsistent.
   Check: SO14. Design: Selection (secondary). Tag: [paper | judgment]
   Paper's best case: Removing seven of 344 speeches (2 percent) with extreme residuals is a standard guard against a few influential observations driving an OLS estimate.
   Evidence: P. 12: seven speeches removed because "their studentized residuals exceeded plus or minus three", leaving 337; Tables 1 and 2 (pp. 54-57) and Figure 2 report N = 339. The paper does not say which model produced the residuals (with or without BR and the moderators), which tail the removed speeches came from, or their BR values. Speeches with the largest unexplained VIX moves are plausibly the most market-moving Chair speeches, the events the theory concerns (stage-2/dgp_map.md, step 4). The direction of any bias cannot be worked out from the paper's evidence, since it reports nothing about the removed speeches. Searched the Methods (pp. 12-18), the robustness section (pp. 24-25), and the Table 1 and Table 2 notes; no estimate on the full 344 speeches is reported. The rule caps a module finding on a secondary design at Minor, though the restriction applies to the main H1 estimate and to H2 and H3.
   Excerpt: "Seven speeches were removed because, based on an outlier analysis, their studentized residuals exceeded plus or minus three."
   Page: 12
   Severity: Minor
   What would settle it: State the reference model for the residuals, list the removed speeches with their dates, BR, and VIX changes, reconcile 337 with 339, and report Table 2 Models 2 to 4 on all 344 speeches alongside the trimmed results, or with a robust estimator that downweights rather than drops observations.

## Checked and fine
- Input files: fingerprint, brief (no user corrections), run.json, Stage 1 flags and dropped_flags (none dropped), Stage 2 dgp_map, and Table 1 CSV were read; the PDF was read at pp. 11-13, 22-25, and 53.
- SO1-SO5 (Heckman and selection corrections): do not apply; the paper uses no selection model (Methods pp. 12-18, robustness pp. 22-25).
- SO6-SO8 (matching, balance, overlap): do not apply; no matching (pp. 12-25).
- SO9 (standard errors after matching): skipped; the inference overlay runs, and there is no matching.
- SO10 (weighting and entropy balancing): does not apply; no weighting.
- SO11 (doubly robust or DML): does not apply.
- SO13 (covariates in a score or weighting model): does not apply; there is no score model. Controls in the outcome regression stay with methods-checks.
- SO15 (method as assumption): the paper states the assumption the ITCV rests on, "Assuming that I have included a reasonable set of control variables" (p. 24), and names unobserved threats (acute and systemic market factors, pp. 23-24). It does not present the ITCV as solving endogeneity.
- Secondary-design limit: two findings reported, the maximum for a secondary design.
