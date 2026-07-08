# pat_helper kickoff — PAT paper, reframe to personal-scale, initial design brainstorm

**Date:** 2026-07-08
**Branch:** main
**Category:** Research / Design kickoff
**Repo state at end of session:** scaffolded, PAT paper+summary in place, no code yet
**Source discussion:** Started as an "add this paper" task in
`~/code/general-ai-abilities`; evolved into "so let's build something like it,
here" once the goals clarified.

## Summary

Dan asked me to add Google's **Paper Assistant Tool (PAT)** paper (Jayaram et
al. 2606.28277, June 26 2026) to the general-ai-abilities collection, then to
discuss implementability. Initial framing was policy-audience-facing ("how do we
demo this?"). Actual goal, surfaced later, is narrower and more actionable:
**a personal-scale review tool Dan can use on his own working papers, shippable
publicly as a teaching artifact for economists learning to use AI**.

Reframing changes the design substantially. This repo is where the reframed
project lives. This convo is the handoff artifact for the next brainstorming
agent.

## Provenance

- **Source paper (PAT):** `papers/Jayaram_Cohen-Addad__2606.28277__paper_assistant_tool.pdf`
  (also text extraction and full summary in `PAPER_SUMMARIES.md`)
- **Dan's concrete target paper for review-tool validation:** working paper
  "Half the Economy Is Already in AI's Reach" (Parshall & Lopez-Luzuriaga, March
  2026). Blog: <https://canaryinstitute.ai/blog/measuring-ais-economic-reach/>.
  PDF: <https://canaryinstitute.ai/papers/Parshall_Lopez-Luzuriaga_TaskExposure_2026.pdf>.
  Not copied into this repo — it's Dan's own artifact and the URL is stable.
- **Related conversation upstream** in general-ai-abilities (added PAT via
  `add-paper` skill, then reframed): no separate doc there — the paper add is
  in commit history around 2026-07-08.

## What PAT actually is (compressed)

Four-stage inference-scaling pipeline built on Gemini Deep Think:

1. **Segmenter** — break manuscript into overlapping/non-contiguous logical
   segments
2. **Adaptive Budgeter** — assign Light/Medium/High compute per segment by
   information density
3. **Deep Review** — parallel Deep Review agents, each with full-paper context,
   focused on one segment
4. **Global Synthesis** — dedup, severity-check, Google-Search-ground for
   hallucinated citations

**Results:** 89.7% error-detection on a Math/CS subset of SPOT vs 55.2% zero-shot
Gemini 3.1 Pro (34.5 pp gap). Not comparable to original SPOT 21.1% SOTA —
different grader. Pilot at STOC 2026 + ICML 2026 covering >4,700 submissions;
97% / 92% would-use-again; but only 55–65% of authors rated feedback as "mostly
or all grounded" (hallucination is still real).

**What's NOT in the paper:** prompts, thresholds, segmenter output schema,
grader definition, dedup algorithm, severity taxonomy, source code.

## The reframe (this is the load-bearing move)

Initial framing was policy-facing: "PAT as a demo of the 4-role taxonomy for AI
policy conversations." Real goal turned out to be:

1. **Primary:** tool Dan can use on his own papers before submitting
2. **Secondary:** shipped publicly as a teaching artifact for economists learning
   to use AI
3. **Tertiary (implicit):** informed by the PAT policy taxonomy but not driven
   by it

This inverts most of PAT's design constraints:

| PAT | pat_helper |
|---|---|
| 4,700 papers × 1 pass | ~5 papers × N iterations |
| Compute cost matters | Effectively free at 1-user scale |
| Segment-by-section (intro/theory/methods) | Segment-by-*review-lens* |
| Grader = "did we catch the SPOT retracted error?" | Grader = "did the tool surface something Dan would want to fix?" |
| Math-proof rigor | Empirical rigor, causal ID, coalition framing, argumentation |
| Ship = deploy | Ship = teach economists how to use it |

The *pattern* transfers cleanly — parallel review, search-grounded synthesis,
dedup by severity. The *lens set* has to be reinvented for econ/policy writing.

## Draft lens set (open for challenge)

For AI Policy / economic-impact papers rather than CS/math:

1. **Empirical rigor** — statistics, sample sizes, effect sizes, robustness
2. **Causal identification** — is the paper claiming causation? confounders?
   IV/RD/DiD checks?
3. **Prior-work grounding** — engaging with relevant literature? opposing views
   steelmanned? load-bearing numbers matched to primary sources?
4. **Framing / coalition risk** — factional language, presuppositions, hooks
   that read as advocacy (per Dan's own "AI Policy" vs "AI Safety" note)
5. **Argumentation** — logical leaps, unsupported transitions, load-bearing
   claims that get dropped
6. **Data / source quality** — primary vs secondary sources, URL-rot resistance,
   numeric verifiability
7. **Structural / clarity / honest-scoping** — abstract matches content? key
   claims findable? explicit "what this doesn't tell you" sections?
8. **Reproducibility** — computational reproducibility of stated results; prompt
   / model versioning

Not settled. The next agent should challenge this set. Two obvious tensions:

- **Are 8 lenses too many?** With multi-model triangulation, cost grows N×M
  (models × lenses). Consider consolidating (e.g., empirical rigor + reproducibility)
  or making lenses adaptive per-paper.
- **Are these the right lenses for econ specifically?** Might be worth asking
  actual econ reviewers or reading a few recent NBER / AEA reviewer guidelines
  to calibrate.

## Design commitments (working, not settled)

1. **Provenance-first output.** Every critique tagged with
   `{lens, model, quote, evidence, severity, suggested-fix}`. Makes it teachable.
2. **Multi-model as a first-class feature.** Run the same lens through Claude /
   GPT / Gemini in parallel. Convergent → probably real. Divergent → probably
   hallucinated or subjective. **This is the pedagogical spine for the "teach
   economists" goal** — showing them how to triangulate rather than trust one AI.
3. **Public-shippable via Colab notebook, not a service.** Reviewable prompts,
   forkable, worked example on Dan's own paper. Sidesteps the "who trained your
   reviewer?" question.
4. **Lens set is econ/policy-domain-specific.** Explicitly not PAT's math-proof
   orientation.

## Concept demo — hand-run review of Dan's blog post

I read <https://canaryinstitute.ai/blog/measuring-ais-economic-reach/> and did a
by-hand pass with a few lenses to show what the tool should produce. Findings:

- **⚠️ HIGH SEVERITY — prior-work grounding:** the blog post's claim
  "autonomous task horizons are doubling roughly every three months" doesn't
  match either of the primary sources in Dan's own paper collection. Kwa et al.
  = 182-day CoT doubling; Gould/Stastny et al. 2606.07157 = 373-day no-CoT
  doubling. The "3 months" figure is closest to ByteDance EdgeBench 2026, but
  that's *post-deployment in-context learning doubling*, a completely different
  construct. **Recommend:** cite Kwa's ~6-month figure and hedge, OR be explicit
  about which construct the 3 months refers to. This is the kind of catch a
  competent-lens reviewer bot with access to Dan's own paper library should
  make easily.

- **MEDIUM — empirical rigor:** "50.5%" reported with no CI. Inter-model
  agreement rate across Sonnet 4.6 / GPT-5-mini / Gemini 3 Flash isn't given.
  Add one-sentence κ / % agreement per axis.

- **MEDIUM — causal ID (definitional):** "Thin chokepoint thesis" presented as
  observation. Could be read as circular ("we defined R such that most tasks are
  R0–R1, then concluded regulation is thin"). One clarifying paragraph on the
  operational R-axis definition would close it.

- **LOW — framing:** "The policy window for AI's labor market effects is closing
  faster than the policy conversation is moving" presupposes there IS a closing
  window and that policy should respond. Neutral rewrite available.

- **POSITIVE FLAG — structural scoping:** the "What This Doesn't Tell You"
  section is exemplary honest scoping. Any auto-review should NOT flag this as
  a defect and ideally should identify it as a strength.

That took ~10 minutes of reading + reflection by hand. Point: this is
*exactly* the kind of pass a Claude-based reviewer could do in ~90 seconds if
the lenses are prompted well.

The "3-month task horizons" catch specifically demonstrates the value of
**cross-referencing against Dan's own primary-source library** — a lens agent
with access to `~/code/general-ai-abilities/PAPER_SUMMARIES.md` would find that
mismatch directly.

## What's in this repo now

Bootstrapped 2026-07-08:

- `README.md`, `CLAUDE.md`, `STATUS.md`, `.gitignore`
- `PAPER_SUMMARIES.md` (PAT summary, ready to grow)
- `papers/Jayaram_Cohen-Addad__2606.28277__paper_assistant_tool.pdf`
- `papers/text/Jayaram_Cohen-Addad__2606.28277__paper_assistant_tool.txt`
- `docs/convos/main/20260708_pat_kickoff_and_reframe.md` (this file)
- `docs/active/`, `docs/historical/` (empty, ready for future branches)

No code yet. That's the next agent's job (partial — see below).

## Open questions for the next agent

Dan said the next step is a fresh brainstorming agent. Here's the list of what's
worth pushing on:

1. **Is the 8-lens set right for AI Policy / econ-impact writing?** Challenge
   the specific lenses. Consider asking Dan for a paper he *doesn't* want to
   share publicly to test the lens set against.
2. **Multi-model triangulation implementation.** Cheapest good design? Vote,
   embed-cluster, LLM-judge dedup, or something smarter? Where does the
   "teach economists" pedagogical value actually manifest in the output format?
3. **Input format decision.** PDF is universal but lossy. Markdown is clean but
   Dan probably drafts in LaTeX or Google Docs. Which do we support first?
   Answer probably affects segmenter design.
4. **Output format.** Markdown review file with anchored critiques is the
   obvious default. Does it need to render inline in Overleaf / a PDF viewer /
   a Google Doc? Second-order design question but affects target UX.
5. **What's the shipping form?** Colab notebook, Python CLI, Claude Code slash
   command, VSCode extension? The "teach economists" goal biases toward Colab
   (economists can read, fork, and understand). But Dan's own iteration loop
   might be better served by a slash-command.
6. **Validation.** How do we know the tool works? Do we need a mini SPOT-analog
   for econ policy papers? Or is "Dan runs it on 3 successive drafts and reports
   which critiques he acted on" enough of a signal?
7. **Should we lean on the `Workflow` tool for the pipeline itself, or write
   plain Python?** Workflow gives free parallelism + progress reporting;
   plain Python is more portable for a Colab notebook. This is probably the
   first major architectural decision.
8. **Cross-referencing the paper library.** The "3-month task horizons" catch
   above only worked because I had access to Dan's paper collection. Should
   pat_helper have a mode where it consults `~/code/general-ai-abilities/PAPER_SUMMARIES.md`
   during review? What if it's someone else's collection?

## Not open for challenge (Dan's stated preferences)

- Python over Bash for anything non-trivial
- "AI Policy" framing over "AI Safety" for external-facing writing
- Multi-model triangulation is a stated design goal, not up for debate — but
  the *implementation* is
- Honest pushback expected, not softened technical objections

## References

- Jayaram et al. 2606.28277 (in this repo)
- Dan's working paper: Parshall & Lopez-Luzuriaga 2026, "Task Exposure"
  (canaryinstitute.ai)
- Dan's paper collection: `~/code/general-ai-abilities/PAPER_SUMMARIES.md`
- Dan's personal-info notes: `~/.claude/CLAUDE.md` — auto-synced from
  `~/code/dotfiles/claude/personal_info.md`
