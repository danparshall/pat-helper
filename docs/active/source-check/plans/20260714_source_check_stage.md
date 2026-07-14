# Source-Check Stage ("strict mode") Implementation Plan

**Goal:** Add pipeline stage 3.5: when the author supplies a folder of cited-source texts, `unverifiable` findings are checked against the actual sources and auto-resolved (upheld / refuted / still-unverifiable).

**Originating conversation:** `docs/convos/main/20260713_unverifiable_verdict_design.md` (section "Follow-on design: source-check stage") — on main, since the design brainstorm preceded the branch.

**Context:** The `unverifiable` verdict (landed `77ffc4e`) stops paper self-claims from refuting critiques, leaving a queue of promissory notes for the author. The 07-14 reverify replay produced two live citation-accuracy specimens (Svanberg 2024, Davidson 2026). PAT itself was search-grounded; this restores that capability in an author-facing, local-first form. Dan's framing: "strict" mode resolves the queue; "relaxed" (default, no flag) hands it to the author unchanged.

**Confidence:** Design settled through structured brainstorm with Dan (retrieval: local-first; authority: auto-resolve; architecture: per-finding check call). The *prompt wording* and gate thresholds are provisional until the live-specimen validation.

**Architecture:** New module `pat_helper/sourcecheck.py` (index build + citation matching), new stage in `pipeline.run_review` between verify and synthesis, new `_source_check.md` prompt, two new schemas in `models.py`. Two zero-API-cost mechanical gates (quote grounding against the source; identity match) sit between the checker's opinion and any verdict change. No flag → byte-identical current behavior.

**Branch:** `source-check` (worktree: `/Users/dan/code/pat-helper/.worktrees/source-check` — all paths below relative to that root)

**Tech Stack:** Python 3.12, uv, pytest; existing provider abstraction (`pat_helper/providers/`), quote-grounding (`pat_helper/quotecheck.py`), markdown prompts (`pat_helper/lenses/`).

---

## Orientation (zero-context engineer starts here)

- `pat_helper/pipeline.py` — `run_review` stages 1–4; stage 3.5 slots after the `survivors` list is built (~line 208) and before synthesis. Note the prime-then-fan-out cache pattern used by stages 1 and 3 — stage 3.5 must follow it, keyed per (checker provider, source file).
- `pat_helper/models.py` — `Finding` (`verified` field), schemas. Schema **object identity** distinguishes call kinds in tests/fakes: define `SOURCE_CHECK_SCHEMA` and `SOURCE_INDEX_SCHEMA` as module-level dicts, pass those exact objects.
- `pat_helper/quotecheck.py` — `check_quote(quote, paper, threshold)`; works on a `FlattenedPaper`. `pat_helper/latex.py` — `load_paper`; check whether it accepts plain `.txt` (if not, add a thin `load_text_source(path) -> FlattenedPaper` there).
- `pat_helper/config.py` — `ReviewConfig`; add `sources_dir: Path | None = None`.
- `tests/test_pipeline.py` — `FakeProvider` dispatches on schema identity; extend with the two new kinds.

## Design invariants (do not trade away while implementing)

1. **No flag → no behavior change.** `sources_dir=None` must produce byte-identical runs (regression-pinned by test).
2. **The model never picks the file.** Citation→file matching is deterministic against the content-built index; zero or ambiguous matches → `unresolved`.
3. **No silent wrong-source demotion.** A `critique-contradicted` resolution is honored only if BOTH gates pass: source_quote grounds against the source text, and the checker-read identity matches the citation.
4. **Verdict vocabulary unchanged.** Stage 3.5 only moves findings between existing verdicts (`unverifiable` → `upheld`/`refuted`/unchanged). Synthesis and report logic need no new verdict.
5. **Checker ≠ finder, and ≠ refuter when a third provider exists** (rotation offset 2, falling back to offset 1 with two providers).

**Testing Plan**

I will add unit tests for `sourcecheck.py` behaviors: index build (N files → N entries via fake provider; sidecar `sources_index.json` written keyed by file sha256; a second build with an unchanged folder makes ZERO provider calls; a changed file re-indexes only itself), citation extraction ("Svanberg et al. (2024)", "Kording & Marinescu (2025)", "Acemoglu (2024)" → (surname, year); no-citation and multi-citation text → None), and matching (unique hit / zero / two-files-same-author-year → ambiguous).

I will add pipeline integration tests through `run_review` with fake providers: with `sources_dir` set and an `unverifiable` finding, a source-check call goes to the rotation-offset-2 provider; `critique-confirmed` → finding enters synthesis with `verified="upheld"` and provenance note; `critique-contradicted` → finding demoted with the exonerating source quote in notes; `unresolved` → stays `unverifiable`; `identity_matches_citation=false` forces unresolved EVEN IF resolution says contradicted; an ungrounded `source_quote` forces unresolved; with `sources_dir=None` no source-check call is ever made and outputs equal today's (pin).

I will add a report test (source-check summary section renders counts) and a CLI test (`--sources` populates config).

NOTE: I will write *all* tests before I add any implementation behavior.

## Steps

**Part A — tests (write all, watch fail)**
1. Create `tests/test_sourcecheck.py`: index-build tests (fake provider; tmp_path sources dir with 2–3 small text files).
2. Same file: citation-extraction and matching tests (pure functions, no provider).
3. `tests/test_pipeline.py`: extend `FakeProvider` with `source_check_resolution` / `source_index` knobs dispatching on the two new schema objects (import will fail until step 6 — that IS the failing state for these tests).
4. Same file: the six integration tests from the Testing Plan, plus the no-flag regression pin.
5. `tests/test_report.py` summary test; `tests/test_cli.py` flag test. Run `uv run pytest` — new tests fail (import errors count), 55 existing pass.

