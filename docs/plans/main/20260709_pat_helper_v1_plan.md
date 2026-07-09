# pat-helper v1 Implementation Plan

**Goal:** Build the v1 review pipeline — LaTeX in → 8 lenses × 3 models async
fan-out → mechanical quote-check → adversarial verify → synthesis → markdown
report — plus a planted-error validation harness.

**Originating conversation:** `docs/convos/main/20260709_v1_design_brainstorm.md`
(design approved there; upstream context in
`docs/convos/main/20260708_pat_kickoff_and_reframe.md`)

**Context:** Personal-scale, econ/AI-Policy analog of Google's PAT (Jayaram et
al. 2606.28277). PAT's segmenter+budgeter solve a scale problem we don't have;
we replace them with rigor machinery (quote grounding + adversarial
verification) targeting PAT's documented weakness — only 55–65% of pilot
authors rated its feedback as grounded. Secondary goal: shippable teaching
artifact for economists, so lens prompts are plain data files and provenance
is never dropped.

**Confidence:** Design approved by Dan after structured brainstorm, but zero
empirical validation yet — the planted-error harness in this plan is what
converts the design arguments into measurements. Expect the lens set and the
verify stage to change based on harness results.

**Architecture:** Plain Python 3.12 + asyncio (explicitly NOT the Claude Code
Workflow tool — portability to a future Colab is a hard requirement). One
common provider interface, three thin clients. Deterministic markdown renderer
(code, not model). Findings are dataclass-shaped JSON with full provenance:
`{lens, model, quote, evidence, severity, suggested_fix}`.

**Branch:** main (fresh repo, sole active line — deviation from worktree
convention noted in the convo doc)

**Tech Stack:** Python 3.12, uv, pyproject.toml, pytest, ruff, `anthropic`
(AsyncAnthropic), `openai`, `google-genai`, `pyyaml`. No framework, no
LangChain.

---

## Testing Plan

I will write **all tests before any implementation code**, with fake provider
clients (never live API calls in pytest):

- **LaTeX loader (behavior):** given a fixture `main.tex` with `\input{sec1}`,
  comments, and math — flattening resolves the input, strips `%` comments
  (but not `\%`), and the line map converts flattened-text offsets back to
  `(file, line)` pairs correctly.
- **Quote-check (behavior):** exact match found; match after whitespace/quote
  normalization (curly→straight, `--`→`-`); fuzzy match above threshold with
  its score; a fabricated quote returns no-match. Verify the returned
  source location, not just a boolean.
- **Report renderer (behavior):** given a list of Finding objects — output
  groups by severity in order HIGH→MED→LOW→POSITIVE, every finding renders
  all provenance fields, ungrounded findings appear only in the appendix
  section, convergence line lists contributing models.
- **Pipeline orchestration (behavior, fake clients):** 8 lenses × 3 fake
  providers → 24 calls issued; one provider raising twice then succeeding is
  retried; one provider failing permanently degrades to a recorded gap (run
  still completes, gap noted in report); refuter model differs from finder
  model for every verify call; synthesis receives only quote-check survivors;
  findings the refuter kills are demoted, not deleted.
- **Defect injector (behavior):** applying `defects.yaml` to a fixture .tex
  produces exactly the specified mutations at the specified locations, and
  the injection manifest round-trips (we can locate every planted defect).

Integration (live APIs) is manual, not pytest: `pat-helper review <tex>` on a
small fixture paper, then the harness run on Dan's real paper once the `.tex`
arrives.

NOTE: I will write *all* tests before I add any implementation behavior.

---

## Tasks

### Phase 0 — scaffold
1. Write `.python-version` (3.12), `pyproject.toml` (project `pat-helper`,
   package `pat_helper`, deps above; dev deps pytest, ruff).
2. Run `uv venv && uv sync`; add `.venv/`, `.env`, `data/` to `.gitignore`;
   write `.env.example` (ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY).
3. Commit scaffold.

### Phase 1 — tests first
4. Create `tests/fixtures/` mini paper (`main.tex` + `\input` section files,
   ~2 pages, containing quotable sentences and a known "defect").
5. Write `tests/test_latex.py` (loader behaviors above). Run: fails.
6. Write `tests/test_quotecheck.py`. Run: fails.
7. Write `tests/test_report.py`. Run: fails.
8. Write `tests/test_pipeline.py` with `FakeProvider` (scriptable responses/
   failures) — orchestration behaviors above. Run: fails.
9. Write `tests/test_injector.py`. Run: fails.
10. Commit failing tests.

### Phase 2 — core modules
11. `pat_helper/models.py` — dataclasses: `Finding` (lens, model, quote,
    evidence, severity enum, suggested_fix, grounding score/location, verify
    verdict), `LensSpec`, `ReviewRun` (per-cell status), plus JSON schema dict
    for provider-forced output.
12. `pat_helper/latex.py` — flatten + line map. Make test_latex pass.
13. `pat_helper/quotecheck.py` — normalize (whitespace, unicode quotes/dashes,
    LaTeX artifacts like `~` and `\%`), substring match, sliding-window
    `difflib` fallback with threshold ~0.85, return (score, location).
    Make test_quotecheck pass.
14. Commit.

### Phase 3 — providers + lenses
15. `pat_helper/providers/base.py` — `async def complete_json(system, user,
    schema) -> dict` interface + shared retry/backoff wrapper (rely on SDK
    retries first; one outer retry for JSON-parse failures with a schema
    reminder appended).
