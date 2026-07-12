# Paid v9 Caching Measurement (STATUS next-action 2)

**Date:** 2026-07-11 evening → 2026-07-12 (Dans-MacBook-Pro)
**Branch:** main
**Handoff from:** [20260711_prompt_caching_implementation.md](20260711_prompt_caching_implementation.md)

## Summary

Ran the paid v9 harness to measure realized caching savings and confirm recall
(the real-paper A/B for the lens-prompt move, plan Q1). It took two runs. Run 1
(07-11 ~22:05 UTC) exposed a logging bug — the per-run INFO cache-usage summary
was silently dropped because no entry point ever configured Python logging, so
the measurement data died in-process — and came in at recall 8/10. Root-caused
and fixed the logging via TDD (`configure_logging()` on the `pat_helper`
logger, wired into both cli.py and harness/run.py, commit `b314bcf`; the
test-quality subagent caught that my entry-point test asserted interior logger
state and could pass with the bug intact, so it was strengthened to a full
fake-SDK e2e run asserting "cache usage" reaches stderr; 50/50 green).

Run 2 (07-12 ~00:25 UTC, after Dan approved the ~$8–10 respend) delivered both
measurements: **recall 10/10** and realized input-side cost **$5.82 vs $24.42
uncached-equivalent (76% saved)** — the plan's ~$23 → ~$8–10 projection is
confirmed. The run-1 recall dip decomposed into verifier noise (one
found-then-refuted defect) and lens noise (one genuine miss), with finding
volume stable across all three runs — no evidence the caching restructure hurt
quality.

## Topics Explored

- Realized cache economics per provider (run 2 INFO lines):

  | provider | cached tok | uncached tok | hit % | no-cache $ | with $ | saved $ |
  |---|---:|---:|---:|---:|---:|---:|
  | anthropic (opus-4-8) | 1,671,351 | 191,002 | 89.7% | 9.31 | 1.79 | 7.52 |
  | openai (gpt-5.5) | 1,913,088 | 315,437 | 85.8% | 11.14 | 2.53 | 8.61 |
  | google (gemini-3.1-pro-preview) | 1,649,337 | 334,418 | 83.1% | 3.97 | 1.49 | 2.47 |
  | **total input-side** | | | | **24.42** | **5.82** | **18.60 (76%)** |

  Pricing assumptions: anthropic $5/MTok input with 0.1× cache read
  (skill-verified); openai $5/MTok with 0.1× cached (published gpt-5-family
  discount, assumed); google $2/MTok with 0.25× implicit-cache discount
  (gemini-3-pro reference price applied to the 3.1 preview, assumed).
  Anthropic caveat: the client folds cache-*write* tokens (billed 1.25×) into
  the uncached bucket, so $1.79 slightly understates true cost (bound ≤ $0.24).
- Run-1 recall forensics: per-lens finding counts morning vs evening (37 vs 43
  issues — no coverage collapse), demoted-appendix search for the two misses,
  and the defect yaml definitions.
- The swallowed-INFO root cause: `pipeline.py` logs on `logging.getLogger
  ("pat_helper")`; neither entry point called any logging config; Python's
  last-resort handler drops < WARNING. The 07-11 live smoke only worked
  because it was an ad-hoc script.
- Judge scope: harness scores only surviving `run.findings` — found-then-
  demoted counts as MISS by design, which is what makes verify kills visible
  in recall.

## Provisional Findings

- **Plan Q1 resolves quality-neutral**: recall 10/10 post-restructure on the
  real paper (run 2); run 1's 8/10 attributable to per-run noise. Finding
  volume across morning/run-1/run-2: 37/43/44 issues + 10/11/11 strengths.
- **First confirmed verify true-kill**: run 1's `model-versions-removed` was
  found by the openai reproducibility lens (grounding 1.00) and refuted by the
  google verifier, which cited the paper's own "complete replication package"
  self-claims as ground truth — circular reasoning, since the critique was
  that the named versions were removed. The same finding survived verify in
  the morning run and run 2 (byte-identical verify prompts) → verifier
  stochasticity/miscalibration, not a caching regression. The demoted
  appendices of the three runs are a ready-made calibration corpus.
- `beta-construct-swap` (run 1's other miss) left no trace in findings,
  strengths, or demoted — a genuine lens miss that run; hit in both other runs.
- OpenAI and Gemini implicit caching demonstrably works under our priming
  call pattern (85.8% / 83.1% hit rates) — no explicit cache API needed.
- Cache-read discount asymmetry: google saves less per token (0.25× vs 0.1×),
  making it ~26% of realized input spend despite the lowest base price.

## Decisions Made

- Rerun approved by Dan (~$8–10) over console-only recovery; run 1's cache
  numbers are unrecoverable locally (in-memory counters died with the process;
  provider consoles could still corroborate if wanted).
- Logging fix committed directly to main per repo convention: `b314bcf`.
- Morning outputs backed up as `*_2026-07-11_morning_lens_upgrades.md` before
  the same-date rerun could clobber them (handoff caveat honored); run 1
  outputs live at `*_2026-07-11.md`, run 2 at `*_2026-07-12.md`.
- Adversarial-verify calibration promoted to top next action in STATUS (now
  has a confirmed failure mode: verifier treats paper self-claims as ground
  truth when refuting).
- Stretch unification (plan step 14) stays deferred, per handoff.

## Results

- Savings table above (source: run 2 INFO cache-usage lines; computation
  script was /tmp/cache_savings.py, transcript-only)
- `data/harness_out_v9/harness_2026-07-12.md` — recall 10/10, extras list
- `data/harness_out_v9/review_2026-07-12.md` — 44 issues + 11 strengths,
  15 demoted
- `data/harness_out_v9/harness_2026-07-11.md` / `review_2026-07-11.md` —
  run 1 (recall 8/10, 43 issues, 21 demoted incl. the refuted true finding)
- Code: `b314bcf` (configure_logging + 2 tests)

## Open Questions

- Verify calibration: how often does refutation kill true findings, and does
  prompting the verifier to distinguish "paper claims X exists" from "X is
  demonstrated in the text" fix the circular-refutation mode?
- Whether google's aggressive "the paper already addresses this elsewhere"
  refutation style is a per-model trait worth balancing (rotate refuter
  assignments?) — 3 of 3 sampled run-1 refutations were google.
- Output-side spend is still unmeasured (cache counters cover input only);
  total realized run cost = $5.82 input + output. A usage-console check
  would close this if Dan wants the full number.
- Carried: the extras skim (Dan), gpt-5.6 default switch, synthesis
  near-duplicate dedup.
