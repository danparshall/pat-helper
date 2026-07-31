# Verdict lattice / provenance brainstorm

**Date:** 2026-07-31
**Branch:** source-check
**Machine:** Dans-MacBook-Pro

## Summary

Worked the open design question carried from steps 14–15: synthesis
most-conservative-wins ranks `softened` above `upheld`, so a
source-check-upheld finding merged with a text-only-softened sibling
renders `softened` — the report undersells a defect confirmed against the
actual cited source. Brainstorm (Nori skill) ran from the step-14 run-3
specimen rather than the abstraction.

Two load-bearing observations surfaced while pulling the specimen:

1. **The softening rationale is unrecoverable.** The fixture harness kept
   no checkpoint for the 07-16 run and the renderer never prints
   `verify_notes`, so the only record of *why* the argumentation sibling
   was softened died with the run. Dan's adjudication ("probably b, but
   can't recall what was said") was unanswerable from the system's own
   artifacts — itself evidence that merge-surviving rationales must be
   structured data that reaches the report.
2. **The mirror case is worse and unhandled.** `refuted` findings —
   including source-check-refuted — are demoted to the appendix *before*
   synthesis (pipeline.py stage boundaries), so a ground-truth-refuted
   finding's text-only-upheld sibling renders at full strength with
   nothing connecting the two. That is the circular-refutation class this
   branch exists to kill, wearing the other sign.

## Topics Explored

- Step-14 run-3 collision specimen (`harness/out/review_2026-07-16.md`
  line 73: prior-work citation-mismatch renders `softened`)
- Where the lattice lives: synthesis prompt rule 7 (`_synthesis.md`) —
  LLM-enforced, not code-enforced; provenance only in free-text
  `verify_notes` tags
- Pipeline ordering: source-check-refuted → demoted pre-synthesis, so
  refuted contributors never enter the merge pool
- Asymmetric stakes: upheld-vs-softened miss wastes Dan's attention;
  refuted-sibling miss makes the report confidently repeat a
  source-contradicted critique

## Decisions Made

- **(b) for the label collision:** source-grounded verdicts outrank
  text-only in the merged `verified` label, but the outranked softening is
  *carried as an annotation*, not discarded — a narrowing can be about an
  aspect (scope, presentation) the source check never addressed. Evidence:
  the step-15 Svanberg adjudication ("I'd prefer the reminder").
- **Mirror case: (iii) now, (i) later.** Dan: "okay with 3 → 1." Now:
  synthesis sees a compact digest of demoted findings and *annotates*
  (never demotes) merged findings duplicating a source-refuted one —
  cheap insurance without granting synthesis dedup kill authority it
  hasn't earned (dedup imperfection is a known STATUS.md open issue).
  Later (tracked ticket): symmetric propagation where source-refuted
  contributors can drag merged siblings down.
- Plan doc for (b)+(iii): `../plans/20260731_verdict_lattice_provenance.md`

## Results

- (none this session — design discussion; specimens cited from existing
  07-16 artifacts)

## Open Questions

- Mechanism choice pending design validation: keep the lattice as a
  synthesis-prompt rule, or move merged-verdict computation into
  deterministic post-processing keyed on contributor ids in the synthesis
  schema (testable; removes the can't-distinguish-policy-from-LLM-error
  problem)?
- Should the demoted digest cover all refuted findings or only
  source-refuted ones? (Lean: source-refuted only — targeted, and
  text-only refutations lack the ground-truth standing that makes the
  annotation trustworthy.)
- Checker prompt-compliance under identity collision remains n=1 (carried
  from step 14).

## Captured Tasks

- [#2: Propagate source-refuted verdicts to merged siblings](https://github.com/danparshall/pat-helper/issues/2) — captured 2026-07-31
