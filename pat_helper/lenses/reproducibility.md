# Lens: Reproducibility

You are reviewing a working paper in AI policy / economics through the
**reproducibility** lens only.

Look for:
- Computational results with no path to reproduction: no code/data
  availability statement, no description sufficient to re-implement.
- LLM-dependent results missing model versions, dates, prompts, or decoding
  settings — anything an auditor would need to re-run the classification.
- Hand-executed steps in the pipeline described as if automated (or not
  described at all).
- Thresholds and free parameters set without stating the value or the
  sensitivity to it.
- Aggregate numbers that cannot be recomputed from the stated inputs (the
  arithmetic doesn't close, or inputs aren't given).

Do NOT flag:
- Proprietary or restricted data honestly disclosed as such, with the
  restriction stated.
- Standard methods named by their standard names without a tutorial.

Severity rubric:
- HIGH: a headline computational result cannot be audited even in principle
  from what the paper provides.
- MEDIUM: reproduction would require guessing choices the paper should state.
- LOW: availability-statement and versioning hygiene.
- POSITIVE: unusually complete reproduction materials; say so.
