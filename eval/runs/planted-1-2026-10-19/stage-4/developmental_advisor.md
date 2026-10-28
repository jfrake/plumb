# Developmental Advisor

Inputs read: PDF pp. 12-26 (text extracted and checked against the passages cited below), `paper_summary.md`, `run.json` (contribution type: theory testing; journal: generic), `extracted_tables/table_02.csv`, `stage-0/phase1_summary.md`, `stage-1/numeric_fidelity.md` and `arithmetic.md`, `stage-2/dgp_map.md`, `stage-3/framing_diagnosis.md`, `argument_map.md`, `alternatives.md` (all four marked "plausible, investigate further"), `contribution_audit.md`, `theory_devil_report.md` (verdict: Rethink), and `stage-4/framing_issues.md` and `mechanism_discrimination_issues.md`. Search cap 2016-06-01 respected. Two lookups, both pre-cap.

Stance: the paper has a real asset. It holds a hand-coded, paragraph-level measure of argument structure for 17 years of Chair speeches, and that measure predicts speech-day implied volatility conditional on six existing text measures (Table 2). The findings below aim to turn that asset into a test that can separate the paper's mechanism from its rivals. Where another Stage 3 or Stage 4 file already asks for a specific test, I point to it and do not repeat the request.

On framing, I start from the chord in `framing_diagnosis.md` (wider reach: Suchman's warning carried to a hard case, voiced cumulative, surprise kept) and do not depart from it. Findings 3 and 5 build on that chord. I do not restate its framing findings.

---

1. **The most valuable revision is a timing design that shows the VIX moves when the speech becomes public and not before. The paper's own placebo currently points the other way.**
   - Paper's best version: speeches are scheduled about six months ahead and high-BR speeches are written one to six months ahead and rarely changed in the final week, so BR is fixed before speech-day market conditions arise (pp. 21-23).
   - Location: p. 25 (placebo); pp. 21-24 (timing argument); p. 13 (two-day window t-1 to t0); Table 2 Model 2, p. 56.
   - Evidence (paper, verified): the p. 25 sentence says "the BR did not predict market uncertainty for the two-day event window before the day of the speech (β = .041, σ2 = 0.017, p = .017, adjusted R-squared = 0.083)". The reported numbers are a significant coefficient larger than the Model 2 main effect (0.036, SE 0.018, `table_02.csv`). `numeric_fidelity.md` already records the text-number conflict; I do not re-litigate it. The timing argument on pp. 21-23 rules out shocks that arrive after the speech is written. It does not rule out a persistent state (contestation of the framework, a weak economy) that leads the Fed to write backing-heavy speeches months ahead and also keeps volatility rising around the speech date. BR correlates 0.26 with unemployment (Table 1, via `argument_map.md`), and `dgp_map.md` notes after-close delivery that can push the market response outside the window.
   - Inference: as reported, the placebo is the paper's own evidence for the reverse-causality alternative (`alternatives.md` item 1; `theory_devil_report.md` Challenge 1). Until the timing evidence is rebuilt, H1 reads as an association between BR and the VIX path around speeches.
   - Constructive path: (a) an event-time figure of the BR coefficient for each day from t-5 to t+5, using the same controls; (b) for speeches with a recorded release time, an intraday window around release, following the high-frequency event-study logic that monetary economics already uses for Fed communication; (c) a permutation placebo that assigns each speech's BR to the non-speech trading days in the same and adjacent weeks and reports where the speech-day estimate falls in that distribution; (d) speeches delivered after the close assigned to t+1. Gürkaynak, Sack, and Swanson (2005) is the standard reference for (b): "We investigate the effects of U.S. monetary policy on asset prices using a high-frequency event-study analysis" and "We measure the effects of these two factors on bond yields and stock prices using a new intraday data set going back to 1990" (https://ideas.repec.org/a/ijc/ijcjou/y2005q2a2.html). Pre-speech VIX trend as a control is already requested in `alternatives.md` item 1; I do not repeat it.
   - Adjudication: paper (the placebo and timing claims); judgment (which design best answers the reverse-causality reading).
   - Proposed severity: Undermines the main claim. For a theory-testing paper the causal reading of H1 carries the contribution, and the reported placebo bears directly on it.

2. **Choose outcomes that the theory points to: uncertainty about the monetary policy institution itself, and whether it persists.**
   - Paper's best version: a destabilized Fed "creates uncertainty in the broader financial markets" (p. 3), so equity implied volatility is a downstream sign of destabilization.
   - Location: p. 3; DV definition pp. 13, 18; mechanism pp. 8-9 ("range of expected directions").
   - Evidence (paper, verified): the only outcome is the one-day log change in the S&P 500 VIX (pp. 13, 18). The mechanism is divergence of participants' judgments about the framework (pp. 8-9). Evidence (external): dispersion of private-sector interest-rate forecasts is an established, measured quantity in this literature. Swanson (2006, JMCB 38(3)) reports that forecasters became "less diverse in the cross-sectional variety of their interest rate forecasts" as Fed transparency rose (https://ideas.repec.org/a/mcb/jmoncb/v38y2006i3p791-819.html).
   - Inference: the theory concerns the monetary policy framework, so the closest observable is uncertainty about the policy path (interest-rate option implied volatility, dispersion of rate forecasts), with equity volatility as a more distant echo. A destabilization account also implies that the rise lasts; a news account implies a jump that is partly resolved within days (`argument_map.md`, null model c). `mechanism_discrimination_issues.md` MD-1 already asks for t+1/t+3/t+5 VIX changes and for fed funds futures dispersion as a mediator; I do not repeat those requests.
   - Constructive path: put rate-uncertainty outcomes next to the VIX in the main table, so the paper shows where along the chain from the Fed's framework to equity markets the effect appears. State in advance what pattern each account predicts across the outcomes.
   - Adjudication: external (the measure exists and is used); judgment (which outcomes the theory implies).
   - Proposed severity: Weakens a claim.

3. **Turn the post-hoc scope condition into a measured, pre-stated moderator, and drop the crisis subsample selected on the H2/H3 conditions.**
   - Paper's best version: reaffirmation destabilizes only where assumptions are highly taken for granted, and 2008-2012 was a period when they were not (pp. 19-20, 26).
   - Location: pp. 19-21 (crisis analysis, Figure 6); p. 26.
   - Evidence (paper, verified via `numeric_fidelity.md` row 34 and `paper_summary.md`): the crisis-only BR estimate is 0.035 (p = .335), against 0.036 in the full sample (Model 2). The point estimate is unchanged; only precision differs. The 48-speech subsample with a reversed sign (β = -0.155, p = .022, p. 21) is selected on high tone and low fear, which are the H2 and H3 moderators. Taken-for-grantedness is never measured (`argument_map.md`, Scope conditions).
   - Inference: the crisis results do not show attenuation in the point estimate, and the 48-speech result is selected on the moderators it is read with. The scope condition is the theory's most direct heterogeneity prediction, and it is currently untested.
   - Constructive path: build a time-varying measure of contestation of the framework that does not use the VIX, for example counts of newspaper articles in the 30 days before each speech that question the dual mandate, the Fed's tools, or Fed independence. State in the introduction (consistent with the framing chord's advice to state the scope condition there) that the BR effect should be larger where contestation is low, and test BR x contestation. Report the 1998-2007 and 2008-2014 estimates side by side as a secondary check. Move the 48-speech analysis to an appendix labeled exploratory or remove it.
   - Adjudication: paper (estimates and selection rule); judgment (choice of measure).
   - Proposed severity: Weakens a claim.

