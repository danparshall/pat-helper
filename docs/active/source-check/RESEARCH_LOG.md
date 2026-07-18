# RESEARCH LOG — source-check

Branch: `source-check` · opened 2026-07-14

## Session: 2026-07-16/17 — step 15 live specimens (plan Part C complete)

### Topics Explored
- Plan step 15: both reverify unverifiable specimens (Svanberg tex:268,
  Davidson tex:2004) through stage 3.5 against Dan's supplied extractions;
  Dan adjudicated. Convo: `convos/20260716_step15_live_specimens.md`

### Provisional Findings
- Davidson: **refuted** (both gates) — Dan: correct. Svanberg: after four
  in-session fixes, **narrowed → softened** with exactly the vision-scope +
  $165k reminders Dan wanted — Dan's ground truth: "not TOTALLY wrong…
  I'd prefer the reminder"
- Four live-caught defects, all fixed TDD (95/95): LaTeX ties/`\&` blocked
  citation extraction (`4581e3e`); Gate B discarded rejected quotes
  (`4a0edfe`); binary resolution vocabulary rounded partial validity to
  demotion — added `critique-narrowed` → `softened` (`f4e2c7a`); pdftotext
  page furniture broke page-spanning quote grounding (`797cb88`)
- Fix-ordering lesson: the resolution boundary, not the fuzzy threshold,
  was load-bearing — grounding fix alone would have shipped a wrong demotion
- Working papers lack printed years; sidecar hand-correction recourse
  exercised and worked

### Results
- `results/20260717_step15_live_specimens.md` (chronology, adjudications,
  defects, provenance); raw runs in `data/harness_out_v9/` (gitignored)

### Next Steps
- Verdict-lattice/provenance design question (carried; still open)
- Carried: Dan's extras/demoted skim for verify-calibration ground truth
- Plan Part C complete — branch nearing merge-readiness discussion



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
