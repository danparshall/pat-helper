# pat-helper — Claude instructions

## Purpose

A personal-scale, econ/policy-domain analog to Google's **Paper Assistant Tool**
(PAT, Jayaram et al. 2606.28277). Built to strengthen Dan Parshall's own working
papers and to serve as a teaching artifact for economists learning to use AI.

The design pattern is transferred from PAT — parallel per-segment review agents
+ search-grounded synthesis + dedup with severity ranking — but the *review
lenses* have been rebuilt for AI Policy / economic-impact writing rather than
mathematical proof verification.

## Research Context

This is an active research project. All findings are provisional — evidence
accumulates gradually.

**Document structure:**
- `docs/convos/main/` — session convo docs on the main line of work (kickoff
  and most day-to-day work will land here)
- `docs/active/<branch-name>/` — active named research lines; each has its own
  `convos/`, `plans/`, `results/`, and `RESEARCH_LOG.md`
- `docs/historical/<topic>/` — archived research lines. **Do NOT read unless the
  user specifically asks.** STATUS.md's "Archived Research Lines" table
  summarizes what's there.

**Epistemic norms:**
- Do NOT treat any prior doc as settled truth — this is a fresh repo and every
  design choice is still open
- Read `docs/convos/main/*.md` to understand the trajectory of thinking
- When Dan says "the data showed X, let's pivot," trust him — he's seen results
  you haven't

## Design commitments (subject to revision)

Not settled — these are the working assumptions coming out of the kickoff
convo (see `docs/convos/main/20260708_pat_kickoff_and_reframe.md`):

1. **Provenance-first output.** Every critique tagged with
   `{lens, model, quote, evidence, severity, suggested-fix}`. Makes it
   teachable.
2. **Multi-model as a first-class feature.** Run the same lens through
   Claude/GPT/Gemini in parallel. Convergent critiques → probably real.
   Divergent → probably hallucinated or subjective. This is *the* pedagogical
   value for economists.
3. **Public-shippable via a Colab notebook, not a service.** Reviewable prompts,
   forkable, worked example on Dan's own paper. Sidesteps "who trained your
   reviewer?".
4. **Lens set is domain-specific.** Empirical rigor, causal ID, prior-work
   grounding, framing/coalition, argumentation, sources, structural scoping,
   reproducibility. Explicitly NOT PAT's math-proof orientation.

## Working style

- Python over Bash for anything non-trivial (Dan reads Python fluently and wants
  to double-check the logic)
- Dan pushes back and expects to be pushed back on — "I have blind spots and I'd
  rather hear your real objection than a softened version of it"
- Prefer "AI Policy" framing over "AI Safety" — factional connotations matter
  for policymaker-facing writing
- On any substantive claim about model capabilities or timelines, cross-
  reference the primary source (`~/code/general-ai-abilities/PAPER_SUMMARIES.md`
  is a good starting index for what's already read)
