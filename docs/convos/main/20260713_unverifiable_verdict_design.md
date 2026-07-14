# Unverifiable Verdict Design (status review → circular-refutation fix)

**Date:** 2026-07-13 (session ran into 07-14 UTC)
**Branch:** main

## Summary

Session opened as a status review after the 07-12 paid v9 caching measurement.
Walking through the top open item — adversarial-verify calibration — we
dissected the confirmed circular-refutation kill from run 1
(`model-versions-removed`): the google verifier refuted a true reproducibility
finding by citing the paper's own "complete replication package" self-claims
as ground truth, when the planted defect had specifically removed the in-text
version details those claims vouch for. Two sibling refutations in the same
run (temperature-experiment design, API-cost assumptions) used the identical
"the replication package provides this" move, and a strengths finding
(anthropic+google) credited the paper with "specific model versions and
dates" that the defect had removed — the self-claim credulity leaks into the
positive side too.

Claude initially proposed that self-claims about external artifacts should
*downgrade severity* rather than refute. Dan pushed back ("why would we want
to downgrade this?") and the downgrade position collapsed under examination:
it imports the *referee's* epistemic position (can't check the package, so
discount by base rate) into an *author-facing* tool whose user can check the
artifact in minutes. Severity should encode how-bad-if-true; conditionality
is a separate dimension and blending it into severity destroys information
the schema deliberately keeps separate. The agreed design: a new verdict,
`unverifiable` — the finding stays in the main report at full severity,
tagged as conditional on an external artifact the author should check.

Code exploration for the plan surfaced two facts that shaped it: (1) the
verdict set is already three-way (`upheld/softened/refuted` — "softened"
exists), so this is a fourth verdict, not a third; (2) verification state
currently dies at synthesis — `SYNTHESIS_SCHEMA` has no `verified` field, so
merged findings reach the report with `verified=None`. For `unverifiable` to
be visible where it matters, synthesis needs an explicit passthrough.

## Topics Explored

- Anatomy of the run-1 circular refutation (verbatim refuter notes from
  `data/harness_out_v9/review_2026-07-11.md` demoted appendix)
- Whether google's "the paper already addresses this elsewhere" style is a
  per-model trait (3 of 3 sampled run-1 refutations were google) — noted,
  deliberately out of scope for this change
- Severity-vs-confidence semantics: downgrade rejected in favor of a
  status/verdict dimension
- Pipeline archaeology: verdict enum, verify prompt checklist (its check #2 —
  "does the paper already address this elsewhere" — is exactly the hook the
  circular refutation abused), synthesis schema gap, renderer routing

## Provisional Findings

- The circular-refutation failure mode is a *pattern* in run 1 (3 refutations
  sampled, all citing paper self-claims about the replication package), not a
  one-off reasoning slip
- Self-claim credulity also appears in at least one POSITIVE finding —
  worth remembering when calibrating against the demoted corpus
- The flooding concern (N boilerplate "it's-in-the-package" findings) is an
  aggregation problem for synthesis, not a severity problem — deferred until
  the known near-duplicate dedup wart is understood
- For a public (non-author) version of the tool, a base-rate discount on
  self-claims becomes legitimate again — per-audience config, not default

## Decisions Made

- Add a fourth verdict `unverifiable`: refutation must cite evidence
  demonstrated in the paper's text; a self-claim that material exists in an
  external artifact cannot refute a critique about that material
- `unverifiable` findings stay in the main report, severity intact, rendered
  with a "check external artifact" tag; only `refuted` demotes
- Synthesis passes `verified` state through (most-conservative-wins:
  unverifiable > softened > upheld)
- Validation before trusting it: verify-only rerun on run 1's refuted
  findings — the three self-claim kills should flip to `unverifiable`, kills
  grounded in actual in-text evidence should stay `refuted`
- Out of scope: refuter rotation (confounded with the prompt change),
  package-audit aggregation (synthesis dedup wart first)
- Plan: `docs/plans/main/20260713_unverifiable_verdict.md`

## Results

- Implementation landed in `77ffc4e` (55/55 tests green, +5 new): fourth
  verdict in schema + `_verify.md`, synthesis `verified` passthrough
  (most-conservative-wins), renderer "check external artifact" tag.
