# STATUS — pat-helper

Last updated: 2026-07-09

## Current Focus

**v1 implemented, awaiting live validation.** Pipeline shape C built
2026-07-09 (flat fan-out → mechanical quote-check → adversarial verify →
synthesis → markdown): 30 tests green, ruff clean. See
`docs/plans/main/20260709_pat_helper_v1_plan.md` and the v1-hardening plan
`docs/plans/main/20260709_v1_hardening_try_except.md`.

Task Exposure `.tex` staged: `data/task_exposure_v9.tex` (built from
`~/code/econ-impact/drafts/CDR_Framework_draft_v9.md` via that repo's
Makefile, 2026-07-09).

Next actions (need Dan):
1. Drop API keys in `.env` (see `.env.example`) → run
   `uv run python harness/run.py tests/fixtures/main.tex` (cheap end-to-end
   harness check, 2 planted defects). Judge is OpenAI now, so
   `OPENAI_API_KEY` is the strictly required one for the harness.
2. Write ~10 real defects for `data/task_exposure_v9.tex` → first real
   recall measurement.
3. Implement graceful-degradation plan A when context allows — spec at
   `docs/plans/main/20260709_v1_hardening_try_except.md`. Not blocking the
   harness runs above, but the fixture run currently hard-crashes without
   all three keys present (only fires the fan-out cells whose keys exist
   *after* A lands).

Still open: lens-set validation (harness-driven), adversarial-verify
calibration (does refutation kill true findings?), OpenAI default pinned to
gpt-5.5 pending GPT-5.6 stability.

## Recent Sessions

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
