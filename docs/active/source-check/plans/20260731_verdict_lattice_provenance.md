# Verdict Lattice Provenance Implementation Plan

**Goal:** Merged verdicts become deterministic and provenance-aware — source-grounded verdicts outrank text-only ones, outranked softenings survive as annotations, and findings that echo a source-refuted demoted sibling get a rendered warning.

**Originating conversation:** `../convos/20260731_verdict_lattice_brainstorm.md`

**Context:** Step-14 run 3 showed synthesis most-conservative-wins rendering a source-check-upheld finding as `softened` (merged with a text-only-softened sibling), underselling a defect confirmed against the actual cited source. The same session found the mirror case: source-check-refuted findings demote *before* synthesis, so a text-only-upheld sibling of a ground-truth-refuted critique renders at full strength. Dan's decisions: (b) source-grounded outranks text-only with softenings carried as annotations; mirror case gets an annotate-only demoted digest now (full symmetric propagation is issue #2, deferred).

**Confidence:** High on semantics (Dan-adjudicated against two live specimens). Medium on the synthesis model's compliance with contributor-id bookkeeping — the fallbacks exist precisely because this is unproven; the paid gate (step 5 of Part 4) is the test.

**Architecture:** Provenance becomes a `Finding` field set at verdict-assignment time (never parsed from text). Synthesis stops deciding merged `verified`; instead it reports which input ids merged into each output (`contributors`) and which outputs echo a source-refuted demoted finding (`echoes_demoted`). A new pure module `pat_helper/lattice.py` computes the merged verdict/provenance/annotations deterministically from the contributor `Finding` objects. No free text is ever matched against — everything consumed is schema-validated enums and integer ids.

**Branch:** `source-check` (worktree: `/Users/dan/code/pat-helper/.worktrees/source-check`)

**Tech Stack:** Python 3.12, pytest, existing fake-provider test harness (`tests/`), JSON-schema structured outputs.

---

**Testing Plan**

I will write unit tests for `lattice.merge_verdict` as a pure function over lists of `Finding` objects (no mocks at all): source-upheld + text-softened → `upheld`/`source` with the softening note carried as an annotation; source-softened + text-upheld → `softened`/`source`; text-only mixtures → today's conservative order (`unverifiable` > `softened` > `upheld` > `None`); all-`None` → `None`; two source-tier contributors upheld+softened → `softened`.

I will extend the existing fake-provider pipeline integration tests: a fake synthesis payload with valid `contributors` produces merged findings whose `verified`/`verify_provenance`/`verify_notes` come from the lattice, not the payload; a payload omitting an input id appends the original finding unmerged plus a gap entry; a payload repeating an id across two outputs (or citing an out-of-range id) triggers the full pass-through-unmerged fallback plus a gap entry; a payload with `echoes_demoted` pointing at a digest entry appends the sibling-refuted warning to `verify_notes`; an invalid `echoes_demoted` id is ignored with a gap entry.

I will extend the verify and source-check unit tests to assert provenance side-effects: `_verify` success sets `verify_provenance="text"`; the source-check upheld/softened/refuted paths set `"source"`; the unresolved path leaves provenance untouched.

I will extend the renderer tests: a `verify_provenance="source"` finding renders `verification: upheld (source-checked)`; carried annotations and the sibling-refuted warning appear in the rendered markdown.

NOTE: I will write *all* tests before I add any implementation behavior.

---

## Part 1 — provenance field + lattice module (pure code)

