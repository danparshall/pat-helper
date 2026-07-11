# Lens Upgrades and v9 Re-run (STATUS next-action 1)

**Date:** 2026-07-11 (Dans-MacBook-Pro)
**Branch:** main

## Summary

Executed the lens-prompt upgrades for the two v9 misses and re-ran the real-paper
harness. Recall went **8/10 → 10/10** with zero regressions on the other eight
defects, and the run doubled as the deferred synthesis-at-scale proof: ~100
survivors merged to 47 findings under the streamed 64k cap with no synthesis
truncation and per-finding convergence recorded. Extras dropped 102 → 37 —
mostly synthesis dedup actually working now that it doesn't truncate, not fewer
raw findings.

The prompt upgrades were built from the judge's miss diagnostics: empirical-rigor
got an explicit RECOMPUTE directive (recompute every derived number, verify
stated input→result chains, show the recomputation in evidence) plus a
POSITIVE-severity guard (never praise a passage whose numbers you haven't
recomputed — the 07-09 run had *praised* the erroneous footnote as "a model of
traceable sourcing"). Sources got a source-type-vs-claim-weight capacity check
(can this KIND of source, even in principle, bear this STRENGTH of claim?),
explicitly decoupled from how the sentence characterizes the source — the lens
had already flagged consultancy provenance elsewhere, so the miss was a
capacity question, not a disreputable-source question.

One regression introduced and fixed in-session: the recompute directive made
empirical-rigor × opus verbose enough (thinking + recomputations) to hit the
16k per-lens output cap — the run's single coverage gap (recall survived via
GPT/Gemini redundancy). Root cause was a stale constraint: 16k was the
non-streaming ceiling, but Anthropic always streams since 2026-07-10, and a cap
is not spend. Raised to 32k. Session closed with a cost analysis (~$22–25/run,
adversarial verify is two-thirds of it) and a plan doc for prompt caching.

## Topics Explored

- Judge diagnostics for the two 07-09 misses (workweek-arithmetic,
  census-to-vendor-source) — both were lens-instruction gaps, not capability gaps
- Prompt-upgrade design: recompute-arithmetic directive; source capacity vs
  claim strength; POSITIVE-severity guards in both lenses
- Synthesis-at-scale validation riding along on the same paid run
- Per-run cost accounting: current prices (opus-4-8 $5/$25, gpt-5.5 $5/$30,
  gemini-3.1-pro $2/$12 per MTok), stage-by-stage estimate, verify dominance
- Prompt caching as a zero-quality-tradeoff cost lever (→ plan doc)

## Provisional Findings

- **Recall 10/10** (`data/harness_out_v9/harness_2026-07-11.md`), both former
  misses flipped with the capacity/recompute reasoning stated explicitly in the
  findings. In-sample caveat: the prompts were patched *from* these two defects,
  so the flips are necessary-not-sufficient evidence.
- **Out-of-sample signal is stronger**: the recompute directive found two real
  (unplanted) arithmetic bugs in the v9 draft — text claims 31.6% of labor time
  at D2+ vs Table 6 summing to 36.3%; task count flips between 23,850 and
  23,852 across sections. No flood of low-value arithmetic findings in extras.
- **Synthesis at scale works**: no truncation at the 64k streamed cap on a real
  ~100-finding merge; convergence recorded ("most convergent finding across
  every lens and model" on abstract-overclaim). Extras 102 → 37 reflects dedup
  working, with some residual imperfection (workweek and census findings each
  appear both as a matched finding and as a near-duplicate extra).
- **Cost structure**: ~$22–25 per full harness run; adversarial verify is
  ~two-thirds because `pipeline._verify` re-sends the full ~44k-token paper per
  HIGH/MEDIUM finding. Verify calls are cache-ready today (fixed system prompt,
  paper-first user prompt); lens calls are not (per-lens system precedes the
  paper in the cache prefix).
- Dan's `personal_info.md` price table is stale for OpenAI: gpt-5.5 is $5/$30,
  not the listed gpt-5.2 $1.75/$14. gpt-5.6-sol inherits $5/$30, so the pending
  OpenAI default switch is cost-neutral.

## Decisions Made

- Lens upgrades committed as `c22ee7d` (empirical-rigor + sources)
- Per-lens output cap raised 16k → 32k as `751b364` (no new test — asserting a
  config literal is a testing anti-pattern; existing 37 cover the plumbing)
- Prompt-caching restructure planned, not implemented:
  `docs/plans/main/20260711_prompt_caching.md`
- The 110-finding-scale synthesis proof is considered delivered

## Results

- `data/harness_out_v9/harness_2026-07-11.md` — recall 10/10, 37 extras
  (gitignored: quotes the unpublished draft)
- `data/harness_out_v9/review_2026-07-11.md` — merged report, 47 findings,
  18 demoted, 1 gap (the 16k lens-cap failure, since fixed)
- Code: `c22ee7d` (lens prompts), `751b364` (32k cap)

## Open Questions

- **The 37 extras skim (needs Dan)** — now includes two real arithmetic bugs in
  the v9 draft; much more tractable than the 07-09 run's 102
- Adversarial-verify calibration still open (does refutation kill true
  findings?) — today only 18 demoted, worth comparing against 07-09's 23
- Prompt caching plan awaits implementation (see plan doc)
- Synthesis dedup imperfection: two planted defects each surfaced as matched
  finding + near-duplicate extra — cosmetic for recall, but inflates extras
- `harness/out/` and the `data` symlink remain untracked (cosmetic, flagged
  2026-07-10)
