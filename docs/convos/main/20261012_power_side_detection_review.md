# 20261012_power_side_detection_review

**Date:** 2026-10-12 → 2026-10-14
**Branch:** main
**Surface:** claude-code
**Machine:** Dans-MacBook-Air
**Session:** Dan (air, pat-helper, 20261012T2355, opus-5.5) · /Users/dan/.claude/projects/-Users-dan-code-pat-helper/1862baee-a6de-4635-8ff3-ca67a0307dd0.jsonl · —

## Summary

First use of pat-helper on a paper other than Task Exposure v9: the
power-side-detection annotated outline (`data/power-side-detection_20261008.tex`,
~11.5k words, private draft — "do not cite or forward"; data/ stays gitignored
for that reason, and this doc paraphrases rather than quotes). Dan chose
**Anthropic only** and the **July default models** (opus-4-8), so the run is
comparable in model terms to the v9 runs but has no cross-model verify and no
convergence signal.

Getting a clean run took three attempts, all billing problems. The repo had no
`.env` linked; the only env file in `~/data/_envs/pat-helper/` turned out to be
corporate keys accidentally copied from econ-impact (Dan renamed it
`.env.corporate.ACCIDENTAL-FROM-ECON-IMPACT`). Run 1 on Dan's personal key ran
5 of 8 lenses before the credit ran out (prior-work, argumentation,
reproducibility and synthesis failed). Run 2 on a new `PAPER_ASSISTANT_KEY`
failed instantly with zero tokens (no credit in that org yet). Run 3, after
Dan added funds, completed: 8/8 lenses, synthesis merged, 33 findings, 0 gaps.

Dan then asked that the paper-assistant key be dedicated to PAT. Implemented
via TDD (`65836a3`): the Anthropic provider reads only `PAPER_ASSISTANT_KEY`
and refuses to fall back to `ANTHROPIC_API_KEY`, so a run can't silently bill a
general-purpose key again.

## Topics Explored

- Running the CLI single-provider: stage 3 (adversarial verify) is skipped
  entirely when `len(providers) == 1`, since the refuter must be a different
  model. Findings go straight to the report, unverified.
- Credit is per Anthropic organization, not per key: a new key in the same org
  doesn't help.
- Output filenames are date-only, so a same-day re-run overwrites — used a
  separate `run2_full/` folder.
- Hand triage of the 33 findings (Claude's read, not checked against the full
  draft).

## Provisional Findings

About the draft (leads, not verdicts — single model, unverified):
- Strongest: the headline "smallest island can often be identified" outruns
  the body (three-phase balancing is a free counter); the band setting was
  chosen with the test half in view; the energy-balance zero depends on an
  in-sample fitted weight; the single-phase result is strongest on balanced
  campus load and untested on residential feeders; one workload.
- Best new finding from the lenses that failed in run 1: no engagement with
  the non-intrusive load monitoring (NILM) literature.
- Framing: privacy/civil-liberties of premises-level grid monitoring is
  unacknowledged — relevant to Dan's coalition goals.
- Claude disputed two: the 5.5 MVA instability finding's reasoning ("reverse
  should detect at least as well") doesn't follow, though the instability is
  real; the Llama 3 linear-scaling critique, if anything, strengthens the
  draft's "crashes are rare" point (from memory: most Llama 3 interruptions
  were per-GPU hardware faults).
- Unchecked model arithmetic: the re-derived crossing range (91–154 kVA).

About the tool:
- Single-provider mode is usable for a first pass but loses both of the
  design's quality signals (verify, convergence). Run 3 cache: 247k cached /
  60k uncached input tokens.
- The synthesis merge noticeably helps single-provider output: run 1
  (unmerged) flagged the headline three times; run 3 once.

## Decisions Made

- `PAPER_ASSISTANT_KEY` is the only Anthropic key pat-helper uses (`65836a3`,
  59/59 green; README + `.env.example` updated).
- Anthropic-only, July default models for this review.

## Results

Kept in gitignored `data/` (they quote the private draft):
- `data/harness_out_power_side/review_power-side-detection_20261008_2026-10-13.md`
  — run 1, partial (5/8 lenses, unmerged, 31 findings)
- `data/harness_out_power_side/run2_full/review_power-side-detection_20261008_2026-10-14.md`
  — run 3, complete (33 findings) — **the one to use**
- `data/harness_out_power_side/run2_full/review_power-side-detection_20261008_2026-10-13.md`
  — run 2, empty (8 billing gaps)
- Logs alongside each.

## Addendum (2026-10-14, same session)

- **Applying the findings / citation checks.** The sources lens checks no
  citations; it can only see the draft's own tags. Spun off branch
  `paper-finder` (see its convo `20261014_paper_finder_kickoff.md`) and a new
  repo `~/code/paper-library` to get the cited sources.
- **Contamination.** This session read the verification repo's own
  power-side claim check (summary, ~5 ledger rows, STATUS entry) and proposed
  it as ground truth. Dan rejected that: pat-helper must not compare notes
  with other citation checks. The rule now in CLAUDE.md: other repos'
  `PAPER_INDEX.md`, `PAPER_SUMMARIES.md`, `papers/` and `papers/text/` are
  freely readable; other checks/reviews/audits of a draft under review are
  off limits. This session's judgments about the power-side report's
  substance are not independent — calibration needs a clean session.
- **Headline discussion** (before the contamination): "can often" is hedged,
  not "always"; Dan: Rahman's prior was that power monitoring is impossible,
  so "surprisingly" is earned. Suggested reframe: lead with the existence
  result against Rahman's claim; "often" is the weak word against an
  adaptive evader.
- **Hard-constraint facts.** A web agent found ODEC's radial 69 kV planning
  caps (10,000 consumers, 50 MW, 700 MW-miles); Dan and Claude reasoned from
  them (night noise floor, flat load invisible in aggregates → AMI, service
  area, thermal search, Kyllo/Naperville). Filed as verification#71; Dan
  asked that such facts be actively sought and surfaced → standing guidance
  in dotfiles `personal_info.md` (`22518d6`).
- **Keys.** `.env.personal` (via `~/data/_envs/pat-helper/.env`) holds
  `ANTHROPIC_API_KEY` (Dan's personal key, no longer read by pat-helper) and
  `PAPER_ASSISTANT_KEY` (the only Anthropic key pat-helper uses). No OpenAI or
  Gemini key is configured, so multi-provider runs — and with them the
  adversarial-verify stage — are unavailable until Dan adds personal keys
  (`OPENAI_API_KEY`, `GEMINI_API_KEY`). The corporate file was quarantined
  as `.env.corporate.ACCIDENTAL-FROM-ECON-IMPACT`.

## Open Questions

- Single-provider verify: worth a same-model refuter mode, or is that too weak
  to bother (a model is worse at spotting its own blind spots)?
- Should output filenames include a time or run id so same-day re-runs don't
  collide?
- Model defaults are still the July set; refresh (with comparability cost)?
- Is the review report worth re-running multi-provider once Dan decides how
  widely the private draft can go to other vendors? (Needs personal OpenAI
  and Gemini keys first.)
- Should OpenAI/Gemini also get dedicated pat-helper key names, like
  `PAPER_ASSISTANT_KEY`, so a run can't bill a general-purpose key?
