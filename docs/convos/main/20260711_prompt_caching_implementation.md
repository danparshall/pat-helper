# Prompt Caching Implementation (STATUS next-action 1)

**Date:** 2026-07-11 (Dans-MacBook-Pro)
**Branch:** main
**Plan:** [docs/plans/main/20260711_prompt_caching.md](../../plans/main/20260711_prompt_caching.md)

## Summary

Implemented the prompt-caching plan end to end (steps 1–13; stretch unification
deferred). TDD throughout: 11 new tests written first and confirmed RED, then
the `str | tuple[str, str]` user form landed in all three provider clients and
the pipeline was restructured — lens instruction moved from `system` to a
volatile user suffix after the paper, verify's prompt split at the
paper/critique boundary (byte-identical text), and cache-priming barriers added
so the first call per provider writes the cache entry before the fan-out reads
it. 48/48 tests green, ruff clean. Committed as `abec241`.

One design flaw in the plan surfaced during implementation: plan step 5 claimed
priming ONE lens cell per provider would let "all verify calls read the cache,"
but verify calls use a different system prompt than lens calls, and Anthropic's
cache key is a prefix match over tools → system → messages — different system,
different cache entry. Without its own priming, the whole concurrent verify
gather (two-thirds of run cost, the claimed core of the dollar win) would miss.
Fix: the verify stage now primes per refuter with the same barrier pattern as
stage 1. The independent test-quality review agent reached the same conclusion
unprompted. This also means the step-14 stretch (verify under SHARED_HEADER)
is now purely an optimization (one shared cache entry instead of two per
provider), not a prerequisite for the verify-stage savings.

Both live gates passed. Cache smoke on opus-4-8 with the v9 paper: call 2 read
63,935 cached tokens with only 13 uncached (also revealed the flattened v9
paper is ~64k tokens, not the plan's ~44k estimate — projected savings larger
than planned). Fixture harness after the lens-prompt restructure: recall 2/2,
0 gaps, 14 findings, 4 demoted — the prompt move out of `system` did not cost
recall on the fixture.

## Topics Explored

- Anthropic prefix-cache semantics: cache entry readable only after the
  writing request starts streaming → concurrent identical calls all miss →
  priming barriers; system prompt participates in the prefix → verify needs
  its own priming (the plan's gap)
- Test-suite integrity hazard: existing tests did `assert X not in user`;
  with `user` becoming a tuple, `in` silently degrades to element equality
  and those assertions become no-ops — added `_user_text()` normalizer and
  routed the three affected tests through it
- Test-quality review by subagent (TDD skill step 2): one weak assertion
  found (lens-suffix set-membership couldn't catch cross-contamination) and
  fixed by requiring exactly-one-lens-per-suffix + bijection

## Provisional Findings

- **Cache mechanism verified live**: 63,935 / 63,948 input tokens (99.98%)
  read from cache on the second identical-prefix opus call; at $5/MTok →
  $0.50/MTok cached, that's the ~90% input discount the plan projected
- **Fixture-harness gate passed post-restructure** (recall 2/2, 0 gaps) —
  necessary-not-sufficient evidence the lens-instruction move is
  quality-neutral; the fixture is small and in-sample, the next paid v9 run
  measures it for real (and now also measures actual $ savings via the new
  per-run INFO cache-usage summary)
- The v9 paper flattens to ~64k tokens, not ~44k — the plan's ~$23 → ~$8–10
  projection was based on the smaller number, so realized savings should be
  at least as good
- Priming semantics also serialize on dead providers: a provider that fails
  its priming cell delays fan-out by its retry time (~seconds). Accepted —
  bounded, and only when a provider is already failing

## Decisions Made

- Verify-stage priming added beyond the plan's letter (rationale above) —
  the plan's own fallback logic made this the conservative choice
- Plan Q1 (A/B the lens-prompt move?): fixture gate only, per the plan's own
  recommendation — the next paid run measures it for free
- Plan Q2 (cache summary in rendered report?): log-only for now (YAGNI);
  INFO line per provider per run
- Plan Q3 / step 14 (stretch unification of verify under SHARED_HEADER):
  **deferred** — each iteration needs another paid harness gate, the verify
  calibration work (STATUS open item) will touch those prompts anyway, and
  verify-priming already banks the verify-stage savings
- Code committed directly to main per repo convention: `abec241`

## Results

- `harness/out/harness_2026-07-11.md` — fixture harness post-restructure:
  recall 2/2, 0 gaps (untracked dir, same as prior runs)
- Live smoke transcript in-session (not persisted): cache read 63,935 tok on
  call 2
- Code: `abec241` (providers tuple form + pipeline restructure + 11 tests)

## Open Questions

- Realized $ savings on a full v9 run — the INFO cache-usage summary now
  makes this observable; expect ~$23 → ~$8–10 or better
- Stretch unification (one cache entry per provider instead of two) —
  deferred; revisit with verify calibration
- OpenAI/Gemini automatic caching efficacy under our call pattern — now
  measurable via the same logging; if they were already caching
  pre-restructure, the plan noted savings are already partly banked
- Carried from 07-11 morning session: the 37-extras skim (needs Dan),
  adversarial-verify calibration, gpt-5.6 default switch

## Handoff (added at session close)

> "Read `docs/convos/main/20260711_prompt_caching_implementation.md`, then run
> the paid v9 harness (`uv run python harness/run.py data/task_exposure_v9.tex
> --defects data/defects_task_exposure_v9.yaml --out data/harness_out_v9`) —
> it doubles as the caching measurement: check the INFO cache-usage lines
> against the ~$23 → ~$8–10 projection, confirm recall holds at 10/10 (this is
> the real-paper A/B for the lens-prompt move, plan Q1), and update STATUS
> with realized savings. Stretch unification (plan step 14) stays deferred."

Caveats attached to the handoff:
- The `--defects`/`--out` flags were reconstructed from the usage docstring
  and STATUS data locations — the next agent should `--help` first.
- The 37-extras skim is Dan's, not an agent's; if the paid run regenerates
  `data/harness_out_v9/harness_2026-07-11.md`, skim or preserve the old one
  first.
- No urgency: nothing is blocked on the paid run (~$8–10 if caching
  delivers, ~$23 if it doesn't) — fire it when the measurement is wanted.
