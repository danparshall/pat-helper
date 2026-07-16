# STATUS — pat-helper

Last updated: 2026-07-14

## Current Focus

**Adversarial-verify calibration: first fix landed and measured.** The
`unverifiable` verdict (main, `77ffc4e`) stops paper self-claims from
refuting critiques; verification state now survives synthesis; renderer
tags these "check external artifact" at full severity. Calibration replay
(`harness/reverify.py`, run 1's 18 refuted findings, same refuters):
13 refuted / 3 unverifiable / 1 softened / 1 upheld — **both** pure
self-claim true-kills now survive to the main report (the third suspected
kill turned out to be a legitimate in-text refutation on re-read), no mass
overcorrection. Run 1 would have scored 9/10.

Next: branch `source-check` (plan ready, implementation not started) —
stage 3.5 "strict mode" resolves `unverifiable` findings against
author-supplied source texts. Start at
`docs/active/source-check/plans/20260714_source_check_stage.md`.

Still needing Dan: the extras/demoted skim (carried since 07-12; now also
ground-truth labels for verify calibration — are the 13 still-refuted all
genuinely bad?); Svanberg 2024 + Davidson 2026 PDFs for the source-check
live specimens.

Data locations unchanged: `data/` is gitignored (quotes the unpublished
draft) — `data/defects_task_exposure_v9.yaml`, `data/harness_out_v9/`
(now also `reverify_2026-07-14.md` + checkpoint jsonl). The 07-11 morning
outputs are preserved as `*_2026-07-11_morning_lens_upgrades.md`.

Still open: OpenAI default pinned to gpt-5.5 pending GPT-5.6 stability
(cost-neutral: gpt-5.6-sol is the same $5/$30); synthesis dedup imperfection
(two defects surfaced as match + near-duplicate extra); stretch unification
of verify under SHARED_HEADER still deferred (pure optimization); renderer
drops severity for demoted-appendix entries (forced the all-HIGH reverify
replay — cheap fix, aids future calibration); scope question: is
`unverifiable` right for cited-literature accuracy critiques, or should it
stay narrowly about the paper's own artifacts? (source-check branch will
inform this); `harness/out/` + `data` symlink untracked (cosmetic).

## Active Research Lines

| Branch | Status | Summary |
|--------|--------|---------|
| `source-check` | active | Stage 3.5 "strict mode": resolve `unverifiable` findings by checking the paper's characterization of cited sources against author-supplied extracted texts (local-first, content-indexed, double-gated). Design: `docs/convos/main/20260713_unverifiable_verdict_design.md`. |

## Recent Sessions

- **2026-07-13/14** — Unverifiable verdict + source-check design (top
  next-action). Dissected the circular refutation (verifier cited paper
  self-claims as ground truth); Dan killed the severity-downgrade idea →
  fourth verdict `unverifiable` stays in-report at full severity. Landed
  via TDD (`77ffc4e`, 55/55; synthesis now passes `verified` through).
  Calibration replay (`harness/reverify.py`, `129aa73`): 18/18 of run 1's
  refuted findings, same refuters → 13 refuted / 3 unverifiable /
  1 softened / 1 upheld; both pure self-claim kills recovered (third
  suspect was a legitimate in-text refutation on re-read); run 1 would
  have been 9/10. Then brainstormed stage 3.5 "strict mode" (source-check
  against author-supplied texts) → branch `source-check` opened, plan
  ready, implementation not started.
  Convo: `docs/convos/main/20260713_unverifiable_verdict_design.md`.

- **2026-07-12** — Paid v9 caching measurement (next-action 2). Two runs:
  run 1 hit a swallowed-INFO logging bug (no entry point configured logging;
  fixed via TDD, `b314bcf`, 50/50 green) and recall 8/10 — decomposed into
  one verify true-kill (google refuter cited the paper's own replication-
  package claims; first confirmed "refutation kills true findings" instance)
  and one lens miss. Run 2: **recall 10/10**, realized input-side **$24.42 →
  $5.82 (76% saved)**; hit rates 89.7/85.8/83.1% (anthropic/openai/google).
  Plan Q1 resolves quality-neutral. Verify calibration promoted to top item.
  Convo: `docs/convos/main/20260712_paid_v9_caching_measurement.md`.

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