1. Write failing unit tests for `Finding.verify_provenance` side-effects: `_verify` success path sets `"text"`; `_verify` exception path leaves it `None`; source-check upheld/softened/refuted paths set `"source"`; unresolved path leaves it unchanged. (Extend `tests/` files that already cover `_verify` and `_source_check_one` — find them with `grep -rl "_source_check_one\|def test.*verify" tests/`.)
2. Write failing unit tests for `pat_helper/lattice.py::merge_verdict(contributors: list[Finding]) -> MergeResult` covering every case in the Testing Plan. `MergeResult` carries `verified`, `provenance`, and `annotations: list[str]` (the outranked contributors' `verify_notes`, each prefixed `[outranked text-only <verdict>]`).
3. Run the new tests; confirm they fail (missing field, missing module).
4. Add `verify_provenance: str | None = None` to `Finding` (models.py) and include it in `to_json()`.
5. Implement `lattice.py`: if any contributor has `provenance == "source"`, the merged verdict is the most conservative *within the source tier* and provenance is `"source"`; otherwise most conservative within all contributors (text tier) and provenance passes through. Conservatism order: `unverifiable` > `softened` > `upheld` > `None`. Annotations collect `verify_notes` from text-tier contributors with verdict `softened`/`unverifiable` whenever the source tier decided.
6. Set provenance in `pipeline.py`: `_verify` success → `"text"`; `_source_check_one` verdict-changing paths → `"source"`.
7. Run the suite; green. Commit.

## Part 2 — synthesis schema + prompt

8. Write failing integration tests (fake synthesis provider) for the new payload shape per the Testing Plan — valid contributors, dropped id, duplicate id, out-of-range id. The fakes live in `tests/` alongside the existing synthesis fixtures (`grep -rl "SYNTHESIS_SCHEMA" tests/`).
9. Run them; confirm failure.
10. models.py `SYNTHESIS_SCHEMA`: remove `verified` from item properties/required; add `contributors` (array of integers, required) and `echoes_demoted` (array of integers, required — empty allowed). Note the Gemini caveat in the existing comment: plain integer arrays are safe; unions are not.
11. `_synthesis.md`: delete rule 7; add — every output finding lists `contributors` (the input `id`s merged into it); every input id must appear in exactly one output finding; `echoes_demoted` lists ids from the `DEMOTED (refuted against source)` digest, empty when none apply; merged verification is computed downstream, do not report it.
12. pipeline.py stage 4: build input as `{"id": i, **f.to_json()}`; append the demoted digest section (Part 3 wires its content; empty section omitted). Post-process: validate ids (coverage / duplicates / range); on per-finding validity, construct the merged `Finding` from `lattice.merge_verdict` over the contributor objects, joining source-tier notes + annotations into `verify_notes`; on dropped ids, append the original findings and a gap; on duplicate/out-of-range ids, fall back to pass-through-unmerged with a gap. Keep the existing quote re-grounding exactly as is.
13. Existing synthesis tests asserting `verified` passthrough (from `77ffc4e`) will now fail — update them to the new contract deliberately, one by one, confirming each failure is the expected contract change and not a regression.
14. Run the suite; green. Commit.

## Part 3 — demoted digest (the (iii) annotation)

15. Write failing integration tests: a source-refuted demoted finding (verdict `refuted`, provenance `"source"`) appears in the synthesis input digest; a fake payload citing it in `echoes_demoted` yields the warning appended to the merged finding's `verify_notes`: `"warning: a sibling formulation of this critique was refuted against the cited source; see appendix"`; text-only-refuted demoted findings do NOT enter the digest; invalid digest ids are ignored with a gap.
16. Run; confirm failure.
17. Implement: digest = enumerated `{id, lens, quote, note}` over `run.demoted` entries with provenance `"source"`, rendered as a separate `# DEMOTED (refuted against source)` JSON block in the synthesis user message; post-processing maps `echoes_demoted` ids back and appends the warning.
18. Run the suite; green. Commit.

## Part 4 — renderer + gate

19. Write failing renderer tests: `(source-checked)` provenance tag; annotations visible; warning visible.
20. Implement in `report.py::_render_finding`: `verification: <verdict> (source-checked)` when `verify_provenance == "source"`; notes rendering is already in place and needs no change beyond what the merge now preserves.
21. Run the full suite; green. Commit.
22. Re-run the fixture gate (`harness/run.py` on the mutated fixture with `--sources`, per `results/20260716_step14_fixture_gate.md`) — **paid run, ask Dan first**. Exit criterion: the citation-mismatch defect's merged finding renders `verification: upheld (source-checked)` with the sibling softening visible as an annotation; baseline recall 3/3 undisturbed.
23. Update docs (update-docs skill) and commit.

---

**Testing Details** The lattice is tested as a pure function on real `Finding` objects — no mocks, all behavior. Pipeline tests use the established fake-provider pattern and assert on run output (merged findings, gaps, demoted), not on internals. Renderer tests assert on markdown text. The only paid call is the final fixture gate, which tests the one thing fakes cannot: live synthesis compliance with contributor bookkeeping.

**Implementation Details**

- Provenance is set exactly where verdicts are set — never inferred, never parsed from notes.
- Source tier can only contain `upheld`/`softened` (source-refuted demotes pre-synthesis); the lattice handles the general case anyway (cheap, and issue #2 will change the invariant).
- `_verify`'s exception path ("verification unavailable" → upheld) keeps provenance `None`, so it can never outrank a real verdict.
- The `"none"` string sentinel leaves the schema entirely — `verified` is no longer a synthesis output.
- Fallback hierarchy: dropped ids → append originals + gap (better than today, where synthesis can silently drop findings); duplicate/out-of-range → whole-stage pass-through + gap (rare, safe, simple).
- `echoes_demoted` never changes a verdict — annotation only, by design (synthesis dedup lacks kill authority; STATUS.md documents its imperfection).
- Digest scope: source-refuted only; text-only refutations lack the ground-truth standing that makes the warning trustworthy.
- Synthesis input findings gain `id` and `verify_provenance` keys; input size growth is a few tokens per finding.

**What could change:** Issue #2 (symmetric propagation) would let source-refuted contributors drag merged siblings down, replacing the annotation with a demotion — the digest plumbing built here is its foundation. If the paid gate shows the synthesis model can't do contributor bookkeeping reliably, the fallback keeps output correct but unmerged, and we'd revisit (smaller id alphabet, exemplar in prompt, or a dedicated cheap-model dedup call). The verify-calibration ground-truth labels (Dan's carried skim) could still shift what "conservative" should mean within the text tier.

**Questions**

- Warning wording for the echoed-demotion annotation — flag strength matters for the teaching artifact; current draft is factual, not alarmist. Dan may want stronger.
- Should the pass-through-unmerged fallback also fire when `echoes_demoted` is malformed, or is ignore-with-gap enough? (Plan says ignore-with-gap; the field is advisory.)
- Step 22 is a paid run (~$2–4 by step-14 precedent) — explicit go/no-go from Dan at that step.

---
