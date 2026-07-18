# Step 15 — Live Specimens Through Stage 3.5

**Date:** 2026-07-16/17 (session spanned midnight UTC)
**Branch:** source-check

## Summary

Ran plan step 15: the two cited-literature `unverifiable` findings from the
07-14 reverify replay (Svanberg 2024 at tex:268, Davidson 2026 at tex:2004)
through the source-check stage against Dan's supplied extractions, with Dan
adjudicating. Both specimens ended at Dan's adjudicated ground truth — but
getting there surfaced and fixed four real defects, each caught by the live
specimens and none by the fixture gate: LaTeX markup blocking citation
extraction, a Gate B observability hole, a too-coarse resolution boundary,
and pdftotext page furniture breaking quote grounding.

The session's central design lesson: the Svanberg specimen's checker wanted
to demote a critique that was two-thirds dead but carried a surviving
scope reminder Dan explicitly wants pre-submission ("not TOTALLY wrong…
I'd prefer the reminder"). The binary confirmed/contradicted vocabulary had
no way to express that; `critique-narrowed` (→ existing `softened` verdict)
now does. Fix-ordering mattered: had the mechanical grounding fix landed
first, the wrong demotion would have gone through — the substantive
resolution boundary was load-bearing, not the 0.85 fuzzy threshold.

A pre-flight zero-cost check (running `extract_citation` against the actual
checkpoint rows before spending anything) caught defect 1 before the first
paid call; the replay harness (`harness/sourcecheck_replay.py`) made the
remaining iterations cheap and reproducible. Total spend ≲ $1.

## Topics Explored

- Replay design: rebuilding reverify-checkpoint rows as `unverifiable`
  Findings and running `_run_source_check` with real providers (checker
  rotation gave anthropic for openai-found/google-refuted specimens)
- Working-paper year problem: the Svanberg extraction prints no year in its
  first 2,000 chars; index honestly returned `year: ""`, and the
  hand-correctable sidecar recourse worked as designed
- Gate B forensics: rejected-quote capture, ligature exoneration
  (casefold expands ﬁ→fi), page-header splice diagnosis (0.834 → 0.959
  counterfactual, → 1.000 after the loader fix)
- The contradicted-vs-narrowed boundary, driven by Dan's live adjudication
  of the Svanberg critique

## Provisional Findings

- The stage's mechanical spine held against live models: no gate ever
  passed something it shouldn't have; all four defects were in plumbing
  and vocabulary, not in gate logic
- Live checker quality was high: both checkers quoted sources verbatim
  (ligatures intact) and reasoned accurately; run 4's narrowed note
  independently reproduced both of Dan's surviving-point reminders
- pdftotext page furniture is a systematic hazard for any quote spanning a
  page break (~1-in-5 chance for paragraph-length quotes); working papers
  routinely lack printed years — both are properties of the *source-supply*
  pipeline, now handled at ingestion
- The fixture gate (step 14) and live specimens (step 15) caught disjoint
  defect sets — neither substitutes for the other

## Decisions Made

- Davidson adjudication: **refuted correct** (Table 5 `S,H,A,Y` row +
  equal-f note match the draft's characterization)
- Svanberg adjudication: **softened correct, refuted wrong** — surviving
  vision-scope + $165k reminders must reach the author
- `critique-narrowed` → `softened`: clears the same gates as demotion
  (identity, grounded quote, untruncated read); unhonored narrowing falls
  back to the full `unverifiable` flag
- Checker prompt: contradicted now requires EVERY substantive charge to
  fail; "minor caveat" in reasoning is a signal to use narrowed
- Page furniture: strip at `load_text_source` (digit-masked line repeated
  ≥5× with ≥4 letters); line map keeps original line numbers
- Commits: `4581e3e`, `4a0edfe`, `f4e2c7a`, `797cb88`; suite 95/95

## Results

- `../results/20260717_step15_live_specimens.md` — full chronology (4 runs),
  adjudications, defects, provenance
- Raw run outputs in `data/harness_out_v9/sourcecheck_replay_*` (gitignored;
  `_run1`–`_run3` suffixes preserve intermediates)

## Open Questions

- Verdict lattice vs provenance (carried from step 14): synthesis
  most-conservative-wins ranks softened above upheld; should source-grounded
  verdicts outrank or annotate text-only ones in merges? Svanberg entering
  as softened is lattice-consistent, so nothing is wrong today, but the
  question is undesigned.
- Should the checker prompt's narrowed path eventually adjust severity
  directly (HIGH→LOW) rather than relying on the renderer's softened
  presentation?
- Step 15 exit criteria are met; plan Part C is complete. Remaining before
  merge-readiness: the carried extras/demoted skim (ground-truth labels for
  verify calibration), and the lattice question above.
