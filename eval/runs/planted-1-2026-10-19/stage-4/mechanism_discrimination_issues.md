Pack: archival

# Mechanism-Discrimination Issues

Source: stage-3/mechanism_discrimination.md. Contribution type: theory testing (run.json, phase1_summary.md).

## MD-1. No test separates the taken-for-grantedness channel from a policy-news channel
- Severity: Undermines the main claim
- Settled by: paper (authors can run the splits)
- Location: H1 and mechanism, pp. 8-9; "likely does not provide new information," p. 27; backing-feature controls, p. 25; Table 2 Model 2 (BR 0.036, SE 0.018).
- Paper's best version: backing paragraphs restate an unchanged framework, so the VIX response cannot be news.
- Fact: the paper never measures its mediator, dispersion of judgments (p. 9). The content controls on p. 25 are reported without coefficients. The crisis interaction (BR x crisis -0.051, p = .088, p. 20) has an ambiguous sign under a news account. Fact (stage-2 timeline): the 2 percent goal was adopted January 25, 2012, and asset purchases and forward guidance began in late 2008, both inside the sample.
- Inference: a news-arrival model predicts H1 equally well, so H1 does not test the proposed theory against it.
- Request: split BR into mandate-restatement and tool-boundary or change-discussing paragraph shares and report both coefficients; estimate Model 2 separately for 1998-2007 and 2008-2014; report VIX changes through t+1, t+3, and t+5; use dispersion of fed funds futures-implied rate paths or professional forecasts on speech days as a mediator outcome.

## MD-2. Policy-uncertainty inference is untested
- Severity: Weakens a claim
- Settled by: paper
- Location: pp. 8-9; argument_map.md Alternative 2.
- Paper's best version: discussing the rules makes alternatives thinkable, not more probable.
- Inference: if traders rationally raise the probability of a rule change, the same H1 and H3 signs follow.
- Request: interact BR with days to the next FOMC meeting and with a 2008-2012 unconventional-tools indicator; apply the BR coding to a sample of governor or regional-president speeches and compare the slope with the Chair's.

## MD-3. Venue attention within audience categories
- Severity: Weakens a claim
- Settled by: paper
- Location: BR-audience correlations, p. 22; audience fixed effects, Table 2 note, p. 57.
- Paper's best version: audience fixed effects absorb venue differences.
- Fact: fixed effects remove the five category means only.
- Request: add a t0 newswire count per speech (or flagship-venue indicators) and its interaction with BR.

## MD-4. H3 interaction is not separated from volatility scaling or reverse feedback
- Severity: Weakens a claim
- Settled by: paper
- Location: fear window t-1 to t+1, p. 16; Table 2 Models 4-5 (BR x fear 30.590, SE 12.626; 26.293, SE 12.482); existing uncertainty enters only as a main effect.
- Paper's best version: fear frames how traders read the backing.
- Inference: larger log-VIX moves in high-volatility periods, plus fear measured after the speech, can produce the interaction with no framing.
- Request: add BR x existing market uncertainty to Models 4-5, and rebuild fear over a window ending at t-1.