16. `pat_helper/providers/anthropic_client.py` — AsyncAnthropic,
    `claude-opus-4-8`, structured output via `output_config.format`
    json_schema (per claude-api skill guidance; adaptive thinking, streaming
    for long outputs).
17. `pat_helper/providers/openai_client.py`, `google_client.py` — per the
    web-research report on current model IDs and structured-output idioms
    (do NOT write from memory; check research results first).
18. `pat_helper/config.py` — model IDs, thresholds, lens list all in one
    place, overridable via CLI flags. Models are config, never hardcoded in
    pipeline logic.
19. `pat_helper/lenses/*.md` — 8 lens prompts (empirical-rigor, causal-id,
    prior-work, framing-coalition, argumentation, sources, structure-scoping,
    reproducibility). Each: role, what to look for, what NOT to flag
    (include the "don't punish honest scoping" instruction — the kickoff's
    POSITIVE-FLAG case), output schema reminder, severity rubric. Also
    `verify.md` (refuter prompt: "try to refute this critique; default to
    refuted if the quote doesn't support the claim") and `synthesis.md`
    (dedup/merge/rank; merge provenance; never invent findings).
20. Commit.

### Phase 4 — pipeline, report, CLI
21. `pat_helper/pipeline.py` — `asyncio.gather` fan-out with semaphore
    (limit ~8 concurrent); quote-check gate; verify stage (refuter = next
    model in rotation ≠ finder); synthesis call (flagship, JSON in/out);
    assemble `ReviewRun`. Make test_pipeline pass.
22. `pat_helper/report.py` — deterministic renderer. Make test_report pass.
23. `pat_helper/cli.py` + `[project.scripts] pat-helper` entry point:
    `pat-helper review paper.tex [--models ...] [--lenses ...] [--out dir]`.
24. Full pytest + ruff; commit.

### Phase 5 — planted-error harness
25. `harness/defects.yaml` — schema: `{id, lens_expected, description,
    location: {file, line-ish anchor string}, original, mutated}`; seed with
    ~10 defect templates against the fixture paper.
26. `harness/inject.py` — apply defects to a copy; emit manifest. Make
    test_injector pass.
27. `harness/score.py` — run pipeline on mutated copy, LLM-judge match
    findings↔defects (cheap model), report recall + extras list.
28. Commit. Live run deferred until Dan's `.tex` lands in `data/`.

### Phase 6 — wrap
29. Smoke-test `pat-helper review tests/fixtures/main.tex` live (all three
    providers, one lens) if keys present; fix what breaks.
30. README quickstart section; update-docs checkpoint; final commit.

---

## Edge cases to handle

- Lens×model cell fails all retries → record gap in `ReviewRun`, render a
  "coverage gaps" note in the report; never crash the run.
- Model returns valid JSON but wrong shape → one retry with schema reminder,
  then treat as failed cell.
- Quote spans a line break / LaTeX comment / `\input` boundary → normalize
  before matching; fuzzy fallback.
- Zero findings from a lens (legit for a good paper) → render "no findings"
  not an error.
- Duplicate findings across models with different wording → synthesis merges;
  test asserts merged provenance keeps both model names.
- Paper text exceeding a provider's context (unlikely at ~30pp) → hard error
  with token count, no silent truncation (per claude-api skill guidance).
- `\%` vs `%`: comment stripping must not eat escaped percents (econ papers
  are full of them).

## Questions / areas needing clarity (non-blocking)

- Exact OpenAI/Gemini model IDs + structured-output idioms → pending
  web-research subagent; config-file change if wrong.
- Verify-stage severity policy: refute HIGH+MED only (planned) or all?
  Cheap to flip in config; harness should compare.
- Where Dan's real `.tex` lands (`data/`, gitignored) — waiting on Dan.

---

**Testing Details:** All tests written first against behavior: latex
flattening semantics, quote-grounding outcomes (found/normalized/fuzzy/miss +
location), renderer output structure, and orchestration behavior via
scriptable FakeProvider (retry, degradation, refuter rotation, demote-not-
delete). No tests of dataclass shapes; no tests that merely assert mocks were
called.

**Implementation Details**
- Provider interface is one async method returning parsed JSON; SDK-level
  retries preferred over hand-rolled loops.
- Anthropic: `claude-opus-4-8`, `output_config.format` json_schema, adaptive
  thinking, streaming for long outputs (claude-api skill, verified 2026-07-09).
- Lens prompts are data (`.md`), not code — the public teaching surface.
- Renderer is deterministic code; the synthesis model outputs JSON only.
- Refuter model must differ from finder model (rotation).
- Ungrounded/refuted findings are demoted to an appendix, never silently
  dropped — pedagogical artifact.
- Config in one module; model IDs never hardcoded elsewhere.
- API keys via `.env` (python-dotenv or os.environ); `data/` gitignored for
  Dan's unpublished drafts.

**What could change:** Lens set consolidation (harness-driven); verify-stage
scope/thresholds; quote-check fuzzy threshold; OpenAI/Gemini model IDs
(pending research); output format may grow an annotated-.tex emitter later
(explicitly deferred); corpus cross-ref seam = optional extra-context param
on the prior-work lens.

**Questions:** See non-blocking list above. Nothing blocks starting Phase 0.

---