- Calibration replay (`harness/reverify.py`, 18/18 of run 1's refuted
  findings, same refuters, new prompt):
  `data/harness_out_v9/reverify_2026-07-14.md`. New verdicts: 13 refuted,
  3 unverifiable, 1 softened, 1 upheld.
  - `model-versions-removed` (the confirmed true-kill) → `unverifiable` ✓;
    run 1 would have scored 9/10.
  - Temperature-experiment kill → `softened` (in-report; refuter now
    concedes the specifics are absent from text, argues only severity).
  - API-cost kill stayed `refuted` — on re-read, its original refutation
    cited real in-text content (Sections 3.0/6.1), so the corpus had TWO
    pure self-claim kills, not three; both now survive to the main report.
  - 13/18 stayed refuted, including the strongest legitimate refutations
    (unanimity-vs-pairwise, max-barrier) — no mass overcorrection.
  - Scope expansion observed: two prior-work critiques about the accuracy
    of *cited external literature* (Svanberg, Davidson) flipped to
    `unverifiable` — epistemically defensible, wider than designed.
  - One unexplained flip refuted → `upheld` (vendor robot stats) — likely
    verifier stochasticity and/or the all-HIGH replay artifact (original
    severities unrecoverable: the renderer drops severity for appendix
    entries — known information-loss wart).
- Replay cache hit (google, 16 calls): 550k cached / 129k uncached input
  tokens (~81%).

## Follow-on design: source-check stage ("strict mode") — brainstormed same session

Dan proposed strict/relaxed modes: strict fires a checker that reads the
cited source and verifies the claim. Brainstorm (structured, incremental)
refined this into **stage 3.5: source-check**, implemented on branch
`source-check`:

- Reframed strict/relaxed from "different verdict rules" to "whether a
  resolution stage runs" — verdict semantics stay fixed for run-to-run
  comparability; `unverifiable` findings form the work queue
- Retrieval: **local-first** — author supplies a flat dir of extracted-text
  files; no PDFs in v1, no web in v1 (web fallback deferred)
- Generalizability fix (Dan's catch: "great for ME, but how flexible for
  others?"): match citations against a **content-built index** (cheap-model
  read of each file's head → `{authors, year, title}`, cached to a
  `sources_index.json` sidecar keyed by file hash), NOT against filename
  conventions — filenames become irrelevant
- Authority: **auto-resolve** — critique-confirmed → upheld;
  critique-contradicted → refuted (demoted with exonerating source quote);
  unresolved → stays unverifiable. Chosen over annotate-only and
  asymmetric-upgrade-only variants
- Two mechanical gates before any verdict is honored (both reuse
  quotecheck, zero API cost): source_quote must ground against the source
  text; checker-read identity must match the citation — an index error can
  cost a check, never cause a silent wrong-source demotion
- Checker = third provider in rotation (≠ finder, ≠ refuter) where possible
- Approach A (per-finding pipeline call, cache-shaped per source) chosen
  over agentic subagent (B) and per-source batching (C); C noted as a free
  later optimization, B's real advantage (web fallback) obtainable later
  without an agent loop
- Validation: fixture harness citation-mismatch defect + the two live
  specimens (Svanberg 2024, Davidson 2026) from the reverify replay,
  adjudicated by Dan
- Plan: `docs/active/source-check/plans/20260714_source_check_stage.md`
  (on the branch)

## Open Questions

- Does the new prompt overcorrect — flag as `unverifiable` critiques that a
  substantive in-text limitations passage genuinely does address? (First
  replay says no at n=18, but the cited-literature scope expansion needs a
  view: is "unverifiable" the right verdict for "does the citation say what
  the paper claims"?)
- Should the renderer include severity for demoted-appendix entries? (Its
  absence forced the all-HIGH replay; cheap fix, aids future calibration.)
- Ground-truth labels for the calibration corpus still need Dan's skim of
  the demoted appendices / extras (carried from 07-12)
- Refuter rotation: after the new prompt is measured, is google's aggressive
  refutation style still a live per-model concern?
- Output-side spend still unmeasured (carried)
