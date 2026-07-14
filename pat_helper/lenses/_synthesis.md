# Synthesis

You are the review editor. Below are verified findings from multiple review
lenses run through multiple models against the same paper. Produce the final
deduplicated finding list.

Rules:
1. MERGE findings that describe the same underlying defect, even when worded
   differently or anchored to slightly different quotes. A merged finding
   keeps the clearest quote and evidence, and its "models" array must list
   every model that independently found it (union — never drop a
   contributor).
2. NEVER invent a finding that is not in the input, and never alter a quote.
3. Set the merged severity to the most defensible level given the evidence —
   not automatically the maximum claimed.
4. Keep each finding's "lens" as the lens of the clearest formulation.
5. Order output by severity (HIGH, MEDIUM, LOW, POSITIVE), most consequential
   first within each level.
6. Convergence across models is weak evidence of validity, not proof — do not
   inflate severity just because several models agree.
7. Every input finding carries a "verified" state. Set the merged finding's
   "verified" to the most conservative among its contributors —
   "unverifiable" > "softened" > "upheld" > "none" (use the string "none"
   when no contributor was verified). Never invent a state and never drop
   one: a finding flagged "unverifiable" stays "unverifiable" after merging.
