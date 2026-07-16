# RESEARCH LOG — source-check

Branch: `source-check` · opened 2026-07-14

## Session: 2026-07-16 — source-check implementation (Parts A+B + fixture gate)

### Topics Explored
- Full TDD implementation of stage 3.5 per `plans/20260714_source_check_stage.md`:
  Part A (27 tests RED-first, subagent quality review), Part B (minimal
  implementation, 82/82), plus the plan's year-near-miss edge case
- Part C step 14 fixture gate (Dan-approved paid runs): three harness runs +
  one diagnostic call; full record in `results/20260716_step14_fixture_gate.md`
- Convo: `convos/20260716_source_check_implementation.md`

### Provisional Findings
- The fixture gate caught two real live-model plumbing bugs unit fakes could
  not: evidence-side comparison citations abort extraction (fix: quote-first);
  Gate A false-rejects "as printed" author strings (fix: name-token matching)
- Run 3: recall 3/3 with the citation-mismatch defect resolved
  **2 upheld / 0 refuted / 0 unresolved** — step-14 exit criterion met
- Synthesis most-conservative-wins can render a source-check-upheld finding
  as `softened` when merged with a text-only-softened sibling (open question:
  should source-grounded verdicts outrank the lattice?)

### Results
- `results/20260716_step14_fixture_gate.md`
- Commits `96cfe3d`, `0c1fe16`, `1f51c54`, `e31d74c`; suite 85/85 green

### Next Steps
- Step 15 (live specimens): PDFs now in `papers/` (main worktree) —
  pdftotext both into a sources dir under `data/`, re-run the two
  unverifiable findings from `reverify_2026-07-14.md` rows 6–7 through the
  stage, Dan adjudicates; record sanitized results
- Decide the verdict-lattice/provenance question before trusting merged
  renders for calibration

## Session: 2026-07-14 — branch kickoff (design carried from main-line convo)

### Topics Explored
- Full design brainstorm happened on the main line, same session as the
  `unverifiable` verdict work: see
  `docs/convos/main/20260713_unverifiable_verdict_design.md`
  ("Follow-on design: source-check stage")

### Provisional Findings
- (none yet on this branch — design decisions recorded in the originating convo)

### Results
- (none yet)

### Next Steps
- Implement per `plans/20260714_source_check_stage.md`
