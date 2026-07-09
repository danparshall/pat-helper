# v1 design brainstorm — pipeline shape approved, scope locked

**Date:** 2026-07-09
**Branch:** main
**Prior convo:** `docs/convos/main/20260708_pat_kickoff_and_reframe.md`
**Plan produced:** `docs/plans/main/20260709_pat_helper_v1_plan.md`

## Summary

Brainstorming session that worked through the kickoff doc's 8 open questions
and converged on an approved v1 design. Dan answered the three questions only
he could answer (draft format, output form, v1 scope); Claude took positions
on the rest, several of which pushed back on the kickoff doc's framing. Dan
approved pipeline shape "C" and authorized solo implementation.

Key reframings this session (provisional, but design-load-bearing):

- **The binding constraint is Dan's attention, not API cost.** 8 lenses × 3
  models ≈ a few dollars/run at personal scale. The kickoff's worry about N×M
  cost was misplaced; the real risk is a 60-item finding flood that gets
  ignored by draft 3. Triage/dedup quality is the design problem.
- **Convergence ≠ truth.** Models share training data and reviewer-boilerplate
  instincts; convergent critiques can be convergent pattern-matching (e.g.,
  all three models reflexively saying "add confidence intervals").
  Divergence→subjective is a more reliable inference than convergence→real.
  Pedagogical framing updated accordingly: teach "agreement across models is
  *weak* evidence — here's how to check it against the quote."
- **PAT's segmenter+budgeter solve a scale problem we don't have.** Dropped
  both stages; replaced with rigor machinery (quote grounding + adversarial
  verification) targeting PAT's own documented weakness (only 55–65% of pilot
  authors rated feedback as grounded).

## Decisions Made

1. **Input format: LaTeX/Overleaf** (Dan drafts in LaTeX). Loader resolves
   `\input`, strips comments, keeps a line map for anchoring.
2. **Output: markdown review file** per run — diffable across drafts, same
   output path for CLI and future Colab.
3. **v1 scope:** core loop + **planted-error validation harness**. Deferred:
   reference-corpus cross-ref, web-search citation grounding, Colab frontend
   (architecture leaves seams for all three).
4. **Pipeline shape C (approved):** flat fan-out (full paper to every
   lens×model call, 24 async calls) → **mechanical quote-check** (string/fuzzy
   match; ungrounded findings demoted to an appendix, not silently dropped —
   itself a teachable artifact) → **adversarial verify** on HIGH/MED findings
   with a *different* model as refuter → one flagship **synthesis** call
   (dedup/merge/rank, records convergence) → deterministic markdown renderer
   (code, not model, so provenance can't be dropped).
5. **Plain Python + asyncio, not the Claude Code Workflow tool** — Workflow is
   Claude-Code-locked and would kill the shippable-teaching-artifact goal.
6. **Package layout:** `pat_helper/` (latex.py, lenses/*.md, providers/,
   models.py, quotecheck.py, pipeline.py, report.py, cli.py) + tests/ +
   harness/. Lens prompts are plain .md data files — the teaching surface.
7. **Validation: planted-error harness** — inject ~10 specified defects into a
   copy of Dan's paper, measure recall via LLM-judge matching. Chosen over
   "Dan acted on critiques" (confounds usefulness with correctness).

## Provisional Findings

- None empirical yet — this was a design session. The claims above (attention
  as constraint, convergence≠truth) are arguments, not measurements; the
  planted-error harness exists to convert them into measurements.

## Open Questions

- Lens set (8 lenses) still unvalidated — harness results should drive
  consolidation, not a priori arguments.
- Need Dan's `.tex` source of the Task Exposure paper for the live harness run
  (Dan is looking for it; will land in `data/`).
- Adversarial-verify calibration: does refutation pressure kill true findings?
  Harness will show this as recall loss vs. the no-verify ablation.
- Where the deferred corpus cross-ref plugs in (likely: extra context handed
  to the prior-work lens only).

## Session Notes

- YOLO mode; Dan authorized solo implementation after design approval.
- Worktree skipped deliberately (fresh repo, sole active line) — noted as an
  explicit deviation from the brainstorming skill's Phase 4.
- claude-exit verification ceremony ran clean at session start.
