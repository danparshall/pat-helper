# STATUS — pat-helper

Last updated: 2026-07-11

## Current Focus

**Recall 10/10 + synthesis-at-scale proven (2026-07-11).** The lens-prompt
upgrades (recompute-arithmetic in empirical-rigor, source-type-vs-claim-weight
in sources) flipped both v9 misses with zero regressions, and the same paid run
delivered the deferred at-scale proof: ~100 survivors merged to 47 findings
under the streamed 64k cap, no truncation, convergence recorded. Extras
102 → 37 (synthesis dedup working). Out-of-sample bonus: the recompute
directive caught two real arithmetic bugs in the v9 draft (31.6% vs 36.3% D2+;
23,850 vs 23,852 task counts). One in-session regression fixed: per-lens cap
raised 16k → 32k after empirical-rigor × opus hit the old cap. 37 tests green.
Convo: `docs/convos/main/20260711_lens_upgrades_and_v9_rerun.md`.

Cost accounting (same session): ~$22–25 per full run, ~two-thirds of it in
adversarial verify (full paper re-sent per HIGH/MEDIUM finding). Prompt-caching
plan written: `docs/plans/main/20260711_prompt_caching.md` (~$23 → ~$8–10,
zero quality tradeoff).

Data locations unchanged: `data/` is gitignored (quotes the unpublished
draft) — `data/defects_task_exposure_v9.yaml`, `data/harness_out_v9/`.

Next actions:
1. **Implement the prompt-caching plan** —
   `docs/plans/main/20260711_prompt_caching.md`. Verify-stage caching alone is
   most of the dollar win; lens restructure is gated on a fixture-harness run.
2. **Skim the 37 extras** (need Dan) —
   `data/harness_out_v9/harness_2026-07-11.md`. Much more tractable than the
   old 102, includes the two real arithmetic bugs; also input for verifier
   calibration.

Still open: adversarial-verify calibration (18 demoted this run vs 23 on
07-09 — does refutation kill true findings?); OpenAI default pinned to gpt-5.5
pending GPT-5.6 stability (cost-neutral: gpt-5.6-sol is the same $5/$30);
synthesis dedup imperfection (two defects surfaced as match + near-duplicate
extra); `harness/out/` + `data` symlink untracked (cosmetic).

## Recent Sessions

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
