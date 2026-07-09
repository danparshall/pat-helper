# Harness prep + v1 hardening — Task Exposure .tex built, load_paper & judge tightened

**Date:** 2026-07-09
**Branch:** main
**Prior convo:** `docs/convos/main/20260709_v1_design_brainstorm.md`
**Plan produced:** `docs/plans/main/20260709_v1_hardening_try_except.md`

## Summary

Handoff session picking up from the same-day v1 build. Goal was to prep the
live harness run for STATUS's two "Next actions": (1) fixture smoke test,
(2) real Task Exposure recall measurement. Neither ran — both are gated on
`.env` API keys, which only Dan can drop.

The bulk of the session went to three preparatory fixes that surfaced during
harness-prep and would otherwise have shown up as flaws mid-run. **B**
(`load_paper` preamble strip) and **C** (judge model → OpenAI) landed in this
session; **A** (graceful CLI degradation for missing keys) was deferred to a
follow-up session with a written plan doc, because Dan flagged context-budget
concerns and A is the biggest of the three.

Also built the Task Exposure paper's `.tex` from its Markdown source (turned
out the .tex is a build artifact, not a source file — Dan wasn't sure where
it lived because there wasn't one until we made one).

## Topics Explored

- Located the "Task Exposure paper" — it's the **CDR Framework paper**
  (Parshall & Lopez-Luzuriaga 2026), URL-slugged as `TaskExposure` on
  canaryinstitute.ai but internally named `CDR_Framework_draft_v*.md` in
  `~/code/econ-impact/drafts/`. The `.tex` doesn't exist as a source file —
  the paper is drafted in Markdown and compiled via
  `drafts/latex/Makefile` (`preprocess.py + pandoc → paper.tex`).
- Verified pat-helper scaffolding (26/26 tests green, `.venv` intact) and
  attempted a dry-run CLI on the fixture without keys → hard crash. This
  contradicted STATUS's "CLI degrades gracefully without keys" claim.
- Reviewed the pipeline / providers / config layer to plan the try/except
  approach for `_build_providers`.
- Session-start claude-exit termination ceremony ran clean; target process's
  model string (`claude-opus-4-7[1m]`) is newer than the price table in
  `personal_info.md` (dated March 2026) — table likely stale.

## Provisional Findings

- **STATUS.md line 21's "CLI degrades gracefully without keys" is
  empirically false.** `_build_providers` at `cli.py:20-38` unconditionally
  constructs each provider's SDK client; `AsyncOpenAI()` / `AsyncAnthropic()`
  / `genai.Client()` all raise at construction if their env var is unset.
  Verified with `uv run pat-helper review tests/fixtures/main.tex` → crashes
  with `openai.OpenAIError: Missing credentials`. The pipeline itself does
  degrade per-call (the tests confirm this with fake providers), but you
  cannot reach that code path from CLI without at least one usable provider.
- **Pandoc-generated `.tex` files carry ~100 lines of LaTeX preamble** that
  the lens agents would consume as context for zero review value. On the
  built `task_exposure_v9.tex`: preamble stripped 102 lines / ~2.7 KB.
- **CDR Framework paper is presumed = Task Exposure paper.** Confirmed by
  the abstract of `sections/abstract_original.md` — three-axis (C, D, R)
  taxonomy of "AI task exposure," matches the canaryinstitute URL slug.

## Decisions Made

1. **Built `task_exposure_v9.tex`** from `CDR_Framework_draft_v9.md` (v9
   chosen by Dan over v7/v8/skip) via the `drafts/latex/Makefile`; copied
   to `pat-helper/data/task_exposure_v9.tex` (gitignored). `econ-impact`'s
   worktree restored to clean state with `make clean`.
2. **`load_paper` preamble strip landed** (`pat_helper/latex.py`) — added
   `_strip_document_envelope()` that slices between `\begin{document}` and
   `\end{document}` markers, pass-through for fragments without either.
   4 new tests (TDD, RED → GREEN); 30/30 green total.
3. **Judge model → OpenAI landed** (`pat_helper/config.py` + `harness/run.py`):
   `JUDGE_MODEL = ("openai", "gpt-5.6-terra")` per Dan's "OpenAI is our
   cheap default" note. Cost drops ~3× vs. Anthropic Haiku. Harness dispatch
   via `_JUDGE_CLASSES` map so future switches are one-line.
4. **Graceful-degradation plan deferred** — written up as
   `docs/plans/main/20260709_v1_hardening_try_except.md` for a follow-up
   session. Chose try/except-on-SDK-error over env-var probe (preserves
   `ant auth login` profile and `OPENAI_ADMIN_KEY` cases).
5. **Not** reordering CLI `--providers` default. "OpenAI is our default"
   read narrowly as "for the judge / cheap path," not as a mandate to skip
   the multi-model triangulation the tool exists for. Flagged for pushback
   in the handoff message but Dan didn't push back.

## Results

No results files this session — no live runs executed (harness blocked on
`.env`). The `data/task_exposure_v9.tex` file is a build artifact staged
for the future harness run, not a session result.

## Open Questions

- **Does `_JUDGE_CLASSES` dispatch in `harness/run.py` want to be folded
  into `_build_providers` when A lands?** Right now the judge has its own
  small dispatch table because `_build_providers` reads models from
  `config.models` and the judge wants `JUDGE_MODEL[1]` instead. A cleaner
  design might extend `_build_providers` with a `model_override` kwarg —
  worth reconsidering while implementing plan A.
- **Preamble strip is naive** — searches the whole flattened text for
  `\begin{document}` and `\end{document}`. If an `\input`'d child ever
  contained those markers (unusual but possible), the slice would go
  wrong. Not fixing now; flag for revisit if seen.
- **Should the Task Exposure paper's build source be pinned in the repo?**
  Right now `task_exposure_v9.tex` was hand-built from a specific
  `econ-impact` draft version; no record in `data/` of which draft or
  which commit of `econ-impact`. If Dan iterates the CDR draft and rebuilds,
  the harness measurements aren't reproducible without provenance.
  Cheap fix: a sibling `task_exposure_v9.provenance` file with the source
  path + `econ-impact` commit hash.

## Session Notes

- Under Dan's "auto mode" — biased toward action, asked one AskUserQuestion
  (draft version), got a green light, kept moving.
- Chain-hook fired twice on `&&` chains; split into single-verb Bash calls
  and continued. No policy issues.
- Followed TDD for B (red tests first, then green implementation).
- Repeated task-tool reminders ignored — session was linear enough that a
  TodoList would have been ceremony.
