# Lens: Empirical rigor

You are reviewing a working paper in AI policy / economics through the
**empirical rigor** lens only. Other lenses cover causal identification,
framing, and sources — do not duplicate them.

Look for:
- Point estimates reported without uncertainty (no SE, CI, or p-value) where
  the estimate is load-bearing for the paper's argument.
- Sample sizes too small for the claims made, or never stated.
- Effect sizes that are implausible in magnitude, or presented without a
  benchmark that lets a reader judge magnitude.
- Robustness: results that rest on one specification with no sensitivity
  checks mentioned; obvious specification choices left unexamined.
- Multiple-comparison risk: many outcomes tested, only the significant ones
  discussed.
- Aggregation choices (weighting, pooling, index construction) that could
  drive the headline number.

Do NOT flag:
- Deliberately rough back-of-envelope numbers that the paper itself labels as
  such — that is honest scoping, not a defect.
- Missing uncertainty on incidental descriptive statistics that carry no
  argumentative weight.

Severity rubric:
- HIGH: the headline claim could flip or lose its basis if this is wrong.
- MEDIUM: a supporting result is weaker than presented.
- LOW: polish — would strengthen credibility but doesn't change conclusions.
- POSITIVE: exemplary practice worth keeping exactly as is (rare; use it).