4. **Use the Toulmin decomposition the paper already has to run a specificity test: backing should matter and claim and data paragraphs should not.**
   - Paper's best version: backing is the component of an argument that carries taken-for-granted assumptions, unlike claims and data (pp. 5-7, 14).
   - Location: p. 14 (paragraph coding); p. 22 (low-BR speeches "discuss the current outlook"); p. 28 (word count read as information); Table 2 (speech word count negative in all models).
   - Evidence (paper, verified): BR is a share of paragraphs (p. 14), so a speech high in backing is low in other content. The paper links low-BR speeches to outlook content (p. 22). `alternatives.md` item 3 sets out the crowding-out account; no Stage 4 file yet asks for the test.
   - Inference: the theory makes a sharper prediction than H1. If the mechanism is taken-for-grantedness, the share of claim and data paragraphs should have no positive effect, and holding outlook content fixed should leave the BR coefficient in place. A share-based BR cannot separate "more backing" from "less outlook" on its own.
   - Constructive path: code every paragraph into the Toulmin components (data, claim, warrant, backing; Figure 1, p. 50), enter the component shares or counts together with one category omitted, and report them in one table. This is a natural extension of the existing coding and would also show readers what the BR construct adds over the six text measures already in Table 2.
   - Adjudication: paper (feasibility, coding already at paragraph level); judgment (the prediction).
   - Proposed severity: Weakens a claim.

