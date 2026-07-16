# Source-Check Implementation (Parts A+B + fixture gate)

**Date:** 2026-07-16
**Branch:** source-check

## Summary

Implemented the full source-check stage (3.5, "strict mode") from
`plans/20260714_source_check_stage.md`, TDD throughout. Part A wrote all 27
tests first (RED verified; a subagent quality review passed 24/25 and its two
real findings — a missing pipeline-level ambiguous-citation test and a
weaker-than-promised no-flag pin — were fixed before any implementation).
Part B landed the minimal implementation: schemas, `sourcecheck.py`
(content-keyed sidecar index, citation extraction, deterministic matching),
`load_text_source`, the pipeline stage with checker rotation and both
mechanical gates, the `_source_check.md` checker prompt, `--sources`
plumbing, and the report section. 82/82 green with the no-flag path pinned
byte-identical.

Dan approved Part C step 14 (paid fixture gate) and copied the Svanberg 2024
+ Davidson 2026 PDFs into `papers/` (main worktree) for step 15. The fixture
gate earned its keep twice: recall was 3/3 on every run, but the planted
citation-mismatch defect initially survived as `unverifiable` rather than
source-check-upheld, exposing two real stage-3.5 bugs that unit tests with
fake providers could not have caught (both were live-model behavior). After
both fixes, run 3 resolved **2 upheld / 0 refuted / 0 unresolved** — the
defect was recalled via the source-check-upheld path, as the plan specified.

The two live-caught bugs, in the order found: (1) citation extraction ran
over quote+evidence, but real critique prose name-drops comparison
literature ("more reminiscent of Brynjolfsson, Li & Raymond (2023)..."),
tripping the >1-distinct-citations abort — fixed by extracting from the
quote first (the disputed citation lives in the paper's verbatim sentence),
falling back to quote+evidence. (2) Mechanical Gate A compared the bare
citation surname against full author strings; the live checker honestly
returned critique-confirmed with authors `["Svanberg, M."]` (as printed in
the source) and the gate false-rejected it to unresolved — fixed by matching
the surname against whole name-tokens of the author string (substrings still
rejected), plus a schema description nudging models toward surnames.

## Topics Explored

- TDD RED→GREEN across four test files; schema object identity as the
  call-kind dispatch mechanism for the two new call kinds
- Subagent test-quality review; resolved its year-near-miss "plan
  contradiction" by keeping `match()`'s exact-year None and putting the
  "possible version mismatch" note at pipeline level (implemented + tested)
- Live fixture-gate debugging: three harness runs, one direct diagnostic
  check call (which returned a textbook-correct critique-confirmed payload,
  isolating Gate A as the false-rejector)
- Renderer semantics: run 3's merged Svanberg finding renders `softened`
  because synthesis most-conservative-wins merges the source-check-upheld
  finding with a text-only-softened sibling (see Open Questions)

## Provisional Findings

- The two mechanical gates behave as designed against fakes AND against a
  lying-free live checker; the failure modes found were both in the
  *plumbing between* honest model output and the gates, not in model behavior
- Live models render author identities "as printed" regardless of schema
  field names — mechanical comparisons must be format-tolerant, prompt fixes
  alone are brittle
- Critique evidence text routinely cites comparison works; any citation
  extraction over evidence text must privilege the quote
- The fixture source deliberately collides with the *real* Svanberg 2024
  (which is about vision-task automation cost-effectiveness, not GenAI
  productivity); the live checker read the supplied source's own identity as
  instructed and did not import its prior knowledge — good prompt-compliance
  evidence, though n=1 (see Open Questions)
- Cache telemetry (fixture-sized runs): anthropic ~11k cached / ~36k
  uncached; openai/google 0 cached — fixture is below their caching
  thresholds; not a concern at real-paper scale

## Decisions Made

- Identity gate applies to `critique-confirmed` too (upholding from the
  wrong source is also an error); quote-grounding gate only blocks
  demotion-enabling `critique-contradicted` (per plan invariant 3)
- `match()` keeps the plan signature (`path | None | AMBIGUOUS`, exact
  year); near-miss detection is a separate pipeline-level note
- Index prompt lives inline in `sourcecheck.py` (mechanical metadata
  extraction, not a review lens) — movable to `lenses/` if Dan prefers
- Reused `fuzzy_threshold=0.85` for source-quote grounding (plan's open
  question; live specimens should inform whether demotions need stricter)
- Empty/un-indexable sources dir → warning + effectively-relaxed run
- Committed `tests/fixtures/sources/sources_index.json` (zero index calls on
  future fixture runs; doubles as a sidecar format example)
- Note-wording contracts pinned by tests: "no matching source", "ambiguous",
  "version mismatch", `[source-check:{provider} {file}@{sha8}]`

## Results

- `results/20260716_step14_fixture_gate.md` — three-run fixture-gate record
  with cost/cache telemetry and both bug diagnoses
- Commits: `96cfe3d` (Part A), `0c1fe16` (Part B), `1f51c54` (near-miss
  note), `e31d74c` (step 14 + both live-caught fixes); suite 85/85
- Raw run outputs in `harness/out/` (untracked, per existing convention)

## Open Questions

- **Verdict lattice vs provenance:** synthesis most-conservative-wins ranks
  `softened` above `upheld`, so a source-check-grounded upheld merged with a
  text-only softened renders softened. Should verification provenance
  (checked-against-source vs text-only) outrank or annotate the lattice?
- Checker prompt-compliance under identity collision is n=1 (the checker
  believed the supplied source over its prior knowledge of the real
  Svanberg 2024, per instruction). Step 15's real sources give cleaner
  evidence; a deliberately-wrong-source test could probe the other side.
- Step 15 still pending: pdftotext the two PDFs (now in `papers/`, main
  worktree) into a sources dir under `data/`, re-run the two live specimens
  from `reverify_2026-07-14.md` rows 6–7, Dan adjudicates.
- Carried: verify-calibration ground-truth labels need Dan's extras/demoted
  skim (since 07-12); output-side spend unmeasured; whether `unverifiable`
  is the right verdict for cited-literature accuracy critiques (this
  session's specimens suggest the source-check stage makes the wider scope
  productive rather than mushy).
