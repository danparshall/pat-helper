# Env Hygiene, Harness Runs (Actions 1+2), and Plan A

**Date:** 2026-07-09 (evening session, Dans-MacBook-Pro)
**Branch:** main

## Summary

Executed both STATUS harness actions plus the deferred v1-hardening plan A.
Session opened with env hygiene: `.gitignore` now covers every `.env*`
variant (keeping `.env.example` tracked as the secret-free template), and
`.env` was symlinked to the new `.env.corporate` so `load_dotenv()` finds
keys. The repo's `data/` directory was set up per the claude-researcher
convention as a symlink to `~/data/pat-helper/`, and `task_exposure_v9.tex`
was rebuilt on this machine from `~/code/econ-impact` (the gitignored copy
built on the laptop doesn't sync).

Action 1 (fixture harness) ran three times, each surfacing something. Run 1:
recall 2/2 but all 8 Google cells failed — Gemini's `response_schema` proto
rejects JSON-Schema `additionalProperties`; fixed by switching to
`response_json_schema` (the SDK-documented raw-JSON-Schema field), verified
with a live smoke call. Run 2: recall 2/2, 57 findings (Google now
contributing), but the Anthropic synthesis call truncated its JSON —
adaptive-thinking tokens count against `max_tokens`, and 8192 was too tight;
raised to 16000. Run 3: recall 2/2, 0 gaps, clean merged report. Plan A
(graceful provider degradation) was implemented via TDD between runs:
`_build_providers` returns `(providers, startup_gaps)`, all-providers-failed
is a clean `SystemExit`, and the harness judge is constructed fail-fast
before any review spend. 35/35 tests green, ruff clean.

Action 2 planted 10 real defects in the Task Exposure v9 paper
(`data/defects_task_exposure_v9.yaml`, gitignored because it quotes the
unpublished draft) and ran the full harness: **recall 8/10** with
opus-4-8 / gpt-5.5 / gemini-3.1-pro-preview. The two misses are lens-prompt
gaps, not noise: no model recomputed an arithmetic claim (one finding even
praised the erroneous footnote's "arithmetic transparency"), and no model
flagged an evidentiary-basis swap (Census microdata → unnamed consultancy
survey) under a "first large-scale confirmation" claim.

## Topics Explored

- `.env` hygiene + `data/` → `~/data/pat-helper/` symlink convention
- Gemini structured-output API: `response_schema` vs `response_json_schema`
- Anthropic adaptive-thinking token accounting vs `max_tokens` (checked
  against the claude-api skill reference)
- Plan A implementation (TDD; test quality reviewed by subagent)
- Defect design for the first real recall measurement (10 defects, one per
  lens family where possible)

## Provisional Findings

- **Recall 8/10 on the real paper.** All internal-consistency, framing,
  scoping, and reproducibility defects were caught by at least one lens.
- **Miss 1 — arithmetic:** `workweek-arithmetic` (40h = "4,800 minutes").
  Evidence suggests the empirical-rigor lens should explicitly instruct
  "recompute every derivation in the text"; models currently treat stated
  arithmetic as given.
- **Miss 2 — source quality:** `census-to-vendor-source`. The sources lens
  checks whether claims are sourced, not whether the source *type* can bear
  the claim's weight. Candidate lens-prompt addition.
- **Synthesis truncates at scale.** 110 findings exceeded even the 16000
  output-token cap (thinking shares the budget); findings passed through
  unmerged. Recall is unaffected (judge scores raw findings) but the
  human-facing report is noisy. Fix options: stream the synthesis call with
  a larger cap, disable thinking for synthesis (mechanical dedup), or chunk
  the synthesis. Leaning streaming + `thinking: disabled`, undecided.
- **102 extras** (findings matching no planted defect) are effectively a
  first AI review of the real v9 draft — worth a human skim.

## Decisions Made

- `data/` is a symlink to `~/data/pat-helper/` (matches other repos; writes
  survive worktree cleanup).
- Defects file and harness outputs for the real paper live under `data/`
  (gitignored) because they quote the unpublished draft.
- `max_output_tokens` default raised 8192 → 16000 (non-streaming ceiling).
- Judge construction is fail-fast and happens before the review fan-out.

## Results

All real-paper outputs are machine-local (gitignored, `~/data/pat-helper/`):

- `data/harness_out_v9/harness_2026-07-09.md` — recall table (8/10) + 102
  extras, models: claude-opus-4-8, gpt-5.5, gemini-3.1-pro-preview
- `data/harness_out_v9/review_2026-07-09.md` — full 110-finding review of
  the mutated paper (unmerged due to synthesis truncation)
- `data/defects_task_exposure_v9.yaml` — the 10 planted defects (experiment
  conditions, self-documenting)
- `harness/out/harness_2026-07-09.md` — fixture run 3 (recall 2/2, 0 gaps)

## Open Questions

- Synthesis-at-scale fix: streaming vs thinking-off vs chunking (next
  session's plan-worthy item).
- Lens-prompt upgrades for the two misses: recompute-arithmetic
  (empirical-rigor) and source-type-vs-claim-weight (sources). Re-measure
  recall after changing prompts — the harness now makes that cheap to test.
- Are the 102 extras mostly real critiques or noise? Manual skim needed;
  also relevant for calibrating the adversarial verifier (only 23 of 133
  raw findings were demoted).
- gpt-5.6-sol stability (OpenAI default still pinned to gpt-5.5).