**Part B — implementation (minimal, in dependency order)**
6. `models.py`: `SOURCE_INDEX_SCHEMA` ({authors: [str], year: str, title: str}) and `SOURCE_CHECK_SCHEMA` ({identity{authors,year,title}, identity_matches_citation: bool, resolution: enum[critique-confirmed, critique-contradicted, unresolved], source_quote: str, reasoning: str}). All required, `additionalProperties: False`, no unions.
7. `latex.py`: `load_text_source()` if `load_paper` can't already ingest plain text.
8. `pat_helper/sourcecheck.py`: `build_index(sources_dir, provider, config)` (head = first 2,000 chars; sidecar cache keyed by sha256; prune entries whose file vanished), `extract_citation(text) -> (surname, year) | None` (regex over quote+evidence; unicode-casefold surnames; None on zero or >1 distinct citations), `match(citation, index) -> path | None | AMBIGUOUS`.
9. `pipeline.py` stage 3.5: queue = survivors with `verified == "unverifiable"`; index built once with the first healthy provider (head-reads are ~2k tokens and cached forever — not worth new cheap-model plumbing; revisit if folders get huge); group queue by matched source, prime-then-fan-out per (checker, source); apply gates; map verdicts; append `[source-check:{provider} {file}@{sha256[:8]}]` notes; move contradicted findings to `run.demoted` before synthesis; set `run.source_check_summary` counts string. Unmatched/ambiguous queue entries get their explanatory note and stay put.
10. `pat_helper/lenses/_source_check.md`: system prompt — you have the SOURCE a paper cites; another reviewer flagged the paper's characterization of it as unverifiable-from-the-paper; determine whether the source supports the critique; quote the source verbatim; report the source's own identity; resolution definitions mirror the schema. (Teaching surface — write for a human reader too.)
11. `config.py` + `cli.py`: `sources_dir` field, `--sources` flag, help text.
12. `report.py`: render `run.source_check_summary` under `## Source check` when set.
13. `uv run pytest` — all green. Commit.

**Part C — validation (paid, ask Dan before firing)**
14. Fixture gate: add `tests/fixtures/sources/` with one tiny fake source; plant a citation-mismatch defect in the harness defects file for the fixture paper; run the fixture harness with `--sources`; expect the defect recalled via a source-check-upheld finding.
15. Live specimens (needs Dan: obtain Svanberg 2024 + Davidson 2026 PDFs → `pdftotext` → a sources dir under `data/`): re-run the two unverifiable findings from `data/harness_out_v9/reverify_2026-07-14.md` rows 6–7 through the stage; Dan adjudicates the resolutions. Record in `docs/active/source-check/results/` (sanitized — no draft quotes) with provenance header.

## Edge cases

- **Oversized source** (book-length extraction): cap source text passed to the check call (reuse the paper-size handling precedent; if truncated, note it — a gated demotion must not rest on a truncated source, so truncation forces max resolution `critique-confirmed`/`unresolved`, never `contradicted`).
- **Year drift** (working paper 2024 vs published 2025): exact-match year; on near-miss (±1) mark unresolved with a "possible version mismatch" note rather than guessing.
- **Diacritics/compound surnames** in citation extraction: NFC-normalize + casefold both sides.
- **Stale sidecar** entries (file deleted/renamed): prune on build; renamed file re-indexes under its new hash (content identical → same sha → cache hit).
- **Two matched findings, same source, different checkers**: cache prefix is per (provider, source) — priming must dedupe on that pair, not on source alone.
- **Finding whose citation is the paper's own artifact** ("replication package"): extraction yields no (surname, year) → unresolved by construction — the correct outcome; add a test documenting it.

## Plan Footer

**Testing Details** All tests exercise behavior: routing through `run_review` (which calls reach which fake provider, where findings land), gate overrides (a lying checker cannot demote), cache/sidecar effects observed as call counts, and the no-flag pin guarding every existing user. No type/dataclass tests; fakes echo through the real pipeline.

**Implementation Details**
- Schema objects module-level; identity is load-bearing for fakes
- Index provider = first healthy review provider (YAGNI over new cheap-model plumbing; noted for revisit)
- Deterministic matcher: model never selects files
- Both gates zero-API-cost, reusing `check_quote`
- Contradicted → demoted pre-synthesis, symmetric with refuted
- Provenance note format: `[source-check:{provider} {file}@{sha256[:8]}]`
- Sidecar is user-inspectable/hand-correctable JSON — teachable artifact
- Prime-then-fan-out per (checker, source), matching stages 1/3
- `source_check_summary` on `ReviewRun`, rendered only when stage ran

**What could change:** Live-specimen validation may show the prompt needs sharper resolution definitions (especially confirmed-vs-unresolved boundary). Dan's pending extras/demoted skim may add specimens or reveal the citation-extraction regex is too narrow for real critique text. Web fallback and per-source batching (approach C) are explicitly deferred, not designed against.

**Questions**
- Reuse `fuzzy_threshold=0.85` for source-quote grounding, or stricter for demotion-enabling quotes?
- Should `--sources` failure to find ANY index-able file be a hard error or a warning + relaxed-mode run? (Plan assumes warning + note.)

---
