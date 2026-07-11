# Prompt Caching Implementation Plan

**Goal:** Cut per-run API cost ~60% (~$23 → ~$8–10) by making the paper text a
cacheable shared prefix across the lens fan-out and adversarial-verify stages,
with zero change to what any model actually reads.

**Originating conversation:** [docs/convos/main/20260711_lens_upgrades_and_v9_rerun.md](../../convos/main/20260711_lens_upgrades_and_v9_rerun.md)

**Context:** The 2026-07-11 cost accounting showed adversarial verify is
~two-thirds of a ~$22–25 run because `pipeline._verify` re-sends the full
~44k-token paper with every HIGH/MEDIUM finding, and the lens fan-out re-sends
it 8× per provider. The tokens are byte-identical across calls — this is pure
engineering waste, and caching removes it with no quality tradeoff ("good over
cheap" gets both). Secondary motive: the cache structure itself is teaching
material for the Colab artifact (what caching is, why prefix order matters,
what it saves).

**Confidence:** High on the verify-stage win (fixed system prompt + paper-first
user prompt is cache-ready today). Medium on the lens-stage restructure — it
moves the lens instruction from `system` to the user message, which could shift
finding quality; the fixture harness is the gate.

**Architecture:** One constant system prompt (`SHARED_HEADER`) for all
paper-reading calls; the paper becomes the first user content block (marked
`cache_control` on Anthropic); the role-specific instruction (lens prompt /
verify prompt + critique) follows the paper. Then every lens call and every
verify call per provider shares one cached prefix. OpenAI and Gemini cache
repeated prefixes automatically — for them this is mostly a *measurement* task
plus the same prompt reordering. Synthesis is untouched (no paper in its
prompt; it's ~$0.70/run).

**Branch:** main (repo convention: main-line work commits directly to main)

**Tech Stack:** Python 3.12, `anthropic` / `openai` / `google-genai` SDKs,
pytest with fake providers (no live calls in tests)

---

## Background for an engineer with zero context

- `pat_helper/pipeline.py` — `run_review()` has 4 stages: lens fan-out
  (`_run_cell`, 8 lenses × N providers, each call gets
  `f"# PAPER\n\n{paper.text}"` as the user prompt and
  `SHARED_HEADER + lens.prompt` as system), mechanical quote-grounding (free),
  adversarial verify (`_verify`, user prompt =
  `f"# PAPER\n\n{paper_text}\n\n{_critique_block(finding)}"`, system =
  `verify_prompt()`), synthesis (one call, findings only).
- `pat_helper/prompts.py` — `SHARED_HEADER`, `load_lenses()`, `verify_prompt()`.
- `pat_helper/providers/*.py` — three clients, each exposing
  `complete_json(system, user, schema, *, max_output_tokens=None)`. The
  Anthropic client always streams.
- `tests/test_pipeline.py` — `FakeProvider` records call args (see
  `call_caps`); this is the established pattern for pipeline-boundary tests.
- Key API facts (verified against the claude-api skill, 2026-07-11):
  - Anthropic caching is a **prefix match**; render order `tools → system →
    messages`. A per-lens system prompt therefore breaks caching for
    everything after it — this is *why* the lens instruction must move.
  - Breakpoint: `cache_control: {"type": "ephemeral"}` on a content block;
    reads ~0.1× input price, writes 1.25×; min cacheable prefix on opus-4-8 is
    **4096 tokens** (smaller papers silently don't cache — no error).
  - Cache reads refresh the 5-minute TTL; a run's stages are adjacent in time.
  - A cache entry is readable only after the writing request **starts
    streaming** — N concurrent identical-prefix calls all miss. Do NOT use the
    `max_tokens: 0` pre-warm trick: it is rejected in combination with
    `output_config.format`, which every call here uses.
  - OpenAI (gpt-5.5) and Gemini (3.1-pro) cache automatically on repeated
    prefixes (Gemini cached input ~$0.20/MTok); no explicit marker exists —
    identical prefix ordering is the whole game.

## Design

1. **Provider interface** — extend `complete_json` so the caller can mark a
   cacheable user prefix. Recommended shape: `user` accepts
   `str | tuple[str, str]`, where the tuple is
   `(cacheable_prefix, volatile_suffix)`.
   - Anthropic: two content blocks; `cache_control` on the first (only when
     the tuple form is used).
   - OpenAI / Google: concatenate the two parts — behaviorally identical to
     today; their caching is automatic. (Keeps one interface, no provider
     branching in the pipeline.)
2. **Verify stage** — `_verify` passes
   `(f"# PAPER\n\n{paper_text}", f"\n\n{_critique_block(finding)}")`. The
   verify system prompt is already constant. This alone captures most of the
   dollar win.
3. **Lens stage** — system becomes `SHARED_HEADER` only (constant); user
   becomes `(f"# PAPER\n\n{paper.text}", f"\n\n# YOUR LENS\n\n{lens.prompt}")`.
   `SHARED_HEADER`'s "your assigned lens" wording still reads correctly, but
   review it during implementation.
4. **Unify the prefix across stages (stretch, do last)** — if verify's system
   prompt also becomes `SHARED_HEADER` with the verify instruction moved after
   the paper, lens and verify share ONE cache entry per provider. Only do this
   if steps 2–3 validate cleanly; it doubles the prompt-shift surface.
5. **Cache-priming order** — in `run_review`, launch ONE Anthropic cell first,
   await its completion, then `gather` the rest. Costs ~1 call of latency,
   guarantees the other 7 lens calls + all verify calls read the cache. (Do
   the same trivially for the other providers by virtue of the same ordering —
   no provider-specific code.)
6. **Measurement** — log per-call cache usage so savings are observable:
   Anthropic `usage.cache_read_input_tokens` / `cache_creation_input_tokens`;
   OpenAI `usage.prompt_tokens_details.cached_tokens`; Gemini
   `usage_metadata.cached_content_token_count`. Emit at DEBUG level per call
   plus one INFO summary line per run (total cached vs uncached input tokens).

**Testing Plan**

I will extend `FakeProvider` in `tests/test_pipeline.py` to record the `user`
argument shape per call (mirroring the existing `call_caps` pattern), then add
pipeline-boundary tests that assert BEHAVIOR of the pipeline↔provider contract:

- Lens calls pass the tuple form with the paper in the cacheable prefix and
  the lens prompt in the suffix; system no longer contains the lens prompt.
- Verify calls pass the tuple form with the paper in the prefix and the
  critique block in the suffix.
- **Prompt-equivalence test:** for both call kinds, `prefix + suffix`
  concatenated contains exactly the same paper text, lens text, and critique
  content the model received before the restructure (guards against silently
  dropping or duplicating content while reordering).
- A unit test per provider client (using each SDK's request-capture seam the
  existing provider tests use) asserting: tuple input → two user content
  blocks with `cache_control` on the first (Anthropic) / single concatenated
  user string (OpenAI, Google); plain-string input → unchanged request shape.
- Priming order: a pipeline test asserting the first provider call completes
  before the remaining fan-out calls start (FakeProvider records start/end
  ordering).

Live validation (not pytest): fixture harness run must reproduce recall 2/2,
0 gaps (quality gate for the lens-prompt move), and a 2-call live smoke on
opus-4-8 must show `cache_read_input_tokens > 0` on the second call. Note the
fixture paper may be under the 4096-token opus minimum — if so, the cache-hit
smoke needs the v9 paper (or any ≥4096-token text), not the fixture.

NOTE: I will write *all* tests before I add any implementation behavior.

## Steps

1. Write the failing FakeProvider-based test: verify calls use tuple form,
   paper in prefix.
2. Write the failing test: lens calls use tuple form; system == SHARED_HEADER.
3. Write the failing prompt-equivalence test (content preserved across the
   reorder).
4. Write the failing per-provider request-shape tests (Anthropic blocks +
   cache_control; OpenAI/Google concatenation).
5. Write the failing priming-order test.
6. Run pytest; confirm all new tests fail for the right reason.
7. Implement the `str | tuple[str, str]` handling in the three provider
   clients.
8. Implement the pipeline changes (`_run_cell` signature/system change,
   `_verify` split, priming order in `run_review`).
9. Run pytest until green; ruff clean.
10. Add cache-usage logging (DEBUG per call, INFO run summary).
11. Live smoke: 2 identical opus-4-8 calls on a ≥4096-token text; assert
    cache read on call 2.
12. Fixture harness run; require recall 2/2, 0 gaps.
13. Commit.
14. (Stretch, separate commit) Unify verify under SHARED_HEADER; re-run
    fixture harness before keeping it.

## Edge cases

- **Papers < 4096 tokens** (opus min prefix): silently uncached — harmless,
  but never *assert* cache hits for small inputs.
- **Provider subsets** (`--providers anthropic`): priming must use the first
  *available* provider, not assume all three.
- **Byte-identical prefix**: nothing call-varying may precede or sit inside
  the paper block (no timestamps, no lens names, no finding counts). The
  prompt-equivalence test plus a grep for interpolation in the prefix path
  covers this.
- **TTL**: 5-minute default is fine — reads refresh it and stages are
  adjacent. If a run ever stalls >5 min between stages, verify calls pay one
  re-write (1.25×), not a failure.
- **Worst case economics**: if nothing ever reads the cache, cost increases
  only by the 25% write premium on Anthropic input (~$2/run) — bounded and
  visible in the usage logging.
- **`max_tokens: 0` pre-warm is unavailable** with `output_config.format` —
  the priming-order approach is the substitute, don't "optimize" back to
  pre-warming.

## Plan footer

**Testing Details** All new tests assert the pipeline↔provider contract
(which content ends up where in the request) and content-preservation across
the reorder — not mock internals. The quality gate for the behavioral risk
(lens prompt moving out of `system`) is a real fixture-harness run scored by
the LLM judge, and the cache mechanism itself is verified by a live smoke on
usage fields, not by trusting the request shape.

**Implementation Details**
- `complete_json` accepts `str | tuple[str, str]`; tuple = (cacheable prefix,
  volatile suffix); only Anthropic renders it as two blocks + `cache_control`
- Lens system prompt shrinks to `SHARED_HEADER`; lens text moves after the
  paper in the user message
- `_verify` splits its existing user prompt at the paper/critique boundary —
  no text changes, only structure
- Priming: first cell awaited, then fan-out; also naturally primes verify
  (after the stretch unification) since reads refresh TTL
- Cache-usage logging on all three providers so the saving is measurable and
  teachable
- Expected result: Anthropic input ~$8 → ~$1.5; total run ~$23 → ~$8–10
- Synthesis and judge untouched
- No new config knobs (YAGNI) — caching is unconditional; the tuple form *is*
  the opt-in

**What could change:**
- If the fixture harness shows recall degradation from the lens-prompt move,
  fall back to verify-only caching (step 2 alone still saves ~$10/run) and
  revisit lens restructure with prompt tweaks
- If adversarial-verify calibration work (STATUS open item) changes how many
  findings get verified, the dollar numbers shift proportionally
- If OpenAI/Gemini usage fields show automatic caching already applying
  pre-restructure, their share of the saving is already banked and the plan's
  total estimate is conservative
- A future `--providers` default change (gpt-5.6 switch) doesn't affect the
  design, only prices

**Questions**
1. Is the lens-instruction move out of `system` acceptable given the
   fixture-harness gate, or do you want an A/B (one paid v9 run with old vs
   new prompt placement) before trusting it? (Recommendation: fixture gate is
   enough; the next paid run measures it for free anyway.)
2. Should the INFO-level cache summary also land in the rendered report's
   coverage section (teaching value for the Colab), or stay log-only for now?
3. Do the stretch unification (verify under SHARED_HEADER) in the same
   session, or defer until the verify-calibration work touches those prompts
   anyway?

---
