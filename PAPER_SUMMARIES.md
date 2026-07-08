# Paper Summaries

Reference papers this project builds on. Full PDFs in `papers/`, text
extractions in `papers/text/`.

---

### Towards Automating Scientific Review with Google's Paper Assistant Tool (PAT)

- **arXiv:** [2606.28277](https://arxiv.org/abs/2606.28277)
- **Authors:** Rajesh Jayaram, Drew Tyler, David Woodruff, Corinna Cortes, Yossi Matias, Vahab Mirrokni, Vincent Cohen-Addad (all Google Research; Woodruff also CMU)
- **Date:** June 26, 2026
- **File:** `Jayaram_Cohen-Addad__2606.28277__paper_assistant_tool.pdf`
- **Related blog posts:** [STOC 2026 pilot](https://research.google/blog/gemini-provides-automated-feedback-for-theoretical-computer-scientists-at-stoc-2026/), [ICML 2026 pilot](https://blog.icml.cc/2026/01/14/icml-experimental-program-using-googles-paper-assistant-tool-pat/)

**Summary:** Introduces the Paper Assistant Tool (PAT), an agentic scaffold for
end-to-end scientific paper review built on Google's Gemini Deep Think, and reports on
pilot deployments as a pre-submission tool for authors at STOC 2026 and ICML 2026
(>4,700 submissions total). Separately, the paper proposes a four-role
"AI-in-peer-review" taxonomy modeled after SAE levels of vehicle autonomy, positioning
PAT explicitly at Role 1 (Tool for Authors).

**Architecture — four stages:**

1. **Segmenter.** An "agent" (paper doesn't specify model) breaks the manuscript
   into logical segments (intro, theory, methodology, experiments, etc.) — segments
   are allowed to overlap and be non-contiguous.
2. **Adaptive Budgeting.** The segmenter assigns each segment a compute budget
   from a three-track thinking regime (Light for intro/conclusion,
   Medium for methodology/experiments, High for theory/proofs). The paper describes
   the tracks conceptually but does not publish thresholds, prompts, or the
   complexity-classification rule.
3. **Deep Review.** Specialized parallel Deep Review agents (Gemini Deep Think, or
   an unnamed "other proprietary inference-scaling pipeline") verify each segment
   with the *full* paper as context. The parallelism is the inference-scaling knob;
   coordination across parallel calls is claimed but the mechanism is not detailed.
4. **Global Synthesis.** A synthesis agent deduplicates critiques across segments,
   assigns severity, and uses **Google Search** to ground-check for hallucinated
   citations, non-existent theorems, and similar failure modes before emitting the
   final review.

The design is motivated as a fix for two failure modes of naive Pass@k inference
scaling: (a) context-budget contention when independent calls all attend to the
same sections, and (b) precision degradation as k grows and reviewers accumulate
hallucinated "issues." Segment-scoped review addresses (a); synthesis with search
grounding addresses (b).

**Key findings:**

- **SPOT benchmark case study (Math/CS "Equation/proof" subset, n=26 papers /
  29 errors):**

  | Verifier | Detection accuracy |
  |---|---|
  | Original SPOT SOTA | 21.1% |
  | Gemini 3.1 Pro zero-shot | 55.2% |
  | PAT (Gemini 3.1 Pro) | 89.7% |

  PAT's 89.7% is a 34.5 pp gain over the same base model's zero-shot recall (the
  paper rounds this to "a 34% improvement"). **Important caveat: the 21.1% SPOT
  SOTA number is not comparable** — PAT uses an LLM-based "logic-aware" grader
  that scores mathematically equivalent phrasings as correct, whereas the original
  SPOT paper used an exact-keyword grader. Both PAT and its zero-shot baseline
  benefit from the more permissive grader; the ~34 pp *within-grader* gap is the
  meaningful number.

- **STOC 2026 pilot** (Nov 2025, TCS-specialized math-only pipeline; n=124 survey
  respondents) and **ICML 2026 pilot** (Jan 2026, generalized pipeline; n=733
  survey respondents; >4,700 total submissions):

  | Metric | STOC | ICML |
  |---|---|---|
  | Would use PAT again | 97% | 92.1% |
  | Improved clarity/readability | 85.1% | 87.0% |
  | Believes PAT has educational value | 75.2% | 83.9% |
  | Very or mostly helpful | 92.7% | 90.7% |
  | Feedback mostly or all grounded (factual) | 55.8% | 64.8% |
  | Identified substantive theory gaps (>1 hr to fix) | 11.6% | 35.4% |
  | Ran new experiments as a result | — | 31% |

  The ICML rate for "substantive theory gaps" (35%) is much higher than STOC's
  (12%) because ICML submissions carry lower baseline math-rigor expectations, not
  because PAT is stronger there. That STOC still surfaced errors requiring >1 hour
  of fixes in ~1/10 papers is notable because STOC proofs are rarely checked end-
  to-end during human review.

- **Grounding gap.** Only 55.8% / 64.8% of respondents rated PAT's feedback as
  "mostly or all grounded" — i.e., ~35–45% of authors saw non-trivial
  hallucination in the review. The paper flags this as the third of three headline
  limitations from pilot feedback: (1) date/knowledge-cutoff hallucinations,
  (2) PDF parsing failures, (3) falsely claiming a valid proof is wrong. (1) and
  (2) they claim to have addressed; (3) remains open.

- **Human-baseline anchor for Roles 3–4.** The paper cites the NeurIPS 2021
  consistency experiment (23% inconsistency rate in acceptance decisions across
  two independent committees, vs 35% for random selection at 22.7% acceptance;
  16% excluding borderline cases). This is deployed as the "the human baseline is
  already noisy" argument that Role 3/4 arguments will need.

**Four-role taxonomy (SAE-style, adapted from Feng et al. 2602.10177):**

- **Role 1 — AI as Tool for Authors.** PAT's current deployment. Authors
  responsible. Risk: makes papers look superficially stronger, forcing reviewers
  to work harder to distinguish quality tiers.
- **Role 2 — AI as Tool for Reviewers.** Reviewer uses AI to draft. Risk: reviewer
  hides usage and doubles down on hallucinated critiques during rebuttal. Requires
  disclosure policy plus author flagging mechanism.
- **Role 3 — AI as Supporting Reviewer.** AI writes a full independent review;
  human is now Area Chair, not reviewer. Role 3.5 adds subjective ratings. Frees
  human bandwidth; risk shifts from labor to error propagation into decisions.
- **Role 4 — Total Automation.** "AIrXiv" concept — a preprint-like repository
  gating publication on multi-round automated review. Introduces novel prestige
  tier between arXiv and journal. Named risks: reduction in diversity of opinion
  from centralized AI viewpoints, adversarial gaming, algorithmic bias,
  equitable-access-to-compute issues.

**Implementation-relevance caveats (for reproduction):**

- **No prompts released.** Segmenter, budgeter, Deep Review, and synthesis prompts
  are not in the paper. Neither is the grader prompt for the SPOT evaluation.
- **No thresholds released.** The Light/Medium/High compute allocation rule is
  described conceptually only.
- **Both models proprietary.** "Advanced version of Gemini 2.5 Deep Think" and
  "Gemini 3.1 Pro" under the hood. The overall pipeline concept transfers to any
  frontier inference-scaling model, but the reported gains do not.
- **No source code, no evaluation harness, no benchmark artifacts.** SPOT itself
  is public (Son et al. 2505.11855) but the exact subset filtering rule is only
  described in prose.
- **Grader is itself an LLM.** They audit every autograder score by hand, which
  is honest, but the audit results are not reported separately from the headline
  detection rates.

**Relevance to pat-helper:** This is the source paper the whole project is
patterned on. The four-stage architecture (Segmenter → Adaptive Budgeter →
parallel Deep Review → search-grounded Global Synthesis) is transferable
essentially as-is at the pattern level. What has to be rebuilt from scratch for
this project's target domain (AI Policy / economic-impact papers rather than
CS/math proofs) is the *lens set* — PAT's math-proof orientation doesn't touch
the failure modes economists care about (causal identification, coalition
framing, prior-work grounding across a broader literature, etc.). See
`docs/convos/main/20260708_pat_kickoff_and_reframe.md` for the reframing.
