<!-- Generated during: convos/20260731_verdict_lattice_part1.md -->

# Step 22 fixture gate — verdict lattice, 2026-08-02

Plan: `plans/20260731_verdict_lattice_provenance.md` Part 4 step 22. One
paid harness run (Dan go 2026-08-02), same command as step 14:
`uv run python harness/run.py tests/fixtures/main.tex --sources
tests/fixtures/sources` (defaults: anthropic=claude-opus-4-8,
openai=gpt-5.5, google=gemini-3.1-pro-preview; 8 lenses; judge
gpt-5.6-terra). Code state: `b634e85` (Parts 1–4 landed, 123/123 green).

## Outcome

| check | result |
|---|---|
| baseline recall | **3/3** (wrong-number, weakened-id, citation-mismatch all HIT) |
| contributor bookkeeping (the plan's medium-confidence unknown) | **compliant** — 24 findings, 0 gaps: no dropped/duplicate/out-of-range ids, no fallback fired |
| `(source-checked)` tag renders | **yes** — merged Svanberg finding |
| outranked text-only softening visible as annotation | **yes** — `[outranked text-only softened] [anthropic] …` in notes |
| exit criterion verdict `upheld (source-checked)` | **not literally met** — rendered `softened (source-checked)`; see below |

## The nuance: two source-tier verdicts, not one

The exit criterion assumed step-14 run 3's shape (one source-check-upheld
finding merged with a text-only-softened sibling). Live, the merged
Svanberg siblings carried **two source-tier verdicts**:

- anthropic checker: `critique-confirmed` → upheld/source — read the
  critique's central charge as the 40% figure; source says 14%.
- google checker: `critique-narrowed` → softened/source — read the central
  charge as the construct mismatch (which the source contradicts: it IS a
  productivity RCT), while noting the number error is "fully validated".

Within-tier conservatism (`softened` > `upheld`) then correctly merges to
`softened (source-checked)` — the exact behavior pinned by
`test_two_source_contributors_take_most_conservative_within_tier`. The
lattice, provenance plumbing, annotations, and renderer all behaved as
designed; the criterion miss is **checker-resolution variance**, not a
code defect.

## Open question (carried)

Checker calibration: when a checker's reasoning validates the critique's
quantitative charge but labels the resolution `narrowed` because it read a
different charge as central, conservatism lets that reading decide the
merged verdict. Related to the step-15 resolution-vocabulary lesson (binary
vocabulary rounded partial validity to demotion; `critique-narrowed` was
added). Possible directions: sharpen `_source_check.md` on what "central
charge" means, or treat confirmed-with-validated-number as outranking
narrowed. Not acted on — needs Dan's read on whether `softened
(source-checked)` undersells a confirmed numeric misstatement. Reader
visibility is intact either way: both checkers' verbatim source quotes
("14 percent") render in the notes.

## Provenance

- Rendered report: `data/harness_out_v9/review_2026-08-02.md` (copied from
  `harness/out/review_2026-08-02.md`)
- Recall scoring: `data/harness_out_v9/harness_2026-08-02.md`
- Cache telemetry: anthropic 11,715 cached / 40,216 uncached input tokens;
  openai and google 0 cached (fixture below their caching thresholds) —
  consistent with step-14 runs.
- 0 demoted this run, so the Part 3 demoted digest / `echoes_demoted` path
  did not exercise live (unit/integration coverage only).
