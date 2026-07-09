# STATUS — pat-helper

Last updated: 2026-07-09

## Current Focus

**v1 implemented, awaiting live validation.** Pipeline shape C built
2026-07-09 (flat fan-out → mechanical quote-check → adversarial verify →
synthesis → markdown): 26 tests green, ruff clean, CLI degrades gracefully
without keys. See `docs/plans/main/20260709_pat_helper_v1_plan.md`.

Next actions (need Dan):
1. Drop API keys in `.env` (see `.env.example`) → run
   `uv run python harness/run.py tests/fixtures/main.tex` (cheap end-to-end
   harness check, 2 planted defects).
2. Drop Task Exposure `.tex` in `data/` → write ~10 real defects → first real
   recall measurement.

Still open: lens-set validation (harness-driven), adversarial-verify
calibration (does refutation kill true findings?), OpenAI default pinned to
gpt-5.5 pending GPT-5.6 stability.

## Recent Sessions

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
