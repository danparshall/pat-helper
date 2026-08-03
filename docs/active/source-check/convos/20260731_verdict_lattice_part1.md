# Verdict Lattice Part 1–4 Implementation + Step-22 Gate

**Date:** 2026-07-31 → 2026-08-03 (gate ran 08-02; closed 08-03 with the
checker-calibration question unadjudicated)
**Branch:** source-check
**Machine:** Dans-MacBook-Pro

## Summary

Implemented the full verdict-lattice/provenance plan
(`../plans/20260731_verdict_lattice_provenance.md`) via TDD, Parts 1–4,
zero-spend through step 21. `Finding.verify_provenance` is now set exactly
where verdicts are set (`"text"` on verify success, `"source"` on
source-check verdict changes, `None` on the verify exception path so the
unearned default can never outrank a real verdict). New pure module
`pat_helper/lattice.py::merge_verdict` computes merged
verdict/provenance/annotations deterministically; synthesis stopped
reporting `verified` and instead reports `contributors` (input ids) +
`echoes_demoted` (digest ids), with validated bookkeeping and safe
fallbacks (dropped ids → originals appended + gap; duplicate/out-of-range/
empty → whole-stage pass-through + gap). Source-refuted demotions enter
synthesis as a read-only digest; echoes get a factual warning annotation.
Renderer tags source-tier verdicts `(source-checked)`.

Mid-session, Dan (via a mid-turn message confirmed for this session) asked
for pushes at every checkpoint and a README_TODAY for concerns — outputs
were needed same-day. All four parts were committed and pushed
individually. Dan approved the step-22 paid gate; it ran 2026-08-02.

Gate outcome: mechanically clean — recall 3/3, contributor bookkeeping
fully compliant live (0 gaps, the plan's medium-confidence unknown), tag
and annotation render. But the merged Svanberg finding rendered
`softened (source-checked)` rather than the criterion's
`upheld (source-checked)`: the run produced *two* source-tier verdicts
(anthropic confirmed; google narrowed while its own reasoning validated
the numeric error), and within-tier conservatism correctly picked
softened. A checker-calibration question, not a code defect.

## Topics Explored

- TDD implementation of plan Parts 1–4 (15 + 5 + 4 + 4 new tests; suite
  95 → 123 green)
- Subagent test-quality review (14 KEEP; surfaced one real gap — the
  exception-path default vs a real text verdict — test added)
- Design decision at implementation time: `refuted` placed first in the
  lattice conservatism order (unreachable today; foundation for issue #2)
- Step-22 paid gate live behavior, incl. checker-resolution variance

## Provisional Findings

- Live synthesis (claude-opus-4-8) complies with contributor-id
  bookkeeping on a 24-finding fixture run — none of the fallbacks fired
- Checker resolution variance is real: same source, same evidence — one
  checker's `critique-confirmed` vs another's `critique-narrowed` hinged
  on which charge they read as the critique's center; conservatism then
  decides the merged verdict
- The Part 3 demoted digest did not exercise live (0 demoted this run)

## Decisions Made

- Dan: go on the step-22 paid gate (~$2–4)
- Commits pushed per part: `2f2c6d9` (Part 1), `1c2b187` (Part 2),
  `534e7d6` (Part 3), `b634e85` (Part 4)
- README_TODAY.md written at worktree root per Dan's instruction
  (ephemeral; durable record is results/ + this log)

## Results

- `../results/20260802_step22_lattice_gate.md` — gate outcome, the
  softened-vs-upheld nuance, provenance
- Raw outputs preserved: `data/harness_out_v9/review_2026-08-02.md`,
  `data/harness_out_v9/harness_2026-08-02.md`

## Open Questions

- Checker calibration: should `_source_check.md` sharpen what "central
  charge" means, or should confirmed-with-validated-number outrank
  narrowed? Does `softened (source-checked)` undersell a confirmed numeric
  misstatement? (Needs Dan's adjudication.)
- Warning wording for the echoed-demotion annotation (plan question;
  current draft factual, untested live)
- Carried: Dan's extras/demoted skim (issue #1); symmetric propagation
  (issue #2)
