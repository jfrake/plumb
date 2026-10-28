# Hypothesis audit

## Issues
1. The Discussion presents the crisis-period extension, which was built after the main results and labeled tentative there, as "additional validation" of the a priori theory, without keeping it apart from H1 to H3.
   Check: HL13. Unit: Hypothesis H1 (crisis-period extension, not a numbered hypothesis). Tag: paper
   Paper's best case: The results section frames the crisis analysis openly as a supplemental attempt to "tentatively extend this story" by relaxing the theory's high taken-for-grantedness assumption (p. 19), and calls the outcome "preliminary evidence" (p. 20), which is honest labeling at the point of first report.
   Evidence: The prediction that reaffirming the backing should "no longer destabilize the institution to the same extent" during the crisis appears first in the results (pp. 19-20), after Table 2 and Figures 3-5; it is not stated in the theory section (pp. 7-12). The results label it "Supplemental Analyses" (p. 19), "tentatively extend" (p. 19), "preliminary evidence of an important extension" (p. 20), and "this exploration" (p. 20). In the Discussion the label drops: the result becomes "additional validation of this story," followed by "Taken together, my findings depict a consistent theory" (p. 26). The ledger lists the BR x crisis interaction and the 48-speech crisis subsample under `unhypothesized_tests` (pp. 20-21, 26). There is no abstract in the manuscript, and the Conclusion (p. 35) does not mention the crisis result. Whether the crisis-period difference is itself established (one interaction at p = .088 with year fixed effects, p. 20) belongs to the packs that own differences across groups and is not raised here.
   Excerpt: "Interestingly, as additional validation of this story, I also illustrated how, during the financial crisis, when the taken-for-grantedness of these assumptions had weakened, reaffirming them no longer creates uncertainty to the same extent."
   Page: 26
   Severity: Minor
   What would settle it: Carry the results-section label into the Discussion: describe the crisis analysis as a post hoc, exploratory extension and keep it out of the sentences that summarize support for H1 to H3.

2. The Discussion restates H1 with a broader outcome than the one tested: "uncertainty in financial markets around the world," while the test is the one-day change in the VIX, which is built from U.S. S&P 500 option prices.
   Check: HL12. Unit: Hypothesis H1. Tag: paper
   Paper's best case: The VIX is a widely used gauge of market uncertainty that the paper motivates with finance studies (p. 13), so a reader may take "financial markets" as shorthand for the measured construct.
   Evidence: H1 states "market uncertainty" (p. 9). The methods measure it as ln(VIX_t/VIX_t-1) over t-1 to t0, where the VIX is computed "by averaging the weighted prices of S&P 500 puts and calls" (p. 13). Table 2 Model 2 tests BR against this outcome only (p. 56). No test in the paper uses a non-U.S. market or any outcome other than the VIX change (searched methods pp. 12-17, results pp. 18-21, robustness pp. 21-25, Tables 1-2 pp. 54-57, Figures 2-7 pp. 50-53). The restatements on pp. 10 and 18 keep the original scope; the p. 25 restatement widens it. Direction is unchanged. The causal wording in the same sentence ("proved," "causes") is left to the inference and archival packs.
   Excerpt: "Using speeches made by the Chair of the United States Federal Reserve from 1998 to 2014, I proved that reaffirming the assumptions underlying the monetary policy framework causes uncertainty in financial markets around the world."
   Page: 25
   Severity: Minor
   What would settle it: Restate the finding at the scope of the test (implied volatility of the U.S. equity market on the speech day), or add tests on non-U.S. volatility indices if the global claim is to stand.

## Checked and fine
- HL1: Every hypothesis has a test in the ledger: H1 in Table 2 Models 2-5 and Figure 3; H2 in Models 3 and 5 and Figure 4; H3 in Models 4 and 5 and Figure 5 (pp. 18-19, 51-52, 56-57).
- HL2: No abstract is supplied, and the Conclusion (p. 35) presents no unhypothesized result as evidence for the theory. The word-count result the Discussion calls "strong support for the signaling perspective" (p. 28) is offered as support for a different theory, not this one, and sits in the Discussion; the crisis split and the 48-speech subsample (pp. 20-21) are labeled exploratory in the results. Neither is an HL2 finding under rule 4; the Discussion's relabeling of the crisis result is raised once, under HL13 (Issue 1).
- HL3: Stage 1 raised no `numbers:hyp:*:HL3` flag; every focal test for H1 to H3 clears the one-tailed .05 level the note sets (p. 57). The `***` on BR in Model 2 (0.036, SE 0.018) overstates the level, but it does not change which hypotheses the text calls supported, and the numbers flags `numbers:arith:2:BR/Model 2:stars_vs_se` and `numbers:text:2` already carry it.
- HL4: No hypothesis is called partially supported.
- HL5: No sign flag. BR is positive in Models 2-5 as H1 predicts; BR x positive tone is negative (H2, weakens a positive base effect); BR x fear is positive (H3, strengthens) (Table 2, p. 56).
- HL7: No null hypothesis in the ledger; no flag.
- HL9: No flag. The product-term signs match the stated shapes in a linear model, and the verdicts on p. 18-19 follow sentences that introduce the product terms in Models 3 and 4.
- HL11 (moderated mediation): No mediation or moderated-mediation hypothesis. HL11 indirect-effect and full-mediation parts would run here (no survey or experiments pack) but have no row to apply to.
- HL12: H1's restatements on pp. 10 and 18 keep its number, direction, and constructs; H2 (p. 18) and H3 (p. 19) are restated consistently; numbering H1-H3 has no gaps. The one change in scope is Issue 2.
- HL13: H1 to H3 are first stated in the theory section (pp. 9, 11, 12), before the results.
- HL14: The outcome in every test is the VIX change the methods define as market uncertainty, a proxy the paper argues for (p. 13); the predictor is the speech-level backing ratio H1 names (pp. 13-14). The business media fear window running through t+1 (pp. 15-16), against H3's "at the time of the speech," is a timing and post-treatment issue the construction ledger and `stage-2/dgp_map.md` already carry; not raised here.
- HL15: No flag. H3's verdict names Models 4 and 5 without naming one as the test (p. 19); both product terms carry significance marks (30.590, SE 12.626; 26.293, SE 12.482; p. 56), so no failing test is involved.
- HL8: not run; owned by the archival, nonlinear, and inference packs.
- HL10: not run; owned by the nonlinear pack (N1).
- Stage 1 inputs: `hypothesis_checks.md` and `.json` report 0 flags, 0 facts, nothing not computed; `dropped_flags.md` lists none; `brief.md` has no user corrections. No `numbers:hyp:` item exists to decline.
