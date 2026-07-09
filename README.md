# pat-helper

Personal-scale review assistant for AI Policy / economic-impact papers.

Modeled on Google's **Paper Assistant Tool (PAT)** (Jayaram et al. 2606.28277,
June 2026) but reoriented for a single-author use case:

- Strengthen my own working papers before submission / posting
- Teach economists how to use AI productively (multi-model triangulation as a
  first-class feature, not a nice-to-have)
- Ship a public artifact — Colab-notebook style — that others can fork

**Design goal:** parallel review agents each running a domain-relevant lens
(empirical rigor, causal identification, prior-work grounding, framing/coalition
risk, argumentation, sources, structural scoping, reproducibility) → search-
grounded synthesis → dedup'd, severity-ranked, provenance-tagged review file.

## Provenance

Repo initialized 2026-07-08. Kicked off from a conversation in
`~/code/general-ai-abilities` (commit `fb73af4` era) where I asked "how close are
we to implementing Google's PAT based on what's described?" The answer was
"~70% of the pipeline is transferable but the lenses need a complete rebuild for
econ/policy work." This repo is where that rebuild lives.

Source paper + summary + kickoff convo in `docs/convos/main/`.

## Quickstart

```bash
uv venv && uv sync
cp .env.example .env   # fill in ANTHROPIC_API_KEY / OPENAI_API_KEY / GEMINI_API_KEY
uv run pat-helper review path/to/main.tex
```

Output: `review_<paper>_<date>.md` — findings grouped by severity, each tagged
`{lens, models, quote, evidence, suggested-fix}`, with demoted (ungrounded or
refuted) findings kept in an appendix and coverage gaps reported. Providers
and lenses are subsettable: `--providers anthropic --lenses causal-id,sources`.
Missing keys degrade to recorded gaps, never a crash.

**Pipeline:** 8 lenses × 3 models fan out in parallel (every call sees the
full paper) → every quote is **mechanically checked** against the source
(hallucinated quotes demoted, zero API cost) → HIGH/MEDIUM findings face an
**adversarial verifier from a different model** → one synthesis call dedups,
merges, and records convergence → deterministic markdown renderer. Where PAT
had a segmenter + compute budgeter (scale machinery), pat-helper has
grounding + refutation (rigor machinery).

Lens prompts live in `pat_helper/lenses/*.md` as plain markdown — read them,
fork them; they are the teaching surface.

**Validation:** `uv run python harness/run.py <main.tex>` plants known defects
(`harness/defects.yaml`), reruns the review, and scores recall via an LLM
judge.

## Directory layout

- `pat_helper/` — the package (pipeline, providers, lenses, report, CLI)
- `harness/` — planted-error validation harness
- `tests/` — pytest suite (fake providers; no live API calls)
- `data/` — gitignored; unpublished drafts under review live here
- `docs/convos/main/` — session convo docs on the main line of work
- `docs/plans/main/` — implementation plans
- `docs/active/` / `docs/historical/` — active / archived research lines
- `papers/`, `papers/text/`, `PAPER_SUMMARIES.md` — reference papers (PAT)
- `STATUS.md` — recent sessions, current focus

## Status

v1 pipeline implemented (2026-07-09); tests green. Awaiting first live
validation run on a real paper. See `STATUS.md` for current focus.
