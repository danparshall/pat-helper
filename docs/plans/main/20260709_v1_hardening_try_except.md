# Plan: Graceful CLI degradation for missing API keys

**Date:** 2026-07-09
**Source convo:** `docs/convos/main/20260709_v1_design_brainstorm.md` (harness-prep
session that discovered the mismatch between STATUS's claim and observed CLI
behavior)
**Scope:** v1 hardening — fix the one behavioral gap the harness-prep session
turned up. Not a redesign; not a v2 item.

## Problem

STATUS.md line 21 claims *"CLI degrades gracefully without keys"* and the
kickoff convo doc says *"with no API keys, a run degrades to recorded coverage
gaps and still emits a valid report (by design)."*

Actual behavior, verified 2026-07-09 with `uv run pat-helper review
tests/fixtures/main.tex` (no `.env`):

```
File "/Users/dan/code/pat-helper/pat_helper/providers/openai_client.py", line 22, in __init__
    self._client = AsyncOpenAI()
openai.OpenAIError: Missing credentials. …
```

Root cause: `pat_helper/cli.py:20-38` `_build_providers()` unconditionally
constructs each requested provider's SDK client. `AsyncOpenAI()`,
`AsyncAnthropic()`, and `genai.Client()` all raise at construction if their
env var is unset. The graceful-per-call degradation the pipeline tests
exercise (via fake providers) is unreachable from the CLI without at least
one usable provider.

## Design decision — probe env-var vs. catch SDK error

| | env-var probe | try/except SDK error |
|---|---|---|
| Doesn't swallow unrelated errors | ✅ | ⚠️ narrow catch keeps it tight |
| Handles Anthropic `ant auth login` profile | ❌ | ✅ constructor succeeds |
| Handles OpenAI `OPENAI_ADMIN_KEY` | ❌ | ✅ |
| Handles future SDK auth mechanisms | ❌ | ✅ |

**Chosen:** try/except on construction. Preserves non-env-var auth for
Anthropic (a real feature per `anthropic_client.py:2`) and OpenAI
(`OPENAI_ADMIN_KEY` shows up in the crash message we observed). Catch the
concrete SDK error type per provider plus a general `Exception` fallback that
records the exception type name — narrow enough not to mask logic bugs, wide
enough to survive SDK reshuffles.

Concrete catch list (verified 2026-07-09):

- OpenAI: `openai.OpenAIError`
- Anthropic: `anthropic.AnthropicError`
- Google: `google.genai.errors.ClientError` (falls under `Exception` if the
  SDK renames it)

## Behavior spec

1. **Per-provider construction failure:** skip that provider, append a
   `CoverageGap` (reuse existing `run.gaps` mechanism — do NOT add a new gap
   type). Gap message shape:
   `"{provider} unavailable at startup: {ErrorType} — check {ENV_VAR}"`.
2. **All-providers-failed (or explicit `--providers` subset all failed):**
   `SystemExit("No usable providers; check .env against .env.example.")`.
   Running with zero providers is a bug outcome, not a graceful one.
3. **Judge model construction (harness):** same try/except; missing key for
   the judge provider is fail-fast (`SystemExit("Judge model ({provider})
   unavailable — cannot score recall.")`), because without a judge we can't
   produce a harness result even in principle.

## Signature / plumbing change

`_build_providers` currently returns `list[Provider]`. Change to
`tuple[list[Provider], list[CoverageGap]]`. Three files touched:

- `pat_helper/cli.py` — return tuple, thread `startup_gaps` into `run_review`
  or merge into `run.gaps` post-hoc before `render()`.
- `harness/run.py` — same signature, but also apply the judge-provider
  fail-fast rule above.
- `pat_helper/pipeline.py` — check whether `run_review` needs a
  `preexisting_gaps` kwarg or whether merging into `run.gaps` after return is
  cleaner. Prefer the merge-after path if it doesn't complicate ordering; the
  synthesis stage produces its own gaps and we want startup-gaps to appear
  alongside them in the report.

## Tests (TDD, new file `tests/test_cli.py`)

Fake SDK client class that raises on construction, monkeypatched into each
provider module:

- `test_missing_openai_key_records_gap_and_continues` — one provider missing,
  others present → run completes, exactly one gap for openai in output.
- `test_all_keys_missing_exits_cleanly` — SystemExit with the specific message
  (no traceback in user-facing output).
- `test_explicit_providers_subset_missing_key_exits` — `--providers openai`
  with OPENAI_API_KEY absent → SystemExit.
- `test_all_keys_present_no_startup_gaps` — regression guard: without any
  missing keys, `_build_providers` adds zero gaps.

Also add a harness test (fake judge provider) confirming the fail-fast
message when the judge model's provider can't be constructed.

## Not doing

- **Not** reordering CLI `--providers` default (`anthropic,openai,google`
  stays). "OpenAI is our default" reads as "for the judge / cheap path," not
  as a mandate to skip the multi-model triangulation the whole tool exists
  for. Revisit if Dan wants single-provider runs to be OpenAI-only.
- **Not** refactoring `_build_providers` into a per-provider factory registry
  — nice-to-have when we add a fourth provider; premature now.
- **Not** adding a `MissingKey`-specific gap subtype — reuse the plain
  `CoverageGap` (existing consumers already know how to render it).

## Estimated effort

~40 min including tests. All test paths are unit-level; no live API calls
required to verify.

## Ordering vs. companion fixes

Companion fixes B (load_paper preamble strip) and C (judge → OpenAI) landed
in the same session that produced this plan — they were fast enough not to
warrant separate plan docs. See the commit that introduces this file for
those changes. This plan A is deferred to a follow-up session because it's
the biggest of the three and Dan wanted context-budget headroom.
