# pat_helper

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

## Directory layout

- `docs/convos/main/` — session convo docs on the main line of work
- `docs/active/` — active named research lines (per branch)
- `docs/historical/` — archived research lines
- `papers/` — reference PDFs (source paper: PAT)
- `papers/text/` — text extractions
- `PAPER_SUMMARIES.md` — summary of PAT and any future reference papers
- `STATUS.md` — recent sessions, current focus, archived research lines

## Status

Kickoff stage — no code yet. See `STATUS.md` for current focus.
