# STATUS — pat-helper

Last updated: 2026-07-12

## Current Focus

**Caching measured for real: input-side $24.42 → $5.82 (76% saved), recall
10/10 (2026-07-12 paid v9 run).** Per-provider cache hit rates: anthropic
89.7%, openai 85.8%, google 83.1% of input tokens — the ~$23 → ~$8–10
projection is confirmed (realized input spend $5.82 + output). OpenAI/Gemini
implicit caching is now measurably working under our call pattern. Numbers
assume openai cached=0.1× and gemini cached=0.25× published discounts;
anthropic figure slightly understates cost (cache-write 1.25× premium folded
into the uncached bucket, bound ≤ $0.24).

It took two paid runs to get the measurement. **Run 1 (07-11 evening): the
INFO cache-usage lines never appeared** — no entry point ever configured
logging, so Python's default WARNING handler silently dropped the summary
(the 07-11 live smoke worked only because it was an ad-hoc script). Root
caused + fixed via TDD in `b314bcf` (`configure_logging()` on the package
logger, wired into cli.py and harness/run.py; 50/50 green). Run 1 also came
in at **recall 8/10**, which decomposed instructively:

- `model-versions-removed` was **found by the lens then refuted by the
  google adversarial verifier**, which cited the paper's own
  replication-package self-claims as ground truth — circular. First
  confirmed instance of the "does refutation kill true findings?" worry,
  and it cost a recall point. The same finding survived verify in both the
  morning run and run 2 → verifier stochasticity, not the caching change
  (verify prompts are byte-identical pre/post-restructure).
- `beta-construct-swap` was genuinely missed in run 1 (no trace anywhere),
  hit in the morning run and run 2 → lens stochasticity.
- Finding volume was stable across all three runs (37/43/44 issues) — the
  lens-instruction move out of `system` did not thin coverage.

So plan Q1 (real-paper A/B of the lens-prompt move) resolves **quality-
neutral**: 10/10 post-restructure, and run 1's dip is attributable to
per-run noise, one point of it specifically to verify miscalibration.
Convo: `docs/convos/main/20260712_paid_v9_caching_measurement.md`.

Data locations unchanged: `data/` is gitignored (quotes the unpublished
draft) — `data/defects_task_exposure_v9.yaml`, `data/harness_out_v9/`.
The 07-11 morning outputs are preserved as
`*_2026-07-11_morning_lens_upgrades.md` (backed up before the same-date
rerun would have clobbered them).

Next actions:
1. **Adversarial-verify calibration is now the top item** — it has a
   confirmed true-kill with a reproducible failure mode (verifier treats
   the paper's self-claims as ground truth when refuting). The demoted
   appendices of all three 07-11/07-12 runs are the calibration corpus.
2. **Skim the extras** (need Dan) — morning backup
   `harness_2026-07-11_morning_lens_upgrades.md` (37 extras) and/or the
   fresh `harness_2026-07-12.md`; also input for verifier calibration.

Still open: OpenAI default pinned to gpt-5.5 pending GPT-5.6 stability
(cost-neutral: gpt-5.6-sol is the same $5/$30); synthesis dedup imperfection
(two defects surfaced as match + near-duplicate extra); stretch unification
of verify under SHARED_HEADER (plan step 14) still deferred — now a pure
optimization (~one extra cache entry per provider); `harness/out/` + `data`
symlink untracked (cosmetic).

## Active Research Lines

| Branch | Status | Summary |
|--------|--------|---------|
| `source-check` | active | Stage 3.5 "strict mode": resolve `unverifiable` findings by checking the paper's characterization of cited sources against author-supplied extracted texts (local-first, content-indexed, double-gated). Design: `docs/convos/main/20260713_unverifiable_verdict_design.md`. |

## Recent Sessions

- 2026-07-16/17: [source-check] step 15 live specimens — plan Part C
  complete. Davidson: refuted (Dan: correct). Svanberg: narrowed → softened
  after four live-caught TDD fixes (LaTeX-tie citation extraction; Gate B
  rejected-quote logging; new `critique-narrowed` resolution → softened;
  page-furniture stripping in load_text_source), 95/95 green. Dan's ground
  truth: partially-valid critiques must survive as reminders, not demote.
  Carried open: verdict-lattice/provenance question.
  Convo: `docs/active/source-check/convos/20260716_step15_live_specimens.md`.

- 2026-07-16: [source-check] implemented stage 3.5 (Parts A+B, TDD, 85/85
  green) and passed the step-14 fixture gate (recall 3/3, citation-mismatch
  defect resolved 2 upheld/0 refuted/0 unresolved) after the gate caught two
  live plumbing bugs (quote-first extraction; name-token identity matching).
  Svanberg/Davidson PDFs now in papers/ (main worktree) — step 15 next.
  Convo: `docs/active/source-check/convos/20260716_source_check_implementation.md`.

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
