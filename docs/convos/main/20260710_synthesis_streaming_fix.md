# Synthesis Streaming Fix (STATUS next-action 1)

**Date:** 2026-07-10 (Dans-MacBook-Pro)
**Branch:** main

## Summary

Executed STATUS next-action 1: synthesis truncation at scale. Session opened
with the options discussion the handoff called for. Key reframing: the
arithmetic shows thinking-off alone would never have fixed the truncation —
110 survivors merged to ~70 unique findings at ~250 tokens each is ~17.5k
output tokens, over the 16k cap *before any thinking spend*. So the cap had to
rise, and the Anthropic SDK requires streaming above ~16k, which makes
streaming the load-bearing fix rather than one of three coequal options. Once
streaming removes the budget contention, disabling adaptive thinking solves
yesterday's problem — it stays on (dedup/merge/severity-ranking are judgment
calls; the marginal cost is ~$0.15–0.25/run). Chunked synthesis deferred as
premature below ~500 findings (it breaks cross-chunk dedup without a
merge-of-merges pass). Dan approved this recommendation.

Implemented via TDD (2 new pipeline-boundary tests, subagent-reviewed: PASS on
all quality criteria; 37/37 green, ruff clean). One scope addition beyond the
approved recommendation, flagged to Dan: `TruncatedOutputError` is never
retried — truncation is deterministic for a given input, and each futile
synthesis retry at the 64k cap would burn ~$1.60 of Opus output tokens.

Verified three ways: live smoke test on claude-opus-4-8 (streamed structured
output OK; deliberate cap=128 raised `TruncatedOutputError` cleanly), full
test suite, and a fixture harness run — recall 2/2, 0 gaps, 17 findings, and
the merged report shows convergence recorded across all three providers
(synthesis merged, not passed through).

## Topics Explored

- Streaming vs thinking-off vs chunking for synthesis at scale (output-size
  arithmetic settled it; checked against the claude-api skill reference)
- Multi-provider symmetry: synthesis routes to the *first healthy* provider,
  so the cap override and truncation detection went into all three clients
- Where the synthesis cap lives: config field + per-call `max_output_tokens`
  override on `complete_json` (provider instances are built once with a single
  cap, so per-call override is the simpler plumbing)
- Retry semantics for deterministic failures (truncation ≠ transient error)

## Provisional Findings

- **Streamed structured output works on opus-4-8**: `messages.stream(...)` +
  `get_final_message()` with `output_config` json_schema returns identical
  shape to `messages.create` — drop-in change.
- **Truncation is now a named, diagnosable failure** on all three providers
  (Anthropic `stop_reason=max_tokens`, OpenAI `status=incomplete`, Google
  `finish_reason=MAX_TOKENS`) instead of a downstream JSON-parse error.
- **Fixture harness re-validates end-to-end**: recall 2/2, 0 gaps
  (`harness/out/harness_2026-07-10.md`), merged report credits
  anthropic+openai+google on convergent findings.
- The real 110-finding-scale validation (v9 paper re-run) is deliberately
  deferred until the lens-prompt upgrades land, so one paid run measures both.

## Decisions Made

- Synthesis cap: `synthesis_max_output_tokens = 64000` (~2.5× headroom over
  the largest observed run; 128k available if ever needed)
- Adaptive thinking stays ON for synthesis
- `TruncatedOutputError` is non-retryable in `_with_retries`
- Chunked synthesis: not built (revisit only past ~500 findings, or fix
  upstream via stricter adversarial-verify demotion)

## Results

- `harness/out/harness_2026-07-10.md` — fixture run, recall 2/2, 0 gaps
- `harness/out/review_2026-07-10.md` — merged report (multi-model convergence
  visible on all three planted-adjacent findings)
- Code: commit `2ff725f` (config, pipeline, all three provider clients,
  +2 tests)

## Open Questions

- Lens-prompt upgrades for the two v9 misses (STATUS next-action 2) — then
  re-run the real-paper harness to measure recall AND confirm synthesis
  merges 110+ findings under the new cap
- The 102 extras skim (needs Dan) and adversarial-verify calibration are
  still open from last session
- `harness/out/` and the `data` symlink are untracked — decide whether to
  gitignore them (cosmetic; flagged 2026-07-10)