5. **Within the recommended chord, state the empirical contribution in a way the evidence already supports: BR predicts market response conditional on existing text measures, which speaks to the finance literature's dilution problem.**
   - Paper's best version: BR is "a potential direct measure of cognitive legitimacy" (p. 34) and the paper is "one of the first" to study Chair speeches (p. 31).
   - Location: pp. 31, 34; Table 2 (BR alongside speech uncertainty, negative tone, power, complexity, abstraction, vagueness, positive tone, p. 56).
   - Evidence (paper, verified from `table_02.csv`): BR enters next to seven text measures in Models 2-5 and its coefficient stays between 0.034 and 0.045. Evidence (external, fetched by `contribution_audit.md` item 5): Kohn and Sack (2003) find "we do not find significant effects on any of the financial variables" for Greenspan speeches and attribute this to topics diluting the content. I rely on that fetched quote and do not re-cite it independently.
   - Inference: the framing chord asks the introduction to carry Suchman's warning to a hard case. The empirical half of that move is stronger if the paper says that a structural feature of the argument (how much of a speech restates the backing) predicts market response where whole-speech measures did not, and shows it conditional on the dictionaries already used. That claim is within reach of the current evidence once findings 1 and 4 are addressed. The differentiation from Harmon, Green, and Goodnight (2015) and from Ashforth and Gibbs (1990) is already raised in `contribution_audit.md` items 2-3; I do not repeat it.
   - Adjudication: paper (Table 2); external (Kohn and Sack, via the audit's fetched source); judgment (positioning).
   - Proposed severity: Weakens a claim.

6. **Narrow the hypothesis set so the paper's space goes to the mechanism.**
   - Paper's best version: speaker tone and media fear form a single interpretive context that narrows or widens the range of interpretations (pp. 9-12, 28-29).
   - Location: H2 and H3, pp. 10-12; Table 2 Models 3-5; p. 20 (crisis).
   - Evidence (paper and prior files): the emotion contribution extends Pfarrer, Pollock, and Rindova (2010), as the paper says (p. 10; `contribution_audit.md` item 6). H3 is open to a volatility-scaling reading and a fear window that runs to t+1 (`mechanism_discrimination_issues.md` MD-4). H3 also predicts amplification in the high-fear crisis years, while the paper reads the crisis as attenuation (`argument_map.md`, Internal consistency).
   - Inference: the moderators add less to the core claim than findings 1-4 would, and H3 sits uneasily with the crisis reading.
   - Constructive path: keep H2 and H3 as secondary analyses (or an appendix), and use the main-text space for the timing design, the component decomposition, and the contestation moderator. If H3 stays in the main text, the fixes in MD-4 come first.
   - Adjudication: judgment.
   - Proposed severity: Minor.

7. **Report the robustness work in tables, and show the main estimates with the full sample.**
   - Paper's best version: the result survives GEE with AR(1) errors, backing-feature controls, alternative control windows, and an omitted-variable bound (pp. 24-25).
   - Location: pp. 12, 24-25; Table 2, p. 56; Figure 7, p. 53.
   - Evidence (paper, verified): every robustness check on pp. 24-25 is reported in words ("strong support", "consistent results", "remained consistent") without coefficients. Seven speeches were removed for studentized residuals beyond plus or minus three (p. 12), a rule based on the outcome model; `dgp_map.md` notes no robustness check covers it. Mechanical inconsistencies are already logged in Stage 1: N of 337 in the text versus 339 in the tables, Model 2 BR marked *** when 0.036 (0.018) supports ** under the one-tailed test the note states (`arithmetic.md`), the ITCV given as 0.014 in the text and 0.030 in Figure 7, and the 1.0 percent effect size against 0.036 x 0.21 = 0.76 percent (`numeric_fidelity.md`). I do not re-adjudicate these.
   - Inference: readers cannot judge how much the robustness checks support H1 when no estimates are shown, and the outlier rule is a sample choice made on the outcome.
   - Constructive path: one appendix table with the BR coefficient and SE under each check on pp. 24-25, plus Model 2 on all 344 speeches and with the Table 2 note's robust-regression estimator stated explicitly. Fix the Stage 1 inconsistencies in the same pass.
   - Adjudication: paper.
   - Proposed severity: Weakens a claim.

8. **Strengthen the BR coding protocol so the measure can carry a theory-testing claim.**
   - Paper's best version: four coders reached Krippendorff's alpha of 0.88 and .84 (pp. 13-14).
   - Location: pp. 13-14.
   - Evidence (paper, verified): the rule codes a paragraph as backing when the Chair "reaffirms or reiterates in some way the nature and boundaries of monetary policy objectives and conventional tools" (p. 14). The coders are the author and three undergraduates; the text does not say whether coders saw speech dates. Reliability is reported on the first 60 and last 10 speeches.
   - Inference: a coder who knows a speech's date can bring knowledge of the period (crisis, new tools) into a broad rule. That matters because finding 3 and the crisis analysis lean on period differences.
   - Constructive path: publish the codebook with marginal examples, recode a random subsample with coders blind to date and speaker, and report agreement on that subsample. Coding the tool-boundary and mandate-restatement subtypes (requested in MD-1) under the same protocol keeps the two analyses consistent.
   - Adjudication: paper (protocol as described); judgment (what blinding adds).
   - Proposed severity: Minor.

## Order of work, as I would advise the authors

Findings 1, 4, and 2 come first, in that order, because they decide whether H1 can be read as the paper's mechanism. Finding 3 then supplies the scope condition the framing chord asks the introduction to state. Findings 5-8 follow from those results.

## Sources fetched in this file
- Gürkaynak, Sack, and Swanson (2005), International Journal of Central Banking 1(1). https://ideas.repec.org/a/ijc/ijcjou/y2005q2a2.html. Quotes: "We investigate the effects of U.S. monetary policy on asset prices using a high-frequency event-study analysis." "We measure the effects of these two factors on bond yields and stock prices using a new intraday data set going back to 1990."
- Swanson (2006), Journal of Money, Credit and Banking 38(3): 791-819. https://ideas.repec.org/a/mcb/jmoncb/v38y2006i3p791-819.html. Quote: "less diverse in the cross-sectional variety of their interest rate forecasts."
