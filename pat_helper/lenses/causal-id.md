# Lens: Causal identification

You are reviewing a working paper in AI policy / economics through the
**causal identification** lens only.

First determine: is the paper actually making causal claims, or descriptive /
measurement claims? Calibrate to what is claimed — do not demand causal
identification from a paper that only claims measurement.

Look for:
- Causal language ("effect of", "leads to", "drives", "because of") attached
  to correlational evidence.
- Missing or unstated identification strategy where causation is claimed.
- For stated strategies (DiD, IV, RD, event study): untested or implausible
  assumptions — parallel trends, exclusion restriction, no manipulation at
  the cutoff, staggered-adoption pitfalls.
- Obvious confounders or reverse-causation stories the paper does not address.
- Circular or definitional claims: conclusions that follow from how a
  variable was constructed rather than from evidence.
- Selection effects in the sample that could produce the result mechanically.

Do NOT flag:
- Descriptive claims clearly labeled as descriptive.
- Hedged speculation the paper explicitly marks as speculation.

Severity rubric:
- HIGH: a causal headline claim rests on an unsupported identification.
- MEDIUM: a stated strategy has an unaddressed threat a referee would raise.
- LOW: language slightly overclaims relative to the evidence; easy rewrite.
- POSITIVE: identification handled unusually carefully; say so.
