<!-- Generated during: convos/20260716_step15_live_specimens.md -->

# Step 15 — live-specimen validation of stage 3.5 (source check)

**Date:** 2026-07-16/17 (runs span midnight UTC)
**Branch:** `source-check` · convo: `../convos/20260716_step15_live_specimens.md`
**Plan:** `../plans/20260714_source_check_stage.md`, Part C step 15

## Provenance

- Specimens: the two cited-literature `unverifiable` rows of
  `data/harness_out_v9/reverify_2026-07-14.md` (rows 6–7; the third
  unverifiable row, the replication-package critique, rode along and
  exercised the no-citation path at zero cost)
- Sources: author-supplied extractions in `data/sources/` —
  `Svanberg_2024__beyond_AI_exposure_cost_effective.txt@8f3573b5`,
  `Davidson_2026__automating_AI_research_explosive_growth.txt@7248528f`
- Harness: `harness/sourcecheck_replay.py` (rebuilds checkpoint rows as
  `unverifiable` findings, runs `_run_source_check` with real providers;
  rotation gives anthropic/claude-opus-4-8 as checker for openai-found,
  google-refuted findings)
- Checker prompt sha256[:16]: `cb1f482f5e8eee44` (runs 1–3), revised in
  `f4e2c7a` for run 4
- Raw outputs (gitignored): `data/harness_out_v9/sourcecheck_replay_*.md/.jsonl`
  (`_run1`…`_run3` suffixes preserve the intermediate runs)
- Adjudicator: Dan, in-session
- Total spend: 4 check calls + 2 index calls, ≲ $1 all-in

## Chronology and outcomes

| Run | Specimens | Outcome |
|-----|-----------|---------|
| 1 (07-16) | all 3 | Davidson **refuted** (both gates passed); Svanberg unresolved (no matching source — index honestly read `year: ""` from the year-less working paper); replication-package unresolved (no citation, by construction) |
| 2 (07-17) | Svanberg | after hand-correcting the sidecar year to 2024 (the designed recourse): checker returned critique-contradicted but Gate B rejected the demotion — quote scored 0.834 vs the 0.85 floor |
| 3 (07-17) | Svanberg | with Gate B logging (`4a0edfe`): rejected quote captured; diagnosis = pdftotext running header spliced mid-sentence (44 header lines; header-stripped counterfactual scores 0.959) |
| 4 (07-17) | Svanberg | with `critique-narrowed` (`f4e2c7a`) + furniture stripping (`797cb88`): **narrowed → softened**, both gates passed, quote grounds at 1.000 |

## Adjudications (ground truth)

- **Davidson specimen — refuted is correct.** The critique suspected the
  source's 13% automation threshold was AI-R&D-specific; the source's
  Table 5 (`S, H, A, Y` row) plus its note ("Here we assume that
  f = fS = fH = fA = fY") shows equal automation across all four sectors
  including goods production. The paper's characterization matches the
  source; demotion with the exonerating quote is right.
- **Svanberg specimen — softened is correct, refuted would have been
  wrong.** The critique's central charge (that the fragmentation mechanism
  was the citing paper's gloss) dies: the source itself writes that the 49%
  result "reflects the extremely fragmented distribution of tasks in the
  economy." But two scope reminders survive (49% is vision-task, firm-level,
  0.79% of compensation; "free" still carries ~$165k engineering), and Dan
  wants those reminders pre-submission: "not TOTALLY wrong… I'd prefer the
  reminder." Run 2's critique-contradicted was therefore a substantive
  miss that Gate B blocked only by mechanical coincidence.

## Defects found by the live specimens (all fixed in-session, TDD)

1. **Citation extraction vs LaTeX markup** (`4581e3e`): critique quotes are
   verbatim `.tex`, so `et al.~(2024)` (tie) and `\&` blocked the regex —
   both specimens aborted before any check call. Caught zero-cost pre-run.
2. **Gate B observability** (`4a0edfe`): the unresolved path discarded the
   rejected `source_quote`, making grounding failures undiagnosable.
3. **Resolution boundary** (`f4e2c7a`): binary confirmed/contradicted forced
   partially-valid critiques to round to demotion. Added
   `critique-narrowed` → `softened` (same gates as demotion; vocabulary
   unchanged); prompt now requires EVERY charge to fail for contradicted.
4. **Page furniture** (`797cb88`): pdftotext running headers splice
   mid-sentence and break grounding of page-spanning quotes;
   `load_text_source` now strips digit-masked lines repeating ≥5× with ≥4
   letters.

## Design observations (carried forward)

- Working papers routinely print no year (the Svanberg head has none);
  the index's honest `year: ""` → no-match is correct behavior, and the
  hand-correctable sidecar is the designed, teachable recourse. It worked.
- The index model resisted both guessing and the "Svanberg (2023)"
  early-draft bait in the acknowledgments — prompt-compliance evidence, n=2
  with the fixture-gate collision test.
- Fix-ordering mattered: stripping page furniture BEFORE adding
  critique-narrowed would have let run 2's wrong demotion through. The
  substantive boundary, not the fuzzy threshold, was load-bearing.
- Open: the verdict-lattice/provenance question from step 14 stands
  (synthesis most-conservative-wins ranks softened above upheld); the
  Svanberg finding now enters synthesis as softened, which is
  lattice-consistent.
