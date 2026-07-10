# STATUS — pat-helper

Last updated: 2026-07-10

## Current Focus

**Synthesis-at-scale fixed (2026-07-10).** The Anthropic provider now always
streams, synthesis gets its own 64k cap (`synthesis_max_output_tokens`) on all
three providers, adaptive thinking stays on, and hitting a cap raises a
non-retryable `TruncatedOutputError` recorded as an explicit gap. 37 tests
green; fixture harness re-validated (recall 2/2, 0 gaps, merged report shows
three-provider convergence). The 110-finding-scale proof is deferred to the
next paid v9 run, bundled with the lens-prompt upgrades. Convo:
`docs/convos/main/20260710_synthesis_streaming_fix.md`.

Prior context: first real recall measurement is 8/10 (10 planted defects in
`data/task_exposure_v9.tex`, opus-4-8 / gpt-5.5 / gemini-3.1-pro-preview).
Defects + outputs live in `data/` (gitignored — they quote the unpublished
draft): `data/defects_task_exposure_v9.yaml`, `data/harness_out_v9/`.

Next actions:
1. **Lens-prompt upgrades from the two misses** — empirical-rigor should
   recompute arithmetic (missed 40h="4,800 minutes"; one finding praised the
   erroneous footnote); sources should test source-type vs claim-weight
   (missed Census→consultancy swap under a "first large-scale confirmation"
   claim). Re-run the real-paper harness after edits — that measures the new
   prompts AND confirms synthesis merges 110+ findings under the 64k cap.
2. **Skim the 102 extras** (need Dan) — findings matching no planted defect
   in `data/harness_out_v9/review_2026-07-09.md` are effectively a first AI
   review of the real v9 draft; also input for verifier calibration.

Still open: adversarial-verify calibration (only 23/133 raw findings
demoted — does refutation kill true findings?), OpenAI default pinned to
gpt-5.5 pending GPT-5.6 stability.

## Recent Sessions

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
