# STATUS — pat-helper

Last updated: 2026-07-11

## Current Focus

**Prompt caching implemented (2026-07-11 evening, `abec241`).** The paper is
now a cacheable shared prefix across the lens fan-out AND adversarial verify
(plan steps 1–13; stretch unification deferred). Live smoke: 99.98% of input
tokens read from cache on the second identical-prefix opus call. Fixture
harness gate after the lens-prompt restructure: recall 2/2, 0 gaps. 48 tests
green (11 new). One plan flaw found+fixed in implementation: verify calls have
their own cache prefix (different system prompt), so the verify stage primes
per refuter — priming only the lens stage would have forfeited the verify-stage
savings (two-thirds of run cost). Realized $ savings now observable via a
per-run INFO cache-usage summary; expect ~$23 → ~$8–10 or better on the next
paid v9 run (the flattened v9 paper is ~64k tokens, not the plan's ~44k).
Convo: `docs/convos/main/20260711_prompt_caching_implementation.md`.

Data locations unchanged: `data/` is gitignored (quotes the unpublished
draft) — `data/defects_task_exposure_v9.yaml`, `data/harness_out_v9/`.

Next actions:
1. **Skim the 37 extras** (need Dan) —
   `data/harness_out_v9/harness_2026-07-11.md`. Much more tractable than the
   old 102, includes the two real arithmetic bugs; also input for verifier
   calibration.
2. **Next paid v9 run doubles as the caching measurement** — the INFO
   cache-usage lines give realized savings for free; also the lens-prompt
   placement A/B the plan's Q1 deferred.

Still open: adversarial-verify calibration (18 demoted this run vs 23 on
07-09 — does refutation kill true findings?); OpenAI default pinned to gpt-5.5
pending GPT-5.6 stability (cost-neutral: gpt-5.6-sol is the same $5/$30);
synthesis dedup imperfection (two defects surfaced as match + near-duplicate
extra); `harness/out/` + `data` symlink untracked (cosmetic).

## Recent Sessions

- **2026-07-11 (evening)** — Prompt caching implemented (next-action 1,
  plan steps 1–13; step-14 stretch deferred). TDD: 11 new tests
  (tuple-form contract, prompt equivalence, per-provider request shapes,
  priming order both stages), 48/48 green. Live smoke: 63,935/63,948 input
  tokens cached on call 2. Fixture gate: recall 2/2, 0 gaps. Plan flaw
  found+fixed: verify stage needs its own priming (distinct cache prefix).
  Commit `abec241`. Convo:
  `docs/convos/main/20260711_prompt_caching_implementation.md`.

- **2026-07-11** — Lens upgrades + v9 re-run (next-action 1). Recall
  **10/10** (was 8/10), no regressions; synthesis merged ~100 findings under
  the 64k streamed cap (at-scale proof delivered); recompute directive found
  two real arithmetic bugs in the draft. Fixed in-session regression:
  per-lens cap 16k → 32k (`751b364`) after empirical-rigor × opus hit 16k.
  Cost analysis (~$22–25/run, verify-dominated) → prompt-caching plan
  (`docs/plans/main/20260711_prompt_caching.md`). Lens commits: `c22ee7d`.
  Convo: `docs/convos/main/20260711_lens_upgrades_and_v9_rerun.md`.

- **2026-07-10** — Synthesis truncation fix (next-action 1). Decision convo:
  output arithmetic showed streaming was load-bearing (merged JSON alone
  exceeds 16k at 110 findings), so: Anthropic always streams, 64k synthesis
  cap on all three providers, adaptive thinking kept, `TruncatedOutputError`
  non-retryable + explicit gap. TDD (+2 tests, 37/37 green), live smoke on
  opus-4-8, fixture harness recall 2/2 / 0 gaps / merged report. Convo:
  `docs/convos/main/20260710_synthesis_streaming_fix.md`.

- **2026-07-09 (evening)** — Env hygiene + both harness actions + plan A.
  Gitignored all `.env*`; `data/` → `~/data/pat-helper/` symlink. Fixture
  harness surfaced and fixed two real bugs (Gemini `response_json_schema`
  for `additionalProperties` schemas; `max_output_tokens` 8192→16000 after
  thinking-shared-budget truncation) → recall 2/2, 0 gaps. Plan A landed via
  TDD (35/35 green). Wrote 10 defects for the Task Exposure v9 paper → first
  real recall **8/10**; misses (arithmetic recompute, source-type weight)
  are lens-prompt gaps. Synthesis truncates at 110 findings — top next
  action. Convo: `docs/convos/main/20260709_env_hygiene_harness_runs_and_plan_a.md`.

- **2026-07-09** — Harness prep + v1 hardening. Built `data/task_exposure_v9.tex`
  from `~/code/econ-impact/drafts/CDR_Framework_draft_v9.md` (CDR paper =
  Task Exposure paper, `.tex` is a Markdown→pandoc build artifact). Discovered
  STATUS's "CLI degrades gracefully without keys" claim was empirically false;
  wrote plan for the try/except fix (deferred). Landed 2 companion fixes:
  `load_paper` now strips LaTeX preamble/postamble (–102 lines on the CDR
  paper) and `JUDGE_MODEL` switched to OpenAI (`gpt-5.6-terra`, ~3× cheaper
  than Anthropic Haiku) with a dispatch table in `harness/run.py`. 30/30
  tests green (was 26). Convo: `docs/convos/main/20260709_harness_prep_and_v1_hardening.md`.

- **2026-07-09** — Design brainstorm: worked kickoff's 8 open questions,
  approved pipeline shape C, locked v1 scope, wrote implementation plan,
  began solo build. Convo: `docs/convos/main/20260709_v1_design_brainstorm.md`.

- **2026-07-08** — Kickoff. Added PAT paper + summary to general-ai-abilities.
  Reframed personal-scale goal after Dan surfaced canaryinstitute.ai working
  paper as concrete target. Ran hand-review of the blog-post version and
  surfaced 5 concrete critiques (most notably: "3-month task-horizon doubling"
  citation mismatches Kwa 182d / Gould 373d — closest is EdgeBench ICL which
  is a different construct). Bootstrapped this repo.
  Convo: `docs/convos/main/20260708_pat_kickoff_and_reframe.md`.

## Archived Research Lines

Lines moved to docs/historical/ — not currently active, but available for reference.

| Topic | Summary | Archived | Material |
|-------|---------|----------|----------|
| (none yet) | | | |
